// E2E — Schwebende Tabbar im iOS-27-Stil (Mobile-Shell)
//
// Konzept: docs/design-requests/mobile_shell_ohne_topbar.md (Scheibe S1)
// Soll-Bild: Design-Canvas „Gregor Mobile Shell", Artboard „TabBar".
//
// Prueft die Zusicherungen dort, wo sie wirken: am gerenderten Element im
// Mobile-Viewport (Bounding-Box + Computed Style), nicht am Quelltext.
//
// TestID-Inventar (bestehend, unveraendert seit #267):
//   bottom-nav, bottom-nav-item-{home,trips,compare,archive}

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

const MOBILE_VIEWPORT = { width: 375, height: 667 };
const SIDE_INSET_PX = 16; // --g-nav-inset
const NAV_HEIGHT_PX = 64; // --g-nav-h
const NAV_GAP_PX = 6; // --g-nav-gap
const KONTO_PX = 64; // Konto-Kreis (S2): --g-nav-h breit, rechts neben der Leiste
const KONTO_GAP_PX = 10; // --g-nav-konto-gap

test.describe('Mobile-Shell: schwebende Tabbar', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.setViewportSize(MOBILE_VIEWPORT);
		await page.goto('/');
		await expect(page.getByTestId('bottom-nav')).toBeVisible();
	});

	test('AC-1: Leiste schwebt — seitlicher Rand und Abstand zur Unterkante', async ({ page }) => {
		/**
		 * GIVEN: Mobile-Viewport 375 px
		 * WHEN:  Uebersicht geladen
		 * THEN:  Der Rahmen (Leiste + Konto-Kreis, S2) ist fixed, beginnt 16 px vom
		 *        linken Rand, endet 16 px vor dem rechten Rand; die Leiste selbst
		 *        endet vor Konto-Kreis + Luft, und die Unterkante liegt 6 px ueber
		 *        der Viewport-Unterkante (Safe-Area im Desktop-Browser = 0)
		 */
		const shell = page.getByTestId('bottom-shell');
		const nav = page.getByTestId('bottom-nav');
		const shellBox = await shell.boundingBox();
		const box = await nav.boundingBox();
		expect(shellBox).not.toBeNull();
		expect(box).not.toBeNull();
		const position = await shell.evaluate((el) => getComputedStyle(el).position);
		expect(position).toBe('fixed');
		expect(Math.round(shellBox!.x)).toBe(SIDE_INSET_PX);
		expect(Math.round(shellBox!.x + shellBox!.width)).toBe(MOBILE_VIEWPORT.width - SIDE_INSET_PX);
		expect(Math.round(box!.x)).toBe(SIDE_INSET_PX);
		expect(Math.round(box!.x + box!.width)).toBe(MOBILE_VIEWPORT.width - SIDE_INSET_PX - KONTO_PX - KONTO_GAP_PX);
		expect(Math.round(box!.height)).toBe(NAV_HEIGHT_PX);
		expect(Math.round(MOBILE_VIEWPORT.height - (box!.y + box!.height))).toBe(NAV_GAP_PX);
	});

	test('AC-2: Leiste ist eine Glas-Kapsel — Blur, Hairline, runde Enden', async ({ page }) => {
		/**
		 * GIVEN: Mobile-Viewport
		 * WHEN:  Leiste gerendert
		 * THEN:  backdrop-filter enthaelt blur, Hintergrund ist halbtransparent
		 *        (Alpha < 1), Radius >= halbe Hoehe, 1 px Rahmen
		 */
		const nav = page.getByTestId('bottom-nav');
		const style = await nav.evaluate((el) => {
			const cs = getComputedStyle(el);
			return {
				backdrop: cs.backdropFilter || (cs as unknown as { webkitBackdropFilter: string }).webkitBackdropFilter,
				background: cs.backgroundColor,
				radius: parseFloat(cs.borderTopLeftRadius),
				borderWidth: parseFloat(cs.borderTopWidth)
			};
		});
		expect(style.backdrop).toContain('blur');
		const alpha = style.background.match(/rgba?\([^)]*,\s*([\d.]+)\)$/);
		expect(alpha).not.toBeNull();
		expect(parseFloat(alpha![1])).toBeLessThan(1);
		expect(style.radius).toBeGreaterThanOrEqual(NAV_HEIGHT_PX / 2);
		expect(style.borderWidth).toBe(1);
	});

	test('AC-3: Vier gleich breite Ziele, jedes mindestens 44 px hoch', async ({ page }) => {
		/**
		 * GIVEN: Mobile-Viewport
		 * WHEN:  Leiste gerendert
		 * THEN:  4 Items, Breiten weichen hoechstens 1 px voneinander ab,
		 *        Hoehe >= 44 px (Touch-Ziel)
		 */
		const items = page.getByTestId('bottom-nav').locator('a');
		await expect(items).toHaveCount(4);
		const boxes = await items.evaluateAll((els) =>
			els.map((el) => {
				const r = el.getBoundingClientRect();
				return { w: r.width, h: r.height };
			})
		);
		const widths = boxes.map((b) => b.w);
		expect(Math.max(...widths) - Math.min(...widths)).toBeLessThanOrEqual(1);
		for (const b of boxes) expect(b.h).toBeGreaterThanOrEqual(44);
	});

	test('AC-4: Aktives Ziel traegt eine Kapsel, inaktive sind transparent', async ({ page }) => {
		/**
		 * GIVEN: Uebersicht (/) geladen
		 * WHEN:  Leiste gerendert
		 * THEN:  genau das Item mit aria-current="page" hat eine gefuellte
		 *        Kapsel (Alpha > 0), alle anderen keinen Hintergrund
		 */
		const items = page.getByTestId('bottom-nav').locator('a');
		const states = await items.evaluateAll((els) =>
			els.map((el) => ({
				current: el.getAttribute('aria-current') === 'page',
				background: getComputedStyle(el).backgroundColor
			}))
		);
		const isTransparent = (c: string) => c === 'rgba(0, 0, 0, 0)' || c === 'transparent';
		expect(states.filter((s) => s.current)).toHaveLength(1);
		for (const s of states) {
			if (s.current) expect(isTransparent(s.background)).toBe(false);
			else expect(isTransparent(s.background)).toBe(true);
		}
	});

	test('AC-5: Inhalt endet oberhalb der schwebenden Leiste', async ({ page }) => {
		/**
		 * GIVEN: Mobile-Viewport
		 * WHEN:  Uebersicht geladen
		 * THEN:  main reserviert unten mindestens Leistenhoehe + Abstand (72 px)
		 */
		const paddingBottom = await page
			.locator('main')
			.evaluate((el) => parseFloat(getComputedStyle(el).paddingBottom));
		expect(paddingBottom).toBeGreaterThanOrEqual(NAV_HEIGHT_PX + NAV_GAP_PX);
	});
});
