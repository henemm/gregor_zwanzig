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
// `dragDndZoneItem` ist seit #1771 S1 geteilt (war hier lokal kopiert) und
// wartet auf das echte `finalize`-Ereignis statt auf eine feste Frist.
import { login, dragDndZoneItem } from './helpers.js';

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
	// SvelteKit liefert die Tab-Leiste server-gerendert VOR der Hydration aus —
	// ein Klick, der vor dem Attachen der Event-Listener ankommt, geht spurlos
	// verloren (#1771; Muster aus compare-hub-inline-edit.spec.ts).
	await page.waitForLoadState('networkidle');
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

		// ── AC-1/AC-2 (Issue #1719 S3, umgedreht): Kanal-Picker schaltet den
		// aktiven Kanal — die Live-Vorschau ("So kommt es an") ist ersatzlos
		// entfernt (PO-Entscheid, WeatherV2MailPreview.svelte gelöscht). Dieser
		// Test prüfte zuvor ausschließlich das Umschalten der Vorschau-Tabelle;
		// ersetzt durch eine Prüfung, dass der Kanal-Picker weiterhin den
		// aktiven Kanal umschaltet und der Reihenfolge-Editor dabei sichtbar
		// bleibt. Absenz der Vorschau ist der eigentliche Nachweis dafür im
		// RED-Bündel `wetter-metriken-vorschau-entfernt.staging.spec.ts` (AC-1).
		test('AC-1/AC-2: Kanal-Picker schaltet den aktiven Kanal Email→Telegram→SMS, keine Vorschau mehr im DOM', async ({
			page
		}) => {
			const tab = await openMetricsTab(page, TRIP_ID);
			await expect(tab.getByTestId('wm2-mail-preview')).toHaveCount(0);

			const emailBtn = tab.getByTestId('channel-tab-email');
			const telegramBtn = tab.getByTestId('channel-tab-telegram');
			const smsBtn = tab.getByTestId('channel-tab-sms');

			await emailBtn.click();
			await expect(emailBtn).toHaveClass(/active/);
			await expect(tab.getByTestId('wm2-reihenfolge')).toBeVisible();

			await telegramBtn.click();
			await expect(telegramBtn).toHaveClass(/active/);
			await expect(emailBtn).not.toHaveClass(/active/);
			await expect(tab.getByTestId('wm2-reihenfolge')).toBeVisible();

			await smsBtn.click();
			await expect(smsBtn).toHaveClass(/active/);
			await expect(telegramBtn).not.toHaveClass(/active/);
			await expect(tab.getByTestId('wm2-reihenfolge')).toBeVisible();
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
			await dragDndZoneItem(page, source, target);

			await expect(rows.first()).toHaveAttribute('data-metric-id', 'precipitation');

			// Issue #1719 S3: die Email-Vorschau-Spaltenreihenfolge-Teilprüfung
			// entfällt — WeatherV2MailPreview.svelte (wm2-email-table) ist mit der
			// Live-Vorschau ersatzlos gelöscht (PO-Entscheid). Der Reload-Beweis
			// unten bleibt der Kern dieses Tests.
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

		// ── AC-5 (Issue #1719 S3, umgedreht — ADR-0050 Regel 4): "Aus ist ein
		// Zustand, keine Löschung". Diese Datei kodierte bisher `toHaveCount(0)`
		// nach "Aus" — das WAR das von ADR-0050 verworfene Verhalten. Jetzt:
		// die Metrik verschwindet aus der aktiven Liste, bleibt aber sichtbar in
		// der "Aus in diesem Kanal"-Gruppe. Vollständiger Klickpfad (Aus →
		// Reload → Aus-Gruppe → Ein → wieder aktiv) im RED-Bündel
		// `kanal-abwahl-bleibt-reversibel.staging.spec.ts` (AC-7).
		test('AC-5: "Aus"-Button entfernt eine Metrik aus der aktiven Liste — sie landet in der Aus-Gruppe, keine Löschung', async ({
			page
		}) => {
			const tab = await openMetricsTab(page, TRIP_ID);
			await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle');

			const row = tab.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="wind"]');
			await expect(row).toBeVisible();
			await row.getByRole('button', { name: 'Aus' }).click();

			await expect(
				tab.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="wind"]'),
				'"wind" muss aus der AKTIVEN Liste verschwinden'
			).toHaveCount(0);
			await expect(
				tab.getByTestId('wm2-aus-gruppe').locator('[data-testid="wm2-aus-row"][data-metric-id="wind"]'),
				'ADR-0050 Regel 4: "wind" darf nicht physisch gelöscht werden — es muss in der Aus-Gruppe stehen'
			).toBeVisible();
			await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle', {
				timeout: 5_000
			});
		});

		// ── AC-7 (Issue #1719 S3, umgedreht): Mobile-FAB + Bottom-Sheet ist mit
		// der Live-Vorschau ersatzlos entfernt (PO-Entscheid) — Nachweis, dass
		// beides aus dem DOM verschwunden ist UND die Seite auf Mobil trotzdem
		// bedienbar bleibt (kein horizontaler Scroll).
		test('AC-7: kein Mobile-FAB/Sheet mehr, Kanal-Wechsel bleibt auf Mobil bedienbar, kein horizontaler Scroll', async ({
			page
		}) => {
			await page.setViewportSize({ width: 390, height: 844 });
			const tab = await openMetricsTab(page, TRIP_ID);

			await expect(page.getByTestId('mobile-mail-fab')).toHaveCount(0);
			await expect(page.getByTestId('mobile-mail-sheet')).toHaveCount(0);

			await tab.locator('[data-testid="channel-tab-telegram"]:visible').first().click();
			await expect(tab.getByTestId('wm2-reihenfolge')).toBeVisible();

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

		// ── AC-4/AC-3 (Issue #1719 S3, umgedreht): >7 aktive Metriken → Cut-Line +
		// Overflow-Chip am Telegram-Button. Telegram-Budget von 8 auf 7 korrigiert
		// (die 8. Backend-Spalte ist die Uhrzeit, keine Metrik —
		// channel_layout.py:110). Die "Zahlen-Konsistenz mit der Vorschau"-Prüfung
		// entfällt: WeatherV2MailPreview.svelte ist mit der Live-Vorschau
		// ersatzlos gelöscht (PO-Entscheid) — Cut-Line/Badge/LTCapNote bleiben die
		// einzigen (weiterhin konsistenten) Zähler.
		test('AC-4/AC-3: >7 aktive Metriken zeigen Cut-Line im Kanal Telegram + Overflow-Chip am Picker', async ({
			page
		}) => {
			const tab = await openMetricsTab(page, OVERFLOW_TRIP_ID);
			// "Wandern"-Preset hat 9 Metriken (> Telegram-Budget 7).
			await tab.getByTestId('weather-preset-pill-wandern').click();
			const confirmOk = page.getByTestId('preset-confirm-ok');
			if (await confirmOk.isVisible()) await confirmOk.click();

			const rows = tab.locator('[data-testid="wm2-reihenfolge-row"]');
			const totalMetrics = await rows.count();
			expect(totalMetrics).toBe(9);
			const tgBudget = 7;
			const expectedOverflow = totalMetrics - tgBudget; // 2

			// Cut-Line erscheint NICHT im Kanal Email (kein Limit).
			await tab.getByTestId('channel-tab-email').click();
			await expect(tab.locator('[data-testid="wm2-cut-line"]')).toHaveCount(0);

			// Cut-Line erscheint im Kanal Telegram an Position 8 (nach 7 Zeilen).
			const telegramBtn = tab.getByTestId('channel-tab-telegram');
			await telegramBtn.click();
			const cutLine = tab.locator('[data-testid="wm2-cut-line"]');
			await expect(cutLine).toBeVisible();
			await expect(cutLine).toContainText('Telegram');
			await expect(cutLine).toContainText(String(tgBudget));

			// Overflow-Chip am Telegram-Button: 9 Metriken > 7 Budget → "−2"
			// (NICHT "−3" — das wäre die vergleich-Konvention mit Label-Spalte).
			await expect(telegramBtn).toContainText(`−${expectedOverflow}`);

			// LTCapNote spiegelt dieselbe Metriken-Zählung (kein "Label +"-Zusatz
			// im route-Kontext, siehe LTCapNote.svelte hasLabelColumn-Prop).
			const capNote = page.locator('[data-testid="lt-cap-note"]:visible').first();
			await expect(capNote).toContainText(`${totalMetrics} Metriken`);
			await expect(capNote).not.toContainText('Label +');
		});
	});
});

// ─────────────────────────────────────────────────────────────────────────────
// Issue #1575 Scheibe 3: die Kanal-Reiter tragen eigene Daten. Ergaenzt die
// AC-6-Garantie oben (reiner Kanal-WECHSEL bleibt clean) um ihre zweite
// Haelfte — ein Kanal-EDIT macht dirty und schreibt NUR den aktiven Kanal.
// Spec: docs/specs/modules/fix_1575_channel_metric_selection.md § AC-2/AC-3
// ─────────────────────────────────────────────────────────────────────────────

const CHANNEL_TRIP_ID = 'e2e-1575-channel-metrics';

const PRE_EMAIL_LAYOUT = [
	{ metric_id: 'temperature', enabled: true, use_friendly_format: true, bucket: 'primary', order: 0 },
	{ metric_id: 'wind', enabled: true, use_friendly_format: true, bucket: 'primary', order: 1 }
];
const PRE_TELEGRAM_LAYOUT = [
	{ metric_id: 'precipitation', enabled: true, use_friendly_format: true, bucket: 'primary', order: 0 }
];

test.describe('Issue #1575 Scheibe 3: kanal-eigene Metrik-Auswahl (context="route")', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.setViewportSize({ width: 1440, height: 900 });
	});

	test.beforeAll(async ({ request }) => {
		await createTrip(request, CHANNEL_TRIP_ID, [
			{ metric_id: 'temperature', order: 0 },
			{ metric_id: 'wind', order: 1 },
			{ metric_id: 'precipitation', order: 2 }
		]);
		// Vorbelegte, unterschiedliche Kanal-Layouts (AC-3-Ausgangslage).
		await request.put(`/api/trips/${CHANNEL_TRIP_ID}/weather-config`, {
			data: {
				metrics: [
					{ metric_id: 'temperature', enabled: true, bucket: 'primary', order: 0 },
					{ metric_id: 'wind', enabled: true, bucket: 'primary', order: 1 },
					{ metric_id: 'precipitation', enabled: true, bucket: 'primary', order: 2 }
				],
				channel_layouts: { email: PRE_EMAIL_LAYOUT, telegram: PRE_TELEGRAM_LAYOUT }
			}
		});
	});

	test.afterAll(async ({ request }) => {
		await request.delete(`/api/trips/${CHANNEL_TRIP_ID}`).catch(() => {});
	});

	test('AC-2/AC-3: SMS-Edit wirkt nur auf SMS und laesst email/telegram unveraendert', async ({
		page,
		request
	}) => {
		const tab = await openMetricsTab(page, CHANNEL_TRIP_ID);
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle');

		// SMS-Reiter startet ohne eigenen Eintrag → globale Auswahl (3 Metriken).
		await tab.getByTestId('channel-tab-sms').click();
		const rows = tab.locator('[data-testid="wm2-reihenfolge-row"]');
		await expect(rows).toHaveCount(3);

		// Copy-on-write: der erste Edit legt den SMS-Eintrag als Kopie an (AC-2).
		await tab
			.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="wind"]')
			.getByRole('button', { name: 'Aus' })
			.click();
		await expect(rows).toHaveCount(2);
		// Issue #1719 S3 (ADR-0050 Regel 4, umgedreht): "wind" verschwindet aus
		// der aktiven Liste, ist aber NICHT gelöscht — es steht in der
		// "Aus in diesem Kanal"-Gruppe.
		await expect(
			tab.getByTestId('wm2-aus-gruppe').locator('[data-testid="wm2-aus-row"][data-metric-id="wind"]')
		).toBeVisible();
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});

		// AC-3: die gespeicherten Layouts der anderen Kanaele ueberleben den Save.
		const trip = await (await request.get(`/api/trips/${CHANNEL_TRIP_ID}`)).json();
		const layouts = trip.display_config?.channel_layouts ?? {};
		expect(
			layouts.email?.filter((m: { enabled: boolean }) => m.enabled).map((m: { metric_id: string }) => m.metric_id)
		).toEqual(['temperature', 'wind']);
		expect(
			layouts.telegram?.filter((m: { enabled: boolean }) => m.enabled).map((m: { metric_id: string }) => m.metric_id)
		).toEqual(['precipitation']);
		expect(
			layouts.sms?.filter((m: { enabled: boolean }) => m.enabled).map((m: { metric_id: string }) => m.metric_id)
		).not.toContain('wind');

		// AC-4/AC-5-Vorstufe: nach dem Reload zeigt jeder Reiter seinen Stand.
		await page.reload();
		await page.getByTestId('trip-detail-tab-weather').click();
		const reloaded = page.getByTestId('weather-metrics-tab');
		await reloaded.getByTestId('channel-tab-email').click();
		await expect(reloaded.locator('[data-testid="wm2-reihenfolge-row"]')).toHaveCount(2);
		await reloaded.getByTestId('channel-tab-sms').click();
		await expect(reloaded.locator('[data-testid="wm2-reihenfolge-row"]')).toHaveCount(2);
		await expect(
			reloaded.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="wind"]'),
			'"wind" darf nach dem Reload nicht mehr in der AKTIVEN Liste stehen'
		).toHaveCount(0);
		// Issue #1719 S3 (ADR-0050 Regel 4, umgedreht): "wind" bleibt auch nach
		// dem Reload sichtbar — persistiert in der Aus-Gruppe, nicht gelöscht.
		await expect(
			reloaded.getByTestId('wm2-aus-gruppe').locator('[data-testid="wm2-aus-row"][data-metric-id="wind"]'),
			'"wind" muss nach dem Reload weiterhin in der Aus-Gruppe stehen (ADR-0050 Regel 4)'
		).toBeVisible();
	});
});
