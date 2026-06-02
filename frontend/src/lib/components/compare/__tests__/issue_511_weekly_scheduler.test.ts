// TDD RED — Issue #511: Weekly-Preset weekday-Picker im SavePresetDialog (AC-5).
//
// Spec: docs/specs/modules/issue_511_weekly_scheduler.md §5 + §6
//
// Source-Inspection-Tests (node:test, kein DOM-Rendering).
// Prüft:
//   - types.ts hat weekday-Feld im ComparePreset-Interface
//   - SavePresetDialog.svelte hat Weekday-Picker (7 Optionen) bei schedule='weekly'
//   - SavePresetDialog sendet weekday im POST-Body
//
// RED-Erwartung (vor Implementation):
//   - types.ts hat kein weekday-Feld in ComparePreset
//   - SavePresetDialog hat keinen Weekday-Picker
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_511_weekly_scheduler.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const TYPES       = resolve('src/lib/types.ts');
const SAVE_DIALOG = resolve('src/lib/components/compare/SavePresetDialog.svelte');

// ── §1 ComparePreset-Interface in types.ts — weekday-Feld ────────────────────

test('AC-5: types.ts hat weekday-Feld im ComparePreset-Interface', () => {
	const src = readFileSync(TYPES, 'utf-8');

	// ComparePreset-Interface muss existieren (Vorbedingung)
	assert.match(src, /interface ComparePreset/, 'ComparePreset-Interface muss in types.ts existieren');

	// weekday-Feld muss im Interface sein (RED: fehlt aktuell)
	const presetBlock = src.match(/interface ComparePreset\s*\{([^}]+)\}/s)?.[1] ?? '';
	assert.match(
		presetBlock,
		/weekday\??:\s*number/,
		'ComparePreset muss ein weekday-Feld (weekday?: number) enthalten — fehlt aktuell (RED)',
	);
});

// ── §2 SavePresetDialog — Weekday-Picker vorhanden ──────────────────────────

test('AC-5: SavePresetDialog hat weekday-State-Variable', () => {
	const src = readFileSync(SAVE_DIALOG, 'utf-8');

	// weekday-State muss deklariert sein
	assert.match(
		src,
		/let\s+weekday\s*[=:]/,
		'SavePresetDialog muss eine weekday-State-Variable haben — fehlt aktuell (RED)',
	);
});

test('AC-5: SavePresetDialog zeigt Weekday-Picker nur bei schedule=weekly', () => {
	const src = readFileSync(SAVE_DIALOG, 'utf-8');

	// Konditionaler Block für weekly muss vorhanden sein
	assert.match(
		src,
		/schedule\s*===?\s*['"]weekly['"]/,
		"SavePresetDialog muss einen konditionalen Block für schedule='weekly' haben",
	);

	// Weekday-Optionen (Montag..Sonntag) müssen vorhanden sein
	// Mindestens ein Wochentag als option-Element
	assert.match(
		src,
		/option.*value[=\s{].*[0-6]/,
		'SavePresetDialog muss Weekday-Optionen (0–6) als <option>-Elemente enthalten — fehlt aktuell (RED)',
	);
});

test('AC-5: SavePresetDialog übergibt weekday im POST-Body bei schedule=weekly', () => {
	const src = readFileSync(SAVE_DIALOG, 'utf-8');

	// handleSave / api.post muss weekday enthalten wenn schedule='weekly'
	// Entweder als bedingter Ausdruck oder immer im Body
	const hasWeekdayInPost = src.includes('weekday') && src.includes('api.post');
	assert.ok(
		hasWeekdayInPost,
		'SavePresetDialog muss weekday im POST-Body an /api/compare/presets übergeben — fehlt aktuell (RED)',
	);
});

// ── §3 SavePresetDialog — Default-Wert Freitag ──────────────────────────────

test('AC-5: SavePresetDialog hat Default-Wochentag 4 (Freitag)', () => {
	const src = readFileSync(SAVE_DIALOG, 'utf-8');

	// Default-Wert 4 für weekday-State
	assert.match(
		src,
		/weekday.*=.*4|4.*weekday/,
		'SavePresetDialog muss weekday-Default auf 4 (Freitag) setzen — fehlt aktuell (RED)',
	);
});
