// TDD: Issue #154 — Epic #135 Step 3: Trip-Hero Pure-Functions.
//
// Spec: docs/specs/modules/epic_135_step3_trip_hero.md
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/utils/tripHero.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { formatDateRange } from './tripHero.ts';
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
