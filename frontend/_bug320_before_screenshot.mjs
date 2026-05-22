import { chromium } from '@playwright/test';
import path from 'node:path';

const SCREENSHOT_DIR = '/home/hem/gregor_zwanzig/docs/artifacts/bug-320-sidebar-archiv/screenshots';

(async () => {
	const browser = await chromium.launch();
	const ctx = await browser.newContext({ baseURL: 'http://localhost:4173' });
	const page = await ctx.newPage();

	// Login
	await page.goto('/');
	if (page.url().includes('/login')) {
		await page.fill('input[name="username"]', 'admin');
		await page.fill('input[name="password"]', 'test1234');
		await page.click('button[type="submit"]');
		await page.waitForURL('/');
	}

	// Desktop sidebar screenshot
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/');
	await page.waitForTimeout(500);
	await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'before-desktop-sidebar.png'), fullPage: false });

	// Mobile bottom nav screenshot
	await page.setViewportSize({ width: 375, height: 667 });
	await page.goto('/');
	await page.waitForTimeout(500);
	await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'before-mobile-bottomnav.png'), fullPage: false });

	await browser.close();
	console.log('Before screenshots saved.');
})().catch((err) => {
	console.error(err);
	process.exit(1);
});
