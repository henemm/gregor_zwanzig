// TDD RED: Epic #137 — Wegpunkt-Editor (Issues #166–#172)
//
// Spec: docs/specs/modules/epic_137_wegpunkt_editor.md
// Workflow: Phase 5 (TDD RED) — Tests MÜSSEN FEHLSCHLAGEN bis Phase 6.
//
// Komponenten (WaypointsPanel, EtappenStrip, StageCard, MapCanvas, WaypointCard,
// PauseStageView) existieren noch NICHT → data-testid Assertions schlagen fehl = RED.
//
// Voraussetzung: Test-Trip `e2e-cockpit-test` aus global.setup.ts existiert
// (3 Stages mit yesterday/today/tomorrow + je 1–2 Waypoints).

import { test, expect } from '@playwright/test';

const TRIP_ID = 'e2e-cockpit-test';

// =============================================================================
// AC-1: EtappenStrip zeigt StageCards für alle Etappen
// =============================================================================

test('AC-1: EtappenStrip zeigt StageCards für alle 3 Etappen', async ({ page }) => {
	await page.goto(`/trips/${TRIP_ID}#stages`);
	await page.getByTestId('trip-detail-tab-stages').click();
	await expect(page.getByTestId('etappen-strip')).toBeVisible();
	await expect(page.getByTestId('stage-card-0')).toBeVisible();
	await expect(page.getByTestId('stage-card-1')).toBeVisible();
	await expect(page.getByTestId('stage-card-pause-2')).toBeVisible();
});

// =============================================================================
// AC-5: MapCanvas zeigt Routenlinie in burnt orange
// =============================================================================

test('AC-5: MapCanvas zeigt Routenlinie mit stroke var(--g-accent)', async ({ page }) => {
	await page.goto(`/trips/${TRIP_ID}#stages`);
	await page.getByTestId('trip-detail-tab-stages').click();
	const canvas = page.getByTestId('map-canvas');
	await expect(canvas).toBeVisible();
	const polyline = canvas.locator('polyline');
	await expect(polyline).toHaveAttribute('stroke', 'var(--g-accent)');
});

// =============================================================================
// AC-6: suggested WaypointPin ist gestrichelt orange
// =============================================================================

test('AC-6: WaypointPin für suggested Waypoint zeigt Bestätigen-Button', async ({ page }) => {
	// Trip mit einem suggested Waypoint patchen
	await page.request.put(`/api/trips/${TRIP_ID}`, {
		data: {
			id: TRIP_ID,
			name: 'E2E Cockpit Test Trip',
			stages: [
				{
					id: 'e2e-stage-1',
					name: 'Gestern',
					date: new Date(Date.now() - 86400000).toISOString().slice(0, 10),
					waypoints: [
						{
							id: 'e2e-wp-suggested',
							name: 'Vorschlag',
							lat: 42.15,
							lon: 9.05,
							elevation_m: 1000,
							suggested: true
						}
					]
				}
			]
		}
	});
	await page.goto(`/trips/${TRIP_ID}#stages`);
	await page.getByTestId('trip-detail-tab-stages').click();
	// WaypointCard für suggested zeigt Bestätigen-Button
	await expect(page.getByTestId('waypoint-confirm-0')).toBeVisible();
});

// =============================================================================
// AC-10: suggested Waypoint zeigt Bestätigen + Verwerfen
// =============================================================================

test('AC-10: suggested Waypoint zeigt Bestätigen + Verwerfen Buttons', async ({ page }) => {
	// Trip mit suggested Waypoint (Zustand aus AC-6 nutzen, oder nochmals patchen)
	await page.request.put(`/api/trips/${TRIP_ID}`, {
		data: {
			id: TRIP_ID,
			name: 'E2E Cockpit Test Trip',
			stages: [
				{
					id: 'e2e-stage-1',
					name: 'Gestern',
					date: new Date(Date.now() - 86400000).toISOString().slice(0, 10),
					waypoints: [
						{
							id: 'e2e-wp-suggested',
							name: 'Vorschlag',
							lat: 42.15,
							lon: 9.05,
							elevation_m: 1000,
							suggested: true
						}
					]
				}
			]
		}
	});
	await page.goto(`/trips/${TRIP_ID}#stages`);
	await page.getByTestId('trip-detail-tab-stages').click();
	await expect(page.getByTestId('waypoint-confirm-0')).toBeVisible();
	await expect(page.getByTestId('waypoint-reject-0')).toBeVisible();
});

// =============================================================================
// AC-11: manueller Waypoint zeigt Umbenennen + Löschen (kein Bestätigen)
// =============================================================================

test('AC-11: manueller Waypoint zeigt Umbenennen + Löschen, kein Bestätigen', async ({
	page
}) => {
	// Trip zurücksetzen: Waypoint ohne suggested
	await page.request.put(`/api/trips/${TRIP_ID}`, {
		data: {
			id: TRIP_ID,
			name: 'E2E Cockpit Test Trip',
			stages: [
				{
					id: 'e2e-stage-1',
					name: 'Gestern',
					date: new Date(Date.now() - 86400000).toISOString().slice(0, 10),
					waypoints: [
						{
							id: 'e2e-wp-manual',
							name: 'Manuell',
							lat: 42.1,
							lon: 9.0,
							elevation_m: 800
						}
					]
				}
			]
		}
	});
	await page.goto(`/trips/${TRIP_ID}#stages`);
	await page.getByTestId('trip-detail-tab-stages').click();
	await expect(page.getByTestId('waypoint-rename-0')).toBeVisible();
	await expect(page.getByTestId('waypoint-delete-0')).toBeVisible();
	await expect(page.getByTestId('waypoint-confirm-0')).not.toBeVisible();
});

// =============================================================================
// AC-12: Speichern-Button löst PUT /api/trips/:id aus
// =============================================================================

test('AC-12: Speichern-Button schickt PUT /api/trips/:id', async ({ page }) => {
	await page.goto(`/trips/${TRIP_ID}#stages`);
	await page.getByTestId('trip-detail-tab-stages').click();
	const saveBtn = page.getByTestId('waypoints-save-btn');
	await expect(saveBtn).toBeVisible();
	// PUT-Request abfangen
	const [request] = await Promise.all([
		page.waitForRequest(
			(req) => req.method() === 'PUT' && req.url().includes(`/api/trips/${TRIP_ID}`)
		),
		saveBtn.click()
	]);
	expect(request).toBeTruthy();
});

// =============================================================================
// AC-13: Pausetag zeigt PauseStageView statt MapCanvas
// =============================================================================

test('AC-13: Pausetag zeigt PauseStageView statt MapCanvas', async ({ page }) => {
	// Trip mit Pausetag seeden (Stage ohne Waypoints = Pausentag)
	await page.request.put(`/api/trips/${TRIP_ID}`, {
		data: {
			id: TRIP_ID,
			name: 'E2E Cockpit Test Trip',
			stages: [
				{
					id: 'e2e-stage-normal',
					name: 'Etappe 1',
					date: new Date(Date.now() - 86400000).toISOString().slice(0, 10),
					waypoints: [
						{ id: 'e2e-wp-1', name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 800 }
					]
				},
				{
					id: 'e2e-stage-pause',
					name: 'Pausentag',
					date: new Date().toISOString().slice(0, 10),
					waypoints: [] // leer = Pausentag
				}
			]
		}
	});
	await page.goto(`/trips/${TRIP_ID}#stages`);
	await page.getByTestId('trip-detail-tab-stages').click();
	// Pausetag-Kachel anklicken (Index 1)
	await page.getByTestId('stage-card-pause-1').click();
	await expect(page.getByTestId('pause-stage-view')).toBeVisible();
	await expect(page.getByTestId('map-canvas')).not.toBeVisible();
});
