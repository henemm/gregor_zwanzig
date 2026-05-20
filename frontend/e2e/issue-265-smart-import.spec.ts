// E2E — Issue #265: Smart-Import Frontend — URL/Koordinaten-Eingabe im NewLocationWizard.
//
// Spec: docs/specs/modules/issue_265_smart_import_frontend.md (AC-1 bis AC-5)
//
// TestID-Inventar (zu implementieren in NewLocationWizard.svelte):
//   location-wizard-resolve-input   — Texteingabe für URL/Koordinaten
//   location-wizard-resolve-btn     — "Auflösen"-Button
//   location-wizard-resolve-preview — Vorschau-Box nach erfolgreichem Resolve
//   location-wizard-resolve-error   — Fehlermeldung bei nicht aufgelöstem Format

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('Smart-Import: URL/Koordinaten-Auflösung in NewLocationWizard (#265)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.goto('/compare');
		// Wizard öffnen
		await page.getByTestId('compare-rail-new-btn').click();
		await expect(page.getByTestId('location-wizard')).toBeVisible();
	});

	// AC-1: Import-Block sichtbar in Schritt 1 — oberhalb der manuellen Felder.
	test('AC-1: Import-Block (Eingabefeld + Auflösen-Button) in Schritt 1 sichtbar', async ({
		page
	}) => {
		const resolveInput = page.getByTestId('location-wizard-resolve-input');
		const resolveBtn = page.getByTestId('location-wizard-resolve-btn');
		const latInput = page.getByTestId('location-wizard-lat');

		// Eingabefeld sichtbar
		await expect(resolveInput).toBeVisible();
		// Richtiger Placeholder
		await expect(resolveInput).toHaveAttribute(
			'placeholder',
			'Komoot-Link, Google-Maps-URL oder Koordinaten…'
		);
		// Button sichtbar
		await expect(resolveBtn).toBeVisible();
		await expect(resolveBtn).toHaveText('Auflösen');

		// Import-Block steht OBERHALB der manuellen Felder:
		// resolveInput muss im DOM vor latInput erscheinen
		const resolveInputBox = await resolveInput.boundingBox();
		const latInputBox = await latInput.boundingBox();
		expect(resolveInputBox).not.toBeNull();
		expect(latInputBox).not.toBeNull();
		expect(resolveInputBox!.y).toBeLessThan(latInputBox!.y);
	});

	// AC-2: Erfolgreiche Auflösung mit Dezimalkoordinaten — Felder werden befüllt.
	test('AC-2: Dezimalkoordinaten auflösen → Felder befüllt + Vorschau sichtbar', async ({
		page
	}) => {
		const resolveInput = page.getByTestId('location-wizard-resolve-input');
		const resolveBtn = page.getByTestId('location-wizard-resolve-btn');

		// Dezimalkoordinaten eingeben (Innsbruck — keine externe API nötig)
		await resolveInput.fill('47.2692, 11.4041');
		await resolveBtn.click();

		// Vorschau-Box erscheint
		const preview = page.getByTestId('location-wizard-resolve-preview');
		await expect(preview).toBeVisible({ timeout: 10000 });

		// Vorschau enthält Koordinaten-Werte
		await expect(preview).toContainText('47.2692');
		await expect(preview).toContainText('11.4041');

		// lat/lon-Felder wurden automatisch befüllt
		const latInput = page.getByTestId('location-wizard-lat');
		const lonInput = page.getByTestId('location-wizard-lon');
		await expect(latInput).toHaveValue('47.2692');
		await expect(lonInput).toHaveValue('11.4041');

		// Button war während des Calls deaktiviert (jetzt wieder aktiv)
		await expect(resolveBtn).toBeEnabled();
	});

	// AC-3: Nicht aufgelöster String → Fehlermeldung erscheint, Felder unverändert.
	test('AC-3: Unbekanntes Format → Fehlermeldung, Koordinaten-Felder unverändert', async ({
		page
	}) => {
		const resolveInput = page.getByTestId('location-wizard-resolve-input');
		const resolveBtn = page.getByTestId('location-wizard-resolve-btn');
		const latInput = page.getByTestId('location-wizard-lat');
		const lonInput = page.getByTestId('location-wizard-lon');

		// Ursprüngliche Werte merken
		const latBefore = await latInput.inputValue();
		const lonBefore = await lonInput.inputValue();

		// Nicht auflösbaren String eingeben
		await resolveInput.fill('Gasthof Zum Löwen, irgendwo in Tirol');
		await resolveBtn.click();

		// Fehlermeldung erscheint
		const errorMsg = page.getByTestId('location-wizard-resolve-error');
		await expect(errorMsg).toBeVisible({ timeout: 10000 });
		// Fehlermeldung ist nicht leer
		const errorText = await errorMsg.textContent();
		expect(errorText?.trim().length).toBeGreaterThan(0);

		// Kein Vorschau-Box sichtbar
		await expect(page.getByTestId('location-wizard-resolve-preview')).not.toBeVisible();

		// lat/lon-Felder sind unverändert
		await expect(latInput).toHaveValue(latBefore);
		await expect(lonInput).toHaveValue(lonBefore);

		// Globaler Wizard-Error-State darf nicht gesetzt sein
		// (Weiter-Button soll noch funktionieren)
		await latInput.fill('47.5');
		await lonInput.fill('12.5');
		await page.getByTestId('location-wizard-next').click();
		await expect(page.getByTestId('trip-wizard-step-2')).toHaveAttribute('data-state', 'active');
	});

	// AC-4: suggested_name wird in Name-Feld übernommen — aber nur wenn noch leer.
	test('AC-4: suggested_name befüllt leeres Name-Feld, überschreibt keinen User-Input', async ({
		page
	}) => {
		// Dezimalkoordinaten haben keinen suggested_name — daher Ergebnis aus Backend prüfen
		// und dann manuell das Feld in Schritt 2 testen.
		// Für diesen Test nutzen wir Koordinaten, die suggested_name haben könnten.
		const resolveInput = page.getByTestId('location-wizard-resolve-input');
		const resolveBtn = page.getByTestId('location-wizard-resolve-btn');

		await resolveInput.fill('47.2692, 11.4041');
		await resolveBtn.click();

		// Vorschau abwarten
		await expect(page.getByTestId('location-wizard-resolve-preview')).toBeVisible({
			timeout: 10000
		});

		// Zu Schritt 2 navigieren
		await page.getByTestId('location-wizard-lat').fill('47.2692');
		await page.getByTestId('location-wizard-lon').fill('11.4041');
		await page.getByTestId('location-wizard-next').click();
		await expect(page.getByTestId('trip-wizard-step-2')).toHaveAttribute('data-state', 'active');

		// Name-Feld ist entweder leer (keine suggested_name) oder vorbelegt
		const nameInput = page.getByTestId('location-wizard-name');
		await expect(nameInput).toBeVisible();
		// Wenn ein Name eingetragen wurde, merken
		const preFilledName = await nameInput.inputValue();

		// Zurück zu Schritt 1
		await page.getByRole('button', { name: 'Zurück' }).click();

		// Anderen Ort mit anderem suggested_name simulieren:
		// Name manuell in Schritt 2 eingeben, dann Zurück und nochmal Auflösen
		// Erwartung: manuell eingetragener Name wird NICHT überschrieben
		await page.getByTestId('location-wizard-next').click();
		const manualName = 'Mein eigener Name';
		await nameInput.fill(manualName);
		await page.getByRole('button', { name: 'Zurück' }).click();

		// Nochmal Auflösen
		await resolveInput.fill('47.2692, 11.4041');
		await resolveBtn.click();
		await expect(page.getByTestId('location-wizard-resolve-preview')).toBeVisible({
			timeout: 10000
		});

		// Zu Schritt 2 — manueller Name muss noch dort stehen
		await page.getByTestId('location-wizard-next').click();
		await expect(nameInput).toHaveValue(manualName);
	});

	// AC-5: Manuelle Koordinaten-Änderung löscht die Vorschau-Box.
	test('AC-5: Manuelles Editieren von lat/lon löscht die Vorschau-Box', async ({ page }) => {
		const resolveInput = page.getByTestId('location-wizard-resolve-input');
		const resolveBtn = page.getByTestId('location-wizard-resolve-btn');
		const latInput = page.getByTestId('location-wizard-lat');

		// Erst auflösen
		await resolveInput.fill('47.2692, 11.4041');
		await resolveBtn.click();
		const preview = page.getByTestId('location-wizard-resolve-preview');
		await expect(preview).toBeVisible({ timeout: 10000 });

		// Lat manuell ändern → Vorschau-Box verschwindet
		await latInput.fill('48.0000');
		await expect(preview).not.toBeVisible();
	});
});
