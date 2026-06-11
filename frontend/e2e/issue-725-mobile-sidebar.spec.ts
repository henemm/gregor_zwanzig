// E2E — Issue #725: Trip-Detail Mobile — Sidebar bleibt sichtbar (aside.hidden rendert display:flex)
//
// Spec: docs/specs/bugfix/bug725_trip_detail_mobile_sidebar.md (AC-1 bis AC-3)
//
// Root Cause: Der Desktop-<aside> in Sidebar.svelte trägt im Inline-style ein
// `display: flex`, das die Tailwind-Klasse `.hidden` (display:none) per Spezifität
// überschreibt → Sidebar bleibt auf Mobile mit 220px sichtbar, <main> schrumpft.
//
// Härtere Assertion als der bestehende mobile-bottom-nav AC-1b (`not.toBeVisible()`):
// hier wird die tatsächliche getBoundingClientRect().width geprüft — genau der
// im Issue dokumentierte Messwert (220 vor Fix, 0 nach Fix).
//
// RED vor Fix:  aside.width === 220 @375px  → FAIL
// GREEN nach Fix: aside.width === 0 @375px   → PASS

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

const MOBILE = { width: 375, height: 812 };
const DESKTOP = { width: 1280, height: 800 };

test.describe('Issue #725: Mobile-Sidebar', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// ─── AC-1: Sidebar auf Mobile ausgeblendet, main volle Breite ────────────
	test('AC-1: Desktop-Sidebar @375px hat Breite 0, main nutzt volle Breite', async ({ page }) => {
		/**
		 * GIVEN: eingeloggter Nutzer, Viewport 375×812
		 * WHEN:  eine App-Seite mit globaler Sidebar geladen ist
		 * THEN:  aside[data-testid="desktop-sidebar"] width === 0, main width > 320
		 */
		await page.setViewportSize(MOBILE);
		await page.goto('/trips');

		const asideWidth = await page.evaluate(() => {
			const el = document.querySelector('aside[data-testid="desktop-sidebar"]');
			return el ? el.getBoundingClientRect().width : -1;
		});
		const mainWidth = await page.evaluate(() => {
			const el = document.querySelector('main');
			return el ? el.getBoundingClientRect().width : -1;
		});

		expect(asideWidth).toBe(0);
		expect(mainWidth).toBeGreaterThan(320);
	});

	// ─── AC-2: Desktop unverändert (Regression-Schutz) ──────────────────────
	test('AC-2: Desktop-Sidebar @1280px bleibt 220px sichtbar', async ({ page }) => {
		/**
		 * GIVEN: eingeloggter Nutzer, Viewport 1280×800
		 * WHEN:  eine App-Seite geladen ist
		 * THEN:  aside-Breite == 220 (Desktop unverändert)
		 */
		await page.setViewportSize(DESKTOP);
		await page.goto('/trips');

		const asideWidth = await page.evaluate(() => {
			const el = document.querySelector('aside[data-testid="desktop-sidebar"]');
			return el ? el.getBoundingClientRect().width : -1;
		});

		expect(asideWidth).toBe(220);
	});

	// ─── AC-3: Mobile-Drawer bleibt funktionsfähig ──────────────────────────
	test('AC-3: Mobile-Menü-Drawer öffnet @375px korrekt', async ({ page }) => {
		/**
		 * GIVEN: eingeloggter Nutzer, Viewport 375×812
		 * WHEN:  der Hamburger-Button (top-app-bar-hamburger) geklickt wird
		 * THEN:  der separate Mobile-Drawer wird sichtbar
		 *        (Fix am Desktop-<aside> beeinträchtigt den Drawer nicht)
		 */
		await page.setViewportSize(MOBILE);
		await page.goto('/trips');

		await page.getByTestId('top-app-bar-hamburger').click();

		// Der Mobile-Drawer ist der mobileMenuOpen-Block in Sidebar.svelte
		const drawer = page.getByTestId('mobile-drawer');
		await expect(drawer).toBeVisible();
	});
});
