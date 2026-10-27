// TDD RED — Issue #321: COPY-Fix "Trip/Trips" → "Trip/Trips"
//
// Spec: docs/specs/modules/issue_321_copy_fix_deine_touren.md (AC-1 bis AC-5)
//
// ALLE Tests MÜSSEN FEHLSCHLAGEN vor der Implementierung:
//   H1 zeigt "Trips" statt "Meine Trips"
//   Button zeigt "Neuer Trip" statt "+ Neue Trip"
//   Dialog zeigt "Trip löschen" statt "Trip löschen"
//   BottomNav zeigt "Trips" statt "Trips"

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

const DESKTOP_VIEWPORT = { width: 1440, height: 900 };
const MOBILE_VIEWPORT = { width: 375, height: 667 };

test.describe('Issue #321 — COPY-Fix "Trip/Trips" in Trips-Listenansicht', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// ─── AC-1: H1 lautet "Meine Trips" ─────────────────────────────────────
	test('AC-1: H1 auf /trips lautet "Meine Trips" (nicht "Trips")', async ({ page }) => {
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/trips');

		const h1 = page.locator('h1').first();
		await expect(h1).toBeVisible({ timeout: 5000 });
		await expect(h1).toHaveText('Meine Trips');
		await expect(h1).not.toContainText('Trips');
	});

	// ─── AC-2: Empty-State verwendet kanonische COPY-Texte ───────────────────
	test('AC-2: Empty-State zeigt "Noch keine Trip." und CTA "+ Neue Trip"', async ({ page }) => {
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/trips');

		const emptyState = page.locator('[data-testid="empty-state"]');
		const isEmpty = await emptyState.isVisible({ timeout: 3000 }).catch(() => false);
		if (!isEmpty) { test.skip(); return; }

		await expect(emptyState.locator('p.font-medium')).toHaveText('Noch keine Trip.');
		await expect(emptyState.getByRole('button', { name: '+ Neue Trip' })).toBeVisible();
		await expect(emptyState).not.toContainText('Trips');
		await expect(emptyState).not.toContainText('Trip');
	});

	// ─── AC-3: Lösch-Dialog-Titel lautet "Trip löschen" ─────────────────────
	test('AC-3: Delete-Dialog zeigt "Trip löschen" (nicht "Trip löschen")', async ({ page }) => {
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/trips');

		const firstRow = page.locator('table tbody tr').first();
		const hasRows = await firstRow.isVisible({ timeout: 3000 }).catch(() => false);
		if (!hasRows) { test.skip(); return; }

		const kebab = firstRow.locator('button[aria-label="Weitere Aktionen"], button[title="Weitere Aktionen"]').first();
		await kebab.click();

		// Kebab-Dropdown ist ein div[role="menu"] mit plain <button>-Eintraegen (kein menuitem-Role).
		const deleteItem = page.locator('div[role="menu"] button', { hasText: 'Löschen' }).first();
		await expect(deleteItem).toBeVisible({ timeout: 2000 });
		await deleteItem.click();

		// Dialog.Title rendert als div[data-slot="dialog-title"][role="heading"], kein <h2>.
		const dialogTitle = page.locator('[data-slot="dialog-title"]').first();
		await expect(dialogTitle).toBeVisible({ timeout: 2000 });
		await expect(dialogTitle).toHaveText('Trip löschen');
		await expect(dialogTitle).not.toContainText('Trip');

		await page.keyboard.press('Escape');
	});

	// ─── AC-4: BottomNav-Label lautet "Trips" ───────────────────────────────
	test('AC-4: Mobile BottomNav-Label lautet "Trips" (nicht "Trips")', async ({ page }) => {
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/trips');

		const navItem = page.getByTestId('bottom-nav-item-trips');
		await expect(navItem).toBeVisible({ timeout: 5000 });
		await expect(navItem).toContainText('Trips');
		await expect(navItem).not.toContainText('Trips');
	});

	// ─── AC-5: Primärer Anlegen-Button lautet "+ Neue Trip" ──────────────────
	test('AC-5: Header-Button lautet "+ Neue Trip" (nicht "Neuer Trip")', async ({ page }) => {
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/trips');

		const createBtn = page.getByRole('button', { name: '+ Neue Trip' });
		await expect(createBtn).toBeVisible({ timeout: 5000 });
		await expect(page.getByRole('button', { name: 'Neuer Trip' })).not.toBeVisible();
	});

	// ─── Bonus: Footer-Zähler verwendet "Trips" ─────────────────────────────
	test('Bonus: Footer-Zähler zeigt "Trips" statt "Trips"', async ({ page }) => {
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/trips');

		const table = page.locator('table');
		const hasTable = await table.isVisible({ timeout: 3000 }).catch(() => false);
		if (!hasTable) { test.skip(); return; }

		const footer = page.locator('.font-mono.text-xs').filter({ hasText: /von/ }).first();
		await expect(footer).toBeVisible({ timeout: 3000 });
		await expect(footer).toContainText('Trips');
		await expect(footer).not.toContainText('Trips');
	});
});
