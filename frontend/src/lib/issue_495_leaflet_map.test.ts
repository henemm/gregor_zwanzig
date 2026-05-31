// TDD RED: Issue #495 — Leaflet-Karte im Wegpunkt-Editor
//
// Spec: docs/specs/modules/issue_495_leaflet_map.md
// Workflow: Phase 5 (TDD RED) — Tests MÜSSEN FEHLSCHLAGEN bis Phase 6.
//
// Source-Inspection-Tests: keine Mocks, keine echten Browser-Instanzen.
// Liest echte Quelldateien und prüft strukturelle Anforderungen.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/issue_495_leaflet_map.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const ROOT = fileURLToPath(new URL('../../..', import.meta.url)); // -> worktree root
const FRONTEND = join(ROOT, 'frontend');
const MAP_CANVAS = join(FRONTEND, 'src/lib/components/trip-detail/waypoints/MapCanvas.svelte');
const WAYPOINT_EDITOR = join(FRONTEND, 'src/lib/utils/waypointEditor.ts');
const PACKAGE_JSON = join(FRONTEND, 'package.json');

// =============================================================================
// AC-1 / AC-2: Leaflet-Paket im Frontend vorhanden
// =============================================================================

test('AC-1: leaflet ist in package.json als Dependency eingetragen', () => {
	const pkg = JSON.parse(readFileSync(PACKAGE_JSON, 'utf-8'));
	const allDeps = { ...pkg.dependencies, ...pkg.devDependencies };
	assert.ok(
		'leaflet' in allDeps,
		'leaflet muss in dependencies oder devDependencies stehen'
	);
});

test('AC-1: @types/leaflet ist in package.json als devDependency eingetragen', () => {
	const pkg = JSON.parse(readFileSync(PACKAGE_JSON, 'utf-8'));
	assert.ok(
		'@types/leaflet' in (pkg.devDependencies ?? {}),
		'@types/leaflet muss in devDependencies stehen'
	);
});

// =============================================================================
// AC-1: MapCanvas.svelte importiert Leaflet statt buildMapPositions
// =============================================================================

test('AC-1: MapCanvas.svelte importiert leaflet', () => {
	const src = readFileSync(MAP_CANVAS, 'utf-8');
	assert.match(
		src,
		/from ['"]leaflet['"]/,
		'MapCanvas.svelte muss leaflet importieren'
	);
});

test('AC-1: MapCanvas.svelte enthält OpenTopoMap-Tile-URL', () => {
	const src = readFileSync(MAP_CANVAS, 'utf-8');
	assert.match(
		src,
		/opentopomap\.org/,
		'MapCanvas.svelte muss die OpenTopoMap-Tile-URL enthalten'
	);
});

test('AC-1: MapCanvas.svelte importiert NICHT mehr buildMapPositions', () => {
	const src = readFileSync(MAP_CANVAS, 'utf-8');
	assert.doesNotMatch(
		src,
		/buildMapPositions/,
		'MapCanvas.svelte darf buildMapPositions nicht mehr referenzieren'
	);
});

test('AC-1: MapCanvas.svelte importiert NICHT mehr TopoBg', () => {
	const src = readFileSync(MAP_CANVAS, 'utf-8');
	assert.doesNotMatch(
		src,
		/TopoBg/,
		'MapCanvas.svelte darf TopoBg nicht mehr importieren — SVG-Attrappe ist entfernt'
	);
});

// =============================================================================
// AC-2: fitBounds vorhanden
// =============================================================================

test('AC-2: MapCanvas.svelte enthält fitBounds für Auto-Zoom', () => {
	const src = readFileSync(MAP_CANVAS, 'utf-8');
	assert.match(
		src,
		/fitBounds/,
		'MapCanvas.svelte muss map.fitBounds() aufrufen'
	);
});

// =============================================================================
// AC-3: Marker-Click-Handler vorhanden (onWaypointActivate)
// =============================================================================

test('AC-3: MapCanvas.svelte enthält Marker-Click-Handler für onWaypointActivate', () => {
	const src = readFileSync(MAP_CANVAS, 'utf-8');
	assert.match(
		src,
		/onWaypointActivate/,
		'MapCanvas.svelte muss onWaypointActivate in einem Marker-Click-Handler aufrufen'
	);
	assert.match(
		src,
		/marker\.on\(['"]click['"]/,
		'MapCanvas.svelte muss marker.on("click", ...) registrieren'
	);
});

// =============================================================================
// AC-5: Europa-Fallback bei leerer Stage
// =============================================================================

test('AC-5: MapCanvas.svelte enthält Europa-Fallback für leere Stage', () => {
	const src = readFileSync(MAP_CANVAS, 'utf-8');
	assert.match(
		src,
		/setView\(\[47/,
		'MapCanvas.svelte muss setView mit Europa-Koordinaten als Fallback enthalten'
	);
});

// =============================================================================
// AC-4: Tile-Attribution (Lizenzpflicht OpenTopoMap CC-BY-SA)
// =============================================================================

test('AC-4: MapCanvas.svelte enthält OpenStreetMap-Attribution', () => {
	const src = readFileSync(MAP_CANVAS, 'utf-8');
	assert.match(
		src,
		/OpenStreetMap/,
		'Tile-Attribution muss "OpenStreetMap" enthalten (CC-Lizenzpflicht)'
	);
});

// =============================================================================
// AC-6: Cleanup via $effect (kein Memory Leak)
// =============================================================================

test('AC-6: MapCanvas.svelte enthält map.remove() für Cleanup', () => {
	const src = readFileSync(MAP_CANVAS, 'utf-8');
	assert.match(
		src,
		/map[?]?\.remove\(\)/,
		'MapCanvas.svelte muss map.remove() im $effect-Cleanup aufrufen'
	);
});

// =============================================================================
// AC-7: buildMapPositions und MapPosition aus waypointEditor.ts entfernt
// =============================================================================

test('AC-7: buildMapPositions ist aus waypointEditor.ts entfernt', () => {
	const src = readFileSync(WAYPOINT_EDITOR, 'utf-8');
	assert.doesNotMatch(
		src,
		/export function buildMapPositions/,
		'buildMapPositions muss aus waypointEditor.ts entfernt sein'
	);
});

test('AC-7: MapPosition-Interface ist aus waypointEditor.ts entfernt', () => {
	const src = readFileSync(WAYPOINT_EDITOR, 'utf-8');
	assert.doesNotMatch(
		src,
		/export interface MapPosition/,
		'MapPosition-Interface muss aus waypointEditor.ts entfernt sein'
	);
});

test('AC-7: kein buildMapPositions-Verweis im Produktionscode', () => {
	// Test-Dateien (*.test.ts) sind ausgeschlossen — sie enthalten den Namen
	// notwendigerweise als String, um genau diese Abwesenheit zu prüfen.
	const result = execSync(
		`grep -r "buildMapPositions" "${join(FRONTEND, 'src')}" --include="*.ts" --include="*.svelte" --exclude="*.test.ts" -l 2>/dev/null || true`,
		{ encoding: 'utf-8' }
	).trim();
	assert.equal(
		result,
		'',
		`buildMapPositions wird noch im Produktionscode referenziert in:\n${result}`
	);
});
