// TDD RED: Issue #344 — Pure-Logik der Wetter-Profile-Karte auf /account
//
// Spec: docs/specs/modules/issue_344_wetter_profile_account.md
//
// `presetCardHelpers.ts` existiert in der RED-Phase noch NICHT → der Import wirft
// einen Modul-Resolve-Fehler (ERR_MODULE_NOT_FOUND) und alle Tests scheitern.
//
// Architektur: Pure-Funktionen liegen in `.ts` (hier testbar via node:test),
// die Svelte-Karte in `+page.svelte` ist nur ein duenner Wrapper, der diese
// Funktionen verdrahtet (Repo-Konvention: kein Svelte-Compiler im Test-Setup).
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/utils/presetCardHelpers.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
	metricCountLabel,
	showDefaultBadge,
	isValidRename,
	applyRename,
	removePreset,
	isEmpty,
} from './presetCardHelpers.ts';
import type { MetricPreset } from '../types.ts';

// =========================================================================
// Helpers
// =========================================================================

function preset(over: Partial<MetricPreset> = {}): MetricPreset {
	return {
		id: 'p-1',
		name: 'Mein Profil',
		is_default: false,
		metrics: [],
		created_at: '2026-05-24T00:00:00Z',
		...over,
	};
}

// =========================================================================
// AC-1: Metrik-Anzahl-Label
// =========================================================================

test('AC-1: metricCountLabel — 3 Metriken → "3 Metriken"', () => {
	const p = preset({
		metrics: [
			{ metric_id: 'temperature', enabled: true, use_friendly_format: false },
			{ metric_id: 'wind', enabled: true, use_friendly_format: false },
			{ metric_id: 'precipitation', enabled: true, use_friendly_format: false },
		],
	});
	assert.equal(metricCountLabel(p), '3 Metriken');
});

test('AC-1: metricCountLabel — leere Liste → "0 Metriken"', () => {
	assert.equal(metricCountLabel(preset({ metrics: [] })), '0 Metriken');
});

test('AC-1: metricCountLabel — fehlende metrics → "0 Metriken" (kein Crash)', () => {
	// Backend-Compat: aeltere Presets koennen metrics undefined liefern.
	const p = preset();
	// @ts-expect-error absichtlich metrics entfernen fuer Robustheits-Check
	delete p.metrics;
	assert.equal(metricCountLabel(p), '0 Metriken');
});

// =========================================================================
// AC-2: Default-Badge nur bei is_default === true
// =========================================================================

test('AC-2: showDefaultBadge — is_default true → true', () => {
	assert.equal(showDefaultBadge(preset({ is_default: true })), true);
});

test('AC-2: showDefaultBadge — is_default false → false', () => {
	assert.equal(showDefaultBadge(preset({ is_default: false })), false);
});

// =========================================================================
// AC-3 / AC-4: Rename-Validierung (leerer Name blockt PATCH)
// =========================================================================

test('AC-3: isValidRename — nicht-leerer Name → true', () => {
	assert.equal(isValidRename('Skitour Hochwinter'), true);
});

test('AC-4: isValidRename — leerer String → false', () => {
	assert.equal(isValidRename(''), false);
});

test('AC-4: isValidRename — nur Whitespace → false', () => {
	assert.equal(isValidRename('   '), false);
});

// =========================================================================
// AC-3: applyRename — ersetzt genau das passende Preset (Reaktivitaet ohne Reload)
// =========================================================================

test('AC-3: applyRename — ersetzt nur das passende Preset, Rest bleibt', () => {
	const a = preset({ id: 'p-a', name: 'A' });
	const b = preset({ id: 'p-b', name: 'B' });
	const updated = preset({ id: 'p-b', name: 'B-neu' });
	const result = applyRename([a, b], updated);
	assert.deepEqual(result.map((p) => p.name), ['A', 'B-neu']);
});

test('AC-3: applyRename — liefert ein neues Array (Immutabilitaet)', () => {
	const list = [preset({ id: 'p-a' })];
	const result = applyRename(list, preset({ id: 'p-a', name: 'X' }));
	assert.notEqual(result, list);
});

// =========================================================================
// AC-5: removePreset — entfernt genau das passende Preset
// =========================================================================

test('AC-5: removePreset — entfernt nur das passende Preset', () => {
	const a = preset({ id: 'p-a', name: 'A' });
	const b = preset({ id: 'p-b', name: 'B' });
	const result = removePreset([a, b], 'p-a');
	assert.deepEqual(result.map((p) => p.id), ['p-b']);
});

test('AC-5: removePreset — unbekannte ID laesst Liste unveraendert', () => {
	const a = preset({ id: 'p-a' });
	const result = removePreset([a], 'p-x');
	assert.deepEqual(result.map((p) => p.id), ['p-a']);
});

// =========================================================================
// AC-6: Leerer Zustand
// =========================================================================

test('AC-6: isEmpty — leere Liste → true', () => {
	assert.equal(isEmpty([]), true);
});

test('AC-6: isEmpty — mindestens ein Preset → false', () => {
	assert.equal(isEmpty([preset()]), false);
});
