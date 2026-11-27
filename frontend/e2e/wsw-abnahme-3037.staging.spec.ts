// Abnahme — Issue #3037: Tabelle „Was steht wo“ (Reiter Wetter, Bau #3122) gegen das Soll-Bild Fassung 4.
// Spec: docs/specs/modules/feat_3037_was_steht_wo_abnahme.md — AC-1 (Ganzseitenbilder Staging), AC-2 (Ein-Ort-Texte),
// AC-3 (Handy 390 px EN: fünf Haken-Spalten ohne seitliches Scrollen), AC-4 (Mockup-Gegenbilder), AC-9 (Aufräumen,
// Sprache DE, zweites Konto sieht das Wegwerf-Abo nicht).
// Soll: docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html (Kontextknöpfe data-ctx trip/orte/ort1).
//
// Prüfkonto: Login per POST /api/auth/login (e2e/pruefkontoZugang.ts: GZ_PRUEFKONTO_* vor GZ_AUTH_*);
// Trip/Orte (drei Orte) = seedIds(): ELEMENTLISTE_TRIP_ID/ELEMENTLISTE_ORTE_ID, sonst Lookup des Seeds nach dem Login;
// ein Ort = Wegwerf-Abo mit Präfix „WSW-3037-“.
// Anmeldung genau EINMAL je Konto (beforeAll bzw. beim ersten Zweitkonto-Zugriff); die Cookies werden in jeden
// Test-Kontext übernommen — wiederholte Logins liefen in HTTP 429 (Adversary F005).
//
// Zweitkonto (AC-9, PFLICHT): zweitkontoZugang() — GZ_ZWEITKONTO_USER/GZ_ZWEITKONTO_PASS, sonst GZ_AUTH_* (geteiltes
// Staging-Konto, z. B. über spec-run), aber nie das Prüfkonto. Fehlt es, schlägt der ort1-Test (und der AC-9-Test)
// mit klarer Meldung fehl, es gibt keinen stillen Skip. Zeigt GZ_AUTH_* auf das Prüfkonto (Server-Weg), muss
// GZ_ZWEITKONTO_* gesetzt sein — beide Konten müssen verschieden sein (geprüft).
// Kontexte über ABNAHME_KONTEXTE (Default "orte,ort1,trip"); der Trip kann so nach #3364 separat laufen.
// Bilder nach $BILD_DIR (Default docs/artifacts/abnahme-3037-was-steht-wo/bilder): mockup-<ctx>-de-<breite>.png und
// staging-<ctx>-<lang>-<breite>.png — passend zu scripts/soll_ist_bild.py.
//
// Nur in /e2e-verify gegen Staging, nie gegen Produktion, nicht in der CI-Positivliste.
//   cd frontend && ABNAHME_KONTEXTE=orte,ort1 npx playwright test --config playwright.3037-wsw-abnahme.staging.config.ts

import { test, expect, request as pwRequest, type APIRequestContext, type Locator, type Page, type TestInfo } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ganzseite } from './ganzseitenaufnahme';
import { oeffneKarte, seedAbo, type Abo, type HubKind, type Json } from './was-steht-wo.helpers';
import { pruefkontoZugang, seedIds, zweitkontoZugang } from './pruefkontoZugang.ts';

const HIER = path.dirname(fileURLToPath(import.meta.url));
const MOCKUP = 'file://' + path.resolve(HIER, '..', '..', 'docs', 'context', 'einstellungen_neu', 'seiten', 'mockup-hub-fassung4.html');
const ARTEFAKTE = path.resolve(HIER, '..', '..', 'docs', 'artifacts', 'abnahme-3037-was-steht-wo', 'bilder');
const PRAEFIX = 'WSW-3037-';

type Lang = 'de' | 'en';
type Ctx = 'trip' | 'orte' | 'ort1';
const SPRACHEN: Lang[] = ['de', 'en'];
const VIEWPORTS = [
	{ width: 1280, height: 900 },
	{ width: 390, height: 844 }
] as const;
const ALLE_KONTEXTE: Ctx[] = ['trip', 'orte', 'ort1'];
const KIND: Record<Ctx, HubKind> = { trip: 'route', orte: 'vergleich', ort1: 'vergleich' };
/** Orte-Metriken wie im Mockup (Vorbild was-steht-wo-bildabgleich.staging.spec.ts). */
const ORTE_METRIKEN = ['temp_max_c', 'temp_min_c', 'wind_max_kmh', 'gust_max_kmh', 'precip_sum_mm', 'sunny_hours_h', 'cloud_avg_pct', 'humidity_avg_pct'];
/** AC-2: Mehrzahl-Formulierungen, die bei genau einem Ort nicht erscheinen dürfen. */
const VERBOTEN_EIN_ORT = ['alle Orte', '1 Orte', 'all locations', '1 locations', 'deine Orte', 'your locations'];
/** Titel im Mockup-Kopf (#head) je Kontext (mockup-hub-fassung4.html, const CTX) — Nachweis, dass der Kontext aktiv ist. */
const MOCKUP_TITEL: Record<Ctx, string> = { trip: 'GR221 Mallorca', orte: 'Münsterland', ort1: 'Tecklenburg' };

function gewaehlteKontexte(): Ctx[] {
	const roh = (process.env.ABNAHME_KONTEXTE ?? 'orte,ort1,trip').split(',').map((s) => s.trim()).filter(Boolean);
	const unbekannt = roh.filter((c) => !ALLE_KONTEXTE.includes(c as Ctx));
	if (unbekannt.length) throw new Error(`ABNAHME_KONTEXTE: unbekannte Kontexte ${unbekannt.join(', ')} (erlaubt: ${ALLE_KONTEXTE.join(', ')})`);
	return roh as Ctx[];
}
const KONTEXTE = gewaehlteKontexte();

test.describe.configure({ mode: 'serial' });

// ── Werkzeuge ────────────────────────────────────────────────────────────────

function bildOrdner(): string {
	const d = process.env.BILD_DIR ?? ARTEFAKTE;
	mkdirSync(d, { recursive: true });
	return d;
}

function alsListe(x: unknown): Json[] {
	return Array.isArray(x) ? x : [];
}

/** Anmeldung per API; das Cookie gilt für die Seite desselben Kontexts. */
async function anmelden(api: APIRequestContext, user: string | undefined, pass: string | undefined, wer: string): Promise<void> {
	if (!user || !pass) throw new Error(`#3037: ${wer} — Zugangsdaten fehlen (Umgebungsvariablen nicht gesetzt)`);
	const r = await api.post('/api/auth/login', { data: { username: user, password: pass } });
	if (!r.ok()) throw new Error(`#3037: ${wer} — Login fehlgeschlagen, HTTP ${r.status()}`);
}

type Cookies = Awaited<ReturnType<APIRequestContext['storageState']>>['cookies'];

/** Eigener API-Zugang (Basic-Auth und Staging-Adresse aus der Konfiguration), optional mit vorhandenen Cookies. */
function neuerZugang(info: TestInfo, cookies?: Cookies): Promise<APIRequestContext> {
	const use = info.project.use;
	return pwRequest.newContext({
		baseURL: use.baseURL,
		httpCredentials: use.httpCredentials,
		ignoreHTTPSErrors: true,
		...(cookies ? { storageState: { cookies, origins: [] } } : {})
	});
}

/** Meldet ein Konto einmal an und liefert seine Cookies (F005: nur ein Login je Konto und Lauf). */
async function einmalAnmelden(info: TestInfo, user: string | undefined, pass: string | undefined, wer: string): Promise<Cookies> {
	const api = await neuerZugang(info);
	try {
		await anmelden(api, user, pass, wer);
		return (await api.storageState()).cookies;
	} finally {
		await api.dispose();
	}
}

/** Cookies des Prüfkontos (beforeAll) und des Zweitkontos (beim ersten Zugriff). */
let pruefkontoCookies: Cookies | null = null;
let zweitkontoCookies: Cookies | null = null;
/** Seed-IDs des Prüfkontos (beforeAll, seedIds). */
let seed: { route: string; vergleich: string } | null = null;

/** AC-9: Zugangsdaten des Zweitkontos — Pflicht, sonst klarer Fehler (F003, kein stiller Skip). */
function zweitkontoDaten(): { user: string; pass: string } {
	return zweitkontoZugang();
}

async function sprache(api: APIRequestContext, lang: Lang): Promise<void> {
	const res = await api.put('/api/auth/profile', { data: { language: lang } });
	expect(res.ok(), `Sprache ${lang}: HTTP ${res.status()}`).toBeTruthy();
}

/** Seed-ID des Kontexts; ort1 bekommt sein Wegwerf-Abo im Test. */
function seedId(ctx: Ctx): string {
	if (!seed) throw new Error(`#3037: Seed-IDs nicht bestimmt (beforeAll) — Kontext ${ctx} nicht prüfbar`);
	return ctx === 'trip' ? seed.route : seed.vergleich;
}

/** Vor dem Anlegen: freie Quota für einen Vergleich und einen Ort, sonst klarer Abbruch. */
async function pruefeQuota(api: APIRequestContext): Promise<void> {
	const profil = await api.get('/api/auth/profile');
	expect(profil.ok(), `Profil: HTTP ${profil.status()}`).toBeTruthy();
	const q = ((await profil.json()) as Json)?.quota;
	if (!q) return;
	if (typeof q.compare_presets === 'number') {
		const aktiv = alsListe(await (await api.get('/api/compare/presets')).json()).filter((p) => !p.archived_at).length;
		if (aktiv >= q.compare_presets) throw new Error(`#3037: Quota erschöpft — ${aktiv}/${q.compare_presets} Vergleiche im Prüfkonto, Wegwerf-Abo nicht anlegbar`);
	}
	if (typeof q.locations === 'number') {
		const orte = alsListe(await (await api.get('/api/locations')).json()).length;
		if (orte >= q.locations) throw new Error(`#3037: Quota erschöpft — ${orte}/${q.locations} Orte im Prüfkonto, Wegwerf-Ort nicht anlegbar`);
	}
}

async function wegwerfAbo(api: APIRequestContext): Promise<Abo> {
	await pruefeQuota(api);
	try {
		return await seedAbo(api, 'vergleich', { orte: 1, metriken: ORTE_METRIKEN, oben: { name: `${PRAEFIX}${Date.now()}` } });
	} catch (e) {
		const text = String(e);
		if (/HTTP (409|403)/.test(text)) throw new Error(`#3037: Wegwerf-Abo abgelehnt (Quota/Rechte) — ${text}`);
		throw e;
	}
}

/** Entfernt alle Vergleiche mit Präfix und ihre Test-Orte (E2E-Präfix). Liefert Restbefunde. */
async function raeumePraefixAuf(api: APIRequestContext): Promise<string[]> {
	const befunde: string[] = [];
	const presets = await api.get('/api/compare/presets');
	if (!presets.ok()) return [`GET /api/compare/presets: HTTP ${presets.status()}`];
	const orte = alsListe(await (await api.get('/api/locations')).json().catch(() => []));
	const testOrt = new Set(orte.filter((o) => String(o.name ?? '').startsWith('E2E-GZ-')).map((o) => String(o.id)));
	for (const p of alsListe(await presets.json()).filter((x) => String(x.name ?? '').startsWith(PRAEFIX))) {
		const d = await api.delete(`/api/compare/presets/${p.id}`);
		if (!d.ok() && d.status() !== 404) befunde.push(`DELETE Vergleich ${p.id}: HTTP ${d.status()}`);
		for (const o of alsListe(p.location_ids).map(String).filter((id) => testOrt.has(id))) {
			const r = await api.delete(`/api/locations/${o}`);
			if (!r.ok() && r.status() !== 404) befunde.push(`DELETE Ort ${o}: HTTP ${r.status()}`);
		}
	}
	return befunde;
}

/** AC-9: das zweite Konto sieht das Wegwerf-Abo nicht (Zweitkonto Pflicht, siehe zweitkontoDaten). */
async function zweitkontoSiehtNichts(info: TestInfo, aboId: string | null): Promise<void> {
	const { user, pass } = zweitkontoDaten();
	zweitkontoCookies ??= await einmalAnmelden(info, user, pass, 'Zweitkonto');
	const api = await neuerZugang(info, zweitkontoCookies);
	try {
		const r = await api.get('/api/compare/presets');
		expect(r.ok(), `Zweitkonto GET Vergleiche: HTTP ${r.status()}`).toBeTruthy();
		const fremd = alsListe(await r.json()).filter((p) => p.id === aboId || String(p.name ?? '').startsWith(PRAEFIX));
		expect(fremd.map((p) => p.id), 'AC-9: Zweitkonto sieht das Wegwerf-Abo').toEqual([]);
	} finally {
		await api.dispose();
	}
}

/** AC-1: Karte und Tabelle sichtbar, Ganzseitenbild mit Bildbreite = Fensterbreite. */
async function aufnahme(page: Page, karte: Locator, ctx: Ctx, lang: Lang, breite: number): Promise<void> {
	await expect(karte, `AC-1 ${ctx} ${lang} ${breite}: Karte nicht sichtbar`).toBeVisible();
	await expect(karte.locator('[data-testid="was-steht-wo-tabelle"]').first(), `AC-1 ${ctx} ${lang} ${breite}: Tabelle nicht sichtbar`).toBeVisible();
	const masse = await ganzseite(page, path.join(bildOrdner(), `staging-${ctx}-${lang}-${breite}.png`));
	expect(masse.breite, `AC-1 ${ctx} ${lang}: Bildbreite`).toBe(breite);
}

/** AC-2 (F004): Bereichsname an der Stelle, die den Bereich benennt — der Eyebrow im Seitenkopf des Hubs
 *  („Orte“ bzw. „Orte · Region“, Schlüssel aktionen.kopf.eltern_orte/eyebrow_orte), NICHT die Reiterleiste.
 *  textContent statt innerText, weil der Eyebrow per CSS in Großbuchstaben steht.
 *  Verbotsliste gegen Seitenkopf des Hubs, Reiter Wetter und Karte „Was steht wo“ (nicht die ganze Seite). */
async function einOrtTexte(page: Page, karte: Locator, lang: Lang): Promise<void> {
	const erwartet = lang === 'de' ? 'Orte' : 'Locations';
	const eyebrow = page.locator('[data-testid="hub-kopf-eyebrow"]:visible').first();
	await expect(eyebrow, `AC-2 ${lang}: Eyebrow des Hub-Kopfs fehlt`).toBeVisible();
	const bereich = ((await eyebrow.textContent()) ?? '').split(' · ')[0].trim();
	expect(bereich, `AC-2 ${lang}: Bereichsname im Hub-Kopf`).toBe(erwartet);
	const kopf = page.locator('.hub-kopf[data-seite="hub"]:visible').first();
	const reiter = page.locator('[data-testid="wetter-tab"]:visible').first();
	await expect(kopf, `AC-2 ${lang}: Hub-Kopf fehlt`).toBeVisible();
	await expect(reiter, `AC-2 ${lang}: Reiter Wetter fehlt`).toBeVisible();
	const texte = [await kopf.innerText(), await reiter.innerText(), await karte.innerText()];
	const klein = texte.join('\n').toLowerCase();
	expect(VERBOTEN_EIN_ORT.filter((v) => klein.includes(v.toLowerCase())), `AC-2 ${lang}: Mehrzahl-Formulierung bei einem Ort`).toEqual([]);
}

/** AC-3: fünf Haken-Spalten nebeneinander im Kartenrahmen, kein seitlicher Überlauf. */
async function handySpalten(page: Page, karte: Locator): Promise<void> {
	const koepfe = karte.locator('[data-slot="et-kopf"] [data-slot="et-kopf-stelle"]');
	const ids = await koepfe.evaluateAll((els) => els.map((e) => e.getAttribute('data-stelle')));
	expect(ids.length, `AC-3: Haken-Spalten im Kopf (${ids.join(', ')})`).toBe(5);
	const rahmen = await karte.boundingBox();
	expect(rahmen, 'AC-3: Kartenrahmen ohne Maße').not.toBeNull();
	const boxen = await koepfe.evaluateAll((els) => els.map((e) => { const r = e.getBoundingClientRect(); return { x: r.left, r: r.right, o: r.top, u: r.bottom }; }));
	const ausserhalb = boxen.filter((b) => b.x < rahmen!.x - 1 || b.r > rahmen!.x + rahmen!.width + 1);
	expect(ausserhalb, 'AC-3: Spaltenkopf außerhalb des Kartenrahmens').toEqual([]);
	expect(Math.max(...boxen.map((b) => b.o)) < Math.min(...boxen.map((b) => b.u)), 'AC-3: Spaltenköpfe nicht in einer Zeile').toBeTruthy();
	const ueberlauf = await page.evaluate(() => {
		const k = document.querySelector<HTMLElement>('[data-testid="was-steht-wo"]');
		const t = k?.querySelector<HTMLElement>('[data-slot="einstell-tabelle"]');
		const d = document.documentElement;
		return [
			['Karte', k?.scrollWidth ?? -1, k?.clientWidth ?? -1],
			['Tabelle', t?.scrollWidth ?? -1, t?.clientWidth ?? -1],
			['Seite', d.scrollWidth, d.clientWidth]
		].filter(([, s, c]) => (s as number) > (c as number) || (s as number) < 0);
	});
	expect(ueberlauf, 'AC-3: seitlicher Überlauf (scrollWidth > clientWidth)').toEqual([]);
}

// ── Vorbedingungen, Login, Aufräumen ────────────────────────────────────────

test.beforeAll(async ({}, info) => {
	const konto = pruefkontoZugang();
	// F005: einmal anmelden, Cookies in jeden Test-Kontext übernehmen (kein Login je Test → kein HTTP 429).
	pruefkontoCookies ??= await einmalAnmelden(info, konto.user, konto.pass, 'Prüfkonto');
	if (KONTEXTE.some((ctx) => ctx !== 'ort1')) {
		const api = await neuerZugang(info, pruefkontoCookies);
		try {
			seed = await seedIds(api);
		} finally {
			await api.dispose();
		}
	}
});

test.beforeEach(async ({ context }) => {
	if (!pruefkontoCookies) throw new Error('#3037: Prüfkonto nicht angemeldet (beforeAll)');
	await context.addCookies(pruefkontoCookies);
});

test.afterAll(async ({}, info) => {
	if (!pruefkontoCookies) return;
	const api = await neuerZugang(info, pruefkontoCookies);
	try {
		for (const b of await raeumePraefixAuf(api)) console.error(`#3037 Aufräumen: ${b}`);
		const r = await api.put('/api/auth/profile', { data: { language: 'de' } });
		if (!r.ok()) console.error(`#3037 Aufräumen: Sprache DE nicht gesetzt, HTTP ${r.status()}`);
	} finally {
		await api.dispose();
	}
});

// ── AC-4: Mockup-Gegenbilder (nur Deutsch) ──────────────────────────────────

test('#3037 AC-4: Mockup Fassung 4 — trip/orte/ort1 × 1280/390, ganze Seite', async ({ browser }) => {
	for (const vp of VIEWPORTS) {
		const m = await browser.newPage({ viewport: vp });
		try {
			await m.goto(MOCKUP);
			for (const ctx of ALLE_KONTEXTE) {
				const geklickt = await m.evaluate((c) => {
					const knopf = document.querySelector<HTMLElement>(`[data-ctx="${c}"]`);
					knopf?.click();
					return !!knopf;
				}, ctx);
				expect(geklickt, `AC-4 Mockup: Kontextknopf data-ctx="${ctx}" fehlt`).toBeTruthy();
				// F006: Kontext wirklich aktiv — Knopf markiert und Kopf zeigt den Titel dieses Kontexts.
				await expect(m.locator(`[data-ctx="${ctx}"]`), `AC-4 Mockup ${ctx}: Kontextknopf nicht aktiv`).toHaveClass(/(^|\s)on(\s|$)/);
				await expect(m.locator('#head'), `AC-4 Mockup ${ctx}: Kopf zeigt anderen Kontext`).toContainText(MOCKUP_TITEL[ctx]);
				await expect(m.locator('[data-abschnitt="was-steht-wo"]').first(), `Mockup ${ctx}: Karte fehlt`).toBeVisible();
				const masse = await ganzseite(m, path.join(bildOrdner(), `mockup-${ctx}-de-${vp.width}.png`));
				expect(masse.breite, `AC-4 Mockup ${ctx}: Bildbreite`).toBe(vp.width);
			}
		} finally {
			await m.close();
		}
	}
});

// ── AC-1/AC-2/AC-3: Staging je Kontext × DE/EN × 1280/390 ──────────────────

for (const ctx of KONTEXTE) {
	test(`#3037 AC-1 Staging ${ctx}: Reiter Wetter × DE/EN × 1280/390${ctx === 'ort1' ? ' (AC-2, AC-9)' : ctx === 'orte' ? ' (AC-3)' : ''}`, async ({ page }, info) => {
		const api = page.request;
		let abo: Abo | null = null;
		try {
			if (ctx === 'ort1') {
				zweitkontoDaten(); // F003: fehlt das Zweitkonto, klar scheitern, bevor ein Wegwerf-Abo entsteht
				abo = await wegwerfAbo(api);
				await zweitkontoSiehtNichts(info, abo.id);
			}
			const id = abo?.id ?? seedId(ctx);
			for (const lang of SPRACHEN) {
				await sprache(api, lang);
				for (const vp of VIEWPORTS) {
					await page.setViewportSize(vp);
					const karte = await oeffneKarte(page, KIND[ctx], id);
					await aufnahme(page, karte, ctx, lang, vp.width);
					if (ctx === 'ort1') await einOrtTexte(page, karte, lang);
					if (ctx === 'orte' && lang === 'en' && vp.width === 390) await handySpalten(page, karte);
				}
			}
		} finally {
			await abo?.aufraeumen();
			await sprache(api, 'de');
		}
	});
}

// ── AC-9: Wegwerf-Abo entfernt, Sprache DE, Zweitkonto ohne Abo ─────────────

test('#3037 AC-9: kein Wegwerf-Abo mehr, Prüfkonto-Sprache DE', async ({ page }, info) => {
	const api = page.request;
	expect(await raeumePraefixAuf(api), 'AC-9: Aufräumen').toEqual([]);
	await sprache(api, 'de');
	const profil = await api.get('/api/auth/profile');
	expect(profil.ok(), `Profil: HTTP ${profil.status()}`).toBeTruthy();
	expect(((await profil.json()) as Json)?.language, 'AC-9: Prüfkonto-Sprache').toBe('de');
	const rest = alsListe(await (await api.get('/api/compare/presets')).json()).filter((p) => String(p.name ?? '').startsWith(PRAEFIX));
	expect(rest.map((p) => p.id), 'AC-9: Wegwerf-Abo noch vorhanden').toEqual([]);
	await zweitkontoSiehtNichts(info, null);
});
