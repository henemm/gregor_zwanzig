import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('Issue #90 — Trip-Übersicht: Aktionsicons gruppiert darstellen', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.goto('/trips');
		const firstRow = page.locator('table tbody tr').first();
		await expect(firstRow).toBeVisible({ timeout: 10_000 });
	});

	test('AC-1: Aktions-Cell enthält drei Gruppen-Container mit korrekten Gap-Klassen', async ({
		page
	}) => {
		const firstRow = page.locator('table tbody tr').first();
		const actionsCell = firstRow.locator('td').last();

		const outerContainer = actionsCell.locator('> div').first();
		const outerClass = (await outerContainer.getAttribute('class')) ?? '';
		expect(outerClass).toMatch(/\bgap-3\b/);

		const innerGroups = outerContainer.locator(':scope > div');
		await expect(innerGroups).toHaveCount(3);

		for (let i = 0; i < 3; i++) {
			const innerClass = (await innerGroups.nth(i).getAttribute('class')) ?? '';
			expect(innerClass).toMatch(/gap-0\.5/);
		}
	});

	test('AC-2: Mobile-Viewport — nur Edit-Gruppe sichtbar, Send- und Delete-Gruppe versteckt', async ({
		page
	}) => {
		await page.setViewportSize({ width: 500, height: 800 });
		await page.reload();

		const firstRow = page.locator('table tbody tr').first();
		await expect(firstRow).toBeVisible({ timeout: 10_000 });

		const actionsCell = firstRow.locator('td').last();
		const outerContainer = actionsCell.locator('> div').first();
		const innerGroups = outerContainer.locator(':scope > div');

		await expect(innerGroups).toHaveCount(3);
		await expect(innerGroups.nth(0)).toBeVisible();
		await expect(innerGroups.nth(1)).not.toBeVisible();
		await expect(innerGroups.nth(2)).not.toBeVisible();
	});

	test('AC-3: DOM-Reihenfolge — Bell → CloudSun → Pencil → Play → Play → Trash', async ({
		page
	}) => {
		const firstRow = page.locator('table tbody tr').first();
		const actionsCell = firstRow.locator('td').last();

		const buttons = actionsCell.locator('button');
		await expect(buttons).toHaveCount(6);

		const titles = await buttons.evaluateAll((els) =>
			els.map((el) => el.getAttribute('title'))
		);

		expect(titles).toEqual([
			'Report-Konfiguration',
			'Wetter-Konfiguration',
			'Bearbeiten',
			'Test Morgen-Report',
			'Test Abend-Report',
			'Löschen'
		]);
	});

	test('AC-4: data-testid="trip-edit-btn" bleibt erreichbar und liegt in der Edit-Gruppe', async ({
		page
	}) => {
		const firstRow = page.locator('table tbody tr').first();
		const actionsCell = firstRow.locator('td').last();
		const outerContainer = actionsCell.locator('> div').first();
		const innerGroups = outerContainer.locator(':scope > div');

		const editBtnInEditGroup = innerGroups.nth(0).locator('[data-testid="trip-edit-btn"]');
		await expect(editBtnInEditGroup).toHaveCount(1);
		await expect(editBtnInEditGroup).toBeVisible();
	});
});
