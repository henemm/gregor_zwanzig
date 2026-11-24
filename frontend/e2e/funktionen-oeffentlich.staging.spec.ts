// Issue #3319 / #3320 — oeffentliche Funktionsuebersicht (Uebersicht + neun Unterseiten)
// und Startseite gegen STAGING.
// AC-2 (Link Startseite -> /funktionen), AC-4 (alle zehn Funktions-Pfade ohne Anmeldung
// 200, kein /api-Aufruf), AC-6 (Kachel -> Unterseite, Sprachumschalter ohne Login),
// AC-8 (Bilder laden), AC-11 (375 px ohne horizontale Scrollleiste auf allen elf Seiten,
// Textkontrast WCAG-AA), AC-12 (Weiter-Kette von der ersten bis zur letzten Unterseite),
// AC-13 (Bildergalerie nur auf Unterseiten; Uebersicht: Kachelbild ist Link; Klick/Enter/Leertaste oeffnet, Pfeiltaste/Schaltflaeche/Wischen
// blaettert nicht umlaufend, Esc/X/Klick daneben schliesst, Fokus zurueck, 375 px),
// F001 (ein <main>, keine App-Seitenleiste auf den Funktionsseiten).
// Spec: docs/specs/modules/oeffentliche_doku_3319.md (v1.2)
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

// F001 (Adversary): die Layout-Verdrahtung selbst — auf den oeffentlichen Funktionsseiten
// rendert das Wurzel-Layout KEIN App-Geruest (Seitenleiste, untere Navigation, zweites <main>).
for (const pfad of ['/funktionen', '/funktionen/briefings', '/funktionen/level']) {
	test(`F001: ${pfad} ohne Login: genau ein <main>, keine App-Seitenleiste, keine untere Navigation`, async ({ page }) => {
		await page.goto(pfad);
		await expect(page.locator('h1')).toBeVisible();
		await expect(page.locator('main'), `${pfad}: <main> nicht genau einmal`).toHaveCount(1);
		await expect(page.locator('[data-testid="desktop-sidebar"]'), `${pfad}: App-Seitenleiste`).toHaveCount(0);
		await expect(page.locator('[data-testid="bottom-nav"]'), `${pfad}: untere App-Navigation`).toHaveCount(0);
	});
}

// AC-13: Bildergalerie (Klick, Pfeiltaste, Esc, Fokus zurueck, 375 px), ohne Anmeldung.
test.describe('AC-13: Bildergalerie', () => {
	const galerie = (page: Page) => page.locator('[data-testid="galerie"]');
	const zaehler = (page: Page) => page.locator('[data-testid="galerie-zaehler"]');
	// Bedienung erst nach der Hydrierung (vorher ist die Schaltflaeche reines HTML):
	// warten, bis keine Netzlast mehr laeuft (Skripte geladen).
	const oeffneSeite = (page: Page, pfad: string) => page.goto(pfad, { waitUntil: 'networkidle' });

	test('Unterseite: Klick oeffnet, Pfeil rechts blaettert, Rand nicht umlaufend, Esc schliesst, Fokus zurueck', async ({ page }) => {
		await oeffneSeite(page, '/funktionen/kanaele');
		const knoepfe = page.locator('main [data-testid="bild-oeffnen"]');
		const anzahl = await knoepfe.count();
		expect(anzahl, 'Messaufbau: kanaele hat mehrere Bilder').toBeGreaterThanOrEqual(3);
		await expect(galerie(page)).toHaveCount(0);

		const zweites = knoepfe.nth(1);
		await zweites.scrollIntoViewIfNeeded();
		await zweites.click();
		await expect(galerie(page)).toBeVisible();
		await expect(page.locator('[role="dialog"]')).toHaveCount(1);
		await expect(zaehler(page)).toHaveText(`2 / ${anzahl}`);
		// dieselbe Datei wie das angeklickte Seitenbild
		const seitenSrc = await zweites.locator('img').getAttribute('src');
		await expect(page.locator('[data-testid="galerie-bild"]')).toHaveAttribute('src', seitenSrc ?? '');
		await expect(page.locator('[data-testid="galerie-beschriftung"]')).not.toBeEmpty();

		await page.keyboard.press('ArrowRight');
		await expect(zaehler(page)).toHaveText(`3 / ${anzahl}`);
		for (let i = 3; i < anzahl; i++) await page.keyboard.press('ArrowRight');
		await expect(zaehler(page)).toHaveText(`${anzahl} / ${anzahl}`);
		await expect(page.locator('[data-testid="galerie-vor"]')).toBeDisabled();
		await page.keyboard.press('ArrowRight');
		await expect(zaehler(page), 'am Ende nicht umlaufend').toHaveText(`${anzahl} / ${anzahl}`);
		await page.locator('[data-testid="galerie-zurueck"]').click();
		await expect(zaehler(page)).toHaveText(`${anzahl - 1} / ${anzahl}`);

		await page.keyboard.press('Escape');
		await expect(galerie(page)).toHaveCount(0);
		await expect(zweites, 'Fokus zurueck auf das angeklickte Bild').toBeFocused();
	});

	test('Tastatur: Enter oeffnet, X-Schaltflaeche schliesst; Leertaste oeffnet, Klick neben das Bild schliesst', async ({ page }) => {
		await oeffneSeite(page, '/funktionen/trips');
		const erstes = page.locator('main [data-testid="bild-oeffnen"]').first();
		await erstes.focus();
		await page.keyboard.press('Enter');
		await expect(galerie(page)).toBeVisible();
		await expect(zaehler(page)).toHaveText(/^1 \/ \d+$/);
		await expect(page.locator('[data-testid="galerie-zurueck"]'), 'erstes Bild: kein Zurueck').toBeDisabled();
		await page.locator('[data-testid="galerie-schliessen"]').click();
		await expect(galerie(page)).toHaveCount(0);
		await expect(erstes).toBeFocused();

		await page.keyboard.press(' ');
		await expect(galerie(page)).toBeVisible();
		// Klick in die linke obere Ecke: leere Flaeche neben dem Bild
		await page.mouse.click(4, 4);
		await expect(galerie(page)).toHaveCount(0);
		await expect(erstes).toBeFocused();
	});

	test('Desktop 1280 px: Klick seitlich neben das Bild (in der Buehne) schliesst, Fokus zurueck', async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 800 });
		await oeffneSeite(page, '/funktionen/trips');
		const erstes = page.locator('main [data-testid="bild-oeffnen"]').first();
		await erstes.scrollIntoViewIfNeeded();
		await erstes.click();
		await expect(galerie(page)).toBeVisible();
		const bild = page.locator('[data-testid="galerie-bild"]');
		await expect.poll(() => bild.evaluate((i: HTMLImageElement) => i.naturalWidth)).toBeGreaterThan(0);
		const kasten = (await bild.boundingBox())!;
		const buehne = (await page.locator('[data-testid="galerie"] .buehne').boundingBox())!;
		// Punkt links vom Bild, mittig in der Bildhoehe, innerhalb der Buehne
		const x = (buehne.x + kasten.x) / 2;
		const y = kasten.y + kasten.height / 2;
		expect(kasten.x - buehne.x, 'Messaufbau: links vom Bild ist freie Buehnenflaeche').toBeGreaterThan(20);
		expect(y).toBeGreaterThan(buehne.y);
		expect(y).toBeLessThan(buehne.y + buehne.height);
		const getroffen = await page.evaluate(([px, py]) => {
			const el = document.elementFromPoint(px, py) as HTMLElement | null;
			return el?.classList.contains('buehne') ?? false;
		}, [x, y]);
		expect(getroffen, 'Messaufbau: der Klickpunkt trifft die Buehne selbst').toBe(true);
		await page.mouse.click(x, y);
		await expect(galerie(page)).toHaveCount(0);
		await expect(erstes).toBeFocused();
	});

	test('Uebersicht: keine Galerie — Klick auf das Kachelbild fuehrt zur Unterseite', async ({ page }) => {
		await oeffneSeite(page, '/funktionen');
		await expect(page.locator('main [data-testid="bild-oeffnen"]'), 'Galerie-Schaltflaeche auf der Uebersicht').toHaveCount(0);
		const bild = page.locator('[data-testid="kachel"][href="/funktionen/briefings"] img');
		await expect(bild).toHaveCount(1);
		await bild.scrollIntoViewIfNeeded();
		await bild.click();
		await expect(page).toHaveURL(/\/funktionen\/briefings$/);
		await expect(galerie(page)).toHaveCount(0);
		await expect(page.locator('[role="dialog"]')).toHaveCount(0);
	});

	for (const lang of ['de', 'en']) {
		test(`375 px (${lang}): offene Galerie ohne horizontale Scrollleiste, Bild hoechstens Fenstergroesse, Beschriftungen aus dem Katalog`, async ({ page, context }) => {
			await context.addCookies([{ name: 'gz_lang', value: lang, url: BASE }]);
			await oeffneSeite(page, '/funktionen/briefings');
			await page.locator('main [data-testid="bild-oeffnen"]').first().click();
			await expect(galerie(page)).toBeVisible();
			const bild = page.locator('[data-testid="galerie-bild"]');
			await expect.poll(() => bild.evaluate((i: HTMLImageElement) => i.naturalWidth)).toBeGreaterThan(0);
			await keineScrollleiste(page, 'offene Galerie');
			const kasten = await bild.boundingBox();
			const fenster = page.viewportSize()!;
			expect(kasten!.x).toBeGreaterThanOrEqual(0);
			expect(kasten!.x + kasten!.width).toBeLessThanOrEqual(fenster.width);
			expect(kasten!.y + kasten!.height).toBeLessThanOrEqual(fenster.height);
			const soll = lang === 'de'
				? { schliessen: 'Galerie schließen', vor: 'Nächstes Bild', zurueck: 'Vorheriges Bild' }
				: { schliessen: 'Close gallery', vor: 'Next image', zurueck: 'Previous image' };
			await expect(page.locator('[data-testid="galerie-schliessen"]')).toHaveAttribute('aria-label', soll.schliessen);
			await expect(page.locator('[data-testid="galerie-vor"]')).toHaveAttribute('aria-label', soll.vor);
			await expect(page.locator('[data-testid="galerie-zurueck"]')).toHaveAttribute('aria-label', soll.zurueck);
		});
	}

	test('Wischen auf dem Handy blaettert', async ({ browser }) => {
		const ctx = await browser.newContext({ hasTouch: true, isMobile: true, viewport: { width: 375, height: 800 }, baseURL: BASE, ignoreHTTPSErrors: true, httpCredentials: { username: process.env.GZ_VALIDATOR_USER ?? '', password: process.env.GZ_VALIDATOR_PASS ?? '' } });
		const page = await ctx.newPage();
		await oeffneSeite(page, '/funktionen/kanaele');
		await page.locator('main [data-testid="bild-oeffnen"]').first().tap();
		await expect(zaehler(page)).toHaveText(/^1 \/ \d+$/);
		const wisch = async (von: number, nach: number) =>
			page.locator('[data-testid="galerie"]').evaluate((el, [a, b]) => {
				const punkt = (x: number) => new Touch({ identifier: 1, target: el, clientX: x, clientY: 300 });
				el.dispatchEvent(new TouchEvent('touchstart', { bubbles: true, changedTouches: [punkt(a)], touches: [punkt(a)] }));
				el.dispatchEvent(new TouchEvent('touchend', { bubbles: true, changedTouches: [punkt(b)], touches: [] }));
			}, [von, nach]);
		await wisch(300, 100);
		await expect(zaehler(page)).toHaveText(/^2 \/ \d+$/);
		await wisch(100, 300);
		await expect(zaehler(page)).toHaveText(/^1 \/ \d+$/);
		await ctx.close();
	});
});

test('AC-2: Startseite zeigt Level-Tabelle, Link fuehrt zu /funktionen', async ({ page }) => {
	await page.goto('/');
	await expect(page.locator('[data-testid="level-tabelle"]')).toBeVisible();
	await page.locator('a[href="/funktionen"]').first().click();
	await expect(page).toHaveURL(/\/funktionen$/);
});
