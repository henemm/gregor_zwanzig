// E2E — Bug #626: Ortsvergleiche Listen-Menü-Aktionen
//
// Spec: docs/specs/bugfix/bug_626_compare_menu_actions.md
//
// Verifikation der 7 ACs als eingeloggter Nutzer gegen Staging.
// Voraussetzung: mindestens ein aktiver Compare-Preset und ein pausierter
// Compare-Preset existieren im Test-Account.
//
// Base-URL: GZ_SVELTE_BASE (Default: playwright.config.ts baseURL = Staging)
//
// Ausführen:
//   cd frontend && E2E_USER=admin E2E_PASS=test1234 \
//     npx playwright test e2e/bug-626-compare-menu-actions.spec.ts \
//     --config playwright.config.ts

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

// Hilfsfunktion: Öffnet das Kebab-Menü der ersten Kachel mit einem bestimmten Status-Label
async function openKebabForStatus(page: import('@playwright/test').Page, statusLabel: string) {
	// Finde eine Kachel, die den gesuchten Status-Label enthält
	const tile = page.locator('[data-testid="compare-tile"]').filter({ hasText: statusLabel }).first();
	await expect(tile).toBeVisible({ timeout: 10_000 });
	// Klick auf den Kebab-Button (⋯) innerhalb der Kachel
	const kebab = tile.locator('[data-testid="compare-tile-kebab"]');
	await kebab.click();
	// Warte auf Dropdown
	await page.waitForTimeout(500);
	return tile;
}

test.describe('Bug #626: Compare Listen-Menü-Aktionen (#626)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.setViewportSize({ width: 1280, height: 900 });
		await page.goto('/compare');
		await page.waitForLoadState('networkidle');
	});

	// ── AC-1: Bearbeiten → /compare/{id}/edit ────────────────────────────────

	test('AC-1: "Bearbeiten" navigiert zu /compare/{id}/edit', async ({ page }) => {
		// Finde die erste aktive oder pausierte Kachel
		const tile = page.locator('[data-testid="compare-tile"]').first();
		await expect(tile).toBeVisible({ timeout: 10_000 });

		// Hole Preset-ID aus dem tile-Link oder data-Attribut
		const kebab = tile.locator('[data-testid="compare-tile-kebab"]');
		await kebab.click();
		await page.waitForTimeout(500);

		// Klick auf "Bearbeiten"
		const editItem = page.getByRole('menuitem', { name: 'Bearbeiten' });
		await expect(editItem).toBeVisible();
		await editItem.click();

		// Prüfe Navigation zur Edit-Seite
		await expect(page).toHaveURL(/\/compare\/[^/]+\/edit/, { timeout: 10_000 });
	});

	// ── AC-4: Vorschau → /compare/{id}?tab=vorschau ──────────────────────────

	test('AC-4: "Vorschau öffnen" navigiert zu ?tab=vorschau', async ({ page }) => {
		const tile = page.locator('[data-testid="compare-tile"]').first();
		await expect(tile).toBeVisible({ timeout: 10_000 });

		const kebab = tile.locator('[data-testid="compare-tile-kebab"]');
		await kebab.click();
		await page.waitForTimeout(500);

		// Klick auf "Vorschau öffnen"
		const previewItem = page.getByRole('menuitem', { name: 'Vorschau öffnen' });
		await expect(previewItem).toBeVisible();
		await previewItem.click();

		// Prüfe URL enthält ?tab=vorschau
		await expect(page).toHaveURL(/\?tab=vorschau/, { timeout: 10_000 });
	});

	// ── AC-2: Aktiver Vergleich pausieren → schedule='manual' ────────────────

	test('AC-2: "Pausieren" wechselt aktiven Vergleich zu pausiert', async ({ page }) => {
		// Suche eine Kachel mit Status "aktiv"
		const aktivTile = page.locator('[data-testid="compare-tile"]').filter({ hasText: 'aktiv' }).first();

		// Wenn keine aktive Kachel vorhanden — Test überspringen
		const count = await aktivTile.count();
		if (count === 0) {
			test.skip(true, 'Kein aktiver Vergleich auf der Seite — AC-2 nicht testbar');
			return;
		}

		await expect(aktivTile).toBeVisible({ timeout: 10_000 });

		// Öffne Kebab-Menü
		const kebab = aktivTile.locator('[data-testid="compare-tile-kebab"]');
		await kebab.click();
		await page.waitForTimeout(500);

		// Prüfe: Menü enthält "Pausieren" (nicht "Aktivieren")
		const pauseItem = page.getByRole('menuitem', { name: 'Pausieren' });
		await expect(pauseItem).toBeVisible();

		// Klick auf "Pausieren"
		await pauseItem.click();

		// Warte auf Reaktivität — Status-Pill soll auf "pausiert" wechseln
		await page.waitForTimeout(1000);

		// Prüfe: dieselbe Kachel zeigt jetzt "pausiert"
		// (Die Kachel ist noch vorhanden, da Pausieren nicht aus der Liste entfernt)
		const statusPill = aktivTile.locator('[data-testid="compare-status-pill"]');
		await expect(statusPill).toContainText('pausiert', { timeout: 5_000 });

		// Prüfe: Kebab-Menü zeigt jetzt "Aktivieren"
		const kebab2 = aktivTile.locator('[data-testid="compare-tile-kebab"]');
		await kebab2.click();
		await page.waitForTimeout(500);
		const activateItem = page.getByRole('menuitem', { name: 'Aktivieren' });
		await expect(activateItem).toBeVisible();
		// Aufräumen: wieder aktivieren
		await activateItem.click();
		await page.waitForTimeout(1000);
	});

	// ── AC-3: Pausierten Vergleich aktivieren → schedule='daily' ─────────────

	test('AC-3: "Aktivieren" wechselt pausierten Vergleich zu aktiv', async ({ page }) => {
		// Suche eine Kachel mit Status "pausiert"
		const pausedTile = page.locator('[data-testid="compare-tile"]').filter({ hasText: 'pausiert' }).first();

		const count = await pausedTile.count();
		if (count === 0) {
			test.skip(true, 'Kein pausierter Vergleich auf der Seite — AC-3 nicht testbar');
			return;
		}

		await expect(pausedTile).toBeVisible({ timeout: 10_000 });

		const kebab = pausedTile.locator('[data-testid="compare-tile-kebab"]');
		await kebab.click();
		await page.waitForTimeout(500);

		// Prüfe: Menü enthält "Aktivieren" (nicht "Pausieren")
		const activateItem = page.getByRole('menuitem', { name: 'Aktivieren' });
		await expect(activateItem).toBeVisible();

		// Klick auf "Aktivieren"
		await activateItem.click();
		await page.waitForTimeout(1000);

		// Prüfe: Status-Pill wechselt auf "aktiv"
		const statusPill = pausedTile.locator('[data-testid="compare-status-pill"]');
		await expect(statusPill).toContainText('aktiv', { timeout: 5_000 });

		// Prüfe: Kebab-Menü zeigt jetzt "Pausieren"
		const kebab2 = pausedTile.locator('[data-testid="compare-tile-kebab"]');
		await kebab2.click();
		await page.waitForTimeout(500);
		const pauseItem = page.getByRole('menuitem', { name: 'Pausieren' });
		await expect(pauseItem).toBeVisible();
		// Aufräumen: wieder pausieren
		await pauseItem.click();
		await page.waitForTimeout(1000);
	});

	// ── AC-5: Draft → "Setup fortsetzen" → /compare/{id}/edit ───────────────

	test('AC-5: "Setup fortsetzen" navigiert Draft zu /compare/{id}/edit', async ({ page }) => {
		const draftTile = page.locator('[data-testid="compare-tile"]').filter({ hasText: 'draft' }).first();

		const count = await draftTile.count();
		if (count === 0) {
			test.skip(true, 'Kein Draft-Vergleich auf der Seite — AC-5 nicht testbar');
			return;
		}

		await expect(draftTile).toBeVisible({ timeout: 10_000 });
		const kebab = draftTile.locator('[data-testid="compare-tile-kebab"]');
		await kebab.click();
		await page.waitForTimeout(500);

		const setupItem = page.getByRole('menuitem', { name: 'Setup fortsetzen' });
		await expect(setupItem).toBeVisible();
		await setupItem.click();

		await expect(page).toHaveURL(/\/compare\/[^/]+\/edit/, { timeout: 10_000 });
	});

	// ── AC-6: Kein "Briefing jetzt senden" im Menü ───────────────────────────

	test('AC-6: Menü enthält kein "Briefing jetzt senden"', async ({ page }) => {
		const tile = page.locator('[data-testid="compare-tile"]').first();
		await expect(tile).toBeVisible({ timeout: 10_000 });

		const kebab = tile.locator('[data-testid="compare-tile-kebab"]');
		await kebab.click();
		await page.waitForTimeout(500);

		// Prüfe: kein "Briefing jetzt senden" vorhanden
		const sendItem = page.getByRole('menuitem', { name: 'Briefing jetzt senden' });
		await expect(sendItem).not.toBeVisible();
	});

	// ── AC-7: Archivieren + Löschen funktionieren weiterhin (Regression) ─────

	test('AC-7 Regression: "Archivieren" und "Löschen" sind im Menü sichtbar', async ({ page }) => {
		const tile = page.locator('[data-testid="compare-tile"]').first();
		await expect(tile).toBeVisible({ timeout: 10_000 });

		const kebab = tile.locator('[data-testid="compare-tile-kebab"]');
		await kebab.click();
		await page.waitForTimeout(500);

		// Beide Aktionen müssen im Menü vorhanden sein
		await expect(page.getByRole('menuitem', { name: 'Archivieren' })).toBeVisible();
		await expect(page.getByRole('menuitem', { name: 'Löschen' })).toBeVisible();

		// Schließe Menü per Escape
		await page.keyboard.press('Escape');
	});
});
