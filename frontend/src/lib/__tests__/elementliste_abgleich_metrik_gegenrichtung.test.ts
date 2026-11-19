// TDD RED — Issue #3011 (Epic #2913), Workflow feat-3008-abgleich-waechter.
// Spec: docs/specs/modules/feat_3008_abgleich_waechter.md — AC-5, AC-6, AC-7.
//
// Heute macht die Gegenrichtung `{metrik}` zu `.+?`: das Muster „+ {metrik}“ erklärt jeden Live-Text, der
// mit „+ “ beginnt, „{metrik} aus dem Briefing nehmen“ jeden Text mit dieser Endung. Fremdtexte fallen nie
// als `zusaetzlich` auf. Soll: `{metrik}` passt in der Gegenrichtung nur auf genau einen bekannten
// Metriknamen (Register ∪ DE-Namen der Elementliste); leere Menge ⇒ nur Listen-Namen (fail-closed).
//
// Ohne Netz, ohne Mock: echte elementliste.json, Register-Ausschnitt im Antwortformat von GET /api/metrics
// (Kategorie → [{id, label, label_de, label_en, …}]); EN-Namen aus der vorhandenen Register-Fixture
// f5_register_namen.json, DE-Namen wie in src/app/metric_catalog.py.
//
// Vertrag (vom Developer in e2e/elementliste_abgleich_logik.ts umzusetzen):
//   metrikNamenAusRegister(antwort: unknown): string[]  — alle nicht-leeren label/label_de/label_en; ungültig ⇒ []
//   metrikNamenAusListe(liste): string[]                — DE-Werte von {metrik} aus text_de (muster enthält {metrik})
//   findeZusaetzliche(befund, liste, ausnahmen, kontoTexte, sprache, metrikNamen: string[] = [])
//   werteGegenrichtungAus(befund, liste, ausnahmen, kontoTexte, sprache, metrikNamen: string[] = [])
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/__tests__/elementliste_abgleich_metrik_gegenrichtung.test.ts
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as logik from '../../../e2e/elementliste_abgleich_logik.ts';
import type { ListenElement } from '../../../e2e/elementliste_abgleich_logik.ts';

// Namespace-Import: fehlende Exporte machen jeden Test einzeln rot statt das ganze Modul zu sprengen.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const L = logik as any;

const HIER = fileURLToPath(new URL('.', import.meta.url));
const FRONTEND = join(HIER, '..', '..', '..');
const KONTEXT = join(FRONTEND, '..', 'docs/context/einstellungen_neu');
const LISTE: ListenElement[] = (JSON.parse(readFileSync(join(KONTEXT, 'elementliste.json'), 'utf8')) as { elemente: ListenElement[] }).elemente;
const F5 = JSON.parse(
	readFileSync(join(HIER, '..', 'components/shared/weather-metrics-tab/__tests__/fixtures/f5_register_namen.json'), 'utf8')
) as Record<string, { label_en: string }>;

const eintrag = (id: string, label_de: string, category: string) => ({
	id,
	label: label_de,
	label_de,
	label_en: F5[id].label_en,
	category,
	unit: '',
	aggregations: [{ id: 'max', label: 'Maximum', label_en: 'Maximum', alert_metric: null }]
});

/** Ausschnitt einer echten /api/metrics-Antwort: Kategorie → Metriken. */
const REGISTER = {
	temperature: [eintrag('temperature', 'Temperatur', 'temperature')],
	wind: [eintrag('wind_direction', 'Windrichtung', 'wind')]
};

const ANKER = { kopf: 1, flaeche: 1 };

type Sprache = 'de' | 'en';
/** Texte, die die Gegenrichtung für ctx/Reiter als `zusaetzlich` meldet. */
function zusaetzlich(texte: string[], sprache: Sprache, metrikNamen?: string[], ctx = 'trip'): string[] {
	const befund = { ctx, reiter: 'wetter', texte };
	const erg = metrikNamen === undefined ? L.findeZusaetzliche(befund, LISTE, [], [], sprache) : L.findeZusaetzliche(befund, LISTE, [], [], sprache, metrikNamen);
	return erg.map((z: { text: string }) => z.text).sort();
}

/** Volle Kette wie im Staging-Lauf: Register-Antwort ∪ Listen-Namen (rot, solange die Exporte fehlen). */
const namen = (): string[] => [...L.metrikNamenAusRegister(REGISTER), ...L.metrikNamenAusListe(LISTE)];
/**
 * Dieselben Registernamen als feste Menge: AC-5/AC-6 prüfen damit allein das Verhalten der Gegenrichtung
 * (rot wegen `{metrik}` = `.+?`, nicht wegen eines fehlenden Exports). Listen-Namen ergänzt die Logik selbst.
 */
const BEKANNT = ['Temperatur', 'Temperature', 'Windrichtung', 'Wind direction'];

describe('#3011 Metriknamen-Quellen', () => {
	test('metrikNamenAusRegister: label/label_de/label_en aller Kategorien', () => {
		const n = new Set(L.metrikNamenAusRegister(REGISTER));
		for (const name of ['Temperatur', 'Temperature', 'Windrichtung', 'Wind direction']) assert.ok(n.has(name), `„${name}“ fehlt`);
		for (const x of n) assert.ok(typeof x === 'string' && x.trim() !== '', `leerer Name „${String(x)}“`);
	});

	test('metrikNamenAusRegister: leere Labels zählen nicht, ungültige Antwort ⇒ []', () => {
		const n = L.metrikNamenAusRegister({ wind: [{ id: 'x', label: '', label_de: '  ', label_en: 'Gust' }] });
		assert.deepEqual([...new Set(n)], ['Gust']);
		for (const kaputt of [null, undefined, 'Fehler', 42, [], { wind: 'kein Array' }]) {
			assert.deepEqual(L.metrikNamenAusRegister(kaputt), [], `ungültige Antwort ${JSON.stringify(kaputt)} lieferte Namen`);
		}
	});

	test('metrikNamenAusListe: reine DE-Namen aus den {metrik}-Einträgen der echten Liste', () => {
		const n = new Set(L.metrikNamenAusListe(LISTE));
		for (const name of ['Windrichtung', 'Temperatur', 'Luftfeuchte', 'Tiefsttemperatur Nacht']) assert.ok(n.has(name), `„${name}“ fehlt`);
		for (const x of n as Set<string>) {
			assert.ok(!x.startsWith('+') && !x.includes('aus dem Briefing nehmen'), `kein reiner Name: „${x}“`);
		}
		assert.ok(!n.has('Quatsch'));
	});

	test('metrikNamenAusListe: Einträge ohne {metrik} liefern keinen Namen', () => {
		const basis = LISTE.find((e) => e.muster === '+ {metrik}');
		assert.ok(basis);
		const klein = [
			{ ...basis, text_de: '+ Taupunkt' },
			{ ...basis, id: 'x2', muster: '{zahl} km/h', text_de: '12 km/h' },
			{ ...basis, id: 'x3', muster: null, text_de: 'Wind' }
		];
		assert.deepEqual(L.metrikNamenAusListe(klein), ['Taupunkt']);
	});
});

describe('#3011 Gegenrichtung: {metrik} nur auf bekannte Metriknamen', () => {
	test('AC-5 (DE, trip): „+ Quatsch“ ⇒ zusaetzlich, „+ Windrichtung“ erklärt', () => {
		assert.deepEqual(zusaetzlich(['+ Quatsch', '+ Windrichtung'], 'de', BEKANNT), ['+ Quatsch']);
	});

	test('AC-5 (EN, trip): „+ Nonsense“ ⇒ zusaetzlich, „+ Wind direction“ erklärt', () => {
		assert.deepEqual(zusaetzlich(['+ Nonsense', '+ Wind direction'], 'en', BEKANNT), ['+ Nonsense']);
	});

	test('AC-5 (DE, orte): „+ Quatsch“ ⇒ zusaetzlich, „+ Windrichtung“ erklärt', () => {
		assert.deepEqual(zusaetzlich(['+ Quatsch', '+ Windrichtung'], 'de', BEKANNT, 'orte'), ['+ Quatsch']);
	});

	test('AC-5: genau EIN Name — „+ Windrichtung Quatsch“ ist kein Metrikname ⇒ zusaetzlich', () => {
		assert.deepEqual(zusaetzlich(['+ Windrichtung Quatsch', '+ Temperatur'], 'de', BEKANNT), ['+ Windrichtung Quatsch']);
		assert.deepEqual(zusaetzlich(['+ Wind direction and more'], 'en', BEKANNT), ['+ Wind direction and more']);
	});

	test('AC-5: Metrikname mit Regex-Sonderzeichen wird wörtlich genommen', () => {
		assert.deepEqual(zusaetzlich(['+ Temp (max)', '+ Temp max', '+ Temp. X'], 'de', ['Temp (max)', 'Temp. X']), ['+ Temp max']);
		assert.deepEqual(zusaetzlich(['+ TempY X'], 'de', ['Temp. X']), ['+ TempY X']);
	});

	test('AC-5: werteGegenrichtungAus reicht die Metriknamen durch', () => {
		const befund = { ctx: 'trip', reiter: 'wetter', anker: ANKER, texte: ['+ Quatsch', '+ Windrichtung'] };
		const erg = L.werteGegenrichtungAus(befund, LISTE, [], [], 'de', BEKANNT);
		assert.equal(erg.ohneHub, null);
		assert.deepEqual(erg.zusaetzlich.map((z: { text: string }) => z.text), ['+ Quatsch']);
		const en = L.werteGegenrichtungAus({ ...befund, texte: ['+ Nonsense', '+ Wind direction'] }, LISTE, [], [], 'en', BEKANNT);
		assert.deepEqual(en.zusaetzlich.map((z: { text: string }) => z.text), ['+ Nonsense']);
	});

	test('AC-5: volle Kette Register-Antwort ∪ Listen-Namen — echte Namen erklärt, Fremdtext zusaetzlich', () => {
		assert.deepEqual(zusaetzlich(['+ Quatsch', '+ Windrichtung', '+ Luftfeuchte', 'Temperatur aus dem Briefing nehmen'], 'de', namen()), ['+ Quatsch']);
		assert.deepEqual(zusaetzlich(['+ Nonsense', '+ Wind direction', 'Remove Temperature from the briefing'], 'en', namen()), ['+ Nonsense']);
	});

	test('AC-6 (DE): „Quatsch aus dem Briefing nehmen“ ⇒ zusaetzlich, „Temperatur aus dem Briefing nehmen“ erklärt', () => {
		assert.deepEqual(zusaetzlich(['Quatsch aus dem Briefing nehmen', 'Temperatur aus dem Briefing nehmen'], 'de', BEKANNT), ['Quatsch aus dem Briefing nehmen']);
	});

	test('AC-6 (EN): „Remove Nonsense from the briefing“ ⇒ zusaetzlich, „Remove Temperature from the briefing“ erklärt', () => {
		assert.deepEqual(
			zusaetzlich(['Remove Nonsense from the briefing', 'Remove Temperature from the briefing', 'Remove Wind direction from the briefing'], 'en', BEKANNT),
			['Remove Nonsense from the briefing']
		);
	});

	test('AC-7: leere Registermenge ⇒ EN-Registername und „+ Quatsch“ zusaetzlich, DE-Listenname erklärt', () => {
		assert.deepEqual(zusaetzlich(['+ Wind direction'], 'en', []), ['+ Wind direction']);
		assert.deepEqual(zusaetzlich(['+ Quatsch', '+ Windrichtung'], 'de', []), ['+ Quatsch']);
	});

	test('AC-7: ohne Parameter metrikNamen gilt dasselbe (Vorgabe leere Menge, nie still erklärt)', () => {
		assert.deepEqual(zusaetzlich(['+ Wind direction'], 'en'), ['+ Wind direction']);
		assert.deepEqual(zusaetzlich(['+ Quatsch', '+ Windrichtung', 'Quatsch aus dem Briefing nehmen'], 'de'), ['+ Quatsch', 'Quatsch aus dem Briefing nehmen']);
	});

	test('AC-7 (F001): Gesamtmenge leer (Register leer, Liste ohne Namen) ⇒ {metrik} erklärt nichts (fail-closed)', () => {
		const plus = LISTE.find((e) => e.muster === '+ {metrik}' && e.ctx === 'trip' && e.reiter === 'wetter' && e.zustand === 'normal');
		const raus = LISTE.find((e) => e.muster === '{metrik} aus dem Briefing nehmen' && e.ctx === 'trip' && e.reiter === 'wetter' && e.zustand === 'normal');
		assert.ok(plus && raus);
		// text_de ohne Metrikwert: die Liste liefert keinen Namen, die Menge bleibt leer.
		const ohneNamen: ListenElement[] = [
			{ ...plus, text_de: '' },
			{ ...raus, text_de: '' }
		];
		assert.deepEqual(L.metrikNamenAusListe(ohneNamen), [], 'Vorbedingung: Liste liefert keinen Namen');
		const de = L.findeZusaetzliche({ ctx: 'trip', reiter: 'wetter', texte: ['+ Quatsch', 'Quatsch aus dem Briefing nehmen'] }, ohneNamen, [], [], 'de', []);
		assert.deepEqual(de.map((z: { text: string }) => z.text).sort(), ['+ Quatsch', 'Quatsch aus dem Briefing nehmen']);
		const en = L.findeZusaetzliche({ ctx: 'trip', reiter: 'wetter', texte: ['+ Nonsense', 'Remove Nonsense from the briefing'] }, ohneNamen, [], [], 'en', []);
		assert.deepEqual(en.map((z: { text: string }) => z.text).sort(), ['+ Nonsense', 'Remove Nonsense from the briefing']);
	});

	test('AC-5 (F002): Metriknamen werden normalisiert (Mehrfach-, Rand-Leerraum)', () => {
		assert.deepEqual(zusaetzlich(['+ Wind direction', '+ Nonsense'], 'en', ['  Wind  direction ']), ['+ Nonsense']);
		assert.deepEqual(zusaetzlich(['Remove Wind direction from the briefing'], 'en', ['Wind direction']), []);
	});
});
