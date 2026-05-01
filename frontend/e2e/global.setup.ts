import { test as setup, expect } from '@playwright/test';

const authFile = 'playwright/.auth/admin.json';

setup('authenticate', async ({ page }) => {
	await page.goto('/login');
	await page.fill('input[name="username"]', 'admin');
	await page.fill('input[name="password"]', 'test1234');
	await page.click('button[type="submit"]');
	await page.waitForURL('/');
	await expect(page).toHaveURL('/');
	await page.context().storageState({ path: authFile });
});
