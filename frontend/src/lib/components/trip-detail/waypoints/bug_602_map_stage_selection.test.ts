// TDD RED — Bug #602: Karte zeigt immer Etappe 1 egal welche Etappe ausgewählt ist
//
// Spec: docs/specs/modules/bug_602_map_stage_selection.md
// Workflow: bug-602-map-stage-selection (Phase 5 TDD RED)
//
// Root Cause: $effect in MapCanvas.svelte liest `stage` nur async → kein reaktiver
// Dependency-Track → Karte re-rendert bei Stage-Wechsel nicht.
// Fix: {#key activeStageId} in WaypointsPanel.svelte um MapCanvas wrappen.
//
// Diese Source-Inspection-Tests SCHEITERN vor dem Fix (RED), bestehen danach (GREEN).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-detail/waypoints/bug_602_map_stage_selection.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const ROOT = fileURLToPath(new URL('../../../../..', import.meta.url)); // -> frontend root
const WAYPOINTS_PANEL = join(ROOT, 'src/lib/components/trip-detail/WaypointsPanel.svelte');

function readSrc(): string {
	return readFileSync(WAYPOINTS_PANEL, 'utf-8');
}

// ---------------------------------------------------------------------------
// AC-1 + AC-2: WaypointsPanel muss {#key activeStageId} um MapCanvas haben.
// Ohne diesen Block re-rendert die Karte nicht wenn activeStageId sich ändert.
// ---------------------------------------------------------------------------

test('AC-1/2: WaypointsPanel enthält {#key activeStageId}-Block', () => {
	const src = readSrc();
	assert.ok(
		src.includes('{#key activeStageId}'),
		'WaypointsPanel.svelte muss {#key activeStageId} enthalten, damit die Karte bei Stage-Wechsel neu gerendert wird'
	);
});

test('AC-1/2: {#key activeStageId} steht VOR <MapCanvas', () => {
	const src = readSrc();
	const keyIdx = src.indexOf('{#key activeStageId}');
	const mapIdx = src.indexOf('<MapCanvas');
	assert.ok(
		keyIdx !== -1,
		'{#key activeStageId} muss in WaypointsPanel.svelte vorhanden sein'
	);
	assert.ok(
		mapIdx !== -1,
		'<MapCanvas muss in WaypointsPanel.svelte vorhanden sein'
	);
	assert.ok(
		keyIdx < mapIdx,
		`{#key activeStageId} (pos ${keyIdx}) muss VOR <MapCanvas (pos ${mapIdx}) stehen`
	);
});

test('AC-1/2: {/key}-Schlusstag folgt nach <MapCanvas', () => {
	const src = readSrc();
	const mapIdx = src.indexOf('<MapCanvas');
	const endKeyIdx = src.indexOf('{/key}', mapIdx);
	assert.ok(
		mapIdx !== -1,
		'<MapCanvas muss in WaypointsPanel.svelte vorhanden sein'
	);
	assert.ok(
		endKeyIdx !== -1,
		'{/key} muss nach <MapCanvas folgen — der Key-Block muss korrekt geschlossen sein'
	);
});

// ---------------------------------------------------------------------------
// AC-3: MapCanvas muss Fallback für leere Stage haben (kein Absturz).
// Dieser Test ist bereits GREEN — er schützt gegen Regression.
// ---------------------------------------------------------------------------

test('AC-3: MapCanvas enthält Europa-Fallback für leere Waypoint-Liste', () => {
	const mapCanvas = readFileSync(
		join(ROOT, 'src/lib/components/trip-detail/waypoints/MapCanvas.svelte'),
		'utf-8'
	);
	assert.match(
		mapCanvas,
		/setView\(\[47/,
		'MapCanvas.svelte muss setView mit Europa-Koordinaten als Fallback für leere Stage enthalten — kein Absturz bei 0 Wegpunkten'
	);
});
