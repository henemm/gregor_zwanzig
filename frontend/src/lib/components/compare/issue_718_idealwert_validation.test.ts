// TDD RED — Issue #718 (Epic #677): Compare-Editor Slice 4 — Idealwert-Validierung
//
// Spec: docs/specs/modules/issue_718_compare_editor_slice4_validierung.md
//
// RED-Phase: Alle Tests schlagen fehl, weil:
//   a) validateIdealRanges() nicht in compareMetricDefs.ts exportiert wird
//   b) doneTabs() kennt idealsValid noch nicht → gibt idealwerte als done zurück
//      obwohl idealsValid=false gesetzt ist
//   c) CompareWizardState hat keinen canAdvanceStep3-Getter → undefined statt boolean
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/issue_718_idealwert_validation.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

// ── Import 1: validateIdealRanges (neu — existiert noch nicht) ───────────────
// RED: Export existiert nicht → TypeError beim Aufruf
import { validateIdealRanges } from './compareMetricDefs.ts';

// ── Import 2: doneTabs (idealsValid-Erweiterung) ─────────────────────────────
import { doneTabs } from './compareEditorLogic.ts';

// CompareWizardState verwendet Svelte-Runes ($state/$derived) — nicht in node:test
// lauffähig. canAdvanceStep3-Verhalten wird via E2E (issue-718-idealwert-validation.spec.ts)
// und durch die validateIdealRanges-Tests indirekt abgedeckt.

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

// ─────────────────────────────────────────────────────────────────────────────
// AC-3: doneTabs() mit idealsValid=false → idealwerte NICHT done
// ─────────────────────────────────────────────────────────────────────────────
describe('AC-3: doneTabs() — idealsValid=false blockt done-Status', () => {
	const base = {
		name: 'Skitouren Hochkönig',
		pickedCount: 3,
		idealsVisited: true,
		layoutVisited: true,
		versandVisited: true
	};

	test('idealsValid=false → idealwerte NICHT in doneTabs', () => {
		// RED: doneTabs() ignoriert idealsValid noch → gibt idealwerte trotzdem zurück
		const done = doneTabs({ ...base, idealsValid: false });
		assert.ok(
			!done.has('idealwerte'),
			'idealwerte darf nicht als done gelten wenn idealsValid=false'
		);
	});

	test('idealsValid=true → idealwerte in doneTabs wie gehabt', () => {
		const done = doneTabs({ ...base, idealsValid: true });
		assert.ok(done.has('idealwerte'), 'idealwerte muss done sein wenn idealsValid=true');
	});
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-5: doneTabs() rückwärtskompatibel — idealsValid=undefined → weiterhin done
// ─────────────────────────────────────────────────────────────────────────────
describe('AC-5: doneTabs() — Rückwärtskompatibilität (undefined = valid)', () => {
	test('idealsValid nicht übergeben (undefined) → idealwerte weiterhin done', () => {
		// Bestehende Tests übergeben idealsValid nicht — dürfen nicht brechen
		const done = doneTabs({
			name: 'X',
			pickedCount: 2,
			idealsVisited: true,
			layoutVisited: false
		});
		assert.ok(
			done.has('idealwerte'),
			'ohne idealsValid muss idealwerte weiterhin als done gelten'
		);
	});
});

// canAdvanceStep3 / canAdvanceCurrent-Getter: via E2E geprüft
// (compare-editor-idealwert-validation.spec.ts AC-2)
// Begründung: CompareWizardState nutzt Svelte-Runes ($state/$derived) —
// diese sind außerhalb des Svelte-Kompilierungsschritts nicht ausführbar.
