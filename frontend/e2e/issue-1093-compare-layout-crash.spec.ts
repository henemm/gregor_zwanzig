import { test, expect, type Page } from '@playwright/test';

// E2E — Issue #1093 (aus #1092 Punkt 1): Orts-Vergleich, Tab "Layout" lädt nicht.
//
// Spec: docs/specs/modules/issue_1093_compare_layout_preview_crash.md
//
// Root Cause (LayoutPreview.svelte Z. 20-24): `rows` filtert die statischen
// DUMMY_LOCATIONS (feste Fantasie-IDs loc-01/07/08) nach `pickedIds`. Sobald echte
// Orte gewählt sind, enthält `pickedIds` echte Location-UUIDs → der Filter matcht nie
// → `rows = []` → Template greift auf `rows[0].name` / `rows[0].feels` zu → wirft
// "Cannot read properties of undefined (reading 'feels')" → Render von Step4Layout
// crasht → der Lade-Zustand ("Lade Metriken-Katalog…", data-testid step4-loading)
// wird nie ersetzt.
//
// RED-Erwartung (aktuelles Staging, vor Fix):
//   AC-1: schlägt fehl — `step4-loading` bleibt sichtbar UND es tritt ein pageerror
//         "reading 'feels'" auf.
//   AC-2: schlägt fehl — die Vorschau-Tabelle rendert nicht (leer/gecrasht).
//
// Ausführen (gegen Staging, aus frontend/):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env
//   source /home/hem/gregor_zwanzig_staging/.env; set +a
//   npx playwright test --config=e2e/playwright.1093.staging.config.ts

// CompareEditor rendert Desktop- (.cm-desktop) und Mobile-Markup gleichzeitig im DOM
// (Issue #682) und schaltet nur per CSS-Breakpoint. Bei Viewport 1280×900 ist nur
// .cm-desktop sichtbar — alle Locators werden darauf gescoped.
function desktop(page: Page) {
	return page.locator('.cm-desktop');
}

/** Öffnet /compare/new, benennt den Vergleich, wählt 2 echte Bibliotheks-Orte und
 *  navigiert bis zum freigeschalteten Layout-Tab. */
async function gotoLayoutTab(page: Page): Promise<void> {
	const D = desktop(page);
	await page.goto('/compare/new', { waitUntil: 'networkidle' });

	await D.getByTestId('compare-editor-name').first().fill('E2E 1093 Layout');
	await D.getByTestId('compare-editor-tab-orte').first().click();

	// 2 gespeicherte Orte per Library-Button wählen (echte Location-IDs).
	const libBtns = D.getByTestId('compare-step2-library').locator('button');
	await expect(libBtns.first()).toBeVisible();
	const count = await libBtns.count();
	expect(count, 'mindestens 2 gespeicherte Orte auf Staging nötig').toBeGreaterThanOrEqual(2);
	await libBtns.nth(0).click();
	await libBtns.nth(1).click();

	// Idealwerte öffnen (schaltet Layout frei), dann Layout.
	await D.getByTestId('compare-editor-tab-idealwerte').first().click();
	await D.getByTestId('compare-editor-tab-layout').first().click();
}

test('AC-1: Layout-Tab lädt ohne pageerror, Spinner verschwindet', async ({ page }) => {
	const pageErrors: string[] = [];
	page.on('pageerror', (e) => pageErrors.push(e.message));

	await gotoLayoutTab(page);

	// Der Lade-Spinner muss innerhalb von 5s verschwinden.
	await expect(page.getByTestId('step4-loading').first()).toBeHidden({ timeout: 5000 });

	// Vorschau muss sichtbar sein.
	await expect(page.getByTestId('compare-step4-layout-preview').first()).toBeVisible();

	// Kein Render-Crash.
	expect(pageErrors, `pageerrors: ${pageErrors.join(' | ')}`).toHaveLength(0);
});

test('AC-2: Vorschau-Tabelle rendert ≥1 Zeile mit Ort-Name, kein "undefined"', async ({ page }) => {
	await gotoLayoutTab(page);

	const preview = page.getByTestId('compare-step4-layout-preview').first();
	await expect(preview).toBeVisible({ timeout: 5000 });

	// Mindestens eine Datenzeile in der Vorschau-Tabelle.
	const rows = preview.locator('tbody tr');
	await expect(rows.first()).toBeVisible();
	expect(await rows.count()).toBeGreaterThanOrEqual(1);

	// Kein "undefined" im gerenderten Vorschau-Text.
	const text = (await preview.innerText()).toLowerCase();
	expect(text).not.toContain('undefined');
});
