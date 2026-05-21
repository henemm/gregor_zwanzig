// E2E — Issue #293: Sidebar Wordmark "gregor.zwanzig"
//
// Spec: docs/specs/modules/issue_293_wordmark.md (AC-1 bis AC-8)
//
// TDD RED: Diese Tests MÜSSEN FEHLSCHLAGEN, weil Wordmark.svelte noch nicht
// existiert und alle Stellen noch den Plaintext "Gregor 20" zeigen.

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

const DESKTOP_VIEWPORT = { width: 1440, height: 900 };
const MOBILE_VIEWPORT  = { width: 375, height: 667 };

test.describe('Issue #293: Wordmark "gregor.zwanzig"', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// ─── AC-1: Desktop-Sidebar zeigt Wordmark mit Untertitel ─────────────────
	test('AC-1: Desktop-Sidebar zeigt "gregor.zwanzig" mit Untertitel', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt, Viewport ≥ 900px (Desktop)
		 * WHEN:  Startseite geladen wird
		 * THEN:  Sidebar enthält Link mit aria-label "Gregor Zwanzig — Home"
		 *        und sichtbaren Text "gregor" sowie "zwanzig"
		 *        und Untertitel "v0.20 · wetter-briefing"
		 */
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/');

		const sidebar = page.getByTestId('desktop-sidebar');
		const wordmark = sidebar.locator('a[aria-label="Gregor Zwanzig — Home"]');
		await expect(wordmark).toBeVisible();
		await expect(wordmark).toContainText('gregor');
		await expect(wordmark).toContainText('zwanzig');
		await expect(wordmark).toContainText('v0.20 · wetter-briefing');
	});

	// ─── AC-2: Mobile TopAppBar zeigt kompaktes Wordmark ohne Untertitel ─────
	test('AC-2: Mobile TopAppBar zeigt Wordmark ohne Untertitel', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt, Viewport < 900px (Mobile)
		 * WHEN:  Startseite geladen wird
		 * THEN:  TopAppBar enthält Link mit aria-label "Gregor Zwanzig — Home"
		 *        aber KEINEN Untertitel "v0.20 · wetter-briefing"
		 */
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/');

		const topBar = page.getByTestId('top-app-bar');
		const wordmark = topBar.locator('a[aria-label="Gregor Zwanzig — Home"]');
		await expect(wordmark).toBeVisible();
		await expect(wordmark).toContainText('gregor');
		await expect(wordmark).toContainText('zwanzig');

		// Untertitel darf im Mobile-Wordmark NICHT im DOM sein (size="sm")
		const subtitle = wordmark.locator('text=v0.20 · wetter-briefing');
		await expect(subtitle).toHaveCount(0);
	});

	// ─── AC-3: Wordmark-Farben entsprechen Design-Tokens ─────────────────────
	test('AC-3: "zwanzig" hat Accent-Farbe, Punkt hat Ink-Faint-Farbe', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt, Desktop-Viewport
		 * WHEN:  Startseite geladen wird
		 * THEN:  ".wordmark__zwanzig" hat computed color rgb(196, 90, 42) = --g-accent
		 *        ".wordmark__dot"     hat computed color rgb(156, 154, 144) = --g-ink-faint
		 */
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/');

		// Sidebar-Wordmark explizit ansprechen (TopAppBar hat desktop:hidden, stört .first())
		const sidebar = page.getByTestId('desktop-sidebar');
		const zwanzig = sidebar.locator('.wordmark__zwanzig');
		const dot     = sidebar.locator('.wordmark__dot');

		await expect(zwanzig).toBeVisible();
		await expect(dot).toBeVisible();

		const zwanzigColor = await zwanzig.evaluate(
			(el) => window.getComputedStyle(el).color
		);
		const dotColor = await dot.evaluate(
			(el) => window.getComputedStyle(el).color
		);

		// --g-accent = #c45a2a = rgb(196, 90, 42)
		expect(zwanzigColor).toBe('rgb(196, 90, 42)');
		// --g-ink-faint = #9c9a90 = rgb(156, 154, 144)
		expect(dotColor).toBe('rgb(156, 154, 144)');
	});

	// ─── AC-4: Klick auf Wordmark navigiert zur Startseite ───────────────────
	test('AC-4: Klick auf Wordmark navigiert zu /', async ({ page }) => {
		/**
		 * GIVEN: User ist auf /trips
		 * WHEN:  User klickt auf das Wordmark in der Sidebar
		 * THEN:  Browser navigiert zu /
		 */
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/trips');

		// Sidebar-Wordmark (Desktop-Sidebar ist sichtbar, TopAppBar hat desktop:hidden)
		const wordmark = page.getByTestId('desktop-sidebar').locator('a[aria-label="Gregor Zwanzig — Home"]');
		await expect(wordmark).toBeVisible();
		await wordmark.click();
		await expect(page).toHaveURL('/');
	});

	// ─── AC-5: Dokumenttitel ist "Gregor Zwanzig" ────────────────────────────
	test('AC-5: Dokumenttitel lautet "Gregor Zwanzig"', async ({ page }) => {
		/**
		 * GIVEN: App geöffnet
		 * WHEN:  Startseite geladen wird
		 * THEN:  Browser-Tab-Titel enthält "Gregor Zwanzig" (nicht "Gregor 20")
		 */
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/');

		await expect(page).toHaveTitle(/Gregor Zwanzig/);
	});

	// ─── AC-6: Login-Seite zeigt Wordmark statt Plain-H1 ─────────────────────
	test('AC-6: Login-Seite zeigt Wordmark (kein h1 "Gregor 20")', async ({ page }) => {
		/**
		 * GIVEN: Unauthentifizierter User
		 * WHEN:  /login geladen wird
		 * THEN:  Seite enthält Link mit aria-label "Gregor Zwanzig — Home"
		 *        und KEIN <h1>-Element mit Text "Gregor 20"
		 */
		await page.goto('/login');

		const wordmark = page.locator('a[aria-label="Gregor Zwanzig — Home"]');
		await expect(wordmark).toBeVisible();

		// Kein Plain-h1 "Gregor 20" mehr
		const oldH1 = page.locator('h1', { hasText: 'Gregor 20' });
		await expect(oldH1).toHaveCount(0);
	});

	// ─── AC-7: Trip-Detail-Titel enthält "Gregor Zwanzig" ────────────────────
	test('AC-7: Trip-Detail-Seitentitel enthält "Gregor Zwanzig"', async ({ page }) => {
		/**
		 * GIVEN: Ein Trip namens "E2E Cockpit Test Trip" existiert (Seed im Setup)
		 * WHEN:  Trip-Detail-Seite geladen wird
		 * THEN:  Dokumenttitel lautet "<Trip-Name> — Gregor Zwanzig"
		 */
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/trips/e2e-cockpit-test');

		await expect(page).toHaveTitle(/— Gregor Zwanzig$/);
	});

	// ─── AC-8: Kein hartcodiertes "Gregor 20" in der UI ──────────────────────
	test('AC-8: Kein sichtbarer Text "Gregor 20" in Sidebar oder TopAppBar', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt, Desktop-Viewport
		 * WHEN:  Startseite geladen wird
		 * THEN:  Sidebar und TopAppBar enthalten KEINEN Text "Gregor 20"
		 */
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/');

		const sidebar = page.getByTestId('desktop-sidebar');
		await expect(sidebar).not.toContainText('Gregor 20');
	});
});
