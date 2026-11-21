import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

// #3207 (tote Tests mitentfernen): die vier Fälle zur gruppierten Orts-Seitenleiste
// auf /compare (group-header, group-checkbox, group-section, Auf-/Zuklappen, Orte
// ohne Gruppe) sind entfernt — GroupSection.svelte ist mit #2288 gelöscht, /compare
// ist seit #439 eine Listen-Übersicht ohne Orts-Seitenleiste (0 Treffer für
// group-header/group-checkbox/group-section in frontend/src). Die Gruppierung der
// Orte bewacht heute src/lib/components/compare/__tests__/step2_orte_library_grouping.test.ts.
// Es bleibt der Fall zum Gruppen-Feld im Orts-Formular (Funktion lebt:
// LocationForm.svelte, data-testid="location-form-group").

test.describe('F76 Phase C2: Orts-Gruppen', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('LocationForm has group input field', async ({ page }) => {
		/**
		 * GIVEN: User opens location form
		 * WHEN: Form is displayed
		 * THEN: A group input field with datalist is present
		 */
		await page.goto('/locations');
		// Click "Neuer Ort" to open the form
		await page.click('button:has-text("Neuer Ort"), button:has-text("Hinzufügen")');
		const groupInput = page.locator('input#group, input[name="group"]');
		await expect(groupInput).toBeVisible();
	});
});
