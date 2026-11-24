// Issue #3337 — Seitenkopf der Funktionsseiten: Angemeldete sehen statt des
// wirkungslosen Sprach-Umschalters einen Hinweis mit Link zur Sprachwahl im Konto;
// Besucher ohne Anmeldung behalten den Umschalter.
// Spec: docs/specs/modules/sprachumschalter_angemeldet_3337.md
//
// AC-1/AC-2 (angemeldet DE/EN: Hinweis, kein Umschalter), AC-4 (abgemeldet: Umschalter,
// kein Hinweis), AC-7 (Texte aus dem Katalog, DE/EN-Paritaet, kein fester Text),
// AC-9 (Matrix 2x2, je Kombination genau ein Element, kein Zustands-Uebertrag).
//
// ECHT gerendert (svelte/server). Der Anmeldestatus kommt — wie im Browser — aus
// den Layout-Daten `page.data.userId` (`$app/state`). Ausserhalb von Vite gibt es
// `$app/state` nicht; der Stub unten liest die Seitendaten bei JEDEM Zugriff frisch
// aus `globalThis.__gzKopfSeitenDaten` (Vorbild routes/__tests__/layout-ssr-hooks.mjs),
// damit kein Rendering den Zustand des vorigen sieht.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/organisms/funktionen/__tests__/funktionen_kopf_sprache.test.ts

import { test, describe, after, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const KOMPONENTEN = path.resolve(HERE, '..');
const LIB = path.resolve(HERE, '../../../..');
const FRONTEND = path.resolve(LIB, '../..');
const ROUTES = path.join(FRONTEND, 'src', 'routes');
const base = pathToFileURL(FRONTEND + '/').href;

// `$app/state`-Stub: Seitendaten je Test einstellbar, bei jedem Zugriff frisch gelesen.
const STATE_STUB = `
export const page = {
	get url() { return new URL(globalThis.__gzKopfPfad ?? '/funktionen', 'http://localhost'); },
	get data() { return globalThis.__gzKopfSeitenDaten ?? {}; },
	params: {}, route: { id: null }, status: 200, error: null, form: null
};
export const navigating = { from: null, to: null, type: null };
export const updated = { current: false, check: async () => false };
`;
const STATE_HOOK = `
const STUB = ${JSON.stringify(STATE_STUB)};
export async function resolve(specifier, context, nextResolve) {
	if (specifier === '$app/state') {
		return { url: 'data:text/javascript,' + encodeURIComponent(STUB), shortCircuit: true };
	}
	return nextResolve(specifier, context);
}
`;

const hook = (p: string) => register(pathToFileURL(p).href, base);
hook(path.join(FRONTEND, 'test-app-environment-stub-hooks.mjs'));
hook(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs'));
hook(path.join(LIB, 'components/trip-new/__tests__/ssrRunesHook.mjs'));
register('data:text/javascript,' + encodeURIComponent(STATE_HOOK), base);

const { render } = await import('svelte/server');
const { locale, trFor } = await import(pathToFileURL(path.join(LIB, 'i18n', 'index.ts')).href);
const { de } = await import(pathToFileURL(path.join(LIB, 'i18n', 'messages', 'de', 'index.ts')).href);
const { en } = await import(pathToFileURL(path.join(LIB, 'i18n', 'messages', 'en', 'index.ts')).href);
const { FUNKTIONEN_SEITEN } = await import(pathToFileURL(path.join(LIB, 'funktionen_seiten.ts')).href);
const ladeKomponente = async (abs: string) => (await import(pathToFileURL(abs).href)).default;

type Lang = 'de' | 'en';
type Zustand = 'angemeldet' | 'abgemeldet';
const SPRACHEN: Lang[] = ['de', 'en'];
const ZUSTAENDE: Zustand[] = ['angemeldet', 'abgemeldet'];

const KEY_HINWEIS = 'konto.sprache.hinweis_angemeldet';
const KEY_LINK = 'konto.sprache.hinweis_link';
/** Freigegebener Wortlaut (Spec, Implementation Details). */
const SOLL: Record<Lang, { hinweis: string; link: string }> = {
	de: { hinweis: 'Die Sprache stellst du in deinem Konto ein.', link: 'Zum Konto' },
	en: { hinweis: 'You set your language in your account.', link: 'Go to account' }
};
const LINK_ZIEL = '/account#sprache';

// ─── HTML-Helfer ────────────────────────────────────────────────────────────
const ent = (s: string) =>
	s.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>');
const nurText = (html: string) =>
	ent(html.replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ').trim();
const anzahl = (html: string, testid: string) =>
	(html.match(new RegExp(`\\bdata-testid="${testid}"`, 'g')) ?? []).length;

/** Element mit `data-testid="sprach-hinweis"` samt Inhalt (bis zum passenden Schlusstag). */
function hinweisHtml(html: string): string {
	const m = html.match(/<(\w+)\b[^>]*\bdata-testid="sprach-hinweis"[^>]*>/);
	assert.ok(m, 'Hinweis data-testid="sprach-hinweis" fehlt');
	const tag = m![1];
	const start = m!.index!;
	// Verschachtelung desselben Tags mitzaehlen.
	const re = new RegExp(`<${tag}\\b[^>]*>|<\\/${tag}>`, 'g');
	re.lastIndex = start;
	let tiefe = 0;
	for (let t = re.exec(html); t; t = re.exec(html)) {
		tiefe += t[0].startsWith('</') ? -1 : 1;
		if (tiefe === 0) return html.slice(start, t.index + t[0].length);
	}
	return html.slice(start);
}

function links(html: string): { href: string; text: string }[] {
	return [...html.matchAll(/<a\b([^>]*)>([\s\S]*?)<\/a>/g)].map((m) => ({
		href: ent(m[1].match(/\bhref="([^"]*)"/)?.[1] ?? ''),
		text: nurText(m[2])
	}));
}

// ─── Rendern mit getrennten Seitendaten je Zustand ──────────────────────────
type G = typeof globalThis & { __gzKopfSeitenDaten?: Record<string, unknown>; __gzKopfPfad?: string };
const g = globalThis as G;

function setzeZustand(zustand: Zustand, lang: Lang, pfad = '/funktionen') {
	// Je Aufruf ein NEUES Objekt: kein Uebertrag zwischen den Faellen.
	g.__gzKopfSeitenDaten =
		zustand === 'angemeldet'
			? { userId: `pruef-${lang}-${Math.random().toString(36).slice(2)}`, lang, oeffentlich: true }
			: { userId: undefined, lang, oeffentlich: true };
	g.__gzKopfPfad = pfad;
	locale.set(lang);
}

async function renderKopf(zustand: Zustand, lang: Lang): Promise<string> {
	setzeZustand(zustand, lang);
	const Kopf = await ladeKomponente(path.join(KOMPONENTEN, 'FunktionenKopf.svelte'));
	return render(Kopf, { props: {} }).body;
}

async function renderUebersicht(zustand: Zustand, lang: Lang): Promise<string> {
	setzeZustand(zustand, lang, '/funktionen');
	const Seite = await ladeKomponente(path.join(ROUTES, 'funktionen', '+page.svelte'));
	return render(Seite, { props: { data: { oeffentlich: true, lang } } }).body;
}

async function renderUnterseite(zustand: Zustand, lang: Lang, slug: string): Promise<string> {
	setzeZustand(zustand, lang, `/funktionen/${slug}`);
	const Seite = await ladeKomponente(path.join(ROUTES, 'funktionen', '[thema]', '+page.svelte'));
	return render(Seite, { props: { data: { oeffentlich: true, lang, slug } } }).body;
}

/** Erwartung je Zustand: angemeldet ⇒ genau ein Hinweis, kein Umschalter; abgemeldet umgekehrt. */
function pruefeKopf(html: string, zustand: Zustand, lang: Lang, wo: string) {
	const umschalter = anzahl(html, 'sprach-umschalter');
	const hinweis = anzahl(html, 'sprach-hinweis');
	if (zustand === 'abgemeldet') {
		assert.equal(umschalter, 1, `${wo} (${zustand}, ${lang}): genau ein Umschalter erwartet, gefunden ${umschalter}`);
		assert.equal(hinweis, 0, `${wo} (${zustand}, ${lang}): kein Konto-Hinweis erwartet, gefunden ${hinweis}`);
		return;
	}
	assert.equal(umschalter, 0, `${wo} (${zustand}, ${lang}): Umschalter darf fuer Angemeldete nicht erscheinen`);
	assert.equal(hinweis, 1, `${wo} (${zustand}, ${lang}): genau ein Konto-Hinweis erwartet, gefunden ${hinweis}`);
	const h = hinweisHtml(html);
	const text = nurText(h);
	assert.ok(text.includes(SOLL[lang].hinweis), `${wo} (${lang}): Hinweistext „${SOLL[lang].hinweis}“ fehlt, ist „${text}“`);
	const l = links(h);
	assert.equal(l.length, 1, `${wo} (${lang}): im Hinweis genau ein Link erwartet, gefunden ${l.length}`);
	assert.equal(l[0].href, LINK_ZIEL, `${wo} (${lang}): Link muss auf ${LINK_ZIEL} zeigen`);
	assert.equal(l[0].text, SOLL[lang].link, `${wo} (${lang}): Linktext`);
	// Kein Text der jeweils anderen Sprache (fest eingetragener Text faellt hier auf).
	const andere: Lang = lang === 'de' ? 'en' : 'de';
	assert.ok(!text.includes(SOLL[andere].hinweis), `${wo} (${lang}): Hinweis in der falschen Sprache`);
	assert.ok(!text.includes(SOLL[andere].link), `${wo} (${lang}): Linktext in der falschen Sprache`);
}

beforeEach(() => {
	g.__gzKopfSeitenDaten = undefined;
});
after(() => {
	locale.set('de');
	g.__gzKopfSeitenDaten = undefined;
	g.__gzKopfPfad = undefined;
});

// ════════════════════════════════════════════════════════════════════════════
describe('AC-7: Hinweistexte stehen in DE und EN im Katalog', () => {
	for (const lang of SPRACHEN) {
		test(`${lang}: ${KEY_HINWEIS} und ${KEY_LINK} mit freigegebenem Wortlaut`, () => {
			const katalog = (lang === 'de' ? de : en) as Record<string, string>;
			assert.equal(katalog[KEY_HINWEIS], SOLL[lang].hinweis, `${lang}: ${KEY_HINWEIS}`);
			assert.equal(katalog[KEY_LINK], SOLL[lang].link, `${lang}: ${KEY_LINK}`);
			assert.equal(trFor(lang, KEY_HINWEIS), SOLL[lang].hinweis);
			assert.equal(trFor(lang, KEY_LINK), SOLL[lang].link);
		});
	}
});

describe('AC-1/AC-2/AC-4/AC-9: Matrix 2x2 am Seitenkopf', () => {
	for (const zustand of ZUSTAENDE) {
		for (const lang of SPRACHEN) {
			test(`${zustand} · ${lang}: genau das erwartete Element`, async () => {
				pruefeKopf(await renderKopf(zustand, lang), zustand, lang, 'FunktionenKopf');
			});
		}
	}

	test('kein Zustands-Uebertrag: abwechselnd gerendert bleibt jede Kombination richtig', async () => {
		const folge: Array<[Zustand, Lang]> = [
			['angemeldet', 'de'],
			['abgemeldet', 'de'],
			['angemeldet', 'en'],
			['abgemeldet', 'en'],
			['abgemeldet', 'de'],
			['angemeldet', 'de']
		];
		for (const [zustand, lang] of folge) {
			pruefeKopf(await renderKopf(zustand, lang), zustand, lang, `Folge ${zustand}/${lang}`);
		}
	});
});

describe('AC-1/AC-2/AC-4: Uebersicht und jede Unterseite in beiden Zustaenden', () => {
	const slugs = (FUNKTIONEN_SEITEN as Array<{ slug: string }>).map((s) => s.slug);
	test('Messaufbau: Unterseiten vorhanden', () => {
		assert.ok(slugs.includes('trips'), 'Unterseite trips fehlt in der Seitenliste');
	});
	for (const zustand of ZUSTAENDE) {
		for (const lang of SPRACHEN) {
			test(`${zustand} · ${lang}: /funktionen und alle /funktionen/<thema>`, async () => {
				pruefeKopf(await renderUebersicht(zustand, lang), zustand, lang, '/funktionen');
				for (const slug of slugs) {
					pruefeKopf(await renderUnterseite(zustand, lang, slug), zustand, lang, `/funktionen/${slug}`);
				}
			});
		}
	}
});
