// E2E — Issue #1232 Scheibe 3b: geteilter LayoutTab-Organism (context="route")
// im Trip-Editor (Wetter-Metriken-Tab).
//
// Spec: docs/specs/modules/layout_tab_route.md
//
// Verhaltensnachweis der ACs als eingeloggter Nutzer gegen einen echten Trip
// (kein Mock). Deckt AC-1..AC-7 ab (AC-8/AC-9/AC-10 sind Diff-/Regressions-
// Review, kein eigener Test nötig).
//
// Ausführen:
//   cd frontend && npx playwright test e2e/layout-tab-route.spec.ts

import { test, expect, type Page } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_ID = 'e2e-layout-tab-route';
const OVERFLOW_TRIP_ID = 'e2e-layout-tab-route-overflow';

// Pre-normalisierter report_config-Blob — spiegelt EXAKT die Defaults, die
// `EditReportConfigSection`s Mount-Effekt aus einem leeren Objekt erzeugen
// würde. Ohne das (Nebenbefund, siehe Rückmeldung an PO): der Mount-Effekt
// überschreibt `reportConfig` bereits synchron beim ersten Render, bevor der
// Metriken-Katalog geladen ist — der dadurch ausgelöste `scheduleAutoSave()`
// würde einen PUT mit noch-leeren `buckets` schedulen und (falls keine
// weitere Bucket-Aktion diesen Debounce vorher ersetzt) die echten Metriken
// überschreiben. Mit vorab-normalisiertem Blob bleibt der Mount-Effekt ein
// No-Op (kein JSON-Diff → kein Auto-Save-Trigger).
const NORMALIZED_REPORT_CONFIG = {
	enabled: true,
	morning_enabled: true,
	evening_enabled: true,
	morning_time: '07:00:00',
	evening_time: '18:00:00',
	send_email: true,
	send_telegram: false,
	send_sms: false,
	multi_day_trend_morning: false,
	multi_day_trend_evening: true,
	multi_day_trend_reports: ['evening'],
	show_compact_summary: true,
	show_daylight: true,
	wind_exposition_min_elevation_m: null,
	show_stage_stats: true,
	show_quick_take_tags: true,
	show_stability: true,
	show_highlights: true,
	daily_summary_metrics: ['precipitation', 'wind', 'visibility', 'thunder'],
	show_metrics_summary: false,
	show_outlook: true,
	email_format: 'full',
	show_yesterday_comparison: true
};

async function createTrip(
	request: import('@playwright/test').APIRequestContext,
	id: string,
	metrics: Array<{ metric_id: string; order: number }>
) {
	await request.delete(`/api/trips/${id}`).catch(() => {});
	await request.post('/api/trips', {
		data: {
			id,
			name: 'E2E LayoutTab Route ' + id,
			report_config: NORMALIZED_REPORT_CONFIG,
			display_config: {
				metrics: metrics.map((m) => ({
					metric_id: m.metric_id,
					enabled: true,
					bucket: 'primary',
					order: m.order
				}))
			},
			stages: [
				{
					id: `${id}-stage-1`,
					name: 'Etappe 1',
					date: '2026-06-01',
					waypoints: [
						{ id: `${id}-wp-1`, name: 'Start', lat: 46.5, lon: 8.1, elevation_m: 1800 },
						{ id: `${id}-wp-2`, name: 'Ziel', lat: 46.6, lon: 8.2, elevation_m: 2400 }
					]
				}
			]
		}
	});
}

async function openMetricsTab(page: Page, id: string) {
	await page.goto(`/trips/${id}?tab=weather`);
	const weatherTabBtn = page.getByTestId('trip-detail-tab-weather');
	await expect(weatherTabBtn).toBeVisible({ timeout: 10_000 });
	await weatherTabBtn.click();
	const tab = page.getByTestId('weather-metrics-tab');
	await expect(tab).toBeVisible({ timeout: 10_000 });
	// Katalog-Fetch abwarten (initiales Render zeigt kurz einen leeren Zustand,
	// bevor `load()` den Katalog befüllt) — erst danach interagieren, sonst
	// überschreibt ein verfrühter Auto-Save-Trigger die Metriken mit [].
	await expect(tab.getByTestId('wm2-grundauswahl').locator('.toggle-btn').first()).toBeVisible({
		timeout: 10_000
	});
	return tab;
}

test.describe('Issue #1232 Scheibe 3b: LayoutTab (context="route")', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.setViewportSize({ width: 1440, height: 900 });
	});

	test.describe('Standard-Trip (3 Metriken)', () => {
		test.beforeAll(async ({ request }) => {
			await createTrip(request, TRIP_ID, [
				{ metric_id: 'temperature', order: 0 },
				{ metric_id: 'wind', order: 1 },
				{ metric_id: 'precipitation', order: 2 }
			]);
		});

		test.afterAll(async ({ request }) => {
			await request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
		});

		// ── AC-1/AC-2: Kanal-Wechsel schaltet Vorschau-Template, keine alten Tabs ──
		test('AC-1/AC-2: Kanal-Picker schaltet Vorschau Email→Telegram→SMS, alte interne Tabs sind weg', async ({
			page
		}) => {
			const tab = await openMetricsTab(page, TRIP_ID);
			const preview = tab.getByTestId('wm2-mail-preview');
			await expect(preview).toBeVisible();

			// Keine alten internen Kanal-Tab-Buttons mehr im Vorschau-Markup.
			await expect(preview.locator('button[data-channel]')).toHaveCount(0);

			await tab.getByTestId('channel-tab-email').click();
			await expect(preview.getByTestId('wm2-email-table')).toBeVisible();

			await tab.getByTestId('channel-tab-telegram').click();
			await expect(preview.getByTestId('wm2-telegram-bubble')).toBeVisible();
			await expect(preview.getByTestId('wm2-email-table')).toHaveCount(0);

			await tab.getByTestId('channel-tab-sms').click();
			await expect(preview.getByTestId('wm2-sms-line')).toBeVisible();
			await expect(preview.getByTestId('wm2-telegram-bubble')).toHaveCount(0);
		});

		// ── AC-3: DnD-Reihenfolge + Auto-Save + Reload-Beweis ──────────────────────
		test('AC-3: Drag & Drop ändert die Reihenfolge, Auto-Save persistiert über Reload', async ({
			page
		}) => {
			const tab = await openMetricsTab(page, TRIP_ID);
			await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle');

			const rows = tab.locator('[data-testid="wm2-reihenfolge-row"]');
			await expect(rows).toHaveCount(3);
			await expect(rows.first()).toHaveAttribute('data-metric-id', 'temperature');

			// "precipitation" (Position 3) vor "temperature" (Position 1) ziehen.
			const source = tab.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="precipitation"]');
			const target = tab.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="temperature"]');
			await source.dragTo(target);

			await expect(rows.first()).toHaveAttribute('data-metric-id', 'precipitation');

			// Email-Vorschau-Spaltenreihenfolge folgt der neuen Reihenfolge.
			await tab.getByTestId('channel-tab-email').click();
			const headerCells = tab.getByTestId('wm2-email-table').locator('thead th');
			await expect(headerCells.nth(1)).toHaveText(/Rain/i);

			await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle', {
				timeout: 5_000
			});

			await page.reload();
			await page.getByTestId('trip-detail-tab-weather').click();
			const reloadedRows = page
				.getByTestId('weather-metrics-tab')
				.locator('[data-testid="wm2-reihenfolge-row"]');
			await expect(reloadedRows.first()).toHaveAttribute('data-metric-id', 'precipitation', {
				timeout: 5_000
			});
		});

		// ── AC-6: reiner Kanalwechsel macht NICHT dirty, kein Auto-Save ────────────
		test('AC-6: Kanalwechsel allein löst KEINEN Auto-Save aus und bleibt nicht-dirty', async ({
			page
		}) => {
			const tab = await openMetricsTab(page, TRIP_ID);
			await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle');

			let putSeen = false;
			page.on('request', (req) => {
				if (req.method() === 'PUT' && req.url().includes('/weather-config')) putSeen = true;
			});

			await tab.getByTestId('channel-tab-telegram').click();
			await tab.getByTestId('channel-tab-sms').click();
			await tab.getByTestId('channel-tab-email').click();
			await page.waitForTimeout(1_200);

			expect(putSeen, 'Kanalwechsel darf keinen PUT /weather-config auslösen').toBe(false);
			await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle');
		});

		// ── AC-5 (Test-Plan-Punkt): Entfernen/Modus-Wechsel funktioniert weiterhin ──
		test('AC-5: "Aus"-Button entfernt eine Metrik weiterhin und löst Auto-Save aus', async ({
			page
		}) => {
			const tab = await openMetricsTab(page, TRIP_ID);
			await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle');

			const row = tab.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="wind"]');
			await expect(row).toBeVisible();
			await row.getByRole('button', { name: 'Aus' }).click();

			await expect(
				tab.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="wind"]')
			).toHaveCount(0);
			await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle', {
				timeout: 5_000
			});
		});

		// ── AC-7: Mobile FAB+Sheet folgt dem gewählten Kanal, kein horiz. Scroll ───
		test('AC-7: Mobile FAB öffnet Sheet mit der Vorschau des gewählten Kanals, kein horizontaler Scroll', async ({
			page
		}) => {
			await page.setViewportSize({ width: 390, height: 844 });
			const tab = await openMetricsTab(page, TRIP_ID);

			await tab.locator('[data-testid="channel-tab-telegram"]:visible').first().click();

			// F001-Fix (Staging-Adversary #1232-3b): FAB lag vor dem CSS-Fix hinter
			// der globalen BottomNav (z-index:50) — echter Klick jetzt möglich,
			// da der FAB per bottom-Offset (64px Nav-Höhe + safe-area + 16px) und
			// z-index:55 über die Nav gehoben wurde (WeatherMetricsTab.svelte).
			await page.locator('[data-testid="mobile-mail-fab"]:visible').first().click();
			const sheet = page.locator('[data-testid="mobile-mail-sheet"]:visible').first();
			await expect(sheet).toBeVisible();
			await expect(sheet.getByTestId('wm2-telegram-bubble')).toBeVisible();

			const overflowsX = await page.evaluate(
				() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 4
			);
			expect(overflowsX, 'Seite scrollt horizontal auf Mobile-Viewport').toBeFalsy();
		});

		// ── AC-8/Regression: SMS-Schwellwerte/Mail-Inhalt/Official-Toggle unverändert ─
		test('AC-8: SMS-Schwellwerte, Mail-Inhalt-Karte und Amtliche-Warnungen bleiben unverändert bedienbar', async ({
			page
		}) => {
			const tab = await openMetricsTab(page, TRIP_ID);
			await expect(tab.getByTestId('sms-thresholds')).toBeVisible();
			await expect(page.getByTestId('report-mail-content')).toBeVisible();
			await expect(page.getByTestId('report-show-official-alerts')).toBeVisible();
		});
	});

	test.describe('Overflow-Trip (9 Metriken, wandern-Preset)', () => {
		test.beforeAll(async ({ request }) => {
			await request.delete(`/api/trips/${OVERFLOW_TRIP_ID}`).catch(() => {});
			await request.post('/api/trips', {
				data: {
					id: OVERFLOW_TRIP_ID,
					name: 'E2E LayoutTab Route Overflow',
					report_config: NORMALIZED_REPORT_CONFIG,
					stages: [
						{
							id: 'lt-route-overflow-stage-1',
							name: 'Etappe 1',
							date: '2026-06-01',
							waypoints: [
								{ id: 'lt-route-overflow-wp-1', name: 'Start', lat: 46.5, lon: 8.1, elevation_m: 1800 },
								{ id: 'lt-route-overflow-wp-2', name: 'Ziel', lat: 46.6, lon: 8.2, elevation_m: 2400 }
							]
						}
					]
				}
			});
		});

		test.afterAll(async ({ request }) => {
			await request.delete(`/api/trips/${OVERFLOW_TRIP_ID}`).catch(() => {});
		});

		// ── AC-4: >8 aktive Metriken → Cut-Line + Overflow-Chip am Telegram-Button ──
		// Fresh-Eyes-Fund #1232-3b: `colCount` im route-Kontext zählt reine
		// Metriken (kein „+1" Label-Spalte wie im vergleich-Kontext) — Badge-
		// Overflow-Zahl, Cut-Line-Position und Vorschau-Hinweis-Zahl MÜSSEN
		// dieselbe Zahl zeigen (hier: 9 Metriken − 8 Budget = 1 Überlauf).
		test('AC-4: >8 aktive Metriken zeigen Cut-Line im Kanal Telegram + Overflow-Chip am Picker', async ({
			page
		}) => {
			const tab = await openMetricsTab(page, OVERFLOW_TRIP_ID);
			// "Wandern"-Preset hat 9 Metriken (> Telegram-Budget 8).
			await tab.getByTestId('weather-preset-pill-wandern').click();
			const confirmOk = page.getByTestId('preset-confirm-ok');
			if (await confirmOk.isVisible()) await confirmOk.click();

			const rows = tab.locator('[data-testid="wm2-reihenfolge-row"]');
			const totalMetrics = await rows.count();
			expect(totalMetrics).toBe(9);
			const tgBudget = 8;
			const expectedOverflow = totalMetrics - tgBudget; // 1

			// Cut-Line erscheint NICHT im Kanal Email (kein Limit).
			await tab.getByTestId('channel-tab-email').click();
			await expect(tab.locator('[data-testid="wm2-cut-line"]')).toHaveCount(0);

			// Cut-Line erscheint im Kanal Telegram an Position 9 (nach 8 Zeilen).
			const telegramBtn = tab.getByTestId('channel-tab-telegram');
			await telegramBtn.click();
			const cutLine = tab.locator('[data-testid="wm2-cut-line"]');
			await expect(cutLine).toBeVisible();
			await expect(cutLine).toContainText('Telegram');
			await expect(cutLine).toContainText(String(tgBudget));

			// Overflow-Chip am Telegram-Button: 9 Metriken > 8 Budget → "−1"
			// (NICHT "−2" — das wäre die vergleich-Konvention mit Label-Spalte).
			await expect(telegramBtn).toContainText(`−${expectedOverflow}`);

			// Zahlen-Konsistenz: Badge-Overflow == Vorschau-Hinweis-Zahl.
			// Die Vorschau zeigt bei Kanal Telegram denselben Überlauf-Wert wie
			// Cut-Line/Badge (kein zweiter, abweichender Zähler im UI).
			const bubble = tab.getByTestId('wm2-mail-preview').getByTestId('wm2-telegram-bubble');
			await expect(bubble).toBeVisible();
			const overflowWord = expectedOverflow === 1 ? 'Metrik passt' : 'Metriken passen';
			await expect(bubble).toContainText(`${expectedOverflow} ${overflowWord} nicht in die Tabelle`);

			// LTCapNote spiegelt dieselbe Metriken-Zählung (kein "Label +"-Zusatz
			// im route-Kontext, siehe LTCapNote.svelte hasLabelColumn-Prop).
			const capNote = page.locator('[data-testid="lt-cap-note"]:visible').first();
			await expect(capNote).toContainText(`${totalMetrics} Metriken`);
			await expect(capNote).not.toContainText('Label +');
		});
	});
});
