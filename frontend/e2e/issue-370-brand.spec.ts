// E2E — Issue #370: Brand-Bibliothek `lib/brand/` (Berg+Blitz-Glyph + Wordmark-Lockup)
//
// Spec: docs/specs/modules/issue_370_brand_library.md (AC-1 bis AC-8)
// Epic: #368 Atomic-Design-Migration; schliesst zugleich #279 (Sidebar-Glyph).
//
// TDD RED: Diese Tests MÜSSEN FEHLSCHLAGEN, weil weder die Brand-Komponenten
// (frontend/src/lib/brand/) noch der Berg+Blitz-Glyph existieren und die
// Showcase-Route /_design die Brand-Demo-Container noch nicht enthält.
//
// KEINE Mocks (Projekt-Regel). Echte E2E gegen den Preview-Build.

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

const DESKTOP_VIEWPORT = { width: 1440, height: 900 };

// Byte-genaue SVG-Pfad-`d`-Attribute aus brand-kit.jsx (Spec §AC-2).
const D_BLITZ = 'M48 11 L41 23 L45 23 L43 29 L50 17 L46 17 Z';
const D_BERGKAMM = 'M3 54 L18 22 L29 38 L38 26 L52 50 L61 54 Z';

test.describe('Issue #370 — Brand-Bibliothek lib/brand/', () => {
	// ─── AC-5 (Kern, #279): Sidebar zeigt Glyph, Wordmark navigiert zu / ─────
	test('AC-5: Desktop-Sidebar zeigt brand-icon, Wordmark navigiert zu /', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt, Viewport ≥ 900px (Desktop)
		 * WHEN:  Eine beliebige App-Route (hier /) geladen wird
		 * THEN:  In der Desktop-Sidebar ist der Berg+Blitz-Glyph
		 *        (data-testid="brand-icon") sichtbar (#279 erledigt),
		 *        und ein Klick auf a[aria-label="Gregor Zwanzig — Home"]
		 *        navigiert zu /.
		 */
		await login(page);
		await page.setViewportSize(DESKTOP_VIEWPORT);
		await page.goto('/trips');

		const glyph = page.locator('[data-testid="desktop-sidebar"] [data-testid="brand-icon"]');
		await expect(glyph).toBeVisible();

		const wordmark = page
			.getByTestId('desktop-sidebar')
			.locator('a[aria-label="Gregor Zwanzig — Home"]');
		await expect(wordmark).toBeVisible();
		await wordmark.click();
		await expect(page).toHaveURL('/');
	});

	// ─── AC-1: BrandWordmark (Default icon="left") = Glyph + gregor.zwanzig ──
	test('AC-1: brand-wordmark enthält brand-icon + Text gregor/zwanzig', async ({ page }) => {
		/**
		 * GIVEN: BrandWordmark mit icon="left" (Default) im Showcase
		 * WHEN:  /_design geladen wird
		 * THEN:  data-testid="brand-wordmark" ist vorhanden, enthält ein
		 *        sichtbares Kind data-testid="brand-icon" und den Text
		 *        "gregor" sowie "zwanzig".
		 */
		await page.goto('/_design');

		const wordmark = page.getByTestId('brand-wordmark').first();
		await expect(wordmark).toBeVisible();

		const glyph = wordmark.getByTestId('brand-icon');
		await expect(glyph).toBeVisible();

		await expect(wordmark).toContainText('gregor');
		await expect(wordmark).toContainText('zwanzig');
	});

	// ─── AC-2: Glyph-SVG enthält byte-genau die zwei Brand-Pfade ─────────────
	test('AC-2: brand-icon SVG enthält byte-genaue Blitz- und Bergkamm-Pfade', async ({ page }) => {
		/**
		 * GIVEN: BrandIcon (via brand-wordmark) im Showcase
		 * WHEN:  Der SVG-Quelltext inspiziert wird
		 * THEN:  Zwei <path> mit exakt den d-Attributen aus brand-kit.jsx —
		 *        der Blitz (D_BLITZ) und der Bergkamm (D_BERGKAMM).
		 */
		await page.goto('/_design');

		const icon = page.getByTestId('brand-icon').first();
		await expect(icon).toBeVisible();

		// Alle d-Attribute der path-Elemente aus dem DOM lesen.
		const dValues = await icon.locator('path').evaluateAll((paths) =>
			paths.map((p) => p.getAttribute('d'))
		);

		// Byte-genauer Vergleich (keine andere Geometrie zulässig).
		expect(dValues).toContain(D_BLITZ);
		expect(dValues).toContain(D_BERGKAMM);
	});

	// ─── AC-3: icon="only" → nur Glyph, kein gregor/zwanzig-Text ─────────────
	test('AC-3: icon="only" rendert nur brand-icon, keinen Wortmark-Text', async ({ page }) => {
		/**
		 * GIVEN: BrandWordmark mit icon="only" im Showcase-Container
		 *        data-testid="brand-demo-icon-only"
		 * WHEN:  /_design geladen wird
		 * THEN:  Der Container enthält data-testid="brand-icon" (sichtbar),
		 *        aber KEINEN Text-Node "gregor" oder "zwanzig".
		 */
		await page.goto('/_design');

		const demo = page.getByTestId('brand-demo-icon-only');
		await expect(demo).toBeVisible();

		await expect(demo.getByTestId('brand-icon')).toBeVisible();
		await expect(demo).not.toContainText('gregor');
		await expect(demo).not.toContainText('zwanzig');
	});

	// ─── AC-4: icon="none" → kein Glyph (caption=null → keine Caption) ───────
	test('AC-4: icon="none" rendert keinen brand-icon', async ({ page }) => {
		/**
		 * GIVEN: BrandWordmark mit icon="none" (und caption={null}) im Container
		 *        data-testid="brand-demo-icon-none"
		 * WHEN:  /_design geladen wird
		 * THEN:  Der Container enthält KEIN data-testid="brand-icon",
		 *        zeigt aber weiterhin den Wortmark-Text "gregor".
		 */
		await page.goto('/_design');

		const demo = page.getByTestId('brand-demo-icon-none');
		await expect(demo).toBeVisible();

		await expect(demo.getByTestId('brand-icon')).toHaveCount(0);
		// Typo-Block bleibt erhalten (nur Icon weggelassen).
		await expect(demo).toContainText('gregor');
	});

	// ─── AC-7: dark={true} → Haupt-Text in --g-paper-Farbe ───────────────────
	test('AC-7: dark={true} rendert Haupt-Text in heller Paper-Farbe', async ({ page }) => {
		/**
		 * GIVEN: BrandWordmark mit dark={true} im Container
		 *        data-testid="brand-demo-dark"
		 * WHEN:  /_design geladen wird
		 * THEN:  Der "gregor"-Haupt-Text hat eine helle computed color
		 *        (--g-paper = rgb(246, 244, 238)), nicht den dunklen Ink-Wert.
		 */
		await page.goto('/_design');

		const demo = page.getByTestId('brand-demo-dark');
		await expect(demo).toBeVisible();

		const gregor = demo.getByText('gregor', { exact: true });
		await expect(gregor).toBeVisible();
		const color = await gregor.evaluate((el) => window.getComputedStyle(el).color);
		// --g-paper = #f6f4ee = rgb(246, 244, 238)
		expect(color).toBe('rgb(246, 244, 238)');
	});

	// ─── AC-8: unbekannte Props → Fallback md/left, kein Laufzeit-Fehler ─────
	test('AC-8: unbekannte size/icon fallen auf md/left zurück (Glyph rendert)', async ({ page }) => {
		/**
		 * GIVEN: BrandWordmark mit unbekanntem size (z.B. "xl") und unbekanntem
		 *        icon (z.B. "bottom") im Container data-testid="brand-demo-fallback"
		 * WHEN:  /_design geladen wird
		 * THEN:  Die Komponente fällt auf size="md" / icon="left" zurück:
		 *        Glyph (brand-icon) ist sichtbar UND Text "gregor" vorhanden,
		 *        ohne Laufzeit-Fehler.
		 */
		const pageErrors: string[] = [];
		page.on('pageerror', (err) => pageErrors.push(err.message));

		await page.goto('/_design');

		const demo = page.getByTestId('brand-demo-fallback');
		await expect(demo).toBeVisible();

		// icon="left"-Fallback → Glyph sichtbar + Typo-Block vorhanden.
		await expect(demo.getByTestId('brand-icon')).toBeVisible();
		await expect(demo).toContainText('gregor');

		// Keine Laufzeit-Fehler durch unbekannte Props.
		expect(pageErrors).toEqual([]);
	});
});
