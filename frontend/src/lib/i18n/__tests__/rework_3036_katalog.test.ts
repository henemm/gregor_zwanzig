// TDD RED — Issue #3036: Textkatalog für die zwei neuen Block-Schalter und ohne Übergangsblock.
// Spec docs/specs/modules/rework_3036_uebergangsblock_aufloesen.md, AC-6 (Titel/Hinweis DE und EN aus dem
// Katalog, ADR-0104) und AC-7 (Keys zustellung.uebergang.* entfallen).
// Gemessen über den Lookup trFor (Laufzeit-Katalog), nicht über Dateiinhalte.
// RED heute: die vier wetter.wsw.bloecke.*-Keys fehlen, zustellung.uebergang.titel/hinweis gibt es noch.
//
//   cd frontend && npm test -- src/lib/i18n/__tests__/rework_3036_katalog.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { trFor } from '../index.ts';
import { de } from '../messages/de/index.ts';
import { en } from '../messages/en/index.ts';

const NEU = [
	'wetter.wsw.bloecke.kurz',
	'wetter.wsw.bloecke.kurz_hinweis',
	'wetter.wsw.bloecke.grosswetterlage',
	'wetter.wsw.bloecke.grosswetterlage_hinweis'
];

describe('#3036 AC-6: Titel und Hinweis der neuen Schalter in DE und EN', () => {
	for (const key of NEU) {
		test(`${key}: DE und EN liefern einen eigenen Text (kein Schlüssel-Echo, kein deutscher Rückfall)`, () => {
			const textDe = trFor('de', key as never);
			const textEn = trFor('en', key as never);
			assert.notEqual(textDe, key, `DE: ${key} fehlt im Katalog`);
			assert.ok(Object.hasOwn(en, key), `EN: ${key} fehlt im Katalog (Rückfall auf Deutsch)`);
			assert.ok(textDe.trim().length > 0 && textEn.trim().length > 0, `${key}: leerer Text`);
			assert.notEqual(textEn, textDe, `${key}: EN gleich DE (nicht übersetzt)`);
		});
	}
	test('die Titel benennen Kurz-Zusammenfassung und Großwetterlage', () => {
		assert.match(trFor('de', 'wetter.wsw.bloecke.kurz' as never), /Kurz-Zusammenfassung/);
		assert.match(trFor('de', 'wetter.wsw.bloecke.grosswetterlage' as never), /Großwetterlage/);
	});
});

describe('#3036 AC-7: kein Übergangsblock mehr im Katalog', () => {
	for (const [lang, katalog] of [['de', de], ['en', en]] as const) {
		test(`${lang}: kein Key zustellung.uebergang.*`, () => {
			const rest = Object.keys(katalog).filter((k) => k.startsWith('zustellung.uebergang.'));
			assert.deepEqual(rest, [], `${lang}: Übergangsblock-Texte noch im Katalog`);
		});
	}
});
