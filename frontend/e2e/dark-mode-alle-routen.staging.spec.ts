// E2E (Staging) — Issue #2400 (Epic #2508): vollständiger Dark Mode, Messlauf aller Routen.
// Spec: docs/specs/modules/fix_2400_dark_mode_vollstaendig.md — AC-1, AC-3, AC-4, AC-5, AC-7,
// AC-8, AC-10, AC-12, AC-13, AC-14.
//
// Gemessen wird am gerenderten DOM mit berechneten Werten (`messeKontrast` aus helpers.ts:
// jeder sichtbare Textknoten gegen seinen effektiven Hintergrund, WCAG-Formel). Routen kommen
// aus dem Routenbaum (src/routes/**/+page.svelte), dynamische Routen ([id]) werden mit der
// ersten Trip-/Vergleichs-ID aus der Liste des eingeloggten Nutzers belegt (Trip und Vergleich
// paarweise). Jede Route wird bei 1280x800 und 390x844 gemessen; Screenshots je Route landen
// unter test-results/ für die Fresh-Eyes-Prüfung.
//
// Ausführen (gegen Staging, aus frontend/, NACH Deploy):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=e2e/playwright.dark-mode.staging.config.ts
import { test, expect, type Page } from '@playwright/test';
import { readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { messeKontrast, kontrastVerstoesse, kontrastBericht, kontrastVerhaeltnis } from './helpers';

const ROUTES_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'src', 'routes');
const VIEWPORTS = [
	{ name: 'desktop', width: 1280, height: 800 },
	{ name: 'mobil', width: 390, height: 844 }
] as const;
/** Nicht ausgeliefert bzw. reine Entwickler-Seiten. */
const NICHT_GEMESSEN = new Set(['/email-preview-dev', '/_design', '/_design-system']);
const AUSGELOGGT = ['/', '/login', '/register', '/forgot-password', '/reset-password', '/magic-link', '/verify-email'];

/** Routen aus dem Routenbaum: Verzeichnisse mit +page.svelte, Gruppen `(x)` entfernt. */
function routenAusBaum(dir = ROUTES_DIR, prefix = ''): string[] {
	const out: string[] = [];
	for (const name of readdirSync(dir)) {
		const p = path.join(dir, name);
		if (name === '+page.svelte') out.push(prefix || '/');
		else if (statSync(p).isDirectory() && name !== '__tests__') {
			out.push(...routenAusBaum(p, /^\(.*\)$/.test(name) ? prefix : `${prefix}/${name}`));
		}
	}
	return out;
}

async function setzeDunkel(page: Page, an: boolean) {
	await page.addInitScript((wert) => {
		try {
			if (wert) localStorage.setItem('gz-dark', '1');
			else localStorage.removeItem('gz-dark');
		} catch {
			/* ignore */
		}
	}, an);
}

/** Erste ID aus einer Listenseite (`/trips` bzw. `/compare`). */
async function ersteId(page: Page, liste: '/trips' | '/compare'): Promise<string | null> {
	await page.goto(liste);
	await page.waitForLoadState('networkidle');
	const hrefs = await page.locator(`a[href^="${liste}/"]`).evaluateAll((as) => as.map((a) => a.getAttribute('href') ?? ''));
	const id = hrefs.map((h) => h.split('/')[2]).find((x) => x && x !== 'new');
	return id ?? null;
}

/** Helle Flächen (Luminanz > 0,5) mit sichtbarer Ausdehnung auf dunklem Seitengrund. */
async function helleFlaechen(page: Page): Promise<string[]> {
	return page.evaluate(() => {
		const lin = (v: number) => {
			const s = v / 255;
			return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
		};
		const out: string[] = [];
		for (const el of Array.from(document.body.querySelectorAll('*'))) {
			if (el.closest('.leaflet-container, .leaflet-pane')) continue; // Kacheln bleiben hell (Out of Scope)
			const r = el.getBoundingClientRect();
			if (r.width < 40 || r.height < 20) continue;
			if (!el.checkVisibility({ opacityProperty: true, visibilityProperty: true })) continue;
			const m = /rgba?\(([^)]+)\)/.exec(getComputedStyle(el).backgroundColor);
			if (!m) continue;
			const [rr, g, b, a = 1] = m[1].split(/[\s,/]+/).filter(Boolean).map(parseFloat);
			if (a < 0.5) continue;
			const l = 0.2126 * lin(rr) + 0.7152 * lin(g) + 0.0722 * lin(b);
			if (l > 0.5) {
				const id = el.getAttribute('data-testid');
				const kl = typeof el.className === 'string' ? el.className.split(/\s+/)[0] : '';
				out.push(`${el.tagName.toLowerCase()}${id ? `[data-testid="${id}"]` : kl ? `.${kl}` : ''} (${Math.round(r.width)}x${Math.round(r.height)}, L=${l.toFixed(2)})`);
			}
		}
		return [...new Set(out)].slice(0, 30);
	});
}

async function messeRoute(page: Page, pfad: string, vp: string) {
	await page.goto(pfad);
	await page.waitForLoadState('networkidle');
	await page.screenshot({ path: test.info().outputPath(`dark-${vp}${pfad.replace(/\//g, '_') || '_root'}.png`), fullPage: true });
	expect(await page.evaluate(() => document.documentElement.getAttribute('data-theme')), `${pfad}: data-theme`).toBe('dark');
	const bericht = kontrastBericht(`${vp} ${pfad}`, kontrastVerstoesse(await messeKontrast(page)));
	const hell = await helleFlaechen(page);
	expect([...bericht, ...hell.map((h) => `${vp} ${pfad} · helle Fläche ${h}`)], `${pfad} im Dark`).toEqual([]);
}

// ─── AC-1 / AC-3: ausgeloggt ──────────────────────────────────────────────────

test.describe('ausgeloggt', () => {
	test.use({ storageState: { cookies: [], origins: [] } });
	for (const vp of VIEWPORTS) {
		for (const pfad of AUSGELOGGT) {
			test(`AC-1/AC-3 ${vp.name} ${pfad}: kein Text < 4,5:1, keine hellen Flächen`, async ({ page }) => {
				await page.setViewportSize(vp);
				await setzeDunkel(page, true);
				await messeRoute(page, pfad, vp.name);
			});
		}
	}
	test('AC-10: /offline.html dunkel lesbar, ohne gz-dark hell', async ({ page }) => {
		await setzeDunkel(page, true);
		await page.goto('/offline.html');
		expect(await page.evaluate(() => document.documentElement.getAttribute('data-theme'))).toBe('dark');
		expect(kontrastVerstoesse(await messeKontrast(page))).toEqual([]);
		const body = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
		expect(kontrastVerhaeltnis('rgb(255, 255, 255)', body)).toBeGreaterThan(10);
	});
});

// ─── AC-3 / AC-13 / AC-14: eingeloggt, alle Routen ────────────────────────────

test.describe('eingeloggt', () => {
	for (const vp of VIEWPORTS) {
		test(`AC-3/AC-13/AC-14 ${vp.name}: alle Routen aus dem Routenbaum`, async ({ page }) => {
			test.setTimeout(600_000);
			await page.setViewportSize(vp);
			await setzeDunkel(page, true);
			const tripId = await ersteId(page, '/trips');
			const compareId = await ersteId(page, '/compare');
			expect(tripId, 'Staging-Nutzer ohne Trip — Trip-Seiten nicht messbar').not.toBeNull();
			expect(compareId, 'Staging-Nutzer ohne Ortsvergleich — Vergleich-Seiten nicht messbar').not.toBeNull();
			const routen = routenAusBaum()
				.filter((r) => !NICHT_GEMESSEN.has(r) && !AUSGELOGGT.includes(r))
				.map((r) => r.replace('/trips/[id]', `/trips/${tripId}`).replace('/compare/[id]', `/compare/${compareId}`));
			const fehler: string[] = [];
			for (const r of routen) {
				await test.step(r, async () => {
					try {
						await messeRoute(page, r, vp.name);
					} catch (e) {
						fehler.push(String((e as Error).message).slice(0, 2000));
					}
				});
			}
			expect(fehler, 'Verstoßliste Dark (Route, Text, Wert, Pfad)').toEqual([]);
		});
	}

	test('AC-14: Karten-Container hat erkennbaren Rand (≥ 3:1) gegen den dunklen Grund', async ({ page }) => {
		await setzeDunkel(page, true);
		const tripId = await ersteId(page, '/trips');
		await page.goto(`/trips/${tripId}`);
		await page.waitForLoadState('networkidle');
		const karte = page.locator('.leaflet-container').first();
		test.skip((await karte.count()) === 0, 'keine Karte auf der Trip-Seite');
		const z = await karte.evaluate((el) => {
			const rahmen = el.parentElement ?? el;
			const cs = getComputedStyle(el);
			const cp = getComputedStyle(rahmen);
			const rand = parseFloat(cs.borderTopWidth) > 0 ? cs.borderTopColor : cp.borderTopColor;
			return { rand, grund: getComputedStyle(document.body).backgroundColor };
		});
		expect(kontrastVerhaeltnis(z.rand, z.grund)).toBeGreaterThanOrEqual(3);
	});
});

// ─── AC-4: kein Hell-Blitz ────────────────────────────────────────────────────

test('AC-4: data-theme und dunkler Seitengrund schon bei DOMContentLoaded (vor Hydrierung)', async ({ page }) => {
	await setzeDunkel(page, true);
	// Framework-JavaScript zurückhalten: gemessen wird, was VOR der Hydrierung gemalt wird.
	await page.route(/\/_app\/immutable\/.*\.js$/, async (route) => {
		await new Promise((r) => setTimeout(r, 3000));
		await route.continue();
	});
	await page.goto('/', { waitUntil: 'domcontentloaded' });
	const z = await page.evaluate(() => ({
		theme: document.documentElement.getAttribute('data-theme'),
		scheme: getComputedStyle(document.documentElement).colorScheme,
		themeColor: document.querySelector('meta[name="theme-color"]')?.getAttribute('content')?.toLowerCase(),
		body: getComputedStyle(document.body).backgroundColor
	}));
	expect(z.theme).toBe('dark');
	expect(z.scheme).toBe('dark');
	expect(z.themeColor).not.toBe('#f6f4ee');
	expect(kontrastVerhaeltnis('rgb(255, 255, 255)', z.body), `Seitengrund im ersten Frame ${z.body}`).toBeGreaterThan(10);
});

// ─── AC-5: Schalter hin und zurück, Desktop und Mobil ─────────────────────────

for (const vp of VIEWPORTS) {
	test(`AC-5 ${vp.name}: Schalter wirkt sofort und bleibt nach Neuladen`, async ({ page }) => {
		await page.setViewportSize(vp);
		await setzeDunkel(page, false);
		await page.goto('/trips');
		await page.waitForLoadState('networkidle');
		const zustand = () =>
			page.evaluate(() => ({
				theme: document.documentElement.getAttribute('data-theme'),
				paper: getComputedStyle(document.documentElement).getPropertyValue('--g-paper').trim().toLowerCase(),
				scheme: getComputedStyle(document.documentElement).colorScheme,
				themeColor: document.querySelector('meta[name="theme-color"]')?.getAttribute('content')?.toLowerCase()
			}));
		const schalter = async () => {
			if (vp.name === 'mobil') {
				await page.getByTestId('konto-kreis').click();
				await page.getByTestId('konto-sheet-dark').getByRole('switch').click();
				await page.keyboard.press('Escape');
			} else {
				await page.getByRole('switch', { name: /Dunkles Design|Dark/i }).first().click();
			}
		};
		expect((await zustand()).paper).toBe('#f6f4ee');
		await schalter();
		await expect.poll(async () => (await zustand()).theme).toBe('dark');
		const dunkel = await zustand();
		expect(dunkel.paper).not.toBe('#f6f4ee');
		expect(dunkel.scheme).toBe('dark');
		expect(dunkel.themeColor).not.toBe('#f6f4ee');
		await page.reload();
		expect((await zustand()).theme).toBe('dark');
		await schalter();
		await expect.poll(async () => (await zustand()).theme).not.toBe('dark');
		expect((await zustand()).paper).toBe('#f6f4ee');
		await page.reload();
		const hell = await zustand();
		expect(hell.theme).not.toBe('dark');
		expect(hell.themeColor).toBe('#f6f4ee');
	});
}

// ─── AC-7: Akzentflächen mit Text, beide Modi ─────────────────────────────────

for (const dunkel of [false, true]) {
	test(`AC-7 ${dunkel ? 'dunkel' : 'hell'}: Schrift auf Akzentflächen ≥ 4,5:1`, async ({ page }) => {
		await page.setViewportSize({ width: 390, height: 844 });
		await setzeDunkel(page, dunkel);
		await page.goto('/trips');
		await page.waitForLoadState('networkidle');
		const flaechen = page.locator('[data-variant="accent"], [data-testid="konto-kreis"]');
		const n = await flaechen.count();
		expect(n, 'keine Akzentfläche gefunden').toBeGreaterThan(0);
		const verstoesse: string[] = [];
		for (let i = 0; i < n; i++) {
			verstoesse.push(...kontrastBericht(`akzent#${i}`, kontrastVerstoesse(await messeKontrast(flaechen.nth(i)))));
		}
		expect(verstoesse).toEqual([]);
	});
}

// ─── AC-8 / AC-12: dark:-Varianten folgen dem Schalter; Eingabe-Rand ≥ 3:1 ────

for (const [os, dunkel] of [
	['light', true],
	['dark', false]
] as const) {
	test(`AC-8: Betriebssystem ${os}, Schalter ${dunkel ? 'dunkel' : 'hell'} ⇒ Eingabefeld folgt dem Schalter`, async ({ browser }) => {
		const ctx = await browser.newContext({ colorScheme: os, storageState: { cookies: [], origins: [] } });
		const page = await ctx.newPage();
		await setzeDunkel(page, dunkel);
		await page.goto('/login');
		const input = page.locator('input').first();
		const z = await input.evaluate((el) => ({
			bg: getComputedStyle(el).backgroundColor,
			rand: getComputedStyle(el).borderTopColor,
			karte: getComputedStyle(el.closest('form') ?? document.body).backgroundColor,
			theme: document.documentElement.getAttribute('data-theme')
		}));
		expect(z.theme === 'dark').toBe(dunkel);
		const [r, g, b] = (z.bg.match(/[\d.]+/g) ?? []).map(Number);
		if (dunkel) expect(Math.max(r, g, b), `Input-Grund im Dark ${z.bg}`).toBeLessThan(90);
		else expect(Math.min(r, g, b), `Input-Grund im Hell ${z.bg}`).toBeGreaterThan(200);
		if (dunkel) expect(kontrastVerhaeltnis(z.rand, 'rgb(29, 29, 26)')).toBeGreaterThanOrEqual(3);
		await ctx.close();
	});
}

// ─── Gemeinsame Messung: Statusboxen und Flächen ──────────────────────────────

/** Statusbox-Muster der Auth-/Konto-Seiten (Erfolg/Warnung/Fehler): `rounded-md border p-3 text-sm`. */
const STATUSBOX = '.rounded-md.border.p-3.text-sm';

interface BoxMessung {
	text: string;
	rand: string;
	boxGrund: string;
	seitenGrund: string;
}

/** Misst je sichtbarer Statusbox: Rand, effektiven Boxen-Grund (transparente Schichten gemischt), Seitengrund. */
async function boxMessungen(page: Page): Promise<BoxMessung[]> {
	return page.evaluate((sel) => {
		type RGBA = [number, number, number, number];
		const parse = (c: string): RGBA => {
			const m = /rgba?\(([^)]+)\)/.exec(c);
			if (!m) return [0, 0, 0, 0];
			const [r, g, b, a = 1] = m[1].split(/[\s,/]+/).filter(Boolean).map(parseFloat);
			return [r, g, b, a];
		};
		const over = (oben: RGBA, unten: [number, number, number]): [number, number, number] => [
			oben[0] * oben[3] + unten[0] * (1 - oben[3]),
			oben[1] * oben[3] + unten[1] * (1 - oben[3]),
			oben[2] * oben[3] + unten[2] * (1 - oben[3])
		];
		const grundBis = (el: Element | null, einschliesslich: boolean): [number, number, number] => {
			const kette: Element[] = [];
			for (let e = el; e; e = e.parentElement) kette.unshift(e);
			if (!einschliesslich) kette.pop();
			let g: [number, number, number] = [255, 255, 255];
			for (const e of kette) g = over(parse(getComputedStyle(e).backgroundColor), g);
			return g;
		};
		const rgb = (c: number[]) => `rgb(${c.map((v) => Math.round(v)).join(', ')})`;
		return Array.from(document.querySelectorAll(sel))
			.filter((el) => el.checkVisibility({ opacityProperty: true, visibilityProperty: true }))
			.map((el) => {
				const cs = getComputedStyle(el);
				const seiten = grundBis(el, false);
				const randRoh = parse(cs.borderTopColor);
				return {
					text: (el.textContent ?? '').trim().slice(0, 60),
					rand: rgb(over(randRoh, seiten)),
					boxGrund: rgb(grundBis(el, true)),
					seitenGrund: rgb(seiten)
				};
			});
	}, STATUSBOX);
}

/** AC-9: Schrift in jeder Box ≥ 4,5:1 (Wert gegen Boxen-Grund), Rand ODER Tönung ≥ 3:1 gegen den Seitengrund. */
async function pruefeStatusboxen(page: Page, label: string, mindestens = 1) {
	const boxen = await boxMessungen(page);
	expect(boxen.length, `${label}: keine Statusbox erzeugt`).toBeGreaterThanOrEqual(mindestens);
	const probleme: string[] = [];
	for (let i = 0; i < boxen.length; i++) {
		const b = boxen[i];
		const text = kontrastBericht(`${label} box#${i}`, kontrastVerstoesse(await messeKontrast(page.locator(STATUSBOX).nth(i))));
		probleme.push(...text);
		const rand = kontrastVerhaeltnis(b.rand, b.seitenGrund);
		const toenung = kontrastVerhaeltnis(b.boxGrund, b.seitenGrund);
		if (Math.max(rand, toenung) < 3) {
			probleme.push(`${label} box#${i} ${JSON.stringify(b.text)}: Rand ${rand.toFixed(2)}:1, Tönung ${toenung.toFixed(2)}:1 < 3:1 gegen Seitengrund`);
		}
	}
	expect(probleme, `${label}: Statusboxen`).toEqual([]);
}

// ─── AC-9: Statusboxen (Erfolg/Fehler) in Hell und Dunkel ─────────────────────
// Ausgelöst ohne Seiteneffekte: Hinweis-Parameter der Login-Seite, falsche Anmeldung für eine
// nicht existierende Adresse, Fantasie-Adresse bei „Passwort vergessen" (Seite zeigt immer
// dieselbe neutrale Erfolgsmeldung, Backend sendet an unbekannte Adresse nichts), ungültige
// Bestätigung/Zurücksetzung mit erfundenem Token (Server lehnt ab, nichts wird verändert).

test.describe('AC-9 Statusboxen', () => {
	test.use({ storageState: { cookies: [], origins: [] } });
	const FANTASIE = `dark-mode-pruefung-${Date.now()}@example.invalid`;
	for (const dunkel of [false, true]) {
		const modus = dunkel ? 'dunkel' : 'hell';

		test(`AC-9 ${modus} /login: Erfolgs-, Abgelaufen- und Fehlerbox (falsches Passwort)`, async ({ page }) => {
			await setzeDunkel(page, dunkel);
			await page.goto('/login?registered=1&expired=1');
			await page.waitForLoadState('networkidle');
			await pruefeStatusboxen(page, `${modus} /login Hinweise`, 2);
			await page.goto('/login');
			await page.waitForLoadState('networkidle');
			await page.fill('input[name="username"]', FANTASIE);
			await page.fill('input[name="password"]', 'falsches-passwort-xyz');
			await page.click('form[action="?/login"] button[type="submit"]');
			await expect(page.locator(STATUSBOX).first()).toBeVisible();
			await pruefeStatusboxen(page, `${modus} /login Fehler`);
		});

		test(`AC-9 ${modus} /forgot-password: neutrale Erfolgsbox für Fantasie-Adresse`, async ({ page }) => {
			await setzeDunkel(page, dunkel);
			await page.goto('/forgot-password');
			await page.waitForLoadState('networkidle');
			await page.fill('input[name="username"]', FANTASIE);
			await page.click('form button[type="submit"]');
			await expect(page.locator(STATUSBOX).first()).toBeVisible();
			await pruefeStatusboxen(page, `${modus} /forgot-password Erfolg`);
		});

		test(`AC-9 ${modus} /verify-email: Fehlerbox (unvollständig) und abgelehnter Fantasie-Token`, async ({ page }) => {
			await setzeDunkel(page, dunkel);
			await page.goto('/verify-email');
			await page.waitForLoadState('networkidle');
			await pruefeStatusboxen(page, `${modus} /verify-email unvollständig`);
			await page.goto('/verify-email?user=u-00000000&token=erfundener-token-0000');
			await page.waitForLoadState('networkidle');
			await page.click('form button[type="submit"]');
			await expect(page.locator(STATUSBOX).first()).toBeVisible();
			await pruefeStatusboxen(page, `${modus} /verify-email abgelehnt`);
		});

		test(`AC-9 ${modus} /reset-password: Fehlerbox bei erfundenem Token`, async ({ page }) => {
			await setzeDunkel(page, dunkel);
			await page.goto('/reset-password?user=u-00000000&token=erfundener-token-0000');
			await page.waitForLoadState('networkidle');
			await page.fill('input[name="new_password"]', 'Pruefung-Dark-12345');
			await page.click('form button[type="submit"]');
			await expect(page.locator(STATUSBOX).first()).toBeVisible();
			await pruefeStatusboxen(page, `${modus} /reset-password Fehler`);
		});
	}
});

test.describe('AC-9 Statusboxen eingeloggt (account, gpx-upload)', () => {
	for (const dunkel of [false, true]) {
		test(`AC-9 ${dunkel ? 'dunkel' : 'hell'}: vorhandene Boxen auf /account und /gpx-upload`, async ({ page }) => {
			await setzeDunkel(page, dunkel);
			for (const pfad of ['/account', '/gpx-upload']) {
				await page.goto(pfad);
				await page.waitForLoadState('networkidle');
				// Keine Aktion ausgelöst (würde Daten verändern): gemessen wird, was die Seite von sich aus zeigt.
				await pruefeStatusboxen(page, `${dunkel ? 'dunkel' : 'hell'} ${pfad}`, 0);
			}
		});
	}
});

// ─── AC-13: Trip und Ortsvergleich als ausdrückliches Paar ────────────────────

for (const vp of VIEWPORTS) {
	test(`AC-13 ${vp.name}: Editor-Flächen in /trips/<id>/edit und /compare/<id>/edit verhalten sich gleich`, async ({ page }) => {
		test.setTimeout(180_000);
		await page.setViewportSize(vp);
		await setzeDunkel(page, true);
		const tripId = await ersteId(page, '/trips');
		const compareId = await ersteId(page, '/compare');
		expect(tripId, 'Staging-Nutzer ohne Trip').not.toBeNull();
		expect(compareId, 'Staging-Nutzer ohne Ortsvergleich').not.toBeNull();
		const messung = async (pfad: string) => {
			await page.goto(pfad);
			await page.waitForLoadState('networkidle');
			await page.screenshot({ path: test.info().outputPath(`dark-paar-${vp.name}${pfad.replace(/\//g, '_')}.png`), fullPage: true });
			const vorhanden = async (testid: string) => (await page.getByTestId(testid).count()) > 0;
			return {
				pfad,
				text: kontrastBericht(`${vp.name} ${pfad}`, kontrastVerstoesse(await messeKontrast(page))),
				hell: await helleFlaechen(page),
				saveIndicator: await vorhanden('save-indicator'),
				korridorEditor: (await page.locator('[data-testid^="corridor-editor-"]').count()) > 0,
				offlineHinweis: await vorhanden('offline-sperre-hinweis')
			};
		};
		const trip = await messung(`/trips/${tripId}/edit`);
		const vergleich = await messung(`/compare/${compareId}/edit`);
		for (const m of [trip, vergleich]) {
			expect(m.text, `${m.pfad}: Text < 4,5:1`).toEqual([]);
			expect(m.hell, `${m.pfad}: helle Flächen auf dunklem Grund`).toEqual([]);
		}
		// Gleiche Behandlung: dieselben Editor-Bausteine sind in beiden Editoren da (oder in keinem).
		expect(
			{ saveIndicator: vergleich.saveIndicator, korridorEditor: vergleich.korridorEditor, offlineHinweis: vergleich.offlineHinweis },
			'Trip- und Vergleich-Editor zeigen nicht dieselben Editor-Flächen'
		).toEqual({ saveIndicator: trip.saveIndicator, korridorEditor: trip.korridorEditor, offlineHinweis: trip.offlineHinweis });
	});
}

// ─── AC-14: Ortsvergleich-Karte (LocationPreviewMap / Leaflet) ────────────────

test('AC-14: Ortsvergleich-Karte hat Rand ≥ 3:1 und lesbare Beschriftung/Zoom-Knöpfe (≥ 4,5:1) im Dunkelmodus', async ({ page }) => {
	await setzeDunkel(page, true);
	const compareId = await ersteId(page, '/compare');
	expect(compareId, 'Staging-Nutzer ohne Ortsvergleich').not.toBeNull();
	const probleme: string[] = [];
	let gesehen = 0;
	for (const pfad of [`/compare/${compareId}`, `/compare/${compareId}/edit`]) {
		await page.goto(pfad);
		await page.waitForLoadState('networkidle');
		const rahmen = page.locator('.g-karten-rahmen, .leaflet-container');
		const n = await rahmen.count();
		for (let i = 0; i < n; i++) {
			const karte = rahmen.nth(i);
			if (!(await karte.isVisible())) continue;
			gesehen++;
			const z = await karte.evaluate((el) => {
				const cs = getComputedStyle(el);
				const eltern = el.parentElement ? getComputedStyle(el.parentElement) : cs;
				const rand = parseFloat(cs.borderTopWidth) > 0 ? cs.borderTopColor : eltern.borderTopColor;
				return { rand, grund: getComputedStyle(document.body).backgroundColor };
			});
			const verh = kontrastVerhaeltnis(z.rand, z.grund);
			if (verh < 3) probleme.push(`${pfad} Karte#${i}: Rand ${verh.toFixed(2)}:1 < 3:1`);
			// Beschriftung der Vorschau (Koordinaten) bzw. Zoom-Knöpfe/Attribution von Leaflet.
			const ziele = karte.locator('p, .leaflet-control-zoom a, .leaflet-control-attribution');
			for (let j = 0; j < (await ziele.count()); j++) {
				probleme.push(...kontrastBericht(`${pfad} Karte#${i}`, kontrastVerstoesse(await messeKontrast(ziele.nth(j)))));
			}
		}
	}
	test.skip(gesehen === 0, 'keine Ortsvergleich-Karte (.g-karten-rahmen/.leaflet-container) auf Detail- und Editor-Seite sichtbar');
	expect(probleme, 'Ortsvergleich-Karte im Dark').toEqual([]);
});
