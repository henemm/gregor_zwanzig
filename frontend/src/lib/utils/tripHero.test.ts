// TDD: Issue #154 — Epic #135 Step 3: Trip-Hero Pure-Functions.
//
// Spec: docs/specs/modules/epic_135_step3_trip_hero.md
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/utils/tripHero.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
	getActiveStageDisplay,
	getNextBriefing,
	getDaysLabel,
	formatDateRange
} from './tripHero.ts';
import type { Trip, Stage } from '../types.ts';

function tripWith(overrides: Partial<Trip>): Trip {
	return {
		id: 't1',
		name: 'Test Trip',
		stages: [],
		...overrides
	} as Trip;
}

function stage(date: string, name = 'Etappe', id?: string): Stage {
	return { id: id ?? `s-${date}`, name, date, waypoints: [] } as Stage;
}

const TODAY = new Date('2026-05-12T12:00:00Z');

// =============================================================================
// getActiveStageDisplay
// =============================================================================

// AC-2: planned, 3 Tage bis Start
test('AC-2: getActiveStageDisplay — planned + 3 Tage bis Start → "startet in 3 Tagen"', () => {
	const trip = tripWith({
		stages: [stage('2026-05-15'), stage('2026-05-17')]
	});
	const result = getActiveStageDisplay(trip, TODAY);
	assert.match(result, /startet in 3 Tagen/);
});

// AC-3: active, heute = Stage 2 von 5
test('AC-3: getActiveStageDisplay — active, Stage 2/5 "Vizzavona" → "Tag 2/5 · Vizzavona"', () => {
	const trip = tripWith({
		stages: [
			stage('2026-05-11', 'Calenzana'),
			stage('2026-05-12', 'Vizzavona'),
			stage('2026-05-13', 'Capannelle'),
			stage('2026-05-14', 'Asinau'),
			stage('2026-05-15', 'Conca')
		]
	});
	assert.equal(getActiveStageDisplay(trip, TODAY), 'Tag 2/5 · Vizzavona');
});

// AC-4: paused
test('AC-4: getActiveStageDisplay — paused_at gesetzt → genau "Pausiert"', () => {
	const trip = tripWith({
		paused_at: '2026-05-11T09:00:00Z',
		stages: [stage('2026-05-11'), stage('2026-05-14')]
	});
	assert.equal(getActiveStageDisplay(trip, TODAY), 'Pausiert');
});

// AC-5: archived
test('AC-5: getActiveStageDisplay — archived + Ende vor 3 Tagen → "Beendet vor 3 Tagen"', () => {
	const trip = tripWith({
		archived_at: '2026-05-10T00:00:00Z',
		stages: [stage('2026-05-08'), stage('2026-05-09')]
	});
	const result = getActiveStageDisplay(trip, TODAY);
	assert.match(result, /Beendet vor 3 Tagen/);
});

// Edge: planned + 1 Tag → "Trip startet morgen"
test('Edge: getActiveStageDisplay — planned + 1 Tag → "Trip startet morgen"', () => {
	const trip = tripWith({
		stages: [stage('2026-05-13')]
	});
	const result = getActiveStageDisplay(trip, TODAY);
	assert.match(result, /Trip startet morgen/);
});

// Edge: active ohne heutigen Stage → "Trip läuft"
test('Edge: getActiveStageDisplay — active ohne heutigen Stage → "Trip läuft"', () => {
	const trip = tripWith({
		stages: [stage('2026-05-10'), stage('2026-05-14')] // heute ist 12., kein Stage am 12.
	});
	assert.equal(getActiveStageDisplay(trip, TODAY), 'Trip läuft');
});

// =============================================================================
// getNextBriefing
// =============================================================================

// AC-6: kein report_config → "Briefings deaktiviert"
test('AC-6: getNextBriefing — kein report_config → "Briefings deaktiviert"', () => {
	const trip = tripWith({
		stages: [stage('2026-05-12')]
	});
	assert.equal(getNextBriefing(trip, TODAY), 'Briefings deaktiviert');
});

// AC-6b: enabled=false → "Briefings deaktiviert"
test('AC-6b: getNextBriefing — enabled=false → "Briefings deaktiviert"', () => {
	const trip = tripWith({
		stages: [stage('2026-05-12')],
		report_config: { enabled: false, morning_time: '07:00:00', evening_time: '18:00:00' }
	});
	assert.equal(getNextBriefing(trip, TODAY), 'Briefings deaktiviert');
});

// AC-7: morning_time vor now → "heute, 07:00"
test('AC-7: getNextBriefing — morning_time=07:00, now=05:30 → "heute, 07:00"', () => {
	const trip = tripWith({
		stages: [stage('2026-05-12')],
		report_config: { enabled: true, morning_time: '07:00:00', evening_time: '18:00:00' }
	});
	const now = new Date('2026-05-12T05:30:00');
	assert.match(getNextBriefing(trip, now), /heute, 07:00/);
});

// AC-8: nach evening → "morgen, 07:00"
test('AC-8: getNextBriefing — now nach evening → "morgen, 07:00"', () => {
	const trip = tripWith({
		stages: [stage('2026-05-12')],
		report_config: { enabled: true, morning_time: '07:00:00', evening_time: '18:00:00' }
	});
	const now = new Date('2026-05-12T19:00:00');
	assert.match(getNextBriefing(trip, now), /morgen, 07:00/);
});

// =============================================================================
// getDaysLabel
// =============================================================================

// AC-9: planned, 3 Tage → "in 3 Tagen"
test('AC-9: getDaysLabel — planned + 3 Tage bis Start → "in 3 Tagen"', () => {
	const trip = tripWith({ stages: [stage('2026-05-15')] });
	assert.equal(getDaysLabel(trip, TODAY), 'in 3 Tagen');
});

// AC-9-Edge: planned + 1 Tag → "morgen"
test('AC-9-Edge: getDaysLabel — planned + 1 Tag → "morgen"', () => {
	const trip = tripWith({ stages: [stage('2026-05-13')] });
	assert.equal(getDaysLabel(trip, TODAY), 'morgen');
});

// AC-9-Edge: planned + 0 Tage (heute!) — Stage IST heute, ist also active, nicht planned
// Aber für planned mit 0 Tagen Differenz (Stage am gleichen Tag wie now)
// = ist eigentlich "active" durch deriveTripStatus. Daher kein eigener Test.

// AC-10: active, Tag 2 → "läuft seit Tag 2"
test('AC-10: getDaysLabel — active, Tag 2 → "läuft seit Tag 2"', () => {
	const trip = tripWith({
		stages: [stage('2026-05-11'), stage('2026-05-12'), stage('2026-05-13')]
	});
	assert.equal(getDaysLabel(trip, TODAY), 'läuft seit Tag 2');
});

// =============================================================================
// formatDateRange
// =============================================================================

// AC-11: gleicher Monat
test('AC-11: formatDateRange — 11.–14. Mai 2026 (gleicher Monat)', () => {
	const trip = tripWith({
		stages: [stage('2026-05-11'), stage('2026-05-14')]
	});
	assert.equal(formatDateRange(trip), '11.–14. Mai 2026');
});

// AC-12: Monatswechsel
test('AC-12: formatDateRange — 30. Mai – 3. Juni 2026 (Monatswechsel)', () => {
	const trip = tripWith({
		stages: [stage('2026-05-30'), stage('2026-06-03')]
	});
	assert.equal(formatDateRange(trip), '30. Mai – 3. Juni 2026');
});

// AC-13: Jahreswechsel
test('AC-13: formatDateRange — Jahreswechsel', () => {
	const trip = tripWith({
		stages: [stage('2025-12-30'), stage('2026-01-03')]
	});
	assert.equal(formatDateRange(trip), '30. Dezember 2025 – 3. Januar 2026');
});

// AC-14: 1-Tages-Trip
test('AC-14: formatDateRange — 1-Tages-Trip → "11. Mai 2026" (kein Bindestrich)', () => {
	const trip = tripWith({
		stages: [stage('2026-05-11')]
	});
	assert.equal(formatDateRange(trip), '11. Mai 2026');
});

// Edge: keine Stages → ""
test('Edge: formatDateRange — leere Stages → ""', () => {
	const trip = tripWith({ stages: [] });
	assert.equal(formatDateRange(trip), '');
});

// Robustheit: unsortierte Stages → intern sortiert
test('Robustheit: formatDateRange — unsortierte Stages werden intern sortiert', () => {
	const trip = tripWith({
		stages: [stage('2026-05-14'), stage('2026-05-11')] // Reihenfolge umgekehrt
	});
	assert.equal(formatDateRange(trip), '11.–14. Mai 2026');
});
