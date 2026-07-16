// TDD RED — Issue #1277: Listen-Übersichten vereinheitlichen (ListTable).
//
// Spec: docs/specs/feature/issue_1277_list_table_unify.md (AC-1, AC-5)
// Soll: geteiltes Tabellen-Organism `ListTable` (+ `ListTableRow`,
// `ListActionsMenu`, `ListNameCell`) in frontend/src/lib/components/organisms/,
// von BEIDEN Desktop-Übersichten (trips/+page.svelte, compare/+page.svelte)
// über denselben Importpfad konsumiert. `CompareGrid.svelte` entfällt danach
// (nur noch von compare/+page.svelte konsumiert, wird durch ListTable ersetzt).
//
// Source-Inspection-Tests (kein DOM-Rendering, keine Mocks, kein Playwright —
// Praezedenz: shared/corridor-editor/corridorEditorMobile.test.ts). Svelte-5-
// Komponenten sind ohne @testing-library/svelte (nicht in package.json) in
// diesem Test-Setup nicht mountbar; echtes Zeilen-/Hover-/Klick-Verhalten
// (AC-2, AC-3, AC-4, AC-6, AC-7) wird ergänzend über Playwright gegen
// Staging abgesichert (AC-8 aktualisiert dafür 4 bestehende e2e-Specs).
//
// RED-Erwartung: `ListTable.svelte` + Sub-Organismen existieren noch nicht,
// beide +page.svelte importieren sie noch nicht, `CompareGrid.svelte`
// existiert noch → alle Tests unten schlagen fehl, bis Phase 6 sie behebt.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/organisms/__tests__/list_table_unify.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const ORGANISMS = join(here, '..');
const LIST_TABLE = join(ORGANISMS, 'ListTable.svelte');
const LIST_TABLE_ROW = join(ORGANISMS, 'ListTableRow.svelte');
const LIST_ACTIONS_MENU = join(ORGANISMS, 'ListActionsMenu.svelte');
const LIST_NAME_CELL = join(ORGANISMS, 'ListNameCell.svelte');
const TRIPS_PAGE = join(here, '..', '..', '..', '..', 'routes', 'trips', '+page.svelte');
const COMPARE_PAGE = join(here, '..', '..', '..', '..', 'routes', 'compare', '+page.svelte');
const COMPARE_GRID = join(here, '..', '..', 'compare', 'CompareGrid.svelte');

describe('AC-1: ListTable + Sub-Organismen existieren als geteilte Komponenten', () => {
	test('ListTable.svelte existiert in organisms/', () => {
		assert.ok(existsSync(LIST_TABLE), 'organisms/ListTable.svelte fehlt noch');
	});

	test('ListTableRow.svelte existiert in organisms/', () => {
		assert.ok(existsSync(LIST_TABLE_ROW), 'organisms/ListTableRow.svelte fehlt noch');
	});

	test('ListActionsMenu.svelte existiert in organisms/', () => {
		assert.ok(existsSync(LIST_ACTIONS_MENU), 'organisms/ListActionsMenu.svelte fehlt noch');
	});

	test('ListNameCell.svelte existiert in organisms/', () => {
		assert.ok(existsSync(LIST_NAME_CELL), 'organisms/ListNameCell.svelte fehlt noch');
	});

	test('ListTable.svelte deklariert die Kern-Props der Spec-API (columns, rows, getRowId, onRowClick, rowActions, rowPrimary, onAction, emptyText)', () => {
		const src = readFileSync(LIST_TABLE, 'utf-8');
		for (const prop of ['columns', 'rows', 'getRowId', 'onRowClick', 'rowActions', 'rowPrimary', 'onAction', 'emptyText']) {
			assert.ok(src.includes(prop), `ListTable.svelte muss Prop "${prop}" deklarieren`);
		}
	});
});

describe('AC-1: trips/+page.svelte und compare/+page.svelte importieren denselben ListTable-Pfad (kein Fork)', () => {
	test('trips/+page.svelte importiert ListTable aus $lib/components/organisms', () => {
		const src = readFileSync(TRIPS_PAGE, 'utf-8');
		assert.match(
			src,
			/from ['"]\$lib\/components\/organisms\/ListTable\.svelte['"]/,
			'trips/+page.svelte muss ListTable aus $lib/components/organisms importieren'
		);
	});

	test('compare/+page.svelte importiert ListTable aus $lib/components/organisms', () => {
		const src = readFileSync(COMPARE_PAGE, 'utf-8');
		assert.match(
			src,
			/from ['"]\$lib\/components\/organisms\/ListTable\.svelte['"]/,
			'compare/+page.svelte muss ListTable aus $lib/components/organisms importieren'
		);
	});

	test('trips/+page.svelte enthält keine eigene Inline-Grid-Tabelle mehr (kein Fork)', () => {
		const src = readFileSync(TRIPS_PAGE, 'utf-8');
		assert.ok(
			!/Desktop Grid-Tabelle/.test(src) && !/gridTemplateColumns|grid-template-columns: 1\.6fr/.test(src),
			'trips/+page.svelte darf die Inline-Grid-Tabelle nicht mehr selbst definieren — muss ListTable nutzen'
		);
	});
});

describe('AC-4: Compare-Zeilenklick öffnet den Detail-Hub, nicht die Tages-Vorschau', () => {
	test('compare/+page.svelte verdrahtet onRowClick auf goto(`/compare/${id}`)', () => {
		const src = readFileSync(COMPARE_PAGE, 'utf-8');
		assert.match(
			src,
			/onRowClick=\{.*goto\(`\/compare\/\$\{.*\}`\)/s,
			'compare/+page.svelte muss ListTable onRowClick auf goto(`/compare/${id}`) verdrahten'
		);
	});
});

describe('AC-5: CompareGrid.svelte ist entfernt (nur noch ListTable rendert die Desktop-Übersicht)', () => {
	test('CompareGrid.svelte existiert nicht mehr im Repo', () => {
		assert.ok(!existsSync(COMPARE_GRID), 'CompareGrid.svelte muss nach dem Umbau gelöscht sein (AC-5)');
	});

	test('compare/+page.svelte importiert CompareGrid nicht mehr', () => {
		const src = readFileSync(COMPARE_PAGE, 'utf-8');
		assert.ok(
			!src.includes("CompareGrid"),
			'compare/+page.svelte darf CompareGrid nach dem Umbau nicht mehr referenzieren'
		);
	});
});
