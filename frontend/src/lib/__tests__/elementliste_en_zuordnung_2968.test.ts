// TDD RED — Issue #2968, Workflow feat-2968-en-katalogtexte.
// Spec: docs/specs/modules/feat_2968_elementliste_en_zuordnung.md — AC-1 bis AC-6, AC-8, AC-9.
//
// EN-Zuordner des Elementlisten-Generators: Regel a (Platzhalter-Muster mit aufgelösten Werten, rekursiv,
// Tiefe ≤ 2), Regel b („ · “-Segmente, führendes „· “), Regel c (sprachneutral), Regel d (Metriknamen aus
// dem Schnappschuss), Abgleich `erwartung` für sprachneutrale Einträge, Eigennamen-Schnappschuss,
// Messgröße und Besitzer über die eingecheckte Elementliste.
// Ohne Browser, ohne Mocks, gegen den echten i18n-Katalog (`ladeKatalog`) und die echten Dateien unter
// docs/context/einstellungen_neu/. Reduzierte Kataloge entstehen nur als Kopie des echten Katalogs im
// Speicher (ein Schlüssel entfernt), um beide Ausgänge eines Falls zu zeigen; synthetische Mini-Kataloge
// nur für die Rekursionstiefe und den Schnappschuss-Parameter (wie elementliste_en_schutz.test.ts).
//
// Vertrag (vom Developer in scripts/elementliste_aus_mockup.ts umzusetzen):
//   export type Bekannte = { metriknamen: string[]; token: string[]; eigennamen: string[] };
//     metriknamen = DE-Metriknamen (label_de, alert_label) aus daten/metriknamen.json   (Regel a/d)
//     token       = Kurz-/Protokoll-Token (sms_code, sms_multi_symbols, kuerzel, compact_label, col_label)
//                   aus daten/metriknamen.json                                           (Regel c.3)
//     eigennamen  = `text` aller Einträge aus daten/eigennamen.json                     (Regel c.4)
//   export function ladeBekannte(datenDir?: string): Bekannte
//     Standard datenDir = docs/context/einstellungen_neu/daten (liest die Schnappschüsse, kein Python).
//   export function ermittleEn(textDe: string, katalog: Katalog, bekannte?: Bekannte): EnErgebnis
//     ohne `bekannte` gilt ladeBekannte() (Standard-Schnappschüsse).
//   EnErgebnis bekommt `sprachneutral?: boolean` (true nur nach Regel c; sonst false oder fehlend).
//   Sprachneutral: text_en = DE-Muster (Zahlen als `{zahl}`), i18n_key = null, luecke = false.
//   Segmente: i18n_key = null, text_en = Segment-EN mit „ · “ verbunden (führendes „· “ bleibt vorn).
// Rekursionstiefe: das äußere Muster ist Tiefe 1, ein Muster als Wert darin Tiefe 2; exakte Katalogwerte,
// Metriknamen, Zahlen zählen nicht als Ebene. „Darstellung Böen in Telegram: Roh“ hat Tiefe 2.
//
// Daten-Schnappschuss eigennamen.json: { "eigennamen": [ { "text": string, "quelle": string } ] }
//   (text exakt und normalisiert, quelle = Fundstelle im Mockup bzw. Prüfkonto #2967).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/__tests__/elementliste_en_zuordnung_2968.test.ts
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
// Namensraum-Import: fehlt eine Funktion des Vertrags, scheitert der einzelne Test mit klarer Meldung,
// nicht die ganze Datei beim Laden.
import * as gen from '../../../../scripts/elementliste_aus_mockup.ts';
import type { Katalog } from '../../../../scripts/elementliste_aus_mockup.ts';
import * as logik from '../../../e2e/elementliste_abgleich_logik.ts';
import type { ListenElement } from '../../../e2e/elementliste_abgleich_logik.ts';

const REPO = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..', '..', '..');
const DATEN = join(REPO, 'docs/context/einstellungen_neu/daten');
const EIGENNAMEN = join(DATEN, 'eigennamen.json');
const METRIKNAMEN = join(DATEN, 'metriknamen.json');
const MOCKUP = join(REPO, 'docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html');
const LISTE = join(REPO, 'docs/context/einstellungen_neu/elementliste.json');
const BESITZER = join(REPO, 'docs/context/einstellungen_neu/elementliste_besitzer.json');

const katalog = gen.ladeKatalog(join(REPO, 'frontend/src/lib/i18n/messages'));
const norm = (s: string) => s.replace(/\s+/g, ' ').trim();

type Bekannte = { metriknamen: string[]; token: string[]; eigennamen: string[] };
type Ergebnis = { i18n_key: string | null; text_en: string | null; muster: string | null; luecke: boolean; sprachneutral?: boolean };
type Ermittle = (t: string, k: Katalog, b?: Bekannte) => Ergebnis;

function bekannte(): Bekannte {
	const lade = (gen as Record<string, unknown>).ladeBekannte as ((dir?: string) => Bekannte) | undefined;
	assert.equal(typeof lade, 'function', 'ladeBekannte fehlt in scripts/elementliste_aus_mockup.ts (Regel d)');
	return lade!();
}
const ermittle: Ermittle = (t, k, b) => (gen.ermittleEn as unknown as Ermittle)(t, k, b);
const mitBekannten = (t: string, k: Katalog = katalog) => ermittle(t, k, bekannte());

/** Kopie des echten Katalogs ohne alle Schlüssel, deren DE-Wert (normalisiert) einer der Texte ist. */
function ohneWerte(...werte: string[]): Katalog {
	const de: Record<string, string> = {};
	const en: Record<string, string> = {};
	for (const [k, v] of Object.entries(katalog.de)) {
		if (werte.includes(norm(v))) continue;
		de[k] = v;
		en[k] = katalog.en[k];
	}
	return { de, en };
}
const keyVonWert = (wert: string) => Object.keys(katalog.de).filter((k) => norm(katalog.de[k]) === wert).sort();

describe('#2968 Schnittstelle', () => {
	test('ladeBekannte liest beide Schnappschüsse (Metriknamen, Token, Eigennamen)', () => {
		assert.ok(existsSync(METRIKNAMEN), 'docs/context/einstellungen_neu/daten/metriknamen.json fehlt');
		assert.ok(existsSync(EIGENNAMEN), 'docs/context/einstellungen_neu/daten/eigennamen.json fehlt');
		const b = bekannte();
		for (const n of ['Regenwahrscheinlichkeit', 'Böen', 'Gewitter']) assert.ok(b.metriknamen.includes(n), `Metrikname ${n} fehlt`);
		for (const t of ['N', 'SL', 'SnowL', 'VS']) assert.ok(b.token.includes(t), `Token ${t} fehlt`);
		assert.ok(b.eigennamen.includes('Münster'), 'Eigenname Münster fehlt');
	});
});

describe('#2968 AC-1 Regel a: Muster mit aufgelösten Werten ohne Wortlaut-Hälfte', () => {
	test('„Regenwahrscheinlichkeit in SMS“ ⇒ wetter.wsw.zelle.sms, EN-Muster, keine Lücke', () => {
		const r = mitBekannten('Regenwahrscheinlichkeit in SMS');
		assert.equal(r.luecke, false, JSON.stringify(r));
		assert.equal(r.i18n_key, 'wetter.wsw.zelle.sms');
		assert.equal(r.text_en, katalog.en['wetter.wsw.zelle.sms']);
		assert.equal(r.muster, '{metrik} in SMS');
		assert.notEqual(r.sprachneutral, true);
	});
	test('Gegenbeispiel: unbekannter Wert bei kurzem Wortlaut ⇒ Lücke', () => {
		const r = mitBekannten('Etwas Unbekanntes in SMS');
		assert.equal(r.luecke, true, JSON.stringify(r));
		assert.equal(r.text_en, null);
	});
	test('Regel d: Metrikname zählt nur über den Schnappschuss (Parameter `bekannte`)', () => {
		// Mini-Katalog ohne exakten Wert „Regenwahrscheinlichkeit“: aufgelöst nur über die Metriknamen.
		const k = { de: { a: '{metrik} in SMS' }, en: { a: '{metrik} in SMS' } };
		const mit = ermittle('Regenwahrscheinlichkeit in SMS', k, { metriknamen: ['Regenwahrscheinlichkeit'], token: [], eigennamen: [] });
		assert.equal(mit.luecke, false, JSON.stringify(mit));
		assert.equal(mit.i18n_key, 'a');
		const ohne = ermittle('Regenwahrscheinlichkeit in SMS', k, { metriknamen: [], token: [], eigennamen: [] });
		assert.equal(ohne.luecke, true, JSON.stringify(ohne));
	});
	test('Zahl mit Einheit ist ein aufgelöster Wert, ein deutscher Satz nicht', () => {
		const k = { de: { a: 'Grenze {wert} oben' }, en: { a: 'Limit {wert} above' } };
		const leer = { metriknamen: [], token: [], eigennamen: [] };
		const zahl = ermittle('Grenze 1200 m oben', k, leer);
		assert.equal(zahl.luecke, false, JSON.stringify(zahl));
		assert.equal(zahl.text_en, 'Limit {wert} above');
		const satz = ermittle('Grenze irgendwo weit hinter dem Berg oben', k, leer);
		assert.equal(satz.luecke, true, JSON.stringify(satz));
	});
});

describe('#2968 AC-2 Regel a rekursiv (Tiefe ≤ 2)', () => {
	test('„Darstellung Böen in Telegram: Roh“ ⇒ bausteine.darstellung.name mit Platzhaltern', () => {
		const r = mitBekannten('Darstellung Böen in Telegram: Roh');
		assert.equal(r.luecke, false, JSON.stringify(r));
		assert.equal(r.i18n_key, 'bausteine.darstellung.name');
		assert.equal(r.text_en, katalog.en['bausteine.darstellung.name']);
		assert.match(r.text_en ?? '', /\{name\}/);
		assert.doesNotMatch(r.text_en ?? '', /Böen|Roh/);
	});
	test('Gegenbeispiel: unbekannter innerer Wert ⇒ Lücke', () => {
		const r = mitBekannten('Darstellung Unbekanntes in Telegram: Roh');
		assert.equal(r.luecke, true, JSON.stringify(r));
		assert.equal(r.text_en, null);
	});
	test('Tiefe 3 im echten Katalog ⇒ Lücke', () => {
		const r = mitBekannten('Darstellung Darstellung Böen in Telegram: Roh: Roh');
		assert.equal(r.luecke, true, JSON.stringify(r));
	});
	test('Tiefe 2 ⇒ Treffer, Tiefe 3 ⇒ Lücke (eindeutiger Mini-Katalog)', () => {
		const k = {
			de: { a: 'Außen {x} Ende', b: 'Mitte {y} Schluss', c: 'Innen {z} Rand', w: 'Wert' },
			en: { a: 'Outer {x} end', b: 'Middle {y} close', c: 'Inner {z} edge', w: 'Value' }
		};
		const leer = { metriknamen: [], token: [], eigennamen: [] };
		const zwei = ermittle('Außen Mitte Wert Schluss Ende', k, leer);
		assert.equal(zwei.luecke, false, JSON.stringify(zwei));
		assert.equal(zwei.i18n_key, 'a');
		assert.equal(zwei.text_en, 'Outer {x} end');
		const drei = ermittle('Außen Mitte Innen Wert Rand Schluss Ende', k, leer);
		assert.equal(drei.luecke, true, JSON.stringify(drei));
	});
});

describe('#2968 AC-3 Regel b: Segmente an „ · “', () => {
	test('„km/h · Mittelwind“ ⇒ aufgelöst, EN der Segmente mit „ · “ verbunden', () => {
		const r = mitBekannten('km/h · Mittelwind');
		assert.equal(r.luecke, false, JSON.stringify(r));
		assert.equal(r.i18n_key, null);
		assert.equal(r.text_en, 'km/h · ' + katalog.en['wetter.hinweis.wind']);
	});
	test('führendes „· grün: bis 30 km/h“ ⇒ aufgelöst, EN trägt das „· “ mit', () => {
		const r = mitBekannten('· grün: bis 30 km/h');
		assert.equal(r.luecke, false, JSON.stringify(r));
		assert.equal(r.text_en, '· ' + katalog.en['wetter.gruen.bis']);
	});
	test('Gegenbeispiel: ein unbekanntes Segment macht die ganze Zeile zur Lücke', () => {
		const r = mitBekannten('km/h · Unbekannter Satz');
		assert.equal(r.luecke, true, JSON.stringify(r));
		assert.equal(r.text_en, null);
		assert.notEqual(r.sprachneutral, true);
	});
});

describe('#2968 AC-4 Schutzfall „°C · vor der Etappe“', () => {
	test('Ist-Katalog: „vor der Etappe“ steht exakt im Katalog ⇒ Treffer über das Segment, nie über „{count} Etappe“', () => {
		const keys = keyVonWert('vor der Etappe');
		assert.ok(keys.length > 0, 'Vorbedingung: „vor der Etappe“ steht exakt im Katalog');
		const r = mitBekannten('°C · vor der Etappe');
		assert.equal(r.luecke, false, JSON.stringify(r));
		assert.equal(r.i18n_key, null);
		assert.equal(r.text_en, '°C · ' + katalog.en[keys[0]]);
		assert.doesNotMatch(r.text_en ?? '', /\{count\}/);
		assert.notEqual(r.muster, '{count} Etappe');
	});
	test('ohne „vor der Etappe“ im Katalog ⇒ Lücke, obwohl „{count} Etappe“ bleibt', () => {
		const k = ohneWerte('vor der Etappe');
		assert.ok(Object.values(k.de).includes('{count} Etappe'), 'Vorbedingung: „{count} Etappe“ bleibt im Katalog');
		const r = mitBekannten('°C · vor der Etappe', k);
		assert.equal(r.luecke, true, JSON.stringify(r));
		assert.equal(r.text_en, null);
	});
});

describe('#2968 AC-5 Regel c: sprachneutral', () => {
	const faelle: Array<[string, string]> = [
		['60%', '{zahl}%'],
		['+49 171 123', '+{zahl} {zahl} {zahl}'],
		['°C', '°C'],
		['N10', 'N{zahl}'],
		['Münster', 'Münster']
	];
	for (const [text, muster] of faelle) {
		test(`„${text}“ ⇒ sprachneutral, text_en = DE-Muster „${muster}“`, () => {
			const r = mitBekannten(text);
			assert.equal(r.sprachneutral, true, JSON.stringify(r));
			assert.equal(r.luecke, false);
			assert.equal(r.i18n_key, null);
			assert.equal(r.text_en, muster);
		});
	}
	test('„Gewitter“ ist nie sprachneutral (Katalogtreffer, kein DE als EN)', () => {
		const r = mitBekannten('Gewitter');
		assert.notEqual(r.sprachneutral, true, JSON.stringify(r));
		assert.notEqual(r.text_en, 'Gewitter');
	});
	// #3154 (AC-10): Metriknamen mit Server-EN (daten/metrik_namen.json, label_de/label_en) sind keine Lücke mehr
	// („Gewitter“ ⇒ „Thunderstorm“). Die Regel „Metrikname allein gibt kein EN“ gilt weiter für einen Namen ohne
	// EN im Schnappschuss.
	test('„Gewitterenergie (CAPE)“ ohne Katalogwert und ohne Server-EN ⇒ Lücke, obwohl es ein Metrikname im Schnappschuss ist', () => {
		assert.ok(bekannte().metriknamen.includes('Gewitterenergie (CAPE)'), 'Vorbedingung: Gewitterenergie (CAPE) ist Metrikname');
		const r = mitBekannten('Gewitterenergie (CAPE)', ohneWerte('Gewitterenergie (CAPE)'));
		assert.equal(r.luecke, true, JSON.stringify(r));
		assert.notEqual(r.sprachneutral, true);
		assert.equal(r.text_en, null);
	});
	test('#3154: „Gewitter“ ohne Katalogwert ⇒ EN aus dem Metrikname-Schnappschuss (Server-Katalog), nie DE', () => {
		const r = mitBekannten('Gewitter', ohneWerte('Gewitter'));
		assert.equal(r.luecke, false, JSON.stringify(r));
		assert.equal(r.text_en, 'Thunderstorm');
		assert.notEqual(r.sprachneutral, true);
	});
	test('deutsches Wort ohne Katalogtreffer ⇒ Lücke, nie sprachneutral', () => {
		const r = mitBekannten('Hagelschauer');
		assert.equal(r.luecke, true, JSON.stringify(r));
		assert.notEqual(r.sprachneutral, true);
	});
	test('„Münster Hauptbahnhof“ (nicht in der Eigennamen-Liste) ⇒ Lücke, nie sprachneutral', () => {
		assert.ok(!bekannte().eigennamen.includes('Münster Hauptbahnhof'));
		const r = mitBekannten('Münster Hauptbahnhof');
		assert.equal(r.luecke, true, JSON.stringify(r));
		assert.notEqual(r.sprachneutral, true);
	});
	test('Eigenname zählt nur über die Liste (Parameter `bekannte`)', () => {
		const ohne = ermittle('Münster', katalog, { metriknamen: [], token: [], eigennamen: [] });
		assert.equal(ohne.luecke, true, JSON.stringify(ohne));
		assert.notEqual(ohne.sprachneutral, true);
	});
});

describe('#2968 AC-5 Eigennamen-Schnappschuss', () => {
	test('jeder Eintrag: normalisiert, mit Quelle, steht im Mockup, ist kein DE-Katalogwert', () => {
		assert.ok(existsSync(EIGENNAMEN), 'docs/context/einstellungen_neu/daten/eigennamen.json fehlt');
		const daten = JSON.parse(readFileSync(EIGENNAMEN, 'utf8')) as { eigennamen?: Array<{ text?: string; quelle?: string }> };
		assert.ok(Array.isArray(daten.eigennamen) && daten.eigennamen.length > 0, 'Feld „eigennamen“ fehlt oder leer');
		const html = readFileSync(MOCKUP, 'utf8');
		const deWerte = new Set(Object.values(katalog.de).map(norm));
		for (const e of daten.eigennamen) {
			const t = String(e.text ?? '');
			assert.ok(t !== '' && norm(t) === t, `Eintrag nicht normalisiert: ${JSON.stringify(e)}`);
			assert.ok(String(e.quelle ?? '').trim() !== '', `Quelle fehlt: ${t}`);
			assert.ok(html.includes(t) || html.includes(t.replace(/'/g, "\\'")), `steht nicht im Mockup: ${t}`);
			assert.ok(!deWerte.has(t), `ist ein DE-Katalogwert (kein Eigenname): ${t}`);
		}
		assert.ok(daten.eigennamen.some((e) => e.text === 'Münster'));
	});
});

describe('#2968 AC-6 Abgleich: sprachneutral im EN-Lauf', () => {
	const el = (text_de: string, muster: string | null, text_en: string): ListenElement =>
		({
			id: 'x', ctx: 'trip', reiter: 'wetter', zustand: 'normal', segment: null, abschnitt: 'metriken', ordnung: 1,
			rolle: 'text', text_de, muster, i18n_key: null, text_en, luecke: false, sprachneutral: true
		}) as ListenElement;
	test('„60%“: andere Zahl passt, fremder Text nicht', () => {
		const re = logik.erwartung(el('60%', '{zahl}%', '{zahl}%'), 'en');
		assert.ok(re, 'sprachneutral ist prüfbar, nicht nicht_pruefbar');
		assert.match('75%', re!);
		assert.doesNotMatch('sixty%', re!);
		assert.doesNotMatch('Regen 60%', re!);
	});
	test('„+49 171 123“: andere Ziffern passen, Buchstaben statt Zahl nicht', () => {
		const re = logik.erwartung(el('+49 171 123', '+{zahl} {zahl} {zahl}', '+{zahl} {zahl} {zahl}'), 'en');
		assert.ok(re);
		assert.match('+49 151 987', re!);
		assert.doesNotMatch('+49 abc 987', re!);
	});
	test('„Münster“: wörtlich, kein anderer Ort', () => {
		const re = logik.erwartung(el('Münster', null, 'Münster'), 'en');
		assert.ok(re);
		assert.match('Münster', re!);
		assert.doesNotMatch('Munich', re!);
	});
});

describe('#2968 AC-8/AC-9 Messgröße und Besitzer über die eingecheckte Elementliste', () => {
	// Ausgangswert 1022 Lücken (Neu-Erzeugung 2026-11-19). Gemessen nach Regeln a–f (Spec-Revision AC-8):
	// 352 Restlücken, alle Mockup≠App, ungebaut oder Kontodaten. Nur Senkung erlaubt.
	const OBERGRENZE = 352;
	const liste = JSON.parse(readFileSync(LISTE, 'utf8')) as { elemente: Array<ListenElement & { sprachneutral?: boolean }> };
	const luecken = liste.elemente.filter((e) => e.luecke);

	test(`Lücken ≤ ${OBERGRENZE} (gemessen, nur Senkung)`, () => {
		assert.ok(luecken.length <= OBERGRENZE, `${luecken.length} Lücken > ${OBERGRENZE}`);
	});
	test('sprachneutrale Einträge: vorhanden, keine Lücke, text_en = DE-Muster', () => {
		const neutral = liste.elemente.filter((e) => e.sprachneutral === true);
		assert.ok(neutral.length > 0, 'kein Eintrag mit sprachneutral: true');
		for (const e of neutral) {
			assert.equal(e.luecke, false, e.id);
			assert.equal(e.i18n_key, null, e.id);
			// #3154: Beispieltexte (Rolle beispiel) sind das Muster {wert}, nicht die Zahlenform des Mockups.
			assert.equal(e.text_en, e.rolle === 'beispiel' ? '{wert}' : e.text_de.replace(/\d+([.,]\d+)?/g, '{zahl}'), e.id);
		}
	});
	test('jede Lücke hat einen Besitzer (Element-ID oder Abschnitt) mit Verweis ≠ #2968', () => {
		const besitzer = logik.leseBesitzer(readFileSync(BESITZER, 'utf8'), liste.elemente);
		const ohne: string[] = [];
		const mit2968: string[] = [];
		for (const e of luecken) {
			const b =
				besitzer.find((x) => x.art === 'element' && x.id === e.id) ??
				besitzer.find((x) => x.art === 'abschnitt' && x.ctx === e.ctx && x.reiter === e.reiter && x.abschnitt === e.abschnitt);
			if (!b) ohne.push(e.id);
			else if (b.verweis.includes('2968')) mit2968.push(e.id);
		}
		assert.deepEqual(ohne, [], `${ohne.length} Lücken ohne Besitzer`);
		assert.deepEqual(mit2968, [], `${mit2968.length} Lücken mit Besitzer #2968`);
	});
	test('kein Besitzer-Eintrag verweist auf #2968', () => {
		const roh = JSON.parse(readFileSync(BESITZER, 'utf8')) as { besitzer: Array<{ verweis: string }> };
		const treffer = roh.besitzer.filter((b) => String(b.verweis).includes('2968'));
		assert.equal(treffer.length, 0, `${treffer.length} Besitzer-Einträge mit #2968`);
	});
});

// TDD RED (Spec-Revision 2026-11-19, Regeln e/f): AC-11, AC-12, AC-8 (Klassen der Restlücken).
// Vertrag Regel f: EnErgebnis/ListenElement bekommen `text_en_alternativen?: string[]` (alle EN-Kandidaten
// der Schlüssel mit demselben DE-Text, nur bei Mehrdeutigkeit); `erwartung(e,'en')` akzeptiert jeden davon.
describe('#2968 AC-11 Regel e: Katalogwert + Zeichen', () => {
	test('„gelb >“ ⇒ aufgelöst, EN = EN des Katalogwerts mit demselben Zeichen', () => {
		assert.equal(katalog.de['wetter.farbe.yellow'], 'gelb', 'Vorbedingung: „gelb“ ist Katalogwert');
		const r = mitBekannten('gelb >');
		assert.equal(r.luecke, false, JSON.stringify(r));
		assert.equal(r.text_en, katalog.en['wetter.farbe.yellow'] + ' >');
		assert.notEqual(r.sprachneutral, true);
	});
	test('„rot <“ ⇒ „red <“', () => {
		const r = mitBekannten('rot <');
		assert.equal(r.luecke, false, JSON.stringify(r));
		assert.equal(r.text_en, katalog.en['wetter.farbe.red'] + ' <');
	});
	test('Gegenbeispiel: unbekanntes Wort + Zeichen („Hagelschauer >“) ⇒ Lücke', () => {
		const r = mitBekannten('Hagelschauer >');
		assert.equal(r.luecke, true, JSON.stringify(r));
		assert.equal(r.text_en, null);
	});
	// Fix-Loop 1 (F001): das „Zeichen“ ist nie ein Wort — sonst entstünde EN wie „Done Münster“.
	for (const text of ['Fertig Telgte', 'gelb Wind', 'Fertig Münster']) {
		test(`Gegenbeispiel: Katalogwert + Wort („${text}“) ⇒ Lücke`, () => {
			const r = mitBekannten(text);
			assert.equal(r.luecke, true, JSON.stringify(r));
			assert.equal(r.text_en, null);
		});
	}
	test('Gegenbeispiel: zwei Wörter vor dem Zeichen („gelb sehr >“) ⇒ Lücke', () => {
		const r = mitBekannten('gelb sehr >');
		assert.equal(r.luecke, true, JSON.stringify(r));
		assert.equal(r.text_en, null);
	});
});

describe('#2968 F003 Reihenfolge: Katalogtreffer vor sprachneutral', () => {
	test('„Wind“ ist Katalogwert UND Token ⇒ Katalogtreffer, nicht sprachneutral', () => {
		assert.ok(bekannte().token.includes('Wind'), 'Vorbedingung: Wind ist Token');
		assert.ok(keyVonWert('Wind').length > 0, 'Vorbedingung: Wind ist Katalogwert');
		const r = mitBekannten('Wind');
		assert.ok(r.i18n_key && keyVonWert('Wind').includes(r.i18n_key), JSON.stringify(r));
		assert.notEqual(r.sprachneutral, true);
		assert.equal(r.text_en, katalog.en[r.i18n_key!]);
	});
});

describe('#2968 F002/AC-13 Erzeugungsweg baueElemente (ohne Browser)', () => {
	type Bau = (g: unknown[], k: Katalog) => Array<ListenElement & { sprachneutral?: boolean }>;
	const bau = (gen as Record<string, unknown>).baueElemente as Bau | undefined;
	const gruppe = (ctx: string, reiter: string, roh: Array<{ abschnitt: string; rolle: string; text: string }>) => [
		{ ctx, reiter, zustand: 'normal', segment: null, roh }
	];
	const eins = (ctx: string, reiter: string, abschnitt: string, rolle: string, text: string) => {
		assert.equal(typeof bau, 'function', 'baueElemente ist nicht exportiert');
		const el = bau!(gruppe(ctx, reiter, [{ abschnitt, rolle, text }]), katalog);
		assert.equal(el.length, 1);
		return el[0];
	};
	test('Reiter etappen, Abschnitt liste: Etappentitel ⇒ trip.hub.etappe_titel', () => {
		const e = eins('trip', 'etappen', 'liste', 'text', "E1 · Port d'Andratx → Estellencs");
		assert.equal(e.i18n_key, 'trip.hub.etappe_titel');
		assert.equal(e.text_en, katalog.en['trip.hub.etappe_titel']);
	});
	test('derselbe Text in anderem Abschnitt ⇒ kein Listenzeilen-Schlüssel', () => {
		const e = eins('trip', 'etappen', 'kopf', 'text', "E1 · Port d'Andratx → Estellencs");
		assert.notEqual(e.i18n_key, 'trip.hub.etappe_titel');
	});
	test('Reiter orte, Abschnitt liste: „Stadt · 60 m“ ⇒ vergleich.hub.ort_gruppe_hoehe; anderswo Lücke', () => {
		assert.equal(eins('orte', 'orte', 'liste', 'text', 'Stadt · 60 m').i18n_key, 'vergleich.hub.ort_gruppe_hoehe');
		const anders = eins('orte', 'orte', 'kopf', 'text', 'Stadt · 60 m');
		assert.equal(anders.luecke, true, JSON.stringify(anders));
	});
	test('Reiter orte, Abschnitt liste: Ortsname ⇒ vergleich.hub.ort_name; im Reiter etappen nicht', () => {
		assert.equal(eins('orte', 'orte', 'liste', 'text', 'Münster').i18n_key, 'vergleich.hub.ort_name');
		assert.notEqual(eins('trip', 'etappen', 'liste', 'text', 'Münster').i18n_key, 'vergleich.hub.ort_name');
	});
	// Fix-Loop 2 (F005): Felder und Zusammenbau des Listeneintrags.
	test('sprachneutraler Text „60%“ ⇒ Eintrag sprachneutral: true, Muster {zahl}%', () => {
		const e = eins('trip', 'wetter', 'metriken', 'text', '60%');
		assert.equal(e.sprachneutral, true, JSON.stringify(e));
		assert.equal(e.text_en, '{zahl}%');
		assert.equal(e.muster, '{zahl}%');
	});
	test('„Fertig“ ⇒ Eintrag text_en_alternativen mit Done und Finished', () => {
		const e = eins('trip', 'wetter', 'grenzen-wind', 'knopf', 'Fertig') as ListenElement & { text_en_alternativen?: string[] };
		assert.ok(e.text_en_alternativen?.includes('Done') && e.text_en_alternativen.includes('Finished'), JSON.stringify(e));
	});
	test('normaler Katalogtreffer ⇒ weder sprachneutral noch text_en_alternativen', () => {
		const e = eins('trip', 'wetter', 'kopf', 'text', 'Zustellung');
		assert.equal(e.i18n_key !== null, true);
		assert.ok(!('sprachneutral' in e), JSON.stringify(e));
		assert.ok(!('text_en_alternativen' in e), JSON.stringify(e));
		assert.equal(e.muster, null);
	});
	test('Lücke mit Zahl ⇒ Muster mit {zahl} (ohne Katalogtreffer)', () => {
		const e = eins('trip', 'wetter', 'metriken', 'text', 'Hagelschauer 3');
		assert.equal(e.luecke, true);
		assert.equal(e.muster, 'Hagelschauer {zahl}');
	});
	test('ordnung fortlaufend in DOM-Reihenfolge; Zahlvarianten werden EIN Element', () => {
		assert.equal(typeof bau, 'function');
		const el = bau!(
			gruppe('trip', 'wetter', [
				{ abschnitt: 'metriken', rolle: 'text', text: 'Zustellung' },
				{ abschnitt: 'metriken', rolle: 'text', text: 'Hagelschauer 3' },
				{ abschnitt: 'metriken', rolle: 'text', text: 'Hagelschauer 5' },
				{ abschnitt: 'metriken', rolle: 'text', text: 'Gewitter' }
			]),
			katalog
		);
		assert.deepEqual(el.map((x) => [x.text_de, x.ordnung]), [['Zustellung', 1], ['Hagelschauer 3', 2], ['Gewitter', 3]]);
		assert.equal(el[1].muster, 'Hagelschauer {zahl}');
	});
	test('Listenzeile greift nur ohne allgemeinen Schlüssel: „entfernen“ bleibt vergleich.hub.ort_entfernen', () => {
		const e = eins('orte', 'orte', 'liste', 'knopf', 'entfernen');
		assert.ok(e.i18n_key && e.i18n_key !== 'vergleich.hub.ort_name', JSON.stringify(e));
		assert.equal(katalog.de[e.i18n_key!], 'entfernen');
	});
	test('Chip-Rolle ⇒ CHIP_SCHLUESSEL; dieselbe Zeile als Text nicht', () => {
		assert.equal(eins('trip', 'wetter', 'metriken', 'chip', '+ Böen').i18n_key, gen.CHIP_SCHLUESSEL);
		assert.notEqual(eins('trip', 'wetter', 'metriken', 'text', '+ Böen').i18n_key, gen.CHIP_SCHLUESSEL);
	});
});

describe('#2968 AC-12 Regel f: mehrdeutiges EN als Alternativen', () => {
	type MitAlt = Ergebnis & { text_en_alternativen?: string[] };
	test('Generator: „Fertig“ trägt beide EN-Kandidaten (Done, Finished)', () => {
		assert.equal(katalog.de['wetter.grenzen.fertig'], 'Fertig', 'Vorbedingung');
		assert.equal(katalog.de['trip.status.finished'], 'Fertig', 'Vorbedingung');
		const r = mitBekannten('Fertig') as MitAlt;
		assert.equal(r.luecke, false, JSON.stringify(r));
		const alle = [...new Set([r.text_en, ...(r.text_en_alternativen ?? [])])].sort();
		assert.ok(alle.includes('Done') && alle.includes('Finished'), `EN-Kandidaten: ${JSON.stringify(alle)}`);
	});
	test('eindeutiger DE-Text trägt keine Alternativen', () => {
		const r = mitBekannten('Zustellung') as MitAlt;
		assert.ok(!r.text_en_alternativen || r.text_en_alternativen.length <= 1, JSON.stringify(r));
	});
	test('Abgleich: Erwartung passt auf „Done“ und „Finished“, nicht auf „Ready“', () => {
		const e = {
			id: 'x', ctx: 'trip', reiter: 'wetter', zustand: 'normal', segment: null, abschnitt: 'grenzen-wind', ordnung: 1,
			rolle: 'knopf', text_de: 'Fertig', muster: null, i18n_key: 'trip.status.finished', text_en: 'Finished', luecke: false,
			text_en_alternativen: ['Done', 'Finished']
		} as unknown as ListenElement;
		const re = logik.erwartung(e, 'en');
		assert.ok(re);
		assert.match('Finished', re!);
		assert.match('Done', re!);
		assert.doesNotMatch('Ready', re!);
		assert.doesNotMatch('Done Finished', re!);
	});
	test('eingecheckte Liste: „Fertig“ im Grenzen-Dialog erwartet auch „Done“', () => {
		const liste = JSON.parse(readFileSync(LISTE, 'utf8')) as { elemente: ListenElement[] };
		const fertig = liste.elemente.filter((x) => x.text_de === 'Fertig' && x.abschnitt.startsWith('grenzen-'));
		assert.ok(fertig.length > 0, 'Vorbedingung: Fertig-Knöpfe im Grenzen-Dialog');
		for (const x of fertig) {
			const re = logik.erwartung(x, 'en');
			assert.ok(re && re.test('Done'), `${x.id}: „Done“ nicht erwartet`);
		}
	});
});

describe('#2968 AC-8 Restlücken nur in den Klassen Mockup≠App / ungebaut / Kontodaten', () => {
	test('keine Restlücke der Klasse „Zusammensetzung im Code“ oder anderer Klassen', () => {
		const liste = JSON.parse(readFileSync(LISTE, 'utf8')) as { elemente: unknown[] };
		const jeGrund = (gen as Record<string, unknown>).lueckenJeGrund as (e: unknown[], b: string) => Array<{ klasse: string; verweis: string; anzahl: number }>;
		const erlaubt = new Set(['Mockup≠App-Abweichung', 'ungebautes Pendant', 'Kontodaten/Eigennamen ohne Listeneintrag']);
		const fremd = jeGrund(liste.elemente, readFileSync(BESITZER, 'utf8')).filter((z) => !erlaubt.has(z.klasse));
		assert.deepEqual(fremd, [], `Restlücken außerhalb der erlaubten Klassen: ${JSON.stringify(fremd)}`);
	});
});

describe('#2968 AC-10 Lücken je Grund und Doku', () => {
	const liste = JSON.parse(readFileSync(LISTE, 'utf8')) as { elemente: Array<ListenElement & { sprachneutral?: boolean }> };
	type JeGrund = (e: unknown[], b: string) => Array<{ klasse: string; verweis: string; anzahl: number }>;
	const jeGrund = (gen as Record<string, unknown>).lueckenJeGrund as JeGrund | undefined;

	test('Zusammenfassung zählt jede Lücke genau einmal, je Klasse und Besitzer, keine ohne Besitzer', () => {
		assert.equal(typeof jeGrund, 'function', 'lueckenJeGrund fehlt in scripts/elementliste_aus_mockup.ts');
		const zeilen = jeGrund!(liste.elemente, readFileSync(BESITZER, 'utf8'));
		const summe = zeilen.reduce((s, z) => s + z.anzahl, 0);
		assert.equal(summe, liste.elemente.filter((e) => e.luecke).length);
		assert.deepEqual(zeilen.filter((z) => z.klasse === 'ohne Besitzer'), []);
		assert.ok(zeilen.some((z) => z.klasse === 'Mockup≠App-Abweichung'), JSON.stringify(zeilen));
		for (const z of zeilen) assert.doesNotMatch(z.verweis, /2968/);
	});
	test('Gegenprobe: ohne Besitzer-Einträge landet jede Lücke in „ohne Besitzer“', () => {
		const zeilen = jeGrund!(liste.elemente, JSON.stringify({ besitzer: [] }));
		assert.deepEqual(zeilen.map((z) => z.klasse), ['ohne Besitzer']);
	});
	// doc-compliance-test
	test('gates_und_ratschen.md beschreibt die Zuordner-Regeln a bis d im Abschnitt Elementliste', () => {
		const doku = readFileSync(join(REPO, 'docs/reference/gates_und_ratschen.md'), 'utf8');
		const start = doku.indexOf('**EN-Zuordner des Generators (#2968');
		assert.ok(start > 0, 'Absatz „EN-Zuordner des Generators (#2968 …)“ fehlt');
		const absatz = doku.slice(start, doku.indexOf('\n## ', start));
		for (const s of ['**Regel a**', '**Regel b**', '**Regel c**', '**Regel d**', '**Regel e**', '**Regel f**', 'text_en_alternativen', 'listenzeileEn', 'sprachneutral', 'metriknamen.json', 'eigennamen.json', 'nichts erfinden']) {
			assert.ok(absatz.includes(s), `Doku-Absatz nennt „${s}“ nicht`);
		}
	});
});
