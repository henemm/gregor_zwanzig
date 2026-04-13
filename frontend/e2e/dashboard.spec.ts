import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('Dashboard (M3a)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('shows trip count stat card', async ({ page }) => {
		await page.goto('/');
		const tripCard = page.locator('[data-testid="stat-trips"]');
		await expect(tripCard).toBeVisible();
		await expect(tripCard.locator('.text-3xl, [data-testid="stat-value"]')).toHaveText(/\d+/);
	});

	test('shows location count stat card', async ({ page }) => {
		await page.goto('/');
		const locCard = page.locator('[data-testid="stat-locations"]');
		await expect(locCard).toBeVisible();
		await expect(locCard.locator('.text-3xl, [data-testid="stat-value"]')).toHaveText(/\d+/);
	});

	test('shows health status card', async ({ page }) => {
		await page.goto('/');
		const healthCard = page.locator('[data-testid="stat-health"]');
		await expect(healthCard).toBeVisible();
	});

	test('has link to trips page', async ({ page }) => {
		await page.goto('/');
		const tripsLink = page.locator('[data-testid="stat-trips"] a[href="/trips"]');
		await expect(tripsLink).toBeVisible();
	});
});
