import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

/**
 * Epic #133 Step 7 — Marken-CTAs (Issue #219)
 *
 * #3207 (tote Tests mitentfernen): AC-1 (Startseiten-CTA `cta-new-trip`, seit #294
 * ohne Treffer in frontend/src) und AC-3 (Compare-Button „Vergleichen", seit dem
 * Umbau von /compare zur Listen-Übersicht #439/#2278 ohne Pendant) sind entfernt.
 * Es bleibt die geltende Zusicherung AC-2 (Hauptaktion = Ink, #2881).
 */

test.describe('Epic #133 Step 7 — Marken-CTAs', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// #2881 (R4, ADR-0111 Punkt 6 / ADR-0110 „Hauptaktion = Ink"): die Anlege-Aktion ist seither
	// auf Listen und Startseite `primary` (Ink), nicht mehr accent — Zusicherung umgedreht.
	test('AC-2: Trips-Liste "Neuer Trip"-Button hat variant="primary" (seit #2881)', async ({ page }) => {
		/**
		 * GIVEN: User ist auf /trips
		 * WHEN:  getByRole('button', { name: 'Neuer Trip' })
		 * THEN:  data-variant="primary"
		 */
		await page.goto('/trips');
		const cta = page.getByRole('button', { name: 'Neuer Trip' });
		await expect(cta).toBeVisible();
		await expect(cta).toHaveAttribute('data-variant', 'primary');
	});
});
