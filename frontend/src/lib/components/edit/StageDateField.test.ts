// TDD RED: Issue #498 — Etappen-Datum nachträglich bearbeiten (Komponente).
//
// Spec: docs/design-requests/stage_date_edit.md
//
// Source-Inspection-Tests: liest die echte .svelte-Quelldatei und prüft Marker.
// Kein Browser, keine Mocks.
//
// RED-Erwartung: edit/StageDateField.svelte existiert noch nicht → readFileSync wirft.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/edit/StageDateField.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

// Test liegt in src/lib/components/edit/ → '../../../' = frontend/src/
const SRC = fileURLToPath(new URL('../../../', import.meta.url));

function read(rel: string): string {
	return readFileSync(join(SRC, rel), 'utf8');
}

const COMPONENT = 'lib/components/edit/StageDateField.svelte';

// ---------------------------------------------------------------------------
// AC-1: Komponente hat data-testid="stage-date-field"
// ---------------------------------------------------------------------------

test('AC-1: StageDateField hat data-testid="stage-date-field"', () => {
	const src = read(COMPONENT);
	assert.ok(
		src.includes('data-testid="stage-date-field"'),
		'StageDateField braucht data-testid="stage-date-field" für E2E-Locator'
	);
});

// ---------------------------------------------------------------------------
// AC-2: Wochentag-Map enthält alle 7 Kürzel in Sonntag-zuerst-Reihenfolge
// (entspricht Date.prototype.getDay() = 0..6 → So..Sa).
// ---------------------------------------------------------------------------

test('AC-2: StageDateField hat Wochentag-Array So..Sa für getDay()-Index', () => {
	const src = read(COMPONENT);
	// Erlaubt: einzeilig oder mit Whitespace; einfach auf Kürzel-Reihenfolge prüfen.
	const normalized = src.replace(/\s+/g, '');
	assert.ok(
		normalized.includes("'So','Mo','Di','Mi','Do','Fr','Sa'") ||
			normalized.includes('"So","Mo","Di","Mi","Do","Fr","Sa"'),
		'Wochentag-Map muss in Sonntag-zuerst-Reihenfolge sein (Date.getDay()-Index)'
	);
});

// ---------------------------------------------------------------------------
// AC-3: Native <input type="date"> wird verwendet (keine Custom-Date-Picker-Lib)
// ---------------------------------------------------------------------------

test('AC-3: StageDateField nutzt native <input type="date">', () => {
	const src = read(COMPONENT);
	assert.ok(
		src.includes('type="date"'),
		'StageDateField muss <input type="date"> verwenden — keine Custom-Picker-Lib'
	);
});

// ---------------------------------------------------------------------------
// AC-4: Svelte-5-Syntax — KEIN export let, KEIN $:, KEIN on:change
// ---------------------------------------------------------------------------

test('AC-4: StageDateField nutzt Svelte-5 ($props/$derived), nicht Legacy', () => {
	const src = read(COMPONENT);
	assert.ok(!/\bexport\s+let\b/.test(src), 'KEIN "export let" (Svelte-5 nutzt $props())');
	assert.ok(!/^\s*\$:/m.test(src), 'KEIN "$:" (Svelte-5 nutzt $derived)');
	assert.ok(!/\bon:change\b/.test(src), 'KEIN "on:change" (Svelte-5 nutzt onchange-Prop)');
	assert.ok(src.includes('$props()'), 'Muss $props() verwenden');
	assert.ok(src.includes('$derived'), 'Muss $derived für Wochentag-Ableitung verwenden');
});

// ---------------------------------------------------------------------------
// AC-5: Label-Markup unterstützt "Tourstart" wenn isFirst=true
// ---------------------------------------------------------------------------

test('AC-5: StageDateField rendert "Tourstart" bedingt via isFirst', () => {
	const src = read(COMPONENT);
	assert.ok(src.includes('Tourstart'), 'Label muss "Tourstart"-Markup enthalten');
	assert.ok(
		src.includes('isFirst'),
		'isFirst-Prop muss im Template referenziert werden (z.B. {#if isFirst})'
	);
});

// ---------------------------------------------------------------------------
// AC-6: onchange-Prop existiert und gibt neuen Wert (string) zurück
// ---------------------------------------------------------------------------

test('AC-6: StageDateField hat onchange-Prop mit string-Argument', () => {
	const src = read(COMPONENT);
	assert.ok(
		/onchange\?:\s*\((?:newValue|value|d|date|v)[^)]*:\s*string\)\s*=>/.test(src),
		'onchange muss als (newValue: string) => void typisiert sein'
	);
});

// ---------------------------------------------------------------------------
// AC-7: Tokens werden für Styling verwendet (var(--g-rule), var(--g-accent-*))
// ---------------------------------------------------------------------------

test('AC-7: StageDateField nutzt Projekt-Tokens (var(--g-*))', () => {
	const src = read(COMPONENT);
	assert.ok(src.includes('var(--g-rule)'), 'Border nutzt --g-rule');
	assert.ok(src.includes('var(--g-accent'), 'Wochentag-Chip nutzt --g-accent-*');
	assert.ok(src.includes('var(--g-font-data)'), 'Mono/Data-Font für Datum');
});

// ---------------------------------------------------------------------------
// AC-8: EditStagesPanelNew importiert StageDateField und ruft handleDateChange
// ---------------------------------------------------------------------------

test('AC-8: EditStagesPanelNew bindet StageDateField + Cascade-Strip ein', () => {
	const src = read('lib/components/edit/EditStagesPanelNew.svelte');
	assert.ok(
		src.includes("from './StageDateField.svelte'") ||
			src.includes('from "./StageDateField.svelte"'),
		'EditStagesPanelNew muss StageDateField importieren'
	);
	assert.ok(
		src.includes('StageDateField'),
		'StageDateField muss im Template verwendet werden'
	);
	assert.ok(src.includes('handleDateChange'), 'handleDateChange-Handler muss existieren');
	assert.ok(
		src.includes('cascade-strip') || src.includes('data-testid="cascade-strip"'),
		'Cascade-Strip mit data-testid="cascade-strip" muss vorhanden sein'
	);
	assert.ok(
		src.includes('dateOverridden'),
		'dateOverridden:true muss bei manuellem Date-Edit gesetzt werden'
	);
});

// ---------------------------------------------------------------------------
// AC-9: PauseStageView verwendet StageDateField statt read-only-Datum
// ---------------------------------------------------------------------------

test('AC-9: PauseStageView ersetzt read-only-Datum durch StageDateField', () => {
	const src = read('lib/components/trip-detail/waypoints/PauseStageView.svelte');
	assert.ok(src.includes('StageDateField'), 'PauseStageView muss StageDateField nutzen');
	assert.ok(
		src.includes('onDateChange'),
		'PauseStageView braucht onDateChange-Prop zum Hochbubble-Pattern'
	);
	// Das read-only <p>{stage.date}</p> darf nicht mehr existieren.
	assert.ok(
		!/<p[^>]*>\s*\{stage\.date\}\s*<\/p>/.test(src),
		'Read-only <p>{stage.date}</p> muss durch StageDateField ersetzt sein'
	);
});

// ---------------------------------------------------------------------------
// AC-10: EditStagesPanelNew reicht onDateChange an PauseStageView durch
// ---------------------------------------------------------------------------

test('AC-10: EditStagesPanelNew gibt onDateChange an PauseStageView weiter', () => {
	const src = read('lib/components/edit/EditStagesPanelNew.svelte');
	assert.ok(
		src.includes('onDateChange='),
		'PauseStageView muss onDateChange-Prop bekommen damit Pausen-Datum editierbar wird'
	);
});
