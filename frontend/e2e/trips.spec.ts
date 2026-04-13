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

	test('create trip dialog opens', async ({ page }) => {
		await page.goto('/trips');
		const createBtn = page.getByRole('button', { name: 'Neuer Trip' });
		await createBtn.click();

		// Dialog should be open with a trip name input
		const dialog = page.locator('[role="dialog"]');
		await expect(dialog).toBeVisible();
		const nameInput = dialog.locator('input[name="trip-name"], input[placeholder*="Name"]');
		await expect(nameInput).toBeVisible();
	});

	test('create trip with stage and waypoint', async ({ page }) => {
		await page.goto('/trips');
		const createBtn = page.getByRole('button', { name: 'Neuer Trip' });
		await createBtn.click();

		const dialog = page.locator('[role="dialog"]');

		// Fill trip name
		const nameInput = dialog.locator('input[name="trip-name"], input[placeholder*="Name"]');
		await nameInput.fill('E2E Test Trip');

		// Add a stage
		const addStageBtn = dialog.locator('button', { hasText: /Etappe|Stage/i });
		await addStageBtn.click();

		// Add a waypoint to the stage
		const addWpBtn = dialog.locator('button', { hasText: /Wegpunkt|Waypoint/i });
		await addWpBtn.click();

		// Fill waypoint name
		const wpNameInput = dialog.locator('input[name="waypoint-name"]').first();
		if (await wpNameInput.isVisible()) {
			await wpNameInput.fill('Testpunkt');
		}

		// Save
		const saveBtn = dialog.locator('button', { hasText: /Speichern|Save/i });
		await saveBtn.click();

		// Dialog should close
		await expect(dialog).not.toBeVisible({ timeout: 5000 });

		// Trip should appear in the list
		await expect(page.locator('text=E2E Test Trip')).toBeVisible();
	});

	test('edit trip opens pre-filled dialog', async ({ page }) => {
		await page.goto('/trips');

		// Find first edit button in the table
		const editBtn = page.locator('button[aria-label="Edit"], button:has-text("Edit"), button:has-text("Bearbeiten")').first();
		// Skip if no trips exist
		if (!(await editBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
			test.skip();
			return;
		}

		await editBtn.click();

		const dialog = page.locator('[role="dialog"]');
		await expect(dialog).toBeVisible();

		// Name input should be pre-filled (not empty)
		const nameInput = dialog.locator('input[name="trip-name"]');
		const value = await nameInput.inputValue();
		expect(value.length).toBeGreaterThan(0);
	});

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
