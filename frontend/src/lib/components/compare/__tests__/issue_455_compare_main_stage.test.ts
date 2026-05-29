// TDD RED — Issue #455: Compare-Hauptbühne Frontend (/compare 3-Spalten-Layout)
//
// Spec: docs/specs/modules/issue_455_compare_main_stage.md
//
// Source-Inspection-Tests (node:test, kein DOM-Rendering).
// Prüft: Imports, TestIDs, API-Call-Muster, Leer-Zustand-Logik in +page.svelte.
//
// RED-Erwartung (vor Implementation):
//   +page.svelte hat noch altes 49-Zeilen-Layout → alle Strukturtests FAIL
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_455_compare_main_stage.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';

const PAGE        = resolve('src/routes/compare/+page.svelte');
const PAGE_SERVER = resolve('src/routes/compare/+page.server.ts');

// ── Voraussetzungen ──────────────────────────────────────────────────────────

test('Voraussetzung: +page.svelte existiert', () => {
	assert.ok(existsSync(PAGE), `Datei nicht gefunden: ${PAGE}`);
});

test('Voraussetzung: +page.server.ts existiert und lädt locations/subscriptions/groups', () => {
	const src = readFileSync(PAGE_SERVER, 'utf-8');
	assert.match(src, /locations/, '+page.server.ts muss locations laden');
	assert.match(src, /subscriptions/, '+page.server.ts muss subscriptions laden');
	assert.match(src, /groups/, '+page.server.ts muss groups laden');
});

// ── Imports: Alle 6 Haupt-Komponenten ────────────────────────────────────────

test('AC-1: LocationsRail wird importiert', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/import\s+LocationsRail\b/,
		'+page.svelte muss LocationsRail importieren'
	);
});

test('AC-1: PresetHeader wird importiert', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/import\s+PresetHeader\b/,
		'+page.svelte muss PresetHeader importieren'
	);
});

test('AC-3: RecommendationBanner wird importiert', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/import\s+RecommendationBanner\b/,
		'+page.svelte muss RecommendationBanner importieren'
	);
});

test('AC-1/AC-2: CompareMatrix wird importiert', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/import\s+CompareMatrix\b/,
		'+page.svelte muss CompareMatrix importieren'
	);
});

test('AC-1: HourlyMatrix wird importiert', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/import\s+HourlyMatrix\b/,
		'+page.svelte muss HourlyMatrix importieren'
	);
});

test('AC-sidebar: AutoReportsOverview wird importiert', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/import\s+AutoReportsOverview\b/,
		'+page.svelte muss AutoReportsOverview importieren'
	);
});

// ── 3-Spalten-Layout: TestIDs ─────────────────────────────────────────────────

test('Layout: data-testid="compare-main-stage" vorhanden', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/compare-main-stage/,
		'+page.svelte muss data-testid="compare-main-stage" enthalten'
	);
});

test('Layout: 3-Spalten-Grid (grid-template-columns) gesetzt', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/grid-template-columns/,
		'+page.svelte muss grid-template-columns für das 3-Spalten-Layout setzen'
	);
});

test('Layout: data-testid="compare-center" für mittlere Spalte vorhanden', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/compare-center/,
		'+page.svelte muss data-testid="compare-center" für die mittlere Spalte enthalten'
	);
});

test('Layout: data-testid="compare-sidebar" für rechte Spalte vorhanden', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/compare-sidebar/,
		'+page.svelte muss data-testid="compare-sidebar" für die rechte Spalte enthalten'
	);
});

// ── AC-5: Leer-Zustand ────────────────────────────────────────────────────────

test('AC-5: data-testid="compare-empty-hint" vorhanden', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/compare-empty-hint/,
		'+page.svelte muss data-testid="compare-empty-hint" für den Leer-Zustand enthalten'
	);
});

test('AC-5: Leer-Zustand prüft selectedIds.length < 2', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/selectedIds\.length\s*<\s*2/,
		'+page.svelte muss selectedIds.length < 2 als Leer-Zustand-Bedingung prüfen'
	);
});

// ── AC-1: API-Call runComparison ─────────────────────────────────────────────

test('AC-1: runComparison-Funktion mit /api/compare/run vorhanden', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/\/api\/compare\/run/,
		'+page.svelte muss den Endpoint /api/compare/run aufrufen'
	);
});

test('AC-1: toCompareProfile wird im API-Call verwendet', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/toCompareProfile/,
		'+page.svelte muss toCompareProfile() für die Profil-Konvertierung verwenden'
	);
});

test('AC-1: location_ids wird an API übergeben', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/location_ids/,
		'+page.svelte muss location_ids im API-Request-Body übergeben'
	);
});

// ── AC-4: Profil-Reaktivität ──────────────────────────────────────────────────

test('AC-4: activityProfile als reaktiver State ($state) deklariert', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/activityProfile[^=]*=\s*\$state/,
		'+page.svelte muss activityProfile als $state deklarieren'
	);
});

test('AC-4: selectedIds als reaktiver State ($state) deklariert', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/selectedIds[^=]*=\s*\$state/,
		'+page.svelte muss selectedIds als $state deklarieren'
	);
});

// ── Mobile-Fallback ───────────────────────────────────────────────────────────

test('Layout: Mobile-Fallback data-testid="compare-mobile-fallback" vorhanden', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/compare-mobile-fallback/,
		'+page.svelte muss einen Mobile-Fallback mit data-testid="compare-mobile-fallback" enthalten'
	);
});
