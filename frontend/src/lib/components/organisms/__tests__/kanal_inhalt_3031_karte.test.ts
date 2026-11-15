// TDD RED — Issue #3031 (Inhalt je Kanal A1): Organismus KanalInhaltKarte im Reiter Wetter.
// Spec: docs/specs/modules/feat_3031_inhalt_je_kanal_listen.md — Test Plan 5, 6, 7 (Anzeige), 12
// (AC-1, AC-4, AC-5, AC-6, AC-12), Affected Files (Einbindung in WetterTabInhalt).
//
// Vertrag (hier festgelegt, /50 baut danach):
//   organisms/wetter-tab/KanalInhaltKarte.svelte, Props:
//     context: 'route' | 'vergleich'
//     listen: KanalListen                          // aus kanalInhalt.ts
//     metriken: Record<id, { label, col_label, sms_code, format_modes, default_format_mode, has_friendly_format }>
//     kanal?: Kanal                                // anfangs gewaehltes Segment (Default 'email')
//     onAendern: (listen: KanalListen) => void
//   Anker (data-testid):
//     kanal-inhalt-karte                Karte
//     kanal-inhalt-segment-<kanal>      Segment-Eintrag je Kanal (email, telegram, sms, premium_sms)
//     kanal-inhalt-liste                Listenbereich des gewaehlten Kanals (Attribut data-kanal="<kanal>")
//     kanal-inhalt-zeile-<id>           Zeile je Metrik (Attribut data-enabled="true|false")
//     kanal-inhalt-schalter-<id>        Schalter (Atom Switch)
//     kanal-inhalt-format-<id>          Roh/Einfach (nur bei Wahl laut Katalog, siehe Modell-Test)
//     kanal-inhalt-beispiel-<id>        Beispiel der gewaehlten Darstellung (kanalInhaltBeispiele.ts)
//     kanal-inhalt-warnungen            feste Zeile „Amtliche Warnungen" (kein Griff, kein Schalter)
//     kanal-inhalt-premium-hinweis      Hinweis „folgt der SMS-Liste" (nur Segment Premium-SMS)
//   Texte (Katalog wetter.json, DE und EN, gleiche Schluessel):
//     wetter.kanal_inhalt.titel, .untertitel, .warnungen, .warnungen_oben, .warnungen_unten,
//     .premium_folgt_sms
//   WetterTabInhalt.svelte bindet die Karte zwischen WarnungenRadarKarte und AnpassenKarte ein.
//
// Verhalten per Server-Render (svelte/server, Muster wetter_tab_scheibe_c.test.ts);
// die Einbindung in WetterTabInhalt ist eine Quellregel: // doc-compliance-test
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/kanal_inhalt_3031_karte.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { parse } from 'svelte/compiler';

import { locale } from '../../../i18n/index.ts';
import { kanalInhaltBeispiele, katalogNachId } from '../../shared/wetter-tab/__tests__/kanalInhaltPruefstand.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
const WT = path.resolve(HERE, '..', 'wetter-tab');
const MSG = path.join(FRONTEND, 'src', 'lib', 'i18n', 'messages');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');

const KAT = (sprache: 'de' | 'en'): Record<string, string> => JSON.parse(readFileSync(path.join(MSG, sprache, 'wetter.json'), 'utf8'));
const KARTE = path.join(WT, 'KanalInhaltKarte.svelte');

async function karte(): Promise<any> {
	if (!existsSync(KARTE)) assert.fail('TDD RED: organisms/wetter-tab/KanalInhaltKarte.svelte fehlt');
	return (await import(pathToFileURL(KARTE).href)).default;
}
const text = (h: string) => h.replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]*>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();
const tag = (h: string, id: string) => h.match(new RegExp(`<[a-z]+\\b[^>]*data-testid="${id}"[^>]*>`))?.[0] ?? null;

/** Vollstaendiges Element (inkl. Kinder) mit `data-testid="<id>"` — Tiefenzaehlung gleichnamiger Tags. */
function element(h: string, id: string): string | null {
	const start = h.search(new RegExp(`<([a-z]+)\\b[^>]*data-testid="${id}"`));
	if (start < 0) return null;
	const name = h.slice(start + 1).match(/^[a-z]+/)![0];
	const re = new RegExp(`<${name}\\b[^>]*?(/?)>|</${name}>`, 'g');
	re.lastIndex = start;
	let tiefe = 0;
	for (let m = re.exec(h); m; m = re.exec(h)) {
		if (m[0].startsWith('</')) tiefe--;
		else if (m[1] !== '/') tiefe++;
		if (tiefe === 0) return h.slice(start, re.lastIndex);
	}
	return h.slice(start);
}
const zeilenIds = (h: string) => [...h.matchAll(/data-testid="kanal-inhalt-zeile-([a-z0-9_]+)"/g)].map((m) => m[1]);

type Zeile = { id: string; enabled: boolean; format: 'roh' | 'einfach' };
const LISTEN = (): Record<'email' | 'telegram' | 'sms', Zeile[]> => ({
	email: [
		{ id: 'temperature', enabled: true, format: 'roh' },
		{ id: 'gust', enabled: true, format: 'einfach' },
		{ id: 'precipitation', enabled: false, format: 'roh' }
	],
	telegram: [
		{ id: 'gust', enabled: true, format: 'roh' },
		{ id: 'temperature', enabled: true, format: 'roh' },
		{ id: 'precipitation', enabled: true, format: 'roh' }
	],
	sms: [
		{ id: 'precipitation', enabled: true, format: 'roh' },
		{ id: 'temperature', enabled: true, format: 'roh' },
		{ id: 'gust', enabled: false, format: 'roh' }
	]
});
const NAMEN: Record<string, Record<'de' | 'en', string>> = {
	temperature: { de: 'Temperatur', en: 'Temperature' },
	gust: { de: 'Böen', en: 'Wind gusts' },
	precipitation: { de: 'Niederschlag', en: 'Precipitation' }
};
function metriken(lang: 'de' | 'en') {
	const k = katalogNachId();
	return Object.fromEntries(Object.keys(NAMEN).map((id) => [id, { ...k[id], label: NAMEN[id][lang] }]));
}
const noop = () => {};
async function html(kanal: string, lang: 'de' | 'en' = 'de', context: 'route' | 'vergleich' = 'route'): Promise<string> {
	const K = await karte();
	locale.set(lang);
	return render(K, { props: { context, listen: LISTEN(), metriken: metriken(lang), kanal, onAendern: noop } }).body;
}
afterEach(() => locale.set('de'));

// ─── AC-1: Segment und Zeilen mit Namen ──────────────────────────────────────

describe('AC-1: Segment E-Mail · Telegram · SMS · Premium-SMS, Liste des gewaehlten Kanals', () => {
	test('vier Segment-Eintraege; Liste des gewaehlten Kanals in seiner Reihenfolge', async () => {
		const h = await html('telegram');
		for (const k of ['email', 'telegram', 'sms', 'premium_sms']) assert.ok(tag(h, `kanal-inhalt-segment-${k}`), `Segment ${k} fehlt`);
		const liste = element(h, 'kanal-inhalt-liste');
		assert.ok(liste, 'Listenbereich fehlt');
		assert.match(tag(liste!, 'kanal-inhalt-liste')!, /data-kanal="telegram"/);
		assert.deepEqual(zeilenIds(liste!), ['gust', 'temperature', 'precipitation']);
	});

	test('Name „Temperatur (Temp | T)" aus dem Katalog; Aus-Zeile steht mit data-enabled="false" an ihrer Position', async () => {
		const h = await html('email');
		assert.match(text(element(h, 'kanal-inhalt-zeile-temperature') ?? ''), /Temperatur \(Temp \| T\)/);
		assert.match(text(element(h, 'kanal-inhalt-zeile-gust') ?? ''), /Böen \(Gust \| G\)/);
		assert.deepEqual(zeilenIds(element(h, 'kanal-inhalt-liste') ?? ''), ['temperature', 'gust', 'precipitation']);
		assert.match(tag(h, 'kanal-inhalt-zeile-precipitation') ?? '', /data-enabled="false"/);
		assert.match(tag(h, 'kanal-inhalt-schalter-precipitation') ?? '', /aria-checked="false"/);
		assert.match(tag(h, 'kanal-inhalt-schalter-temperature') ?? '', /aria-checked="true"/);
	});

	test('Trip und Vergleich rendern dieselbe Karte (derselbe Code, AC-9)', async () => {
		const strip = (h: string) => zeilenIds(h).join(',') + '|' + text(h);
		assert.equal(strip(await html('sms', 'de', 'vergleich')), strip(await html('sms', 'de', 'route')));
	});
});

// ─── AC-4 / Test 7: Roh/Einfach nur bei Wahl, Beispiel der gewaehlten Darstellung ──

describe('AC-4: Roh/Einfach je Zeile mit Beispiel', () => {
	test('Temperatur (nur Roh im Katalog) ohne Umschalter; Boeen mit Umschalter', async () => {
		const h = await html('email');
		assert.equal(tag(h, 'kanal-inhalt-format-temperature'), null, 'Temperatur hat keine Einfach-Darstellung');
		assert.ok(tag(h, 'kanal-inhalt-format-gust'), 'Boeen ohne Roh/Einfach');
	});

	test('Beispiel zeigt die gewaehlte Darstellung je Kanal (E-Mail Einfach, Telegram Roh)', async () => {
		const b = await kanalInhaltBeispiele();
		const mail = text(element(await html('email'), 'kanal-inhalt-beispiel-gust') ?? '');
		const tg = text(element(await html('telegram'), 'kanal-inhalt-beispiel-gust') ?? '');
		assert.equal(mail, b.beispiel('gust', 'einfach', 'de'));
		assert.equal(tg, b.beispiel('gust', 'roh', 'de'));
	});
});

// ─── AC-5 / Test 6: Amtliche Warnungen ───────────────────────────────────────

describe('Test 6 (AC-5): „Amtliche Warnungen" fest — oben bei E-Mail/Telegram, unten bei SMS/Premium-SMS', () => {
	for (const [kanal, pos] of [['email', 'oben'], ['telegram', 'oben'], ['sms', 'unten'], ['premium_sms', 'unten']] as const) {
		test(`${kanal}: Warnungs-Zeile ${pos}, ohne Griff und Schalter, nicht in der Sortierzone`, async () => {
			const h = await html(kanal);
			const liste = element(h, 'kanal-inhalt-liste') ?? '';
			const w = element(liste, 'kanal-inhalt-warnungen');
			assert.ok(w, 'Warnungs-Zeile fehlt im Listenbereich');
			const iW = liste.indexOf('data-testid="kanal-inhalt-warnungen"');
			const zeilen = [...liste.matchAll(/data-testid="kanal-inhalt-zeile-/g)].map((m) => m.index!);
			assert.ok(zeilen.length > 0, 'keine Metrik-Zeilen');
			if (pos === 'oben') assert.ok(iW < zeilen[0], 'Warnungen stehen nicht ganz oben');
			else assert.ok(iW > zeilen.at(-1)!, 'Warnungen stehen nicht am Ende');
			assert.doesNotMatch(w!, /role="switch"/, 'Warnungs-Zeile hat einen Schalter');
			assert.doesNotMatch(w!, /data-testid="drag-handle"/, 'Warnungs-Zeile hat einen Griff');
			const zone = liste.match(/<div\b[^>]*class="sortable-zone[\s\S]*/)?.[0] ?? '';
			const zoneEl = zone ? element(zone.replace(/^<div\b/, '<div data-testid="zz-zone"'), 'zz-zone') ?? '' : '';
			assert.ok(!zoneEl.includes('kanal-inhalt-warnungen'), 'Warnungs-Zeile liegt in der Sortierzone (waere ziehbar)');
		});
	}
});

// ─── AC-6 / Test 5: Premium-SMS ──────────────────────────────────────────────

describe('Test 5 (AC-6): Premium-SMS zeigt die SMS-Liste schreibgeschuetzt mit Hinweis', () => {
	test('Liste = SMS-Liste (Reihenfolge, Aus-Zeile), Hinweis „folgt der SMS-Liste" aus dem Katalog', async () => {
		const h = await html('premium_sms');
		const liste = element(h, 'kanal-inhalt-liste') ?? '';
		assert.deepEqual(zeilenIds(liste), LISTEN().sms.map((z) => z.id));
		assert.match(tag(liste, 'kanal-inhalt-zeile-gust') ?? '', /data-enabled="false"/);
		const hinweis = element(h, 'kanal-inhalt-premium-hinweis');
		assert.ok(hinweis, 'Hinweis fehlt');
		assert.ok(text(hinweis!).includes(KAT('de')['wetter.kanal_inhalt.premium_folgt_sms']), `Hinweis nicht aus dem Katalog: ${text(hinweis!)}`);
	});

	test('Schalter, Griff und Roh/Einfach sind nicht bedienbar', async () => {
		const liste = element(await html('premium_sms'), 'kanal-inhalt-liste') ?? '';
		const schalter = [...liste.matchAll(/<[a-z]+\b[^>]*role="switch"[^>]*>/g)].map((m) => m[0]);
		assert.ok(schalter.length >= 3, 'Vakuum-Schutz: Schalter je Zeile erwartet');
		for (const s of schalter) assert.match(s, /aria-disabled="true"/, `Schalter bedienbar: ${s}`);
		for (const g of [...liste.matchAll(/<[a-z]+\b[^>]*data-testid="drag-handle"[^>]*>/g)].map((m) => m[0])) {
			assert.match(g, /aria-disabled="true"/, `Griff bedienbar: ${g}`);
		}
		for (const b of [...liste.matchAll(/<button\b[^>]*>/g)].map((m) => m[0])) assert.match(b, /\sdisabled\b/, `Knopf bedienbar: ${b}`);
	});

	test('Gegenprobe SMS: dieselbe Liste ist dort bedienbar, ohne Hinweis', async () => {
		const h = await html('sms');
		assert.equal(tag(h, 'kanal-inhalt-premium-hinweis'), null);
		assert.doesNotMatch(tag(h, 'kanal-inhalt-schalter-temperature') ?? '', /aria-disabled="true"/);
	});
});

// ─── AC-12 / Test 12: DE/EN aus wetter.json ──────────────────────────────────

describe('Test 12 (AC-12): Texte aus dem Katalog wetter.json, DE und EN; Kuerzel bleiben', () => {
	const SCHLUESSEL = [
		'wetter.kanal_inhalt.titel',
		'wetter.kanal_inhalt.untertitel',
		'wetter.kanal_inhalt.warnungen',
		'wetter.kanal_inhalt.warnungen_oben',
		'wetter.kanal_inhalt.warnungen_unten',
		'wetter.kanal_inhalt.premium_folgt_sms'
	];

	test('die Schluessel stehen in DE und EN, nicht leer, EN ist uebersetzt', () => {
		const de = KAT('de');
		const en = KAT('en');
		for (const k of SCHLUESSEL) {
			assert.ok(typeof de[k] === 'string' && de[k].trim(), `TDD RED: ${k} fehlt in de/wetter.json`);
			assert.ok(typeof en[k] === 'string' && en[k].trim(), `TDD RED: ${k} fehlt in en/wetter.json`);
			assert.notEqual(en[k], de[k], `${k}: EN gleich DE`);
		}
		assert.equal(de['wetter.kanal_inhalt.titel'], 'Inhalt je Kanal und Fläche', 'Titel laut Mockup Fassung 3');
	});

	for (const lang of ['de', 'en'] as const) {
		test(`${lang}: Titel, Untertitel, Warnungs-Zeilen, Hinweis und Beispiele aus dem ${lang}-Katalog; Kuerzel T bleibt T`, async () => {
			const kat = KAT(lang);
			const b = await kanalInhaltBeispiele();
			const mail = text(await html('email', lang));
			const sms = text(await html('sms', lang));
			const premium = text(await html('premium_sms', lang));
			for (const k of ['wetter.kanal_inhalt.titel', 'wetter.kanal_inhalt.untertitel', 'wetter.kanal_inhalt.warnungen', 'wetter.kanal_inhalt.warnungen_oben']) {
				assert.ok(mail.includes(kat[k]), `${lang}/E-Mail: ${k} („${kat[k]}") fehlt`);
			}
			assert.ok(sms.includes(kat['wetter.kanal_inhalt.warnungen_unten']), `${lang}/SMS: warnungen_unten fehlt`);
			assert.ok(premium.includes(kat['wetter.kanal_inhalt.premium_folgt_sms']), `${lang}/Premium: Hinweis fehlt`);
			assert.ok(mail.includes(b.beispiel('gust', 'einfach', lang)), `${lang}: Beispiel nicht in der Nutzersprache`);
			assert.match(mail, new RegExp(`${NAMEN.temperature[lang]} \\(Temp \\| T\\)`), `${lang}: Kuerzel T veraendert`);
			const andere = KAT(lang === 'de' ? 'en' : 'de');
			for (const k of SCHLUESSEL) {
				if (andere[k] && andere[k] !== kat[k]) assert.ok(!(mail + sms + premium).includes(andere[k]), `${lang}: Text der anderen Sprache (${k}) sichtbar`);
			}
		});
	}
});

// ─── Einbindung in WetterTabInhalt (Quellregel) ──────────────────────────────

describe('WetterTabInhalt bindet die Karte zwischen Warnungen/Radar und Anpassen ein (doc-compliance-test)', () => {
	type Knoten = Record<string, any>;
	function alle(x: unknown, pred: (n: Knoten) => boolean, aus: Knoten[] = []): Knoten[] {
		if (Array.isArray(x)) x.forEach((y) => alle(y, pred, aus));
		else if (x && typeof x === 'object') {
			const n = x as Knoten;
			if (pred(n)) aus.push(n);
			for (const [k, v] of Object.entries(n)) if (k !== 'parent') alle(v, pred, aus);
		}
		return aus;
	}

	test('Reihenfolge WarnungenRadarKarte → KanalInhaltKarte → AnpassenKarte, Import aus ./KanalInhaltKarte.svelte', () => {
		const q = readFileSync(path.join(WT, 'WetterTabInhalt.svelte'), 'utf8');
		const a = parse(q, { modern: true }) as unknown as Knoten;
		const imp = (a.instance?.content?.body ?? []).find(
			(s: Knoten) => s.type === 'ImportDeclaration' && s.specifiers.some((sp: Knoten) => sp.local?.name === 'KanalInhaltKarte')
		);
		assert.ok(imp, 'TDD RED: WetterTabInhalt importiert KanalInhaltKarte nicht');
		assert.match(String(imp.source.value), /^\.\/KanalInhaltKarte\.svelte$/);
		const namen = alle(a.fragment, (n) => n.type === 'Component' && ['WarnungenRadarKarte', 'KanalInhaltKarte', 'AnpassenKarte'].includes(n.name))
			.sort((x, y) => x.start - y.start)
			.map((n) => n.name);
		assert.deepEqual(namen, ['WarnungenRadarKarte', 'KanalInhaltKarte', 'AnpassenKarte']);
	});

	test('die Karte bekommt context, listen und onAendern (Stand des Reiters, ein Speicherer)', () => {
		const q = readFileSync(path.join(WT, 'WetterTabInhalt.svelte'), 'utf8');
		const a = parse(q, { modern: true }) as unknown as Knoten;
		const k = alle(a.fragment, (n) => n.type === 'Component' && n.name === 'KanalInhaltKarte');
		assert.equal(k.length, 1, 'KanalInhaltKarte nicht genau einmal eingebunden');
		const attr = (k[0].attributes as Knoten[]).map((x) => (x.type === 'Attribute' ? x.name : x.name ?? x.type));
		for (const p of ['context', 'listen', 'onAendern']) assert.ok(attr.includes(p), `Prop ${p} fehlt an KanalInhaltKarte: ${attr.join(', ')}`);
	});
});
