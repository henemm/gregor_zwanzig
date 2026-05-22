// E2E — Bug #320: Sidebar-Nav hat nur 3 Items — "Archiv" fehlt (CHARTER §2)
//
// Spec: docs/specs/modules/bug_320_sidebar_archiv.md (AC-1 bis AC-4)
//
// TDD RED: Diese Tests MÜSSEN FEHLSCHLAGEN, weil:
//   - Sidebar.svelte navItems[3] noch auf /locations zeigt (nicht /archiv)
//   - BottomNav.svelte noch 'bottom-nav-item-locations' hat (nicht 'bottom-nav-item-archive')
//   - /archiv-Route noch nicht existiert → 404 / Redirect nach /login
//
// Nach Implementation müssen alle Tests grün sein.
//
// TestID-Inventar (wird in Implementation gesetzt):
//   desktop-sidebar                — bestehend (Sidebar.svelte)
//   bottom-nav                     — bestehend (BottomNav.svelte)
//   bottom-nav-item-archive        — NEU (ersetzt bottom-nav-item-locations)

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

const MOBILE_VIEWPORT = { width: 375, height: 667 };
const DESKTOP_VIEWPORT = { width: 1440, height: 900 };

test.describe('Bug #320: Sidebar + BottomNav — Archiv als 4. Nav-Item', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// ─── AC-1: Desktop-Sidebar zeigt /archiv, nicht /locations ─────────────
	test('AC-1: Desktop-Sidebar zeigt 4 Items mit Archiv statt Standorte', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt, Desktop-Viewport
		 * WHEN:  Sidebar gerendert
		 * THEN:  Link zu /archiv vorhanden, kein Link zu /locations in der Sidebar
		 */
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/');

		const sidebar = page.getByTestId('desktop-sidebar');

		// Pflicht-Links der ersten 3 Items (unverändert)
		await expect(sidebar.locator('a[href="/"]').filter({ hasText: 'Startseite' })).toBeVisible();
		await expect(sidebar.locator('a[href="/trips"]').filter({ hasText: 'Meine Touren' })).toBeVisible();
		await expect(sidebar.locator('a[href="/compare"]').filter({ hasText: 'Orts-Vergleich' })).toBeVisible();

		// 4. Item MUSS /archiv sein
		await expect(sidebar.locator('a[href="/archiv"]')).toBeVisible();

		// /locations DARF NICHT mehr in der Haupt-Sidebar stehen
		await expect(sidebar.locator('a[href="/locations"]')).toHaveCount(0);
	});

	// ─── AC-2: BottomNav hat bottom-nav-item-archive (Mobile) ───────────────
	test('AC-2: BottomNav zeigt "Archiv" als 4. Item mit korrektem testid', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt, Mobile-Viewport (375px)
		 * WHEN:  BottomNav gerendert
		 * THEN:  data-testid="bottom-nav-item-archive" sichtbar,
		 *        data-testid="bottom-nav-item-locations" existiert nicht
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/');

		// Archiv-Item MUSS vorhanden sein
		await expect(page.getByTestId('bottom-nav-item-archive')).toBeVisible();

		// Locations-Item DARF NICHT mehr in der BottomNav stehen
		await expect(page.getByTestId('bottom-nav-item-locations')).toHaveCount(0);
	});

	// ─── AC-3: /archiv-Route antwortet 200 + zeigt Inhalt ──────────────────
	test('AC-3a: /archiv-Route antwortet mit 200 (kein 404/Redirect)', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt
		 * WHEN:  User navigiert direkt zu /archiv
		 * THEN:  URL bleibt /archiv (kein Redirect zu /login oder 404)
		 */
		await page.goto('/archiv');
		await expect(page).toHaveURL('/archiv');
	});

	test('AC-3b: /archiv-Seite zeigt Eyebrow "ARCHIV" und Empty-State', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt, /archiv-Route existiert
		 * WHEN:  Seite geladen
		 * THEN:  Eyebrow enthält "ARCHIV", Empty-State-Text sichtbar
		 */
		await page.goto('/archiv');

		// Eyebrow: "ARCHIV · VERGANGENE TOUREN"
		await expect(page.getByText('ARCHIV · VERGANGENE TOUREN')).toBeVisible();

		// Empty-State-Text
		await expect(page.locator('text=/Archiv/i').first()).toBeVisible();
	});

	test('AC-3c: Klick auf "Archiv" in Sidebar navigiert zu /archiv', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt, Desktop-Viewport
		 * WHEN:  User klickt auf "Archiv" in der Sidebar
		 * THEN:  URL wechselt auf /archiv
		 */
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/');

		const sidebar = page.getByTestId('desktop-sidebar');
		await sidebar.locator('a[href="/archiv"]').click();
		await expect(page).toHaveURL('/archiv');
	});

	// ─── AC-4: /locations-Route weiterhin erreichbar ────────────────────────
	test('AC-4: /locations-Route bleibt erreichbar (kein Breaking Change)', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt
		 * WHEN:  User ruft /locations direkt auf
		 * THEN:  URL bleibt /locations (kein 404) — backward compatibility
		 */
		await page.goto('/locations');
		await expect(page).toHaveURL('/locations');
	});
});
