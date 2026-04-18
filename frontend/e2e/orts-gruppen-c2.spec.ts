import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('F76 Phase C2: Orts-Gruppen', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('sidebar shows group headers when locations have groups', async ({ page }) => {
		/**
		 * GIVEN: Locations with group field set exist
		 * WHEN: User opens /compare
		 * THEN: Group headers appear in the sidebar
		 */
		await page.goto('/compare');
		// Wait for sidebar to load
		const sidebar = page.locator('aside');
		await expect(sidebar).toBeVisible();
		// At least one group header with a chevron icon should exist
		const groupHeader = sidebar.locator('[data-testid="group-header"]');
		await expect(groupHeader.first()).toBeVisible();
	});

	test('group header checkbox toggles all locations in group', async ({ page }) => {
		/**
		 * GIVEN: A group with multiple locations exists
		 * WHEN: User clicks the group checkbox
		 * THEN: All locations in that group are selected/deselected
		 */
		await page.goto('/compare');
		const sidebar = page.locator('aside');
		const groupCheckbox = sidebar.locator('[data-testid="group-checkbox"]').first();
		await expect(groupCheckbox).toBeVisible();
		// Click to deselect all in group
		await groupCheckbox.click();
		// Verify locations in group are deselected
		const groupSection = sidebar.locator('[data-testid="group-section"]').first();
		const locationCheckboxes = groupSection.locator('input[type="checkbox"]:not([data-testid="group-checkbox"])');
		const count = await locationCheckboxes.count();
		for (let i = 0; i < count; i++) {
			await expect(locationCheckboxes.nth(i)).not.toBeChecked();
		}
	});

	test('clicking group header collapses/expands the group', async ({ page }) => {
		/**
		 * GIVEN: A group exists and is expanded
		 * WHEN: User clicks the group header
		 * THEN: The group collapses (locations hidden)
		 */
		await page.goto('/compare');
		const sidebar = page.locator('aside');
		const groupHeader = sidebar.locator('[data-testid="group-header"]').first();
		// Locations should be visible initially
		const groupSection = sidebar.locator('[data-testid="group-section"]').first();
		const locationLabel = groupSection.locator('label').first();
		await expect(locationLabel).toBeVisible();
		// Click header to collapse
		await groupHeader.click();
		// Locations should be hidden now
		await expect(locationLabel).not.toBeVisible();
	});

	test('LocationForm has group input field', async ({ page }) => {
		/**
		 * GIVEN: User opens location form
		 * WHEN: Form is displayed
		 * THEN: A group input field with datalist is present
		 */
		await page.goto('/locations');
		// Click "Neuer Ort" to open the form
		await page.click('button:has-text("Neuer Ort"), button:has-text("Hinzufügen")');
		const groupInput = page.locator('input#group, input[name="group"]');
		await expect(groupInput).toBeVisible();
	});

	test('ungrouped locations appear without group header', async ({ page }) => {
		/**
		 * GIVEN: Some locations have no group set
		 * WHEN: User opens /compare
		 * THEN: Ungrouped locations appear without a group header at the end
		 */
		await page.goto('/compare');
		const sidebar = page.locator('aside');
		// There should be locations NOT inside a group-section
		const ungroupedCheckbox = sidebar.locator('label:not([data-testid="group-section"] label) input[type="checkbox"]');
		// At least one ungrouped location should exist
		await expect(ungroupedCheckbox.first()).toBeVisible();
	});
});
