// E2E — Issue #714: Trip-Editor UI-Kleinigkeiten (#706, #713, #719)
//
// Spec: docs/specs/modules/issue_714_trip_ui_polish.md (AC-1 bis AC-5)
//
// TDD RED: Diese Tests MÜSSEN FEHLSCHLAGEN, solange:
//   #706 — das Aktionsmenü in der Trip-Tabelle in <Card overflow:hidden> liegt
//          (position:absolute) und unten abgeschnitten wird,
//   #713 — der Trip-Name ein dauerhaft sichtbares Eingabefeld ist (kein Stift-Toggle),
//   #719 — der mobile Etappen-Tab keinen Etappen-Lösch-Button hat.
//
// Verhaltenstests aus Nutzerperspektive gegen den lokalen Preview-Build mit
// eingeloggter Session + geseedetem Test-Trip `e2e-cockpit-test`.
//
// Ausführung: cd frontend && npx playwright test issue-714-trip-ui-polish

import { test, expect, type Locator } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_ID = 'e2e-cockpit-test';
const TRIP_NAME = 'E2E Cockpit Test Trip';
const DESKTOP = { width: 1440, height: 900 };
const MOBILE = { width: 375, height: 800 };

/**
 * Prüft geometrisch, ob ein Element von einem overflow-Vorfahren (z.B. die
 * <Card overflow:hidden> der Trip-Tabelle) abgeschnitten wird — genau der
 * #706-Bug. position:fixed bricht die Clip-Kette der overflow-Vorfahren auf
 * (fixe Elemente werden nicht von overflow-Vorfahren beschnitten), daher gilt
 * ein fixes Menü als NICHT von der Karte abgeschnitten.
 * Gibt true zurück, wenn das Element von einem overflow-Vorfahren clippt.
 */
async function isClippedByOverflowAncestor(loc: Locator): Promise<boolean> {
	return loc.evaluate((el) => {
		const TOL = 1;
		// Fixe Elemente entkommen dem overflow-Clipping der Vorfahren.
		if (getComputedStyle(el).position === 'fixed') return false;
		const r = el.getBoundingClientRect();
		let node: HTMLElement | null = el.parentElement;
		while (node) {
			const s = getComputedStyle(node);
			if (/(auto|hidden|scroll|clip)/.test(s.overflow + s.overflowX + s.overflowY)) {
				const nr = node.getBoundingClientRect();
				if (
					r.bottom > nr.bottom + TOL ||
					r.top < nr.top - TOL ||
					r.left < nr.left - TOL ||
					r.right > nr.right + TOL
				) {
					return true;
				}
			}
			node = node.parentElement;
		}
		return false;
	});
}

test.describe('Issue #714 — Trip-Editor UI-Kleinigkeiten', () => {
	// ─── AC-1 (#706): Aktionsmenü ist vollständig sichtbar, nicht abgeschnitten ───
	test('AC-1: "…"-Menü in der Trip-Tabelle ist nicht abgeschnitten', async ({ page }) => {
		/**
		 * GIVEN: /trips Desktop-Tabelle — Menü der UNTERSTEN Zeile (dort ragt das
		 *        Menü über den unteren Karten-Rand hinaus).
		 * WHEN:  der "…"-Aktionsknopf der letzten Zeile geklickt wird
		 * THEN:  der unterste Eintrag "Löschen" wird NICHT von der Karte
		 *        (overflow:hidden) abgeschnitten.
		 * RED-Grund: das Menü (position:absolute) liegt in <Card overflow:hidden>
		 *            und wird an der letzten Zeile unten beschnitten.
		 */
		await page.setViewportSize(DESKTOP);
		await login(page);
		await page.goto('/trips');

		const menuBtns = page.locator('[data-testid="trip-row-menu-btn"]:visible');
		await expect(menuBtns.first()).toBeVisible({ timeout: 8000 });
		await menuBtns.last().click();
		const loeschen = page.getByRole('menuitem', { name: 'Löschen' });
		await expect(loeschen).toBeVisible({ timeout: 8000 });

		expect(await isClippedByOverflowAncestor(loeschen)).toBe(false);
	});

	// ─── AC-2 (#713): Default-Zustand zeigt Stift-Icon, kein Eingabefeld ───
	test('AC-2: Trip-Name zeigt Stift-Icon statt dauerhaftem Eingabefeld', async ({ page }) => {
		/**
		 * GIVEN: Trip-Detail-Seite frisch geladen (kein Edit-Zustand)
		 * WHEN:  die Seite gerendert ist
		 * THEN:  das Namens-Eingabefeld ist NICHT sichtbar, der Stift-Toggle ist sichtbar.
		 * RED-Grund: name-edit-row (Input + "Umbenennen") ist heute dauerhaft sichtbar,
		 *            trip-name-edit-toggle existiert noch nicht.
		 */
		await page.setViewportSize(DESKTOP);
		await login(page);
		await page.goto(`/trips/${TRIP_ID}`);

		await expect(page.getByTestId('trip-detail-h1')).toBeVisible({ timeout: 8000 });
		await expect(page.getByTestId('trip-name-edit-toggle')).toBeVisible();
		await expect(page.getByTestId('trip-name-edit')).toBeHidden();
	});

	// ─── AC-3 (#713): Stift öffnet Inline-Edit, Name persistiert, Feld schließt ───
	test('AC-3: Stift-Klick → Name ändern → Speichern → persistiert + Feld verborgen', async ({
		page
	}) => {
		/**
		 * GIVEN: Trip-Detail-Seite
		 * WHEN:  Stift klicken, Namen ändern, Speichern drücken
		 * THEN:  Eingabefeld erscheint erst nach Klick, neuer Name persistiert via API,
		 *        danach ist das Eingabefeld wieder verborgen.
		 * RED-Grund: trip-name-edit-toggle existiert nicht → Klick schlägt fehl.
		 */
		await page.setViewportSize(DESKTOP);
		await login(page);
		await page.goto(`/trips/${TRIP_ID}`);

		const newName = 'E2E #714 — umbenannt';
		await page.getByTestId('trip-name-edit-toggle').click();
		const input = page.getByTestId('trip-name-edit');
		await expect(input).toBeVisible();
		await input.fill(newName);
		await page.getByTestId('trip-name-save').click();

		await expect(page.getByTestId('trip-name-edit')).toBeHidden({ timeout: 8000 });
		const res = await page.request.get(`/api/trips/${TRIP_ID}`);
		const trip = await res.json();
		expect(trip.name).toBe(newName);

		// Cleanup: Name zurücksetzen
		await page.request.put(`/api/trips/${TRIP_ID}`, { data: { ...trip, name: TRIP_NAME } });
	});

	// ─── AC-4 (#719): Mobile Etappen-Löschung mit Bestätigungsdialog ───
	test('AC-4: Mobile /trips/new — Etappe löschen mit Rückfrage', async ({ page }) => {
		/**
		 * GIVEN: mobiler Etappen-Tab von /trips/new mit ≥1 Etappe
		 * WHEN:  der ×-Lösch-Knopf einer Etappen-Karte geklickt wird
		 * THEN:  der Bestätigungsdialog (#708) erscheint; "Abbrechen" lässt die Etappe
		 *        bestehen, "Löschen" entfernt genau diese Etappe.
		 * RED-Grund: tn-mobile-stage-remove-0 existiert im mobilen Layout nicht.
		 */
		await page.setViewportSize(MOBILE);
		await login(page);
		await page.goto('/trips/new');

		await page.getByTestId('trip-new-name-input').last().fill('Mobile Lösch-Test');
		await page.getByTestId('trip-new-date-input').last().fill('2026-07-01');
		await page.getByRole('tab', { name: 'Etappen & GPX' }).click();

		const cards = page.getByTestId('tn-mobile-stage-card');
		await expect(cards.first()).toBeVisible({ timeout: 8000 });
		const before = await cards.count();

		// Lösch-Knopf der ersten Etappe → Dialog
		await page.getByTestId('tn-mobile-stage-remove-0').click();
		await expect(page.getByTestId('confirm-delete-stage')).toBeVisible();

		// Abbrechen lässt die Etappe bestehen
		await page.getByTestId('cancel-delete-stage').click();
		await expect(cards).toHaveCount(before);

		// Erneut → Löschen entfernt genau eine Etappe
		await page.getByTestId('tn-mobile-stage-remove-0').click();
		await page.getByTestId('confirm-delete-stage').click();
		await expect(cards).toHaveCount(before - 1);
	});

	// ─── AC-5 (#719): GPX-Entfernen und Etappen-Löschen sind getrennt ───
	test('AC-5: Mobile — GPX-× und Etappen-× sind getrennte Aktionen', async ({ page }) => {
		/**
		 * GIVEN: mobiler Etappen-Tab mit ≥1 Etappe
		 * WHEN:  die Etappen-Karte gerendert ist
		 * THEN:  es existiert ein Etappen-Lösch-Knopf (tn-mobile-stage-remove-0), der den
		 *        Lösch-Dialog auslöst — getrennt vom GPX-Entfernen.
		 * RED-Grund: der Etappen-Lösch-Knopf fehlt im mobilen Layout.
		 */
		await page.setViewportSize(MOBILE);
		await login(page);
		await page.goto('/trips/new');

		await page.getByTestId('trip-new-name-input').last().fill('Mobile Trenn-Test');
		await page.getByTestId('trip-new-date-input').last().fill('2026-07-01');
		await page.getByRole('tab', { name: 'Etappen & GPX' }).click();

		await expect(page.getByTestId('tn-mobile-stage-card').first()).toBeVisible({ timeout: 8000 });
		const removeBtn = page.getByTestId('tn-mobile-stage-remove-0');
		await expect(removeBtn).toBeVisible();
		await removeBtn.click();
		// Etappen-× löst den Lösch-Dialog aus (nicht das GPX-Entfernen)
		await expect(page.getByTestId('confirm-delete-stage')).toBeVisible();
	});
});
