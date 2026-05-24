// TDD RED: Issue #343 — computeHorizonSummary() Wording-Heuristik
//
// Spec: docs/specs/modules/issue_343_horizon_chip_ui.md  §6 + Wording-Heuristik
//
// `horizonHelpers.ts` existiert in der RED-Phase noch NICHT → der Import wirft
// einen Modul-Resolve-Fehler und alle Tests scheitern.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/utils/horizonHelpers.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { computeHorizonSummary, dotsForHorizons } from './horizonHelpers.ts';

// =========================================================================
// Helpers
// =========================================================================

type Horizons = { today: boolean; tomorrow: boolean; day_after: boolean };

type HorizonSummaryInput = {
	metric_id: string;
	horizons: Horizons;
	enabled?: boolean;
};

function h(t: boolean, m: boolean, d: boolean): Horizons {
	return { today: t, tomorrow: m, day_after: d };
}

function metric(id: string, horizons: Horizons, enabled = true): HorizonSummaryInput {
	return { metric_id: id, horizons, enabled };
}

// =========================================================================
// Tests
// =========================================================================

test('5 Metriken mit allen drei Horizonten → "5 alle drei Tage"', () => {
	const metrics = [
		metric('m1', h(true, true, true)),
		metric('m2', h(true, true, true)),
		metric('m3', h(true, true, true)),
		metric('m4', h(true, true, true)),
		metric('m5', h(true, true, true)),
	];
	const result = computeHorizonSummary(metrics);
	assert.equal(result, '5 alle drei Tage');
});

test('2 Metriken nur heute + morgen → "2 nur heute + morgen"', () => {
	const metrics = [
		metric('m1', h(true, true, false)),
		metric('m2', h(true, true, false)),
	];
	const result = computeHorizonSummary(metrics);
	assert.equal(result, '2 nur heute + morgen');
});

test('1 Metrik nur heute → "1 nur heute"', () => {
	const metrics = [metric('m1', h(true, false, false))];
	const result = computeHorizonSummary(metrics);
	assert.equal(result, '1 nur heute');
});

test('gemischtes Beispiel aus Mockup: 5 alle / 2 heute+morgen / 1 nur heute', () => {
	const metrics = [
		// 5 × alle drei
		metric('a1', h(true, true, true)),
		metric('a2', h(true, true, true)),
		metric('a3', h(true, true, true)),
		metric('a4', h(true, true, true)),
		metric('a5', h(true, true, true)),
		// 2 × heute + morgen
		metric('b1', h(true, true, false)),
		metric('b2', h(true, true, false)),
		// 1 × nur heute
		metric('c1', h(true, false, false)),
	];
	const result = computeHorizonSummary(metrics);
	assert.equal(
		result,
		'5 alle drei Tage · 2 nur heute + morgen · 1 nur heute',
		`Trenner " · " (Mittelpunkt mit Spaces) und Bucket-Reihenfolge (alle → heute+morgen → nur heute) erwartet, bekommen: "${result}"`
	);
});

test('exotische Kombination (nur uebermorgen) → "sonstige Kombinationen"', () => {
	const metrics = [metric('m1', h(false, false, true))];
	const result = computeHorizonSummary(metrics);
	assert.match(
		result,
		/1 sonstige Kombinationen/,
		`Pattern (false,false,true) muss in den "sonstige Kombinationen"-Bucket fallen, bekommen: "${result}"`
	);
});

test('disabled Metriken werden nicht gezaehlt (nur enabled)', () => {
	const metrics = [
		// 3 enabled mit allen drei
		metric('e1', h(true, true, true), true),
		metric('e2', h(true, true, true), true),
		metric('e3', h(true, true, true), true),
		// 2 disabled — duerfen NICHT in die Summary einfliessen
		metric('d1', h(true, true, true), false),
		metric('d2', h(true, false, false), false),
	];
	const result = computeHorizonSummary(metrics);
	assert.equal(
		result,
		'3 alle drei Tage',
		`disabled-Metriken muessen ignoriert werden — bekommen: "${result}"`
	);
});

test('leere Metrik-Liste → "" (leerer String)', () => {
	const result = computeHorizonSummary([]);
	assert.equal(
		result,
		'',
		`leere Liste muss "" ergeben, keine Buckets — bekommen: "${result}"`
	);
});

test('dotsForHorizons: ●/○-Pattern in Reihenfolge heute/morgen/uebermorgen', () => {
	assert.equal(dotsForHorizons(h(true, true, true)), '●●●');
	assert.equal(dotsForHorizons(h(true, true, false)), '●●○');
	assert.equal(dotsForHorizons(h(true, false, false)), '●○○');
	assert.equal(dotsForHorizons(h(false, false, false)), '○○○');
});
