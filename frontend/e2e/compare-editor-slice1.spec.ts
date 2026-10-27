// E2E — Issue #678 (Epic #677): Compare-Editor Slice 1 — Gerüst + Tab „Vergleich"
//
// Spec: docs/specs/modules/issue_678_compare_editor_shell.md
//
// Verhaltensnachweis der ACs als eingeloggter Nutzer gegen Staging. In der
// RED-Phase schlägt der Test fehl, weil `/compare/new` noch den alten Wizard
// (Stepper) rendert und die neuen Editor-Testids nicht existieren.
//
// Base-URL: GZ_SVELTE_BASE (Default: playwright.config.ts baseURL = Staging)
//
// Ausführen:
//   cd frontend && E2E_USER=admin E2E_PASS=test1234 \
//     npx playwright test e2e/compare-editor-slice1.spec.ts --config playwright.config.ts

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('Issue #678: Compare-Editor Slice 1 (Desktop/Create)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.setViewportSize({ width: 1280, height: 900 });
		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');
	});

	// ── AC-1: Ohne Namen ist „Orte" gesperrt — Klick wechselt nicht ──────────
	test('AC-1: gesperrter Tab "Orte" wechselt ohne Namen nicht', async ({ page }) => {
		const editor = page.locator('[data-testid="compare-editor"]');
		await expect(editor).toBeVisible({ timeout: 10_000 });

		const orteTab = page.locator('[data-testid="compare-editor-tab-orte"]');
		await expect(orteTab).toHaveAttribute('data-locked', 'true');
		await orteTab.click();
		// aktiver Tab bleibt "vergleich"
		await expect(
			page.locator('[data-testid="compare-editor-tab-vergleich"]')
		).toHaveAttribute('data-active', 'true');
	});

	// ── AC-2: Mit Namen wird „Orte" freigeschaltet, „Vergleich" trägt ✓ ──────
	test('AC-2: Name schaltet "Orte" frei + "Vergleich" done', async ({ page }) => {
		await page.locator('[data-testid="compare-editor-name"]').fill('Skitouren Hochkönig');
		const orteTab = page.locator('[data-testid="compare-editor-tab-orte"]');
		await expect(orteTab).toHaveAttribute('data-locked', 'false');
		await expect(
			page.locator('[data-testid="compare-editor-tab-vergleich"]')
		).toHaveAttribute('data-done', 'true');
	});

	// ── AC-3 (Epic #1301 F2a): Fortschrittsbalken 5 Segmente + „N / 5" ────────
	// Der CompareNewEditor hat 5 Schritte (CompareNewEditor.svelte TAB_DEFS =
	// anlegeKette('vergleich'): vergleich · orte · wetter-metriken ·
	// wertebereiche · alarme). Bis Issue #1743 (Spec AC-17/AC-19) waren es 6 —
	// der Schritt `versand` ist dort entfallen, der Versand-Inhalt steht unten im
	// Schritt „Wetter-Metriken" und zaehlt nicht als eigener Schritt. Davor (bis
	// #1360) waren es 7 mit dem Reiter `layout`. Der Fortschrittsbalken iteriert
	// TAB_DEFS, progressCount() deckelt entsprechend bei 5.
	test('AC-3: Fortschritt zeigt 5 Segmente und steigt mit Name', async ({ page }) => {
		const progress = page.locator('[data-testid="compare-editor-progress"]');
		await expect(progress).toBeVisible();
		await expect(
			page.locator('[data-testid="compare-editor-progress-segment"]')
		).toHaveCount(5);
		await page.locator('[data-testid="compare-editor-name"]').fill('Trip A');
		await expect(progress).toContainText('1 / 5');
	});

	// ── AC-4: Profil-Auswahl bleibt nach Tab-Wechsel erhalten ────────────────
	test('AC-4: Profil-Auswahl persistiert über Tab-Wechsel', async ({ page }) => {
		await page.locator('[data-testid="compare-editor-name"]').fill('Trip A');
		const firstProfile = page.locator('[data-testid^="compare-editor-profile-"]').first();
		await firstProfile.click();
		await expect(firstProfile).toHaveAttribute('data-selected', 'true');
		// zu "orte" und zurück
		await page.locator('[data-testid="compare-editor-tab-orte"]').click();
		await page.locator('[data-testid="compare-editor-tab-vergleich"]').click();
		await expect(firstProfile).toHaveAttribute('data-selected', 'true');
	});

	// ── AC-5: „Orte hinzufügen →" wechselt aktiv auf Tab „Orte" ──────────────
	test('AC-5: Weiter-Button wechselt auf Tab "Orte"', async ({ page }) => {
		await page.locator('[data-testid="compare-editor-name"]').fill('Trip A');
		await page.locator('[data-testid="compare-editor-continue-orte"]').click();
		await expect(
			page.locator('[data-testid="compare-editor-tab-orte"]')
		).toHaveAttribute('data-active', 'true');
	});
});
