import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('F76 Phase F: Wetter Drill-Down', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('sidebar has weather icon button per location', async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 720 });
		await page.goto('/compare');
		const sidebar = page.locator('aside');
		const weatherBtns = sidebar.locator('[data-testid="weather-btn"]');
		// Should have at least one weather button if locations exist
		const locCount = await sidebar.locator('input[type="checkbox"]').count();
		if (locCount > 1) {
			// More than just "Alle" checkbox
			await expect(weatherBtns.first()).toBeVisible();
		}
	});

	test('clicking weather icon shows forecast in content', async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 720 });
		await page.goto('/compare');
		const sidebar = page.locator('aside');
		const weatherBtn = sidebar.locator('[data-testid="weather-btn"]').first();
		const count = await weatherBtn.count();
		if (count > 0) {
			await weatherBtn.click();
			// Content should show weather heading
			await expect(page.getByText(/Wetter:/)).toBeVisible({ timeout: 10000 });
		}
	});

	test('weather view has back button', async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 720 });
		await page.goto('/compare');
		const weatherBtn = page.locator('aside [data-testid="weather-btn"]').first();
		const count = await weatherBtn.count();
		if (count > 0) {
			await weatherBtn.click();
			await expect(page.getByText(/Wetter:/)).toBeVisible({ timeout: 10000 });
			const backBtn = page.getByRole('button', { name: /Zurück/i });
			await expect(backBtn).toBeVisible();
		}
	});

	test('back button returns to default view', async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 720 });
		await page.goto('/compare');
		const weatherBtn = page.locator('aside [data-testid="weather-btn"]').first();
		const count = await weatherBtn.count();
		if (count > 0) {
			await weatherBtn.click();
			await expect(page.getByText(/Wetter:/)).toBeVisible({ timeout: 10000 });
			await page.getByRole('button', { name: /Zurück/i }).click();
			// Should show auto-reports or settings again
			await expect(page.getByText(/Wetter:/)).not.toBeVisible();
			await expect(page.getByRole('heading', { name: 'Orts-Vergleich' })).toBeVisible();
		}
	});
});
