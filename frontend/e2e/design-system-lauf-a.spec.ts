import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

/**
 * TDD RED Tests — Epic #133 Lauf A
 * Issues #141 (CSS-Tokens) und #142 (Schriften)
 *
 * Diese Tests MÜSSEN vor der Implementierung ROT sein:
 * - --g-* CSS-Tokens existieren noch nicht
 * - Inter Tight ist noch nicht eingebunden
 */

test.describe('Issue #141: Design-Tokens (--g-*)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('--g-accent ist als CSS Custom Property in :root definiert', async ({ page }) => {
		/**
		 * GIVEN: App ist geladen
		 * WHEN: CSS Custom Properties von :root werden ausgelesen
		 * THEN: --g-accent ist definiert und nicht leer
		 */
		await page.goto('/');
		const value = await page.evaluate(() =>
			getComputedStyle(document.documentElement).getPropertyValue('--g-accent').trim()
		);
		expect(value).not.toBe('');
		expect(value).toBe('#c45a2a');
	});

	test('--g-paper ist als CSS Custom Property in :root definiert', async ({ page }) => {
		/**
		 * GIVEN: App ist geladen
		 * WHEN: CSS Custom Properties von :root werden ausgelesen
		 * THEN: --g-paper ist definiert
		 */
		await page.goto('/');
		const value = await page.evaluate(() =>
			getComputedStyle(document.documentElement).getPropertyValue('--g-paper').trim()
		);
		expect(value).not.toBe('');
		expect(value).toBe('#f6f4ee');
	});

	test('--g-ink ist als CSS Custom Property in :root definiert', async ({ page }) => {
		/**
		 * GIVEN: App ist geladen
		 * WHEN: CSS Custom Properties von :root werden ausgelesen
		 * THEN: --g-ink ist definiert
		 */
		await page.goto('/');
		const value = await page.evaluate(() =>
			getComputedStyle(document.documentElement).getPropertyValue('--g-ink').trim()
		);
		expect(value).not.toBe('');
		expect(value).toBe('#1a1a18');
	});

	test('Wetter-Token --g-wx-rain ist definiert', async ({ page }) => {
		/**
		 * GIVEN: App ist geladen
		 * WHEN: CSS Custom Properties von :root werden ausgelesen
		 * THEN: --g-wx-rain ist definiert (repräsentativ für alle 6 Wetter-Tokens)
		 */
		await page.goto('/');
		const value = await page.evaluate(() =>
			getComputedStyle(document.documentElement).getPropertyValue('--g-wx-rain').trim()
		);
		expect(value).not.toBe('');
	});

	test('Elevation-Token --g-elev-1 ist definiert', async ({ page }) => {
		/**
		 * GIVEN: App ist geladen
		 * WHEN: CSS Custom Properties von :root werden ausgelesen
		 * THEN: --g-elev-1 ist definiert (repräsentativ für alle 3 Elevation-Tokens)
		 */
		await page.goto('/');
		const value = await page.evaluate(() =>
			getComputedStyle(document.documentElement).getPropertyValue('--g-elev-1').trim()
		);
		expect(value).not.toBe('');
	});

	test('--g-font-ui ist definiert und enthält Inter Tight', async ({ page }) => {
		/**
		 * GIVEN: App ist geladen
		 * WHEN: --g-font-ui CSS-Property ausgelesen wird
		 * THEN: Wert enthält 'Inter Tight'
		 */
		await page.goto('/');
		const value = await page.evaluate(() =>
			getComputedStyle(document.documentElement).getPropertyValue('--g-font-ui').trim()
		);
		expect(value).toContain('Inter Tight');
	});
});

test.describe('Issue #142: Schriften (Inter Tight + JetBrains Mono)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('body verwendet Inter Tight als Schriftart', async ({ page }) => {
		/**
		 * GIVEN: App ist geladen und Inter Tight ist eingebunden
		 * WHEN: Computed font-family des body-Elements ausgelesen wird
		 * THEN: font-family enthält 'Inter Tight'
		 */
		await page.goto('/');
		const fontFamily = await page.evaluate(() =>
			getComputedStyle(document.body).fontFamily
		);
		expect(fontFamily).toContain('Inter Tight');
	});

	test('Google Fonts Stylesheet ist im HTML-Head eingebunden', async ({ page }) => {
		/**
		 * GIVEN: App-HTML wird geladen
		 * WHEN: <link>-Tags im <head> geprüft werden
		 * THEN: Ein Link zu fonts.googleapis.com mit Inter+Tight und JetBrains+Mono existiert
		 */
		await page.goto('/');
		const fontLink = await page.locator('link[href*="fonts.googleapis.com"]').first();
		await expect(fontLink).toHaveCount(1);
		const href = await fontLink.getAttribute('href');
		expect(href).toContain('Inter+Tight');
		expect(href).toContain('JetBrains+Mono');
	});
});
