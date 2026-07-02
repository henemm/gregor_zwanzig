// TDD RED: Bug #708 — Etappen dürfen nicht ohne Rückfrage gelöscht werden
//
// Spec: docs/specs/modules/bug_708_etappe_delete_confirm.md
// Workflow: Phase 5 (TDD RED) — Verhaltens-Tests gegen lokalen Preview-Build.
//
// RED-Erwartung: aktueller Code löscht sofort beim ×-Klick, kein Dialog erscheint.
// → AC-1 schlägt fehl (stage-card-1 verschwunden, kein confirm-delete-stage sichtbar).
// → Nach GREEN: alle Tests grün, kein sofortiges Löschen mehr ohne Bestätigung.
//
// Navigations-Muster: Trip-Editor unter /trips/{id}?tab=stages
// Auth via storageState (global.setup.ts) — kein per-Test-Login.

import { test, expect } from '@playwright/test';

const TRIP_ID = 'e2e-708-stage-confirm';
const TRIP_NAME = 'E2E #708 Etappe-Confirm-Test';
const today = new Date().toISOString().slice(0, 10);

const seedStages = [
	{
		id: 's1',
		name: 'Etappe Alpha',
		date: today,
		waypoints: [
			{ id: 'w1a', name: 'Start', lat: 47.0, lon: 11.0, elevation_m: 800 },
			{ id: 'w1b', name: 'Ziel',  lat: 47.04, lon: 11.0, elevation_m: 900 }
		]
	},
	{
		id: 's2',
		name: 'Etappe Beta',
		date: today,
		waypoints: [
			{ id: 'w2a', name: 'Start', lat: 47.04, lon: 11.0, elevation_m: 900 },
			{ id: 'w2b', name: 'Ziel',  lat: 47.08, lon: 11.0, elevation_m: 1000 }
		]
	}
];

const seedBody = { id: TRIP_ID, name: TRIP_NAME, region: 'Korsika', stages: seedStages };

async function openStagesEditor(page: import('@playwright/test').Page) {
	await page.goto(`/trips/${TRIP_ID}?tab=stages`);
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
}

test.beforeEach(async ({ page }) => {
	await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	const res = await page.request.post('/api/trips', { data: seedBody });
	expect(res.ok(), `seed HTTP ${res.status()}`).toBeTruthy();
});

// AC-1: × klicken → Dialog erscheint, Etappe bleibt zunächst bestehen.
test('AC-1: × klicken öffnet Bestätigungs-Dialog, Etappe noch vorhanden', async ({ page }) => {
	await openStagesEditor(page);

	// Beide Karten vorhanden
	await expect(page.getByTestId('stage-card-0')).toBeVisible();
	await expect(page.getByTestId('stage-card-1')).toBeVisible();

	// × der ersten Karte klicken
	await page.getByTestId('stage-card-0')
		.getByRole('button', { name: 'Etappe entfernen' })
		.click();

	// Dialog mit Löschen-Button muss erscheinen
	await expect(page.getByTestId('confirm-delete-stage')).toBeVisible();

	// BEIDE Karten müssen noch sichtbar sein (keine sofortige Löschung)
	await expect(page.getByTestId('stage-card-0')).toBeVisible();
	await expect(page.getByTestId('stage-card-1')).toBeVisible();
});

// AC-2: Abbrechen → Dialog weg, Etappe bleibt.
test('AC-2: Abbrechen schließt Dialog, Etappe bleibt erhalten', async ({ page }) => {
	await openStagesEditor(page);

	await page.getByTestId('stage-card-0')
		.getByRole('button', { name: 'Etappe entfernen' })
		.click();

	await expect(page.getByTestId('cancel-delete-stage')).toBeVisible();
	await page.getByTestId('cancel-delete-stage').click();

	// Dialog weg
	await expect(page.getByTestId('confirm-delete-stage')).toHaveCount(0);
	// Etappe noch da
	await expect(page.getByTestId('stage-card-0')).toBeVisible();
	await expect(page.getByTestId('stage-card-1')).toBeVisible();
});

// AC-3: Löschen → Etappe entfernt, Dialog weg.
test('AC-3: Löschen bestätigen entfernt die Etappe', async ({ page }) => {
	await openStagesEditor(page);

	await page.getByTestId('stage-card-0')
		.getByRole('button', { name: 'Etappe entfernen' })
		.click();

	await expect(page.getByTestId('confirm-delete-stage')).toBeVisible();
	await page.getByTestId('confirm-delete-stage').click();

	// Dialog geschlossen
	await expect(page.getByTestId('confirm-delete-stage')).toHaveCount(0);
	// Nur noch eine Karte
	await expect(page.getByTestId('stage-card-0')).toBeVisible();
	await expect(page.getByTestId('stage-card-1')).toHaveCount(0);
});

// AC-5: Aktive Etappe löschen → andere wird aktiviert, kein kaputter Zustand.
test('AC-5: Aktive Etappe löschen aktiviert die verbleibende', async ({ page }) => {
	await openStagesEditor(page);

	// Erste Karte anklicken (aktivieren)
	await page.getByTestId('stage-card-0').click();

	// × der ersten (aktiven) Karte klicken und Löschen bestätigen
	await page.getByTestId('stage-card-0')
		.getByRole('button', { name: 'Etappe entfernen' })
		.click();
	await page.getByTestId('confirm-delete-stage').click();

	// Panel noch intakt, eine Karte sichtbar
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	await expect(page.getByTestId('stage-card-0')).toBeVisible();
	await expect(page.getByTestId('stage-card-1')).toHaveCount(0);
});

// AC-4: /trips/new Etappen-Tab — gleiches Dialog-Verhalten.
test('AC-4: /trips/new × klicken öffnet Bestätigungs-Dialog', async ({ page }) => {
	await page.goto('/trips/new');
	await expect(page.getByTestId('trip-new-editor')).toBeVisible();

	// Name eingeben (Desktop-Input, direkt sichtbar)
	const nameInput = page.getByTestId('trip-new-name-input-desktop');
	await nameInput.fill('Test-Tour 708');

	// Startdatum: Desktop-Input hat kein testid → via type="date" im Desktop-Bereich
	const dateInputs = page.locator('input[type="date"]');
	// Ersten sichtbaren date-Input verwenden
	const visibleDate = dateInputs.first();
	await visibleDate.fill(today);
	await visibleDate.dispatchEvent('change');

	// "Weiter"-Button klicken zum etappen-Tab navigieren
	await page.getByTestId('trip-new-continue-etappen').click();

	// Warte bis etappen-Tab aktiv: "Etappe hinzufügen"-Button sichtbar
	await expect(page.getByRole('button', { name: '+ Etappe hinzufügen' })).toBeVisible();

	// Sicherstellen, dass es mindestens eine Etappe gibt (default sind 2)
	// Klicke × der ersten Etappe (data-testid="tn-stage-remove-0")
	await expect(page.getByTestId('tn-stage-remove-0')).toBeVisible();
	await page.getByTestId('tn-stage-remove-0').click();

	// Dialog muss erscheinen
	await expect(page.getByTestId('confirm-delete-stage')).toBeVisible();

	// Abbrechen erhält die Etappe
	await page.getByTestId('cancel-delete-stage').click();
	await expect(page.getByTestId('tn-stage-remove-0')).toBeVisible();

	// Nochmal × und Löschen bestätigen
	await page.getByTestId('tn-stage-remove-0').click();
	await page.getByTestId('confirm-delete-stage').click();
	await expect(page.getByTestId('confirm-delete-stage')).toHaveCount(0);
});
