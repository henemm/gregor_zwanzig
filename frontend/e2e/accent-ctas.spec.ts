import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

/**
 * TDD RED Tests — Epic #133 Step 7 — Marken-CTAs auf accent (Issue #219)
 *
 * Diese Tests MÜSSEN vor der Implementierung ROT sein:
 * - Cockpit / Trips-Liste / Compare haben aktuell variant="primary"
 * - Erwartet wird variant="accent" → data-variant="accent" am DOM
 */

test.describe('Epic #133 Step 7 — Marken-CTAs auf accent', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('AC-1: Cockpit "Neuer Trip"-CTA hat variant="accent"', async ({ page }) => {
		/**
		 * GIVEN: User ist auf der Startseite /
		 * WHEN:  getByTestId('cta-new-trip')
		 * THEN:  data-variant="accent"
		 */
		await page.goto('/');
		const cta = page.getByTestId('cta-new-trip');
		await expect(cta).toBeVisible();
		await expect(cta).toHaveAttribute('data-variant', 'accent');
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

	test('AC-3: Compare "Vergleichen"-Button hat variant="accent"', async ({ page }) => {
		/**
		 * GIVEN: User ist auf /compare
		 * WHEN:  getByRole('button', { name: /Vergleichen/i })
		 * THEN:  data-variant="accent"
		 */
		await page.goto('/compare');
		const cta = page.getByRole('button', { name: /Vergleichen/i });
		await expect(cta).toBeVisible();
		await expect(cta).toHaveAttribute('data-variant', 'accent');
	});
});
