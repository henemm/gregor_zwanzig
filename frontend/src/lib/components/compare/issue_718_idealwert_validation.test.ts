// Issue #718 (Epic #677): Compare-Editor Slice 4 — Idealwert-Validierung
//
// Spec: docs/specs/modules/issue_718_compare_editor_slice4_validierung.md
//
// Epic #1301 F2b (2026-07-19): Der Alt-Editor `compareEditorLogic.ts` (doneTabs)
// wurde ersatzlos gelöscht (abgelöst durch compareNewLogic.ts, F2a). Die
// doneTabs()-Blöcke (AC-3/AC-5) sind daher entfallen — nur die
// validateIdealRanges()-Blöcke (compareMetricDefs.ts, bleibt bestehen) leben
// hier weiter.
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/issue_718_idealwert_validation.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { validateIdealRanges } from './compareMetricDefs.ts';

// ─────────────────────────────────────────────────────────────────────────────
// AC-1/AC-2/AC-4: validateIdealRanges() — pure Funktion
// ─────────────────────────────────────────────────────────────────────────────
describe('AC-1/AC-4: validateIdealRanges() — Kernlogik', () => {
	test('min > max → invalid, invalidKeys enthält den Key', () => {
		// RED: validateIdealRanges ist nicht exportiert → TypeError beim Aufruf
		const result = validateIdealRanges(
			{ temp_max_c: { min: 35, max: 15 } },
			['temp_max_c']
		);
		assert.equal(result.valid, false, 'min 35 > max 15 muss invalid sein');
		assert.ok(
			result.invalidKeys.includes('temp_max_c'),
			'temp_max_c muss in invalidKeys stehen'
		);
	});

	test('min === max → invalid (kein sinnvoller Bereich)', () => {
		const result = validateIdealRanges(
			{ wind_max_kmh: { min: 30, max: 30 } },
			['wind_max_kmh']
		);
		assert.equal(result.valid, false, 'min === max ist kein gültiger Bereich');
	});

	test('min < max → valid, invalidKeys leer', () => {
		const result = validateIdealRanges(
			{ temp_max_c: { min: 10, max: 25 } },
			['temp_max_c']
		);
		assert.equal(result.valid, true, 'min 10 < max 25 ist valide');
		assert.equal(result.invalidKeys.length, 0, 'invalidKeys muss leer sein');
	});

	test('enum-Metrik ohne min-Wert → valid (kein min/max Vergleich)', () => {
		const result = validateIdealRanges(
			{ thunder_level_max: { max: 'NONE' } },
			['thunder_level_max']
		);
		assert.equal(result.valid, true, 'enum-Metriken ohne numerisches min sind valide');
	});

	test('leere idealRanges → valid (keine aktiven Metriken mit Fehler)', () => {
		const result = validateIdealRanges({}, ['temp_max_c']);
		assert.equal(result.valid, true, 'fehlende Range zählt nicht als Fehler');
	});

	test('Metrik nicht in activeKeys → ignoriert (auch wenn min > max)', () => {
		const result = validateIdealRanges(
			{ temp_max_c: { min: 40, max: 10 } }, // Fehler, aber Metrik nicht aktiv
			['wind_max_kmh'] // temp_max_c nicht aktiv
		);
		assert.equal(result.valid, true, 'inaktive Metriken werden nicht validiert');
	});

	test('mehrere Metriken, eine fehlerhaft → invalid mit korrekten invalidKeys', () => {
		const result = validateIdealRanges(
			{
				temp_max_c: { min: 10, max: 25 },     // ok
				wind_max_kmh: { min: 80, max: 20 },   // fehler: 80 > 20
				precip_sum_mm: { min: 0, max: 5 }     // ok
			},
			['temp_max_c', 'wind_max_kmh', 'precip_sum_mm']
		);
		assert.equal(result.valid, false);
		assert.deepEqual(result.invalidKeys, ['wind_max_kmh']);
	});
});

// AC-3/AC-5 (doneTabs()-Blöcke) entfallen mit Epic #1301 F2b — die Alt-Editor-
// Lock-Engine compareEditorLogic.ts (inkl. doneTabs()) wurde ersatzlos gelöscht,
// abgelöst durch compareNewLogic.ts (F2a), dort eigenständig getestet.
//
// canAdvanceStep3 / canAdvanceCurrent-Getter: via E2E geprüft
// (compare-editor-idealwert-validation.spec.ts AC-2)
// Begründung: CompareWizardState nutzt Svelte-Runes ($state/$derived) —
// diese sind außerhalb des Svelte-Kompilierungsschritts nicht ausführbar.
