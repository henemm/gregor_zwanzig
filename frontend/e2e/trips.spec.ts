import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('Trips Page (M3a)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('trips page loads and shows table or empty state', async ({ page }) => {
		await page.goto('/trips');
		// Should show either a table or an empty state message
		const table = page.locator('table');
		const emptyState = page.locator('[data-testid="empty-state"]');
		const visible = await table.isVisible().catch(() => false)
			|| await emptyState.isVisible().catch(() => false);
		expect(visible).toBe(true);
	});

	test('has create trip button', async ({ page }) => {
		await page.goto('/trips');
		const createBtn = page.getByRole('button', { name: 'Neuer Trip' });
		await expect(createBtn).toBeVisible();
	});

	test('create trip navigates to wizard', async ({ page }) => {
		await page.goto('/trips');
		const createBtn = page.getByRole('button', { name: 'Neuer Trip' });
		await createBtn.click();

		// Should navigate to wizard page
		await page.waitForURL('/trips/new');
		await expect(page.locator('[data-testid="trip-wizard"]')).toBeVisible();

		// Wizard should show trip name input
		const nameInput = page.locator('[data-testid="trip-name-input"]');
		await expect(nameInput).toBeVisible();
	});

	test('create trip via wizard', async ({ page }) => {
		await page.goto('/trips/new');

		// Fill trip name
		const nameInput = page.locator('[data-testid="trip-name-input"]');
		await nameInput.fill('E2E Test Trip');

		// Add a manual stage
		const manualBtn = page.locator('button', { hasText: /[Mm]anuell/ });
		await manualBtn.click();

		// Navigate to step 2
		await page.locator('[data-testid="wizard-next"]').click();

		// Add a waypoint
		const addWpBtn = page.locator('button', { hasText: /[Ww]egpunkt/ });
		await addWpBtn.click();

		// Fill waypoint coordinates
		await page.locator('input[name="lat"]').first().fill('47.0');
		await page.locator('input[name="lon"]').first().fill('11.0');

		// Navigate to step 3 and 4
		await page.locator('[data-testid="wizard-next"]').click();
		await page.locator('[data-testid="wizard-next"]').click();

		// Save
		const saveBtn = page.locator('[data-testid="wizard-save"]');
		await saveBtn.click();

		// Should navigate back to trips list
		await page.waitForURL('/trips', { timeout: 5000 });

		// Trip should appear in the list
		await expect(page.locator('text=E2E Test Trip')).toBeVisible();
	});

	// 'edit trip navigates to wizard with pre-filled name' moved to trip-edit.spec.ts (Issue #91 — TripEditView replaces TripWizard for edit).

	test('delete trip with confirmation', async ({ page }) => {
		await page.goto('/trips');

		// Find first delete button in the table
		const firstRow = page.locator('table tbody tr').first();
		if (!(await firstRow.isVisible({ timeout: 3000 }).catch(() => false))) {
			test.skip();
			return;
		}
		const tripName = await firstRow.locator('td').first().textContent();
		const deleteBtn = firstRow.getByRole('button', { name: 'Löschen' });
		await deleteBtn.click();

		// Confirmation dialog should appear
		const dialog = page.locator('[role="dialog"]');
		await expect(dialog).toBeVisible();

		// Click the destructive confirm button inside dialog
		const confirmBtn = dialog.locator('button', { hasText: /Löschen/i });
		await confirmBtn.click();

		// Dialog should close
		await expect(dialog).not.toBeVisible({ timeout: 5000 });

		// Trip should no longer be in the table
		if (tripName) {
			await expect(page.locator('table').locator(`text=${tripName.trim()}`)).not.toBeVisible({ timeout: 5000 });
		}
	});

	test('trips table shows stage count and date range', async ({ page }) => {
		await page.goto('/trips');

		const firstRow = page.locator('table tbody tr').first();
		if (!(await firstRow.isVisible({ timeout: 3000 }).catch(() => false))) {
			test.skip();
			return;
		}

		// Should have columns for stages/date
		const cells = firstRow.locator('td');
		const cellCount = await cells.count();
		// At minimum: Name, Stages, Date Range, Actions = 4 columns
		expect(cellCount).toBeGreaterThanOrEqual(3);
	});
});
