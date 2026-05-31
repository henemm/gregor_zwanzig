// TDD RED: Issue #490 — CompareGrid (Kachel-Grid für /compare-Übersicht)
//
// Spec: docs/specs/modules/issue_490_compare_grid.md
//
// Prüft, dass die /compare-Route auf Kachel-Grid umgebaut wurde:
//   CompareGrid.svelte (neu) + +page.svelte umverdrahtet +
//   CompareList/CompareRow gelöscht + Block-A-Guards (CompareTile, CompareKebab).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_490_compare_grid.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const ROOT = fileURLToPath(new URL('../../../../../', import.meta.url)); // → frontend/src/../ = frontend/

const GRID     = join(ROOT, 'src/lib/components/compare/CompareGrid.svelte');
const PAGE     = join(ROOT, 'src/routes/compare/+page.svelte');
const SERVER   = join(ROOT, 'src/routes/compare/+page.server.ts');
// CompareTile/CompareKebab leben physisch in compare/ und werden via
// molecules/index.ts cross-directory re-exportiert (siehe Issue #488).
const TILE     = join(ROOT, 'src/lib/components/compare/CompareTile.svelte');
const KEBAB    = join(ROOT, 'src/lib/components/compare/CompareKebab.svelte');

// ── AC-1: CompareGrid.svelte existiert und ist kein Tabellen-Layout ──────────

test('AC-1: CompareGrid.svelte existiert', () => {
	assert.ok(
		existsSync(GRID),
		'CompareGrid.svelte muss in compare/ vorhanden sein (wurde noch nicht erstellt)'
	);
});

test('AC-1: CompareGrid.svelte enthält CSS-Grid repeat(auto-fill, minmax(300px, 1fr))', () => {
	const src = readFileSync(GRID, 'utf-8');
	assert.match(
		src,
		/repeat\(auto-fill,\s*minmax\(300px,\s*1fr\)\)/,
		'CompareGrid.svelte muss grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)) definieren'
	);
});

test('AC-1: CompareGrid.svelte importiert keine Table-Primitives aus ui/table', () => {
	const src = readFileSync(GRID, 'utf-8');
	assert.doesNotMatch(
		src,
		/from ['"].*ui\/table/,
		'CompareGrid.svelte darf kein Table-Primitiv aus ui/table importieren (Grid statt Tabelle)'
	);
});

test('AC-1: CompareGrid.svelte hat presets-Prop mit ComparePreset-Typ', () => {
	const src = readFileSync(GRID, 'utf-8');
	assert.match(
		src,
		/ComparePreset/,
		'CompareGrid.svelte muss ComparePreset als Prop-Typ verwenden'
	);
});

// ── AC-2: Aktive Kachel — accent-Border ──────────────────────────────────────

test('AC-2: CompareGrid.svelte übergibt accent-Prop an CompareTile für aktive Vergleiche', () => {
	const src = readFileSync(GRID, 'utf-8');
	assert.match(
		src,
		/accent/,
		'CompareGrid.svelte muss accent-Prop an CompareTile weitergeben (border-left: 3px solid var(--g-accent))'
	);
});

// ── AC-3: Search-Pill + Empty-State ──────────────────────────────────────────

test('AC-3: CompareGrid.svelte hat Search-State und toLowerCase-Filterung', () => {
	const src = readFileSync(GRID, 'utf-8');
	assert.match(
		src,
		/search/,
		'CompareGrid.svelte muss einen search-State haben'
	);
	assert.match(
		src,
		/toLowerCase/,
		'CompareGrid.svelte muss case-insensitiv filtern (toLowerCase)'
	);
});

test('AC-3: CompareGrid.svelte enthält Suche-leer-Empty-State mit Query-Interpolation', () => {
	const src = readFileSync(GRID, 'utf-8');
	assert.match(
		src,
		/Keine Vergleiche.*gefunden|keine.*vergleiche.*gefunden/i,
		'CompareGrid.svelte muss leeren Suche-State mit Query-Text anzeigen'
	);
});

test('AC-3: CompareGrid.svelte enthält globalen Empty-State für keine Vergleiche', () => {
	const src = readFileSync(GRID, 'utf-8');
	assert.match(
		src,
		/Noch keine Orts-Vergleiche|keine.*orts-vergleiche/i,
		'CompareGrid.svelte muss Empty-State anzeigen wenn noch keine Vergleiche vorhanden'
	);
});

// ── AC-4: Navigation + stopPropagation ───────────────────────────────────────

test('AC-4: CompareGrid.svelte verarbeitet Delete-Aktion über onAction-Prop von CompareTile', () => {
	const src = readFileSync(GRID, 'utf-8');
	// CompareTile emittiert onAction(id) — CompareGrid lauscht auf id === 'delete'
	const hasOnAction = /onAction/.test(src);
	const hasDeleteId = /['"]delete['"]/.test(src);
	const hasOndelete = /ondelete/.test(src);
	const hasStopPropagation = /stopPropagation/.test(src);
	assert.ok(
		(hasOnAction && hasDeleteId) || hasOndelete || hasStopPropagation,
		'CompareGrid.svelte muss Delete via onAction("delete") oder ondelete-Prop oder stopPropagation handhaben'
	);
});

test('AC-4: CompareGrid.svelte navigiert zu /compare/{id} beim Kachel-Klick', () => {
	const src = readFileSync(GRID, 'utf-8');
	assert.match(
		src,
		/\/compare\//,
		'CompareGrid.svelte muss zu /compare/{id} navigieren (onclick oder href)'
	);
});

// ── AC-5: Delete-Dialog via molecules/ConfirmDialog ──────────────────────────

test('AC-5: CompareGrid.svelte importiert ConfirmDialog aus molecules (kein direktes ui/dialog)', () => {
	const src = readFileSync(GRID, 'utf-8');
	assert.match(
		src,
		/ConfirmDialog/,
		'CompareGrid.svelte muss ConfirmDialog-Molecule für den Lösch-Dialog verwenden'
	);
	assert.doesNotMatch(
		src,
		/from ['"].*ui\/dialog/,
		'CompareGrid.svelte darf ui/dialog NICHT direkt importieren (nutze molecules/ConfirmDialog)'
	);
});

test('AC-5: CompareGrid.svelte ruft api.del für /api/compare/presets auf', () => {
	const src = readFileSync(GRID, 'utf-8');
	assert.match(
		src,
		/api\.del\(.*\/api\/compare\/presets/,
		'CompareGrid.svelte muss DELETE auf /api/compare/presets/{id} aufrufen'
	);
});

// ── AC-5: +page.svelte — CompareGrid statt CompareList ───────────────────────

test('AC-5: +page.svelte importiert CompareGrid, nicht CompareList', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/import.*CompareGrid/,
		'+page.svelte muss CompareGrid importieren (Tabelle durch Grid ersetzt)'
	);
});

test('AC-5: +page.svelte importiert CompareList NICHT mehr', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.doesNotMatch(
		src,
		/import.*CompareList/,
		'+page.svelte darf CompareList nicht mehr importieren (wurde gelöscht)'
	);
});

// ── Migrations-Invarianten (von issue_472 übernommen) ────────────────────────

test('Invariant: +page.svelte importiert LocationsRail NICHT', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.doesNotMatch(src, /import.*LocationsRail/);
});

test('Invariant: +page.svelte importiert PresetHeader NICHT', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.doesNotMatch(src, /import.*PresetHeader/);
});

test('Invariant: +page.svelte importiert CompareMatrix NICHT', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.doesNotMatch(src, /import.*CompareMatrix/);
});

test('Invariant: +page.svelte enthält Eyebrow WORKSPACE · ORTS-VERGLEICHE', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(src, /WORKSPACE.*ORTS-VERGLEICHE|Workspace.*Orts-Vergleiche/i);
});

test('Invariant: +page.svelte enthält H1 Orts-Vergleiche', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(src, /Orts-Vergleiche/);
});

test('Invariant: +page.svelte enthält Stats-Zeile mit Aktiv/Pausiert/Drafts', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(src, /[Aa]ktiv/);
	assert.match(src, /[Pp]ausiert/);
	assert.match(src, /[Dd]raft/);
});

test('Invariant: +page.server.ts lädt keine /api/subscriptions', () => {
	const src = readFileSync(SERVER, 'utf-8');
	assert.doesNotMatch(src, /\/api\/subscriptions/);
});

// ── Block-A-Guards (CompareTile + CompareKebab müssen existieren) ─────────────

test('Block-A-Guard: molecules/CompareTile.svelte existiert (Issue #488)', () => {
	assert.ok(
		existsSync(TILE),
		'molecules/CompareTile.svelte muss existieren (Block A #488 nicht fertig?)'
	);
});

test('Block-A-Guard: molecules/CompareKebab.svelte existiert (Issue #488)', () => {
	assert.ok(
		existsSync(KEBAB),
		'molecules/CompareKebab.svelte muss existieren (Block A #488 nicht fertig?)'
	);
});
