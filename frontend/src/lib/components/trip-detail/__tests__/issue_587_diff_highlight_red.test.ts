// TDD RED: Issue #587 — AC-2 Diff-Aufleuchten (diffHighlight)
//
// Spec: docs/specs/modules/issue_587_weather_tab_v2.md
// ABSICHTLICH ROT bis diffHighlight in metricsEditor.ts existiert.
//
// Ausführen (aus frontend/):
//   node --experimental-strip-types --test \
//     src/lib/components/trip-detail/__tests__/issue_587_diff_highlight_red.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { diffHighlight } from '../metricsEditor.ts';

// Helfer: minimal gültiger WeatherSnapshot
function snap(
	columns: string[],
	mode: Record<string, 'raw' | 'indicator'> = {},
	presetId = 'default',
) {
	return { columns, mode, presetId };
}

// ============================================================================
// Regel 1: preset gewechselt + Spaltenmenge komplett anders → kind:'preset'
// ============================================================================

test('#587 AC-2: preset-Wechsel mit neuer Spaltenmenge → { id: null, kind: "preset" }', () => {
	const prev = snap(['temperature', 'wind'], {}, 'outdoor');
	const next = snap(['humidity', 'pressure'], {}, 'alpine');
	const result = diffHighlight(prev, next);
	assert.deepEqual(result, { id: null, kind: 'preset' });
});

// ============================================================================
// Regel 2: genau eine Spalte hinzugefügt → kind:'added'
// ============================================================================

test('#587 AC-2: eine Spalte hinzugefügt → { id: <neue>, kind: "added" }', () => {
	const prev = snap(['temperature', 'wind']);
	const next = snap(['temperature', 'wind', 'humidity']);
	const result = diffHighlight(prev, next);
	assert.deepEqual(result, { id: 'humidity', kind: 'added' });
});

// ============================================================================
// Regel 3: genau eine Spalte entfernt → kind:'removed'
// ============================================================================

test('#587 AC-2: eine Spalte entfernt → { id: <entfernte>, kind: "removed" }', () => {
	const prev = snap(['temperature', 'wind', 'humidity']);
	const next = snap(['temperature', 'wind']);
	const result = diffHighlight(prev, next);
	assert.deepEqual(result, { id: 'humidity', kind: 'removed' });
});

// ============================================================================
// Regel 4: gleiche Menge, andere Reihenfolge → kind:'moved'
// ============================================================================

test('#587 AC-2: Reihenfolge geändert → { id: <erste verschobene>, kind: "moved" }', () => {
	const prev = snap(['temperature', 'wind', 'humidity']);
	const next = snap(['wind', 'temperature', 'humidity']);
	const result = diffHighlight(prev, next);
	// 'temperature' war an Index 0, ist jetzt an Index 1 — erste verschobene id
	assert.ok(result !== null, 'Ergebnis darf nicht null sein');
	assert.equal(result!.kind, 'moved');
	assert.ok(typeof result!.id === 'string', 'id muss ein String sein');
});

// ============================================================================
// Regel 5: gleiche Spalten/Reihenfolge, ein mode[id] unterscheidet sich → kind:'mode'
// ============================================================================

test('#587 AC-2: Modus geändert → { id: <betroffene>, kind: "mode" }', () => {
	const prev = snap(['temperature', 'wind'], { temperature: 'raw', wind: 'raw' });
	const next = snap(['temperature', 'wind'], { temperature: 'indicator', wind: 'raw' });
	const result = diffHighlight(prev, next);
	assert.deepEqual(result, { id: 'temperature', kind: 'mode' });
});

// ============================================================================
// Regel 6: keine Änderung → null
// ============================================================================

test('#587 AC-2: keine Änderung → null', () => {
	const prev = snap(['temperature', 'wind'], { temperature: 'raw' }, 'default');
	const next = snap(['temperature', 'wind'], { temperature: 'raw' }, 'default');
	const result = diffHighlight(prev, next);
	assert.equal(result, null);
});

// ============================================================================
// F001-Härtung: Duplikat-Input darf kein Phantom-„moved" liefern
// ============================================================================

test('#587 F001: Duplikat-columns → null (kein Phantom-moved)', () => {
	// Duplikat in beiden Snapshots — nach Dedup identische Menge + Reihenfolge.
	const prev = snap(['temperature', 'temperature', 'wind']);
	const next = snap(['temperature', 'temperature', 'wind']);
	const result = diffHighlight(prev, next);
	assert.equal(result, null, 'Duplikat-Input darf kein Phantom-moved liefern');
});
