// TDD RED: Issue #408 — Locations-Seite: NewLocationWizard verdrahten
//
// Spec: docs/specs/modules/issue_408_location_wizard.md
//
// Source-Inspection-Tests: lesen echte .svelte-Datei und pruefen, dass
// NewLocationWizard korrekt fuer den Create-Pfad verdrahtet ist.
//
// RED-Erwartung (vor Implementation):
//   - +page.svelte importiert NewLocationWizard nicht → AC-1 FAIL
//   - Create-Dialog nutzt noch LocationForm statt NewLocationWizard → AC-1 FAIL
//   - handleNewLocationSave existiert nicht → AC-2 FAIL
//   - groups={[]} im Wizard-Aufruf fehlt → AC-4 FAIL
//   (AC-3 Edit-Pfad bleibt bestehen, AC-5 via svelte-check)
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

// ── AC-1: NewLocationWizard importiert und im Create-Dialog verwendet ──────

test('AC-1: +page.svelte importiert NewLocationWizard', () => {
	const src = readFileSync(LOCATIONS_PAGE, 'utf-8');
	assert.match(
		src,
		/import\s+NewLocationWizard\s+from\s+['"][^'"]*compare\/NewLocationWizard[^'"]*['"]/,
		'+page.svelte muss NewLocationWizard aus compare/NewLocationWizard.svelte importieren'
	);
});

test('AC-1: Create-Dialog rendert <NewLocationWizard statt nur <LocationForm', () => {
	const src = readFileSync(LOCATIONS_PAGE, 'utf-8');
	assert.match(
		src,
		/<NewLocationWizard/,
		'+page.svelte muss <NewLocationWizard> im Create-Dialog enthalten'
	);
});

test('AC-1: <NewLocationWizard> ist an dialogMode === "create" gekoppelt', () => {
	const src = readFileSync(LOCATIONS_PAGE, 'utf-8');
	// Create-Block muss NewLocationWizard enthalten — pruefen dass create+NewLocationWizard zusammen vorkommen
	const createBlock =
		src.match(/dialogMode\s*===\s*['"]create['"][\s\S]{0,600}?<NewLocationWizard/)?.[0] ??
		src.match(/<NewLocationWizard[\s\S]{0,600}?dialogMode\s*===\s*['"]create['"]/)?.[0] ??
		'';
	assert.ok(
		createBlock.length > 0,
		'<NewLocationWizard> muss im dialogMode === "create" Block verwendet werden'
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
	// Die Funktion handleNewLocationSave extrahieren und auf api.post pruefen
	const fnMatch = src.match(
		/function\s+handleNewLocationSave\s*\([^)]*\)\s*\{([\s\S]*?)(?=\n\t*function\s|\n\t*async\s+function\s|\n<\/script>)/
	);
	const fnBody = fnMatch?.[1] ?? '';
	assert.doesNotMatch(
		fnBody,
		/api\.post/,
		'handleNewLocationSave darf keinen api.post-Call machen (Wizard speichert intern)'
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
	// LocationForm muss nach wie vor vorkommen (Edit-Modus)
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

// ── AC-4: groups={[]} an NewLocationWizard ────────────────────────────────

test('AC-4: NewLocationWizard erhaelt groups={[]} (keine Gruppen-Daten auf /locations)', () => {
	const src = readFileSync(LOCATIONS_PAGE, 'utf-8');
	// Suche nach groups={[]} oder groups=\{[]\} in der Naehe von NewLocationWizard
	const wizardBlock = src.match(/<NewLocationWizard[\s\S]{0,400}?\/>/)?.[0] ?? '';
	assert.ok(wizardBlock.length > 0, '<NewLocationWizard ... /> Block nicht gefunden');
	assert.match(
		wizardBlock,
		/groups=\{?\[\]/,
		'NewLocationWizard muss groups={[]} erhalten (Locations-Seite hat keine Gruppen)'
	);
});
