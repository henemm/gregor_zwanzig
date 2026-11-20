// doc-compliance-test (liest die Katalogdateien als DATEN: Pflichttexte der Spec wortgetreu nach Mockup Fassung 4)
//
// TDD RED — Issue #3111 (Epic #2913): Wetter-Dialoge nach Mockup. AC-1 bis AC-8 (Katalogteil).
// Spec: docs/specs/modules/feat_3111_wetter_dialoge_mockup.md
// Soll-Wortlaut: docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html Z. 356, 458-500.
//
// RED heute: die neuen Schlüssel fehlen, die DE-Texte tragen noch ‚…‘ statt „…“, das Label heißt „Beschreibung“.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test src/lib/i18n/__tests__/feat_3111_wetter_dialoge_katalog.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HIER = dirname(fileURLToPath(import.meta.url));
const lies = (l: 'de' | 'en'): Record<string, string> => JSON.parse(readFileSync(join(HIER, '..', 'messages', l, 'wetter.json'), 'utf-8'));
const DE = lies('de');
const EN = lies('en');
const platzhalter = (t: string) => [...new Set([...t.matchAll(/\{([a-z0-9_]+)\}/g)].map((m) => m[1]))].sort();

/** Neue Schlüssel und der DE-Wortlaut laut Mockup Fassung 4. */
const NEU: Record<string, string> = {
	'wetter.grenzen.unten_1': 'unten',
	'wetter.grenzen.unten_2': 'zu wenig',
	'wetter.grenzen.oben_1': 'oben',
	'wetter.grenzen.oben_2': 'zu viel',
	'wetter.vorlage.aktiv_marker': '· aktiv',
	'wetter.vorlage.stichworte.alpen_trekking': 'Gewitter, Böen, Nullgradgrenze',
	'wetter.vorlage.stichworte.wandern': 'Regen, Sonne, UV',
	'wetter.vorlage.stichworte.skitouren': 'Neuschnee, Schneehöhe, Sicht',
	'wetter.vorlage.stichworte.wintersport': 'Schnee, Kälte',
	'wetter.vorlage.stichworte.radtour': 'Wind, Regen, gefühlte Temperatur',
	'wetter.vorlage.stichworte.wassersport': 'Wind beidseitig, Gewitter',
	'wetter.vorlage.stichworte.allgemein': 'Standard-Ampel',
	'wetter.vorlage.frage_titel': '„{neu}“ übernehmen?',
	'wetter.vorlage.ersetzt_route': 'Ersetzt Metrik-Auswahl, Ampel-Grenzen und Alarmstufen dieses Trips.',
	'wetter.dialog.name_platzhalter': 'z.B. Mallorca Frühling',
	'wetter.dialog.beschreibung_platzhalter': 'wofür die Vorlage gedacht ist',
};
/** Geänderte Bestandstexte (DE-Wortlaut Mockup). */
const GEAENDERT: Record<string, string> = {
	'wetter.dialog.beschreibung': 'Beschreibung (optional)',
	'wetter.grenzen.hinweis': 'Grün ist alles zwischen „gelb unten“ und „gelb oben“. Ein leeres Feld heißt: auf dieser Seite keine Grenze.',
	'wetter.grenzen.abweichend': 'Abweichend von der Vorlage „{vorlage}“.',
	'wetter.gewitter.keins_gruen': '„keins“ ist immer grün.',
	'wetter.vorlage.verlust.one': 'Deine 1 Abweichung von „{alt}“ geht verloren.',
	'wetter.vorlage.verlust.other': 'Deine {count} Abweichungen von „{alt}“ gehen verloren.',
};

describe('#3111 Katalog: neue Schlüssel in DE und EN', () => {
	for (const [k, wert] of Object.entries(NEU)) {
		test(`${k}: DE wortgetreu, EN vorhanden und ungleich DE`, () => {
			assert.equal(DE[k], wert, `DE ${k}`);
			assert.ok(EN[k] && EN[k].trim() !== '', `EN ${k} fehlt`);
			assert.notEqual(EN[k], DE[k], `EN ${k} ist nicht übersetzt (gleich DE)`);
			assert.deepEqual(platzhalter(EN[k]), platzhalter(DE[k]), `Platzhalter ${k} DE/EN`);
		});
	}
	test('Bestätigung für Orte: ersetzt_vergleich nennt „für diesen Ort“ bzw. „für diese Orte“ (Mockup Z. 488), nicht „Orts-Briefings“', () => {
		assert.ok(DE['wetter.vorlage.ersetzt_vergleich'], 'ersetzt_vergleich fehlt');
		assert.match(DE['wetter.vorlage.ersetzt_vergleich'], /^Ersetzt Metrik-Auswahl, Ampel-Grenzen und Alarmstufen für dies(en Ort|e Orte)\.$/);
		assert.ok(EN['wetter.vorlage.ersetzt_vergleich'] && EN['wetter.vorlage.ersetzt_vergleich'] !== DE['wetter.vorlage.ersetzt_vergleich']);
	});
	test('alle 7 Systemvorlagen tragen kuratierte Stichworte (Schlüsselmenge = Namensmenge)', () => {
		const namen = Object.keys(DE).filter((k) => k.startsWith('wetter.vorlage.name.')).map((k) => k.split('.').pop());
		const stich = Object.keys(DE).filter((k) => k.startsWith('wetter.vorlage.stichworte.')).map((k) => k.split('.').pop());
		assert.equal(namen.length, 7);
		assert.deepEqual([...stich].sort(), [...namen].sort());
	});
});

describe('#3111 Katalog: geänderte Bestandstexte', () => {
	for (const [k, wert] of Object.entries(GEAENDERT)) {
		test(`${k}: DE wortgetreu nach Mockup`, () => {
			assert.equal(DE[k], wert);
		});
	}
	test('EN „Beschreibung (optional)“ trägt „optional“', () => {
		assert.match(EN['wetter.dialog.beschreibung'], /\(optional\)/i);
	});
});

describe('#3111 Katalog: keine ‚…‘-Anführungszeichen mehr in den betroffenen DE-Texten', () => {
	const BETROFFEN = [
		'wetter.grenzen.hinweis', 'wetter.grenzen.abweichend', 'wetter.gewitter.keins_gruen',
		'wetter.vorlage.verlust.one', 'wetter.vorlage.verlust.other', 'wetter.vorlage.frage_titel',
		'wetter.vorlage.frage_route', 'wetter.vorlage.frage_vergleich',
	];
	for (const k of BETROFFEN) {
		test(k, () => {
			if (DE[k] === undefined) return; // frage_route/_vergleich dürfen entfallen (ersetzt durch frage_titel + ersetzt_*)
			assert.doesNotMatch(DE[k], /[‚‘’]/, `${k} enthält noch ‚…‘: ${DE[k]}`);
		});
	}
});

describe('#3111 Katalog: Parität DE/EN', () => {
	test('DE und EN tragen dieselben Schlüssel', () => {
		assert.deepEqual(Object.keys(EN).sort(), Object.keys(DE).sort());
	});
});
