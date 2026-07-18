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

	// D2 von #1301 (2026-07-18): der ehemalige F001-Test prüfte den
	// Flush-Guard des ATL-Toggles im Alarme-Tab (`alerts-tab-official-alerts-toggle`).
	// Dieser Schalter ist entfernt — das Datenverlust-/Flush-Guard-Szenario für
	// `official_alerts_enabled` ist jetzt über den Inhalt-Tab-Toggle
	// `report-show-official-alerts` abgedeckt (siehe
	// e2e/issue-1117-official-alerts-content-tab.spec.ts AC-3).
});
