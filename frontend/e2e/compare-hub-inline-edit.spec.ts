// E2E (Staging) — Issue #1256 Scheibe 6: Hub-Orte-Tab Drag/Entfernen/
// Add-Panel + eingebetteter CorridorEditor im Hub-Idealwerte-Tab
// (AC-14, AC-15, AC-31, AC-32, AC-33, AC-34).
//
// Spec: docs/specs/modules/issue_1256_compare_ui_rewire.md § Scheibe 6
// Context: docs/context/feat-1256-s6-hub-idealwerte-inline.md
//
// Ausführen (gegen Staging, aus frontend/):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=playwright.1256-s6.staging.config.ts

import { test, expect, type Page, type Locator } from '@playwright/test';

// Fix-Loop 1 (F003, Adversary MEDIUM): `svelte-dnd-action`s `dndzone` deaktiviert
// natives HTML5-Drag-and-Drop bewusst (node_modules/svelte-dnd-action/dist/index.js:
// draggableEl.draggable = false) und fährt eine eigene Pointer-/Maus-Event-basierte
// Drag-Logik mit 3px-Bewegungsschwelle (MIN_MOVEMENT_BEFORE_DRAG_START_PX). Playwrights
// `locator.dragTo()` erzeugt nur EINEN einzigen Move-Schritt und trifft diese Schwelle
// nicht zuverlässig — anders als natives HTML5-DnD (layout-tab-route.spec.ts:160), das
// hier NICHT als Präzedenzfall gilt. Stattdessen: manuelle Maus-Sequenz mit mehreren
// Zwischenschritten (bekanntes Kompatibilitätsmuster für svelte-dnd-action + Playwright).
async function dragDndZoneItem(page: Page, source: Locator, target: Locator): Promise<void> {
	const sourceBox = await source.boundingBox();
	const targetBox = await target.boundingBox();
	if (!sourceBox || !targetBox) throw new Error('dragDndZoneItem: source/target ohne BoundingBox');

	await page.mouse.move(sourceBox.x + sourceBox.width / 2, sourceBox.y + sourceBox.height / 2);
	await page.mouse.down();
	// Erster Zwischenschritt reißt sicher die 3px-Schwelle, damit dndzone den
	// Drag überhaupt als solchen erkennt (nicht als bloßen Klick).
	await page.mouse.move(sourceBox.x + sourceBox.width / 2, sourceBox.y + sourceBox.height / 2 - 12, {
		steps: 6
	});
	await page.waitForTimeout(120);
	await page.mouse.move(targetBox.x + targetBox.width / 2, targetBox.y + targetBox.height / 2, { steps: 15 });
	await page.waitForTimeout(120);
	await page.mouse.up();
}

let createdIds: string[] = [];
let createdLocationIds: string[] = [];

test.afterEach(async ({ page }) => {
	for (const id of createdIds) {
		try {
			await page.request.delete(`/api/compare/presets/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdIds = [];
	for (const id of createdLocationIds) {
		try {
			await page.request.delete(`/api/locations/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdLocationIds = [];
});

async function createLocation(page: Page, name: string, lat: number, lon: number): Promise<string> {
	const res = await page.request.post('/api/locations', { data: { name, lat, lon } });
	expect(res.ok(), 'Location-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	const id = body.id as string;
	createdLocationIds.push(id);
	return id;
}

async function createPresetWithLocations(
	page: Page,
	name: string,
	locationIds: string[],
	extra: Record<string, unknown> = {}
): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: locationIds,
			schedule: 'daily',
			profil: 'wintersport',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['urlauber@example.com'],
			...extra
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	const id = body.id as string;
	createdIds.push(id);
	return id;
}

test.describe('Issue #1256 Scheibe 6: Hub-Orte-Tab (AC-14/15/31/32)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-14/AC-15: Drag ändert Reihenfolge sofort + PUT + Reload-Persistenz ──
	test('AC-14/AC-15: Ort per Drag umsortieren löst PUT mit neuer location_ids-Reihenfolge aus, überlebt Reload', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E S6 Ort-A ${suffix}`, 47.26, 11.4);
		const locB = await createLocation(page, `E2E S6 Ort-B ${suffix}`, 47.1, 11.29);
		const locC = await createLocation(page, `E2E S6 Ort-C ${suffix}`, 47.05, 11.32);
		const name = `E2E S6 Reorder ${suffix}`;
		const id = await createPresetWithLocations(page, name, [locA, locB, locC]);

		await page.goto(`/compare/${id}?tab=orte`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-orte"]:visible').click();

		const rows = page.locator('[data-testid="hub-orte-row"]');
		await expect(rows).toHaveCount(3, { timeout: 10_000 });
		await expect(rows.nth(0)).toHaveAttribute('data-loc-id', locA);

		const source = page.locator(`[data-testid="hub-orte-row"][data-loc-id="${locC}"]`);
		const target = page.locator(`[data-testid="hub-orte-row"][data-loc-id="${locA}"]`);

		const putPromise = page.waitForResponse(
			(res) => res.url().includes(`/api/compare/presets/${id}`) && res.request().method() === 'PUT'
		);
		await dragDndZoneItem(page, source, target);
		const putRes = await putPromise;
		expect(putRes.ok(), 'PUT nach Drag fehlgeschlagen: ' + putRes.status()).toBeTruthy();
		const putBody = putRes.request().postDataJSON() as { location_ids: string[] };
		expect(putBody.location_ids[0]).toBe(locC);

		await expect(rows.nth(0)).toHaveAttribute('data-loc-id', locC, { timeout: 5_000 });

		// AC-15: Reload zeigt die zuletzt gespeicherte Reihenfolge.
		await page.reload();
		await page.waitForLoadState('networkidle');
		const reloadedRows = page.locator('[data-testid="hub-orte-row"]');
		await expect(reloadedRows.nth(0)).toHaveAttribute('data-loc-id', locC, { timeout: 5_000 });
	});

	// ── AC-31: "Ort hinzufügen" öffnet inline im Hub, kein Redirect ──────────
	test('AC-31: "Ort hinzufügen" öffnet ein Inline-Panel im Hub, URL bleibt /compare/{id}?tab=orte', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E S6 Add-Ort-A ${suffix}`, 47.4, 10.9);
		const locB = await createLocation(page, `E2E S6 Add-Ort-B ${suffix}`, 47.35, 10.85);
		const name = `E2E S6 AddPanel ${suffix}`;
		const id = await createPresetWithLocations(page, name, [locA]);

		await page.goto(`/compare/${id}?tab=orte`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-orte"]:visible').click();

		const addBtn = page.locator('[data-testid="hub-orte-add"]:visible');
		await expect(addBtn).toBeVisible({ timeout: 10_000 });
		await addBtn.click();

		const panel = page.locator('[data-testid="hub-orte-panel"]:visible');
		await expect(panel).toBeVisible({ timeout: 10_000 });
		await expect(page).toHaveURL(new RegExp(`/compare/${id}\\?tab=orte$`));

		await expect(panel).toContainText(`E2E S6 Add-Ort-B ${suffix}`, { timeout: 10_000 });
	});

	// ── AC-32: Entfernen persistiert per PUT, Zeile verschwindet, Tab bleibt ──
	test('AC-32: Entfernen-Klick löscht die Zeile und persistiert per PUT ohne Tab-Verlassen', async ({ page }) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E S6 Remove-Ort-A ${suffix}`, 47.2, 11.1);
		const locB = await createLocation(page, `E2E S6 Remove-Ort-B ${suffix}`, 47.15, 11.05);
		const name = `E2E S6 Remove ${suffix}`;
		const id = await createPresetWithLocations(page, name, [locA, locB]);

		await page.goto(`/compare/${id}?tab=orte`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-orte"]:visible').click();

		const rows = page.locator('[data-testid="hub-orte-row"]');
		await expect(rows).toHaveCount(2, { timeout: 10_000 });

		const removeBtn = page.locator(
			`[data-testid="hub-orte-row"][data-loc-id="${locB}"] [data-testid="hub-orte-remove"]`
		);
		const putPromise = page.waitForResponse(
			(res) => res.url().includes(`/api/compare/presets/${id}`) && res.request().method() === 'PUT'
		);
		await removeBtn.click();
		const putRes = await putPromise;
		expect(putRes.ok(), 'PUT nach Entfernen fehlgeschlagen: ' + putRes.status()).toBeTruthy();
		const putBody = putRes.request().postDataJSON() as { location_ids: string[] };
		expect(putBody.location_ids).toEqual([locA]);

		await expect(rows).toHaveCount(1, { timeout: 5_000 });
		await expect(page.locator('[data-testid="compare-detail-panel-orte"]:visible')).toBeVisible();
	});
});

test.describe('Issue #1256 Scheibe 6: Hub-Idealwerte-Tab (AC-16/33/34)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-33: Inline-Bearbeitung eines bestehenden Idealbereichs (min/max) ──
	test('AC-33: Zahlenfeld-Bearbeitung im eingebetteten CorridorEditor löst PUT aus (kein Redirect)', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E S6 Ideal-Ort ${suffix}`, 47.0, 11.0);
		const name = `E2E S6 IdealEdit ${suffix}`;
		const id = await createPresetWithLocations(page, name, [locA], {
			corridors: [{ metric: 'snow_depth_cm', range: [30, null], notify: false, mark: true }],
			display_config: {
				ideal_ranges: { snow_depth_cm: { min: 30, max: null } },
				active_metrics: ['snow_depth_cm']
			}
		});

		await page.goto(`/compare/${id}?tab=idealwerte`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-idealwerte"]:visible').click();

		const editor = page.locator('[data-testid="corridor-editor-vergleich"]:visible');
		await expect(editor).toBeVisible({ timeout: 10_000 });

		const row = editor.locator('[data-testid="corridor-row-snow_depth_cm"]');
		await expect(row).toBeVisible({ timeout: 10_000 });
		const minInput = row.locator('input[type="number"]').first();
		await minInput.fill('45');

		const putPromise = page.waitForResponse(
			(res) => res.url().includes(`/api/compare/presets/${id}`) && res.request().method() === 'PUT'
		);
		await minInput.blur();
		const putRes = await putPromise;
		expect(putRes.ok(), 'PUT nach Idealwert-Bearbeitung fehlgeschlagen: ' + putRes.status()).toBeTruthy();
		const putBody = putRes.request().postDataJSON() as { corridors: Array<{ metric: string; range: [number, number | null] }> };
		const edited = putBody.corridors.find((c) => c.metric === 'snow_depth_cm');
		expect(edited?.range[0]).toBe(45);

		await expect(page).not.toHaveURL(/\/edit/);
	});

	// ── AC-34: "Metrik hinzufügen" fügt eine neue Korridor-Zeile hinzu + PUT ──
	test('AC-34: "Metrik hinzufügen" im eingebetteten CorridorEditor legt eine neue Zeile an und persistiert per PUT', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E S6 AddMetrik-Ort ${suffix}`, 46.9, 10.8);
		const name = `E2E S6 AddMetrik ${suffix}`;
		const id = await createPresetWithLocations(page, name, [locA], {
			corridors: [{ metric: 'snow_depth_cm', range: [30, null], notify: false, mark: true }],
			display_config: {
				ideal_ranges: { snow_depth_cm: { min: 30, max: null } },
				active_metrics: ['snow_depth_cm']
			}
		});

		await page.goto(`/compare/${id}?tab=idealwerte`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-idealwerte"]:visible').click();

		const editor = page.locator('[data-testid="corridor-editor-vergleich"]:visible');
		await expect(editor).toBeVisible({ timeout: 10_000 });
		await expect(editor.locator('[data-testid="corridor-row-snow_depth_cm"]')).toBeVisible({ timeout: 10_000 });

		const poolBtn = editor.locator('.ce-pool-btn').first();
		await expect(poolBtn).toBeVisible({ timeout: 10_000 });

		const putPromise = page.waitForResponse(
			(res) => res.url().includes(`/api/compare/presets/${id}`) && res.request().method() === 'PUT'
		);
		await poolBtn.click();
		const putRes = await putPromise;
		expect(putRes.ok(), 'PUT nach Metrik-Hinzufügen fehlgeschlagen: ' + putRes.status()).toBeTruthy();
		const putBody = putRes.request().postDataJSON() as { corridors: Array<{ metric: string }> };
		expect(putBody.corridors.length).toBeGreaterThan(1);

		const rows = editor.locator('[data-testid^="corridor-row-"]');
		await expect(rows).toHaveCount(2, { timeout: 5_000 });
		await expect(page).not.toHaveURL(/\/edit/);
	});

	// ── Fix-Loop 1 (F002, Adversary HIGH): Band-Handle-Drag mit Pointer-Release
	// AUSSERHALB des Editor-Subtrees darf keinen stillen Datenverlust erzeugen ──
	test('F002: Band-Handle-Drag mit Release über dem Seiten-Header persistiert trotzdem, überlebt Reload', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E S6 F002-Ort ${suffix}`, 47.05, 10.95);
		const name = `E2E S6 F002-Drag ${suffix}`;
		const id = await createPresetWithLocations(page, name, [locA], {
			corridors: [{ metric: 'snow_depth_cm', range: [30, 200], notify: false, mark: true }],
			display_config: {
				ideal_ranges: { snow_depth_cm: { min: 30, max: 200 } },
				active_metrics: ['snow_depth_cm']
			}
		});

		await page.goto(`/compare/${id}?tab=idealwerte`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-idealwerte"]:visible').click();

		const editor = page.locator('[data-testid="corridor-editor-vergleich"]:visible');
		await expect(editor).toBeVisible({ timeout: 10_000 });
		const row = editor.locator('[data-testid="corridor-row-snow_depth_cm"]');
		await expect(row).toBeVisible({ timeout: 10_000 });

		const minHandle = row.locator('.ce-handle').first();
		const handleBox = await minHandle.boundingBox();
		expect(handleBox, 'Band-Handle ohne BoundingBox').not.toBeNull();

		// Release-Ziel bewusst AUSSERHALB von .hub-corridor-wrap: der Tab-Header
		// oben auf der Seite (exakt der Grenzfall aus dem Adversary-Finding).
		const header = page.locator('[data-testid="compare-detail-tab-uebersicht"]');
		const headerBox = await header.boundingBox();
		expect(headerBox, 'Tab-Header ohne BoundingBox').not.toBeNull();

		const putPromise = page.waitForResponse(
			(res) => res.url().includes(`/api/compare/presets/${id}`) && res.request().method() === 'PUT'
		);
		await page.mouse.move(handleBox!.x + handleBox!.width / 2, handleBox!.y + handleBox!.height / 2);
		await page.mouse.down();
		await page.mouse.move(handleBox!.x + 50, handleBox!.y - 20, { steps: 8 });
		await page.mouse.move(headerBox!.x + headerBox!.width / 2, headerBox!.y + headerBox!.height / 2, {
			steps: 15
		});
		// Release-Punkt liegt jetzt über dem Tab-Header, NICHT über .hub-corridor-wrap.
		await page.mouse.up();

		const putRes = await putPromise;
		expect(
			putRes.ok(),
			'PUT nach Band-Handle-Drag mit Release außerhalb des Editors fehlgeschlagen (F002-Regression): ' +
				putRes.status()
		).toBeTruthy();

		const minInput = row.locator('input[type="number"]').first();
		const draggedValue = await minInput.inputValue();

		await page.reload();
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-idealwerte"]:visible').click();
		const reloadedEditor = page.locator('[data-testid="corridor-editor-vergleich"]:visible');
		await expect(reloadedEditor).toBeVisible({ timeout: 10_000 });
		const reloadedRow = reloadedEditor.locator('[data-testid="corridor-row-snow_depth_cm"]');
		const reloadedMinInput = reloadedRow.locator('input[type="number"]').first();
		await expect(reloadedMinInput).toHaveValue(draggedValue, { timeout: 5_000 });
	});
});
