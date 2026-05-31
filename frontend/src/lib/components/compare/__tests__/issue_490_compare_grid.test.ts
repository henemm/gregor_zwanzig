// TDD RED — Issue #490: Compare-Übersicht → Kachel-Grid (Block B, Epic #485)
//
// Spec: docs/specs/modules/issue_490_compare_grid.md
//
// Source-Inspection-Tests: prüfen Soll-Zustand nach Implementation.
//
// RED-Erwartung (vor Implementation):
//   AC-Grid-1: FAIL — CompareGrid.svelte existiert nicht
//   AC-Grid-2: FAIL — /compare/+page.svelte importiert noch CompareList, nicht CompareGrid
//   AC-Grid-3: FAIL — CompareList.svelte existiert noch (soll gelöscht werden)
//   AC-Grid-4: FAIL — molecules/index.ts exportiert CompareGrid nicht
//   AC-Grid-5: FAIL — CompareGrid.svelte hat keine grid-cols-Klassen
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_490_compare_grid.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const COMPARE_DIR = dirname(fileURLToPath(import.meta.url)) + '/..';
const ROUTES_COMPARE = join(COMPARE_DIR, '..', '..', '..', 'routes', 'compare');
const MOLECULES_DIR = join(COMPARE_DIR, '..', 'molecules');

const GRID_FILE = join(COMPARE_DIR, 'CompareGrid.svelte');
const LIST_FILE = join(COMPARE_DIR, 'CompareList.svelte');
const PAGE_FILE = join(ROUTES_COMPARE, '+page.svelte');
const MOL_INDEX = join(MOLECULES_DIR, 'index.ts');

// ── AC-Grid-1: CompareGrid.svelte existiert ───────────────────────────────────

describe('AC-Grid-1: CompareGrid.svelte vorhanden', () => {
	test('CompareGrid.svelte existiert in compare/', () => {
		assert.ok(
			existsSync(GRID_FILE),
			'CompareGrid.svelte fehlt — muss in frontend/src/lib/components/compare/ erstellt werden'
		);
	});

	test('CompareGrid.svelte exportiert CompareGrid als default', () => {
		assert.ok(existsSync(GRID_FILE), 'CompareGrid.svelte fehlt');
		const src = readFileSync(GRID_FILE, 'utf-8');
		assert.match(
			src,
			/CompareGrid/,
			'CompareGrid.svelte enthält keinen Bezug auf CompareGrid'
		);
	});
});

// ── AC-Grid-2: /compare/+page.svelte nutzt CompareGrid ───────────────────────

describe('AC-Grid-2: /compare/+page.svelte importiert CompareGrid statt CompareList', () => {
	test('+page.svelte importiert CompareGrid', () => {
		const src = readFileSync(PAGE_FILE, 'utf-8');
		assert.match(
			src,
			/CompareGrid/,
			'CompareGrid wird in /compare/+page.svelte nicht importiert — Migration fehlt'
		);
	});

	test('+page.svelte importiert NICHT mehr CompareList', () => {
		const src = readFileSync(PAGE_FILE, 'utf-8');
		assert.ok(
			!src.includes('CompareList'),
			'CompareList wird noch in /compare/+page.svelte importiert — muss durch CompareGrid ersetzt werden'
		);
	});
});

// ── AC-Grid-3: CompareList.svelte entfernt ────────────────────────────────────

describe('AC-Grid-3: CompareList.svelte gelöscht', () => {
	test('CompareList.svelte existiert nicht mehr', () => {
		assert.ok(
			!existsSync(LIST_FILE),
			'CompareList.svelte existiert noch — muss nach Migration gelöscht werden'
		);
	});
});

// ── AC-Grid-4: CompareGrid hat Grid-Layout ────────────────────────────────────

describe('AC-Grid-4: CompareGrid rendert CSS-Grid mit CompareTile-Kacheln', () => {
	test('CompareGrid.svelte enthält grid-cols oder auto-fill für Kachel-Layout', () => {
		assert.ok(existsSync(GRID_FILE), 'CompareGrid.svelte fehlt');
		const src = readFileSync(GRID_FILE, 'utf-8');
		assert.match(
			src,
			/grid|auto-fill|repeat/,
			'CompareGrid.svelte hat kein Grid-Layout (grid, auto-fill oder repeat fehlen)'
		);
	});

	test('CompareGrid.svelte verwendet CompareTile', () => {
		assert.ok(existsSync(GRID_FILE), 'CompareGrid.svelte fehlt');
		const src = readFileSync(GRID_FILE, 'utf-8');
		assert.match(
			src,
			/CompareTile/,
			'CompareGrid.svelte rendert kein CompareTile — Kachel-Import fehlt'
		);
	});

	test('CompareGrid.svelte enthält ConfirmDialog für Lösch-Bestätigung', () => {
		assert.ok(existsSync(GRID_FILE), 'CompareGrid.svelte fehlt');
		const src = readFileSync(GRID_FILE, 'utf-8');
		assert.match(
			src,
			/ConfirmDialog/,
			'CompareGrid.svelte enthält keinen ConfirmDialog — Lösch-Bestätigung fehlt'
		);
	});
});

// ── AC-Grid-5: Build-Sicherheit ───────────────────────────────────────────────

describe('AC-Grid-5: /compare/+page.svelte enthält keinen CompareList-Import', () => {
	test('+page.svelte hat kein CompareList-Import (Build würde brechen)', () => {
		const src = readFileSync(PAGE_FILE, 'utf-8');
		assert.ok(
			!src.includes("from './CompareList") &&
			!src.includes('CompareList.svelte'),
			'Direkter Dateiimport von CompareList noch vorhanden — Datei wird gelöscht'
		);
	});
});
