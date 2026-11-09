// Issue #2661 (i18n F12, Epic #2644) — Sprachwechsel aus Nutzersicht im echten Browser
// gegen den isolierten CI-Stack: Besucher-Umschalter (Cookie gz_lang), zwei Konten
// (de/en) in getrennten Kontexten, Konto-Wechsel ohne Neuladen, Sprach-Mischung der
// sechs Hauptflaechen (beide Hubs ueber HUB_KINDS) und 24 Screenshot-Paare DE/EN.
// Erwartungstexte kommen ueber das Spiegel-Prinzip aus den Katalogdateien (enTextZu),
// die Hub-Reiter fest nach Glossar (Target ranges, Delivery).
// Spec: docs/specs/modules/i18n_f12_frontend_abschluss_2661.md (AC-2 bis AC-6)
//
// Kontingent: /api/auth/register erlaubt 5 Konten je IP und Stunde (router.go). Diese
// Spec legt genau ZWEI an und meldet sie unter eigener X-Real-IP an (die der Go-Server
// nur von Loopback glaubt, #2159), damit fremde Specs im selben Lauf ihr Kontingent behalten.
//
//   cd frontend && npx playwright test e2e/sprachwechsel.spec.ts --project=tests

import { test, expect, request as pwRequest } from '@playwright/test';
import type { APIRequestContext, Browser, BrowserContext, Page } from '@playwright/test';
import { mkdirSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createTestComparePreset, createTestLocation, createTestTrip, HUB_KINDS, HUB_SEL, openHub, type HubKind } from './helpers.ts';
import { assertNotProdBaseURL } from './prodUrlGuard.ts';

type Lang = 'de' | 'en';
const PASSWORT = 'test1234';
const LAUF = Date.now().toString(36);
const NAME: Record<Lang, string> = { de: `e2e-gz-sprache-de-${LAUF}`, en: `e2e-gz-sprache-en-${LAUF}` };
const IP: Record<Lang, string> = { de: '10.26.61.1', en: '10.26.61.2' };
const ARTEFAKTE = fileURLToPath(new URL('../../docs/artifacts/i18n-f12-frontend-abschluss/', import.meta.url));
const MSG = new URL('../src/lib/i18n/messages/', import.meta.url);

const DEUTSCH_WOERTER = ['Speichern', 'Abbrechen', 'Löschen', 'Anmelden', 'Registrieren', 'Einstellungen', 'Wertebereiche', 'Versand', 'Alarme', 'Vorschau', 'Zurück', 'Weiter', 'bitte', 'nicht'];
const ENGLISCH_WOERTER = ['Cancel', 'Delete', 'Sign in', 'Settings', 'Save', 'Target ranges', 'Delivery'];
// Bekannter Backend-Rest (kein Frontend-Text): der Python-Core liefert die Begruendung
// `hourlyNotSelectableReason` (src/output/renderers/compare_hourly_metric_ids.py) nur
// deutsch. Gemeldet als Nebenbefund zu #2661; jede weitere deutsche Zeile bleibt rot.
const BEKANNTE_BACKEND_ZEILEN = [/^Stuendlich nur als Einstrahlung \(W\/m²\) verfuegbar/];

function katalog(lang: Lang): Record<string, string> {
	const dir = new URL(`${lang}/`, MSG);
	return Object.assign({}, ...readdirSync(dir).filter((f) => f.endsWith('.json')).map((f) => JSON.parse(readFileSync(new URL(f, dir), 'utf8'))));
}
const KAT = { de: katalog('de'), en: katalog('en') };
/** Spiegel-Prinzip: englischer Wert des Schluessels, der den deutschen Text traegt. */
function enTextZu(deText: string): string {
	const k = Object.keys(KAT.de).find((s) => KAT.de[s] === deText);
	expect(k, `kein Katalogschluessel mit „${deText}"`).toBeTruthy();
	return KAT.en[k as string];
}

const wortRe = (w: string) => new RegExp(`(?<!\\p{L})${w}(?!\\p{L})`, 'iu');
async function sichtbareZeilen(page: Page): Promise<string[]> {
	const text = await page.evaluate(() => document.body.innerText);
	return text
		.split('\n')
		.map((z) => z.trim())
		.filter((z) => z && !z.includes('E2E-GZ-') && !/e2e-gz-sprache/i.test(z) && !BEKANNTE_BACKEND_ZEILEN.some((re) => re.test(z)));
}
async function pruefeSprache(page: Page, lang: Lang, flaeche: string): Promise<void> {
	await expect(page.locator('html')).toHaveAttribute('lang', lang);
	const verboten = lang === 'en' ? DEUTSCH_WOERTER : ENGLISCH_WOERTER;
	const treffer = (await sichtbareZeilen(page)).flatMap((z) => verboten.filter((w) => wortRe(w).test(z)).map((w) => `${w}: ${z}`));
	expect(treffer, `${flaeche} (${lang}) mischt Sprachen`).toEqual([]);
}

async function legeKontoAn(admin: APIRequestContext, baseURL: string, lang: Lang): Promise<void> {
	const gast = await pwRequest.newContext({ baseURL, storageState: { cookies: [], origins: [] }, extraHTTPHeaders: { 'X-Real-IP': IP[lang] } });
	const reg = await gast.post('/api/auth/register', { data: { username: NAME[lang], password: PASSWORT, email: `${NAME[lang]}@example.com`, language: lang } });
	expect([200, 201], `Registrierung ${lang}: ${reg.status()} ${await reg.text()}`).toContain(reg.status());
	const { id } = (await reg.json()) as { id: string };
	const tok = await admin.post('/api/auth/verify-email/staging-token', { data: { username: id } });
	expect(tok.ok(), `Staging-Token ${lang}: ${tok.status()}`).toBeTruthy();
	const { token } = (await tok.json()) as { token: string };
	expect((await gast.post('/api/auth/verify-email', { data: { user: id, token } })).ok()).toBeTruthy();
	await gast.dispose();
}

async function neuerKontext(browser: Browser, extra: Record<string, unknown> = {}): Promise<BrowserContext> {
	return browser.newContext({ storageState: { cookies: [], origins: [] }, serviceWorkers: 'block', ...extra });
}
async function meldeAn(browser: Browser, lang: Lang): Promise<Page> {
	const page = await (await neuerKontext(browser)).newPage();
	await page.goto('/login');
	await page.fill('input[name="username"]', `${NAME[lang]}@example.com`);
	await page.fill('input[name="password"]', PASSWORT);
	await page.click('form[action="?/login"] button[type="submit"]');
	await page.waitForURL((url) => url.pathname === '/', { timeout: 15_000 });
	return page;
}
async function waehleBesucherSprache(page: Page, lang: Lang): Promise<void> {
	await page.getByTestId('sprach-umschalter').getByRole('button', { name: lang.toUpperCase(), exact: true }).click();
	await expect(page.locator('html')).toHaveAttribute('lang', lang);
}
async function hubOeffnen(page: Page, kind: HubKind, id: string): Promise<void> {
	await openHub(page, kind, id);
	await expect(page.locator(`[data-testid^="${HUB_SEL[kind].reiter}-"]:visible`).first()).toBeVisible();
}

test.describe.serial('Sprachwechsel de <-> en (#2661)', () => {
	const seite: Partial<Record<Lang, Page>> = {};
	const hub: Partial<Record<Lang, Record<HubKind, string>>> = {};

	test.beforeAll(async ({ browser, request, baseURL }) => {
		test.setTimeout(120_000);
		assertNotProdBaseURL(baseURL ?? '');
		for (const lang of ['de', 'en'] as const) {
			await legeKontoAn(request, baseURL as string, lang);
			const page = await meldeAn(browser, lang);
			const r = page.request;
			const ort = await createTestLocation(r, { name: `E2E-GZ-Sprache Ort ${lang}` });
			const ort2 = await createTestLocation(r, { name: `E2E-GZ-Sprache Ort B ${lang}` });
			const trip = await createTestTrip(r, {
				name: `E2E-GZ-Sprache Trip ${lang}`,
				stages: [{ id: 's1', name: 'E2E-GZ-Sprache Etappe', date: '2027-08-01', waypoints: [{ id: 'a', name: 'E2E-GZ-A', lat: 42.0, lon: 9.0, elevation_m: 800 }] }]
			});
			const preset = await createTestComparePreset(r, { name: `E2E-GZ-Sprache Vergleich ${lang}`, locationIds: [ort.id, ort2.id] });
			seite[lang] = page;
			hub[lang] = { route: trip.id, vergleich: preset.id };
		}
	});
	test.afterAll(async () => {
		for (const p of Object.values(seite)) await p?.context().close();
	});

	test('Fall 1 (AC-2): Besucher wechselt auf /login nach EN, Cookie und Neuladen halten, DE stellt zurueck', async ({ browser }) => {
		const page = await (await neuerKontext(browser)).newPage();
		await page.goto('/login');
		await expect(page.locator('html')).toHaveAttribute('lang', 'de');
		await waehleBesucherSprache(page, 'en');
		const knopf = page.locator('form[action="?/login"] button[type="submit"]');
		await expect(knopf).toHaveText(enTextZu('Anmelden'));
		const cookie = (await page.context().cookies()).find((c) => c.name === 'gz_lang');
		expect(cookie?.value).toBe('en');
		await page.reload();
		await expect(page.locator('html')).toHaveAttribute('lang', 'en');
		await expect(knopf).toHaveText(enTextZu('Anmelden'));
		await waehleBesucherSprache(page, 'de');
		await expect(knopf).toHaveText('Anmelden');
		await page.context().close();
	});

	test('Fall 2 (AC-3): zwei Nutzer nebeneinander, kein Uebertrag der Sprache', async () => {
		const en = seite.en as Page;
		const de = seite.de as Page;
		await en.goto('/');
		await de.goto('/');
		await pruefeSprache(en, 'en', 'Cockpit');
		await pruefeSprache(de, 'de', 'Cockpit');
		await en.reload();
		await pruefeSprache(en, 'en', 'Cockpit nach Neuladen');
		await pruefeSprache(de, 'de', 'Cockpit Gegenkontext');
	});

	test('Fall 3 (AC-4): Konto-Wechsel en -> de ohne Neuladen, bleibt nach Neuladen, Gegenwechsel; Nutzer de unberuehrt', async () => {
		const en = seite.en as Page;
		const auswahl = en.getByTestId('sprache-auswahl');
		await en.goto('/account');
		await expect(auswahl).toHaveValue('en');
		await auswahl.selectOption('de');
		await expect(en.getByTestId('sprache-gespeichert')).toHaveText('Sprache gespeichert');
		await pruefeSprache(en, 'de', 'Konto nach Wechsel');
		await en.reload();
		await pruefeSprache(en, 'de', 'Konto nach Neuladen');
		await auswahl.selectOption('en');
		await expect(en.getByTestId('sprache-gespeichert')).toHaveText(enTextZu('Sprache gespeichert'));
		await pruefeSprache(en, 'en', 'Konto nach Gegenwechsel');
		await (seite.de as Page).reload();
		await pruefeSprache(seite.de as Page, 'de', 'Konto Gegenkontext');
	});

	for (const kind of HUB_KINDS) {
		test(`Fall 4 (AC-5): Hub ${kind} – beide Nutzer ohne Sprach-Mischung, Reiter nach Glossar`, async () => {
			for (const lang of ['de', 'en'] as const) {
				const page = seite[lang] as Page;
				await hubOeffnen(page, kind, (hub[lang] as Record<HubKind, string>)[kind]);
				await pruefeSprache(page, lang, `Hub ${kind}`);
				// #2794 S3a (Spec feat_2794_s3a_teil2_leiste.md): Reiter Wetter / Zustellung (Weather / Delivery).
				const reiter = page.locator(`[data-testid="${HUB_SEL[kind].reiter}-wetter"]:visible`).first();
				await expect(reiter).toHaveText(lang === 'en' ? /Weather/i : /Wetter/i);
				// Seit #1743 ist Versand kein Reiter mehr, sondern der Abschnitt #versand (seit #2794 im Reiter Zustellung).
				await openHub(page, kind, (hub[lang] as Record<HubKind, string>)[kind], { tab: 'zustellung', hash: 'versand' });
				const zu = page.locator(`[data-testid="${HUB_SEL[kind].reiter}-zustellung"]:visible`).first();
				await expect(zu).toHaveText(lang === 'en' ? /Delivery/i : /Zustellung/i);
				await pruefeSprache(page, lang, `Hub ${kind} Zustellung/Versand`);
			}
		});
	}

	test('Fall 4 (AC-5): Start, Login, Cockpit und Konto – beide Sprachen ohne Mischung', async ({ browser }) => {
		for (const lang of ['de', 'en'] as const) {
			const besucher = await (await neuerKontext(browser)).newPage();
			await besucher.goto('/login');
			if (lang === 'en') await waehleBesucherSprache(besucher, 'en');
			await pruefeSprache(besucher, lang, 'Login');
			await besucher.goto('/');
			await pruefeSprache(besucher, lang, 'Start');
			await besucher.context().close();
			for (const pfad of ['/', '/account']) {
				await (seite[lang] as Page).goto(pfad);
				await pruefeSprache(seite[lang] as Page, lang, pfad);
			}
		}
	});

	test('Fall 5 (AC-6): 24 Screenshot-Dateien, auffaellige Elemente als Anhang', async ({ browser }) => {
		test.setTimeout(180_000);
		mkdirSync(ARTEFAKTE, { recursive: true });
		const auffaellig: string[] = [];
		for (const lang of ['de', 'en'] as const) {
			for (const breite of [375, 1280]) {
				const besucher = await (await neuerKontext(browser, { viewport: { width: breite, height: 900 } })).newPage();
				const nutzer = seite[lang] as Page;
				await nutzer.setViewportSize({ width: breite, height: 900 });
				const flaechen: [string, Page, () => Promise<unknown>][] = [
					['login', besucher, async () => { await besucher.goto('/login'); if (lang === 'en') await waehleBesucherSprache(besucher, 'en'); }],
					['start', besucher, () => besucher.goto('/')],
					['cockpit', nutzer, () => nutzer.goto('/')],
					['trip-hub', nutzer, () => hubOeffnen(nutzer, 'route', (hub[lang] as Record<HubKind, string>).route)],
					['compare-hub', nutzer, () => hubOeffnen(nutzer, 'vergleich', (hub[lang] as Record<HubKind, string>).vergleich)],
					['konto', nutzer, () => nutzer.goto('/account')]
				];
				for (const [name, page, oeffne] of flaechen) {
					await oeffne();
					await expect(page.locator('html')).toHaveAttribute('lang', lang);
					const datei = `${ARTEFAKTE}${name}.${lang}.${breite}.png`;
					await page.screenshot({ path: datei, fullPage: true });
					const eng = await page.evaluate(() =>
						[...document.querySelectorAll('button, [role="tab"], .pill, [class*="pill"], [class*="chip"]')]
							.filter((e) => e.scrollWidth > e.clientWidth + 1)
							.map((e) => (e as HTMLElement).innerText.trim().slice(0, 60))
					);
					auffaellig.push(...eng.map((t) => `${name}.${lang}.${breite}: ${t}`));
				}
				await besucher.context().close();
			}
		}
		for (const name of ['start', 'login', 'cockpit', 'trip-hub', 'compare-hub', 'konto'])
			for (const lang of ['de', 'en'])
				for (const breite of [375, 1280]) expect(statSync(`${ARTEFAKTE}${name}.${lang}.${breite}.png`).size).toBeGreaterThan(0);
		await test.info().attach('auffaellige-elemente', { body: auffaellig.join('\n') || '(keine)', contentType: 'text/plain' });
	});
});
