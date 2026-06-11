// E2E — Issue #724: Trip-Name umbenennen — Fehler-Feedback bei fehlgeschlagenem Save
//
// Spec: docs/specs/modules/issue_724_trip_name_save_error.md (AC-1 bis AC-3)
//
// TDD RED: AC-1 und AC-3 MÜSSEN FEHLSCHLAGEN, solange `makeNameSaveHandler` in
// TripHeader.svelte keinen `catch` hat und keine sichtbare Fehlermeldung
// (data-testid="trip-name-save-error") rendert. Bei einem fehlschlagenden
// PUT /api/trips/{id} bleibt heute nur das Feld offen — der Nutzer bekommt
// KEINE Rückmeldung.
//
// Verhaltenstests aus Nutzerperspektive: ein fehlschlagender PUT wird via
// Playwright-Route-Interception erzwungen (kein Mock der Komponente, echtes
// Klick-Verhalten gegen den gerenderten Build).
//
// Ausführung: cd frontend && npx playwright test issue-724-trip-name-save-error

import { test, expect, type Page } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_ID = 'e2e-cockpit-test';
const TRIP_NAME = 'E2E Cockpit Test Trip';
const DESKTOP = { width: 1440, height: 900 };

/** Erzwingt, dass der nächste PUT /api/trips/{id} mit HTTP 500 scheitert. */
async function forceFailedSave(page: Page): Promise<void> {
	await page.route(`**/api/trips/${TRIP_ID}`, async (route) => {
		if (route.request().method() === 'PUT') {
			await route.fulfill({
				status: 500,
				contentType: 'application/json',
				body: JSON.stringify({ error: 'Serverfehler beim Speichern (Test 500)' })
			});
		} else {
			await route.continue();
		}
	});
}

test.describe('Issue #724 — Fehler-Feedback beim Trip-Namens-Save', () => {
	// ─── AC-1: Fehlschlag → Feld bleibt offen + sichtbare Fehlermeldung ───
	test('AC-1: PUT scheitert → Edit-Feld offen + Fehlermeldung sichtbar', async ({ page }) => {
		/**
		 * GIVEN: Trip-Detail-Seite, Inline-Namens-Edit geöffnet
		 * WHEN:  "Umbenennen" geklickt wird und PUT /api/trips/{id} fehlschlägt (500)
		 * THEN:  das Eingabefeld (trip-name-edit) bleibt sichtbar UND eine
		 *        Fehlermeldung (trip-name-save-error) erscheint mit nicht-leerem Text.
		 * RED-Grund: makeNameSaveHandler hat keinen catch → kein trip-name-save-error.
		 */
		await page.setViewportSize(DESKTOP);
		await login(page);
		await page.goto(`/trips/${TRIP_ID}`);
		await expect(page.getByTestId('trip-detail-h1')).toBeVisible({ timeout: 8000 });

		await forceFailedSave(page);

		await page.getByTestId('trip-name-edit-toggle').click();
		const input = page.getByTestId('trip-name-edit');
		await expect(input).toBeVisible();
		await input.fill('E2E #724 — soll scheitern');
		await page.getByTestId('trip-name-save').click();

		// Feld bleibt offen (Eingabe nicht verloren)
		await expect(input).toBeVisible({ timeout: 8000 });
		// Sichtbare, nicht-leere Fehlermeldung
		const err = page.getByTestId('trip-name-save-error');
		await expect(err).toBeVisible({ timeout: 8000 });
		await expect(err).not.toHaveText('');
	});

	// ─── AC-2: Erfolg → Feld schließt, neuer Name im Header, keine Fehlermeldung ───
	test('AC-2: PUT 2xx → Feld geschlossen, Name aktualisiert, keine Fehlermeldung', async ({
		page
	}) => {
		/**
		 * GIVEN: Trip-Detail-Seite
		 * WHEN:  Name geändert und erfolgreich gespeichert wird (echter Backend-Pfad)
		 * THEN:  Eingabefeld verschwindet, neuer Name steht in trip-detail-h1,
		 *        trip-name-save-error ist nicht sichtbar.
		 */
		await page.setViewportSize(DESKTOP);
		await login(page);
		await page.goto(`/trips/${TRIP_ID}`);
		await expect(page.getByTestId('trip-detail-h1')).toBeVisible({ timeout: 8000 });

		const newName = 'E2E #724 — erfolgreich';
		await page.getByTestId('trip-name-edit-toggle').click();
		await page.getByTestId('trip-name-edit').fill(newName);
		await page.getByTestId('trip-name-save').click();

		await expect(page.getByTestId('trip-name-edit')).toBeHidden({ timeout: 8000 });
		await expect(page.getByTestId('trip-detail-h1')).toContainText(newName);
		await expect(page.getByTestId('trip-name-save-error')).toBeHidden();

		// Cleanup: Name zurücksetzen
		const res = await page.request.get(`/api/trips/${TRIP_ID}`);
		const trip = await res.json();
		await page.request.put(`/api/trips/${TRIP_ID}`, { data: { ...trip, name: TRIP_NAME } });
	});

	// ─── AC-3: Fehlermeldung wird bei neuem Versuch / Abbrechen / Neu-Öffnen zurückgesetzt ───
	test('AC-3: Fehlermeldung wird bei Abbrechen + Neu-Öffnen zurückgesetzt', async ({ page }) => {
		/**
		 * GIVEN: zuvor angezeigte Fehlermeldung nach fehlgeschlagenem Save
		 * WHEN:  der Nutzer "Abbrechen" klickt und den Edit über das Stift-Icon neu öffnet
		 * THEN:  die Fehlermeldung (trip-name-save-error) ist nicht mehr sichtbar.
		 * RED-Grund: ohne Fehler-State existiert weder die Meldung noch ihr Reset.
		 */
		await page.setViewportSize(DESKTOP);
		await login(page);
		await page.goto(`/trips/${TRIP_ID}`);
		await expect(page.getByTestId('trip-detail-h1')).toBeVisible({ timeout: 8000 });

		await forceFailedSave(page);

		// Fehler provozieren
		await page.getByTestId('trip-name-edit-toggle').click();
		await page.getByTestId('trip-name-edit').fill('E2E #724 — reset-test');
		await page.getByTestId('trip-name-save').click();
		await expect(page.getByTestId('trip-name-save-error')).toBeVisible({ timeout: 8000 });

		// Abbrechen → Edit schließt
		await page.getByRole('button', { name: 'Abbrechen' }).click();
		await expect(page.getByTestId('trip-name-edit')).toBeHidden();

		// Neu öffnen via Stift → Fehlermeldung ist weg
		await page.getByTestId('trip-name-edit-toggle').click();
		await expect(page.getByTestId('trip-name-edit')).toBeVisible();
		await expect(page.getByTestId('trip-name-save-error')).toBeHidden();
	});
});
