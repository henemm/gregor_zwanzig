// TDD RED: Issue #675 — Startzeiten je Etappe editieren können
//
// Spec: docs/specs/modules/issue_675_etappen_startzeiten.md
// Workflow: Phase 5 (TDD RED) — Verhaltens-Tests gegen Staging als eingeloggter Nutzer.
//
// Die Komponente StageTimeField (data-testid="stage-start-time-field") existiert
// noch NICHT → AC-1/AC-2/AC-3/AC-5 schlagen fehl = RED.
// AC-4 (alt-treu) und AC-7 (Pausentag ohne Feld) sind Guard-Tests, die vor UND
// nach der Implementierung grün bleiben müssen (Regressionsschutz).
//
// Editor lebt im Trip-Detail unter ?tab=stages (EditStagesSection →
// EditStagesPanelNew, showSave=true). /trips/{id}/edit ist deprecated (Redirect).
// Auth via storageState (issue-675.staging.setup.ts) — kein per-Test-Login.

import { test, expect } from '@playwright/test';

const TRIP_ID = 'e2e-675-starttime';
const TRIP_NAME = 'E2E #675 Startzeit-Test';
const today = new Date().toISOString().slice(0, 10);

// Flache Etappe, 2 Wegpunkte ~4 km auseinander (0.036° lat ≈ 4 km), gleiche Höhe.
// Naismith flach: 4 km / 4 km/h = 1 h → start_time=15:00 ⇒ wp0=15:00, wp1=16:00.
const seedStages = [
	{
		id: 's1',
		name: 'Anreisetag',
		date: today,
		waypoints: [
			{ id: 'w0', name: 'Start', lat: 47.0, lon: 11.0, elevation_m: 800 },
			{ id: 'w1', name: 'Ziel', lat: 47.036, lon: 11.0, elevation_m: 800 }
		]
	}
];

const seedBody = { id: TRIP_ID, name: TRIP_NAME, region: 'Korsika', stages: seedStages };

async function openStagesEditor(page: import('@playwright/test').Page) {
	await page.goto(`/trips/${TRIP_ID}?tab=stages`);
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	await expect(page.getByTestId('stage-date-field').first()).toBeVisible();
}

test.beforeEach(async ({ page }) => {
	await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	const res = await page.request.post('/api/trips', { data: seedBody });
	expect(res.ok(), `seed HTTP ${res.status()}`).toBeTruthy();
});

// AC-1: Startzeit-Feld erscheint pro Etappe, zeigt sichtbar 08:00 bei ungesetzt.
test('AC-1: Startzeit-Feld sichtbar mit Default 08:00', async ({ page }) => {
	await openStagesEditor(page);
	const field = page.getByTestId('stage-start-time-field').first();
	await expect(field).toBeVisible();
	await expect(field.locator('input[type="time"]')).toHaveValue('08:00');
});

// AC-2: Startzeit 15:00 → Wegpunkt-Ankunftszeiten rechnen live ab 15:00.
test('AC-2: Startzeit 15:00 verschiebt Ankunftszeiten live', async ({ page }) => {
	await openStagesEditor(page);
	const input = page.getByTestId('stage-start-time-field').first().locator('input[type="time"]');
	await input.fill('15:00');
	await input.blur();
	await expect(page.getByTestId('wp-arrival-0').first()).toHaveText('15:00');
	await expect(page.getByTestId('wp-arrival-1').first()).toHaveText('16:00');
});

// AC-3: Persistenz-Roundtrip — nach Speichern liefert die API 15:00.
test('AC-3: Startzeit wird gespeichert (API-Roundtrip)', async ({ page }) => {
	await openStagesEditor(page);
	const input = page.getByTestId('stage-start-time-field').first().locator('input[type="time"]');
	await input.fill('15:00');
	await input.blur();
	await page.getByRole('button', { name: /Etappen speichern/ }).click();
	await expect(page.getByText('Gespeichert ✓')).toBeVisible();
	const res = await page.request.get(`/api/trips/${TRIP_ID}`);
	const trip = await res.json();
	expect(trip.stages[0].start_time).toBe('15:00');
});

// AC-4 (Guard): alt-treu — bloßes Öffnen+Speichern setzt KEIN start_time.
test('AC-4: Öffnen ohne Änderung schreibt kein start_time', async ({ page }) => {
	await openStagesEditor(page);
	await page.getByRole('button', { name: /Etappen speichern/ }).click();
	await expect(page.getByText('Gespeichert ✓')).toBeVisible();
	const res = await page.request.get(`/api/trips/${TRIP_ID}`);
	const trip = await res.json();
	expect(trip.stages[0].start_time ?? null).toBeNull();
});

// AC-5: Feld leeren → zurück auf 08:00-Default.
test('AC-5: Geleertes Feld fällt auf 08:00 zurück', async ({ page }) => {
	await openStagesEditor(page);
	const input = page.getByTestId('stage-start-time-field').first().locator('input[type="time"]');
	await input.fill('15:00');
	await input.blur();
	await expect(page.getByTestId('wp-arrival-0').first()).toHaveText('15:00');
	await input.fill('');
	await input.blur();
	await expect(page.getByTestId('wp-arrival-0').first()).toHaveText('08:00');
});

// AC-7 (Guard): Pausentag (Etappe ohne Wegpunkte) zeigt KEIN Startzeit-Feld.
test('AC-7: Pausentag ohne Startzeit-Feld', async ({ page }) => {
	// Name "Pause" → isPauseStage erkennt den Pausentag (kein Wegpunkt).
	await page.request.put(`/api/trips/${TRIP_ID}`, {
		data: {
			...seedBody,
			stages: [...seedStages, { id: 'pause1', name: 'Pause', date: today, waypoints: [] }]
		}
	});
	await openStagesEditor(page);
	await page.getByTestId('stage-card-pause-1').click();
	await expect(page.getByTestId('pause-stage-view')).toBeVisible();
	await expect(page.getByTestId('stage-start-time-field')).toHaveCount(0);
});
