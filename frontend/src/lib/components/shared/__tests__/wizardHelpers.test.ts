// TDD RED — Tests für Epic #136 Master-Spec gemeinsame Helper.
// Erwartet: FAIL bis wizardHelpers.ts angelegt und alle Funktionen exportiert sind.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-wizard/__tests__/wizardHelpers.test.ts
//
// Node 22+ benötigt für --experimental-strip-types.

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
	mapActivityToProfile,
	formatStageNumber,
	isPauseStage,
	addDays,
	today,
	newId
} from '../wizardHelpers.ts';

test('mapActivityToProfile: trekking → summer_trekking', () => {
	assert.equal(mapActivityToProfile('trekking'), 'summer_trekking');
});

test('mapActivityToProfile: skitour → wintersport', () => {
	assert.equal(mapActivityToProfile('skitour'), 'wintersport');
});

test('mapActivityToProfile: hochtour → summer_trekking', () => {
	assert.equal(mapActivityToProfile('hochtour'), 'summer_trekking');
});

test('mapActivityToProfile: klettersteig → summer_trekking', () => {
	assert.equal(mapActivityToProfile('klettersteig'), 'summer_trekking');
});

test('mapActivityToProfile: mtb → allgemein', () => {
	assert.equal(mapActivityToProfile('mtb'), 'allgemein');
});

test('formatStageNumber: index 0 → T01', () => {
	assert.equal(formatStageNumber(0), 'T01');
});

test('formatStageNumber: index 9 → T10', () => {
	assert.equal(formatStageNumber(9), 'T10');
});

test('formatStageNumber: index 99 → T100', () => {
	assert.equal(formatStageNumber(99), 'T100');
});

test('isPauseStage: leere Wegpunkte → true', () => {
	assert.equal(isPauseStage({ id: 'p1', name: 'Pause', date: '2026-06-01', waypoints: [] }), true);
});

test('isPauseStage: mit Wegpunkten → false', () => {
	const stage = {
		id: 's1',
		name: 'Etappe',
		date: '2026-06-01',
		waypoints: [{ id: 'w1', name: 'Start', lat: 47, lon: 11, elevation_m: 500 }]
	};
	assert.equal(isPauseStage(stage), false);
});

test('addDays: 2026-05-09 + 1 Tag → 2026-05-10', () => {
	assert.equal(addDays('2026-05-09', 1), '2026-05-10');
});

test('addDays: Monatsgrenze 2026-05-31 + 1 → 2026-06-01', () => {
	assert.equal(addDays('2026-05-31', 1), '2026-06-01');
});

test('today: liefert ISO-Datum YYYY-MM-DD', () => {
	const t = today();
	assert.match(t, /^\d{4}-\d{2}-\d{2}$/);
});

test('newId: liefert nicht-leeren String', () => {
	const id = newId();
	assert.equal(typeof id, 'string');
	assert.ok(id.length > 0, 'ID darf nicht leer sein');
});

test('newId: liefert eindeutige Werte', () => {
	const ids = new Set<string>();
	for (let i = 0; i < 50; i++) ids.add(newId());
	assert.equal(ids.size, 50, 'alle 50 IDs müssen unterschiedlich sein');
});
