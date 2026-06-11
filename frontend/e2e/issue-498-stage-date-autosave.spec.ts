// TDD RED: Issue #498 — Etappen-Datum verschieben muss SOFORT persistieren.
//
// Spec: docs/specs/modules/issue_498_stage_date_autosave.md
// Workflow: Phase 5 (TDD RED) — Verhaltens-Tests gegen den laufenden Stack als
// eingeloggter Nutzer (Playwright, kein Mock, kein Dateiinhalt-Check).
//
// Root Cause (re-open): Datum-Änderung + Kaskaden-Bestätigung mutierten nur den
// lokalen UI-Zustand. Persistiert wurde NUR über den separaten „Etappen speichern"-
// Button. Der grüne „verschoben ✓"-Done-State täuschte Abschluss vor → Nutzer
// verloren die Änderung beim Verlassen/Reload.
//
// AC-1/AC-2/AC-3/AC-5 lassen den separaten Save-Klick BEWUSST weg → vor dem Fix ROT.
// Editor lebt im Trip-Detail unter ?tab=stages (EditStagesSection → EditStagesPanelNew).
// Auth via storageState (playwright.config 'tests'-Projekt → admin.json).

import { test, expect, type Page } from '@playwright/test';

const TRIP_ID = 'e2e-498-autosave';
const TRIP_NAME = 'E2E #498 Datum-Autosave';

const wp = (id: string, lat: number) => ({ id, name: id, lat, lon: 9.0, elevation_m: 800 });

// 3 Wander-Etappen (08-01/02/03) + ein Pausentag (08-04) am Ende.
const seedStages = [
	{ id: 's1', name: 'Tag 1', date: '2026-08-01', waypoints: [wp('a', 42.0), wp('b', 42.04)] },
	{ id: 's2', name: 'Tag 2', date: '2026-08-02', waypoints: [wp('c', 42.1), wp('d', 42.14)] },
	{ id: 's3', name: 'Tag 3', date: '2026-08-03', waypoints: [wp('e', 42.2), wp('f', 42.24)] },
	{ id: 'pause', name: 'Pausentag', date: '2026-08-04', waypoints: [] }
];

const seedBody = { id: TRIP_ID, name: TRIP_NAME, region: 'Korsika', stages: seedStages };

async function openStagesEditor(page: Page) {
	await page.goto(`/trips/${TRIP_ID}?tab=stages`);
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	await expect(page.getByTestId('stage-date-field').first()).toBeVisible();
}

function activeDateInput(page: Page) {
	return page.getByTestId('stage-date-field').first().locator('input[type="date"]');
}

async function fetchStageDates(page: Page): Promise<Record<string, string>> {
	const res = await page.request.get(`/api/trips/${TRIP_ID}`);
	expect(res.ok(), `GET trip HTTP ${res.status()}`).toBeTruthy();
	const trip = await res.json();
	const out: Record<string, string> = {};
	for (const s of trip.stages) out[s.id] = s.date;
	return out;
}

test.beforeEach(async ({ page }) => {
	await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	const res = await page.request.post('/api/trips', { data: seedBody });
	expect(res.ok(), `seed HTTP ${res.status()}`).toBeTruthy();
});

test.afterEach(async ({ page }) => {
	await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
});

// AC-1: Datum einer (mittleren) Etappe ändern, KEIN „Etappen speichern"-Klick,
// Hard-Reload → API liefert das neue Datum. Vor dem Fix: Datum verloren.
test('AC-1: Datum-Änderung persistiert sofort ohne Save-Klick', async ({ page }) => {
	await openStagesEditor(page);
	// Mittlere Etappe (Tag 2) aktivieren — keine Kaskade.
	await page.getByText('Tag 2', { exact: false }).first().click();
	await expect(activeDateInput(page)).toHaveValue('2026-08-02');

	await activeDateInput(page).fill('2026-08-20');
	await activeDateInput(page).blur();

	// BEWUSST KEIN Klick auf „Etappen speichern".
	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();

	const dates = await fetchStageDates(page);
	expect(dates['s2']).toBe('2026-08-20');
});

// AC-2: Erste Etappe verschieben + „Alle mitverschieben" bestätigen, KEIN Save-Klick,
// Hard-Reload → ALLE Etappen um N Tage verschoben. Genau der verlorene Nutzer-Flow.
test('AC-2: Kaskade „Alle mitverschieben" persistiert alle Etappen sofort', async ({ page }) => {
	await openStagesEditor(page);
	await page.getByText('Tag 1', { exact: false }).first().click();
	await expect(activeDateInput(page)).toHaveValue('2026-08-01');

	// 08-01 → 07-22 (−10 Tage).
	await activeDateInput(page).fill('2026-07-22');
	await activeDateInput(page).blur();

	await expect(page.getByTestId('cascade-strip')).toBeVisible();
	await page.getByRole('button', { name: /Alle mitverschieben/ }).click();
	await expect(page.getByTestId('cascade-done')).toBeVisible();

	// BEWUSST KEIN Klick auf „Etappen speichern".
	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();

	const dates = await fetchStageDates(page);
	expect(dates['s1']).toBe('2026-07-22');
	expect(dates['s2']).toBe('2026-07-23');
	expect(dates['s3']).toBe('2026-07-24');
	expect(dates['pause']).toBe('2026-07-25');
});

// AC-3: Header-Datum (Eyebrow REGION · DATUM) aktualisiert sich SOFORT ohne Reload.
test('AC-3: Trip-Header-Datum aktualisiert sofort ohne Reload', async ({ page }) => {
	await openStagesEditor(page);
	// Vor Edit zeigt der Header „August 2026".
	await expect(page.getByText(/AUGUST 2026/i).first()).toBeVisible();

	await page.getByText('Tag 1', { exact: false }).first().click();
	await activeDateInput(page).fill('2026-09-15');
	await activeDateInput(page).blur();
	// Kaskade ablehnen — nur diese Etappe (Header-Range deckt dann Sep–Aug ab).
	await expect(page.getByTestId('cascade-strip')).toBeVisible();
	await page.getByRole('button', { name: /Nur diese Etappe/ }).click();

	// OHNE Reload muss „September" im Header erscheinen.
	await expect(page.getByText(/SEPTEMBER 2026/i).first()).toBeVisible({ timeout: 5000 });
});

// AC-4: Der grüne Done-State erscheint nach erfolgreichem Auto-Save, und die
// Persistenz ist per API bestätigt (Erfolgsfall).
test('AC-4: Kaskaden-Done-State + API-Persistenz im Erfolgsfall', async ({ page }) => {
	await openStagesEditor(page);
	await page.getByText('Tag 1', { exact: false }).first().click();
	await activeDateInput(page).fill('2026-08-06');
	await activeDateInput(page).blur();
	await expect(page.getByTestId('cascade-strip')).toBeVisible();
	await page.getByRole('button', { name: /Alle mitverschieben/ }).click();
	await expect(page.getByTestId('cascade-done')).toBeVisible();

	// Done-State bedeutet WIRKLICH gespeichert — API ohne Reload prüfen.
	const dates = await fetchStageDates(page);
	expect(dates['s1']).toBe('2026-08-06');
	expect(dates['s2']).toBe('2026-08-07');
});

// AC-5 (Guard): Pausentag-Datum persistiert ebenfalls sofort; Save-Button bleibt da.
test('AC-5: Pausentag-Datum persistiert sofort + Save-Button bleibt', async ({ page }) => {
	await openStagesEditor(page);
	await expect(page.getByRole('button', { name: /Etappen speichern/ })).toBeVisible();

	await page.getByText('Pausentag', { exact: false }).first().click();
	const pauseView = page.getByTestId('pause-stage-view');
	await expect(pauseView).toBeVisible();
	const pauseInput = pauseView.getByTestId('stage-date-field').locator('input[type="date"]');
	await expect(pauseInput).toHaveValue('2026-08-04');

	await pauseInput.fill('2026-08-09');
	await pauseInput.blur();

	// KEIN Save-Klick.
	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();

	const dates = await fetchStageDates(page);
	expect(dates['pause']).toBe('2026-08-09');
});
