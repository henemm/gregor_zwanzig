import { test, expect } from '@playwright/test';

// E2E — Issue #1080: /compare/new — per Smart-Import angelegter Ort bleibt unsichtbar
// + kein Benennen möglich.
//
// Spec: docs/specs/modules/issue_1080_compare_new_url_add.md
//
// Root Cause (Step2Orte.svelte, ~Z. 48-50): `pickedLocations` löst `ws.pickedIds`
// gegen den STATISCHEN `locations`-Prop (Seiten-Load) auf. `addLocation()` /
// `addLocationFromFallback()` legen die Location per POST /api/locations an (201) und
// pushen die ID nach `ws.pickedIds`, aber die neue Location ist NICHT im `locations`-Prop
// → wird per `.filter(Boolean)` herausgefiltert → kein sichtbarer Eintrag.
//
// Statt der in der Spec genannten Google-Maps-Kurz-URL nutzt Test A einen Dezimal-
// Koordinaten-String ("43.0421, 6.1049") — das trifft denselben Root-Cause-Codepfad
// (Resolve → addLocation() → ws.pickedIds.push, Location fehlt im locations-Prop) OHNE
// Abhängigkeit von einer externen Google/Nominatim-Auflösung, und ist damit deterministisch
// gegen Staging ausführbar (Backend-Resolver erkennt Dezimalkoordinaten lokal, s.
// internal/resolver/coords.go::resolveDecimal).
//
// RED-Erwartung (aktuelles Staging, vor Fix):
//   Test A: schlägt fehl — der Picked-Eintrag erscheint NICHT in der Liste (Timeout beim
//           Warten auf [data-testid^="compare-step2-picked-item-"]), weil er durch das
//           stale locations-Prop herausgefiltert wird (AC-1).
//   Test B: schlägt fehl — [data-testid="compare-step2-name-input"] existiert noch nicht
//           in der "Erkannt"-Vorschau (AC-2).
//   Test C: schlägt fehl aus demselben Grund wie Test A, diesmal über den manuellen
//           Koordinaten-Fallback-Pfad (AC-3).
//
// Ausführen (gegen Staging, aus frontend/):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=e2e/playwright.1080.staging.config.ts

const UNIQUE_LAT_A = '43.0421';
const UNIQUE_LON_A = '6.1049';
const UNIQUE_LAT_B = '45.8326';
const UNIQUE_LON_B = '6.8652';

// CompareEditor rendert Desktop- (`.cm-desktop`) und Mobile-Markup (`.cm-mobile`)
// GLEICHZEITIG im DOM und schaltet nur per CSS-Breakpoint sichtbar/unsichtbar
// (Issue #682, s. CompareEditor.svelte Z. 553-556: ".cm-mobile sichtbar bei ≤899px").
// <Step2Orte> wird für BEIDEN Zweigen gemountet (Z. 532 + Z. 674) — jede
// data-testid-Query auf Step2-Elemente matcht daher zwei DOM-Knoten (strict-mode-
// Verstoß). Bei Viewport 1280×900 ist ausschließlich `.cm-desktop` sichtbar, daher
// werden alle Step2-Locators hier auf diesen Container gescoped.
function desktop(page: import('@playwright/test').Page) {
	return page.locator('.cm-desktop');
}

/** Legt einen frischen, eindeutig benannten Vergleich an und schaltet den "Orte"-Tab frei. */
async function createComparisonAndOpenOrteTab(page: import('@playwright/test').Page) {
	await page.goto('/compare/new');
	await page.waitForLoadState('networkidle');

	const nameInput = page.locator('[data-testid="compare-editor-name"]');
	await expect(nameInput).toBeVisible({ timeout: 15_000 });
	await nameInput.fill(`Bug-1080 E2E ${Date.now()}`);

	const continueBtn = page.locator('[data-testid="compare-editor-continue-orte"]');
	await expect(continueBtn).toBeVisible({ timeout: 5_000 });
	await continueBtn.click();

	const step2 = desktop(page).locator('[data-testid="compare-wizard-step-2"]');
	await expect(step2).toBeVisible({ timeout: 10_000 });
}

test.describe('Issue #1080: compare/new — Ort per URL/Koordinaten hinzufügen sichtbar machen', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-1 / AC-4 — Kern-Bug: neu angelegter Ort bleibt in der Picked-Liste unsichtbar ──
	test('AC-1/AC-4: per Smart-Import (Koordinaten) hinzugefügter Ort erscheint in der Im-Vergleich-Liste', async ({
		page
	}) => {
		await createComparisonAndOpenOrteTab(page);

		const importInput = desktop(page).locator('[data-testid="compare-step2-smart-import-input"]');
		await importInput.fill(`${UNIQUE_LAT_A}, ${UNIQUE_LON_A}`);

		const resolveBtn = desktop(page).locator('[data-testid="compare-step2-resolve-btn"]');
		await resolveBtn.click();

		// "Erkannt"-Vorschau abwarten (kein eigenes data-testid auf dem Preview-Block —
		// der Hinzufügen-Button existiert nur innerhalb von {#if preview}).
		const addBtn = desktop(page).getByRole('button', { name: /Zum Vergleich hinzufügen/ });
		await expect(addBtn).toBeVisible({ timeout: 15_000 });
		await addBtn.click();

		// RED: dieser Eintrag ist auf dem aktuellen Staging NICHT sichtbar, weil die neue
		// Location gegen das stale `locations`-Prop herausgefiltert wird.
		const pickedList = desktop(page).locator('[data-testid="compare-step2-picked-list"]');
		const pickedItem = pickedList.locator('[data-testid^="compare-step2-picked-item-"]');
		await expect(pickedItem).toBeVisible({ timeout: 8_000 });
		await expect(pickedItem).toHaveCount(1);

		// Header-Zähler "Im Vergleich · N" erhöht sich um 1.
		await expect(desktop(page).getByText('Im Vergleich · 1', { exact: false })).toBeVisible();

		// AC-4: angezeigter Name ist NICHT die rohe Eingabe (hier: Koordinaten-String,
		// nicht z.B. eine importierte URL). Bei Dezimal-Import ohne suggested_name ist der
		// Default aktuell `importInput` (roh) — nach Fix soll er dem Koordinaten-Format
		// entsprechen. Wir prüfen zumindest, dass NICHT der rohe Trenner-String "43.0421, 6.1049"
		// unverändert 1:1 als Ortsname übernommen wurde, sondern lat/lon im Namen erscheinen.
		await expect(pickedItem).toContainText(UNIQUE_LAT_A);
	});

	// ── AC-2 — Benennungsfeld in der "Erkannt"-Vorschau ─────────────────────────────────
	test('AC-2: Namensfeld in der Vorschau erlaubt Benennen vor dem Hinzufügen', async ({
		page
	}) => {
		await createComparisonAndOpenOrteTab(page);

		const importInput = desktop(page).locator('[data-testid="compare-step2-smart-import-input"]');
		await importInput.fill(`${UNIQUE_LAT_B}, ${UNIQUE_LON_B}`);

		const resolveBtn = desktop(page).locator('[data-testid="compare-step2-resolve-btn"]');
		await resolveBtn.click();

		const addBtn = desktop(page).getByRole('button', { name: /Zum Vergleich hinzufügen/ });
		await expect(addBtn).toBeVisible({ timeout: 15_000 });

		// RED: existiert auf aktuellem Staging noch nicht.
		const nameInput = desktop(page).locator('[data-testid="compare-step2-name-input"]');
		await expect(nameInput).toBeVisible({ timeout: 8_000 });

		const customName = `Mein Testort ${Date.now()}`;
		await nameInput.fill(customName);
		await addBtn.click();

		const pickedList = desktop(page).locator('[data-testid="compare-step2-picked-list"]');
		await expect(pickedList.getByText(customName, { exact: false })).toBeVisible({
			timeout: 8_000
		});
	});

	// ── AC-3 — Koordinaten-Fallback (manueller Pfad) ────────────────────────────────────
	test('AC-3: manueller Koordinaten-Fallback fügt Ort sichtbar zur Liste hinzu', async ({
		page
	}) => {
		await createComparisonAndOpenOrteTab(page);

		// Eingabe, die deterministisch KEIN Format erkennt (keine URL, keine Koordinaten,
		// keine DMS/UTM/GPX-Syntax) → löst zuverlässig den Fehler-/Fallback-Zweig aus.
		const importInput = desktop(page).locator('[data-testid="compare-step2-smart-import-input"]');
		await importInput.fill('nicht-erkennbare-eingabe-1080-xyz');

		const resolveBtn = desktop(page).locator('[data-testid="compare-step2-resolve-btn"]');
		await resolveBtn.click();

		const fallbackLat = desktop(page).locator('[data-testid="compare-step2-fallback-lat"]');
		const fallbackLon = desktop(page).locator('[data-testid="compare-step2-fallback-lon"]');
		await expect(fallbackLat).toBeVisible({ timeout: 8_000 });
		await expect(fallbackLon).toBeVisible();

		await fallbackLat.fill('47.2692');
		await fallbackLon.fill('11.4041');

		const fallbackAddBtn = desktop(page).locator('[data-testid="compare-step2-fallback-add-btn"]');
		await expect(fallbackAddBtn).toBeEnabled({ timeout: 5_000 });
		await fallbackAddBtn.click();

		// RED: derselbe Root Cause wie Test A — Eintrag verschwindet still.
		const pickedList = desktop(page).locator('[data-testid="compare-step2-picked-list"]');
		const pickedItem = pickedList.locator('[data-testid^="compare-step2-picked-item-"]');
		await expect(pickedItem).toBeVisible({ timeout: 8_000 });
		await expect(pickedItem).toHaveCount(1);
	});
});
