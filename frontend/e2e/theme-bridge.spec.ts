import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

/**
 * TDD RED Tests — Epic #133 Step 6 — Theme-Bridge (Issue #218)
 *
 * Diese Tests MÜSSEN vor der Implementierung ROT sein:
 * - `@theme {}` in `frontend/src/app.css` enthält noch hartcodierte `oklch()`-Werte
 * - Erwartet wird, dass `--color-*` nach Edit zu den `--g-*`-Werten auflöst
 */

test.describe('Epic #133 Step 6 — Theme-Bridge', () => {
	// Light-Mode sicherstellen, falls Auth-State Dark-Mode mitbringt
	test.beforeEach(async ({ page }) => {
		await page.addInitScript(() => localStorage.removeItem('gz-dark'));
		await login(page);
	});

	test('AC-1: --color-primary löst zu Ink-Schwarz auf (rgb(26, 26, 24))', async ({ page }) => {
		/**
		 * GIVEN: Light-Mode geladen, kein gz-dark in localStorage
		 * WHEN:  getComputedStyle(:root).getPropertyValue('--color-primary')
		 * THEN:  liefert exakt rgb(26, 26, 24) — den aufgelösten Wert von var(--g-ink)
		 */
		await page.goto('/');
		const value = await page.evaluate(() =>
			getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim()
		);
		expect(value).toBe('rgb(26, 26, 24)');
	});

	test('AC-2: --color-background löst zu Paper-Off-White auf (rgb(246, 244, 238))', async ({ page }) => {
		/**
		 * GIVEN: Light-Mode geladen
		 * WHEN:  getComputedStyle(:root).getPropertyValue('--color-background')
		 * THEN:  liefert exakt rgb(246, 244, 238) — Wert von var(--g-paper)
		 */
		await page.goto('/');
		const value = await page.evaluate(() =>
			getComputedStyle(document.documentElement).getPropertyValue('--color-background').trim()
		);
		expect(value).toBe('rgb(246, 244, 238)');
	});

	test('AC-3: --color-accent löst zu Burnt-Orange auf (rgb(196, 90, 42))', async ({ page }) => {
		/**
		 * GIVEN: Light-Mode geladen
		 * WHEN:  getComputedStyle(:root).getPropertyValue('--color-accent')
		 * THEN:  liefert exakt rgb(196, 90, 42) — Marken-Akzent var(--g-accent)
		 */
		await page.goto('/');
		const value = await page.evaluate(() =>
			getComputedStyle(document.documentElement).getPropertyValue('--color-accent').trim()
		);
		expect(value).toBe('rgb(196, 90, 42)');
	});

	test('AC-4: --color-destructive löst zu Danger-Rot auf (rgb(168, 50, 50))', async ({ page }) => {
		/**
		 * GIVEN: Light-Mode geladen
		 * WHEN:  getComputedStyle(:root).getPropertyValue('--color-destructive')
		 * THEN:  liefert exakt rgb(168, 50, 50) — Wert von var(--g-danger)
		 */
		await page.goto('/');
		const value = await page.evaluate(() =>
			getComputedStyle(document.documentElement).getPropertyValue('--color-destructive').trim()
		);
		expect(value).toBe('rgb(168, 50, 50)');
	});

	test('AC-5: Dark-Mode über data-theme — Gregor-Palette und Bridge werden dunkel (#2400)', async ({ page }) => {
		/**
		 * GIVEN: Dark-Mode via localStorage aktiviert
		 * WHEN:  Seite geladen (Kopf-Skript in app.html setzt den Modus vor dem ersten Paint)
		 * THEN:  <html data-theme="dark">, color-scheme dark, berechnetes --g-paper und
		 *        --color-background dunkel, KEIN Inline-Style-Override mehr (#2400, Spec AC-4/AC-5)
		 */
		await page.addInitScript(() => localStorage.setItem('gz-dark', '1'));
		await page.goto('/');
		const z = await page.evaluate(() => {
			const html = document.documentElement;
			const cs = getComputedStyle(html);
			return {
				theme: html.getAttribute('data-theme'),
				colorScheme: cs.colorScheme,
				paper: cs.getPropertyValue('--g-paper').trim().toLowerCase(),
				background: cs.getPropertyValue('--color-background').trim(),
				inline: html.style.getPropertyValue('--color-background'),
				body: getComputedStyle(document.body).backgroundColor
			};
		});
		expect(z.theme).toBe('dark');
		expect(z.colorScheme).toBe('dark');
		expect(z.paper).not.toBe('#f6f4ee');
		expect(z.background).not.toBe('rgb(246, 244, 238)');
		expect(z.inline, 'Inline-Style-Override (darkVars) muss entfallen').toBe('');
		const [r, g, b] = (z.body.match(/[\d.]+/g) ?? []).map(Number);
		expect(Math.max(r, g, b), `Seitengrund nicht dunkel: ${z.body}`).toBeLessThan(60);
	});
});
