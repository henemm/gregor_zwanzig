// E2E — Issue #293: Sidebar Wordmark "gregor.zwanzig"
//
// Spec: docs/specs/modules/issue_293_wordmark.md (AC-1 bis AC-8)
//       docs/specs/modules/issue_370_brand_library.md (§9 Test-Update)
//
// TDD RED (Issue #370): Diese Tests MÜSSEN FEHLSCHLAGEN, bis #370 die
// Brand-Bibliothek liefert. Das neue Soll:
//   - Caption ist UPPERCASE "V0.20 · WETTER-BRIEFING" (text-transform:uppercase
//     in BrandWordmark) statt lowercase "v0.20 · wetter-briefing".
//   - In Desktop-Sidebar UND auf der Login-Seite ist der Berg+Blitz-Glyph
//     `data-testid="brand-icon"` (ein <svg>) sichtbar (Issue #279).
//   - Fragile Svelte-scoped CSS-Klassen (.wordmark__zwanzig / .wordmark__dot)
//     wurden durch Text-/testid-basierte Checks ersetzt.

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

const DESKTOP_VIEWPORT = { width: 1440, height: 900 };
const MOBILE_VIEWPORT  = { width: 375, height: 667 };

test.describe('Issue #293: Wordmark "gregor.zwanzig"', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// ─── AC-1: Desktop-Sidebar zeigt Wordmark mit Glyph + UPPERCASE-Untertitel ─
	test('AC-1: Desktop-Sidebar zeigt "gregor.zwanzig" mit Glyph + Untertitel', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt, Viewport ≥ 900px (Desktop)
		 * WHEN:  Startseite geladen wird
		 * THEN:  Sidebar enthält Link mit aria-label "Gregor Zwanzig — Home",
		 *        sichtbaren Berg+Blitz-Glyph (data-testid="brand-icon"),
		 *        Text "gregor" + "zwanzig"
		 *        und UPPERCASE-Untertitel "V0.20 · WETTER-BRIEFING".
		 */
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/');

		const sidebar = page.getByTestId('desktop-sidebar');
		const wordmark = sidebar.locator('a[aria-label="Gregor Zwanzig — Home"]');
		await expect(wordmark).toBeVisible();
		await expect(wordmark).toContainText('gregor');
		await expect(wordmark).toContainText('zwanzig');
		// Caption ist nun UPPERCASE (text-transform:uppercase in BrandWordmark).
		await expect(wordmark).toContainText('V0.20 · WETTER-BRIEFING');

		// Issue #279: Berg+Blitz-Glyph ist als <svg> in der Sidebar-Wordmark sichtbar.
		const glyph = wordmark.getByTestId('brand-icon');
		await expect(glyph).toBeVisible();
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

		// Untertitel darf im Mobile-Wordmark NICHT im DOM sein (size="sm").
		// Guard auf die tatsaechlich gerenderte UPPERCASE-Caption (#370): die
		// frueher gepruefte lowercase-Form existiert nie mehr → Assertion waere
		// trivial wahr und wuerde eine sm-Caption-Regression nicht erkennen.
		const subtitle = wordmark.locator('text=V0.20 · WETTER-BRIEFING');
		await expect(subtitle).toHaveCount(0);
	});

	// ─── AC-3: Wordmark zeigt Glyph + "zwanzig" in Accent-Farbe ──────────────
	test('AC-3: Berg+Blitz-Glyph sichtbar, "zwanzig" hat Accent-Farbe', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt, Desktop-Viewport
		 * WHEN:  Startseite geladen wird
		 * THEN:  Der Berg+Blitz-Glyph (data-testid="brand-icon") ist sichtbar
		 *        und der Text "zwanzig" hat computed color rgb(196, 90, 42) = --g-accent.
		 *
		 * Hinweis (#370): Die früheren scoped CSS-Klassen .wordmark__zwanzig /
		 * .wordmark__dot wurden entfernt — Svelte-scoped Klassen sind in E2E nicht
		 * stabil. Stattdessen testid-basierter Glyph-Check + Text-Span-Farbprüfung.
		 */
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/');

		// Sidebar-Wordmark explizit ansprechen (TopAppBar hat desktop:hidden, stört .first())
		const sidebar = page.getByTestId('desktop-sidebar');
		const wordmark = sidebar.locator('a[aria-label="Gregor Zwanzig — Home"]');

		// Berg+Blitz-Glyph als <svg> sichtbar.
		const glyph = wordmark.getByTestId('brand-icon');
		await expect(glyph).toBeVisible();

		// "zwanzig" wird als eigener Span mit Accent-Farbe gerendert.
		const zwanzig = wordmark.getByText('zwanzig', { exact: true });
		await expect(zwanzig).toBeVisible();
		const zwanzigColor = await zwanzig.evaluate((el) => window.getComputedStyle(el).color);
		// --g-accent = #c45a2a = rgb(196, 90, 42)
		expect(zwanzigColor).toBe('rgb(196, 90, 42)');
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

	// ─── AC-6: Login-Seite zeigt Wordmark mit Glyph statt Plain-H1 ───────────
	test('AC-6: Login-Seite zeigt Wordmark mit Glyph (kein h1 "Gregor 20")', async ({ page }) => {
		/**
		 * GIVEN: Unauthentifizierter User
		 * WHEN:  /login geladen wird
		 * THEN:  Seite enthält Link mit aria-label "Gregor Zwanzig — Home",
		 *        den sichtbaren Berg+Blitz-Glyph (data-testid="brand-icon", #279)
		 *        und KEIN <h1>-Element mit Text "Gregor 20"
		 */
		await page.goto('/login');

		const wordmark = page.locator('a[aria-label="Gregor Zwanzig — Home"]');
		await expect(wordmark).toBeVisible();

		// Issue #279: Glyph ist auch auf der Login-Seite sichtbar.
		const glyph = wordmark.getByTestId('brand-icon');
		await expect(glyph).toBeVisible();

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
