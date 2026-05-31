// TDD RED: Bug #484 — Dropdown-Menü abgeschnitten in overflow-Container
//
// Spec: docs/specs/modules/bug_484_dropdown_portal.md
//
// Voraussetzung: e2e-cockpit-test Trip aus global.setup.ts existiert.
// Desktop-Ansicht (1280x720) — das Kebab-Menü ist nur auf Desktop sichtbar.

import { test, expect } from '@playwright/test';

test.use({ viewport: { width: 1280, height: 720 } });

test.describe('Bug #484 — Trip-Aktionsmenü vollständig sichtbar', () => {
	test('AC-1: Alle Dropdown-Einträge sind vollständig im Viewport sichtbar', async ({ page }) => {
		await page.goto('/trips');
		await page.waitForLoadState('networkidle');

		// ⋯-Button öffnen (erster Trip in der Desktop-Tabelle)
		const menuBtn = page.getByRole('button', { name: 'Weitere Aktionen' }).first();
		await expect(menuBtn).toBeVisible();
		await menuBtn.click();

		// "Löschen" muss vollständig im Viewport liegen — dies schlägt fehl wenn geclippt
		const deleteBtn = page.getByRole('menuitem', { name: 'Löschen' });
		await expect(deleteBtn).toBeVisible();

		const box = await deleteBtn.boundingBox();
		expect(box).not.toBeNull();
		// Bounding Box muss vollständig innerhalb des Viewports liegen (nicht abgeschnitten)
		expect(box!.y + box!.height).toBeLessThanOrEqual(720);
		expect(box!.y).toBeGreaterThanOrEqual(0);
	});

	test('AC-2: Escape schließt das Dropdown', async ({ page }) => {
		await page.goto('/trips');
		await page.waitForLoadState('networkidle');

		const menuBtn = page.getByRole('button', { name: 'Weitere Aktionen' }).first();
		await menuBtn.click();

		// Dropdown ist offen
		const deleteBtn = page.getByRole('menuitem', { name: 'Löschen' });
		await expect(deleteBtn).toBeVisible();

		// Escape schließt
		await page.keyboard.press('Escape');
		await expect(deleteBtn).not.toBeVisible();
	});

	test('AC-3: Klick außerhalb schließt das Dropdown', async ({ page }) => {
		await page.goto('/trips');
		await page.waitForLoadState('networkidle');

		const menuBtn = page.getByRole('button', { name: 'Weitere Aktionen' }).first();
		await menuBtn.click();

		const deleteBtn = page.getByRole('menuitem', { name: 'Löschen' });
		await expect(deleteBtn).toBeVisible();

		// Außerhalb klicken
		await page.mouse.click(100, 100);
		await expect(deleteBtn).not.toBeVisible();
	});

	test('AC-3b: Bearbeiten-Aktion öffnet Edit-Dialog', async ({ page }) => {
		await page.goto('/trips');
		await page.waitForLoadState('networkidle');

		const menuBtn = page.getByRole('button', { name: 'Weitere Aktionen' }).first();
		await menuBtn.click();

		const editBtn = page.getByRole('menuitem', { name: 'Bearbeiten' });
		await expect(editBtn).toBeVisible();
		await editBtn.click();

		// Edit-Dialog öffnet sich
		await expect(page.getByRole('dialog')).toBeVisible();
	});
});
