// Issue #2981 (Epic #2913, ADR-0104) — eingebaute Wetter-Vorlagennamen zweisprachig.
// Die Vorlage-Karte (Reiter Wetter) und die alte Vorlagen-Leiste zeigten das feste
// deutsche Server-Label („Wandern“) auch bei Sprache Englisch. Der Name wird jetzt
// ueber eine ID-zu-Katalogschluessel-Map aufgeloest (Vorbild PROFILE_LABELS);
// unbekannte IDs und eigene Vorlagen behalten das Server- bzw. Nutzer-Label.
// Spec: docs/specs/modules/fix_2981_vorlage_name_en.md
//
// Kein Mock: echter Katalog (trFor), echte Map, echte Aufloesungsfunktion.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/vorlageName.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { de } from '../../../../i18n/messages/de/index.ts';
import { en } from '../../../../i18n/messages/en/index.ts';
import { vorlageNameKey, vorlageAnzeigename } from '../vorlageName.ts';

// Systemvorlagen laut Server (src/app/metric_catalog.py WEATHER_TEMPLATES):
// id → [heutiges deutsches Server-Label, englischer Name laut Spec AC-1]
const SYSTEMVORLAGEN: Record<string, [string, string]> = {
	'alpen-trekking': ['Alpen-Trekking', 'Alpine trekking'],
	wandern: ['Wandern', 'Hiking'],
	skitouren: ['Skitouren', 'Ski touring'],
	wintersport: ['Wintersport', 'Winter sports'],
	radtour: ['Radtour', 'Cycling'],
	wassersport: ['Wassersport', 'Water sports'],
	allgemein: ['Allgemein', 'General'],
};

describe('Test 1 / AC-1, AC-2, AC-7: Sprache EN zeigt englische Namen', () => {
	for (const [id, [labelDe, nameEn]] of Object.entries(SYSTEMVORLAGEN)) {
		test(`${id} → „${nameEn}“`, () => {
			assert.equal(vorlageAnzeigename('en', id, labelDe), nameEn);
		});
	}
	test('Kernfall aus dem Bug: wandern ist bei EN „Hiking“, nicht „Wandern“', () => {
		assert.notEqual(vorlageAnzeigename('en', 'wandern', 'Wandern'), 'Wandern');
		assert.equal(vorlageAnzeigename('en', 'wandern', 'Wandern'), 'Hiking');
	});
});

describe('Test 2 / AC-3: Sprache DE bleibt unveraendert', () => {
	for (const [id, [labelDe]] of Object.entries(SYSTEMVORLAGEN)) {
		test(`${id} → „${labelDe}“`, () => {
			assert.equal(vorlageAnzeigename('de', id, labelDe), labelDe);
		});
	}
	test('undefined-Sprache faellt wie trFor auf Deutsch', () => {
		assert.equal(vorlageAnzeigename(undefined, 'wandern', 'Wandern'), 'Wandern');
	});
});

describe('Test 3 / AC-5: unbekannte ID faellt auf das Server-Label zurueck', () => {
	test('vorlageNameKey liefert fuer unbekannte ID null', () => {
		assert.equal(vorlageNameKey('gletscher-neu'), null);
		assert.equal(vorlageNameKey(''), null);
	});
	test('Anzeige zeigt das Server-Label in DE und EN, nie leer, nie Schluessel', () => {
		for (const lang of ['de', 'en'] as const) {
			const name = vorlageAnzeigename(lang, 'gletscher-neu', 'Gletschertour');
			assert.equal(name, 'Gletschertour');
			assert.ok(!name.startsWith('wetter.'));
		}
	});
	test('fehlt auch das Server-Label, steht wie bisher die ID (nie leer)', () => {
		assert.equal(vorlageAnzeigename('en', 'gletscher-neu', undefined), 'gletscher-neu');
		assert.equal(vorlageAnzeigename('en', 'gletscher-neu', ''), 'gletscher-neu');
	});
	test('Map-Schutz gegen Prototyp-Schluessel: constructor/toString sind unbekannt', () => {
		assert.equal(vorlageNameKey('constructor'), null);
		assert.equal(vorlageNameKey('toString'), null);
	});
});

describe('Test 4: Katalog-Paritaet DE/EN fuer jeden Map-Schluessel', () => {
	for (const id of Object.keys(SYSTEMVORLAGEN)) {
		test(`${id}: Schluessel wetter.vorlage.name.${id} in beiden Sprachen, nicht leer`, () => {
			const key = vorlageNameKey(id);
			assert.equal(key, `wetter.vorlage.name.${id}`);
			const deWert = (de as Record<string, string>)[key!];
			const enWert = (en as Record<string, string>)[key!];
			assert.ok(deWert && deWert.trim().length > 0, `DE fehlt/leer: ${key}`);
			assert.ok(enWert && enWert.trim().length > 0, `EN fehlt/leer: ${key}`);
			assert.notEqual(enWert, deWert, `EN-Wert ist noch deutsch: ${key}`);
		});
	}
});

describe('Test 5 / AC-4: eigene Vorlage behaelt den Nutzernamen', () => {
	test('eigene Vorlage „Mein Wochenende“ ist in DE und EN identisch', () => {
		for (const lang of ['de', 'en'] as const) {
			assert.equal(vorlageAnzeigename(lang, 'eigen-7f3a', 'Mein Wochenende'), 'Mein Wochenende');
		}
	});
});
