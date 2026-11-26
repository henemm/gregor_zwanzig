// Paket #3419 Adversary-Runde 1 (F001–F003): Gegenrichtungs-Zusatz an der Produktfunktion geprüft.
// Spec: docs/specs/modules/feat_3419_elementliste_nachzug.md (AC-3, AC-4).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks --test e2e/feat3419_gegenrichtung_zusatz.test.ts
//
// Kern-Schicht, ohne Netz, gegen die exportierten Funktionen und die versionierten Dateien. Kein Mock.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as L from './elementliste_abgleich_logik.ts';
import type { Ergebnis, ListenElement } from './elementliste_abgleich_logik.ts';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, '..', '..');
const lies = (...teile: string[]): unknown => JSON.parse(readFileSync(join(REPO, ...teile), 'utf8'));
const echtePaare = () =>
	L.namenPaareAus(
		lies('docs', 'context', 'einstellungen_neu', 'daten', 'metrik_namen.json'),
		lies('src', 'i18n', 'messages', 'de', 'vergleich.json'),
		lies('src', 'i18n', 'messages', 'en', 'vergleich.json')
	);

let nr = 0;
function el(text_de: string, extra: Partial<ListenElement> = {}): ListenElement {
	nr += 1;
	return {
		id: `z3419-${nr}`, ctx: 'orte', reiter: 'wetter', zustand: 'normal', segment: null, abschnitt: 'was-steht-wo',
		ordnung: nr, rolle: 'text', text_de, muster: null, i18n_key: null, text_en: text_de, luecke: false, ...extra
	};
}
const beispiel = (text: string, extra: Partial<ListenElement> = {}) => el(text, { rolle: 'beispiel', muster: '{wert}', text_en: '{wert}', sprachneutral: true, ...extra });
const zusaetzlich = (liste: ListenElement[], texte: string[], namenDeEn: L.NamensPaar[]) =>
	L.findeZusaetzliche({ ctx: 'orte', reiter: 'wetter', texte }, liste, [], [], 'en', [], { namenDeEn }).map((z) => z.text).sort();

describe('#3422 F001: namenPaareAus liest Schnappschuss UND Server-Katalog vergleich.zeile.*', () => {
	test('echte Dateien: Böen→Gusts und Regen→Rain (nur im Katalog), Böen→Wind gusts (Schnappschuss)', () => {
		const p = echtePaare();
		const hat = (de: string, en: string) => p.some((x) => x.de === de && x.en === en);
		assert.ok(hat('Böen', 'Gusts'), 'vergleich.zeile.gust_max fehlt');
		assert.ok(hat('Regen', 'Rain'), 'vergleich.zeile.precip_sum fehlt');
		assert.ok(hat('Sonne', 'Sun'), 'vergleich.zeile.sunny_hours fehlt');
		assert.ok(hat('Böen', 'Wind gusts'), 'Schnappschuss metrik_namen.json fehlt');
	});

	test('nur Schlüssel vergleich.zeile.* mit beiden Sprachen; ungültige Quellen tragen nichts bei', () => {
		const p = L.namenPaareAus(
			{ namen: [{ de: 'A', en: 'B' }, { de: '', en: 'X' }, 'kaputt'] },
			{ 'vergleich.zeile.x': 'Wolke', 'vergleich.anders': 'Nein', 'vergleich.zeile.ohne_en': 'Fehlt' },
			{ 'vergleich.zeile.x': 'Cloud', 'vergleich.anders': 'No' }
		);
		assert.deepEqual(p, [{ de: 'A', en: 'B' }, { de: 'Wolke', en: 'Cloud' }]);
		assert.deepEqual(L.namenPaareAus(null, 'x', []), []);
	});
});

describe('#3422 F002: EN-Form ersetzt den DE-Namen nur als ganzes Wort', () => {
	test('„Regen“ in „Regenwahrscheinlichkeit 60%“ wird nicht zu „Rain…“', () => {
		nr = 0;
		const liste = [beispiel('Regenwahrscheinlichkeit 60%')];
		// Teilwort-Ersetzung ergäbe „Rainwahrscheinlichkeit {zahl}%“ und erklärte diesen Text fälschlich.
		assert.deepEqual(zusaetzlich(liste, ['Rainwahrscheinlichkeit 70%'], [{ de: 'Regen', en: 'Rain' }]), ['Rainwahrscheinlichkeit 70%']);
	});

	test('Gegenprobe: als ganzes Wort wird ersetzt („Regen 1.8 mm“ → „Rain 3.4 mm“ erklärt)', () => {
		nr = 0;
		assert.deepEqual(zusaetzlich([beispiel('Regen 1.8 mm')], ['Rain 3.4 mm'], [{ de: 'Regen', en: 'Rain' }]), []);
	});

	test('echte Namenspaare: „Regenwahrscheinlichkeit 60%“ erklärt „Rain probability 70%“, nicht „Rainwahrscheinlichkeit 70%“', () => {
		nr = 0;
		const liste = [beispiel('Regenwahrscheinlichkeit 60%')];
		assert.deepEqual(zusaetzlich(liste, ['Rain probability 70%', 'Rainwahrscheinlichkeit 70%'], echtePaare()), ['Rainwahrscheinlichkeit 70%']);
	});
});

describe('#3419 Nr. 6 F003: angenommeneWerte nimmt nur gefundene {wert}-Elemente', () => {
	const liste = () => {
		nr = 0;
		return [beispiel('R1.8@15'), beispiel('W30@10', { ctx: 'trip' }), el('Wind in SMS', { rolle: 'eingabe', muster: '{metrik} in SMS', text_en: '{metrik} in SMS' })];
	};

	test('gefunden mit ist ⇒ Eintrag mit ctx/Reiter des Elements', () => {
		const l = liste();
		const erg = new Map<string, Ergebnis>([[l[0].id, { status: 'gefunden', ist: 'R 0.0-1.3@16' }]]);
		assert.deepEqual(L.angenommeneWerte(l, erg, 'de'), [{ ctx: 'orte', reiter: 'wetter', text: 'R 0.0-1.3@16' }]);
	});

	test('abweichendes {wert}-Element mit ist-Text liefert nichts', () => {
		const l = liste();
		const erg = new Map<string, Ergebnis>([
			[l[0].id, { status: 'abweichend', grund: 'Abschnitt-Haken data-abschnitt="was-steht-wo" fehlt', ist: 'R 0.0-1.3@16' }],
			[l[1].id, { status: 'nicht_pruefbar', grund: 'x', ist: 'W 17-50@19' }]
		]);
		assert.deepEqual(L.angenommeneWerte(l, erg, 'de'), []);
	});

	test('gefundenes Element ohne {wert} (Zellname) liefert nichts, auch mit ist', () => {
		const l = liste();
		const erg = new Map<string, Ergebnis>([[l[2].id, { status: 'gefunden', ist: 'Wind in SMS' }]]);
		assert.deepEqual(L.angenommeneWerte(l, erg, 'de'), []);
	});
});
