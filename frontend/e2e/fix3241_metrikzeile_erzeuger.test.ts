// Issue #3241 (Epic #2913): Metrik-Zeilen im englischen Elementlisten-Abgleich einzeln prüfbar.
// Spec: docs/specs/modules/fix_3241_elementliste_en_metrikzeile_chips.md (AC-1 bis AC-4, Tests 1-4).
//
//   cd frontend && node --experimental-strip-types --test e2e/fix3241_metrikzeile_erzeuger.test.ts
//
// Kern-Schicht: echter Katalog (frontend/src/lib/i18n/messages), echte erzeugte Elementliste, kein Mock.
// Erwartete neue Funktion im Erzeuger: metrikZeileEn(abschnitt, textDe, katalog, allgemein): EnErgebnis.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as E from '../../scripts/elementliste_aus_mockup.ts';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, '..', '..');

const katalog = E.ladeKatalog(E.STANDARD_MESSAGES);

type Eintrag = { abschnitt: string; text_de: string; text_en: string | null; i18n_key: string | null; muster: string | null; luecke: boolean };
const LISTE: { elemente: Eintrag[] } = JSON.parse(readFileSync(join(REPO, 'docs/context/einstellungen_neu/elementliste.json'), 'utf-8'));

// Aufruf wie im Erzeuger: erst der allgemeine Zuordner, dann der Sonderfall.
const zeile = (abschnitt: string, textDe: string) => {
	const metrikZeileEn = (E as unknown as Record<string, unknown>).metrikZeileEn as
		| ((a: string, t: string, k: typeof katalog, g: ReturnType<typeof E.ermittleEn>) => ReturnType<typeof E.ermittleEn>)
		| undefined;
	assert.equal(typeof metrikZeileEn, 'function', 'metrikZeileEn ist (noch) nicht aus scripts/elementliste_aus_mockup.ts exportiert');
	return metrikZeileEn!(abschnitt, textDe, katalog, E.ermittleEn(textDe, katalog));
};

describe('#3241 Test 1 / AC-1: Einheit + Hinweis aus wetter.hinweis.*', () => {
	test('„mm · Summe“ wird „mm · total“', () => {
		const r = zeile('metriken', 'mm · Summe');
		assert.equal(r.text_en, 'mm · total');
		assert.equal(r.i18n_key, 'wetter.hinweis.precipitation');
		assert.equal(r.luecke, false);
	});
	test('„m · Minimum“ wird „m · minimum“', () => {
		const r = zeile('metriken', 'm · Minimum');
		assert.equal(r.text_en, 'm · minimum');
		assert.equal(r.i18n_key, 'wetter.hinweis.visibility');
		assert.equal(r.luecke, false);
	});
});

describe('#3241 Test 2 / AC-2: Hinweis mit eigenem „ · “ als Ganzes', () => {
	test('„°C · Tageshöchst · Tagestief“ wird „°C · daily high · daily low“', () => {
		const r = zeile('metriken', '°C · Tageshöchst · Tagestief');
		assert.equal(r.text_en, '°C · daily high · daily low');
		assert.equal(r.i18n_key, 'wetter.hinweis.temperature');
		assert.equal(r.luecke, false);
	});
});

describe('#3241 Test 3 / AC-3: Grünbereich ohne Einheit', () => {
	test('„· grün: bis 6“ wird Muster „· grün: bis {bis}“ / „· green: up to {bis}“', () => {
		const r = zeile('metriken', '· grün: bis 6');
		assert.equal(r.muster, '· grün: bis {bis}');
		assert.equal(r.text_en, '· green: up to {bis}');
		assert.equal(r.i18n_key, 'wetter.gruen.bis');
		assert.equal(r.luecke, false);
	});
	test('mit Einheit („· grün: bis 1 mm“) bleibt das allgemeine Ergebnis', () => {
		const allgemein = E.ermittleEn('· grün: bis 1 mm', katalog);
		assert.deepEqual(zeile('metriken', '· grün: bis 1 mm'), allgemein);
	});
	test('außerhalb von metriken unverändert', () => {
		for (const t of ['mm · Summe', '°C · Tageshöchst · Tagestief', '· grün: bis 6']) {
			assert.deepEqual(zeile('liste', t), E.ermittleEn(t, katalog), t);
		}
	});
});

describe('#3241 Test 4 / AC-4: erzeugte Liste', () => {
	const NEU: Record<string, { en: string }> = {
		'mm · Summe': { en: 'mm · total' },
		'm · Minimum': { en: 'm · minimum' },
		'°C · Tageshöchst · Tagestief': { en: '°C · daily high · daily low' },
		'· grün: bis 6': { en: '· green: up to {bis}' },
	};
	test('genau 12 Einträge tragen die neuen EN-Werte', () => {
		const m = LISTE.elemente.filter((e) => e.abschnitt === 'metriken' && Object.hasOwn(NEU, e.text_de));
		assert.equal(m.length, 12);
		for (const e of m) {
			assert.equal(e.text_en, NEU[e.text_de].en, e.text_de);
			assert.equal(e.luecke, false, e.text_de);
		}
	});
	test('andere Metrik-Zeilen behalten ihren Text („km/h · Mittelwind“)', () => {
		const m = LISTE.elemente.filter((e) => e.abschnitt === 'metriken' && e.text_de === 'km/h · Mittelwind');
		assert.ok(m.length > 0);
		for (const e of m) assert.equal(e.text_en, 'km/h · mean wind');
	});
});
