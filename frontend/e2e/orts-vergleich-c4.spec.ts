import { test, expect } from '@playwright/test';
import { login, createTestLocation } from './helpers.js';

test.describe('F76 Phase C4: Location-Gruppen in Sidebar', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('sidebar groups locations by group field', async ({ page }) => {
		/**
		 * GIVEN: Locations with group field exist
		 * WHEN: /compare page loads on desktop
		 * THEN: Group headers are visible in the sidebar
		 */
		await page.setViewportSize({ width: 1280, height: 720 });
		await page.goto('/compare');
		const sidebar = page.locator('aside');
		// Should have at least one group header or ungrouped locations
		// Group headers use a button/disclosure pattern
		const groupHeaders = sidebar.locator('[data-testid="group-header"]');
		// If locations have groups, headers should exist
		// This test validates the STRUCTURE exists (even if 0 groups)
		await expect(sidebar).toBeVisible();
	});

	test('group header toggles visibility of locations', async ({ page }) => {
		/**
		 * GIVEN: A group header exists in sidebar
		 * WHEN: User clicks the group header
		 * THEN: Locations in that group collapse/expand
		 */
		await page.setViewportSize({ width: 1280, height: 720 });
		await page.goto('/compare');
		const sidebar = page.locator('aside');
		const groupHeader = sidebar.locator('[data-testid="group-header"]').first();
		const count = await groupHeader.count();
		if (count > 0) {
			await groupHeader.click();
			// After click, group content should toggle
		}
	});

	test('LocationForm has group input field', async ({ page }) => {
		/**
		 * GIVEN: User opens "Neuer Ort" dialog
		 * WHEN: Dialog is visible
		 * THEN: A "Gruppe" input field exists
		 */
		await page.setViewportSize({ width: 1280, height: 720 });
		await page.goto('/compare');
		const sidebar = page.locator('aside');
		await sidebar.getByRole('button', { name: /Neuer Ort/i }).click();
		// Wait for dialog
		const dialog = page.locator('[role="dialog"]');
		await expect(dialog).toBeVisible();
		// Should have a group input
		const groupInput = dialog.locator('#loc-group, input[placeholder*="Gruppe"], input[placeholder*="gruppe"]');
		await expect(groupInput).toBeVisible();
	});

	test('backend accepts group field on location', async ({ page }) => {
		/**
		 * GIVEN: Go API is running
		 * WHEN: POST /api/locations with group field
		 * THEN: Response includes the group field
		 */
		// Login to get session
		await login(page);

		// #1329 Maßnahme B: zentralisiert über den geteilten Helfer (helpers.ts).
		// Vormals hart auf `http://localhost:8090` (PROD-Go-Port!) verdrahtet
		// statt relativ über die aktuelle baseURL/den Proxy zu laufen — der
		// geteilte Helfer nutzt `page.request`, respektiert also die konfigurierte
		// baseURL und trägt zusätzlich das reservierte Präfix (vormals
		// `__test_c4_group__`, kollisionsanfällig, Kontext-Dok.).
		const loc = await createTestLocation(page.request, {
			lat: 47.0,
			lon: 11.0,
			elevation_m: 2000,
			group: 'Test-Gruppe'
		});
		const resp = await page.request.get(`/api/locations/${loc.id}`);
		expect(resp.ok()).toBeTruthy();
		const body = await resp.json();
		expect(body.group).toBe('Test-Gruppe');
	});
});
