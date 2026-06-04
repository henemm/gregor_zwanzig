// Issue #408 — Locations-Seite: NewLocationWizard verdrahten
// Aktualisiert durch Issue #588: NewLocationWizard → LocationNewModal ersetzt.
//
// Spec: docs/specs/modules/issue_408_location_wizard.md
//       docs/specs/modules/issue_588_location_new.md
//
// Source-Inspection-Tests: lesen echte .svelte-Datei und pruefen, dass
// LocationNewModal korrekt fuer den Create-Pfad verdrahtet ist.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/routes/locations/__tests__/issue_408_location_wizard.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const FRONTEND = fileURLToPath(new URL('../../../../', import.meta.url)); // -> frontend/

const LOCATIONS_PAGE = join(FRONTEND, 'src/routes/locations/+page.svelte');

// ── AC-1: LocationNewModal importiert und im Create-Pfad verwendet ──────────

test('AC-1: +page.svelte importiert LocationNewModal', () => {
	const src = readFileSync(LOCATIONS_PAGE, 'utf-8');
	assert.match(
		src,
		/import\s+LocationNewModal\s+from\s+['"][^'"]*compare\/LocationNewModal[^'"]*['"]/,
		'+page.svelte muss LocationNewModal aus compare/LocationNewModal.svelte importieren'
	);
});

test('AC-1: Create-Pfad rendert <LocationNewModal', () => {
	const src = readFileSync(LOCATIONS_PAGE, 'utf-8');
	assert.match(
		src,
		/<LocationNewModal/,
		'+page.svelte muss <LocationNewModal> im Create-Pfad enthalten'
	);
});

test('AC-1: <LocationNewModal> ist an dialogMode === "create" gekoppelt', () => {
	const src = readFileSync(LOCATIONS_PAGE, 'utf-8');
	const createBlock =
		src.match(/dialogMode\s*===\s*['"]create['"][\s\S]{0,600}?<LocationNewModal/)?.[0] ??
		src.match(/<LocationNewModal[\s\S]{0,600}?dialogMode\s*===\s*['"]create['"]/)?.[0] ??
		'';
	assert.ok(
		createBlock.length > 0,
		'<LocationNewModal> muss im dialogMode === "create" Block verwendet werden'
	);
});

// ── AC-2: handleNewLocationSave ohne zweiten API-Call ─────────────────────

test('AC-2: handleNewLocationSave Funktion existiert in +page.svelte', () => {
	const src = readFileSync(LOCATIONS_PAGE, 'utf-8');
	assert.match(
		src,
		/function\s+handleNewLocationSave\s*\(/,
		'+page.svelte muss Funktion handleNewLocationSave definieren'
	);
});

test('AC-2: handleNewLocationSave enthaelt keinen api.post-Call (kein doppelter POST)', () => {
	const src = readFileSync(LOCATIONS_PAGE, 'utf-8');
	const fnMatch = src.match(
		/function\s+handleNewLocationSave\s*\([^)]*\)\s*\{([\s\S]*?)(?=\n\t*function\s|\n\t*async\s+function\s|\n<\/script>)/
	);
	const fnBody = fnMatch?.[1] ?? '';
	assert.doesNotMatch(
		fnBody,
		/api\.post/,
		'handleNewLocationSave darf keinen api.post-Call machen (Modal speichert intern)'
	);
});

test('AC-2: handleNewLocationSave ruft refetchLocations() auf', () => {
	const src = readFileSync(LOCATIONS_PAGE, 'utf-8');
	const fnMatch = src.match(
		/function\s+handleNewLocationSave\s*\([^)]*\)\s*\{([\s\S]*?)(?=\n\t*function\s|\n\t*async\s+function\s|\n<\/script>)/
	);
	const fnBody = fnMatch?.[1] ?? '';
	assert.match(
		fnBody,
		/refetchLocations\s*\(\s*\)/,
		'handleNewLocationSave muss refetchLocations() aufrufen'
	);
});

// ── AC-3: Edit-Pfad weiterhin mit LocationForm ────────────────────────────

test('AC-3: LocationForm bleibt im Edit-Pfad erhalten', () => {
	const src = readFileSync(LOCATIONS_PAGE, 'utf-8');
	assert.match(
		src,
		/<LocationForm/,
		'+page.svelte muss weiterhin <LocationForm> fuer den Edit-Modus enthalten'
	);
});

test('AC-3: <LocationForm> ist an dialogMode === "edit" gekoppelt', () => {
	const src = readFileSync(LOCATIONS_PAGE, 'utf-8');
	const editBlock =
		src.match(/dialogMode\s*===\s*['"]edit['"][\s\S]{0,600}?<LocationForm/)?.[0] ??
		src.match(/<LocationForm[\s\S]{0,600}?dialogMode\s*===\s*['"]edit['"]/)?.[0] ??
		'';
	assert.ok(
		editBlock.length > 0,
		'<LocationForm> muss im dialogMode === "edit" Block verwendet werden (Edit-Pfad unveraendert)'
	);
});

// ── AC-4: LocationNewModal empfaengt onsave und oncancel ─────────────────

test('AC-4: LocationNewModal empfaengt onsave-Callback', () => {
	const src = readFileSync(LOCATIONS_PAGE, 'utf-8');
	const modalBlock = src.match(/<LocationNewModal[\s\S]{0,400}?\/>/)?.[0] ?? '';
	assert.ok(modalBlock.length > 0, '<LocationNewModal ... /> Block nicht gefunden');
	assert.match(
		modalBlock,
		/onsave=/,
		'LocationNewModal muss onsave-Prop erhalten'
	);
});
