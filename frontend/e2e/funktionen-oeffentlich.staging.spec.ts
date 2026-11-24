// Issue #3319 / #3320 — oeffentliche Funktionsuebersicht (Uebersicht + neun Unterseiten)
// und Startseite gegen STAGING.
// AC-2 (Link Startseite -> /funktionen), AC-4 (alle zehn Funktions-Pfade ohne Anmeldung
// 200, kein /api-Aufruf), AC-6 (Kachel -> Unterseite, Sprachumschalter ohne Login),
// AC-8 (Bilder laden), AC-11 (375 px ohne horizontale Scrollleiste auf allen elf Seiten,
// Textkontrast WCAG-AA), AC-12 (Weiter-Kette von der ersten bis zur letzten Unterseite).
// Spec: docs/specs/modules/oeffentliche_doku_3319.md (v1.1)
//
// Aufruf (nach Staging-Deploy):
//   cd frontend/e2e && GZ_VALIDATOR_USER=... GZ_VALIDATOR_PASS=... \
//     npx playwright test funktionen-oeffentlich.staging.spec.ts
//
// GEHOERT NICHT in `.github/ci_e2e_specs.txt` (braucht Staging, Suffix `.staging.`).
import { test, expect, type Page } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import { FUNKTIONEN_SEITEN } from '../src/lib/funktionen_seiten';

const BASE = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
const SLUGS = FUNKTIONEN_SEITEN.map((s: { slug: string }) => s.slug);
const FUNKTIONS_PFADE = ['/funktionen', ...SLUGS.map((s: string) => `/funktionen/${s}`)];
const ALLE_SEITEN = ['/', ...FUNKTIONS_PFADE];

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

test('Messaufbau: neun Unterseiten, zehn Funktions-Pfade, elf Seiten', () => {
	expect(SLUGS).toEqual(['trips', 'briefings', 'alarme', 'ortsvergleich', 'kanaele', 'befehle', 'wetterdaten', 'konto', 'level']);
	expect(FUNKTIONS_PFADE).toHaveLength(10);
	expect(ALLE_SEITEN).toHaveLength(11);
});

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

async function keineScrollleiste(page: Page, pfad: string) {
	const [scroll, breite] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
	expect(scroll, `${pfad}: horizontale Scrollleiste bei 375 px`).toBeLessThanOrEqual(breite);
}

for (const lang of ['de', 'en']) {
	test(`AC-4/8/11 (${lang}): alle elf Seiten ohne Anmeldung 200, 375 px, Kontrast, Bilder, kein /api`, async ({ page, context }) => {
		await context.addCookies([{ name: 'gz_lang', value: lang, url: BASE }]);
		const apiAufrufe: string[] = [];
		page.on('request', (r) => {
			if (new URL(r.url()).pathname.startsWith('/api')) apiAufrufe.push(r.url());
		});
		for (const pfad of ALLE_SEITEN) {
			const antwort = await page.goto(pfad);
			expect(antwort?.status(), `${pfad} ohne Login`).toBe(200);
			expect(new URL(page.url()).pathname, `${pfad}: keine Weiterleitung`).toBe(pfad);
			await expect(page.locator('html')).toHaveAttribute('lang', lang);
			for (const img of await page.locator('main img').all()) {
				await img.scrollIntoViewIfNeeded();
				await expect.poll(() => img.evaluate((i: HTMLImageElement) => i.naturalWidth), { message: `${pfad}: Bild laedt nicht` }).toBeGreaterThan(0);
			}
			await keineScrollleiste(page, pfad);
			const k = await kleinsterKontrast(page);
			expect(k.wert, `${pfad}: Kontrast unter AA bei ${k.wo}`).toBeGreaterThanOrEqual(4.5);
			if (pfad.startsWith('/funktionen/')) {
				await expect(page.locator('[data-testid="themen-navigation"] a'), `${pfad}: Themen-Navigation`).toHaveCount(9);
			}
		}
		expect(apiAufrufe, 'Funktionsseiten rufen die API').toEqual([]);
	});
}

test('AC-12: Weiter-Kette von der ersten bis zur letzten Unterseite', async ({ page }) => {
	await page.goto(`/funktionen/${SLUGS[0]}`);
	await expect(page.locator('[data-testid="seite-zurueck"]')).toHaveCount(0);
	for (let i = 1; i < SLUGS.length; i++) {
		await page.locator('[data-testid="seite-weiter"]').click();
		await expect(page).toHaveURL(new RegExp(`/funktionen/${SLUGS[i]}$`));
		await expect(page.locator('[data-testid="themen-navigation"] a[aria-current="page"]')).toHaveAttribute('href', `/funktionen/${SLUGS[i]}`);
	}
	await expect(page.locator('[data-testid="seite-weiter"]')).toHaveCount(0);
});

test('AC-6: Kachel auf der Uebersicht fuehrt zur Unterseite, Brotkrumen zurueck', async ({ page }) => {
	await page.goto('/funktionen');
	await expect(page.locator('[data-testid="kachel"]')).toHaveCount(9);
	await page.locator('[data-testid="kachel"][href="/funktionen/alarme"]').click();
	await expect(page).toHaveURL(/\/funktionen\/alarme$/);
	await page.locator('[data-testid="brotkrumen"] a[href="/funktionen"]').click();
	await expect(page).toHaveURL(/\/funktionen$/);
});

test('AC-6: Sprachumschalter wechselt auf einer Unterseite ohne Login', async ({ page }) => {
	await page.goto('/funktionen/level');
	const vorher = await page.locator('html').getAttribute('lang');
	await page
		.locator('[data-testid="sprach-umschalter"] button, [data-testid="sprach-umschalter"] a')
		.filter({ hasText: vorher === 'en' ? /DE/ : /EN/ })
		.first()
		.click();
	await expect(page).toHaveURL(/\/funktionen\/level$/);
	await expect(page.locator('html')).not.toHaveAttribute('lang', vorher ?? '');
	await expect(page.locator('[data-testid="level-tabelle"]')).toBeVisible();
});

test('AC-5: unbekannte Unterseite ohne Login fuehrt zum Login', async ({ page }) => {
	await page.goto('/funktionen/unbekannt');
	await expect(page).toHaveURL(/\/login/);
});

test('AC-2: Startseite zeigt Level-Tabelle, Link fuehrt zu /funktionen', async ({ page }) => {
	await page.goto('/');
	await expect(page.locator('[data-testid="level-tabelle"]')).toBeVisible();
	await page.locator('a[href="/funktionen"]').first().click();
	await expect(page).toHaveURL(/\/funktionen$/);
});
