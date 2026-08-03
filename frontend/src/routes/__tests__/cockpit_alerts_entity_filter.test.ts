// TDD RED — Issue #1467 Scheibe S1: Alarm-Filter der Startseite unterscheidet Typen.
//
// Spec: docs/specs/modules/rework_1467_s1_alarm_kennung.md (AC-9)
//
// Der Bestand filtert in +page.svelte:109 mit `a.trip_id === hero?.id`. Nach der
// Zusammenlegung liegen Tour- und Ortsvergleichs-Kennungen im SELBEN Feld — ein
// Gleichheits-Vergleich allein ist dann nicht mehr eindeutig. Der Filter zieht
// deshalb in cockpitHelpers.ts um und prüft Kennung UND Typ.
//
// Reine Funktion, kein Render, keine Mocks.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/routes/__tests__/cockpit_alerts_entity_filter.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { alertsForTrip } from '../_home/cockpitHelpers.ts';

const base = { sent_at: '2026-08-03T06:00:00Z', changes_count: 1, severity: 'LOW' as const };

test('AC-9: gleiche Kennung, anderer Typ — nur der Tour-Alarm erscheint', () => {
	const alerts = [
		{ ...base, entity_id: 'x1', entity_type: 'trip' },
		{ ...base, entity_id: 'x1', entity_type: 'compare' }
	];

	const result = alertsForTrip(alerts, 'x1');

	assert.equal(result.length, 1, 'nur der Tour-Eintrag darf durchkommen');
	assert.equal(result[0].entity_type, 'trip');
});

test('AC-9: fremde Tour wird nicht mitgezählt', () => {
	const alerts = [
		{ ...base, entity_id: 'x1', entity_type: 'trip' },
		{ ...base, entity_id: 'x2', entity_type: 'trip' }
	];

	assert.equal(alertsForTrip(alerts, 'x1').length, 1);
});

test('AC-9: ohne Tour-Kennung bleibt die Liste leer statt alles durchzulassen', () => {
	const alerts = [{ ...base, entity_id: 'x1', entity_type: 'trip' }];

	assert.equal(alertsForTrip(alerts, undefined).length, 0);
});

test('AC-9: leere Alarm-Liste ergibt leere Liste (fail-soft)', () => {
	assert.equal(alertsForTrip(undefined, 'x1').length, 0);
});
