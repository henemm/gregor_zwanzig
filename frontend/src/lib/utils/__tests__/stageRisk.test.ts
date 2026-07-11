// TDD RED: Issue #1223 — Cockpit-Etappen-Kacheln: Wetter-Risiko-Farben.
//
// Spec: docs/specs/modules/fix_1223_cockpit_stage_risk_colors.md
//
// Reproduziert den doppelten Defekt aus Nutzersicht:
//   AC-1: red/yellow/green → korrekte Pill-Töne + Labels (heute: alles fällt auf 'good'/'OK')
//   AC-2: null/undefined → neutrale '—'-Pille, NIE Falsch-Grün
//   AC-3: fetchStageRisk ruft korrekten Endpoint auf, mappt risk je Etappe, fail-soft
//
// RED vor Implementierung: src/lib/utils/stageRisk.ts existiert noch nicht → Import-Fehler.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/utils/__tests__/stageRisk.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { riskToPill, fetchStageRisk } from '../stageRisk.ts';
import type { StagesWeatherResponse } from '../../types.ts';

// ── AC-1: Mapping der Risiko-Stufen auf Pill-Ton + Label ──────────────────────

test('AC-1: red → Ton bad, Label "Risiko"', () => {
	assert.deepEqual(riskToPill('red'), { tone: 'bad', label: 'Risiko' });
});

test('AC-1: yellow → Ton warn, Label "Achten"', () => {
	assert.deepEqual(riskToPill('yellow'), { tone: 'warn', label: 'Achten' });
});

test('AC-1: green → Ton good, Label "OK"', () => {
	assert.deepEqual(riskToPill('green'), { tone: 'good', label: 'OK' });
});

test('AC-1: drei Stufen sind eindeutig unterscheidbar', () => {
	const tones = new Set(['red', 'yellow', 'green'].map((r) => riskToPill(r as 'red').tone));
	assert.equal(tones.size, 3, 'red/yellow/green müssen drei verschiedene Töne ergeben');
});

// ── AC-2: Kein Falsch-Grün bei fehlenden Daten ────────────────────────────────

test('AC-2: null → neutrale "—"-Pille, NICHT grün', () => {
	const pill = riskToPill(null);
	assert.deepEqual(pill, { tone: 'neutral', label: '—' });
	assert.notEqual(pill.tone, 'good', 'null darf NIEMALS als grünes OK erscheinen');
});

test('AC-2: undefined (noch am Laden) → neutrale "—"-Pille, NICHT grün', () => {
	const pill = riskToPill(undefined);
	assert.deepEqual(pill, { tone: 'neutral', label: '—' });
	assert.notEqual(pill.tone, 'good', 'fehlende Daten dürfen NIEMALS als grünes OK erscheinen');
});

// ── AC-3: Endpoint-Fetch, Merge, Fail-Soft ────────────────────────────────────

const FIXTURE: StagesWeatherResponse = {
	results: {
		's-1': { weather_summary: null, risk: 'red' },
		's-2': { weather_summary: null, risk: 'green' },
		's-3': { weather_summary: null, risk: null },
		's-4': null
	}
};

test('AC-3: ruft genau /api/trips/{id}/stages/weather und mappt risk je Etappe', async () => {
	let calledUrl = '';
	const fakeFetch = async (url: string) => {
		calledUrl = url;
		return {
			ok: true,
			json: async () => FIXTURE
		} as Response;
	};

	const map = await fetchStageRisk('trip-42', fakeFetch as typeof fetch);

	assert.equal(calledUrl, '/api/trips/trip-42/stages/weather');
	assert.equal(map['s-1'], 'red');
	assert.equal(map['s-2'], 'green');
	assert.equal(map['s-3'], null); // vorhanden, aber ohne Bewertung
	assert.equal(map['s-4'], null); // Etappe ganz ohne Ergebnis
});

test('AC-3: Endpoint-Fehler (reject) → leere Map, kein Throw (fail-soft)', async () => {
	const rejectFetch = async () => {
		throw new Error('network down');
	};
	const map = await fetchStageRisk('trip-42', rejectFetch as unknown as typeof fetch);
	assert.deepEqual(map, {}, 'bei Fehler neutrale/leere Map — kein Crash');
});

test('AC-3: Non-OK-Response → leere Map, kein Throw (fail-soft)', async () => {
	const notOkFetch = async () =>
		({ ok: false, json: async () => ({}) }) as Response;
	const map = await fetchStageRisk('trip-42', notOkFetch as typeof fetch);
	assert.deepEqual(map, {});
});
