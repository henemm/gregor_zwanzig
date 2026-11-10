// Fix-Loop 6 Issue #2794 S3a Teil-PR 3, Adversary-Befund F002 (zweite Ursache AC-19, Kontext route):
// Ein per „−“ deaktivierter und per „+“ wieder aufgenommener Trip-Eintrag blieb in `metrics[]`
// an seinem alten Platz. Spec AC-19 („hinten angehaengt“) und AC-37 („neue Metriken hinten“)
// verlangen hinten; der Vergleich haengt bereits hinten an (Code-Teilung Trip/Vergleich).
//
// Tech-Lead-Entscheidung (fix-loop-5.md): ein im Bestand `enabled: false` stehender Eintrag, der
// jetzt in der Auswahl steht, gilt als neu hinzugefuegt → ans Ende (Auswahl-Reihenfolge, zusammen
// mit echten Neuen) und behaelt ALLE uebrigen Felder (Feld-Eigentum Spec §(e), Read-Modify-Write).
// Nicht ausgewaehlte bleiben deaktiviert an ihrem Platz.
//
// Gemessen ueber die oeffentliche Schreib-Funktion `tripSpeicherPayload` (das, was der Reiter PUTtet).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/shared/wetter-tab/__tests__/fixloop6_trip_wieder_hinzu_hinten.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { tripSpeicherPayload } from '../ampelSchreiben.ts';

type Eintrag = { metric_id: string; enabled: boolean } & Record<string, unknown>;

function speichern(bestand: Eintrag[], auswahl: string[]): Eintrag[] {
	const p = tripSpeicherPayload({
		vorlage: { template: 'wandern', metrics: {} },
		aufgeloest: { template: 'wandern', metrics: {} },
		auswahl,
		displayConfig: { metrics: structuredClone(bestand) },
		reportConfig: {},
		warnFelder: {},
		warnungenAn: false,
		tagesfenster: { start: 6, end: 20 }
	});
	return p.weatherConfig.metrics as Eintrag[];
}

const A = { metric_id: 'temperature', enabled: true, format_mode: 'raw' };
const WIND_AUS = { metric_id: 'wind', enabled: false, sms_threshold: 12, use_friendly_format: true };
const B = { metric_id: 'humidity', enabled: true };

describe('F002/AC-19/AC-37 route: wieder aufgenommene Metrik steht hinten', () => {
	test('deaktivierter Bestandseintrag in der Auswahl wandert ans Ende und behaelt seine Felder', () => {
		const metrics = speichern([A, WIND_AUS, B], ['temperature', 'humidity', 'wind']);
		assert.deepEqual(metrics.map((e) => e.metric_id), ['temperature', 'humidity', 'wind'], 'Wind nicht hinten angehaengt');
		const wind = metrics.find((e) => e.metric_id === 'wind');
		assert.deepEqual(wind, { metric_id: 'wind', enabled: true, sms_threshold: 12, use_friendly_format: true }, 'Felder von Wind verloren oder nicht aktiviert');
		assert.equal(metrics.length, 3, 'Eintrag doppelt');
	});

	test('wieder aufgenommene und echt neue Metriken stehen hinten in Auswahl-Reihenfolge', () => {
		const metrics = speichern([A, WIND_AUS, B], ['temperature', 'dewpoint', 'humidity', 'wind']);
		assert.deepEqual(metrics.map((e) => e.metric_id), ['temperature', 'humidity', 'dewpoint', 'wind']);
		assert.deepEqual(metrics[2], { metric_id: 'dewpoint', enabled: true });
	});

	test('nicht ausgewaehlter deaktivierter Eintrag bleibt an seinem Platz deaktiviert', () => {
		const metrics = speichern([A, WIND_AUS, B], ['temperature', 'humidity']);
		assert.deepEqual(metrics.map((e) => e.metric_id), ['temperature', 'wind', 'humidity']);
		assert.deepEqual(metrics[1], WIND_AUS, 'deaktivierter Eintrag veraendert');
	});

	test('unveraenderte Auswahl aendert die Reihenfolge nicht', () => {
		const bestand = [A, B, { metric_id: 'wind', enabled: true, sms_threshold: 12 }];
		const metrics = speichern(bestand, ['temperature', 'humidity', 'wind']);
		assert.deepEqual(metrics, bestand);
	});

	test('entfernte Metrik bleibt an ihrem Platz, nur deaktiviert', () => {
		const metrics = speichern([A, { metric_id: 'wind', enabled: true, sms_threshold: 12 }, B], ['temperature', 'humidity']);
		assert.deepEqual(metrics.map((e) => e.metric_id), ['temperature', 'wind', 'humidity']);
		assert.deepEqual(metrics[1], { metric_id: 'wind', enabled: false, sms_threshold: 12 });
	});
});
