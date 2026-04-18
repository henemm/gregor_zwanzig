import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('Weather Table (M3c)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('weather page loads with location selector and button', async ({ page }) => {
		await page.goto('/weather');
		const selector = page.locator('select[name="location-select"]');
		await expect(selector).toBeVisible();
		const loadBtn = page.getByRole('button', { name: 'Laden' });
		await expect(loadBtn).toBeVisible();
	});

	test('shows error when no location selected', async ({ page }) => {
		await page.goto('/weather');
		await page.getByRole('button', { name: 'Laden' }).click();
		const error = page.locator('.text-destructive');
		await expect(error).toBeVisible();
	});

	test('loads forecast table after selecting location', async ({ page }) => {
		await page.goto('/weather');
		// Select first location
		const selector = page.locator('select[name="location-select"]');
		const options = selector.locator('option');
		const count = await options.count();
		if (count < 2) {
			test.skip();
			return;
		}
		// Pick 2nd option (1st is placeholder)
		const value = await options.nth(1).getAttribute('value');
		await selector.selectOption(value!);

		await page.getByRole('button', { name: 'Laden' }).click();

		// Table should appear
		const table = page.locator('table');
		await expect(table).toBeVisible({ timeout: 15000 });
	});

	test('forecast table has 8 columns', async ({ page }) => {
		await page.goto('/weather');
		const selector = page.locator('select[name="location-select"]');
		const options = selector.locator('option');
		if ((await options.count()) < 2) { test.skip(); return; }
		await selector.selectOption((await options.nth(1).getAttribute('value'))!);
		await page.getByRole('button', { name: 'Laden' }).click();

		const table = page.locator('table');
		await expect(table).toBeVisible({ timeout: 15000 });

		const headers = table.locator('thead th');
		await expect(headers).toHaveCount(8);
	});

	test('shows meta info after loading forecast', async ({ page }) => {
		await page.goto('/weather');
		const selector = page.locator('select[name="location-select"]');
		const options = selector.locator('option');
		if ((await options.count()) < 2) { test.skip(); return; }
		await selector.selectOption((await options.nth(1).getAttribute('value'))!);
		await page.getByRole('button', { name: 'Laden' }).click();

		// Meta info should show provider
		const meta = page.locator('[data-testid="forecast-meta"]');
		await expect(meta).toBeVisible({ timeout: 15000 });
		await expect(meta).toContainText(/OPENMETEO|openmeteo/i);
	});

	test('weather page is still accessible via direct URL', async ({ page }) => {
		// F76: Wetter removed from sidebar nav, but page still accessible
		await page.goto('/weather');
		await expect(page.getByRole('heading', { name: 'Wetter' })).toBeVisible();
	});
});
