// TDD RED: Issue #296-FE — Trip-Editor: Wegpunkte über Höhenprofil (keine Karte)
//
// Spec: docs/specs/modules/issue_296_fe_profile_editor.md
// Test-Manifest: docs/specs/tests/issue_296_fe_profile_editor_tests.md
// Vorbild: frontend/e2e/waypoints-editor.spec.ts
//
// Workflow: Phase 5 (TDD RED). Diese E2E-Specs werden in Phase 6 (GREEN)
// implementiert (EditStagesPanelNew + ProfileEditor/WaypointCard-Props) und
// POST-PUSH gegen Staging grün geprüft — siehe CLAUDE.md
// „E2E-Verifikation (Post-Push auf Staging)". Sie werden hier NICHT lokal
// ausgeführt; die echte E2E-Prüfung (Server starten, Playwright gegen echten
// Trip `e2e-cockpit-test`, KEINE Mocks) läuft auf Staging.
//
// Bis EditStagesPanelNew existiert + die Lat/Lon-Inputs entfernt sind, sind
// diese Assertions rot.
//
// Abgedeckte Acceptance Criteria: AC-1, AC-2, AC-3, AC-4, AC-5, AC-9, AC-10.

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_ID = 'e2e-cockpit-test';
const EDIT_URL = `/trips/${TRIP_ID}/edit`;

// Etappen ist Default-Tab; nur klicken wenn Panel noch nicht sichtbar
// (Issue #494: Accordion → Tab-Navigation).
async function ensureEtappenOpen(page: import('@playwright/test').Page) {
	const tab = page.locator('[data-testid="edit-tabs"] [data-value="etappen"]');
	await expect(tab).toBeVisible();
	const panel = page.getByTestId('edit-stages-panel');
	if (!(await panel.isVisible({ timeout: 500 }).catch(() => false))) {
		await tab.click();
		await expect(panel).toBeVisible();
	}
}

test.beforeEach(async ({ page }) => {
	await login(page);
});

// =============================================================================
// AC-1: Keine Lat/Lon/Höhen-Eingabefelder mehr
// =============================================================================

test('AC-1: Editor zeigt keine wp-lat / wp-lon / wp-ele Felder', async ({ page }) => {
	await page.goto(EDIT_URL);
	await ensureEtappenOpen(page);

	await expect(page.getByTestId('wp-lat')).toHaveCount(0);
	await expect(page.getByTestId('wp-lon')).toHaveCount(0);
	await expect(page.getByTestId('wp-ele')).toHaveCount(0);
});

// =============================================================================
// AC-2: Höhenprofil-SVG mit einem Pin pro Wegpunkt sichtbar
// =============================================================================

test('AC-2: aktive Stage mit Wegpunkten zeigt profile-editor mit Pins', async ({ page }) => {
	await page.goto(EDIT_URL);
	await ensureEtappenOpen(page);

	const profile = page.getByTestId('profile-editor');
	await expect(profile).toBeVisible();

	// Stage 1 (e2e-stage-1) hat 2 Wegpunkte → mind. 2 Pins.
	const pins = profile.getByTestId(/^waypoint-pin-/);
	await expect(pins.first()).toBeVisible();
	expect(await pins.count()).toBeGreaterThanOrEqual(2);
});

// =============================================================================
// AC-3: suggested → Bestätigen/Verwerfen, manuell → Umbenennen/Löschen
// =============================================================================

test('AC-3: suggested Wegpunkt zeigt Bestätigen + Verwerfen', async ({ page }) => {
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
						{ id: 'e2e-wp-a', name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 800 },
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
	await page.goto(EDIT_URL);
	await ensureEtappenOpen(page);

	await expect(page.getByTestId('waypoint-confirm-1')).toBeVisible();
	await expect(page.getByTestId('waypoint-reject-1')).toBeVisible();
});

test('AC-3: manueller Wegpunkt zeigt Umbenennen + Löschen, kein Bestätigen', async ({ page }) => {
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
						{ id: 'e2e-wp-manual', name: 'Manuell', lat: 42.1, lon: 9.0, elevation_m: 800 }
					]
				}
			]
		}
	});
	await page.goto(EDIT_URL);
	await ensureEtappenOpen(page);

	await expect(page.getByTestId('waypoint-rename-0')).toBeVisible();
	await expect(page.getByTestId('waypoint-delete-0')).toBeVisible();
	await expect(page.getByTestId('waypoint-confirm-0')).toHaveCount(0);
});

// =============================================================================
// AC-4: Klick aufs Profil fügt interpolierten (suggested) Wegpunkt ein
// =============================================================================

test('AC-4: Klick auf Höhenprofil-Fläche fügt neuen suggested Wegpunkt ein', async ({ page }) => {
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
						{ id: 'e2e-wp-a', name: 'A', lat: 42.0, lon: 9.0, elevation_m: 800 },
						{ id: 'e2e-wp-b', name: 'B', lat: 42.4, lon: 9.6, elevation_m: 1200 }
					]
				}
			]
		}
	});
	await page.goto(EDIT_URL);
	await ensureEtappenOpen(page);

	const profile = page.getByTestId('profile-editor');
	await expect(profile).toBeVisible();

	// Vorher: 2 Wegpunkt-Karten.
	const cardsBefore = await page.getByTestId(/^waypoint-card-/).count();

	// In die Mitte der Profil-Fläche klicken (fraction ~0.5 → zwischen A und B).
	const box = await profile.boundingBox();
	if (!box) throw new Error('profile-editor hat keine boundingBox');
	await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);

	// Nachher: eine Karte mehr, neuer Wegpunkt ist suggested (Verwerfen-Button sichtbar).
	const cardsAfter = await page.getByTestId(/^waypoint-card-/).count();
	expect(cardsAfter).toBe(cardsBefore + 1);
	await expect(page.getByTestId('waypoint-reject-1')).toBeVisible();
});

// =============================================================================
// AC-5: Ankunftszeit wp-arrival-{i} pro Wegpunkt sichtbar
// =============================================================================

test('AC-5: jede WaypointCard zeigt eine Ankunftszeit wp-arrival-{i}', async ({ page }) => {
	await page.request.put(`/api/trips/${TRIP_ID}`, {
		data: {
			id: TRIP_ID,
			name: 'E2E Cockpit Test Trip',
			stages: [
				{
					id: 'e2e-stage-1',
					name: 'Gestern',
					date: new Date(Date.now() - 86400000).toISOString().slice(0, 10),
					start_time: '08:00',
					waypoints: [
						{ id: 'e2e-wp-a', name: 'A', lat: 42.0, lon: 9.0, elevation_m: 1000 },
						{ id: 'e2e-wp-b', name: 'B', lat: 42.4, lon: 9.0, elevation_m: 1000 }
					]
				}
			]
		}
	});
	await page.goto(EDIT_URL);
	await ensureEtappenOpen(page);

	const arrival0 = page.getByTestId('wp-arrival-0');
	const arrival1 = page.getByTestId('wp-arrival-1');
	await expect(arrival0).toBeVisible();
	await expect(arrival1).toBeVisible();
	// Format "HH:MM"
	await expect(arrival0).toHaveText(/^\d{2}:\d{2}$/);
	await expect(arrival1).toHaveText(/^\d{2}:\d{2}$/);
});

// =============================================================================
// AC-9: Detail-View /trips/:id (epic_137) bleibt regressionsfrei
// =============================================================================

test('AC-9: Detail-View Etappen-Tab zeigt MapCanvas + ProfileEditor (keine Regression)', async ({
	page
}) => {
	await page.goto(`/trips/${TRIP_ID}#stages`);
	await page.getByTestId('trip-detail-tab-stages').click();
	await expect(page.getByTestId('map-canvas')).toBeVisible();
	await expect(page.getByTestId('profile-editor')).toBeVisible();
});

// =============================================================================
// AC-10: Pausentag → PauseStageView statt Höhenprofil
// =============================================================================

test('AC-10: Pausentag-Stage zeigt pause-stage-view statt profile-editor', async ({ page }) => {
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
					waypoints: []
				}
			]
		}
	});
	await page.goto(EDIT_URL);
	await ensureEtappenOpen(page);

	// Pausentag-Kachel (Index 1) aktivieren.
	await page.getByTestId('stage-card-pause-1').click();
	await expect(page.getByTestId('pause-stage-view')).toBeVisible();
	await expect(page.getByTestId('profile-editor')).toHaveCount(0);
});
