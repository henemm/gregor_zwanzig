// Issue #3319 / #3320 — oeffentliche Funktionsuebersicht /funktionen und Level-Kurzform
// auf der Startseite, ECHT gerendert (svelte/server), je Sprache ueber den Katalog.
// AC-2 (Startseite: Level-Kurzform + Link), AC-4 (Load ohne API/Nutzerdaten),
// AC-6 (14 Abschnitte, Sprunganker, volle Level-Tabelle, Sprache), AC-7 (keine
// Konnektor/Admin/Design-Texte, keine Empfehlungen), AC-8 (Bilder je Sprache,
// < 200 KB, WebP, Alt, Masse, lazy), AC-10 (Befehlsliste = Hilfe-Quelle, Kanalhinweis).
// Spec: docs/specs/modules/oeffentliche_doku_3319.md
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/i18n/__tests__/funktionen_seite.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync, statSync } from 'node:fs';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { locale, trFor, type MessageKey } from '../index.ts';
import { de } from '../messages/de/index.ts';

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
const katalog = de as Record<string, string>;
const keys = Object.keys(katalog) as MessageKey[];
const txt = (lang: Lang, k: string) => trFor(lang, k as MessageKey);

/** Abschnitte 1–14 des Funktionsinventars (Spec, Implementation Details „Inhalt“). */
const ABSCHNITT_IDS = [
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

const ent = (s: string) =>
	s.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>');
const nurText = (html: string) => ent(html.replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ');

async function renderFunktionen(lang: Lang): Promise<string> {
	locale.set(lang);
	const Seite = await ladeKomponente(path.join(ROUTES, 'funktionen', '+page.svelte'));
	return render(Seite, { props: { data: { oeffentlich: true, lang } } }).body;
}

async function renderStartseite(lang: Lang): Promise<string> {
	locale.set(lang);
	const Seite = await ladeKomponente(path.join(ROUTES, '_start', 'Startseite.svelte'));
	return render(Seite, { props: {} }).body;
}

/** Inhalt des Elements mit `id="<id>"` bis zum naechsten <section …> bzw. Seitenende. */
function abschnittHtml(html: string, id: string): string {
	const start = html.search(new RegExp(`<section\\b[^>]*\\bid="${id}"`));
	assert.ok(start >= 0, `Abschnitt #${id} fehlt`);
	const rest = html.slice(start + 1);
	const ende = rest.search(/<section\b/);
	return ende < 0 ? rest : rest.slice(0, ende);
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

after(() => locale.set('de'));

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

describe('AC-2: Startseite zeigt die Level-Kurzform und verlinkt /funktionen', () => {
	for (const lang of SPRACHEN) {
		test(`${lang}: Kurztabelle mit echten Grenzen, Wechselweg, kein Preis, Link /funktionen`, async () => {
			const html = await renderStartseite(lang);
			pruefeLevelZeilen(levelZeilen(html), ZAHLEN_FELDER, lang);
			const text = nurText(html);
			assert.match(text, /Free/);
			assert.match(text, /Standard/);
			assert.match(text, /Premium/);
			assert.match(html, /<a\b[^>]*href="\/funktionen"/, `${lang}: Link zu /funktionen fehlt`);
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

describe('AC-4: Load der Funktionsseite ruft keine API und liefert keine Nutzerdaten', () => {
	test('load liefert nur oeffentlich + lang, fetch wird nie aufgerufen', async () => {
		const mod = await import(pathToFileURL(path.join(ROUTES, 'funktionen', '+page.server.ts')).href);
		let aufrufe = 0;
		const fetch = async () => {
			aufrufe++;
			throw new Error('kein API-Aufruf erlaubt');
		};
		const orig = globalThis.fetch;
		globalThis.fetch = fetch as typeof globalThis.fetch;
		try {
			for (const userId of [undefined, 'nutzer-a']) {
				const r = await mod.load({ locals: { lang: 'en', userId }, fetch, cookies: { get: () => undefined } });
				assert.deepEqual(Object.keys(r).sort(), ['lang', 'oeffentlich']);
				assert.equal(r.oeffentlich, true);
				assert.equal(r.lang, 'en');
			}
		} finally {
			globalThis.fetch = orig;
		}
		assert.equal(aufrufe, 0);
	});
});

describe('AC-6: vollstaendige Seite je Sprache', () => {
	for (const lang of SPRACHEN) {
		test(`${lang}: 14 Abschnitte, Inhaltsverzeichnis mit Sprungankern, Titel aus dem Katalog`, async () => {
			const html = await renderFunktionen(lang);
			assert.match(html, /data-testid="funktionen"/);
			const ids = [...html.matchAll(/<section\b[^>]*\bid="([^"]+)"/g)].map((m) => m[1]);
			assert.deepEqual(ids, [...ABSCHNITT_IDS], `${lang}: Abschnitte/Reihenfolge`);
			const nav = html.match(/<nav\b[^>]*data-testid="inhaltsverzeichnis"[^>]*>([\s\S]*?)<\/nav>/);
			assert.ok(nav, `${lang}: Inhaltsverzeichnis fehlt`);
			const anker = [...nav![1].matchAll(/href="#([^"]+)"/g)].map((m) => m[1]);
			assert.deepEqual(anker, [...ABSCHNITT_IDS], `${lang}: Sprunganker`);
			for (const id of ABSCHNITT_IDS) {
				const titel = txt(lang, `funktionen.${id}.titel`);
				assert.ok(titel && titel !== `funktionen.${id}.titel`, `${lang}: Titel funktionen.${id}.titel fehlt`);
				assert.ok(nurText(abschnittHtml(html, id)).includes(titel), `${lang}: Titel von #${id} nicht im Abschnitt`);
			}
			assert.match(html, /data-testid="sprach-umschalter"/, `${lang}: Sprachumschalter fehlt`);
		});
		test(`${lang}: volle Level-Tabelle inkl. Premium-SMS-Antworten, E-Mail und Telegram`, async () => {
			const zeilen = levelZeilen(await renderFunktionen(lang));
			pruefeLevelZeilen(zeilen, [...ZAHLEN_FELDER, 'premium_sms_antworten_pro_tag'], lang);
			for (const f of ['email', 'telegram']) {
				assert.ok(zeilen[f]?.length === 3, `${lang}: Zeile ${f} fehlt`);
				assert.ok(zeilen[f].every((c) => c.length > 0), `${lang}: ${f} ohne Angabe`);
			}
		});
	}
	test('Sprache wirkt: de- und en-Seite unterscheiden sich im Titel', async () => {
		const de_ = nurText(await renderFunktionen('de'));
		const en_ = nurText(await renderFunktionen('en'));
		assert.notEqual(txt('de', 'funktionen.titel'), txt('en', 'funktionen.titel'));
		assert.ok(de_.includes(txt('de', 'funktionen.titel')));
		assert.ok(en_.includes(txt('en', 'funktionen.titel')));
		assert.ok(!en_.includes(txt('de', 'funktionen.titel')), 'en-Seite zeigt deutschen Titel');
	});
});

describe('AC-7: nur Funktionsbeschreibung, nichts Internes', () => {
	const funktionenKeys = keys.filter((k) => k.startsWith('funktionen.'));
	const VERBOTEN = /konnektor|connector|\bmcp\b|admin|design|claude/i;
	const EMPFEHLUNG_DE = /solltest|sollte\b|empfehl|ratsam|am besten|musst du/i;
	const EMPFEHLUNG_EN = /\bshould\b|recommend|advis|\bbest to\b|\byou must\b/i;
	test('Gegenprobe: die Regeln greifen', () => {
		assert.match('Der Claude-Konnektor', VERBOTEN);
		assert.match('Admin area', VERBOTEN);
		assert.match('Du solltest bei Gewitter umkehren', EMPFEHLUNG_DE);
		assert.match('We recommend turning back', EMPFEHLUNG_EN);
		assert.doesNotMatch('Die Böen am Pass in km/h', EMPFEHLUNG_DE);
	});
	test('kein funktionen.*-Text nennt Konnektor/MCP/Admin/Design oder empfiehlt etwas', () => {
		assert.ok(funktionenKeys.length >= 28, `zu wenige funktionen.*-Texte: ${funktionenKeys.length}`);
		for (const k of funktionenKeys) {
			if (k.endsWith('.src')) continue;
			assert.doesNotMatch(txt('de', k), VERBOTEN, `de ${k}`);
			assert.doesNotMatch(txt('en', k), VERBOTEN, `en ${k}`);
			assert.doesNotMatch(txt('de', k), EMPFEHLUNG_DE, `de ${k}`);
			assert.doesNotMatch(txt('en', k), EMPFEHLUNG_EN, `en ${k}`);
		}
	});
	test('auch die gerenderte Seite ist frei davon', async () => {
		for (const lang of SPRACHEN) {
			const text = nurText(await renderFunktionen(lang));
			assert.doesNotMatch(text, VERBOTEN, lang);
		}
	});
});

describe('AC-8: Bilder je Sprache', () => {
	type Img = { src: string; alt: string; width: string; height: string; loading: string };
	const attr = (tag: string, a: string) => ent(tag.match(new RegExp(`\\b${a}="([^"]*)"`))?.[1] ?? '');
	const bilder = (html: string): Img[] =>
		[...html.matchAll(/<img\b[^>]*>/g)].map((m) => ({
			src: attr(m[0], 'src'),
			alt: attr(m[0], 'alt'),
			width: attr(m[0], 'width'),
			height: attr(m[0], 'height'),
			loading: attr(m[0], 'loading')
		}));
	const istWebp = (b: Buffer) => b.subarray(0, 4).toString('latin1') === 'RIFF' && b.subarray(8, 12).toString('latin1') === 'WEBP';

	test('Gegenprobe: WebP-Erkennung lehnt PNG ab', () => {
		assert.equal(istWebp(readFileSync(path.join(FRONTEND, 'static', 'landing', 'alarm.png'))), false);
	});

	for (const lang of SPRACHEN) {
		test(`${lang}: >= 10 Bilder, eigene Datei je Sprache, WebP < 200 KB, Alt, Masse, lazy`, async () => {
			const liste = bilder(await renderFunktionen(lang));
			assert.ok(liste.length >= 10, `${lang}: nur ${liste.length} Bilder`);
			const praefix = lang === 'de' ? /^\/funktionen\/[^/]+\.webp$/ : /^\/funktionen\/en\/[^/]+\.webp$/;
			for (const b of liste) {
				assert.match(b.src, praefix, `${lang}: Bildpfad ${b.src}`);
				const datei = path.join(FRONTEND, 'static', b.src.replace(/^\//, ''));
				assert.ok(existsSync(datei), `${lang}: ${b.src} fehlt`);
				assert.ok(statSync(datei).size < 200 * 1024, `${lang}: ${b.src} >= 200 KB`);
				assert.ok(istWebp(readFileSync(datei)), `${lang}: ${b.src} ist kein WebP`);
				assert.ok(b.alt.trim().length > 10, `${lang}: Alt-Text zu ${b.src} fehlt`);
				assert.match(b.width, /^\d+$/, `${lang}: width zu ${b.src}`);
				assert.match(b.height, /^\d+$/, `${lang}: height zu ${b.src}`);
				assert.equal(b.loading, 'lazy', `${lang}: loading zu ${b.src}`);
			}
		});
	}

	test('DE/EN-Paar: gleiche Dateinamen, verschiedene Dateien, verschiedene Alt-Texte', async () => {
		const name = (s: string) => s.split('/').pop()!;
		const deB = bilder(await renderFunktionen('de'));
		const enB = bilder(await renderFunktionen('en'));
		assert.deepEqual(enB.map((b) => name(b.src)), deB.map((b) => name(b.src)));
		deB.forEach((b, i) => {
			assert.notEqual(enB[i].alt, b.alt, `Alt-Text ${name(b.src)} nicht uebersetzt`);
			const a = readFileSync(path.join(FRONTEND, 'static', b.src.slice(1)));
			const e = readFileSync(path.join(FRONTEND, 'static', enB[i].src.slice(1)));
			assert.ok(!a.equals(e), `${name(b.src)}: en-Datei ist eine Kopie der de-Datei`);
		});
	});

	test('Renderer-Bilder fuer alle vier Kanaele und Alarm vorhanden', async () => {
		const namen = bilder(await renderFunktionen('de')).map((b) => b.src.split('/').pop()!);
		for (const muster of [/mail/, /telegram/, /(^|-)sms/, /premium-sms/, /alarm/]) {
			assert.ok(namen.some((n) => muster.test(n)), `kein Bild zu ${muster}`);
		}
	});
});

describe('AC-10: Befehlsliste aus der Hilfe-Quelle, Kanalhinweis', () => {
	const befehlsKeys = keys.filter((k) => /^hilfe\.befehle\.[^.]+\.befehl$/.test(k));
	test('Messaufbau: 15 Befehle in der Hilfe-Quelle', () => {
		assert.equal(befehlsKeys.length, 15);
	});
	for (const lang of SPRACHEN) {
		test(`${lang}: Abschnitt #befehle zeigt genau die Befehle der Hilfe`, async () => {
			const abschnitt = abschnittHtml(await renderFunktionen(lang), 'befehle');
			const gezeigt = [...abschnitt.matchAll(/<code\b[^>]*>([\s\S]*?)<\/code>/g)].map((m) => nurText(m[1]).trim());
			const soll = befehlsKeys.map((k) => txt(lang, k));
			assert.deepEqual([...gezeigt].sort(), [...soll].sort(), `${lang}: Befehlsliste weicht von der Hilfe ab`);
		});
		test(`${lang}: Hinweis, ueber welche Kanaele Befehle ankommen`, async () => {
			const text = nurText(abschnittHtml(await renderFunktionen(lang), 'befehle'));
			assert.match(text, /E-Mail|email/i);
			assert.match(text, /Telegram/);
			assert.match(text, /Premium-SMS/);
			assert.match(text, lang === 'de' ? /SMS[^.]*nur[^.]*empfang|nur[^.]*empfang[^.]*SMS/i : /SMS[^.]*receive only|receive[^.]*only[^.]*SMS|only[^.]*receiv[^.]*SMS|SMS[^.]*only[^.]*receiv/i);
		});
	}
});
