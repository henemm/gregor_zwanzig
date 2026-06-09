// E2E — Issue #680 (Epic #677): Compare-Editor Slice 3 — Orte + Idealwerte Fidelity
//
// Spec: docs/specs/modules/issue_680_compare_editor_slice3.md
//
// Verhaltensnachweis der ACs als eingeloggter Nutzer gegen den lokalen Preview-Server
// (oder Staging, wenn GZ_SVELTE_BASE gesetzt). In der RED-Phase schlagen alle Tests
// fehl, weil:
//   - compare-step2-picked-item-* und compare-step2-picked-remove-* nicht existieren
//   - compare-step3-slider-min-* und compare-step3-slider-max-* nicht existieren
//   - compare-step3-add-metric-btn nicht existiert
//   - Bibliotheks-Einträge nicht nach Region gruppiert sind (keine Spalten-Überschriften)
//
// Ausführen (lokal):
//   cd frontend && npx playwright test e2e/compare-editor-slice3.spec.ts
//
// Ausführen (Staging):
//   cd frontend && BASE_URL=https://staging.gregor20.henemm.com \
//     npx playwright test e2e/compare-editor-slice3.spec.ts

import { test, expect, type Page } from '@playwright/test';

// ─────────────────────────────────────────────────────────────────────────────
// Setup-Helper: Preset + 2 Locations anlegen
// ─────────────────────────────────────────────────────────────────────────────
async function createPresetWithLocations(
	page: Page
): Promise<{ presetId: string; locIdA: string; locIdB: string }> {
	// Location A (mit region)
	const resA = await page.request.post('/api/locations', {
		data: { name: 'Ort-Region-A', lat: 47.4, lon: 13.0, region: 'Hochkönig' }
	});
	expect(resA.ok(), 'Location A fehlgeschlagen').toBeTruthy();
	const locA = await resA.json();

	// Location B (ohne region → Fallback-Bucket)
	const resB = await page.request.post('/api/locations', {
		data: { name: 'Ort-kein-Region', lat: 47.1, lon: 12.8 }
	});
	expect(resB.ok(), 'Location B fehlgeschlagen').toBeTruthy();
	const locB = await resB.json();

	// Preset mit beiden Orten und WINTERSPORT-Profil
	const resP = await page.request.post('/api/compare/presets', {
		data: {
			name: 'Slice3 E2E ' + Date.now(),
			location_ids: [locA.id, locB.id],
			schedule: 'daily',
			profil: 'wintersport',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['slice3-e2e@example.com'],
			display_config: {}
		}
	});
	expect(resP.ok(), 'Preset-Anlage fehlgeschlagen').toBeTruthy();
	const preset = await resP.json();
	return { presetId: preset.id, locIdA: locA.id, locIdB: locB.id };
}

// ─────────────────────────────────────────────────────────────────────────────
// Test-Suite
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Issue #680: Compare-Editor Slice 3 — Orte + Idealwerte', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-1: Nummerierte Picked-Liste mit ✕ ─────────────────────────────────
	test('AC-1: Picked-Liste zeigt Nummern und ✕-Entfernen-Buttons', async ({ page }) => {
		const { presetId, locIdA, locIdB } = await createPresetWithLocations(page);
		await page.goto(`/compare/${presetId}/edit`);
		await page.waitForLoadState('networkidle');

		// Orte-Tab navigieren
		await page.locator('[data-testid="compare-editor-tab-orte"]').click();
		await page.waitForTimeout(300);

		// Picked-Liste sichtbar
		const pickedList = page.locator('[data-testid="compare-step2-picked-list"]');
		await expect(pickedList).toBeVisible({ timeout: 8_000 });

		// Beide Orte als Items vorhanden
		const itemA = page.locator(`[data-testid="compare-step2-picked-item-${locIdA}"]`);
		const itemB = page.locator(`[data-testid="compare-step2-picked-item-${locIdB}"]`);
		await expect(itemA).toBeVisible();
		await expect(itemB).toBeVisible();

		// Nummern 1 und 2 vorhanden
		await expect(itemA.locator('text=1')).toBeVisible();
		await expect(itemB.locator('text=2')).toBeVisible();

		// ✕-Button entfernt Ort: locIdA entfernen
		const removeA = page.locator(`[data-testid="compare-step2-picked-remove-${locIdA}"]`);
		await expect(removeA).toBeVisible();
		await removeA.click();

		// Nach Entfernen: Item A weg, Item B noch da (jetzt Nr. 1)
		await expect(itemA).toHaveCount(0);
		await expect(itemB).toBeVisible();
	});

	// ── AC-2: Counter Warn/OK ────────────────────────────────────────────────
	test('AC-2: Counter zeigt "min. 2 erforderlich" unter 2 Orten', async ({ page }) => {
		const { presetId, locIdA } = await createPresetWithLocations(page);

		// Preset mit nur 1 Ort anlegen
		await page.request.patch(`/api/compare/presets/${presetId}`, {
			data: { location_ids: [locIdA] }
		});

		await page.goto(`/compare/${presetId}/edit`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-editor-tab-orte"]').click();
		await page.waitForTimeout(300);

		const counter = page.locator('[data-testid="compare-step2-counter"]');
		await expect(counter).toBeVisible();
		await expect(counter).toContainText('min. 2 erforderlich');
	});

	// ── AC-3: Bibliotheks-Grid nach Region ───────────────────────────────────
	test('AC-3: Bibliothek zeigt Regionsgruppen als Spalten-Überschriften', async ({ page }) => {
		const { presetId } = await createPresetWithLocations(page);
		await page.goto(`/compare/${presetId}/edit`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-editor-tab-orte"]').click();
		await page.waitForTimeout(300);

		// Bibliotheks-Grid vorhanden
		const library = page.locator('[data-testid="compare-step2-library"]');
		await expect(library).toBeVisible({ timeout: 8_000 });

		// Mind. eine Regionsgruppen-Überschrift mit "HOCHKÖNIG" (case-insensitive)
		const regionHeader = library.locator('text=/hochkönig/i');
		await expect(regionHeader).toBeVisible();

		// Fallback-Bucket für Orte ohne Region
		const weitereHeader = library.locator('text=/weitere/i');
		await expect(weitereHeader).toBeVisible();
	});

	// ── AC-4: Profil-Defaults beim ersten Öffnen des Idealwerte-Tabs ─────────
	test('AC-4: Idealwerte-Tab zeigt WINTERSPORT-Metriken beim ersten Öffnen', async ({ page }) => {
		const { presetId } = await createPresetWithLocations(page);
		await page.goto(`/compare/${presetId}/edit`);
		await page.waitForLoadState('networkidle');

		// Tab "Idealwerte" öffnen
		await page.locator('[data-testid="compare-editor-tab-idealwerte"]').click();
		await page.waitForTimeout(300);

		const step3 = page.locator('[data-testid="compare-wizard-step-3"]');
		await expect(step3).toBeVisible({ timeout: 8_000 });

		// WINTERSPORT hat snow_depth_cm → Slider oder Eingabe sichtbar
		const snowSlider = page.locator('[data-testid="compare-step3-slider-min-snow_depth_cm"]');
		await expect(snowSlider).toBeVisible({ timeout: 5_000 });
	});

	// ── AC-6: Dual-Handle-Slider aktualisiert Ideal-Text ─────────────────────
	test('AC-6: Slider-Drag aktualisiert idealRanges und abgeleiteten Ideal-Text', async ({
		page
	}) => {
		const { presetId } = await createPresetWithLocations(page);
		await page.goto(`/compare/${presetId}/edit`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-editor-tab-idealwerte"]').click();
		await page.waitForTimeout(300);

		// Slider-Handle für snow_depth_cm
		const sliderMin = page.locator(
			'[data-testid="compare-step3-slider-min-snow_depth_cm"]'
		);
		await expect(sliderMin).toBeVisible({ timeout: 5_000 });

		// Pfeiltaste → Wert ändert sich
		await sliderMin.focus();
		await sliderMin.press('ArrowRight');
		await sliderMin.press('ArrowRight');

		// Ideal-Text aktualisiert
		const idealText = page.locator(
			'[data-testid="compare-step3-ideal-text-snow_depth_cm"]'
		);
		await expect(idealText).toBeVisible();
		// Text enthält ein "–" (min–max) und "cm"
		await expect(idealText).toContainText('cm');
	});

	// ── AC-7: Enum-Metrik als Segmented-Control ───────────────────────────────
	test('AC-7: thunder_level_max zeigt Segmented-Control statt Slider', async ({ page }) => {
		// Preset mit SUMMER_TREKKING (hat thunder_level_max als enum)
		const resP = await page.request.post('/api/compare/presets', {
			data: {
				name: 'Slice3 Enum E2E ' + Date.now(),
				location_ids: [],
				schedule: 'daily',
				profil: 'summer_trekking',
				hour_from: 7,
				hour_to: 16,
				empfaenger: ['slice3-enum@example.com'],
				display_config: {}
			}
		});
		expect(resP.ok()).toBeTruthy();
		const preset = await resP.json();

		// Location anlegen damit Idealwerte-Tab freischaltbar ist
		const [rA, rB] = await Promise.all([
			page.request.post('/api/locations', {
				data: { name: 'EnumTestA', lat: 47.0, lon: 13.0 }
			}),
			page.request.post('/api/locations', {
				data: { name: 'EnumTestB', lat: 47.1, lon: 13.1 }
			})
		]);
		const [lA, lB] = await Promise.all([rA.json(), rB.json()]);
		await page.request.patch(`/api/compare/presets/${preset.id}`, {
			data: { location_ids: [lA.id, lB.id] }
		});

		await page.goto(`/compare/${preset.id}/edit`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-editor-tab-idealwerte"]').click();
		await page.waitForTimeout(300);

		// Kein Slider für thunder_level_max
		await expect(
			page.locator('[data-testid="compare-step3-slider-min-thunder_level_max"]')
		).toHaveCount(0);

		// Segmented-Control vorhanden — mindestens ein Segment mit "NONE"
		const noneSegment = page.locator(
			'[data-testid="compare-step3-max-thunder_level_max"] >> text=NONE'
		);
		await expect(noneSegment).toBeVisible({ timeout: 5_000 });
	});

	// ── AC-8: Metrik hinzufügen ───────────────────────────────────────────────
	test('AC-8: "＋ Metrik hinzufügen" fügt eine neue Metrik zur Liste hinzu', async ({
		page
	}) => {
		const { presetId } = await createPresetWithLocations(page);
		await page.goto(`/compare/${presetId}/edit`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-editor-tab-idealwerte"]').click();
		await page.waitForTimeout(300);

		// Vor Hinzufügen: Zähle Metrik-Zeilen
		const step3 = page.locator('[data-testid="compare-wizard-step-3"]');
		await expect(step3).toBeVisible({ timeout: 8_000 });
		const countBefore = await page.locator('[data-testid^="compare-step3-metric-"]').count();

		// Klick auf "＋ Metrik hinzufügen"
		const addBtn = page.locator('[data-testid="compare-step3-add-metric-btn"]');
		await expect(addBtn).toBeVisible();
		await addBtn.click();

		// Eine Option wählen (erste verfügbare)
		const firstOption = page.locator('[data-testid^="compare-step3-add-metric-option-"]').first();
		await expect(firstOption).toBeVisible({ timeout: 3_000 });
		await firstOption.click();

		// Metrik-Zeilen um 1 mehr
		const countAfter = await page.locator('[data-testid^="compare-step3-metric-"]').count();
		assert.ok(countAfter === countBefore + 1, `Erwartet +1 Metrik, war vorher ${countBefore}, nachher ${countAfter}`);
	});

	// ── AC-9: Metrik entfernen ────────────────────────────────────────────────
	test('AC-9: ✕ an Metrik-Zeile entfernt die Metrik sofort', async ({ page }) => {
		const { presetId } = await createPresetWithLocations(page);
		await page.goto(`/compare/${presetId}/edit`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-editor-tab-idealwerte"]').click();
		await page.waitForTimeout(300);

		// Erste Metrik-Zeile und ihr ✕-Button
		const firstMetricRow = page.locator('[data-testid^="compare-step3-metric-"]').first();
		await expect(firstMetricRow).toBeVisible({ timeout: 8_000 });

		// Metrik-Key aus dem testid lesen
		const testid = await firstMetricRow.getAttribute('data-testid');
		const key = testid?.replace('compare-step3-metric-', '') ?? '';
		assert.ok(key.length > 0, 'Konnte Metrik-Key nicht ermitteln');

		// ✕-Button klicken
		const removeBtn = page.locator(`[data-testid="compare-step3-remove-metric-${key}"]`);
		await expect(removeBtn).toBeVisible();
		await removeBtn.click();

		// Metrik-Zeile weg
		await expect(
			page.locator(`[data-testid="compare-step3-metric-${key}"]`)
		).toHaveCount(0);
	});

	// ── AC-10: Persistenz — active_metrics wird gespeichert und geladen ───────
	test('AC-10: active_metrics wird im Edit-Modus gespeichert und beim Reload wiederhergestellt', async ({
		page
	}) => {
		const { presetId } = await createPresetWithLocations(page);
		await page.goto(`/compare/${presetId}/edit`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-editor-tab-idealwerte"]').click();
		await page.waitForTimeout(300);

		await page.locator('[data-testid="compare-wizard-step-3"]').waitFor({ timeout: 8_000 });

		// Erste Metrik entfernen (damit active_metrics < Profil-Defaults)
		const firstRow = page.locator('[data-testid^="compare-step3-metric-"]').first();
		await expect(firstRow).toBeVisible();
		const testid = await firstRow.getAttribute('data-testid');
		const key = testid?.replace('compare-step3-metric-', '') ?? '';
		await page.locator(`[data-testid="compare-step3-remove-metric-${key}"]`).click();
		await expect(page.locator(`[data-testid="compare-step3-metric-${key}"]`)).toHaveCount(0);

		// Speichern
		const saveBtn = page.locator('[data-testid="compare-editor-save"]');
		await expect(saveBtn).toBeVisible();
		await saveBtn.click();
		await page.waitForTimeout(600);

		// Reload
		await page.reload();
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-editor-tab-idealwerte"]').click();
		await page.waitForTimeout(300);

		// Entfernte Metrik ist nach Reload immer noch weg
		await expect(
			page.locator(`[data-testid="compare-step3-metric-${key}"]`)
		).toHaveCount(0);
	});
});

// Hilfsfunktion für den AC-8-Test (node:assert im Playwright-Kontext)
function assert(condition: boolean, msg: string): void {
	if (!condition) throw new Error(msg);
}
// Damit assert.ok als assert() funktioniert
(assert as unknown as Record<string, (cond: boolean, msg?: string) => void>).ok = assert;
