// E2E — Issue #1117: „Amtliche Warnungen" auch im Tab „Inhalt" konfigurierbar.
//
// Spec: docs/specs/modules/issue_1117_official_alerts_content_tab.md
// Workflow: fix-1117-official-alerts-content-tab
//
// Ziel-Oberfläche: Trip-Detail-Seite /trips/[id]?tab=weather, Tab „Inhalt"
// (WeatherMetricsTab.svelte, Checkbox neben der "E-Mail-Inhalt"-Card).
// `official_alerts_enabled` wird ausschließlich hier geschaltet.
//
// Issue #1232 Scheibe 1 (Nachzügler-Fix): der „Amtliche Warnungen"-Schalter
// (`alerts-tab-official-alerts-toggle`) ist aus dem Alerts-Tab in den neuen
// Versand-Tab (VersandTab.svelte, context="route") umgezogen — testid
// unverändert, nur der Tab darüber hat sich geändert (AC-6/AC-7 der Spec
// versand_tab_route.md).
//
// Issue #1258 Scheibe S3 (D5, atomarer Umzug): derselbe Schalter zog ein
// weiteres Mal um — aus dem Versand-Tab in den neuen geteilten Alarme-Tab
// (AlarmeTab.svelte, context="route", Tab-Trigger „Alarme", Panel
// `trip-detail-panel-alarme`).
//
// Epic #1301 Scheibe D2 (2026-07-18): der Alarme-Tab-Einstiegspunkt für
// `official_alerts_enabled` ist ENTFERNT — der doppelte Schalter
// (`alerts-tab-official-alerts-toggle`) existiert im Alarme-Tab nicht mehr,
// dort lebt nur noch der Auslöser-Schalter
// (`alerts-tab-official-alert-triggers-toggle`). Einzige Bedienstelle für
// `official_alerts_enabled` ist jetzt der Inhalt-Tab-Toggle
// `report-show-official-alerts` (WeatherMetricsTab.svelte). Ehemals AC-2
// (Cross-Tab-Synchronität) wurde durch einen D2-Regressionstest ersetzt, der
// die Abwesenheit des Alarme-Tab-Schalters positiv beweist; ehemals AC-4
// (Regression auf dem entfernten Alarme-Tab-Schalter) wurde gelöscht; AC-1
// und AC-3 (Flush-Guard, jetzt über den Etappen-Tab geführt) bleiben
// inhaltlich gültig. `:visible` an den Tab-Trigger-Selektoren, weil
// Segmented-Tab-Trigger im Mobile+Desktop-Layout doppelt im DOM stehen
// können.

import { test, expect } from '@playwright/test';
import type { APIRequestContext, Page } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_PREFIX = 'e2e-issue-1117';

function tripId(suffix: string): string {
	return `${TRIP_PREFIX}-${suffix}`;
}

async function createTrip(
	request: APIRequestContext,
	id: string,
	officialAlertsEnabled: boolean = true
): Promise<void> {
	const res = await request.post('/api/trips', {
		data: {
			id,
			name: `Issue 1117 ${id}`,
			stages: [
				{
					id: `${id}-stage-1`,
					name: 'Etappe',
					date: new Date().toISOString().slice(0, 10),
					waypoints: [{ id: `${id}-wp-1`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
				}
			],
			report_config: { enabled: true, morning_time: '07:00', evening_time: '18:00' },
			official_alerts_enabled: officialAlertsEnabled,
			alert_rules: []
		}
	});
	expect([200, 201]).toContain(res.status());
}

async function deleteTrip(request: APIRequestContext, id: string): Promise<void> {
	const res = await request.delete(`/api/trips/${id}`);
	expect([200, 204, 404]).toContain(res.status());
}

async function openInhalt(page: Page, id: string): Promise<void> {
	await page.goto(`/trips/${id}?tab=weather`);
	await page.locator('[data-testid="weather-metrics-tab"]').waitFor({ state: 'visible' });
	await page.locator('[data-testid="report-mail-content"]').waitFor({ state: 'visible' });
}

// Exakter Pfad-Match (nicht `.includes()`) — sonst matcht auch die
// `/api/trips/{id}/weather-config`-PUT, die kein `official_alerts_enabled` trägt.
function isTripPut(url: string, id: string): boolean {
	try {
		return new URL(url).pathname === `/api/trips/${id}`;
	} catch {
		return false;
	}
}

test.describe('Issue #1117: Amtliche Warnungen im Inhalt-Tab', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('AC-1: Schalter sichtbar im Inhalt-Tab, Zustand persistiert nach Reload', async ({ page, request }) => {
		const id = tripId('ac1');
		await createTrip(request, id, true);
		try {
			await openInhalt(page, id);

			const toggle = page.locator('[data-testid="report-show-official-alerts"] input[type="checkbox"]');
			await expect(toggle).toBeVisible();
			await expect(toggle).toBeChecked();

			const putDone = page.waitForResponse(
				(r) => isTripPut(r.url(), id) && r.request().method() === 'PUT'
			);
			await toggle.click();
			await putDone;

			await page.reload();
			await page.locator('[data-testid="weather-metrics-tab"]').waitFor({ state: 'visible' });
			await expect(
				page.locator('[data-testid="report-show-official-alerts"] input[type="checkbox"]')
			).not.toBeChecked();
		} finally {
			await deleteTrip(request, id);
		}
	});

	test('D2: Alarme-Tab hat keinen amtliche-Warnungen-Inhalt-Schalter mehr, nur den Auslöser', async ({
		page,
		request
	}) => {
		const id = tripId('ac2');
		await createTrip(request, id, true);
		try {
			await page.goto(`/trips/${id}`);
			await page.locator('[data-testid="trip-detail-tab-alarme"]:visible').first().click();
			await page.locator('[data-testid="trip-detail-panel-alarme"]').waitFor({ state: 'visible' });

			await expect(page.locator('[data-testid="alerts-tab-official-alerts-toggle"]')).toHaveCount(0);
			await expect(
				page.locator('[data-testid="alerts-tab-official-alert-triggers-toggle"]:visible').first()
			).toBeVisible();
		} finally {
			await deleteTrip(request, id);
		}
	});

	test('AC-3: Sofortiger Tab-Wechsel direkt nach dem Toggle verliert die Änderung nicht', async ({
		page,
		request
	}) => {
		const id = tripId('ac3');
		await createTrip(request, id, true);
		try {
			await openInhalt(page, id);
			const inhaltToggle = page.locator('[data-testid="report-show-official-alerts"] input[type="checkbox"]');
			await expect(inhaltToggle).toBeChecked();

			// Bewusst KEIN Warten auf die PUT-Antwort — echter schneller Nutzer-Pfad,
			// prüft den Flush-Guard in TripTabs.svelte::handleValueChange beim
			// Verlassen des Inhalt-Tabs. D2: der Alarme-Tab hat keinen Toggle mehr,
			// daher wird stattdessen in den Etappen-Tab gewechselt und der
			// Datenverlust-Beweis rein über das Backend geführt.
			await inhaltToggle.click();
			await page.locator('[data-testid="trip-detail-tab-stages"]:visible').first().click();
			await page.locator('[data-testid="trip-detail-panel-stages"]').waitFor({ state: 'visible' });

			// Backend-Beweis: kein Datenverlust unabhängig vom Render-Timing.
			const check = await request.get(`/api/trips/${id}`);
			expect(check.ok(), `GET trip HTTP ${check.status()}`).toBeTruthy();
			const trip = await check.json();
			expect(trip.official_alerts_enabled).toBe(false);
		} finally {
			await deleteTrip(request, id);
		}
	});
});
