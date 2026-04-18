import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('F76 Phase B: Startseite Kachel-Übersicht', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('shows trip cards with name and stage count', async ({ page }) => {
		/**
		 * GIVEN: User is logged in and has trips
		 * WHEN: Startseite loads
		 * THEN: Trip cards are shown with name and "N Etappen"
		 */
		await page.goto('/');
		const section = page.locator('section', { hasText: 'Meine Touren' });
		await expect(section).toBeVisible();
		const cards = section.locator('[data-testid="trip-card"]');
		await expect(cards.first()).toBeVisible();
		await expect(cards.first()).toContainText(/Etappen?/);
	});

	test('shows subscription cards with name and schedule', async ({ page }) => {
		/**
		 * GIVEN: User is logged in and has subscriptions
		 * WHEN: Startseite loads
		 * THEN: Subscription cards are shown with name and schedule label
		 */
		await page.goto('/');
		const section = page.locator('section', { hasText: 'Orts-Vergleiche' });
		await expect(section).toBeVisible();
		const cards = section.locator('[data-testid="subscription-card"]');
		await expect(cards.first()).toBeVisible();
		// Schedule label like "tägl. 07:00" or "Do 18:00"
		await expect(cards.first()).toContainText(/tägl\.|Mo|Di|Mi|Do|Fr|Sa|So/);
	});

	test('old stat-cards are gone', async ({ page }) => {
		/**
		 * GIVEN: User is logged in
		 * WHEN: Startseite loads
		 * THEN: Old stat-cards (stat-trips, stat-locations, stat-health) are NOT present
		 */
		await page.goto('/');
		await expect(page.locator('[data-testid="stat-trips"]')).toHaveCount(0);
		await expect(page.locator('[data-testid="stat-locations"]')).toHaveCount(0);
		await expect(page.locator('[data-testid="stat-health"]')).toHaveCount(0);
	});

	test('shows CTA buttons for new tour and new comparison', async ({ page }) => {
		/**
		 * GIVEN: User is logged in and has data
		 * WHEN: Startseite loads
		 * THEN: CTA buttons "Neue Tour" and "Neuer Vergleich" are visible
		 */
		await page.goto('/');
		await expect(page.locator('a', { hasText: 'Neue Tour' })).toBeVisible();
		await expect(page.locator('a', { hasText: 'Neuer Vergleich' })).toBeVisible();
	});

	test('trip card navigates to /trips on click', async ({ page }) => {
		/**
		 * GIVEN: User is logged in and has trips
		 * WHEN: User clicks a trip card
		 * THEN: Navigation to /trips occurs
		 */
		await page.goto('/');
		const card = page.locator('[data-testid="trip-card"]').first();
		await card.click();
		await page.waitForURL('/trips');
		expect(page.url()).toContain('/trips');
	});

	test('subscription card navigates to /compare on click', async ({ page }) => {
		/**
		 * GIVEN: User is logged in and has subscriptions
		 * WHEN: User clicks a subscription card
		 * THEN: Navigation to /compare occurs
		 */
		await page.goto('/');
		const card = page.locator('[data-testid="subscription-card"]').first();
		await card.click();
		await page.waitForURL('/compare');
		expect(page.url()).toContain('/compare');
	});

	test('heading says "Startseite" not "Übersicht"', async ({ page }) => {
		/**
		 * GIVEN: User is logged in
		 * WHEN: Startseite loads
		 * THEN: Page heading is "Startseite", not the old "Übersicht"
		 */
		await page.goto('/');
		const mainHeading = page.locator('main h1');
		await expect(mainHeading).toContainText('Startseite');
		await expect(mainHeading).not.toContainText('Übersicht');
	});
});
