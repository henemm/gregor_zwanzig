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

	test('beide Schriftfamilien sind eingebunden — vom eigenen Host, nicht von Google', async ({
		page
	}) => {
		/**
		 * GIVEN: App-HTML wird geladen
		 * WHEN: die eingebundenen Schriftfamilien geprüft werden
		 * THEN: Inter Tight und JetBrains Mono sind verfügbar und kommen aus dem
		 *       eigenen /fonts-Verzeichnis
		 *
		 * Die Zusicherung ist unverändert („beide Familien sind eingebunden"), der
		 * MESSPUNKT ist mit Issue #2128 gewandert: früher ein <link> auf
		 * fonts.googleapis.com, jetzt @font-face vom eigenen Host (PWA-Fähigkeit
		 * ohne Netz, kein Fremdaufruf). Deshalb wird geprüft, was der Browser
		 * tatsächlich als Schriftfamilie führt — und dass die Dateien wirklich
		 * ausgeliefert werden.
		 */
		await page.goto('/');
		await expect(page.locator('link[href*="fonts.googleapis.com"]')).toHaveCount(0);

		const familien = await page.evaluate(() => {
			const out: string[] = [];
			document.fonts.forEach((f) => out.push(f.family.replace(/["']/g, '')));
			return out;
		});
		expect(familien).toContain('Inter Tight');
		expect(familien).toContain('JetBrains Mono');

		for (const datei of ['/fonts/inter-tight-latin.woff2', '/fonts/jetbrains-mono-latin.woff2']) {
			expect((await page.request.get(datei)).status(), `${datei} fehlt`).toBe(200);
		}
	});
});
