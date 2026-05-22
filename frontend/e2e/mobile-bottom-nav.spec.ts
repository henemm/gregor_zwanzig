// E2E — Issue #267: Mobile Bottom-Navigation
//
// Spec: docs/specs/modules/issue_267_mobile_bottom_nav.md (AC-1 bis AC-7)
//
// TDD RED: Diese Tests MÜSSEN FEHLSCHLAGEN, weil BottomNav.svelte und
// TopAppBar.svelte noch nicht existieren und die Sidebar noch kein
// data-testid="bottom-nav" / "top-app-bar" hat.
//
// TestID-Inventar (wird in Implementation angelegt):
//   bottom-nav                    — BottomNav-Container (fixed, 64px)
//   bottom-nav-item-home          — Link zu /
//   bottom-nav-item-trips         — Link zu /trips
//   bottom-nav-item-compare       — Link zu /compare
//   bottom-nav-item-archive       — Link zu /archiv
//   top-app-bar                   — TopAppBar-Container (mobile only)
//   top-app-bar-hamburger         — Hamburger-Button
//   top-app-bar-toggle-dark       — Dark-Mode-Toggle

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

const MOBILE_VIEWPORT = { width: 375, height: 667 };
const DESKTOP_VIEWPORT = { width: 1440, height: 900 };

test.describe('Issue #267: Mobile Bottom-Navigation', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// ─── AC-1: TopAppBar sichtbar auf Mobile ────────────────────────────────
	test('AC-1: TopAppBar ist auf Mobile-Viewport sichtbar (< 900px)', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt
		 * WHEN:  Viewport ist 375×667 px (Mobile)
		 * THEN:  TopAppBar mit data-testid="top-app-bar" ist sichtbar
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/');

		const topBar = page.getByTestId('top-app-bar');
		await expect(topBar).toBeVisible();
	});

	// ─── AC-1b: Desktop-Sidebar NICHT sichtbar auf Mobile ───────────────────
	test('AC-1b: Desktop-Sidebar ist auf Mobile-Viewport NICHT sichtbar', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt
		 * WHEN:  Viewport ist 375×667 px (Mobile)
		 * THEN:  Desktop-Sidebar (nav.desktop-nav) ist nicht sichtbar
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/');

		// Desktop-Sidebar hat data-testid="desktop-sidebar" nach Implementation
		const sidebar = page.getByTestId('desktop-sidebar');
		await expect(sidebar).not.toBeVisible();
	});

	// ─── AC-2: BottomNav mit 4 Items auf Mobile ─────────────────────────────
	test('AC-2: BottomNav ist auf Mobile-Viewport sichtbar', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt
		 * WHEN:  Viewport ist 375×667 px (Mobile)
		 * THEN:  BottomNav mit data-testid="bottom-nav" ist sichtbar
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/');

		const nav = page.getByTestId('bottom-nav');
		await expect(nav).toBeVisible();
	});

	test('AC-2b: BottomNav hat genau 4 Nav-Items', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt, Mobile-Viewport
		 * WHEN:  BottomNav gerendert
		 * THEN:  4 Links (Übersicht, Trips, Vergleich, Locations)
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/');

		await expect(page.getByTestId('bottom-nav-item-home')).toBeVisible();
		await expect(page.getByTestId('bottom-nav-item-trips')).toBeVisible();
		await expect(page.getByTestId('bottom-nav-item-compare')).toBeVisible();
		await expect(page.getByTestId('bottom-nav-item-archive')).toBeVisible();
	});

	// ─── AC-3: Navigation via BottomNav + Akzent-Linie ─────────────────────
	test('AC-3: Klick auf "Trips" navigiert zu /trips und zeigt Akzent', async ({ page }) => {
		/**
		 * GIVEN: User ist auf Startseite, Mobile-Viewport
		 * WHEN:  User tippt auf "Trips" in der BottomNav
		 * THEN:  URL wird /trips, Trips-Item hat box-shadow Akzent-Linie
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/');

		await page.getByTestId('bottom-nav-item-trips').click();
		await expect(page).toHaveURL('/trips');

		// Aktives Item hat aria-current="page" oder data-active="true"
		const tripsItem = page.getByTestId('bottom-nav-item-trips');
		await expect(tripsItem).toHaveAttribute('aria-current', 'page');
	});

	test('AC-3b: Aktiver Startseite-Link hat Akzent-Markierung', async ({ page }) => {
		/**
		 * GIVEN: User ist auf / , Mobile-Viewport
		 * WHEN:  BottomNav gerendert
		 * THEN:  Home-Item hat aria-current="page"
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/');

		const homeItem = page.getByTestId('bottom-nav-item-home');
		await expect(homeItem).toHaveAttribute('aria-current', 'page');
	});

	// ─── AC-4: Drawer zeigt nur sekundäre Items ──────────────────────────────
	test('AC-4: Drawer zeigt Konto und Logout, KEINE Workspace-Nav-Links', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt, Mobile-Viewport
		 * WHEN:  User öffnet Hamburger-Drawer
		 * THEN:  Drawer hat Konto + Logout, KEINE Links zu /trips, /compare, /locations
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/');

		await page.getByTestId('top-app-bar-hamburger').click();

		// Sekundäre Items müssen vorhanden sein
		await expect(page.locator('a[href="/account"]').first()).toBeVisible();
		await expect(page.locator('button[type="submit"]').filter({ hasText: 'Abmelden' })).toBeVisible();

		// Workspace-Nav DARF NICHT im Drawer sein
		// (Diese Links sind jetzt in der BottomNav, nicht im Drawer)
		const drawerTripsLink = page.locator('[data-testid="mobile-drawer"] a[href="/trips"]');
		await expect(drawerTripsLink).toHaveCount(0);

		const drawerCompareLink = page.locator('[data-testid="mobile-drawer"] a[href="/compare"]');
		await expect(drawerCompareLink).toHaveCount(0);
	});

	// ─── AC-5: Safe-Area / Content nicht unter BottomNav ────────────────────
	test('AC-5: Main-Content endet oberhalb der BottomNav (kein Overlap)', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt, Mobile-Viewport
		 * WHEN:  App geladen
		 * THEN:  BottomNav hat padding-bottom mit env(safe-area-inset-bottom)
		 *        main hat ausreichend padding-bottom (≥ 64px)
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/');

		const main = page.locator('main');
		const paddingBottom = await main.evaluate((el) =>
			parseInt(window.getComputedStyle(el).paddingBottom, 10)
		);

		// Main-Content-Padding muss mindestens 64px betragen (BottomNav-Höhe)
		expect(paddingBottom).toBeGreaterThanOrEqual(64);
	});

	// ─── AC-6: Desktop unverändert ──────────────────────────────────────────
	test('AC-6: Desktop-Sidebar ist bei ≥ 900px sichtbar, keine BottomNav', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt
		 * WHEN:  Viewport ist 1440×900 px (Desktop)
		 * THEN:  Desktop-Sidebar sichtbar, BottomNav NICHT sichtbar
		 */
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/');

		await expect(page.getByTestId('desktop-sidebar')).toBeVisible();
		await expect(page.getByTestId('bottom-nav')).not.toBeVisible();
	});

	// ─── AC-7: Desktop-Sidebar hat 4 Items (inkl. Locations) ────────────────
	test('AC-7: Desktop-Sidebar zeigt 4 Nav-Items inkl. Locations', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt, Desktop-Viewport
		 * WHEN:  Desktop-Sidebar gerendert
		 * THEN:  Sidebar zeigt Links zu /, /trips, /compare, /locations
		 */
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/');

		const sidebar = page.getByTestId('desktop-sidebar');
		await expect(sidebar.locator('a[href="/"]')).toBeVisible();
		await expect(sidebar.locator('a[href="/trips"]')).toBeVisible();
		await expect(sidebar.locator('a[href="/compare"]')).toBeVisible();
		await expect(sidebar.locator('a[href="/archiv"]')).toBeVisible();
	});

	// ─── Zusatz: BottomNav auf Tablets zwischen 768-899px ───────────────────
	test('Zusatz: BottomNav ist auch bei 850px (zwischen md und 900px) sichtbar', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt
		 * WHEN:  Viewport ist 850×1024 px (zwischen Tailwind md: und 900px)
		 * THEN:  BottomNav sichtbar, Desktop-Sidebar nicht sichtbar
		 *        (Zeigt dass 900px-Breakpoint korrekt, nicht 768px)
		 */
		await page.setViewportSize({ width: 850, height: 1024 });
		await page.goto('/');

		await expect(page.getByTestId('bottom-nav')).toBeVisible();
		await expect(page.getByTestId('desktop-sidebar')).not.toBeVisible();
	});
});
