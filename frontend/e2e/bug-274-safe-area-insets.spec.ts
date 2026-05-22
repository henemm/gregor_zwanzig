// TDD RED: Bug #274 — Safe-Area-Insets für Sticky-Bottom-Bar im Trip-Edit
//
// Spec: docs/specs/modules/bug_274_safe_area_insets.md
// Phase 5 (TDD RED) — Test MUSS FEHLSCHLAGEN bis Phase 6.
//
// AC-1: app.html-Viewport-Meta enthält viewport-fit=cover (sonst ignoriert
//        iOS Safari alle env(safe-area-inset-*)-Aufrufe).
// AC-2: Die fixed Bottom-Action-Bar im Trip-Edit (Container von
//        [data-testid="edit-save-btn"]) hat ein style-Attribut mit
//        padding-bottom und env(safe-area-inset-bottom.
//
// KEINE Mocks — echter SvelteKit-Build via Playwright-Preview, echte DOM-Prüfung.
// env(safe-area-inset-bottom) ergibt im Test-Viewport immer 0px (kein iOS-Gerät);
// Akzeptanz-Nachweis daher über DOM-Attribut-Prüfung statt Pixel-Messung.

import { test, expect } from '@playwright/test';

const TRIP_ID = 'e2e-cockpit-test';
const EDIT_URL = `/trips/${TRIP_ID}/edit`;

// =============================================================================
// AC-1: Viewport-Meta-Tag enthält viewport-fit=cover
// =============================================================================

test('AC-1: viewport-meta enthält viewport-fit=cover', async ({ page }) => {
	await page.goto(EDIT_URL);
	const viewport = page.locator('meta[name="viewport"]');
	await expect(viewport).toHaveAttribute('content', /viewport-fit=cover/);
});

// =============================================================================
// AC-2: Action-Bar-Container hat safe-area padding-bottom im style-Attribut
// =============================================================================

test('AC-2: Action-Bar-Container hat env(safe-area-inset-bottom) im style', async ({ page }) => {
	await page.goto(EDIT_URL);

	const saveBtn = page.getByTestId('edit-save-btn');
	await expect(saveBtn).toBeVisible();

	// Container = die fixed Bottom-Bar (Vorfahre des Save-Buttons mit der
	// fixed-bottom-0-Klasse). Wir greifen den nächsten fixed-Vorfahren.
	const bar = page.locator('div.fixed.bottom-0').filter({ has: saveBtn });
	await expect(bar).toBeVisible();

	const style = (await bar.getAttribute('style')) ?? '';
	expect(style).toMatch(/padding-bottom/);
	expect(style).toMatch(/env\(safe-area-inset-bottom/);
});
