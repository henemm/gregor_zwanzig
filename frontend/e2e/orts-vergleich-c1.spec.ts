import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('F76 Phase C1: Orts-Vergleich Master-Detail', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('page title is "Orts-Vergleich"', async ({ page }) => {
		await page.goto('/compare');
		await expect(page.getByRole('heading', { name: 'Orts-Vergleich' })).toBeVisible();
	});

	test('has a sidebar with "Meine Orte" heading on desktop', async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 720 });
		await page.goto('/compare');
		const sidebar = page.locator('aside');
		await expect(sidebar).toBeVisible();
		await expect(sidebar.getByText('Meine Orte')).toBeVisible();
	});

	test('sidebar shows location checkboxes', async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 720 });
		await page.goto('/compare');
		const sidebar = page.locator('aside');
		// Should have at least the "Alle" checkbox
		await expect(sidebar.locator('input[type="checkbox"]').first()).toBeVisible();
	});

	test('sidebar has "Neuer Ort" button', async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 720 });
		await page.goto('/compare');
		const sidebar = page.locator('aside');
		await expect(sidebar.getByRole('button', { name: /Neuer Ort/i })).toBeVisible();
	});

	test('sidebar is hidden on mobile', async ({ page }) => {
		await page.setViewportSize({ width: 375, height: 667 });
		await page.goto('/compare');
		const sidebar = page.locator('aside');
		await expect(sidebar).not.toBeVisible();
	});

	test('settings card does NOT contain location checkboxes on desktop', async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 720 });
		await page.goto('/compare');
		// The settings card should not have the "Locations" label anymore on desktop
		const content = page.locator('main .flex-1, main > div > div:last-child');
		const settingsCard = content.locator('[class*="card"]').first();
		await expect(settingsCard.getByText('Locations')).not.toBeVisible();
	});

	test('compare button still works', async ({ page }) => {
		await page.goto('/compare');
		const compareBtn = page.getByRole('button', { name: /Vergleichen/i });
		await expect(compareBtn).toBeVisible();
	});
});
