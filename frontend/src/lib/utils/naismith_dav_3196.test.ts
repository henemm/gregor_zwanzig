// TDD RED — Issue #3196 (Workflow feat-3196-trip-tempo-etappen)
// Spec: docs/specs/modules/feat_3196_trip_tempo_etappen.md — AC-3, AC-4, AC-6, AC-12
//
// TS-Rechner nach DAV (DIN 33466) gegen die gemeinsame Falltabelle
// tests/fixtures/naismith_dav_paritaet.json (dieselbe lesen Go und Python).
// Rad rechnet mit 600/1000 Hm/h (bisherige Drift 300/500 behoben).
//
// Erwarteter Vertrag (naismith.ts):
//   davHours(km, hmAuf, hmAb, speeds) -> Stunden
//   tripTempo(trip) -> { fortbewegung, grundtempo_kmh, flatKmh, ascentMh, descentMh }
//     (tempo am Trip, sonst Ableitung aus activity)
//   deriveTempo(activity) -> Tempo
//   wechsleFortbewegung(tempo, neu) -> Tempo mit Vorschlagswert (AC-4)
//   computeArrivalTimes(stage, startTime, tempo) rechnet nach DAV
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/utils/naismith_dav_3196.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { davHours, tripTempo, deriveTempo, wechsleFortbewegung, computeArrivalTimes, istGueltigesTempo } from './naismith.ts';
import type { Stage, Tempo } from '../types.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const TABELLE = JSON.parse(
	readFileSync(path.resolve(HERE, '../../../../tests/fixtures/naismith_dav_paritaet.json'), 'utf-8')
);

for (const f of TABELLE.faelle) {
	test(`AC-6 Falltabelle: ${f.name}`, () => {
		const sp = tripTempo({ tempo: { fortbewegung: f.fortbewegung, grundtempo_kmh: f.grundtempo_kmh } } as never);
		const got = davHours(f.km, f.hm_auf, f.hm_ab, sp) * 60;
		assert.ok(Math.abs(got - f.minuten) < 1e-6, `${f.name}: erwartet ${f.minuten}, bekommen ${got}`);
	});
}

test('AC-6: Rad nutzt 600/1000 Hm/h (Drift gegen Go behoben)', () => {
	const sp = tripTempo({ tempo: { fortbewegung: 'rad', grundtempo_kmh: 20 } } as never);
	assert.equal(sp.ascentMh, 600);
	assert.equal(sp.descentMh, 1000);
});

for (const [activity, want] of Object.entries(TABELLE.ableitung_activity)) {
	test(`AC-2/AC-12 Ableitung activity="${activity}"`, () => {
		assert.deepEqual(deriveTempo(activity as never), want);
		const sp = tripTempo({ activity } as never);
		assert.equal(sp.fortbewegung, (want as Tempo).fortbewegung);
		assert.equal(sp.grundtempo_kmh, (want as Tempo).grundtempo_kmh);
	});
}

test('AC-12: gespeichertes tempo hat Vorrang vor activity', () => {
	const sp = tripTempo({ activity: 'fahrrad_20', tempo: { fortbewegung: 'fuss', grundtempo_kmh: 5 } } as never);
	assert.equal(sp.fortbewegung, 'fuss');
	assert.equal(sp.flatKmh, 5);
	assert.equal(sp.ascentMh, 375);
});

test('AC-4: Wechsel der Fortbewegung setzt das Grundtempo auf den Vorschlag', () => {
	let t: Tempo = { fortbewegung: 'fuss', grundtempo_kmh: 4.5 };
	t = wechsleFortbewegung(t, 'rad');
	assert.deepEqual(t, { fortbewegung: 'rad', grundtempo_kmh: 20 });
	t = wechsleFortbewegung(t, 'mtb');
	assert.deepEqual(t, { fortbewegung: 'mtb', grundtempo_kmh: 12 });
	t = wechsleFortbewegung(t, 'ski');
	assert.deepEqual(t, { fortbewegung: 'ski', grundtempo_kmh: 3 });
	t = wechsleFortbewegung(t, 'fuss');
	assert.deepEqual(t, { fortbewegung: 'fuss', grundtempo_kmh: 4 });
});

test('AC-3: Etappe 8 km ↑600 ↓600 zu Fuß 4 km/h = 4:12 (08:00 → 12:12)', () => {
	const stage = {
		id: 'S1', name: 'D1', date: '2026-07-01',
		waypoints: [
			{ id: 'A', name: 'A', lat: 47, lon: 11, elevation_m: 1000, distance_from_start_km: 0 },
			{ id: 'B', name: 'B', lat: 47, lon: 11, elevation_m: 1600, distance_from_start_km: 4 },
			{ id: 'C', name: 'C', lat: 47, lon: 11, elevation_m: 1000, distance_from_start_km: 8 }
		]
	} as unknown as Stage;
	const arr = computeArrivalTimes(stage, '08:00', { fortbewegung: 'fuss', grundtempo_kmh: 4 });
	assert.deepEqual(arr, ['08:00', '10:30', '12:12']);
});

// Fix-Loop 2, F001: Grenzen 0.5 <= v <= 60 aus derselben Tabelle wie Go und Python.
test('F001: Gueltigkeitstabelle (Untergrenze 0.5, Obergrenze 60)', () => {
	assert.ok(Array.isArray(TABELLE.gueltigkeit) && TABELLE.gueltigkeit.length >= 8, 'Gueltigkeitstabelle fehlt');
	for (const g of TABELLE.gueltigkeit) {
		const got = istGueltigesTempo({ fortbewegung: g.fortbewegung, grundtempo_kmh: g.grundtempo_kmh } as Tempo);
		assert.equal(got, g.gueltig, `istGueltigesTempo(${g.fortbewegung}, ${g.grundtempo_kmh})`);
	}
});
