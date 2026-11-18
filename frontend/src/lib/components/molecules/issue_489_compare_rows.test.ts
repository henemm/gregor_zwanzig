// TDD RED: Issue #489 — Block A2 (Epic #485): 3 Compare-Row-Molecules
//
// Spec: docs/specs/modules/issue_489_compare_row_molecules.md
//
// Source-Inspection-Tests (node:test, kein Render, keine Mocks):
//   Datei-Existenz, index.ts-Re-Exporte.
//
// Alle drei Molecules dieses Blocks sind inzwischen abgelöst:
//   - CompareLayoutRow.svelte  — #1360 (Attrappen-Zeile ohne Handler)
//   - CompareIdealRow.svelte   — #2346 S2 (toter Baustein ohne Importeur)
//   - CompareLocationRow.svelte — #3007 (Orte-Zeile = geteilter Baustein Listenzeile, ADR-0097;
//     Rang-Badge und Wechselfarbe entfallen laut Mockup Fassung 3)
// Die Suite wacht darüber, dass sie nicht zurückkehren.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/lib/components/molecules/issue_489_compare_rows.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const read = (f: string) => readFileSync(join(here, f), 'utf-8');
const has = (f: string) => existsSync(join(here, f));

const ABGELOEST = ['CompareLocationRow', 'CompareIdealRow', 'CompareLayoutRow'];

test('#489 AC-4a: abgelöste Compare-Row-Molecules sind gelöscht (#1360, #2346 S2, #3007)', () => {
	for (const name of ABGELOEST) assert.ok(!has(`${name}.svelte`), `${name}.svelte muss gelöscht sein`);
});

test('#489 AC-4b: index.ts exportiert keine abgelöste Compare-Row mehr', () => {
	const idx = read('index.ts'); // doc-compliance-test
	for (const name of ABGELOEST) assert.ok(!new RegExp(`\\b${name}\\b`).test(idx.replace(/\/\/.*$/gm, '')), `index.ts exportiert noch ${name}`);
});
