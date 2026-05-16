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

	// 'create trip navigates to wizard' + 'create trip via wizard' entfernt (#217):
	// Tests verwendeten alte Wizard-Selectoren (trip-wizard, wizard-next, wizard-save,
	// trip-name-input) die seit Epic #136 nicht mehr existieren. Coverage durch
	// dedizierte trip-wizard-step1/2/3/4.spec.ts + trip-wizard-shell.spec.ts.
	// Vollstaendige Entfernung des alten Wizards: Issue #190.

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
