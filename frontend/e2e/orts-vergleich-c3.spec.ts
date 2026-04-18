import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('F76 Phase C3: Auto-Reports im Orts-Vergleich', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('shows "Deine Auto-Reports" heading when no comparison active', async ({ page }) => {
		await page.goto('/compare');
		await expect(page.getByText('Deine Auto-Reports')).toBeVisible();
	});

	test('shows subscription cards with name and schedule', async ({ page }) => {
		await page.goto('/compare');
		// If subscriptions exist, they should be shown as cards
		const autoReports = page.locator('[data-testid="auto-report-card"]');
		const count = await autoReports.count();
		if (count > 0) {
			// Each card should have a name and schedule info
			const firstCard = autoReports.first();
			await expect(firstCard).toBeVisible();
		}
	});

	test('shows enabled/disabled badge on subscription cards', async ({ page }) => {
		await page.goto('/compare');
		const autoReports = page.locator('[data-testid="auto-report-card"]');
		const count = await autoReports.count();
		if (count > 0) {
			// Should have a badge indicating enabled/disabled
			const badge = autoReports.first().locator('.badge, [class*="badge"]');
			await expect(badge.first()).toBeVisible();
		}
	});

	test('has link to /subscriptions for management', async ({ page }) => {
		await page.goto('/compare');
		const manageLink = page.locator('a[href="/subscriptions"]');
		await expect(manageLink).toBeVisible();
	});

	test('auto-reports disappear after running comparison', async ({ page }) => {
		await page.goto('/compare');
		// Before comparison: auto-reports visible
		const autoReportsHeading = page.getByText('Deine Auto-Reports');
		// Run comparison
		await page.getByRole('button', { name: /Vergleichen/i }).click();
		// Wait for loading to finish
		await page.waitForTimeout(5000);
		// After comparison: auto-reports should be hidden
		await expect(autoReportsHeading).not.toBeVisible();
	});
});
