// Issue #3319 / #3320 — oeffentliche Funktionsuebersicht und Startseite gegen STAGING.
// AC-2 (Link Startseite -> /funktionen), AC-4 (ohne Anmeldung, kein /api-Aufruf),
// AC-6 (Sprunganker, Sprachumschalter ohne Login), AC-8 (Bilder laden),
// AC-11 (375 px ohne horizontale Scrollleiste, Textkontrast WCAG-AA).
// Spec: docs/specs/modules/oeffentliche_doku_3319.md
//
// Aufruf (nach Staging-Deploy):
//   cd frontend/e2e && GZ_VALIDATOR_USER=... GZ_VALIDATOR_PASS=... \
//     npx playwright test funktionen-oeffentlich.staging.spec.ts
//
// GEHOERT NICHT in `.github/ci_e2e_specs.txt` (braucht Staging, Suffix `.staging.`).
import { test, expect, type Page } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';

const BASE = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
const ABSCHNITTE = [
	'cockpit', 'trip_anlegen', 'trip_hub', 'briefings', 'wetter', 'zustellung', 'alarme',
	'ortsvergleich', 'kanaele', 'befehle', 'archiv', 'konto', 'app', 'wetterdaten'
];

test.use({
	baseURL: BASE,
	ignoreHTTPSErrors: true,
	httpCredentials: {
		username: process.env.GZ_VALIDATOR_USER ?? '',
		password: process.env.GZ_VALIDATOR_PASS ?? ''
	},
	storageState: { cookies: [], origins: [] },
	viewport: { width: 375, height: 800 }
});

test.beforeAll(() => assertNotProdBaseURL(BASE));

/** Kleinster Kontrast Text/Hintergrund aller sichtbaren Textelemente (WCAG-Formel). */
async function kleinsterKontrast(page: Page): Promise<{ wert: number; wo: string }> {
	return page.evaluate(() => {
		const rgb = (s: string) => (s.match(/[\d.]+/g) ?? []).map(Number);
		const lum = ([r, g, b]: number[]) => {
			const k = (c: number) => ((c /= 255) <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
			return 0.2126 * k(r) + 0.7152 * k(g) + 0.0722 * k(b);
		};
		const grund = (el: Element | null): number[] => {
			for (let e = el; e; e = e.parentElement) {
				const c = rgb(getComputedStyle(e).backgroundColor);
				if (c.length >= 3 && (c.length < 4 || c[3] > 0.5)) return c.slice(0, 3);
			}
			return [255, 255, 255];
		};
		let min = { wert: 21, wo: '' };
		for (const el of Array.from(document.querySelectorAll('main *'))) {
			const eigenerText = Array.from(el.childNodes).some((n) => n.nodeType === 3 && n.textContent!.trim());
			const s = getComputedStyle(el);
			if (!eigenerText || s.visibility === 'hidden' || s.display === 'none') continue;
			const a = lum(rgb(s.color).slice(0, 3));
			const b = lum(grund(el));
			const k = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
			if (k < min.wert) min = { wert: k, wo: `${el.tagName}: ${el.textContent!.trim().slice(0, 40)}` };
		}
		return min;
	});
}

for (const lang of ['de', 'en']) {
	test(`AC-4/6/8/11 (${lang}): /funktionen ohne Anmeldung, Anker, Bilder, 375 px, Kontrast`, async ({ page, context }) => {
		await context.addCookies([{ name: 'gz_lang', value: lang, url: BASE }]);
		const apiAufrufe: string[] = [];
		page.on('request', (r) => {
			if (new URL(r.url()).pathname.startsWith('/api')) apiAufrufe.push(r.url());
		});
		const antwort = await page.goto('/funktionen');
		expect(antwort?.status()).toBe(200);
		await expect(page).toHaveURL(/\/funktionen$/);
		await expect(page.locator('html')).toHaveAttribute('lang', lang);
		for (const id of ABSCHNITTE) await expect(page.locator(`section#${id}`)).toHaveCount(1);
		await page.locator('[data-testid="inhaltsverzeichnis"] a[href="#alarme"]').click();
		await expect(page).toHaveURL(/#alarme$/);
		await expect(page.locator('[data-testid="level-tabelle"]')).toBeVisible();
		for (const img of await page.locator('[data-testid="funktionen"] img').all()) {
			await img.scrollIntoViewIfNeeded();
			await expect.poll(() => img.evaluate((i: HTMLImageElement) => i.naturalWidth)).toBeGreaterThan(0);
		}
		const breite = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
		expect(breite[0], 'horizontale Scrollleiste bei 375 px').toBeLessThanOrEqual(breite[1]);
		const k = await kleinsterKontrast(page);
		expect(k.wert, `Kontrast unter AA bei ${k.wo}`).toBeGreaterThanOrEqual(4.5);
		expect(apiAufrufe, 'Funktionsseite ruft die API').toEqual([]);
	});
}

test('AC-6: Sprachumschalter wechselt ohne Login', async ({ page }) => {
	await page.goto('/funktionen');
	const vorher = await page.locator('html').getAttribute('lang');
	await page.locator('[data-testid="sprach-umschalter"] button, [data-testid="sprach-umschalter"] a').filter({ hasText: vorher === 'en' ? /DE/ : /EN/ }).first().click();
	await expect(page).toHaveURL(/\/funktionen/);
	await expect(page.locator('html')).not.toHaveAttribute('lang', vorher ?? '');
});

test('AC-2/AC-11: Startseite 375 px ohne Scrollleiste, Level-Tabelle sichtbar, Link fuehrt zu /funktionen', async ({ page }) => {
	await page.goto('/');
	await expect(page.locator('[data-testid="level-tabelle"]')).toBeVisible();
	const breite = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
	expect(breite[0]).toBeLessThanOrEqual(breite[1]);
	const k = await kleinsterKontrast(page);
	expect(k.wert, `Kontrast unter AA bei ${k.wo}`).toBeGreaterThanOrEqual(4.5);
	await page.locator('a[href="/funktionen"]').first().click();
	await expect(page).toHaveURL(/\/funktionen$/);
});
