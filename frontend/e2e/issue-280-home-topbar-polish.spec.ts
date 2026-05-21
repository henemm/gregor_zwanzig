import { test, expect } from '@playwright/test';

/**
 * Issue #280 — Home Topbar: tracking-tight für H1
 * Spec: docs/specs/modules/issue_280_home_topbar_polish.md
 *
 * RED: Test schlägt fehl weil .home__title noch kein letter-spacing hat.
 * GRÜN: Nach Implementierung (letter-spacing: -0.025em in +page.svelte).
 */

test.describe('Issue #280 — Home H1 tracking-tight', () => {
	test.use({ storageState: 'playwright/.auth/admin.json' });

	// AC-1: H1 hat letter-spacing -0.025em
	test('AC-1: .home__title hat letter-spacing -0.025em', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt
		 * WHEN: User öffnet /
		 * THEN: Das H1 "Startseite" hat berechnetes letter-spacing von -0.025em
		 */
		await page.goto('/');
		await page.waitForLoadState('networkidle');

		const h1 = page.locator('h1.home__title');
		await expect(h1).toBeVisible();
		await expect(h1).toContainText('Startseite');

		// letter-spacing wird als px-Wert zurückgegeben (browser computed)
		// -0.025em bei 16px base = -0.4px, bei 24px (--g-text-3xl) = -0.6px
		const letterSpacing = await h1.evaluate(
			(el) => window.getComputedStyle(el).letterSpacing
		);

		// Muss ein negativer Wert sein (entweder -0.4px, -0.6px o.ä. — abhängig von font-size)
		// Aktuell: "normal" oder "0px" → Test schlägt fehl (RED)
		expect(letterSpacing).not.toBe('normal');
		expect(letterSpacing).not.toBe('0px');
		const parsed = parseFloat(letterSpacing);
		expect(parsed).toBeLessThan(0);
	});
});
