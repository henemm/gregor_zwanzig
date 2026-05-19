// E2E — Issue #249: LocationsRail + NewLocationWizard.
//
// Spec: docs/specs/modules/issue_249_locations_rail.md (AC-1 bis AC-6)
//
// TestID-Inventar (implementiert in LocationsRail.svelte + NewLocationWizard.svelte):
//   compare-rail                  — Rail-Container
//   compare-rail-search           — Suchfeld
//   compare-rail-chip             — Chip-Filter-Button (aria-label=Gruppenname)
//   compare-rail-group-header     — Gruppen-Header (1 pro Gruppe)
//   compare-rail-new-btn          — "+ NEU"-Button
//   location-wizard               — Wizard-Dialog-Container
//   location-wizard-stepper       — Stepper mit 3 Schritten
//   location-wizard-lat           — Lat-Input (Schritt 1)
//   location-wizard-lon           — Lon-Input (Schritt 1)
//   location-wizard-next          — "Weiter"-Button
//   location-wizard-name          — Name-Input (Schritt 2)
//   location-wizard-save          — "Speichern"-Button (Schritt 3)

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('Compare: LocationsRail + NewLocationWizard (#249)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.goto('/compare');
	});

	// AC-1: Gruppen-Header mit Zähler sichtbar.
	test('AC-1: Rail zeigt Gruppen-Header mit Zähler', async ({ page }) => {
		const rail = page.getByTestId('compare-rail');
		await expect(rail).toBeVisible();

		const groupHeaders = page.getByTestId('compare-rail-group-header');
		await expect(groupHeaders.first()).toBeVisible();

		// Gruppen-Header enthält Zähler-Pattern "(N)"
		const headerText = await groupHeaders.first().textContent();
		expect(headerText).toMatch(/\(\d+\)/);
	});

	// AC-2: Suchfeld filtert Locations nach Name oder Gruppe.
	test('AC-2: Rail-Suchfeld filtert Locations', async ({ page }) => {
		const search = page.getByTestId('compare-rail-search');
		await expect(search).toBeVisible();

		// Alle Gruppen-Header sichtbar vor Suche
		const headersBefore = await page.getByTestId('compare-rail-group-header').count();
		expect(headersBefore).toBeGreaterThan(0);

		// Suche nach unbekanntem Begriff → keine Gruppen-Header
		await search.fill('xyzxyz_nicht_existent');
		const headersAfter = await page.getByTestId('compare-rail-group-header').count();
		expect(headersAfter).toBe(0);

		// Suche zurücksetzen → wieder alle sichtbar
		await search.fill('');
		const headersReset = await page.getByTestId('compare-rail-group-header').count();
		expect(headersReset).toBe(headersBefore);
	});

	// AC-3: Chip-Filter-Toggle.
	test('AC-3: Gruppen-Chip-Filter zeigt nur gewählte Gruppe, zweiter Klick hebt auf', async ({
		page
	}) => {
		const chips = page.getByTestId('compare-rail-chip');
		await expect(chips.first()).toBeVisible();

		const firstChipLabel = await chips.first().getAttribute('aria-label');
		expect(firstChipLabel).toBeTruthy();

		// Chip anklicken → nur diese Gruppe sichtbar
		await chips.first().click();
		const headersFiltered = await page.getByTestId('compare-rail-group-header').count();
		expect(headersFiltered).toBeLessThanOrEqual(1);

		// Nochmal klicken → Filter aufgehoben
		await chips.first().click();
		const headersUnfiltered = await page.getByTestId('compare-rail-group-header').count();
		expect(headersUnfiltered).toBeGreaterThan(0);
	});

	// AC-4: "+ NEU"-Button öffnet Wizard mit 3-Schritt-Stepper.
	test('AC-4: "+ NEU"-Button öffnet Wizard mit 3-Schritt-Stepper', async ({ page }) => {
		const newBtn = page.getByTestId('compare-rail-new-btn');
		await expect(newBtn).toBeVisible();

		await newBtn.click();

		const wizard = page.getByTestId('location-wizard');
		await expect(wizard).toBeVisible();

		const stepper = page.getByTestId('location-wizard-stepper');
		await expect(stepper).toBeVisible();

		// Stepper zeigt 3 Schritte
		const steps = stepper.getByTestId(/trip-wizard-step-[123]/);
		await expect(steps).toHaveCount(3);

		// Schritt 1 ist aktiv
		const step1 = page.getByTestId('trip-wizard-step-1');
		await expect(step1).toHaveAttribute('data-state', 'active');
	});

	// AC-5: Weiter-Navigation von Schritt 1 zu Schritt 2.
	test('AC-5: Weiter mit gültigen Koordinaten → Schritt 2', async ({ page }) => {
		await page.getByTestId('compare-rail-new-btn').click();
		await expect(page.getByTestId('location-wizard')).toBeVisible();

		// Koordinaten eingeben
		const latInput = page.getByTestId('location-wizard-lat');
		const lonInput = page.getByTestId('location-wizard-lon');
		await expect(latInput).toBeVisible();
		await expect(lonInput).toBeVisible();

		await latInput.fill('47.1234');
		await lonInput.fill('11.5678');

		// Weiter klicken
		const nextBtn = page.getByTestId('location-wizard-next');
		await expect(nextBtn).toBeVisible();
		await nextBtn.click();

		// Schritt 2 ist jetzt aktiv
		const step2 = page.getByTestId('trip-wizard-step-2');
		await expect(step2).toHaveAttribute('data-state', 'active');

		// Name-Feld sichtbar
		await expect(page.getByTestId('location-wizard-name')).toBeVisible();
	});

	// AC-6: Vollständiger Durchlauf → Speichern → Location erscheint in Rail.
	test('AC-6: Neuen Ort anlegen → erscheint in Rail', async ({ page }) => {
		const uniqueName = `Testort E2E ${Date.now()}`;

		// Wizard öffnen
		await page.getByTestId('compare-rail-new-btn').click();
		await expect(page.getByTestId('location-wizard')).toBeVisible();

		// Schritt 1: Koordinaten
		await page.getByTestId('location-wizard-lat').fill('47.5');
		await page.getByTestId('location-wizard-lon').fill('12.5');
		await page.getByTestId('location-wizard-next').click();

		// Schritt 2: Name
		await expect(page.getByTestId('location-wizard-name')).toBeVisible();
		await page.getByTestId('location-wizard-name').fill(uniqueName);
		await page.getByTestId('location-wizard-next').click();

		// Schritt 3: Aktivitätsprofil (erstes auswählen)
		const saveBtn = page.getByTestId('location-wizard-save');
		await expect(saveBtn).toBeVisible();
		await saveBtn.click();

		// Dialog geschlossen
		await expect(page.getByTestId('location-wizard')).not.toBeVisible();

		// Location in der Rail sichtbar
		const rail = page.getByTestId('compare-rail');
		await expect(rail).toContainText(uniqueName);
	});
});
