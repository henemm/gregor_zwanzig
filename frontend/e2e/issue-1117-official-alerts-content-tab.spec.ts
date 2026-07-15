// E2E — Issue #1117: „Amtliche Warnungen" auch im Tab „Inhalt" konfigurierbar.
//
// Spec: docs/specs/modules/issue_1117_official_alerts_content_tab.md
// Workflow: fix-1117-official-alerts-content-tab
//
// Ziel-Oberfläche: Trip-Detail-Seite /trips/[id]?tab=weather, Tab „Inhalt"
// (WeatherMetricsTab.svelte, Checkbox neben der "E-Mail-Inhalt"-Card) sowie
// der Tab „Versand" (value=briefings). Beide UI-Einstiegspunkte
// schreiben/lesen dasselbe Feld `trip.official_alerts_enabled`.
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
// `trip-detail-panel-alarme`). testid unverändert. AC-2/AC-3/AC-4 zielen
// deshalb jetzt auf den Tab-Trigger „Alarme"; die Kern-Aussage (Cross-Tab-
// Konsistenz mit dem Inhalt-Tab-Toggle `report-show-official-alerts`) bleibt
// unverändert erhalten. `:visible` an den Tab-Trigger-/Toggle-Selektoren,
// weil Segmented-Tab-Trigger im Mobile+Desktop-Layout doppelt im DOM stehen
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

// Issue #1258 Scheibe S3 (D5): echter Klick-Pfad auf den Tab-Trigger „Alarme"
// (war: „Versand", s. Issue #1232 — der Schalter zog seither ein weiteres
// Mal um, s. Modul-Kommentar oben). `:visible` wegen möglicher
// Doppel-Renderings des Segmented-Tab-Triggers.
async function openAlarme(page: Page, id: string): Promise<void> {
	await page.goto(`/trips/${id}`);
	await page.locator('[data-testid="trip-detail-tab-alarme"]:visible').first().click();
	await page.locator('[data-testid="alerts-tab-official-alerts-toggle"]:visible').first().waitFor({ state: 'visible' });
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

	test('AC-2: Zustand synchron zwischen Inhalt-Tab und Alarme-Tab (beide Richtungen)', async ({ page, request }) => {
		const id = tripId('ac2');
		await createTrip(request, id, true);
		try {
			// Richtung A: Inhalt -> Alarme
			await openInhalt(page, id);
			const inhaltToggle = page.locator('[data-testid="report-show-official-alerts"] input[type="checkbox"]');
			await expect(inhaltToggle).toBeChecked();

			const putA = page.waitForResponse((r) => isTripPut(r.url(), id) && r.request().method() === 'PUT');
			await inhaltToggle.click();
			await putA;

			await page.locator('[data-testid="trip-detail-tab-alarme"]:visible').first().click();
			const alarmeToggle = page.locator('[data-testid="alerts-tab-official-alerts-toggle"]:visible input[type="checkbox"]');
			await expect(alarmeToggle).not.toBeChecked();

			// Richtung B: Alarme -> Inhalt
			const putB = page.waitForResponse((r) => isTripPut(r.url(), id) && r.request().method() === 'PUT');
			await alarmeToggle.click();
			await putB;

			await page.locator('[data-testid="trip-detail-tab-weather"]:visible').first().click();
			await page.locator('[data-testid="weather-metrics-tab"]').waitFor({ state: 'visible' });
			await expect(
				page.locator('[data-testid="report-show-official-alerts"] input[type="checkbox"]')
			).toBeChecked();
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
			// Verlassen des Inhalt-Tabs (Issue #1258 Scheibe S3: Guard umfasst
			// jetzt 'alarme', da der Ziel-Tab „Alarme" den analogen Schalter trägt).
			await inhaltToggle.click();
			await page.locator('[data-testid="trip-detail-tab-alarme"]:visible').first().click();

			const alarmeToggle = page.locator('[data-testid="alerts-tab-official-alerts-toggle"]:visible input[type="checkbox"]');
			await expect(alarmeToggle).not.toBeChecked();

			// Zusätzlicher Backend-Beweis: kein Datenverlust unabhängig vom Render-Timing.
			const check = await request.get(`/api/trips/${id}`);
			expect(check.ok(), `GET trip HTTP ${check.status()}`).toBeTruthy();
			const trip = await check.json();
			expect(trip.official_alerts_enabled).toBe(false);
		} finally {
			await deleteTrip(request, id);
		}
	});

	test('AC-4 (Regression): bestehender Schalter im Alarme-Tab bleibt unverändert funktionsfähig', async ({
		page,
		request
	}) => {
		const id = tripId('ac4');
		await createTrip(request, id, true);
		try {
			await openAlarme(page, id);
			const alarmeToggle = page.locator('[data-testid="alerts-tab-official-alerts-toggle"]:visible input[type="checkbox"]');
			await expect(alarmeToggle).toBeVisible();
			await expect(alarmeToggle).toBeChecked();

			const putDone = page.waitForResponse((r) => isTripPut(r.url(), id) && r.request().method() === 'PUT');
			await alarmeToggle.click();
			await putDone;

			await page.reload();
			await page.locator('[data-testid="trip-detail-panel-alarme"]').waitFor({ state: 'visible' });
			await expect(
				page.locator('[data-testid="alerts-tab-official-alerts-toggle"]:visible input[type="checkbox"]')
			).not.toBeChecked();
		} finally {
			await deleteTrip(request, id);
		}
	});
});
