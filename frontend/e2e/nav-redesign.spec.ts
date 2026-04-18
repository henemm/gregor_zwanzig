import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('F76 Phase A: Navigation Redesign', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('sidebar shows exactly 3 nav items', async ({ page }) => {
		/**
		 * GIVEN: User is logged in
		 * WHEN: Sidebar is visible
		 * THEN: Exactly 3 navigation links are shown (Startseite, Meine Touren, Orts-Vergleich)
		 */
		await page.goto('/');
		const navLinks = page.locator('nav a[href]');
		await expect(navLinks).toHaveCount(3);
	});

	test('sidebar shows "Startseite" link to /', async ({ page }) => {
		/**
		 * GIVEN: User is logged in
		 * WHEN: Sidebar is visible
		 * THEN: A link labeled "Startseite" pointing to "/" exists
		 */
		await page.goto('/');
		const link = page.locator('nav a[href="/"]');
		await expect(link).toBeVisible();
		await expect(link).toContainText('Startseite');
	});

	test('sidebar shows "Meine Touren" link to /trips', async ({ page }) => {
		/**
		 * GIVEN: User is logged in
		 * WHEN: Sidebar is visible
		 * THEN: A link labeled "Meine Touren" pointing to "/trips" exists
		 */
		await page.goto('/');
		const link = page.locator('nav a[href="/trips"]');
		await expect(link).toBeVisible();
		await expect(link).toContainText('Meine Touren');
	});

	test('sidebar shows "Orts-Vergleich" link to /compare', async ({ page }) => {
		/**
		 * GIVEN: User is logged in
		 * WHEN: Sidebar is visible
		 * THEN: A link labeled "Orts-Vergleich" pointing to "/compare" exists
		 */
		await page.goto('/');
		const link = page.locator('nav a[href="/compare"]');
		await expect(link).toBeVisible();
		await expect(link).toContainText('Orts-Vergleich');
	});

	test('sidebar does NOT show old nav items (Locations, Abos, Wetter)', async ({ page }) => {
		/**
		 * GIVEN: User is logged in
		 * WHEN: Sidebar is visible
		 * THEN: No links to /locations, /subscriptions, /weather in the sidebar nav
		 */
		await page.goto('/');
		await expect(page.locator('nav a[href="/locations"]')).toHaveCount(0);
		await expect(page.locator('nav a[href="/subscriptions"]')).toHaveCount(0);
		await expect(page.locator('nav a[href="/weather"]')).toHaveCount(0);
	});

	test('sidebar has no group headers (Daten, System)', async ({ page }) => {
		/**
		 * GIVEN: User is logged in
		 * WHEN: Sidebar is visible
		 * THEN: No group header labels "Daten" or "System" exist
		 */
		await page.goto('/');
		const nav = page.locator('nav');
		await expect(nav.locator('text=Daten')).toHaveCount(0);
		await expect(nav.locator('text=System')).toHaveCount(0);
	});

	test('active page is highlighted in nav', async ({ page }) => {
		/**
		 * GIVEN: User navigates to /trips
		 * WHEN: Sidebar renders
		 * THEN: "Meine Touren" link has the active class
		 */
		await page.goto('/trips');
		const link = page.locator('nav a[href="/trips"]');
		await expect(link).toHaveClass(/bg-sidebar-accent/);
		await expect(link).toContainText('Meine Touren');
	});
});
