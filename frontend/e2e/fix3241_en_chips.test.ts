// Issue #3241 (Epic #2913): Metrik-Chips „+ {metrik}“ im englischen Abgleich einzeln prüfbar.
// Spec: docs/specs/modules/fix_3241_elementliste_en_metrikzeile_chips.md (AC-5 bis AC-7, Tests 5-8).
//
//   cd frontend && node --experimental-strip-types --test e2e/fix3241_en_chips.test.ts
//
// Kern-Schicht: echte Namenspaare (metrik_namen.json + Katalog vergleich.json), echte Chips aus elementliste.json.
// Neuer letzter optionaler Parameter `namenDeEn: NamensPaar[] = []` an bewerteKontoChips und bewerteAbschnitt.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as L from './elementliste_abgleich_logik.ts';
import type { ListenElement } from './elementliste_abgleich_logik.ts';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, '..', '..');
const lies = (p: string): unknown => JSON.parse(readFileSync(join(REPO, p), 'utf-8'));

const PAARE = L.namenPaareAus(
	lies('docs/context/einstellungen_neu/daten/metrik_namen.json'),
	lies('src/i18n/messages/de/vergleich.json'),
	lies('src/i18n/messages/en/vergleich.json')
);
const ALLE: ListenElement[] = (lies('docs/context/einstellungen_neu/elementliste.json') as { elemente: ListenElement[] }).elemente;

const nameDe = (e: ListenElement) => e.text_de.replace(/^\+ /, '');
const enName = (e: ListenElement) => PAARE.find((p) => p.de === nameDe(e))?.en;

// Echte Chips (Trip, Wetter, normal); nur solche mit Namenspaar, damit die Erwartung eindeutig ist.
const CHIPS = ALLE.filter(
	(e) => e.ctx === 'trip' && e.reiter === 'wetter' && e.zustand === 'normal' && e.abschnitt === 'metriken' && e.rolle === 'chip'
).sort((a, b) => a.ordnung - b.ordnung);
const MIT_PAAR = CHIPS.filter((e) => enName(e));
const [A, B] = MIT_PAAR;

// Letzter Parameter `namenDeEn` ist neu; ohne ihn (heute) ignoriert die Funktion ihn.
const bewerte = (chips: ListenElement[], texte: string[], sprache: 'de' | 'en', paare = PAARE) =>
	(L.bewerteAbschnitt as (...a: unknown[]) => ReturnType<typeof L.bewerteAbschnitt>)(chips, { marker: true, texte }, sprache, 'metriken', paare);

describe('#3241 Testdaten', () => {
	test('mindestens zwei echte Chips mit Namenspaar', () => {
		assert.ok(MIT_PAAR.length >= 2, `Chips mit Paar: ${MIT_PAAR.length} von ${CHIPS.length}`);
		assert.ok(A.ordnung < B.ordnung);
	});
});

describe('#3241 Test 5 / AC-5: sichtbarer Chip ist einzeln gefunden', () => {
	test('„+ <EN-Name>“ sichtbar, Chip ist nicht das erste Element => gefunden', () => {
		const r = bewerte(CHIPS, [`+ ${enName(B)}`], 'en');
		assert.equal(r.get(B.id)?.status, 'gefunden', JSON.stringify(r.get(B.id)));
	});
	test('über bewerteKontoChips direkt', () => {
		const r = (L.bewerteKontoChips as (...a: unknown[]) => ReturnType<typeof L.bewerteKontoChips>)(
			CHIPS, { marker: true, texte: [`+ ${enName(B)}`] }, 'en', 'metriken', PAARE
		);
		assert.equal(r.get(B.id)?.status, 'gefunden', JSON.stringify(r.get(B.id)));
	});
});

describe('#3241 Test 6 / AC-5: nicht sichtbarer Chip', () => {
	test('weiteres Element ohne sichtbaren Text => nicht_pruefbar „ist in diesem Konto kein Chip“', () => {
		const r = bewerte(CHIPS, [`+ ${enName(A)}`], 'en');
		assert.equal(r.get(A.id)?.status, 'gefunden', JSON.stringify(r.get(A.id)));
		const x = r.get(B.id);
		assert.equal(x?.status, 'nicht_pruefbar');
		assert.match(x?.grund ?? '', /ist in diesem Konto kein Chip/);
		assert.doesNotMatch(x?.grund ?? '', /in EN ist nur das Muster prüfbar/);
	});
});

describe('#3241 Test 7 / AC-6: Chip ohne Namenspaar', () => {
	test('„+ Fantasiewert“ => nicht_pruefbar „kein EN-Name für Fantasiewert“, nichts geraten', () => {
		const fremd: ListenElement = { ...B, id: 'test.fantasie', ordnung: B.ordnung + 1000, text_de: '+ Fantasiewert' };
		const r = bewerte([...CHIPS, fremd], [`+ ${enName(A)}`, '+ Fantasiewert'], 'en');
		const x = r.get(fremd.id);
		assert.equal(x?.status, 'nicht_pruefbar', JSON.stringify(x));
		assert.match(x?.grund ?? '', /kein EN-Name für Fantasiewert/);
	});
});

describe('#3241 Test 8 / AC-7: DE-Lauf unverändert (Regressionswächter)', () => {
	const fall: Array<[string, string[]]> = [
		['erstes Chip sichtbar', [`+ ${nameDe(A)}`]],
		['zweites Chip sichtbar', [`+ ${nameDe(B)}`]],
		['nichts sichtbar', ['irgendwas']],
	];
	for (const [name, texte] of fall) {
		test(`DE ${name}: mit und ohne Namenspaare identisch`, () => {
			assert.deepEqual([...bewerte(CHIPS, texte, 'de', PAARE)], [...bewerte(CHIPS, texte, 'de', [])]);
		});
	}
});
