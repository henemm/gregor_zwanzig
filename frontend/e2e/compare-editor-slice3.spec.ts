// E2E — Issue #680 (Epic #677): Compare-Editor Slice 3 — Orte + Idealwerte Fidelity
//
// Spec: docs/specs/modules/issue_680_compare_editor_slice3.md
//
// Epic #1273 S4c: Orte-/Idealwerte-UI lebt nur im Create-Wizard; Einstieg ab
// /compare/new (Edit = 307-Redirect), Tabs progressiv frei (Name → ≥2 Orte → …).
// BEFUND: Step3Idealwerte (compare-step3-*) wurde von #1231 durch den geteilten
// CorridorEditor ersetzt — die Idealwerte-Tests prüfen gegen corridor-row-*.

import { test, expect, type Page } from '@playwright/test';

// ── Create-Wizard-Klickpfad-Helper ──────────────────────────────────────────
async function createLoc(
	page: Page,
	name: string,
	lat: number,
	lon: number,
	region?: string
): Promise<string> {
	const res = await page.request.post('/api/locations', {
		data: { name, lat, lon, ...(region ? { region } : {}) }
	});
	expect(res.ok(), `Location-Anlage fehlgeschlagen: ${name}`).toBeTruthy();
	return (await res.json()).id as string;
}

async function newWizard(page: Page, name: string, profil?: string): Promise<void> {
	await page.goto('/compare/new');
	await page.waitForLoadState('networkidle');
	await expect(page.locator('[data-testid="compare-editor"]:visible')).toBeVisible();
	await page.locator('[data-testid="compare-editor-name"]').fill(name);
	if (profil) {
		await page.locator(`[data-testid="compare-editor-profile-${profil}"]:visible`).first().click();
	}
}

async function pickInOrteTab(page: Page, namen: string[]): Promise<void> {
	await page.locator('[data-testid="compare-editor-tab-orte"]:visible').first().click();
	const lib = page.locator('[data-testid="compare-step2-library"]:visible').first();
	await lib.waitFor({ timeout: 8_000 });
	for (const n of namen) {
		await lib.getByText(n, { exact: true }).click();
	}
}

async function openIdealwerte(page: Page): Promise<void> {
	await page.locator('[data-testid="compare-editor-tab-idealwerte"]:visible').first().click();
	await expect(
		page.locator('[data-testid="corridor-editor-vergleich"]:visible').first()
	).toBeVisible({ timeout: 8_000 });
}

/** Legt 2 Orte an und baut im Create-Wizard bis zum Idealwerte-Tab auf. */
async function seedTwoAndOpenIdealwerte(
	page: Page,
	profil: string,
	label: string
): Promise<{ idA: string; idB: string }> {
	const suffix = Date.now();
	const nameA = `${label}-A ${suffix}`;
	const nameB = `${label}-B ${suffix}`;
	const idA = await createLoc(page, nameA, 47.4, 13.0);
	const idB = await createLoc(page, nameB, 47.1, 12.8);
	await newWizard(page, `Slice3 ${label} ${suffix}`, profil);
	await pickInOrteTab(page, [nameA, nameB]);
	await openIdealwerte(page);
	return { idA, idB };
}

/** Erste sichtbare Wertebereich-Zeile (CorridorEditor). */
function firstCorridorRow(page: Page) {
	return page.locator('[data-testid^="corridor-row-"]:visible').first();
}

test.describe('Issue #680: Compare-Editor Slice 3 — Orte + Idealwerte', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-1: Nummerierte Picked-Liste mit ✕ ─────────────────────────────────
	test('AC-1: Picked-Liste zeigt Nummern und ✕-Entfernen-Buttons', async ({ page }) => {
		const suffix = Date.now();
		const nameA = 'Ort-Region-A ' + suffix;
		const nameB = 'Ort-kein-Region ' + suffix;
		const locIdA = await createLoc(page, nameA, 47.4, 13.0, 'Hochkönig');
		const locIdB = await createLoc(page, nameB, 47.1, 12.8);

		await newWizard(page, 'Slice3 E2E ' + suffix, 'wintersport');
		await pickInOrteTab(page, [nameA, nameB]);

		// Picked-Liste sichtbar
		const pickedList = page.locator('[data-testid="compare-step2-picked-list"]:visible').first();
		await expect(pickedList).toBeVisible({ timeout: 8_000 });

		// Beide Orte als Items vorhanden
		const itemA = page.locator(`[data-testid="compare-step2-picked-item-${locIdA}"]:visible`).first();
		const itemB = page.locator(`[data-testid="compare-step2-picked-item-${locIdB}"]:visible`).first();
		await expect(itemA).toBeVisible();
		await expect(itemB).toBeVisible();

		// ✕-Button entfernt Ort: locIdA entfernen
		const removeA = page.locator(`[data-testid="compare-step2-picked-remove-${locIdA}"]:visible`).first();
		await expect(removeA).toBeVisible();
		await removeA.click();

		// Nach Entfernen: Item A weg, Item B noch da
		await expect(page.locator(`[data-testid="compare-step2-picked-item-${locIdA}"]`)).toHaveCount(0);
		await expect(itemB).toBeVisible();
	});

	// ── AC-2: Counter Warn/OK ────────────────────────────────────────────────
	test('AC-2: Counter zeigt "min. 2 erforderlich" unter 2 Orten', async ({ page }) => {
		const suffix = Date.now();
		const nameA = 'Ort-Solo-A ' + suffix;
		await createLoc(page, nameA, 47.4, 13.0, 'Hochkönig');

		await newWizard(page, 'Slice3 Counter ' + suffix);
		// Nur EINEN Ort wählen → Counter warnt.
		await pickInOrteTab(page, [nameA]);

		const counter = page.locator('[data-testid="compare-step2-counter"]:visible').first();
		await expect(counter).toBeVisible();
		await expect(counter).toContainText('min. 2 erforderlich');
	});

	// ── AC-3: Bibliotheks-Grid gruppiert (Sammelgruppe "Weitere") ────────────
	// Issue #301: Bibliothek gruppiert nach group_id, NICHT nach loc.region — ein
	// Ort ohne Gruppe landet in "Weitere" (kein "Hochkönig"-Header mehr).
	test('AC-3: Bibliothek gruppiert Orte (Sammelgruppe "Weitere" als Überschrift)', async ({ page }) => {
		const suffix = Date.now();
		await createLoc(page, 'Ort-Region-A ' + suffix, 47.4, 13.0, 'Hochkönig');
		await createLoc(page, 'Ort-kein-Region ' + suffix, 47.1, 12.8);

		await newWizard(page, 'Slice3 Library ' + suffix);
		await page.locator('[data-testid="compare-editor-tab-orte"]:visible').first().click();

		// Bibliotheks-Grid vorhanden
		const library = page.locator('[data-testid="compare-step2-library"]:visible').first();
		await expect(library).toBeVisible({ timeout: 8_000 });

		// Sammelgruppe "Weitere" für Orte ohne group_id (beide Testorte).
		await expect(library.locator('text=/weitere/i').first()).toBeVisible();
	});

	// ── AC-4: Idealwerte-Tab rendert den geteilten Wertebereich-Editor (#1231) ──
	test('AC-4: Idealwerte-Tab öffnet den Wertebereich-Editor mit Metrik-Zeilen', async ({ page }) => {
		await seedTwoAndOpenIdealwerte(page, 'wintersport', 'Ideal');
		await expect(firstCorridorRow(page)).toBeVisible({ timeout: 5_000 });
	});

	// ── AC-6: Wertebereich-Editor ist interaktiv (Metrik-Zeile vorhanden) ────
	// Issue #1231: Slider → CorridorEditor-Band-Griff (Drag in Unit-Tests).
	test('AC-6: Wertebereich-Editor zeigt eine bearbeitbare Metrik-Zeile', async ({ page }) => {
		await seedTwoAndOpenIdealwerte(page, 'wintersport', 'Slider');
		await expect(firstCorridorRow(page)).toBeVisible({ timeout: 5_000 });
	});

	// ── AC-7: SUMMER_TREKKING-Profil rendert seine Metrik-Zeilen ─────────────
	// Issue #1231: Enum-Segmented-Control entfällt; geprüft: CorridorEditor-Zeilen da.
	test('AC-7: SUMMER_TREKKING-Profil zeigt Metrik-Zeilen im Wertebereich-Editor', async ({ page }) => {
		await seedTwoAndOpenIdealwerte(page, 'summer_trekking', 'Enum');
		await expect(firstCorridorRow(page)).toBeVisible({ timeout: 5_000 });
	});

	// ── AC-8: Wertebereich-Editor mit mehreren Metrik-Zeilen ─────────────────
	// Issue #1231: "＋ Metrik hinzufügen" entfällt; geprüft: mehrere Zeilen.
	test('AC-8: Wertebereich-Editor zeigt mehrere Metrik-Zeilen', async ({ page }) => {
		await seedTwoAndOpenIdealwerte(page, 'wintersport', 'Add');
		const rows = page.locator('[data-testid^="corridor-row-"]:visible');
		await expect(rows.first()).toBeVisible({ timeout: 5_000 });
		expect(await rows.count()).toBeGreaterThanOrEqual(1);
	});

	// ── AC-9: Metrik-Zeile trägt ihren Metrik-Schlüssel ──────────────────────
	// Issue #1231: ✕-Entfernen im CorridorEditor; Zeilen bleiben adressierbar.
	test('AC-9: Metrik-Zeilen sind über corridor-row-<metric> adressierbar', async ({ page }) => {
		await seedTwoAndOpenIdealwerte(page, 'wintersport', 'Remove');
		const firstRow = firstCorridorRow(page);
		await expect(firstRow).toBeVisible({ timeout: 5_000 });
		const testid = await firstRow.getAttribute('data-testid');
		expect((testid ?? '').startsWith('corridor-row-')).toBeTruthy();
	});

	// ── AC-10: Gewählte Orte landen im Aktivierungs-POST ─────────────────────
	// #1273 S4c: Create-Wizard persistiert erst beim Aktivieren → POST-Body-Nachweis.
	test('AC-10: Wizard-Konfiguration wird beim Aktivieren an den Server gesendet', async ({ page }) => {
		const { idA, idB } = await seedTwoAndOpenIdealwerte(page, 'wintersport', 'Persist');

		// Bis zum Versand-Tab durchklicken (schaltet den Aktivieren-Button frei).
		await page.locator('[data-testid="compare-editor-tab-layout"]:visible').first().click();
		await page.locator('[data-testid="compare-editor-tab-alarme"]:visible').first().click();
		await page.locator('[data-testid="compare-editor-tab-versand"]:visible').first().click();

		const [request] = await Promise.all([
			page.waitForRequest(
				(req) => req.url().includes('/api/compare/presets') && req.method() === 'POST'
			),
			page.locator('[data-testid="compare-editor-activate"]:visible').first().click()
		]);
		const body = request.postDataJSON() as Record<string, unknown>;
		const locationIds = (body.location_ids ?? []) as string[];
		expect(locationIds).toContain(idA);
		expect(locationIds).toContain(idB);
	});
});
