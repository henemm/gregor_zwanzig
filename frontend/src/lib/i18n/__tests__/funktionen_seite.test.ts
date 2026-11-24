// Issue #3319 / #3320 — oeffentliche Funktionsuebersicht /funktionen (Uebersicht mit
// Themenkacheln) + neun Unterseiten /funktionen/<slug> und Level-Kurzform auf der
// Startseite, ECHT gerendert (svelte/server), je Sprache ueber den Katalog.
// Spec: docs/specs/modules/oeffentliche_doku_3319.md (v1.1, Unterseiten-Struktur)
//
// AC-2 (Startseite: Level-Kurzform + Links), AC-3 (Level-Datei einzige Zahlenquelle),
// AC-4 (Loader ohne API/Nutzerdaten, unbekannter Slug 404), AC-6 (neun Unterseiten,
// Kacheln, 14 Inventarpunkte genau einmal, DE/EN je Schluessel, Sprache),
// AC-7 (keine Konnektor/Admin/Design-Texte, keine Empfehlungen), AC-10 (Befehlsliste
// = Hilfe-Quelle mit Gegenprobe, Kanalhinweis), AC-12 (Brotkrumen, Themen-Navigation,
// Weiter/Zurueck, Registrierungsaufruf, eigene Titel/Meta-Beschreibung).
// Bilder (AC-8): textkatalog.test.ts.
//
// Vertrag der gerenderten Seiten (Test-Anker):
//   Uebersicht:  <a data-testid="kachel" href="/funktionen/<slug>"> je Unterseite
//   Unterseite:  <section data-inventar="<id>"> je Inventarpunkt,
//                <nav data-testid="brotkrumen">, <nav data-testid="themen-navigation">
//                (aktuelle Seite aria-current="page"), <a data-testid="seite-zurueck">,
//                <a data-testid="seite-weiter">, <a href="/register">,
//                <svelte:head> mit <title> und <meta name="description">
//   Katalog:     funktionen.seite.<slug>.titel | .kachel, funktionen.<inventar>.titel
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/i18n/__tests__/funktionen_seite.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { locale, trFor, type MessageKey } from '../index.ts';
import { de } from '../messages/de/index.ts';
import { en } from '../messages/en/index.ts';
import { translate, type Kataloge } from '../translate.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const LIB = path.resolve(HERE, '../..');
const FRONTEND = path.resolve(LIB, '../..');
const ROUTES = path.join(FRONTEND, 'src', 'routes');
const base = pathToFileURL(FRONTEND + '/').href;
const hook = (p: string) => register(pathToFileURL(p).href, base);
hook(path.join(FRONTEND, 'test-app-environment-stub-hooks.mjs'));
hook(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs'));
hook(path.join(LIB, 'components/trip-new/__tests__/ssrRunesHook.mjs'));

const { render } = await import('svelte/server');
const ladeKomponente = async (abs: string) => (await import(pathToFileURL(abs).href)).default;

type Lang = 'de' | 'en';
const SPRACHEN: Lang[] = ['de', 'en'];
const katalogDe = de as Record<string, string>;
const katalogEn = en as Record<string, string>;
const keys = Object.keys(katalogDe) as MessageKey[];
const txt = (lang: Lang, k: string) => trFor(lang, k as MessageKey);

// ─── Seitenliste (einzige Quelle der Unterseiten) ───────────────────────────
type Seite = { slug: string; inventar: readonly string[] };
let SEITEN_ROH: unknown = undefined;
let ladeFehler = '';
try {
	({ FUNKTIONEN_SEITEN: SEITEN_ROH } = await import(pathToFileURL(path.join(LIB, 'funktionen_seiten.ts')).href));
} catch (e) {
	ladeFehler = String(e);
}
function seiten(): Seite[] {
	assert.ok(Array.isArray(SEITEN_ROH), `frontend/src/lib/funktionen_seiten.ts fehlt/exportiert FUNKTIONEN_SEITEN nicht ${ladeFehler}`);
	return SEITEN_ROH as Seite[];
}

/** Soll laut Spec, Implementation Details „Seitenstruktur“ (Reihenfolge + Zuordnung). */
const SOLL_ZUORDNUNG: ReadonlyArray<[string, readonly string[]]> = [
	['trips', ['cockpit', 'trip_anlegen', 'trip_hub', 'archiv']],
	['briefings', ['briefings', 'wetter']],
	['alarme', ['alarme']],
	['ortsvergleich', ['ortsvergleich']],
	['kanaele', ['kanaele', 'zustellung']],
	['befehle', ['befehle']],
	['wetterdaten', ['wetterdaten']],
	['konto', ['konto', 'app']],
	['level', []]
];
const SOLL_SLUGS = SOLL_ZUORDNUNG.map(([s]) => s);

/** Inventar 1–14 (Spec, Implementation Details „Inhalt“). */
const INVENTAR = [
	'cockpit',
	'trip_anlegen',
	'trip_hub',
	'briefings',
	'wetter',
	'zustellung',
	'alarme',
	'ortsvergleich',
	'kanaele',
	'befehle',
	'archiv',
	'konto',
	'app',
	'wetterdaten'
] as const;

// ─── Level-Datei ────────────────────────────────────────────────────────────
type Level = 'free' | 'standard' | 'premium';
type LevelEintrag = Record<string, number | boolean | null>;
const LEVEL_DATEI = path.join(LIB, 'level_grenzen.json');
const ladeLevel = (): Record<Level, LevelEintrag> => JSON.parse(readFileSync(LEVEL_DATEI, 'utf-8'));
const ZAHLEN_FELDER = [
	'trips',
	'ortsvergleiche',
	'orte',
	'sms_pro_tag',
	'premium_sms_pro_tag',
	'alarme_pro_tag'
] as const;

// ─── HTML-Helfer ────────────────────────────────────────────────────────────
const ent = (s: string) =>
	s.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>');
const nurText = (html: string) => ent(html.replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ');
const attr = (tag: string, a: string) => ent(tag.match(new RegExp(`\\b${a}="([^"]*)"`))?.[1] ?? '');

type Gerendert = { body: string; head: string };

async function renderUebersicht(lang: Lang): Promise<Gerendert> {
	locale.set(lang);
	const Seite = await ladeKomponente(path.join(ROUTES, 'funktionen', '+page.svelte'));
	const r = render(Seite, { props: { data: { oeffentlich: true, lang } } });
	return { body: r.body, head: r.head };
}

const UNTERSEITE = path.join(ROUTES, 'funktionen', '[thema]', '+page.svelte');
async function renderUnterseite(lang: Lang, slug: string): Promise<Gerendert> {
	assert.ok(existsSync(UNTERSEITE), 'frontend/src/routes/funktionen/[thema]/+page.svelte fehlt');
	locale.set(lang);
	const Seite = await ladeKomponente(UNTERSEITE);
	const r = render(Seite, { props: { data: { oeffentlich: true, lang, slug } } });
	return { body: r.body, head: r.head };
}

async function renderStartseite(lang: Lang): Promise<string> {
	locale.set(lang);
	const Seite = await ladeKomponente(path.join(ROUTES, '_start', 'Startseite.svelte'));
	return render(Seite, { props: {} }).body;
}

/** Innerer HTML-Inhalt des ersten `<nav data-testid="<id>">`. */
function navHtml(html: string, id: string): string {
	const m = html.match(new RegExp(`<nav\\b[^>]*data-testid="${id}"[^>]*>([\\s\\S]*?)<\\/nav>`));
	assert.ok(m, `<nav data-testid="${id}"> fehlt`);
	return m![1];
}

/** Inhalt von `<section data-inventar="<id>">` bis zum naechsten <section bzw. Seitenende. */
function inventarHtml(html: string, id: string): string {
	const start = html.search(new RegExp(`<section\\b[^>]*\\bdata-inventar="${id}"`));
	assert.ok(start >= 0, `Abschnitt data-inventar="${id}" fehlt`);
	const rest = html.slice(start + 1);
	const ende = rest.search(/<section\b/);
	return ende < 0 ? rest : rest.slice(0, ende);
}

/** Alle `<a …>…</a>` mit gegebenem data-testid: href + Text. */
function linksMitTestid(html: string, id: string): { href: string; text: string; tag: string }[] {
	return [...html.matchAll(/<a\b([^>]*)>([\s\S]*?)<\/a>/g)]
		.filter((m) => new RegExp(`\\bdata-testid="${id}"`).test(m[1]))
		.map((m) => ({ href: attr(m[1], 'href'), text: nurText(m[2]).trim(), tag: m[1] }));
}

/** Zellen-Texte je Zeile `<tr data-feld="…">` der Tabelle `data-testid="level-tabelle"`. */
function levelZeilen(html: string): Record<string, string[]> {
	const t = html.match(/<table\b[^>]*data-testid="level-tabelle"[^>]*>([\s\S]*?)<\/table>/);
	assert.ok(t, 'Level-Tabelle (data-testid="level-tabelle") fehlt');
	const zeilen: Record<string, string[]> = {};
	for (const m of t![1].matchAll(/<tr\b[^>]*data-feld="([^"]+)"[^>]*>([\s\S]*?)<\/tr>/g)) {
		zeilen[m[1]] = [...m[2].matchAll(/<td\b[^>]*>([\s\S]*?)<\/td>/g)].map((c) => nurText(c[1]).trim());
	}
	return zeilen;
}

function pruefeLevelZeilen(zeilen: Record<string, string[]>, felder: readonly string[], lang: Lang) {
	const d = ladeLevel();
	for (const f of felder) {
		const z = zeilen[f];
		assert.ok(z, `${lang}: Zeile ${f} fehlt in der Level-Tabelle`);
		assert.equal(z.length, 3, `${lang}: Zeile ${f} braucht drei Level-Spalten`);
		(['free', 'standard', 'premium'] as Level[]).forEach((lv, i) => {
			const soll = d[lv][f];
			if (soll === null) {
				assert.ok(z[i].length > 0 && !/\d|null/.test(z[i]), `${lang}: ${f}/${lv} muss „unbegrenzt“ zeigen, ist "${z[i]}"`);
			} else {
				assert.match(z[i], new RegExp(`(^|\\D)${soll}(\\D|$)`), `${lang}: ${f}/${lv} soll ${soll} zeigen, ist "${z[i]}"`);
			}
		});
	}
}

const titelVon = (head: string) => nurText(head.match(/<title>([\s\S]*?)<\/title>/)?.[1] ?? '').trim();
const beschreibungVon = (head: string) => {
	const tag = head.match(/<meta\b[^>]*\bname="description"[^>]*>/)?.[0] ?? '';
	return attr(tag, 'content').trim();
};

after(() => locale.set('de'));

// ════════════════════════════════════════════════════════════════════════════
describe('AC-3/AC-2: Level-Datei ist die einzige Zahlenquelle', () => {
	test('Level-Datei existiert mit free/standard/premium', () => {
		assert.ok(existsSync(LEVEL_DATEI), 'frontend/src/lib/level_grenzen.json fehlt');
		assert.deepEqual(Object.keys(ladeLevel()).sort(), ['free', 'premium', 'standard']);
	});
	test('Kataloge enthalten keine Level-Zahlen als Klartext (nur Platzhalter)', () => {
		const level = keys.filter((k) => k.startsWith('level.') || k.startsWith('start.level.'));
		assert.ok(level.length > 0, 'keine level.*-/start.level.*-Texte im Katalog');
		for (const lang of SPRACHEN) {
			for (const k of level) assert.doesNotMatch(txt(lang, k), /\b(15|50|200|30)\b/, `${lang} ${k}: Zahl im Text`);
		}
	});
});

describe('AC-2: Startseite zeigt die Level-Kurzform und verlinkt Uebersicht und Level-Seite', () => {
	for (const lang of SPRACHEN) {
		test(`${lang}: Kurztabelle mit echten Grenzen, Wechselweg, kein Preis, Links /funktionen und /funktionen/level`, async () => {
			const html = await renderStartseite(lang);
			pruefeLevelZeilen(levelZeilen(html), ZAHLEN_FELDER, lang);
			const text = nurText(html);
			assert.match(text, /Free/);
			assert.match(text, /Standard/);
			assert.match(text, /Premium/);
			assert.match(html, /<a\b[^>]*href="\/funktionen"/, `${lang}: Link zu /funktionen fehlt`);
			assert.match(html, /<a\b[^>]*href="\/funktionen\/level"/, `${lang}: Link zur Level-Seite fehlt`);
			assert.doesNotMatch(text, /€|\$|EUR\b|Preis|price|kostet|costs|bezahl|payment|Abo\b|subscription/i, `${lang}: Preis-/Bezahltext`);
			if (lang === 'de') {
				assert.match(text, /Registrierung/);
				assert.match(text, /Antrag/);
				assert.match(text, /Betreiber/);
			} else {
				assert.match(text, /sign[- ]?up|registration/i);
				assert.match(text, /request/i);
				assert.match(text, /operator/i);
			}
		});
	}
});

// ════════════════════════════════════════════════════════════════════════════
describe('AC-4: Loader rufen keine API und liefern keine Nutzerdaten', () => {
	async function mitFetchWaechter<T>(fn: (fetch: typeof globalThis.fetch) => Promise<T>): Promise<number> {
		let aufrufe = 0;
		const fetch = (async () => {
			aufrufe++;
			throw new Error('kein API-Aufruf erlaubt');
		}) as unknown as typeof globalThis.fetch;
		const orig = globalThis.fetch;
		globalThis.fetch = fetch;
		try {
			await fn(fetch);
		} finally {
			globalThis.fetch = orig;
		}
		return aufrufe;
	}

	test('Uebersicht: load liefert nur oeffentlich + lang', async () => {
		const mod = await import(pathToFileURL(path.join(ROUTES, 'funktionen', '+page.server.ts')).href);
		const aufrufe = await mitFetchWaechter(async (fetch) => {
			for (const userId of [undefined, 'nutzer-a']) {
				const r = await mod.load({ locals: { lang: 'en', userId }, fetch, cookies: { get: () => undefined } });
				assert.deepEqual(Object.keys(r).sort(), ['lang', 'oeffentlich']);
				assert.equal(r.oeffentlich, true);
				assert.equal(r.lang, 'en');
			}
		});
		assert.equal(aufrufe, 0);
	});

	test('Unterseite: load liefert nur oeffentlich + lang + slug fuer jeden Slug der Seitenliste', async () => {
		const datei = path.join(ROUTES, 'funktionen', '[thema]', '+page.server.ts');
		assert.ok(existsSync(datei), 'frontend/src/routes/funktionen/[thema]/+page.server.ts fehlt');
		const mod = await import(pathToFileURL(datei).href);
		const aufrufe = await mitFetchWaechter(async (fetch) => {
			for (const { slug } of seiten()) {
				for (const userId of [undefined, 'nutzer-a']) {
					const r = await mod.load({
						params: { thema: slug },
						locals: { lang: 'en', userId },
						fetch,
						cookies: { get: () => undefined }
					});
					assert.deepEqual(Object.keys(r).sort(), ['lang', 'oeffentlich', 'slug'], slug);
					assert.equal(r.oeffentlich, true);
					assert.equal(r.lang, 'en');
					assert.equal(r.slug, slug);
				}
			}
		});
		assert.equal(aufrufe, 0);
	});

	test('Unterseite: unbekannter Slug ergibt 404', async () => {
		const datei = path.join(ROUTES, 'funktionen', '[thema]', '+page.server.ts');
		assert.ok(existsSync(datei), 'frontend/src/routes/funktionen/[thema]/+page.server.ts fehlt');
		const mod = await import(pathToFileURL(datei).href);
		for (const thema of ['unbekannt', 'Trips', 'hilfe']) {
			await assert.rejects(
				async () => mod.load({ params: { thema }, locals: { lang: 'de', userId: 'nutzer-a' }, cookies: { get: () => undefined } }),
				(e: { status?: number }) => e?.status === 404,
				`${thema} muss 404 ergeben`
			);
		}
	});
});

// ════════════════════════════════════════════════════════════════════════════
describe('AC-6: Seitenliste, Zuordnung der 14 Inventarpunkte', () => {
	test('Seitenliste: neun Slugs in der Reihenfolge der Spec', () => {
		assert.deepEqual(seiten().map((s) => s.slug), SOLL_SLUGS);
	});
	test('jeder der 14 Inventarpunkte steht auf genau einer Unterseite', () => {
		const alle = seiten().flatMap((s) => [...s.inventar]);
		assert.deepEqual([...alle].sort(), [...INVENTAR].sort(), 'Inventarpunkte fehlen oder sind doppelt');
		assert.equal(new Set(alle).size, alle.length, 'Inventarpunkt doppelt zugeordnet');
	});
	test('Zuordnung entspricht der Spec', () => {
		const ist = seiten().map((s) => [s.slug, [...s.inventar]] as const);
		assert.deepEqual(ist, SOLL_ZUORDNUNG.map(([s, i]) => [s, [...i]] as const));
	});
});

describe('AC-6: DE und EN fuer jeden Katalogschluessel', () => {
	const funktionenKeys = keys.filter((k) => k.startsWith('funktionen.'));
	test('jeder funktionen.*-Schluessel existiert in DE und EN, nicht leer; EN hat keine Extra-Schluessel', () => {
		assert.ok(funktionenKeys.length >= 40, `zu wenige funktionen.*-Texte: ${funktionenKeys.length}`);
		for (const k of funktionenKeys) {
			assert.ok(katalogDe[k]?.trim().length > 0, `de ${k} leer`);
			assert.ok(katalogEn[k]?.trim().length > 0, `en ${k} fehlt oder leer`);
		}
		const nurEn = Object.keys(katalogEn).filter((k) => k.startsWith('funktionen.') && !(k in katalogDe));
		assert.deepEqual(nurEn, [], 'Schluessel nur im EN-Katalog');
	});
	test('je Unterseite Titel und Kachelsatz in DE und EN, uebersetzt', () => {
		for (const { slug } of seiten()) {
			for (const teil of ['titel', 'kachel']) {
				const k = `funktionen.seite.${slug}.${teil}`;
				assert.ok(katalogDe[k]?.trim().length > 0, `de ${k} fehlt`);
				assert.ok(katalogEn[k]?.trim().length > 0, `en ${k} fehlt`);
			}
			assert.notEqual(katalogEn[`funktionen.seite.${slug}.kachel`], katalogDe[`funktionen.seite.${slug}.kachel`], `${slug}: Kachelsatz nicht uebersetzt`);
		}
	});
	test('je Inventarpunkt eine Zwischenueberschrift in DE und EN', () => {
		for (const id of INVENTAR) {
			assert.ok(katalogDe[`funktionen.${id}.titel`]?.trim().length > 0, `de funktionen.${id}.titel fehlt`);
			assert.ok(katalogEn[`funktionen.${id}.titel`]?.trim().length > 0, `en funktionen.${id}.titel fehlt`);
		}
	});
});

describe('AC-6: Uebersicht mit neun Themenkacheln je Sprache', () => {
	for (const lang of SPRACHEN) {
		test(`${lang}: neun Kacheln mit Ziel aus der Seitenliste, Titel und Satz aus dem Katalog`, async () => {
			const { body } = await renderUebersicht(lang);
			assert.match(body, /data-testid="sprach-umschalter"/, `${lang}: Sprachumschalter fehlt`);
			const kacheln = linksMitTestid(body, 'kachel');
			assert.deepEqual(
				kacheln.map((k) => k.href),
				seiten().map((s) => `/funktionen/${s.slug}`),
				`${lang}: Kachel-Ziele/Reihenfolge`
			);
			kacheln.forEach((k, i) => {
				const slug = seiten()[i].slug;
				assert.ok(k.text.includes(txt(lang, `funktionen.seite.${slug}.titel`)), `${lang}: Kachel ${slug} ohne Titel`);
				assert.ok(k.text.includes(txt(lang, `funktionen.seite.${slug}.kachel`)), `${lang}: Kachel ${slug} ohne Satz`);
			});
			assert.doesNotMatch(body, /href="#/, `${lang}: Uebersicht nutzt noch Sprunganker statt Unterseiten`);
		});
	}
	test('Sprache wirkt: EN-Uebersicht zeigt keine deutschen Kacheltexte', async () => {
		const enText = nurText((await renderUebersicht('en')).body);
		for (const { slug } of seiten()) {
			assert.ok(!enText.includes(txt('de', `funktionen.seite.${slug}.kachel`)), `en zeigt deutschen Kachelsatz ${slug}`);
		}
	});
});

describe('AC-6: jede Unterseite zeigt genau ihre Inventarpunkte in der gewaehlten Sprache', () => {
	for (const lang of SPRACHEN) {
		test(`${lang}: Abschnitte je Unterseite = Zuordnung der Seitenliste, mit Zwischenueberschrift`, async () => {
			for (const { slug, inventar } of seiten()) {
				const { body } = await renderUnterseite(lang, slug);
				const ids = [...body.matchAll(/<section\b[^>]*\bdata-inventar="([^"]+)"/g)].map((m) => m[1]);
				assert.deepEqual(ids, [...inventar], `${lang}/${slug}: Inventar-Abschnitte`);
				for (const id of inventar) {
					assert.ok(nurText(inventarHtml(body, id)).includes(txt(lang, `funktionen.${id}.titel`)), `${lang}/${slug}: Ueberschrift ${id}`);
				}
				const h1 = body.match(/<h1\b[^>]*>([\s\S]*?)<\/h1>/);
				assert.ok(h1 && nurText(h1[1]).includes(txt(lang, `funktionen.seite.${slug}.titel`)), `${lang}/${slug}: Seitentitel (h1)`);
				assert.match(body, /data-testid="sprach-umschalter"/, `${lang}/${slug}: Sprachumschalter fehlt`);
			}
		});
	}
	test('EN-Unterseite zeigt keinen deutschen Seitentitel', async () => {
		for (const { slug } of seiten()) {
			const deT = txt('de', `funktionen.seite.${slug}.titel`);
			if (deT === txt('en', `funktionen.seite.${slug}.titel`)) continue; // z. B. Eigennamen
			const h1 = (await renderUnterseite('en', slug)).body.match(/<h1\b[^>]*>([\s\S]*?)<\/h1>/);
			assert.ok(h1 && !nurText(h1[1]).includes(deT), `en/${slug} zeigt deutschen Titel`);
		}
	});
});

describe('AC-6: volle Level-Tabelle auf der Unterseite level', () => {
	for (const lang of SPRACHEN) {
		test(`${lang}: Level-Tabelle inkl. Premium-SMS-Antworten, E-Mail und Telegram`, async () => {
			const zeilen = levelZeilen((await renderUnterseite(lang, 'level')).body);
			pruefeLevelZeilen(zeilen, [...ZAHLEN_FELDER, 'premium_sms_antworten_pro_tag'], lang);
			for (const f of ['email', 'telegram']) {
				assert.ok(zeilen[f]?.length === 3, `${lang}: Zeile ${f} fehlt`);
				assert.ok(zeilen[f].every((c) => c.length > 0), `${lang}: ${f} ohne Angabe`);
			}
		});
		test(`${lang}: Level-Seite nennt den Wechselweg, keine Preise`, async () => {
			const text = nurText((await renderUnterseite(lang, 'level')).body);
			assert.match(text, lang === 'de' ? /Antrag/ : /request/i);
			assert.match(text, lang === 'de' ? /Betreiber/ : /operator/i);
			assert.doesNotMatch(text, /€|\$|EUR\b|Preis|price|kostet|costs|bezahl|payment|Abo\b|subscription/i);
		});
	}
});

// ════════════════════════════════════════════════════════════════════════════
describe('AC-7: nur Funktionsbeschreibung, nichts Internes', () => {
	const funktionenKeys = keys.filter((k) => k.startsWith('funktionen.'));
	const VERBOTEN = /konnektor|connector|\bmcp\b|admin|design|claude/i;
	// F004 (Adversary): Ratschlag-Muster statt reiner Schluesselwortliste —
	// (1) Modal-/Ratschlagwoerter (sollte, musst, empfehlen, ratsam, am besten, besser, lieber),
	// (2) Handlungs-Imperative am Satzanfang (Nimm…, Geh…, Brich… ab, Kehr… um, Bleib…, Warte…,
	//     Meide…, Pack…, Zieh…, Verschieb…, Starte…), (3) feste Wendungen (umkehren, brich … ab).
	// EN entsprechend (should, ought to, recommend, advise, best to, you must, better, make sure,
	// turn back, Imperative Take/Go/Turn/Stay/Wait/Avoid/Pack/Bring/Head/Postpone/Start/Leave).
	// #3324: DE zusaetzlich empfiehlt/empfehlenswert, am sichersten, „Plane … um“ (nur mit „um“,
	// nacktes „Plane“ ist Substantiv), Beachte/Denk/Achte am Satzanfang; EN prudent, wise to,
	// advisable, it is/it's best/wise/safer, you'd want to, would be wise, be sure, keep in mind,
	// Consider am Satzanfang. Bewusst NICHT: „check“, „note that“ (treffen zulaessige Texte).
	// Fix-Loop 1: Flexionen Denke/Beachtet/Beachten/Achtet/Achten am Satzanfang, Imperative nie
	// als Bindestrich-Kompositum („Denk-Pause“); EN you may want to, don't/do not forget.
	const SATZANFANG = String.raw`(?:^|[.!?:;]\s+|\n)`;
	const EMPFEHLUNG_DE = new RegExp(
		String.raw`\bsollte(?:st|n|t)?\b|\bmusst\b|\bempfehl|\bempfiehl|\bratsam\b|\bam besten\b|\bam sichersten\b|\bbesser\b|\blieber\b|\bumkehren\b|\bbrich\b[^.!?]*\bab\b|` +
			`${SATZANFANG}plane\\b[^.!?]*\\bum\\b|` +
			`${SATZANFANG}(?:nimm|geh|brich|kehr|bleib|warte|meide|vermeide|pack|zieh|verschieb|starte|beachte[nt]?|denke?|achte[nt]?)\\b(?![-‐])`,
		'iu'
	);
	const EMPFEHLUNG_EN = new RegExp(
		String.raw`\bshould\b|\bought to\b|recommend|\badvis|\bbest to\b|\byou must\b|\bbetter\b|\bmake sure\b|\bturn back\b|` +
			String.raw`\bprudent\b|\bwise to\b|\bit(?: is|['’]s) (?:best|wise|safer)\b|\byou['’]d want to\b|\bwould be wise\b|\bbe sure\b|\bkeep in mind\b|\byou may want to\b|\bdon['’]t forget\b|\bdo not forget\b|` +
			`${SATZANFANG}(?:take|go|turn|stay|wait|avoid|pack|bring|head|postpone|start|leave|consider)\\b`,
		'iu'
	);
	const EMPFEHLUNG: Record<Lang, RegExp> = { de: EMPFEHLUNG_DE, en: EMPFEHLUNG_EN };
	/** Schluessel aller funktionen.*-Texte einer Sprache, die einen Ratschlag enthalten. */
	function ratschlagTreffer(kataloge: Kataloge, lang: Lang): string[] {
		return funktionenKeys.filter((k) => !k.endsWith('.src') && EMPFEHLUNG[lang].test(translate(kataloge, lang, k)));
	}
	test('Gegenprobe: die Regeln greifen', () => {
		assert.match('Der Claude-Konnektor', VERBOTEN);
		assert.match('Admin area', VERBOTEN);
		assert.match('Du solltest bei Gewitter umkehren', EMPFEHLUNG_DE);
		assert.match('We recommend turning back', EMPFEHLUNG_EN);
		assert.doesNotMatch('Die Böen am Pass in km/h', EMPFEHLUNG_DE);
	});
	test('F004 Gegenprobe: Ratschlaege ohne Schluesselwort der alten Liste werden erkannt', () => {
		for (const s of [
			'Nimm besser eine Regenjacke mit.',
			'Nimm eine Regenjacke mit.',
			'Bei Gewitter: Brich die Etappe ab.',
			'Die Böen nehmen zu. Geh früh los.',
			'Kehr am Pass um, wenn es blitzt.',
			'Am Nachmittag lieber im Tal bleiben.',
			'Bleib bei Nebel auf dem Weg.'
		]) {
			assert.match(s, EMPFEHLUNG_DE, s);
		}
		for (const s of [
			'Take a rain jacket.',
			'Gusts increase. Turn back at the pass.',
			'Better start early.',
			'You had better wait.',
			'Make sure you carry water.',
			'Avoid the ridge after noon.'
		]) {
			assert.match(s, EMPFEHLUNG_EN, s);
		}
	});
	test('F004 Gegenprobe: reine Funktionsbeschreibungen bleiben frei', () => {
		for (const s of [
			'Die Böen am Pass in km/h',
			'Gregor meldet sich, wenn ein Gewitter aufzieht.',
			'Mit dem Befehl STOP beendest du den Versand.',
			'Abbruch per Befehl STOP',
			'Lege einen Trip an und lade je Etappe eine GPX-Datei hoch.'
		]) {
			assert.doesNotMatch(s, EMPFEHLUNG_DE, s);
		}
		for (const s of ['Gusts at the pass in km/h', 'Gregor tells you when a thunderstorm builds up.', 'Create a trip and upload one GPX file per stage.']) {
			assert.doesNotMatch(s, EMPFEHLUNG_EN, s);
		}
	});
	// Issue #3324 (Spec pruefregeln_funktionsseiten_3324, AC-1/AC-2): gaengige
	// Ratschlag-Formulierungen, die die Regeln oben bisher uebersehen. Alle Saetze fiktiv.
	test('#3324 AC-1: weitere Ratschlag-Formulierungen DE werden erkannt', () => {
		for (const s of [
			'Es empfiehlt sich, früh zu starten.',
			'Ein früher Start ist empfehlenswert.',
			'Am sichersten ist ein früher Start.',
			'Plane die Etappe um.',
			'Bei Gewitter: Plane die Etappe um.',
			'Beachte die Gewitterwarnung.',
			'Denk an die Regenjacke.',
			'Achte auf die Böen am Grat.',
			'Denke an die Regenjacke.',
			'Beachtet die Gewitterwarnung.',
			'Beachten Sie die Gewitterwarnung.',
			'Achtet auf die Böen am Grat.',
			'Achten Sie auf die Böen am Grat.'
		]) {
			assert.match(s, EMPFEHLUNG_DE, s);
		}
	});
	test('#3324 AC-1: weitere Ratschlag-Formulierungen EN werden erkannt', () => {
		for (const s of [
			'A prudent hiker turns back.',
			'It is wise to start early.',
			"It's wise to start early.",
			'It is advisable to carry water.',
			'It is safer to start early.',
			"It's best to start early.",
			'You would be wise to start early.',
			"You'd want to leave early.",
			'Be sure to carry water.',
			'Keep in mind that storms build up.',
			'Consider a rain jacket.',
			'Gusts increase. Consider a rain jacket.',
			// Je Regex-Alternative ein Satz, der NUR diese Alternative trifft (Fix-Loop 1, F002).
			'Starting early is wise to beat the storm.',
			'Starting early would be wise.',
			'It is best at dawn.',
			'It is wise, given the storm.',
			"It's safer at dawn.",
			'You may want to leave early.',
			"Don't forget the rain jacket.",
			'Do not forget the rain jacket.'
		]) {
			assert.match(s, EMPFEHLUNG_EN, s);
		}
	});
	test('#3324 AC-2: Funktionsbeschreibungen mit aehnlichen Woertern bleiben frei', () => {
		for (const s of [
			'Plane dienen als Schutz.',
			'Plan: Free, Standard, Premium',
			'Die Planung der Etappe übernimmst du im Editor.',
			'Gregor achtet auf die Böen am Grat.',
			'Die Warnung beachtet alle amtlichen Stufen.',
			'Denk-Pause am Pass: Gregor zeigt die Böen.'
		]) {
			assert.doesNotMatch(s, EMPFEHLUNG_DE, s);
		}
		for (const s of [
			'Gregor shows the gusts and you check the waypoints.',
			'The table considers every location.',
			'Gregor keeps the stage in the briefing.',
			'Note that the table has no ranking.'
		]) {
			assert.doesNotMatch(s, EMPFEHLUNG_EN, s);
		}
	});
	test('#3324 AC-2 Gegenprobe: eingefuegter Ratschlag in einem Katalogtext wird rot', () => {
		const k = funktionenKeys.find((x) => !x.endsWith('.src'));
		assert.ok(k);
		// Kopie des geladenen Katalogs: ein funktionen.*-Text bekommt einen Ratschlag; dieselbe
		// Pruefung wie der Lauf ueber alle Texte muss genau diesen Schluessel melden.
		const kopieDe: Record<string, string> = { ...katalogDe, [k]: `${katalogDe[k]} Es empfiehlt sich, früh zu starten.` };
		const kopieEn: Record<string, string> = { ...katalogEn, [k]: `${katalogEn[k]} It is advisable to carry water.` };
		const kopie: Kataloge = { de: kopieDe, en: kopieEn };
		assert.deepEqual(ratschlagTreffer(kopie, 'de'), [k]);
		assert.deepEqual(ratschlagTreffer(kopie, 'en'), [k]);
		assert.deepEqual(ratschlagTreffer({ de, en }, 'de'), [], 'Original-Katalog unveraendert');
	});
	test('kein funktionen.*-Text nennt Konnektor/MCP/Admin/Design oder empfiehlt etwas', () => {
		assert.ok(funktionenKeys.length >= 28, `zu wenige funktionen.*-Texte: ${funktionenKeys.length}`);
		for (const k of funktionenKeys) {
			if (k.endsWith('.src')) continue;
			assert.doesNotMatch(txt('de', k), VERBOTEN, `de ${k}`);
			assert.doesNotMatch(txt('en', k), VERBOTEN, `en ${k}`);
		}
		assert.deepEqual(ratschlagTreffer({ de, en }, 'de'), [], 'de: Ratschlag in funktionen.*');
		assert.deepEqual(ratschlagTreffer({ de, en }, 'en'), [], 'en: Ratschlag in funktionen.*');
	});
	test('auch die gerenderten Seiten (Uebersicht + alle Unterseiten) sind frei davon', async () => {
		for (const lang of SPRACHEN) {
			assert.doesNotMatch(nurText((await renderUebersicht(lang)).body), VERBOTEN, `${lang} Uebersicht`);
			for (const { slug } of seiten()) {
				assert.doesNotMatch(nurText((await renderUnterseite(lang, slug)).body), VERBOTEN, `${lang}/${slug}`);
			}
		}
	});
});

// ════════════════════════════════════════════════════════════════════════════
describe('AC-10: Befehlsliste auf der Unterseite befehle aus der Hilfe-Quelle, Kanalhinweis', () => {
	const befehlsKeys = keys.filter((k) => /^hilfe\.befehle\.[^.]+\.befehl$/.test(k));
	/** Abweichung gezeigt ↔ Hilfe-Quelle (leer = keine Drift). */
	const drift = (gezeigt: string[], soll: string[]) => {
		const g = new Set(gezeigt);
		const s = new Set(soll);
		return [
			...soll.filter((b) => !g.has(b)).map((b) => `fehlt: ${b}`),
			...gezeigt.filter((b) => !s.has(b)).map((b) => `zu viel: ${b}`),
			...(gezeigt.length !== g.size ? ['doppelt'] : [])
		];
	};
	const gezeigteBefehle = (html: string) =>
		[...html.matchAll(/<code\b[^>]*>([\s\S]*?)<\/code>/g)].map((m) => nurText(m[1]).trim());

	test('Messaufbau: 15 Befehle in der Hilfe-Quelle', () => {
		assert.equal(befehlsKeys.length, 15);
	});
	test('Gegenprobe: verfaelschter, fehlender oder doppelter Befehl wird als Drift erkannt', () => {
		const soll = befehlsKeys.map((k) => txt('de', k));
		assert.deepEqual(drift([...soll], soll), []);
		assert.notDeepEqual(drift(soll.map((b, i) => (i === 0 ? `${b}X` : b)), soll), []);
		assert.notDeepEqual(drift(soll.slice(1), soll), []);
		assert.notDeepEqual(drift([...soll, soll[0]], soll), []);
	});
	for (const lang of SPRACHEN) {
		test(`${lang}: Unterseite befehle zeigt genau die Befehle der Hilfe`, async () => {
			const gezeigt = gezeigteBefehle((await renderUnterseite(lang, 'befehle')).body);
			const soll = befehlsKeys.map((k) => txt(lang, k));
			assert.deepEqual(drift(gezeigt, soll), [], `${lang}: Befehlsliste weicht von der Hilfe ab`);
		});
		test(`${lang}: Hinweis, ueber welche Kanaele Befehle ankommen`, async () => {
			const text = nurText(inventarHtml((await renderUnterseite(lang, 'befehle')).body, 'befehle'));
			assert.match(text, /E-Mail|email/i);
			assert.match(text, /Telegram/);
			assert.match(text, /Premium-SMS/);
			assert.match(text, lang === 'de' ? /SMS[^.]*nur[^.]*empfang|nur[^.]*empfang[^.]*SMS/i : /SMS[^.]*receive only|receive[^.]*only[^.]*SMS|only[^.]*receiv[^.]*SMS|SMS[^.]*only[^.]*receiv/i);
		});
	}
});

// ════════════════════════════════════════════════════════════════════════════
describe('AC-12: Orientierung auf jeder Unterseite', () => {
	for (const lang of SPRACHEN) {
		test(`${lang}: Brotkrumen „Funktionen › Thema“ mit Link zur Uebersicht`, async () => {
			for (const { slug } of seiten()) {
				const nav = navHtml((await renderUnterseite(lang, slug)).body, 'brotkrumen');
				assert.match(nav, /<a\b[^>]*href="\/funktionen"/, `${lang}/${slug}: Brotkrumen ohne Link zur Uebersicht`);
				assert.ok(nurText(nav).includes(txt(lang, `funktionen.seite.${slug}.titel`)), `${lang}/${slug}: Brotkrumen ohne Thema`);
			}
		});
		test(`${lang}: Themen-Navigation mit allen neun Unterseiten, aktuelle markiert`, async () => {
			const soll = seiten().map((s) => `/funktionen/${s.slug}`);
			for (const { slug } of seiten()) {
				const nav = navHtml((await renderUnterseite(lang, slug)).body, 'themen-navigation');
				const links = [...nav.matchAll(/<a\b([^>]*)>([\s\S]*?)<\/a>/g)];
				assert.deepEqual(links.map((m) => attr(m[1], 'href')), soll, `${lang}/${slug}: Navigationslinks`);
				links.forEach((m, i) => {
					assert.ok(nurText(m[2]).includes(txt(lang, `funktionen.seite.${seiten()[i].slug}.titel`)), `${lang}/${slug}: Link ${i} ohne Titel`);
				});
				const aktuell = links.filter((m) => /\baria-current="page"/.test(m[1])).map((m) => attr(m[1], 'href'));
				assert.deepEqual(aktuell, [`/funktionen/${slug}`], `${lang}/${slug}: aktuelle Seite markiert`);
			}
		});
		test(`${lang}: Zurueck/Weiter gemaess Reihenfolge (erste ohne Zurueck, letzte ohne Weiter)`, async () => {
			const liste = seiten();
			for (let i = 0; i < liste.length; i++) {
				const { body } = await renderUnterseite(lang, liste[i].slug);
				const zurueck = linksMitTestid(body, 'seite-zurueck');
				const weiter = linksMitTestid(body, 'seite-weiter');
				if (i === 0) assert.equal(zurueck.length, 0, `${lang}/${liste[i].slug}: erste Seite ohne Zurueck`);
				else {
					assert.deepEqual(zurueck.map((l) => l.href), [`/funktionen/${liste[i - 1].slug}`], `${lang}/${liste[i].slug}: Zurueck`);
					assert.ok(zurueck[0].text.includes(txt(lang, `funktionen.seite.${liste[i - 1].slug}.titel`)), `${lang}/${liste[i].slug}: Zurueck ohne Titel`);
				}
				if (i === liste.length - 1) assert.equal(weiter.length, 0, `${lang}/${liste[i].slug}: letzte Seite ohne Weiter`);
				else {
					assert.deepEqual(weiter.map((l) => l.href), [`/funktionen/${liste[i + 1].slug}`], `${lang}/${liste[i].slug}: Weiter`);
					assert.ok(weiter[0].text.includes(txt(lang, `funktionen.seite.${liste[i + 1].slug}.titel`)), `${lang}/${liste[i].slug}: Weiter ohne Titel`);
				}
			}
		});
		test(`${lang}: Aufruf zur Registrierung auf jeder Unterseite`, async () => {
			for (const { slug } of seiten()) {
				assert.match((await renderUnterseite(lang, slug)).body, /<a\b[^>]*href="\/register"/, `${lang}/${slug}: kein Link /register`);
			}
		});
		test(`${lang}: eigener Seitentitel und eigene Meta-Beschreibung je Seite (eindeutig)`, async () => {
			const titel = new Map<string, string>();
			const beschreibung = new Map<string, string>();
			const ueb = await renderUebersicht(lang);
			titel.set('uebersicht', titelVon(ueb.head));
			beschreibung.set('uebersicht', beschreibungVon(ueb.head));
			for (const { slug } of seiten()) {
				const { head } = await renderUnterseite(lang, slug);
				const t = titelVon(head);
				assert.ok(t.includes(txt(lang, `funktionen.seite.${slug}.titel`)), `${lang}/${slug}: <title> nennt das Thema nicht ("${t}")`);
				titel.set(slug, t);
				beschreibung.set(slug, beschreibungVon(head));
			}
			for (const [s, t] of titel) assert.ok(t.length > 0, `${lang}/${s}: <title> fehlt`);
			for (const [s, b] of beschreibung) assert.ok(b.length > 20, `${lang}/${s}: Meta-Beschreibung fehlt`);
			assert.equal(new Set(titel.values()).size, titel.size, `${lang}: Seitentitel nicht eindeutig`);
			assert.equal(new Set(beschreibung.values()).size, beschreibung.size, `${lang}: Meta-Beschreibungen nicht eindeutig`);
		});
	}
	test('Titel und Meta-Beschreibung sind je Sprache eigene Texte', async () => {
		for (const { slug } of seiten()) {
			const d = beschreibungVon((await renderUnterseite('de', slug)).head);
			const e = beschreibungVon((await renderUnterseite('en', slug)).head);
			assert.notEqual(e, d, `${slug}: Meta-Beschreibung nicht uebersetzt`);
		}
	});
});
