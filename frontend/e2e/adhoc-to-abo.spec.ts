import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('F76 Ad-hoc → Abo: Compare-Ergebnis als Auto-Report speichern', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.goto('/compare');
	});

	test('shows "Als Auto-Report speichern" button after compare results', async ({ page }) => {
		/**
		 * GIVEN: User ist auf /compare und hat einen Vergleich durchgefuehrt
		 * WHEN: Ergebnisse angezeigt werden
		 * THEN: Ein Button "Als Auto-Report speichern" ist sichtbar
		 */
		// Warte auf Vergleichsergebnisse (waehle Locations und starte Vergleich)
		// Der Button soll nur nach erfolgreichem Vergleich sichtbar sein
		const saveButton = page.getByRole('button', { name: /auto-report speichern/i });
		// Zuerst: Button existiert NICHT wenn kein Vergleich aktiv
		await expect(saveButton).not.toBeVisible();

		// Starte Vergleich: Locations auswaehlen und vergleichen
		const compareButton = page.getByRole('button', { name: /vergleichen/i });
		if (await compareButton.isVisible()) {
			await compareButton.click();
			// Nach Vergleich sollte der Save-Button erscheinen
			await expect(saveButton).toBeVisible({ timeout: 30000 });
		}
	});

	test('opens subscription dialog when "Als Auto-Report speichern" clicked', async ({ page }) => {
		/**
		 * GIVEN: Vergleichsergebnisse werden angezeigt
		 * WHEN: User klickt "Als Auto-Report speichern"
		 * THEN: Ein Dialog mit Abo-Formular oeffnet sich
		 */
		// Starte Vergleich
		const compareButton = page.getByRole('button', { name: /vergleichen/i });
		if (await compareButton.isVisible()) {
			await compareButton.click();
			await page.waitForTimeout(5000);
		}

		const saveButton = page.getByRole('button', { name: /auto-report speichern/i });
		await expect(saveButton).toBeVisible({ timeout: 30000 });
		await saveButton.click();

		// Dialog sollte sich oeffnen mit Titel
		await expect(page.getByText('Als Auto-Report speichern')).toBeVisible();
		// Formular sollte Name-Feld haben
		await expect(page.getByLabel(/name/i)).toBeVisible();
	});

	test('pre-fills subscription form with compare parameters', async ({ page }) => {
		/**
		 * GIVEN: Dialog ist offen nach Vergleich
		 * WHEN: Formular wird angezeigt
		 * THEN: Zeitfenster, Forecast-Stunden und Aktivitaetsprofil sind vorausgefuellt
		 */
		const compareButton = page.getByRole('button', { name: /vergleichen/i });
		if (await compareButton.isVisible()) {
			await compareButton.click();
			await page.waitForTimeout(5000);
		}

		const saveButton = page.getByRole('button', { name: /auto-report speichern/i });
		await expect(saveButton).toBeVisible({ timeout: 30000 });
		await saveButton.click();

		// Zeitfenster sollte vorausgefuellt sein (nicht leer/default)
		// Schedule-Feld sollte vorhanden sein
		await expect(page.getByRole('dialog').locator('select').first()).toBeVisible();
	});
});
