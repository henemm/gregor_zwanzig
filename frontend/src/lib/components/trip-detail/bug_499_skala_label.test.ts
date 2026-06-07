// TDD RED — Bug #499: Label "Skala" → "Einfach" in allen UI-Stellen.
// SPEC: docs/specs/modules/bug_499_skala_label.md (AC-1 bis AC-4)
//
// Diese Tests scheitern solange "Skala" noch in den Quelldateien steht.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-detail/bug_499_skala_label.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));

const ACTIVE_METRIC_ROW  = join(here, 'ActiveMetricRow.svelte');
const WEATHER_CONFIG_DLG = join(here, '..', 'WeatherConfigDialog.svelte');
const STEP3_WEATHER      = join(here, '..', 'trip-wizard', 'steps', 'Step3Weather.svelte');
const SAVE_PRESET_DLG    = join(here, 'SavePresetDialog.svelte');
const TABLE_PREVIEW      = join(here, 'TablePreview.svelte');

// --- AC-1: Toggle in ActiveMetricRow ---

test('AC-1: ActiveMetricRow zeigt Button-Label "Einfach" statt "Skala"', () => {
	const src = readFileSync(ACTIVE_METRIC_ROW, 'utf-8');
	assert.ok(
		src.includes('>Einfach<'),
		'AC-1 RED: Button-Label muss ">Einfach<" enthalten'
	);
});

test('AC-1: ActiveMetricRow enthält kein Button-Label "Skala" mehr', () => {
	const src = readFileSync(ACTIVE_METRIC_ROW, 'utf-8');
	assert.ok(
		!src.includes('>Skala<'),
		'AC-1 RED: Button-Label ">Skala<" muss entfernt sein'
	);
});

test('AC-1: ActiveMetricRow aria-label verwendet "Einfach" statt "Skala"', () => {
	const src = readFileSync(ACTIVE_METRIC_ROW, 'utf-8');
	assert.ok(
		src.includes('Roh oder Einfach'),
		'AC-1 RED: aria-label muss "Roh oder Einfach" enthalten'
	);
});

// --- AC-2: Issue #629 — scale/symbol-Dropdown durch Roh/Einfach-Toggle ersetzt ---
// Das ursprüngliche #499-Label "Skala"→"Einfach" betraf das 4-Wert-Dropdown.
// #629 entfernt scale/symbol komplett aus der UI (Boolean-Toggle Roh/Einfach),
// damit ist die #499-Intention ("kein 'Skala'") verschärft erfüllt: es gibt gar
// keine scale/symbol-Option mehr.

test('AC-2 (#629): WeatherConfigDialog bietet kein scale/symbol-Label mehr', () => {
	const src = readFileSync(WEATHER_CONFIG_DLG, 'utf-8');
	assert.ok(!src.includes("scale: '"), 'WeatherConfigDialog darf kein scale-Label mehr haben');
	assert.ok(!src.includes("symbol: '"), 'WeatherConfigDialog darf kein symbol-Label mehr haben');
	assert.ok(!src.includes("scale: 'Skala'"), "WeatherConfigDialog darf scale: 'Skala' nicht enthalten");
});

test('AC-2 (#629): WeatherConfigDialog bietet Roh/Einfach-Toggle', () => {
	const src = readFileSync(WEATHER_CONFIG_DLG, 'utf-8');
	assert.ok(src.includes('Einfach'), 'WeatherConfigDialog muss Toggle-Label "Einfach" enthalten');
	assert.ok(src.includes('Roh'), 'WeatherConfigDialog muss Toggle-Label "Roh" enthalten');
});

test('AC-2 (#629): Step3Weather bietet kein scale/symbol-Label mehr', () => {
	const src = readFileSync(STEP3_WEATHER, 'utf-8');
	assert.ok(!src.includes("scale: '"), 'Step3Weather darf kein scale-Label mehr haben');
	assert.ok(!src.includes("symbol: '"), 'Step3Weather darf kein symbol-Label mehr haben');
	assert.ok(!src.includes("scale: 'Skala'"), "Step3Weather darf scale: 'Skala' nicht enthalten");
});

test('AC-2 (#629): Step3Weather bietet Roh/Einfach-Toggle', () => {
	const src = readFileSync(STEP3_WEATHER, 'utf-8');
	assert.ok(src.includes('Einfach'), 'Step3Weather muss Toggle-Label "Einfach" enthalten');
	assert.ok(src.includes('Roh'), 'Step3Weather muss Toggle-Label "Roh" enthalten');
});

// --- AC-3: Preset-Zusammenfassung SavePresetDialog ---

test('AC-3: SavePresetDialog zeigt "als Einfach" statt "als Skala"', () => {
	const src = readFileSync(SAVE_PRESET_DLG, 'utf-8');
	assert.ok(
		src.includes('als Einfach'),
		'AC-3 RED: SavePresetDialog muss "als Einfach" enthalten'
	);
});

test('AC-3: SavePresetDialog enthält kein "als Skala" mehr', () => {
	const src = readFileSync(SAVE_PRESET_DLG, 'utf-8');
	assert.ok(
		!src.includes('als Skala'),
		'AC-3 RED: SavePresetDialog darf "als Skala" nicht mehr enthalten'
	);
});

// --- AC-4: Tabellen-Vorschau TablePreview ---

test('AC-4: TablePreview zeigt Suffix "·einfach" statt "·skala"', () => {
	const src = readFileSync(TABLE_PREVIEW, 'utf-8');
	assert.ok(
		src.includes('·einfach'),
		'AC-4 RED: TablePreview muss "·einfach" enthalten'
	);
});

test('AC-4: TablePreview enthält kein "·skala" mehr', () => {
	const src = readFileSync(TABLE_PREVIEW, 'utf-8');
	assert.ok(
		!src.includes('·skala'),
		'AC-4 RED: TablePreview darf "·skala" nicht mehr enthalten'
	);
});
