// E2E — Issue #1232 Scheibe 1: geteilter Versand-Organism (VersandTab,
// context="route") im Trip-Editor.
//
// Spec: docs/specs/modules/versand_tab_route.md
// Workflow: feat-1232-versand-tab-route
//
// Ziel-Oberfläche: Trip-Detail-Seite, Tab „Versand" (value=briefings). Die
// komplette Alert-Zustellung (Cooldown, Stille Stunden, Beispiel-Warnung) ist
// aus dem Alerts-Tab in den Versand-Tab umgezogen (AC-1, AC-6); Kanäle und
// Zeitplan bleiben dort (AC-2, AC-3, AC-7).
//
// Issue #1258 Scheibe S3 (D5, AC-13/AC-14): die Alert-Zustellungs-Sektion
// zog ATOMAR ein weiteres Mal um — aus dem Versand-Tab (value=briefings) in
// den neuen geteilten Alarme-Tab (value=alarme, Panel
// trip-detail-panel-alarme). Versand-Panel enthält seither NUR noch Kanäle
// des geplanten Briefings, Zeitplan und Laufzeit-Link (AC-14). Diese Datei
// zieht die betroffenen Selektoren/Klickpfade entsprechend um — der
// Kanal-/Zeitplan-Teil (AC-2/AC-3/AC-7) bleibt unangetastet im Versand-Panel.
//
// Echter Klick-Pfad: Trip öffnen → auf den Tab-Trigger „Versand"/„Alarme"
// klicken (kein direktes goto mit ?tab=…), da nur so die tatsächliche
// UI-Interaktion (Tab-Wechsel-Mechanik in TripTabs.svelte) verifiziert wird.
// `:visible` wird verwendet, weil manche testids (Segmented-Atom) im
// Mobile+Desktop-Layout doppelt im DOM stehen können.

import { test, expect, type APIRequestContext, type Page } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_PREFIX = 'e2e-1232-versand-tab';
const tripId = (suffix: string) => `${TRIP_PREFIX}-${suffix}`;

async function createTrip(request: APIRequestContext, id: string): Promise<void> {
	const res = await request.post('/api/trips', {
		data: {
			id,
			name: `Issue 1232 ${id}`,
			stages: [
				{
					id: `${id}-stage-1`,
					name: 'Etappe 1',
					date: '2026-08-01',
					waypoints: [{ id: `${id}-wp-1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
				},
				{
					id: `${id}-stage-2`,
					name: 'Etappe 2',
					date: '2026-08-03',
					waypoints: [{ id: `${id}-wp-2`, name: 'Ziel', lat: 42.2, lon: 9.1, elevation_m: 700 }]
				}
			],
			report_config: {
				enabled: true,
				morning_enabled: true,
				evening_enabled: true,
				morning_time: '07:00',
				evening_time: '18:00',
				send_email: true,
				send_telegram: true,
				send_sms: false
			},
			display_config: { metric_alert_levels: { wind_gust: 'standard' } },
			alert_rules: [{ id: 'r1', kind: 'absolute', metric: 'wind_gust', threshold: 50, severity: 'warning', enabled: true }]
		}
	});
	expect([200, 201]).toContain(res.status());
}

async function deleteTrip(request: APIRequestContext, id: string): Promise<void> {
	const res = await request.delete(`/api/trips/${id}`);
	expect([200, 204, 404]).toContain(res.status());
}

async function openTripOverview(page: Page, id: string): Promise<void> {
	await page.goto(`/trips/${id}`);
	await expect(page.getByTestId('trip-detail-tab-list')).toBeVisible();
}

async function clickVersandTab(page: Page): Promise<void> {
	await page.getByTestId('trip-detail-tab-briefings').first().click();
	await expect(page.getByTestId('trip-detail-panel-briefings')).toBeVisible();
}

async function clickAlertsTab(page: Page): Promise<void> {
	await page.getByTestId('trip-detail-tab-alerts').first().click();
	await expect(page.getByTestId('trip-detail-panel-alerts')).toBeVisible();
}

// Issue #1258 Scheibe S3 (D5): neuer Tab „Alarme" — Ziel-Panel der
// Alert-Zustellungs-Sektion nach dem atomaren Umzug.
async function clickAlarmeTab(page: Page): Promise<void> {
	await page.getByTestId('trip-detail-tab-alarme').first().click();
	await expect(page.getByTestId('trip-detail-panel-alarme')).toBeVisible();
}

test.describe('Issue #1232 Scheibe 1 — VersandTab (context=route)', () => {
	test.beforeEach(async ({ page }) => {
		await page.request.delete(`/api/trips/${tripId('main')}`).catch(() => {});
		await createTrip(page.request, tripId('main'));
	});

	test.afterEach(async ({ page }) => {
		await deleteTrip(page.request, tripId('main'));
	});

	// Issue #1258 (D5, AC-13/AC-14): Alert-Zustellung (Cooldown, Stille
	// Stunden, Beispiel-Warnung) lebt jetzt im Alarme-Panel, „Etappen öffnen"
	// (Laufzeit-Sektion) bleibt im Versand-Panel.
	test('AC-13: Alert-Zustellung ist im Alarme-Panel sichtbar', async ({ page }) => {
		await login(page);
		await openTripOverview(page, tripId('main'));
		await clickAlarmeTab(page);

		const panel = page.getByTestId('trip-detail-panel-alarme');
		await expect(panel.getByTestId('alarme-tab')).toBeVisible();
		await expect(panel.getByTestId('alert-cooldown-card')).toBeVisible();
		await expect(panel.getByTestId('alert-quiet-hours-card')).toBeVisible();
		await expect(panel.getByTestId('alert-preview-card')).toBeVisible();
	});

	test('AC-14: „Etappen öffnen" bleibt im Versand-Panel sichtbar', async ({ page }) => {
		await login(page);
		await openTripOverview(page, tripId('main'));
		await clickVersandTab(page);

		const panel = page.getByTestId('trip-detail-panel-briefings');
		await expect(panel.getByText('Etappen öffnen →')).toBeVisible();
	});

	// AC-2/AC-3/AC-7: Kanäle + Zeitplan bleiben (weiterhin) im Versand-Panel.
	test('AC-2/AC-3: Kanal-Toggle + Morgen-Zeitplan bleiben im Versand-Panel', async ({ page }) => {
		await login(page);
		await openTripOverview(page, tripId('main'));
		await clickVersandTab(page);

		const panel = page.getByTestId('trip-detail-panel-briefings');
		await expect(panel.getByTestId('channel-email').locator(':visible').first()).toBeVisible();
		await expect(panel.getByTestId('morning-master-switch').locator(':visible').first()).toBeVisible();
		await expect(panel.getByTestId('report-morning-time')).toBeVisible();
	});

	// AC-6: Alerts-Panel (Wertebereiche) enthält die Zustell-Controls NICHT mehr.
	test('AC-6: Alerts-Panel (Wertebereiche) enthält Cooldown/Beispiel-Warnung NICHT mehr', async ({ page }) => {
		await login(page);
		await openTripOverview(page, tripId('main'));
		await clickAlertsTab(page);

		const panel = page.getByTestId('trip-detail-panel-alerts');
		await expect(panel).toBeVisible();
		await expect(panel.getByTestId('alert-cooldown-card')).toHaveCount(0);
		await expect(panel.getByTestId('alert-preview-card')).toHaveCount(0);
	});

	// Issue #1258 AC-14: Versand-Panel enthält die Zustell-Controls NICHT
	// mehr (nach dem Umzug in den Alarme-Tab).
	test('AC-14: Versand-Panel enthält Cooldown/amtliche-Warnungen-Toggle NICHT mehr', async ({ page }) => {
		await login(page);
		await openTripOverview(page, tripId('main'));
		await clickVersandTab(page);

		const panel = page.getByTestId('trip-detail-panel-briefings');
		await expect(panel.getByTestId('alert-cooldown-card')).toHaveCount(0);
		await expect(panel.getByTestId('alerts-tab-official-alerts-toggle')).toHaveCount(0);
	});

	// AC-5: Etappen öffnen wechselt tatsächlich in den Etappen-Tab.
	test('AC-5: „Etappen öffnen →" wechselt in den Etappen-Tab', async ({ page }) => {
		await login(page);
		await openTripOverview(page, tripId('main'));
		await clickVersandTab(page);

		await page.getByTestId('trip-detail-panel-briefings').getByText('Etappen öffnen →').click();
		await expect(page.getByTestId('trip-detail-tab-stages')).toHaveAttribute('data-state', 'active');
		await expect(page.getByTestId('trip-detail-panel-stages')).toBeVisible();
	});

	// Adversary-Fund F001 (BROKEN → Fix): schneller Tab-Wechsel weg vom
	// Alarme-Tab, VOR Ablauf des 700ms-Debounce, darf den Toggle NICHT
	// verwerfen — TripTabs.svelte muss den Flush-Guard auch für 'alarme'
	// greifen lassen (sonst überschreibt der nächste Save aus WeatherMetricsTab
	// den veralteten official_alerts_enabled-Snapshot).
	// Issue #1258 (D5): Toggle + Panel zogen aus dem Versand-Tab in den
	// Alarme-Tab um — der Flush-Guard-Beweis bleibt inhaltlich derselbe.
	test('F001: Toggle im Alarme-Tab überlebt sofortigen Tab-Wechsel (kein Datenverlust)', async ({ page }) => {
		await login(page);
		await openTripOverview(page, tripId('main'));
		await clickAlarmeTab(page);

		const toggle = page
			.getByTestId('trip-detail-panel-alarme')
			.getByTestId('alerts-tab-official-alerts-toggle')
			.getByRole('checkbox');
		await expect(toggle).toBeChecked();
		await toggle.uncheck();

		// Sofort wegklicken — VOR Ablauf des 700ms-Debounce-Fensters.
		await page.getByTestId('trip-detail-tab-stages').first().click();
		await expect(page.getByTestId('trip-detail-panel-stages')).toBeVisible();

		// Der Flush muss bereits abgeschlossen sein (handleValueChange awaitet
		// saveController.flush() VOR dem Tab-Wechsel) — der Server-Wert muss
		// also sofort false sein, kein Warten auf den Debounce nötig.
		const res = await page.request.get(`/api/trips/${tripId('main')}`);
		expect(res.ok()).toBeTruthy();
		const updated = await res.json();
		expect(updated.official_alerts_enabled).toBe(false);

		// Zurück in den Alarme-Tab: Wert bleibt erhalten (kein Stale-Overwrite).
		await clickAlarmeTab(page);
		await expect(
			page
				.getByTestId('trip-detail-panel-alarme')
				.getByTestId('alerts-tab-official-alerts-toggle')
				.getByRole('checkbox')
		).not.toBeChecked();
	});
});
