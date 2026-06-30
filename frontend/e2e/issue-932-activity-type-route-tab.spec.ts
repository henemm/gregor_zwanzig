// E2E — Issue #932: Aktivitätstyp auf Route-Tab (erstes Screen).
//
// Spec: docs/specs/modules/issue_932_activity_type_first_screen.md
//
// Diese Tests sind in der RED-Phase noch NICHT grün:
//   - AC-1: activity-dropdown existiert NICHT im Route-Tab (liegt noch im Metriken-Tab)
//   - AC-5 ist Regressionsschutz (schon grün) für den Edit-Modus
//
// AC-2 (Template-Vorauswahl), AC-3 (kein Speichern im Create-Modus),
// AC-4 (manuelle Anpassung bleibt erhalten) werden nach Implementation
// gegen Staging via /e2e-verify verifiziert (benötigen GPX-Upload).

import { test, expect } from '@playwright/test';

const DESKTOP = { width: 1280, height: 900 };

// Bekannte Test-Touren auf Staging (werden auch in epic-138-metriken-editor.spec.ts genutzt)
const EDIT_TRIP_ID = 'e2e-trip-edit-target';

test.describe('Issue #932 — Aktivitätstyp auf Route-Tab', () => {

	// AC-1: Aktivitätstyp-Dropdown auf Route-Tab sichtbar
	// RED: Vor dem Fix liegt das Dropdown im Metriken-Tab, nicht hier.
	test('AC-1: Aktivitätstyp-Dropdown auf Route-Tab sichtbar (Desktop)', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		await page.goto('/trips/new');

		// Route-Tab ist der erste und Standard-Tab — kein Navigieren nötig.
		// data-testid="trip-new-editor" muss vorhanden sein.
		await expect(page.getByTestId('trip-new-editor')).toBeVisible();

		// AC-1: Das Aktivitätstyp-Dropdown muss auf dem Route-Tab sichtbar sein.
		// RED: Schlägt fehl, weil das Dropdown noch im Metriken-Tab liegt.
		const dropdown = page.getByTestId('activity-dropdown');
		await expect(dropdown).toBeVisible();
	});

	// AC-1 mobil: Dropdown auch auf Mobile-Route-Tab sichtbar
	test('AC-1: Aktivitätstyp-Dropdown auf Route-Tab sichtbar (Mobile)', async ({ page }) => {
		await page.setViewportSize({ width: 375, height: 667 });
		await page.goto('/trips/new');

		// Mobile App-Leiste sichtbar (Route-Tab ist aktiv)
		await expect(page.getByTestId('tn-mobile-appbar')).toBeVisible();

		// AC-1: Dropdown muss auch auf Mobile-Route-Tab vorhanden sein.
		// RED: Schlägt fehl, weil das Dropdown noch im Metriken-Tab liegt.
		const dropdown = page.getByTestId('activity-dropdown');
		await expect(dropdown).toBeVisible();
	});

	// AC-5 Regressionsschutz: Speichern-Button im Edit-Modus weiterhin sichtbar
	// GRÜN schon vor dem Fix — guards gegen Regress durch die createMode-Änderung.
	test('AC-5: Speichern-Button im Edit-Modus sichtbar (kein Regress)', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		// Nutze einen bekannten Staging-Test-Trip im Edit-Modus.
		// Falls kein solcher Trip existiert, wird via /trips zur Trip-Liste gegangen
		// und der erste verfügbare Trip-Edit-Link verwendet.
		await page.goto('/trips');

		// Ersten Trip aus der Liste öffnen und zum Edit-View navigieren
		const firstEditLink = page.locator('a[href*="/edit"]').first();
		const hasEditLink = await firstEditLink.count() > 0;

		if (!hasEditLink) {
			// Kein Trip vorhanden — Test wird übersprungen (Staging-Daten fehlen)
			test.skip();
			return;
		}

		await firstEditLink.click();
		await page.waitForURL(/\/trips\/[^/]+\/edit/);

		// Wetter-Tab in TripEditView öffnen
		const wetterTab = page.locator('[data-testid^="edit-tab-"]', { hasText: 'Wetter' });
		await wetterTab.click();

		// AC-5: Speichern-Button muss im Edit-Modus (createMode=false) vorhanden sein.
		// Dieser Test ist GREEN vor und nach dem Fix — guards gegen Regress.
		await expect(page.getByTestId('weather-metrics-tab-save')).toBeVisible();
	});
});
