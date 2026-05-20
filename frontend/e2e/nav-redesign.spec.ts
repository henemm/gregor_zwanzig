import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

const DESKTOP_VIEWPORT = { width: 1440, height: 900 };

test.describe('F76 Phase A: Navigation Redesign', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await login(page);
	});

	test('sidebar shows exactly 4 nav items (inkl. Locations)', async ({ page }) => {
		/**
		 * GIVEN: User is logged in, Desktop-Viewport
		 * WHEN: Sidebar is visible
		 * THEN: Genau 4 sichtbare Workspace-Links (Startseite, Meine Touren, Orts-Vergleich, Standorte)
		 *       — Issue #267 ergänzt Locations als 4. NavItem.
		 *       Footer-Konto-Links sind im Dropdown versteckt (display:none).
		 */
		await page.goto('/');
		const sidebar = page.getByTestId('desktop-sidebar');
		const workspaceHrefs = ['/', '/trips', '/compare', '/locations'];
		for (const href of workspaceHrefs) {
			await expect(sidebar.locator(`a[href="${href}"]`).first()).toBeVisible();
		}
	});

	test('sidebar shows "Startseite" link to /', async ({ page }) => {
		await page.goto('/');
		const sidebar = page.getByTestId('desktop-sidebar');
		const link = sidebar.locator('a[href="/"]');
		await expect(link).toBeVisible();
		await expect(link).toContainText('Startseite');
	});

	test('sidebar shows "Meine Touren" link to /trips', async ({ page }) => {
		await page.goto('/');
		const sidebar = page.getByTestId('desktop-sidebar');
		const link = sidebar.locator('a[href="/trips"]');
		await expect(link).toBeVisible();
		await expect(link).toContainText('Meine Touren');
	});

	test('sidebar shows "Orts-Vergleich" link to /compare', async ({ page }) => {
		await page.goto('/');
		const sidebar = page.getByTestId('desktop-sidebar');
		const link = sidebar.locator('a[href="/compare"]');
		await expect(link).toBeVisible();
		await expect(link).toContainText('Orts-Vergleich');
	});

	test('sidebar does NOT show old nav items (Abos, Wetter)', async ({ page }) => {
		/**
		 * GIVEN: User is logged in, Desktop-Viewport
		 * WHEN: Sidebar is visible
		 * THEN: No links to /subscriptions, /weather in the sidebar nav
		 *       — /locations ist seit Issue #267 wieder Teil der Workspace-Nav
		 */
		await page.goto('/');
		await expect(page.locator('nav a[href="/subscriptions"]')).toHaveCount(0);
		await expect(page.locator('nav a[href="/weather"]')).toHaveCount(0);
	});

	test('sidebar has no group headers (Daten)', async ({ page }) => {
		/**
		 * GIVEN: User is logged in
		 * WHEN: Sidebar is visible
		 * THEN: No group header label "Daten" exists
		 *       (Hinweis: "System-Status" steht im Footer-Dropdown — kein Header)
		 */
		await page.goto('/');
		const sidebar = page.getByTestId('desktop-sidebar');
		await expect(sidebar.locator('text=Daten')).toHaveCount(0);
	});

	test('active page is highlighted in nav', async ({ page }) => {
		/**
		 * GIVEN: User navigates to /trips
		 * WHEN: Sidebar renders
		 * THEN: "Meine Touren" link in der Sidebar hat die aktive Klasse
		 */
		await page.goto('/trips');
		const sidebar = page.getByTestId('desktop-sidebar');
		const link = sidebar.locator('a[href="/trips"]');
		await expect(link).toHaveClass(/bg-sidebar-accent/);
		await expect(link).toContainText('Meine Touren');
	});
});
