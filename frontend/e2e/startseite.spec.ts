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
		const section = page.locator('section', { hasText: 'Meine Trips' });
		await expect(section).toBeVisible();
		const cards = section.locator('[data-testid^="subscription-card-"][data-kind="trip"]');
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
		// #2346 S2: Vergleichs-Kacheln stehen in der Card „Außerdem beobachtet" (div, keine section).
		const cards = page.locator('[data-testid^="subscription-card-"][data-kind="vergleich"]');
		await expect(cards.first()).toBeVisible();
		// Name ist ein echter Link auf den Vergleichs-Hub
		await expect(cards.first().locator('a[href^="/compare/"]').first()).toBeVisible();
		// Naechster Versand (Backend-Wert, z. B. "Do 07:00 (CEST)") oder "—"
		await expect(cards.first().locator('[data-field="next-send"]')).toHaveText(/^nächster ((Mo|Di|Mi|Do|Fr|Sa|So) \d{2}:\d{2} \(|—$)|pausiert|beendet|manueller Versand|abgeschaltet|kein Termin/);
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

	test('shows CTA buttons for new trip and new comparison', async ({ page }) => {
		/**
		 * GIVEN: User is logged in and has data
		 * WHEN: Startseite loads
		 * THEN: CTA buttons "Neue Trip" and "Neuer Vergleich" are visible
		 */
		await page.goto('/');
		await expect(page.locator('a', { hasText: 'Neue Trip' })).toBeVisible();
		await expect(page.locator('a', { hasText: 'Neuer Vergleich' })).toBeVisible();
	});

	test('trip card navigates to /trips on click', async ({ page }) => {
		/**
		 * GIVEN: User is logged in and has trips
		 * WHEN: User clicks a trip card
		 * THEN: Navigation to /trips occurs
		 */
		await page.goto('/');
		const card = page.locator('[data-testid^="subscription-card-"][data-kind="trip"]').first();
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
		const card = page.locator('[data-testid^="subscription-card-"][data-kind="vergleich"]').first();
		const id = (await card.getAttribute('data-testid'))!.replace('subscription-card-', '');
		// Name-Link der Kachel fuehrt auf den Hub dieses Vergleichs
		await card.locator(`a[href="/compare/${id}"]`).click();
		await page.waitForURL(new RegExp(`/compare/${id}(\\?|$)`));
		expect(page.url()).toContain(`/compare/${id}`);
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
