// E2E (Staging) — Issue #1719 Scheibe 3, Block C: "Aus" ist ein ZUSTAND,
// keine Löschung (ADR-0050 Regel 4).
//
// Spec: docs/specs/modules/fix_1719_s3_aus_ist_ein_zustand.md AC-7, AC-9, AC-11.
// ADR: docs/adr/0050-metrik-kaskade-verfeinerung-nicht-ersetzung.md Regel 3+4.
//
// Kontrakt fuer GREEN — neue Test-IDs (existieren heute NICHT, RED-Phase
// definiert sie als Nachweis-Ziel, Spec Abschnitt 2 "Darstellung von 'Aus'"):
//   data-testid="wm2-aus-gruppe"   Container "Aus in diesem Kanal", unterhalb
//                                   der sortierbaren wm2-reihenfolge-Liste
//   data-testid="wm2-aus-row"      je abgewählte Metrik, data-metric-id={id}
//   Button-Rolle "Ein" innerhalb einer wm2-aus-row (Gegenstück zum
//   bestehenden "Aus"-Button in WeatherV2Reihenfolge.svelte:108-115)
//
// SCHREIBT NUR — wird in dieser RED-Phase NICHT ausgeführt (Testauflage PO,
// "Das ist KRITISCH!!!!!" — der Lauf gehört in die GREEN-/Verifikationsphase).
//
// Vorbilder: metrik-grundauswahl-schneidet-kanal.staging.spec.ts (S2,
// Dreier-Struktur), layout-tab-route.spec.ts (Testaufbau, wm2-*-Konventionen).
//
// Ausführen (gegen Staging, aus frontend/, NACH GREEN):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=e2e/playwright.kanal-abwahl-bleibt-reversibel.staging.config.ts

import { test, expect, type APIRequestContext, type Page } from '@playwright/test';

const TRIP_AC7 = 'e2e-1719-s3-aus-reversibel';
const TRIP_AC9 = 'e2e-1719-s3-sofort-geschnitten';
const TRIP_AC11 = 'e2e-1719-s3-anwahl-schreibt-nicht-durch';

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

async function createTrip(request: APIRequestContext, id: string) {
	await request.delete(`/api/trips/${id}`).catch(() => {});
	await request.post('/api/trips', {
		data: {
			id,
			name: `E2E #1719 S3 ${id}`,
			report_config: REPORT_CONFIG,
			display_config: {
				metrics: [
					{ metric_id: 'temperature', enabled: true, bucket: 'primary', order: 0 },
					{ metric_id: 'wind', enabled: true, bucket: 'primary', order: 1 },
					{ metric_id: 'precipitation', enabled: true, bucket: 'primary', order: 2 }
				]
			},
			stages: [
				{
					id: `${id}-stage-1`,
					name: 'Etappe 1',
					date: new Date().toISOString().slice(0, 10),
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
	await expect(tab.getByTestId('wm2-grundauswahl').locator('.toggle-btn').first()).toBeVisible({
		timeout: 10_000
	});
	return tab;
}

test.describe('Issue #1719 S3 Block C: "Aus" ist ein Zustand', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1440, height: 900 });
	});

	test.afterAll(async ({ request }) => {
		await request.delete(`/api/trips/${TRIP_AC7}`).catch(() => {});
		await request.delete(`/api/trips/${TRIP_AC9}`).catch(() => {});
		await request.delete(`/api/trips/${TRIP_AC11}`).catch(() => {});
	});

	test('AC-7: abgewählte Metrik verschwindet nicht, sondern landet in der Aus-Gruppe und ist von dort reaktivierbar — auch nach Reload', async ({
		page,
		request
	}) => {
		await createTrip(request, TRIP_AC7);
		const tab = await openMetricsTab(page, TRIP_AC7);
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle');

		await tab.getByTestId('channel-tab-sms').click();
		const windRow = tab.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="wind"]');
		await expect(windRow).toBeVisible();
		await windRow.getByRole('button', { name: 'Aus' }).click();

		// "wind" verschwindet aus der aktiven Liste, ist aber NICHT weg.
		await expect(
			tab.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="wind"]'),
			'AC-7 FAIL: "wind" darf nach "Aus" nicht aus der aktiven Liste verschwinden ohne Ersatz'
		).toHaveCount(0);
		const ausGruppe = tab.getByTestId('wm2-aus-gruppe');
		await expect(ausGruppe, 'AC-7 FAIL: "Aus in diesem Kanal"-Gruppe fehlt komplett').toBeVisible();
		const windAusRow = ausGruppe.locator('[data-testid="wm2-aus-row"][data-metric-id="wind"]');
		await expect(
			windAusRow,
			'AC-7 FAIL: "wind" muss nach der Abwahl in der Aus-Gruppe erscheinen'
		).toBeVisible();

		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});

		// Persistiert über Reload.
		await page.reload();
		await page.getByTestId('trip-detail-tab-weather').click();
		const reloaded = page.getByTestId('weather-metrics-tab');
		await reloaded.getByTestId('channel-tab-sms').click();
		const reloadedAusRow = reloaded
			.getByTestId('wm2-aus-gruppe')
			.locator('[data-testid="wm2-aus-row"][data-metric-id="wind"]');
		await expect(
			reloadedAusRow,
			'AC-7 FAIL: "wind" muss auch nach dem Reload in der Aus-Gruppe stehen'
		).toBeVisible();

		// Von dort reaktivierbar.
		await reloadedAusRow.getByRole('button', { name: 'Ein' }).click();
		await expect(
			reloaded.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="wind"]'),
			'AC-7 FAIL: "wind" muss nach "Ein" wieder in der aktiven Liste stehen'
		).toBeVisible();
		await expect(
			reloaded.getByTestId('wm2-aus-gruppe').locator('[data-testid="wm2-aus-row"][data-metric-id="wind"]'),
			'AC-7 FAIL: "wind" darf nach "Ein" nicht mehr in der Aus-Gruppe stehen'
		).toHaveCount(0);
	});

	test('AC-9: eine globale Abwahl schneidet den bereits geöffneten SMS-Reiter SOFORT, ohne Reload', async ({
		page,
		request
	}) => {
		await createTrip(request, TRIP_AC9);
		const tab = await openMetricsTab(page, TRIP_AC9);
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle');

		// SMS-Reiter öffnen -> copy-on-write legt die Kanal-Kopie an, "precipitation" ist dort aktiv.
		await tab.getByTestId('channel-tab-sms').click();
		await expect(
			tab.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="precipitation"]')
		).toBeVisible();

		// Grundauswahl: "precipitation" global abwählen (kein Reload).
		const precipToggle = tab.locator('[data-testid="wm2-grundauswahl"] .toggle-btn[title="Niederschlag"]');
		await expect(precipToggle).toHaveClass(/\bon\b/);
		await precipToggle.click();

		// Zurück in den bereits geöffneten SMS-Reiter: "precipitation" ist SOFORT weg
		// (weder aktiv noch in der Aus-Gruppe — ADR-0050 Regel 1/2/3, AC-8).
		await tab.getByTestId('channel-tab-sms').click();
		await expect(
			tab.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="precipitation"]'),
			'AC-9 FAIL: eine globale Abwahl muss den geöffneten SMS-Reiter sofort schneiden, ohne Reload'
		).toHaveCount(0);
		await expect(
			tab.getByTestId('wm2-aus-gruppe').locator('[data-testid="wm2-aus-row"][data-metric-id="precipitation"]'),
			'AC-9 FAIL: eine GLOBAL abgewählte Metrik darf auch nicht in der Aus-Gruppe des Kanals auftauchen'
		).toHaveCount(0);
	});

	test('AC-11: eine im SMS-Reiter bewusst abgewählte Metrik bleibt abgewählt, wenn die Grundauswahl aus- und wieder eingeschaltet wird', async ({
		page,
		request
	}) => {
		await createTrip(request, TRIP_AC11);
		const tab = await openMetricsTab(page, TRIP_AC11);
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle');

		// SMS-Reiter: "temperature" bewusst abwählen -> landet in der Aus-Gruppe.
		await tab.getByTestId('channel-tab-sms').click();
		const tempRow = tab.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="temperature"]');
		await expect(tempRow).toBeVisible();
		await tempRow.getByRole('button', { name: 'Aus' }).click();
		await expect(
			tab.getByTestId('wm2-aus-gruppe').locator('[data-testid="wm2-aus-row"][data-metric-id="temperature"]')
		).toBeVisible();
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});

		// Grundauswahl: "temperature" aus- und wieder einschalten (bleibt global aktiv).
		const tempToggle = tab.locator('[data-testid="wm2-grundauswahl"] .toggle-btn[title="Temperatur"]');
		await expect(tempToggle).toHaveClass(/\bon\b/);
		await tempToggle.click();
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});
		await tempToggle.click();
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});

		// SMS-Reiter: "temperature" bleibt abgewählt — die Anwahl in der Grundauswahl
		// schreibt NICHT in den Kanal-Override durch (Spec Abschnitt 4, "keine Bevormundung").
		await tab.getByTestId('channel-tab-sms').click();
		await expect(
			tab.locator('[data-testid="wm2-reihenfolge-row"][data-metric-id="temperature"]'),
			'AC-11 FAIL: die Anwahl in der Grundauswahl darf den SMS-Kanal-Override nicht überschreiben'
		).toHaveCount(0);
		await expect(
			tab.getByTestId('wm2-aus-gruppe').locator('[data-testid="wm2-aus-row"][data-metric-id="temperature"]'),
			'AC-11 FAIL: "temperature" muss weiterhin in der SMS-Aus-Gruppe stehen'
		).toBeVisible();
	});
});
