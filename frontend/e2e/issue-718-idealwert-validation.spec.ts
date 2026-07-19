// E2E — Wizard-Orte-Gate ("Weiter erst ab 2 Orten") im Compare-Create-Wizard.
// (Dateiname bewusst beibehalten — Spec-Greps referenzieren ihn.)
// Spec: docs/specs/modules/issue_718_compare_editor_slice4_validierung.md
// Epic #1273 S4c: Die frühere min>max-Validierung lebt seit #1231 als Clamping im
// CorridorEditor (unit-getestet, corridorEditorState.test.ts) — ihre E2E-Fälle
// wurden entfernt. Hier bleibt das Orte-Gate: der Weiter-Button
// (compare-editor-continue-metriken) ist disabled bis ≥2 Orte gewählt sind.
// Epic #1301 F2a: der Orte-Weiter-Knopf führt jetzt ehrlich zum NEUEN
// Wetter-Metriken-Tab (Ziel-benannt), nicht mehr direkt zu Wertebereiche.

import { test, expect, type Page } from '@playwright/test';
import { login } from './helpers.js';

async function createLoc(page: Page, name: string, lat: number, lon: number): Promise<string> {
	const res = await page.request.post('/api/locations', { data: { name, lat, lon } });
	expect(res.ok(), `Location-Anlage fehlgeschlagen: ${name}`).toBeTruthy();
	return (await res.json()).id as string;
}

test.describe('Compare-Create-Wizard: Orte-Gate (Weiter erst ab 2 Orten) [Issue #718 / #1231]', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-2: Weiter-Button disabled bis 2 Orte gewählt (echter Klickpfad ab /compare/new) ──
	test('AC-2: Weiter-Button im Wizard ist disabled bis 2 Orte gewählt sind', async ({ page }) => {
		const suffix = Date.now();
		const nameA = 'Idealwert-A ' + suffix;
		const nameB = 'Idealwert-B ' + suffix;
		await createLoc(page, nameA, 47.4, 13.0);
		await createLoc(page, nameB, 47.1, 12.8);

		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');
		await expect(page.locator('[data-testid="compare-editor"]:visible')).toBeVisible();
		await page.locator('[data-testid="compare-editor-name"]').fill('Validierungstest 718 ' + suffix);

		// Orte-Tab: noch kein Ort gewählt → Weiter-Button disabled.
		await page.locator('[data-testid="compare-editor-tab-orte"]:visible').first().click();
		const weiter = page.locator('[data-testid="compare-editor-continue-metriken"]:visible').first();
		await expect(weiter).toBeVisible({ timeout: 8_000 });
		await expect(weiter).toBeDisabled();

		// Zwei Orte aus der Bibliothek wählen → Weiter-Button wird aktiv.
		const lib = page.locator('[data-testid="compare-step2-library"]:visible').first();
		await lib.waitFor({ timeout: 8_000 });
		await lib.getByText(nameA, { exact: true }).click();
		await lib.getByText(nameB, { exact: true }).click();

		await expect(weiter).toBeEnabled({ timeout: 5_000 });
	});
});
