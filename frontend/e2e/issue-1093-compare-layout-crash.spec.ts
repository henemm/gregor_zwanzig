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
 *  öffnet den Reiter, der seit #1360 den früheren Layout-Inhalt trägt
 *  (Wetter-Metriken mit der Stundenverlauf-Steuerung). */
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

	await D.getByTestId('compare-editor-tab-wetter-metriken').first().click();
}

// Stand #2287-Nachbarschaft: Der Layout-Reiter (Step4Layout mit LayoutPreview,
// `step4-loading`/`compare-step4-layout-preview`) ist per #1360 aufgelöst; die
// Crash-Oberfläche von #1093 existiert nicht mehr. AC-1 prüft deshalb den
// Nachfolger — Wetter-Metriken mit echten Orten rendert ohne pageerror. AC-2
// (Vorschau-Tabelle) ist GELÖSCHT: die Vorschau-Tabelle gibt es nicht mehr
// (layout-tab-vergleich.spec.ts AC-11 prüft ausdrücklich ihre Abwesenheit).
test('AC-1: Wetter-Metriken (früher Layout) lädt mit echten Orten ohne pageerror', async ({ page }) => {
	const pageErrors: string[] = [];
	page.on('pageerror', (e) => pageErrors.push(e.message));

	await gotoLayoutTab(page);

	await expect(
		desktop(page).getByTestId('compare-layout-hourly-enabled-toggle').first()
	).toBeVisible({ timeout: 10_000 });

	// Kein Render-Crash.
	expect(pageErrors, `pageerrors: ${pageErrors.join(' | ')}`).toHaveLength(0);
});
