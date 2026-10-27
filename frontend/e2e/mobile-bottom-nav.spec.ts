// E2E — Issue #267: Mobile Bottom-Navigation
//
// Spec: docs/specs/modules/issue_267_mobile_bottom_nav.md (AC-1 bis AC-7)
//
// Mobile-Shell S2 (docs/design-requests/mobile_shell_ohne_topbar.md): kein
// fixer Balken oben mehr, kein Hamburger-Drawer. Konto/Abmelden liegen im
// Konto-Sheet, das der Konto-Kreis rechts neben der Tabbar oeffnet.
//
// TestID-Inventar:
//   bottom-nav                    — BottomNav-Container (schwebend, 64px)
//   bottom-nav-item-home          — Link zu /
//   bottom-nav-item-trips         — Link zu /trips
//   bottom-nav-item-compare       — Link zu /compare
//   bottom-nav-item-archive       — Link zu /archiv
//   konto-kreis                   — User-Badge neben der Tabbar (mobile only)
//   konto-sheet                   — Konto-Sheet (Konto · Status · Dunkel · Export · Abmelden)

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

const MOBILE_VIEWPORT = { width: 375, height: 667 };
const DESKTOP_VIEWPORT = { width: 1440, height: 900 };

test.describe('Issue #267: Mobile Bottom-Navigation', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// ─── AC-1: Konto-Kreis sichtbar auf Mobile, kein fixer Balken oben ──────
	test('AC-1: Konto-Kreis ist auf Mobile-Viewport sichtbar, kein Top-Balken (< 900px)', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt
		 * WHEN:  Viewport ist 375×667 px (Mobile)
		 * THEN:  Konto-Kreis (data-testid="konto-kreis") ist sichtbar,
		 *        ein fixer Balken oben (top-app-bar) existiert nicht mehr
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/');

		await expect(page.getByTestId('konto-kreis')).toBeVisible();
		await expect(page.getByTestId('top-app-bar')).toHaveCount(0);
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

	// ─── AC-4: Konto-Sheet zeigt nur sekundäre Items ────────────────────────
	test('AC-4: Konto-Sheet zeigt Konto und Logout, KEINE Workspace-Nav-Links', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt, Mobile-Viewport
		 * WHEN:  User tippt den Konto-Kreis neben der Tabbar
		 * THEN:  Konto-Sheet hat Einstellungen + Abmelden, KEINE Links zu /trips, /compare
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/');

		await page.getByTestId('konto-kreis').click();
		const sheet = page.getByTestId('konto-sheet');
		await expect(sheet).toBeVisible();

		// Sekundäre Items müssen vorhanden sein
		await expect(sheet.locator('a[href="/account"]')).toBeVisible();
		await expect(sheet.locator('button[type="submit"]').filter({ hasText: 'Abmelden' })).toBeVisible();

		// Workspace-Nav DARF NICHT im Sheet sein (die Links leben in der BottomNav)
		await expect(sheet.locator('a[href="/trips"]')).toHaveCount(0);
		await expect(sheet.locator('a[href="/compare"]')).toHaveCount(0);
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
		// `nav a` — die Wordmark der Sidebar verlinkt ebenfalls auf "/".
		await expect(sidebar.locator('nav a[href="/"]')).toBeVisible();
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
