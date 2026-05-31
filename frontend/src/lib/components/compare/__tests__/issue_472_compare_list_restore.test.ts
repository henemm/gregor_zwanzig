// TDD RED: Issue #472 — /compare Listenansicht wiederherstellen
//
// Spec: docs/specs/modules/issue_472_compare_list_restore.md
//
// Prüft, dass die /compare-Route auf die Design-konforme Listenansicht
// (ComparePreset-basiert) umgebaut wurde und das alte 3-Spalten-Live-Tool
// (LocationsRail, PresetHeader etc.) entfernt wurde.
//
// RED-Erwartung (vor Implementation):
//   - +page.svelte importiert noch LocationsRail → doesNotMatch FAIL
//   - +page.svelte hat kein Eyebrow/H1 → match FAIL
//   - CompareList.svelte nutzt noch Subscription → match FAIL
//   - CompareRow.svelte nutzt noch Subscription → match FAIL
//   - subscriptionHelpers.ts hat kein deriveStatusFromPreset → match FAIL
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_472_compare_list_restore.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const ROOT = fileURLToPath(new URL('../../../../../', import.meta.url)); // → frontend/

const PAGE     = join(ROOT, 'src/routes/compare/+page.svelte');
const SERVER   = join(ROOT, 'src/routes/compare/+page.server.ts');
const LIST     = join(ROOT, 'src/lib/components/compare/CompareList.svelte');
const ROW      = join(ROOT, 'src/lib/components/compare/CompareRow.svelte');
const HELPERS  = join(ROOT, 'src/lib/components/compare/subscriptionHelpers.ts');

// ── AC-1: +page.svelte — kein altes Live-Tool mehr ───────────────────────────

test('AC-1: +page.svelte importiert LocationsRail NICHT mehr', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.doesNotMatch(
		src,
		/import.*LocationsRail/,
		'+page.svelte darf LocationsRail nicht mehr importieren (altes 3-Spalten-Tool entfernt)'
	);
});

test('AC-1: +page.svelte importiert PresetHeader NICHT mehr', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.doesNotMatch(
		src,
		/import.*PresetHeader/,
		'+page.svelte darf PresetHeader nicht mehr importieren (altes 3-Spalten-Tool entfernt)'
	);
});

test('AC-1: +page.svelte importiert CompareMatrix NICHT mehr', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.doesNotMatch(
		src,
		/import.*CompareMatrix/,
		'+page.svelte darf CompareMatrix nicht mehr importieren (altes 3-Spalten-Tool entfernt)'
	);
});

// ── AC-1: +page.svelte — neuer Listenansicht-Header ──────────────────────────

test('AC-1: +page.svelte enthält Eyebrow WORKSPACE · ORTS-VERGLEICHE', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/WORKSPACE.*ORTS-VERGLEICHE|Workspace.*Orts-Vergleiche/i,
		'+page.svelte muss Eyebrow-Text "WORKSPACE · ORTS-VERGLEICHE" enthalten'
	);
});

test('AC-1: +page.svelte enthält H1 Orts-Vergleiche', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/Orts-Vergleiche/,
		'+page.svelte muss den Seitentitel "Orts-Vergleiche" enthalten'
	);
});

test('AC-1: +page.svelte importiert CompareList', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/import.*CompareList/,
		'+page.svelte muss CompareList.svelte importieren'
	);
});

// ── AC-6: +page.svelte — Stats-Zeile (Aktiv / Pausiert / Drafts) ─────────────

test('AC-6: +page.svelte enthält Stats-Zeile mit Aktiv/Pausiert/Drafts', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/[Aa]ktiv/,
		'+page.svelte muss Stats-Zeile mit "Aktiv" anzeigen'
	);
	assert.match(
		src,
		/[Pp]ausiert/,
		'+page.svelte muss Stats-Zeile mit "Pausiert" anzeigen'
	);
	assert.match(
		src,
		/[Dd]raft/,
		'+page.svelte muss Stats-Zeile mit "Drafts" anzeigen'
	);
});

// ── AC-2: +page.server.ts — vereinfacht, nur presets ─────────────────────────

test('AC-2: +page.server.ts lädt keine /api/subscriptions mehr', () => {
	const src = readFileSync(SERVER, 'utf-8');
	assert.doesNotMatch(
		src,
		/\/api\/subscriptions/,
		'+page.server.ts darf /api/subscriptions nicht mehr laden (nur noch /api/compare/presets)'
	);
});

test('AC-2: +page.server.ts gibt locations nicht mehr zurück', () => {
	const src = readFileSync(SERVER, 'utf-8');
	assert.doesNotMatch(
		src,
		/return\s*\{[^}]*\blocations\b/s,
		'+page.server.ts darf locations nicht mehr im return-Objekt haben'
	);
});

// ── AC-2: CompareList.svelte — ComparePreset statt Subscription ───────────────

test('AC-2: CompareList.svelte importiert ComparePreset, nicht Subscription', () => {
	const src = readFileSync(LIST, 'utf-8');
	assert.match(
		src,
		/ComparePreset/,
		'CompareList.svelte muss ComparePreset-Typ verwenden, nicht Subscription'
	);
});

test('AC-2: CompareList.svelte hat presets-Prop, nicht subscriptions-Prop', () => {
	const src = readFileSync(LIST, 'utf-8');
	assert.match(
		src,
		/presets.*ComparePreset|ComparePreset.*presets/,
		'CompareList.svelte muss presets: ComparePreset[] als Prop haben'
	);
});

test('AC-4: CompareList.svelte ruft /api/compare/presets für Delete auf', () => {
	const src = readFileSync(LIST, 'utf-8');
	assert.match(
		src,
		/\/api\/compare\/presets/,
		'CompareList.svelte muss DELETE auf /api/compare/presets/{id} aufrufen'
	);
});

// ── AC-2: CompareRow.svelte — ComparePreset statt Subscription ───────────────

test('AC-2: CompareRow.svelte importiert ComparePreset, nicht Subscription', () => {
	const src = readFileSync(ROW, 'utf-8');
	assert.match(
		src,
		/ComparePreset/,
		'CompareRow.svelte muss ComparePreset-Typ verwenden, nicht Subscription'
	);
});

test('AC-2: CompareRow.svelte hat preset-Prop, nicht sub-Prop', () => {
	const src = readFileSync(ROW, 'utf-8');
	assert.match(
		src,
		/\bpreset\b.*ComparePreset|ComparePreset.*\bpreset\b/,
		'CompareRow.svelte muss preset: ComparePreset als Prop haben (nicht sub: Subscription)'
	);
});

test('AC-2: CompareRow.svelte zeigt location_ids.length für Orte-Spalte', () => {
	const src = readFileSync(ROW, 'utf-8');
	assert.match(
		src,
		/location_ids/,
		'CompareRow.svelte muss preset.location_ids für die Orte-Anzahl nutzen'
	);
});

// ── subscriptionHelpers.ts — neue ComparePreset-Helfer ───────────────────────

test('AC-6: subscriptionHelpers.ts exportiert deriveStatusFromPreset', () => {
	const src = readFileSync(HELPERS, 'utf-8');
	assert.match(
		src,
		/export function deriveStatusFromPreset/,
		'subscriptionHelpers.ts muss deriveStatusFromPreset() für ComparePreset exportieren'
	);
});

test('AC-6: deriveStatusFromPreset gibt draft zurück wenn location_ids leer', () => {
	const src = readFileSync(HELPERS, 'utf-8');
	assert.match(
		src,
		/location_ids/,
		'deriveStatusFromPreset muss location_ids.length prüfen für draft-Status'
	);
});

test('AC-2: subscriptionHelpers.ts exportiert presetLocationsLabel', () => {
	const src = readFileSync(HELPERS, 'utf-8');
	assert.match(
		src,
		/export function presetLocationsLabel/,
		'subscriptionHelpers.ts muss presetLocationsLabel() für ComparePreset exportieren'
	);
});
