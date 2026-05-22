// TDD RED: Bug #273 — Koordinaten-Inputs im Trip-Editor mit inputmode="decimal"
//
// Spec: docs/specs/modules/bug_273_coordinate_inputmode.md
// Phase 5 (TDD RED) — Test MUSS FEHLSCHLAGEN bis Phase 6.
//
// AC-5: Given die gerenderte HTML-Ausgabe von EditStagesSection,
//        When die Koordinaten-Inputs geprüft werden,
//        Then hat jedes der drei Felder (wp-lat, wp-lon, wp-ele)
//        das Attribut inputmode="decimal" im DOM.
//
// KEINE Mocks — echter SvelteKit-Build via Playwright-Preview, echte DOM-Prüfung.

import { test, expect } from '@playwright/test';

const TRIP_ID = 'e2e-cockpit-test';
const EDIT_URL = `/trips/${TRIP_ID}/edit`;

async function ensureEtappenOpen(page: import('@playwright/test').Page) {
	// Etappen ist Default-offen; nur klicken wenn geschlossen.
	const section = page.getByTestId('edit-section-etappen');
	const header = page.getByTestId('edit-section-etappen-header');
	await expect(header).toBeVisible();
	const cls = (await section.getAttribute('class')) ?? '';
	if (!cls.includes('shadow-sm') && !cls.includes('border-primary')) {
		await header.click();
		await page.waitForTimeout(200);
	}
}

// =============================================================================
// AC-5: Alle drei Koordinaten-Inputs tragen inputmode="decimal"
// =============================================================================

test('AC-5: Lat/Lon/Höhe-Inputs haben inputmode="decimal" im DOM', async ({ page }) => {
	await page.goto(EDIT_URL);
	await ensureEtappenOpen(page);

	for (const testid of ['wp-lat', 'wp-lon', 'wp-ele']) {
		const input = page.getByTestId(testid).first();
		await expect(input).toBeVisible();
		await expect(input).toHaveAttribute('inputmode', 'decimal');
	}
});
