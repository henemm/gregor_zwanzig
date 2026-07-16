// E2E — Bug #626: Ortsvergleiche Listen-Menü-Aktionen
//
// Spec: docs/specs/bugfix/bug_626_compare_menu_actions.md
//
// Issue #1256 Scheibe 1 (2026-07-13): AC-6 und AC-7 wurden auf den neuen
// Listen-Kebab-Vertrag korrigiert (Soll molecules.jsx:1018-1027) —
// "Archivieren" ist kein Bestandteil des Listen-Kebabs mehr (wandert in die
// Hub-Header-Lifecycle-Liste, Scheibe 3); "Briefing jetzt senden" ist seit
// #627 fester Bestandteil (die ursprüngliche AC-6-Annahme "kein send" war
// bereits vor dieser Scheibe stale). Siehe docs/specs/modules/issue_1256_compare_ui_rewire.md AC-1/AC-2.
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
	const tile = page.locator('[data-testid^="compare-tile-"]:visible').filter({ hasText: statusLabel }).first();
	await expect(tile).toBeVisible({ timeout: 10_000 });
	// Klick auf den Kebab-Button (⋯) innerhalb der Kachel
	const kebab = tile.locator('button[aria-label="Weitere Aktionen"]');
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
		const tile = page.locator('[data-testid^="compare-tile-"]:visible').first();
		await expect(tile).toBeVisible({ timeout: 10_000 });

		// Hole Preset-ID aus dem tile-Link oder data-Attribut
		const kebab = tile.locator('button[aria-label="Weitere Aktionen"]');
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
		const tile = page.locator('[data-testid^="compare-tile-"]:visible').first();
		await expect(tile).toBeVisible({ timeout: 10_000 });

		const kebab = tile.locator('button[aria-label="Weitere Aktionen"]');
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
		const aktivTile = page.locator('[data-testid^="compare-tile-"]:visible').filter({ hasText: 'aktiv' }).first();

		// Wenn keine aktive Kachel vorhanden — Test überspringen
		const count = await aktivTile.count();
		if (count === 0) {
			test.skip(true, 'Kein aktiver Vergleich auf der Seite — AC-2 nicht testbar');
			return;
		}

		await expect(aktivTile).toBeVisible({ timeout: 10_000 });

		// Öffne Kebab-Menü
		const kebab = aktivTile.locator('button[aria-label="Weitere Aktionen"]');
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
		const kebab2 = aktivTile.locator('button[aria-label="Weitere Aktionen"]');
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
		const pausedTile = page.locator('[data-testid^="compare-tile-"]:visible').filter({ hasText: 'pausiert' }).first();

		const count = await pausedTile.count();
		if (count === 0) {
			test.skip(true, 'Kein pausierter Vergleich auf der Seite — AC-3 nicht testbar');
			return;
		}

		await expect(pausedTile).toBeVisible({ timeout: 10_000 });

		const kebab = pausedTile.locator('button[aria-label="Weitere Aktionen"]');
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
		const kebab2 = pausedTile.locator('button[aria-label="Weitere Aktionen"]');
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
		const draftTile = page.locator('[data-testid^="compare-tile-"]:visible').filter({ hasText: 'draft' }).first();

		const count = await draftTile.count();
		if (count === 0) {
			test.skip(true, 'Kein Draft-Vergleich auf der Seite — AC-5 nicht testbar');
			return;
		}

		await expect(draftTile).toBeVisible({ timeout: 10_000 });
		const kebab = draftTile.locator('button[aria-label="Weitere Aktionen"]');
		await kebab.click();
		await page.waitForTimeout(500);

		const setupItem = page.getByRole('menuitem', { name: 'Setup fortsetzen' });
		await expect(setupItem).toBeVisible();
		await setupItem.click();

		await expect(page).toHaveURL(/\/compare\/[^/]+\/edit/, { timeout: 10_000 });
	});

	// ── AC-6 (korrigiert #1256 S1): "Briefing jetzt senden" IST Teil des Menüs ──
	//
	// #1256 S1: Korrigiert — die ursprüngliche bug-626-Annahme "kein 'Briefing
	// jetzt senden'" wurde bereits durch #627 (Einzel-Sofortversand) überholt;
	// "send" ist seit #627 fester Bestandteil des 5er-Vertrags (Soll
	// molecules.jsx:1018-1027). Assertion auf den aktuellen Vertrag umgestellt.

	test('AC-6 (korrigiert #1256 S1): Menü enthält "Briefing jetzt senden"', async ({ page }) => {
		const tile = page.locator('[data-testid^="compare-tile-"]:visible').first();
		await expect(tile).toBeVisible({ timeout: 10_000 });

		const kebab = tile.locator('button[aria-label="Weitere Aktionen"]');
		await kebab.click();
		await page.waitForTimeout(500);

		// Prüfe: "Briefing jetzt senden" ist vorhanden (#627, seit #1256 S1 fester Bestandteil der 5 Aktionen)
		const sendItem = page.getByRole('menuitem', { name: 'Briefing jetzt senden' });
		await expect(sendItem).toBeVisible();

		await page.keyboard.press('Escape');
	});

	// ── AC-7 (korrigiert #1256 S1): Listen-Kebab = genau 5 Aktionen, KEIN Archivieren ──
	//
	// #1256 S1: Archivieren aus Listen-Kebab entfernt (Soll molecules.jsx:1018-1027);
	// Hub-Lifecycle folgt in S3. Listen-Kebab active/paused = genau
	// [Pausieren|Aktivieren, Briefing jetzt senden, Vorschau öffnen, Bearbeiten, Löschen].

	test('AC-7 (korrigiert #1256 S1): Listen-Kebab zeigt genau 5 Aktionen ohne Archivieren', async ({
		page
	}) => {
		const tile = page.locator('[data-testid^="compare-tile-"]:visible').first();
		await expect(tile).toBeVisible({ timeout: 10_000 });

		const kebab = tile.locator('button[aria-label="Weitere Aktionen"]');
		await kebab.click();
		await page.waitForTimeout(500);

		// Pflicht-Aktionen: Löschen und Bearbeiten müssen weiterhin vorhanden sein.
		await expect(page.getByRole('menuitem', { name: 'Löschen' })).toBeVisible();
		await expect(page.getByRole('menuitem', { name: 'Bearbeiten' })).toBeVisible();
		await expect(page.getByRole('menuitem', { name: 'Vorschau öffnen' })).toBeVisible();
		await expect(page.getByRole('menuitem', { name: 'Briefing jetzt senden' })).toBeVisible();
		// Genau eine der beiden Toggle-Varianten (status-abhängig) muss vorhanden sein.
		const pauseOrActivate = page.getByRole('menuitem', { name: /^(Pausieren|Aktivieren)$/ });
		await expect(pauseOrActivate).toHaveCount(1);

		// #1256 S1: "Archivieren" darf im Listen-Kebab NICHT mehr vorkommen.
		await expect(page.getByRole('menuitem', { name: 'Archivieren' })).not.toBeVisible();

		// Exakt 5 Menüeinträge insgesamt (kein Archivieren, kein sechster Eintrag).
		const menuItems = page.getByRole('menuitem');
		await expect(menuItems).toHaveCount(5);

		// Schließe Menü per Escape
		await page.keyboard.press('Escape');
	});
});
