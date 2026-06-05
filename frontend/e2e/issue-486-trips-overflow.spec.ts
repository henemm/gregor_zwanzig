// TDD RED — Issue #486: Desktop Trips-Liste — Icon-Geschwader → Overflow-Menü
//
// Spec: docs/specs/modules/bug_486_trips_overflow_regression.md (AC-1..AC-8)
//
// RED-Phase: Diese Tests scheitern SOLANGE die Desktop-Aktionsspalte noch
// 6 einzelne Icon-Buttons pro Zeile zeigt (Regression) und kein ⋯-Menü hat.
//
// Ausführung (lokal gegen laufenden Preview-Server):
//   cd frontend && npx playwright test e2e/issue-486-trips-overflow.spec.ts

import { test, expect } from '@playwright/test';

const DESKTOP_VIEWPORT = { width: 1280, height: 800 };

test.describe('Issue #486 — Desktop Trips-Zeile: Overflow-Menü statt Icon-Geschwader', () => {
	test.use({ viewport: DESKTOP_VIEWPORT });

	test.beforeEach(async ({ page }) => {
		await page.goto('/trips');
		// Warte auf mindestens eine Zeile im Desktop-Grid
		await page.locator('.hidden.desktop\\:block').waitFor({ state: 'visible', timeout: 10_000 });
	});

	// AC-1: Keine Reihe von Einzel-Icon-Buttons in der Aktionsspalte mehr
	test('AC-1: Aktionsspalte zeigt KEINE Reihe von 3+ Icon-Buttons nebeneinander', async ({ page }) => {
		/**
		 * GIVEN: Desktop-Viewport (1280), /trips geladen, mindestens 1 Trip
		 * WHEN:  Seite gerendert
		 * THEN:  In der Aktionsspalte der ersten Zeile gibt es weniger als 3
		 *        nebeneinanderstehende kleine Icon-Buttons (kein "Geschwader").
		 *        Konkret: der ⋯-Button ist vorhanden; die alten 6 Buttons sind weg.
		 */
		const desktopGrid = page.locator('.hidden.desktop\\:block');

		// Der ⋯-Button MUSS vorhanden sein (AC-4 Vorbedingung)
		const menuBtn = desktopGrid.locator('[data-testid="trip-row-menu-btn"]').first();
		await expect(menuBtn).toBeVisible({ timeout: 5_000 });

		// In der Aktionszelle der ersten Zeile darf es NICHT 6 separate kleine
		// Border-Icon-Buttons geben. Wir prüfen, dass die Anzahl sichtbarer
		// Buttons in der letzten Grid-Spalte ≤ 2 ist (Quick-Action + ⋯).
		// Die alten Buttons hatten border: 1px solid var(--g-rule-soft) + width/height 30px.
		// Wir zählen Buttons INNERHALB der Aktionszelle der ersten Daten-Zeile.
		const firstRow = desktopGrid.locator('[role="button"]').first();
		await expect(firstRow).toBeVisible();

		// Buttons in der Aktionszelle (letzter Grid-Cell) – schließt den ⋯-Button und
		// ggf. die Quick-Action ein. Darf NICHT 6 sein.
		const actionCell = firstRow.locator('div').last();
		const btnsInAction = actionCell.locator('button');
		const count = await btnsInAction.count();
		expect(count).toBeLessThanOrEqual(2);
	});

	// AC-2: Klick auf Zeile (außerhalb Aktionszelle) navigiert zu /trips/<id>
	test('AC-2: Klick auf Trip-Zeile (außerhalb Aktionszelle) navigiert zu Trip-Detail', async ({ page }) => {
		/**
		 * GIVEN: Desktop-Viewport, /trips geladen
		 * WHEN:  User klickt irgendwo auf die Zeile (Name-Spalte)
		 * THEN:  Navigation zu /trips/<id>
		 */
		const desktopGrid = page.locator('.hidden.desktop\\:block');
		const firstRow = desktopGrid.locator('[role="button"]').first();
		await expect(firstRow).toBeVisible();

		// Name-Spalte klicken (erste Spalte, hat kein Button drin)
		const nameCell = firstRow.locator('div').first();
		await nameCell.click();

		await expect(page).toHaveURL(/\/trips\/[a-zA-Z0-9_-]+$/, { timeout: 10_000 });
	});

	// AC-2b: Zeile hat role="button" und tabIndex=0
	test('AC-2b: Trip-Zeile hat role="button" und tabIndex 0', async ({ page }) => {
		/**
		 * GIVEN: Desktop-Viewport, /trips geladen
		 * THEN:  Erste Daten-Zeile hat role="button" und tabIndex="0"
		 */
		const desktopGrid = page.locator('.hidden.desktop\\:block');
		const firstRow = desktopGrid.locator('[role="button"]').first();
		await expect(firstRow).toBeVisible();
		await expect(firstRow).toHaveAttribute('tabindex', '0');
	});

	// AC-4: ⋯-Button existiert und öffnet Menü mit 6 Items
	test('AC-4: ⋯-Button öffnet Overflow-Menü mit allen 6 Einträgen', async ({ page }) => {
		/**
		 * GIVEN: Desktop-Viewport, /trips geladen, mindestens 1 Trip
		 * WHEN:  User klickt auf [data-testid="trip-row-menu-btn"]
		 * THEN:  Ein [role="menu"] erscheint mit den Texten:
		 *        „Briefing jetzt senden", „Email-Vorschau", „Alert-Konfiguration",
		 *        „Wetter-Metriken", „Bearbeiten", „Löschen"
		 */
		const desktopGrid = page.locator('.hidden.desktop\\:block');
		const menuBtn = desktopGrid.locator('[data-testid="trip-row-menu-btn"]').first();
		await expect(menuBtn).toBeVisible();
		await menuBtn.click();

		const menu = page.locator('[role="menu"]').first();
		await expect(menu).toBeVisible({ timeout: 3_000 });

		for (const label of [
			'Briefing jetzt senden',
			'Email-Vorschau',
			'Alert-Konfiguration',
			'Wetter-Metriken',
			'Bearbeiten',
			'Löschen',
		]) {
			await expect(menu.getByText(label, { exact: false })).toBeVisible();
		}
	});

	// AC-4b: Menü schließt bei Klick außerhalb
	test('AC-4b: Menü schließt bei Klick außerhalb', async ({ page }) => {
		const desktopGrid = page.locator('.hidden.desktop\\:block');
		const menuBtn = desktopGrid.locator('[data-testid="trip-row-menu-btn"]').first();
		await menuBtn.click();
		const menu = page.locator('[role="menu"]').first();
		await expect(menu).toBeVisible({ timeout: 3_000 });

		// Echter Viewport-Klick außerhalb des Menüs — löst das position:fixed Overlay-onclick aus
		await page.mouse.click(10, 10);
		await expect(menu).not.toBeVisible({ timeout: 3_000 });
	});

	// AC-5: Klick auf Aktionszelle löst KEINE Zeilen-Navigation aus
	test('AC-5: Klick auf ⋯-Button navigiert NICHT zu Trip-Detail (stopPropagation)', async ({ page }) => {
		/**
		 * GIVEN: Desktop-Viewport, /trips geladen
		 * WHEN:  User klickt auf [data-testid="trip-row-menu-btn"]
		 * THEN:  URL bleibt /trips (keine Navigation), Menü öffnet sich
		 */
		const desktopGrid = page.locator('.hidden.desktop\\:block');
		const menuBtn = desktopGrid.locator('[data-testid="trip-row-menu-btn"]').first();
		await expect(menuBtn).toBeVisible();
		await menuBtn.click();

		// URL darf sich NICHT geändert haben
		expect(page.url()).toMatch(/\/trips\/?(\?.*)?$/);

		// Menü muss sichtbar sein
		const menu = page.locator('[role="menu"]').first();
		await expect(menu).toBeVisible({ timeout: 3_000 });
	});

	// AC-6: trip-edit-btn Selektor erhalten (jetzt im Menü)
	test('AC-6: data-testid="trip-edit-btn" ist im Menü vorhanden', async ({ page }) => {
		/**
		 * GIVEN: Desktop-Viewport, /trips geladen
		 * WHEN:  ⋯-Menü geöffnet
		 * THEN:  [data-testid="trip-edit-btn"] existiert im Menü
		 */
		const desktopGrid = page.locator('.hidden.desktop\\:block');
		const menuBtn = desktopGrid.locator('[data-testid="trip-row-menu-btn"]').first();
		await menuBtn.click();

		const menu = page.locator('[role="menu"]').first();
		await expect(menu).toBeVisible({ timeout: 3_000 });
		await expect(menu.locator('[data-testid="trip-edit-btn"]')).toBeVisible();
	});

	// AC-8: Mobile-Pfad unberührt — trip-card-menu-btn bleibt sichtbar auf Mobile
	test('AC-8: Mobile-Pfad unberührt — trip-card-menu-btn vorhanden auf Mobile-Viewport', async ({ page }) => {
		/**
		 * GIVEN: Mobile-Viewport (375), /trips geladen
		 * WHEN:  Seite gerendert
		 * THEN:  [data-testid="trip-card-menu-btn"] ist sichtbar (Mobile-Stack bleibt erhalten)
		 */
		await page.setViewportSize({ width: 375, height: 667 });
		await page.goto('/trips');
		await expect(
			page.locator('[data-testid="trip-card-menu-btn"]').first()
		).toBeVisible({ timeout: 10_000 });
	});
});
