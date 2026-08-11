// E2E (Staging) — Issue #1719 Scheibe 3: echte Platzgrenzen im Trip-Editor.
//
// Spec: docs/specs/modules/fix_1719_s3_aus_ist_ein_zustand.md
//   AC-3 (Telegram-Kapplinie nach der 7. Metrik), AC-4 (SMS nennt 160
//   Zeichen, keine Spaltengrenze), AC-8 (global abgewählte Metrik erscheint
//   in keinem Kanal-Reiter — Playwright-Anteil, Unit-Anteil bereits in
//   channelOffGroupListBuilding.test.ts). Zuordnungstabelle: Commit 3da43cad
//   (Bündel `kanal-grenzen-und-hinweise`).
//
// SCHREIBT NUR — wird in dieser RED-Phase NICHT ausgeführt (Testauflage PO,
// "Das ist KRITISCH!!!!!" — der Lauf gehört in die GREEN-/Verifikationsphase).
//
// Vorbilder: metrik-grundauswahl-schneidet-kanal.staging.spec.ts (S2,
// Dreier-Struktur), layout-tab-route.spec.ts (Overflow-Trip-Testaufbau,
// AC-4 "9 Metriken > Telegram-Budget" — dort noch mit dem FALSCHEN Budget 8;
// dieser Test verankert das korrigierte Budget 7).
//
// Ausführen (gegen Staging, aus frontend/, NACH GREEN):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=e2e/playwright.kanal-grenzen-und-hinweise.staging.config.ts

import { test, expect, type APIRequestContext, type Page } from '@playwright/test';

const TRIP_ID = 'e2e-1719-s3-kanal-grenzen';

const REPORT_CONFIG = {
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

// 9 global aktive Metriken (> Telegram-Budget 7) + EINE global abgewählte
// ("wind_direction", AC-8-Ziel-Metrik: enabled:false, kein bucket).
const ACTIVE_METRICS = [
	'temperature',
	'wind',
	'gust',
	'precipitation',
	'thunder',
	'visibility',
	'humidity',
	'dewpoint',
	'cloud_total'
];
const OFF_METRIC = 'wind_direction';

async function createTrip(request: APIRequestContext) {
	await request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	await request.post('/api/trips', {
		data: {
			id: TRIP_ID,
			name: 'E2E #1719 S3 Kanal-Grenzen',
			report_config: REPORT_CONFIG,
			display_config: {
				metrics: [
					...ACTIVE_METRICS.map((metric_id, order) => ({
						metric_id,
						enabled: true,
						bucket: 'primary',
						order
					})),
					{ metric_id: OFF_METRIC, enabled: false }
				]
			},
			stages: [
				{
					id: `${TRIP_ID}-stage-1`,
					name: 'Etappe 1',
					date: new Date().toISOString().slice(0, 10),
					waypoints: [
						{ id: `${TRIP_ID}-wp-1`, name: 'Start', lat: 46.5, lon: 8.1, elevation_m: 1800 },
						{ id: `${TRIP_ID}-wp-2`, name: 'Ziel', lat: 46.6, lon: 8.2, elevation_m: 2400 }
					]
				}
			]
		}
	});
}

async function openMetricsTab(page: Page) {
	await page.goto(`/trips/${TRIP_ID}?tab=weather`);
	const weatherTabBtn = page.getByTestId('trip-detail-tab-weather');
	await expect(weatherTabBtn).toBeVisible({ timeout: 10_000 });
	await weatherTabBtn.click();
	const tab = page.getByTestId('weather-metrics-tab');
	await expect(tab).toBeVisible({ timeout: 10_000 });
	await expect(tab.getByTestId('wm2-grundauswahl').locator('.toggle-btn').first()).toBeVisible({
		timeout: 10_000
	});
	return tab;
}

test.describe('Issue #1719 S3: echte Platzgrenzen im Trip-Editor', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1440, height: 900 });
	});

	test.beforeAll(async ({ request }) => {
		await createTrip(request);
	});

	test.afterAll(async ({ request }) => {
		await request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	});

	test('AC-3: bei 9 aktiven Metriken sitzt die Telegram-Kapplinie nach der 7., Überlauf-Chip nennt 2', async ({
		page
	}) => {
		const tab = await openMetricsTab(page);
		const rows = tab.locator('[data-testid="wm2-reihenfolge-row"]');
		await expect(rows).toHaveCount(9);

		const telegramBtn = tab.getByTestId('channel-tab-telegram');
		await telegramBtn.click();
		const cutLine = tab.locator('[data-testid="wm2-cut-line"]');
		await expect(cutLine).toBeVisible();
		await expect(cutLine).toContainText('Telegram');
		await expect(
			cutLine,
			'AC-3 FAIL: die Kapplinie muss "7" nennen (nicht mehr "8" — die 8. Spalte ist die Uhrzeit)'
		).toContainText('7');

		await expect(
			telegramBtn,
			'AC-3 FAIL: Überlauf-Chip am Telegram-Tab muss "−2" zeigen (9 aktive Metriken − 7 Budget)'
		).toContainText('−2');
	});

	test('AC-4: SMS-Reiter nennt die Zeichengrenze 160, nicht "—" und nicht "140", keine Spaltengrenze', async ({
		page
	}) => {
		const tab = await openMetricsTab(page);
		const smsBtn = tab.getByTestId('channel-tab-sms');
		await expect(
			smsBtn.locator('.lt-ch-badge'),
			'AC-4 FAIL: der SMS-Chip muss "160" zeigen, nicht "—" (der heutige Spalten-Sentinel-Fallback)'
		).toContainText('160');

		await smsBtn.click();
		const capNote = page.locator('[data-testid="lt-cap-note"]:visible').first();
		await expect(capNote).toContainText('160');
		await expect(
			capNote,
			'AC-4 FAIL: der SMS-Hinweistext darf nicht "140" nennen (falscher Wert, gehört zum Vergleichspfad)'
		).not.toContainText('140');
		await expect(
			capNote,
			'AC-4 FAIL: der SMS-Hinweistext darf keine Spaltengrenze behaupten'
		).not.toContainText(/max\s*\d+\s*Spalten/i);
	});

	test('AC-8: eine in der Grundauswahl abgewählte Metrik erscheint im Kanal-Reiter weder aktiv noch in der Aus-Gruppe', async ({
		page
	}) => {
		const tab = await openMetricsTab(page);

		// Ziel-Metrik ist bereits GLOBAL abgewählt (OFF_METRIC) -- ein Kanal kann
		// sie nicht zurückholen (ADR-0050 Regel 1/2).
		await tab.getByTestId('channel-tab-sms').click();
		await expect(
			tab.locator(`[data-testid="wm2-reihenfolge-row"][data-metric-id="${OFF_METRIC}"]`),
			'AC-8 FAIL: eine global abgewählte Metrik darf im Kanal-Reiter nicht aktiv erscheinen'
		).toHaveCount(0);
		await expect(
			tab.getByTestId('wm2-aus-gruppe').locator(`[data-testid="wm2-aus-row"][data-metric-id="${OFF_METRIC}"]`),
			'AC-8 FAIL: eine global abgewählte Metrik darf auch nicht in der Aus-Gruppe des Kanals auftauchen'
		).toHaveCount(0);

		// Dasselbe im Telegram-Reiter (die Regel gilt kanalunabhängig).
		await tab.getByTestId('channel-tab-telegram').click();
		await expect(
			tab.locator(`[data-testid="wm2-reihenfolge-row"][data-metric-id="${OFF_METRIC}"]`)
		).toHaveCount(0);
		await expect(
			tab.getByTestId('wm2-aus-gruppe').locator(`[data-testid="wm2-aus-row"][data-metric-id="${OFF_METRIC}"]`)
		).toHaveCount(0);
	});
});
