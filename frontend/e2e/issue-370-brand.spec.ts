// E2E — Issue #370: Brand-Bibliothek `lib/brand/` (Berg+Blitz-Glyph + Wordmark-Lockup)
//
// Spec: docs/specs/modules/issue_370_brand_library.md (AC-1 bis AC-8, Nummerierung
// dieser Datei) -- die drei Tests, die auf die Glyph-GEOMETRIE zielen, wurden fuer
// Issue #2341 (Spec docs/specs/modules/brand_icon_silhouette.md) umgeschrieben: die
// alte Kontur-Linie (stroke) ist einer gefuellten Silhouette (fill) gewichen, der
// Blitz ist 1,35x groesser. Referenzen auf "AC-N (Issue #2341)" in dieser Datei
// meinen die ACs der NEUEN Spec, nicht die Nummerierung dieser Datei.
// Epic: #368 Atomic-Design-Migration; schliesst zugleich #279 (Sidebar-Glyph).
//
// TDD RED (Issue #2341): Die Tests unten mit "(Issue #2341)" im Titel MÜSSEN
// FEHLSCHLAGEN, weil BrandIcon/BrandIconSquare noch die alte Kontur-Geometrie
// rendern (stroke statt fill, kein vergroesserter Blitz, Nebenkante/Horizont noch
// vorhanden). Diese Datei ist Teil der Live-E2E-Schicht (CLAUDE.md, "Zwei
// Schichten") -- lokal geschrieben, ausgefuehrt/verifiziert ueber den CI-e2e-Job
// bzw. /e2e-verify gegen Staging, nicht per lokalem Ad-hoc-Stack.
//
// KEINE Mocks (Projekt-Regel). Echte E2E gegen den Preview-Build.

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

const DESKTOP_VIEWPORT = { width: 1440, height: 900 };

// Alte Kontur-Geometrie (bis Issue #2341) -- bleibt hier als Referenz fuer den
// Vorher/Nachher-Vergleich in den umgeschriebenen Tests stehen.
const D_BLITZ = 'M48 11 L41 23 L45 23 L43 29 L50 17 L46 17 Z';
const D_BERGKAMM = 'M3 54 L18 22 L29 38 L38 26 L52 50 L61 54 Z';
const D_NEBENKANTE = 'M3 54 L18 22 L25 32';

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

	// ─── AC-1 (Issue #2341): Bergkamm ist Fill-Silhouette, Blitz 1,35x groesser ──
	test('AC-1 (Issue #2341): brand-icon zeigt Fill-Silhouette + vergroesserten Blitz', async ({ page }) => {
		/**
		 * GIVEN: BrandIcon (via brand-wordmark) im Showcase
		 * WHEN:  Der SVG-Quelltext inspiziert wird
		 * THEN:  Der Bergkamm-Pfad (D_BERGKAMM, geometrisch unveraendert) traegt
		 *        ein fill-Attribut und KEIN stroke-Attribut mehr (Silhouette statt
		 *        Kontur), und der Blitz-Pfad (D_BLITZ) sitzt in einer <g> mit
		 *        einem transform, der "scale(1.35)" enthaelt.
		 */
		await page.goto('/_design');

		const icon = page.getByTestId('brand-icon').first();
		await expect(icon).toBeVisible();

		const bergkamm = icon.locator(`path[d="${D_BERGKAMM}"]`);
		await expect(bergkamm).toHaveCount(1);
		await expect(bergkamm).toHaveAttribute('fill', /.+/);
		await expect(bergkamm).not.toHaveAttribute('stroke', /.+/);

		const blitzGroupTransform = await icon
			.locator(`g:has(path[d="${D_BLITZ}"])`)
			.first()
			.getAttribute('transform');
		expect(blitzGroupTransform ?? '').toContain('scale(1.35)');
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

	// ─── AC-2 (Issue #2341): BrandIconSquare ohne Nebenkante/Horizont ────────
	test('AC-2 (Issue #2341): brand-icon-square hat keine Nebenkante und keine Horizontlinie mehr', async ({ page }) => {
		/**
		 * GIVEN: BrandIconSquare (Groesse >=32px) im Showcase
		 * WHEN:  Das SVG-DOM inspiziert wird
		 * THEN:  Weder ein <path> mit D_NEBENKANTE noch ein <line>-Element mit
		 *        y1="58" existiert -- beide Zusatzelemente der alten Kontur-Optik
		 *        sind ersatzlos entfernt.
		 *
		 * BrandIconSquare wird laut docs/context/fix-2341-pwa-logo.md NUR im
		 * `_design-system`-Showcase eingebunden (nicht live im Produkt, auch
		 * nicht auf `/_design` -- dort gibt es nur BrandWordmark/BrandIcon).
		 * Korrektur nach CI-Fehlschlag: vorher stand hier faelschlich
		 * `/_design` (Copy-Paste aus den AC-1-Tests), obwohl der Kommentar
		 * direkt darunter schon immer die richtige Route nannte.
		 */
		await page.goto('/_design-system');

		// BrandIconSquare traegt keinen eigenen data-testid; die Panel-Caption
		// "Favicon · Avatar · App-Icon" (siehe _design-system/+page.svelte) ist
		// die stabile Verankerung fuer den umgebenden Container mit den vier
		// Groessen-Beispielen (>=32px zeigten bislang Nebenkante + Horizont).
		const panel = page.locator('div', { hasText: 'Favicon · Avatar · App-Icon' }).first();
		await expect(panel).toBeVisible();

		await expect(panel.locator(`path[d="${D_NEBENKANTE}"]`)).toHaveCount(0);
		await expect(panel.locator('line[y1="58"]')).toHaveCount(0);
	});

	// ─── AC-3 (Issue #2341): favicon.svg ist randfuellende Fill-Silhouette ───
	test('AC-3 (Issue #2341): favicon.svg zeigt eine durchgehend gefuellte Bergflaeche', async ({ page, baseURL }) => {
		/**
		 * GIVEN: /favicon.svg wird als <img> im Browser gerendert
		 * WHEN:  Ein Pixel INNERHALB der Bergkamm-Flaeche (Punkt (30,45) im
		 *        64x64-ViewBox, auf 256x256 hochskaliert) per Canvas ausgelesen wird
		 * THEN:  Der Pixel traegt durchgehend die Ink-Farbe (#1a1a18 = rgb(26,26,24)),
		 *        nicht die Hintergrundfarbe mit duenner Umrandung wie bei einer
		 *        Kontur-Linie -- echte Bildinhalts-Pruefung, kein SVG-Quelltext-Match.
		 *
		 * `page.setContent()` navigiert NICHT zur baseURL -- eine relative
		 * `src="/favicon.svg"` würde gegen `about:blank` aufgelöst und nie laden
		 * (CI-Fehlschlag: Pixel kam als [0,0,0] statt [26,26,24] zurück, weil das
		 * <img> gar nicht erst geladen hatte). Deshalb die absolute URL bauen.
		 */
		await page.setContent(`
			<img id="fav" src="${baseURL}/favicon.svg" width="256" height="256" />
			<canvas id="cv" width="256" height="256"></canvas>
		`);
		const img = page.locator('#fav');
		await expect(img).toBeVisible();

		const rgb = await page.evaluate(() => {
			const img = document.getElementById('fav') as HTMLImageElement;
			const canvas = document.getElementById('cv') as HTMLCanvasElement;
			const ctx = canvas.getContext('2d')!;
			ctx.drawImage(img, 0, 0, 256, 256);
			// Punkt (30,45) im 64x64-ViewBox -> Faktor 4 -> (120,180)
			const data = ctx.getImageData(120, 180, 1, 1).data;
			return [data[0], data[1], data[2]];
		});

		expect(rgb).toEqual([26, 26, 24]);
	});
});
