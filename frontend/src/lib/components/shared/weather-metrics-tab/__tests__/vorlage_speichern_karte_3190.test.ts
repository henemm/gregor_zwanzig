// Issue #3190 (Epic #2913), Fix-Loop nach Adversary (F001-F003): geteilte Bedienlogik der Karte
// „Als eigene Vorlage speichern“ ($lib/utils/vorlageSpeichernKarte.ts) und der Auslöser im Alt-Editor.
// Spec: docs/specs/modules/feat_3190_vorlage_dialog_inline.md (AC-6, AC-7, AC-8, AC-10)
//
// Die Logik ist dieselbe, die SavePresetDialog (Escape, Fokus ins Namensfeld), VorlageKarte (Reiter Wetter)
// und WeatherMetricsTab (Alt-Editor) aufrufen; die Attrappe mit `focus()` steht für den echten Knopf bzw.
// das echte Namensfeld. Die Browser-Verdrahtung prüft das Staging-E2E s3a2794-teil3-vorlage-inline.spec.ts.
//
//   cd frontend && npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/vorlage_speichern_karte_3190.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../../..');
const K = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/utils/vorlageSpeichernKarte.ts')).href);
// #3297/#3020: die zwei Faelle „WeatherMetricsTab verdrahtet Ausloeser und Karte“ entfallen (Datei geloescht).
// #3383 S1: der Block „Auslöser im Alt-Editor (WeatherV2PresetBar)" entfiel mit der Waise WeatherV2PresetBar.svelte.

/** Attrappe eines fokussierbaren Elements: zählt die focus()-Aufrufe. */
function knopf() {
	const k = { fokus: 0, focus() { k.fokus += 1; } };
	return k;
}

describe('#3190 F003/AC-6: Escape in der Karte', () => {
	test('Escape schließt, solange nicht gespeichert wird', () => {
		assert.equal(K.karteSchliesstPerTaste('Escape', false), true);
	});
	test('Escape während des Speicherns ist wirkungslos (Abbrechen ist dann gesperrt)', () => {
		assert.equal(K.karteSchliesstPerTaste('Escape', true), false);
	});
	test('andere Tasten schließen nie', () => {
		for (const taste of ['Enter', 'Tab', ' ', 'Esc']) assert.equal(K.karteSchliesstPerTaste(taste, false), false, taste);
	});
});

describe('#3190 F002/AC-7: Escape am Fenster schließt nur die offene Vorlagen-Auswahl', () => {
	test('Auswahl offen + Escape ⇒ schließen; zu oder andere Taste ⇒ nichts', () => {
		assert.equal(K.pickerSchliesstPerTaste('Escape', true), true);
		assert.equal(K.pickerSchliesstPerTaste('Escape', false), false);
		assert.equal(K.pickerSchliesstPerTaste('Enter', true), false);
	});
});

describe('#3190 F002/AC-8: Fokus ins Namensfeld beim Öffnen', () => {
	test('offen ⇒ Namensfeld bekommt den Fokus, nichts wird zurückgesetzt', () => {
		const feld = knopf();
		assert.equal(K.beiKartenWechsel(true, feld), 'fokus');
		assert.equal(feld.fokus, 1);
	});
	test('offen, Feld noch nicht da ⇒ kein Fehler, kein Zurücksetzen', () => {
		assert.equal(K.beiKartenWechsel(true, null), 'fokus');
	});
	test('geschlossen ⇒ zurücksetzen, kein Fokus', () => {
		const feld = knopf();
		assert.equal(K.beiKartenWechsel(false, feld), 'zuruecksetzen');
		assert.equal(feld.fokus, 0);
	});
});

describe('#3190 F001/AC-1/AC-6/AC-10: Auslöser schaltet um und bekommt den Fokus zurück', () => {
	test('Klick öffnet, zweiter Klick schließt', () => {
		const a = K.speicherKarteAusloeser();
		const k = knopf();
		assert.equal(a.umschalten(k, false), true);
		assert.equal(a.umschalten(k, true), false);
	});
	test('nach Abbrechen/Escape/Speichern geht der Fokus auf den zuletzt geklickten Auslöser', () => {
		const a = K.speicherKarteAusloeser();
		const k = knopf();
		a.zurueck(); // noch nie geklickt: nichts
		a.umschalten(k, false);
		a.zurueck();
		assert.equal(k.fokus, 1);
	});
	test('ohne Element (z. B. Aufruf ohne Klick) bleibt der gemerkte Auslöser', () => {
		const a = K.speicherKarteAusloeser();
		const k = knopf();
		a.umschalten(k, false);
		a.umschalten(null, true);
		a.zurueck();
		assert.equal(k.fokus, 1);
	});
});
