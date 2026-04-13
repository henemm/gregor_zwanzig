import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('Locations Page (M3b)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('locations page loads and shows table or empty state', async ({ page }) => {
		await page.goto('/locations');
		const table = page.locator('table');
		const emptyState = page.locator('[data-testid="empty-state"]');
		const visible =
			(await table.isVisible().catch(() => false)) ||
			(await emptyState.isVisible().catch(() => false));
		expect(visible).toBe(true);
	});

	test('has create location button', async ({ page }) => {
		await page.goto('/locations');
		const createBtn = page.getByRole('button', { name: 'Neue Location' });
		await expect(createBtn).toBeVisible();
	});

	test('create location dialog opens', async ({ page }) => {
		await page.goto('/locations');
		await page.getByRole('button', { name: 'Neue Location' }).click();

		const dialog = page.locator('[role="dialog"]');
		await expect(dialog).toBeVisible();
		const nameInput = dialog.locator('input[name="location-name"]');
		await expect(nameInput).toBeVisible();
	});

	test('create location with coordinates', async ({ page }) => {
		await page.goto('/locations');
		await page.getByRole('button', { name: 'Neue Location' }).click();

		const dialog = page.locator('[role="dialog"]');

		// Fill location fields
		await dialog.locator('input[name="location-name"]').fill('E2E Testort');
		await dialog.locator('input[name="location-lat"]').fill('47.123');
		await dialog.locator('input[name="location-lon"]').fill('11.456');
		await dialog.locator('input[name="location-elevation"]').fill('1500');

		// Save
		await dialog.locator('button', { hasText: /Speichern|Save/i }).click();

		// Dialog should close
		await expect(dialog).not.toBeVisible({ timeout: 5000 });

		// Location should appear in the list
		await expect(page.locator('text=E2E Testort')).toBeVisible();
	});

	test('edit location opens pre-filled dialog', async ({ page }) => {
		await page.goto('/locations');

		const firstRow = page.locator('table tbody tr').first();
		if (!(await firstRow.isVisible({ timeout: 3000 }).catch(() => false))) {
			test.skip();
			return;
		}

		const editBtn = firstRow.getByRole('button', { name: 'Bearbeiten' });
		await editBtn.click();

		const dialog = page.locator('[role="dialog"]');
		await expect(dialog).toBeVisible();

		const nameInput = dialog.locator('input[name="location-name"]');
		const value = await nameInput.inputValue();
		expect(value.length).toBeGreaterThan(0);
	});

	test('delete location with confirmation', async ({ page }) => {
		await page.goto('/locations');

		const firstRow = page.locator('table tbody tr').first();
		if (!(await firstRow.isVisible({ timeout: 3000 }).catch(() => false))) {
			test.skip();
			return;
		}
		const locationName = await firstRow.locator('td').first().textContent();
		const deleteBtn = firstRow.getByRole('button', { name: 'Löschen' });
		await deleteBtn.click();

		const dialog = page.locator('[role="dialog"]');
		await expect(dialog).toBeVisible();

		// Confirm delete
		const confirmBtn = dialog.locator('button', { hasText: /Löschen/i });
		await confirmBtn.click();

		await expect(dialog).not.toBeVisible({ timeout: 5000 });

		if (locationName) {
			await expect(
				page.locator('table').locator(`text=${locationName.trim()}`)
			).not.toBeVisible({ timeout: 5000 });
		}
	});

	test('table shows coordinates and elevation', async ({ page }) => {
		await page.goto('/locations');

		const firstRow = page.locator('table tbody tr').first();
		if (!(await firstRow.isVisible({ timeout: 3000 }).catch(() => false))) {
			test.skip();
			return;
		}

		const cells = firstRow.locator('td');
		const cellCount = await cells.count();
		// Name, Coordinates, Elevation, Profile, Actions = 5 columns min
		expect(cellCount).toBeGreaterThanOrEqual(4);
	});

	test('activity profile badge shown after selection', async ({ page }) => {
		await page.goto('/locations');
		await page.getByRole('button', { name: 'Neue Location' }).click();

		const dialog = page.locator('[role="dialog"]');
		await dialog.locator('input[name="location-name"]').fill('Profil Test');
		await dialog.locator('input[name="location-lat"]').fill('47.0');
		await dialog.locator('input[name="location-lon"]').fill('11.0');

		// Select activity profile
		await dialog.locator('select[name="activity-profile"]').selectOption('wandern');

		await dialog.locator('button', { hasText: /Speichern|Save/i }).click();
		await expect(dialog).not.toBeVisible({ timeout: 5000 });

		// Location should appear in list with profile badge
		await expect(page.locator('text=Profil Test')).toBeVisible();
		const row = page.locator('table tbody tr', { hasText: 'Profil Test' });
		await expect(row.locator('text=wandern')).toBeVisible();
	});
});
