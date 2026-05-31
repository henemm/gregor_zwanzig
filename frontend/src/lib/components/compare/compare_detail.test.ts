// TDD RED: Issue #491 — Orts-Vergleich Detail-Seite /compare/[id]
//
// Spec: docs/specs/modules/issue_491_compare_detail.md
//
// Source-Inspection-Test (kein Render, keine Mocks): Datei-Existenz und
// Schlüssel-Inhalte für CompareDetail.svelte, +page.svelte, +page.server.ts.
//
// RED vor Implementierung: alle Dateien fehlen → alle Asserts schlagen fehl.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/lib/components/compare/compare_detail.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const read = (f: string) => readFileSync(join(here, f), 'utf-8');
const has = (f: string) => existsSync(join(here, f));

test('#491 AC-5: CompareDetail.svelte existiert', () => {
	assert.ok(has('CompareDetail.svelte'), 'CompareDetail.svelte fehlt in frontend/src/lib/components/compare/');
});

test('#491 AC-1: +page.svelte Breadcrumb-Text enthält ORTS-VERGLEICHE', () => {
	const pagePath = '../../../routes/compare/[id]/+page.svelte';
	assert.ok(has(pagePath), 'frontend/src/routes/compare/[id]/+page.svelte fehlt');
	const src = read(pagePath);
	assert.ok(src.includes('ORTS-VERGLEICHE'), '+page.svelte enthält keinen Breadcrumb-Text "ORTS-VERGLEICHE"');
});

test('#491 AC-1: +page.svelte hat Bearbeiten-Link', () => {
	const pagePath = '../../../routes/compare/[id]/+page.svelte';
	assert.ok(has(pagePath), 'frontend/src/routes/compare/[id]/+page.svelte fehlt');
	const src = read(pagePath);
	assert.ok(src.includes('Bearbeiten'), '+page.svelte enthält keinen "Bearbeiten"-Link');
	assert.ok(src.includes('/compare/'), '+page.svelte enthält keinen /compare/-Pfad für Bearbeiten-Link');
});

test('#491 AC-2: CompareDetail.svelte hat Monitoring-Streifen-Felder', () => {
	assert.ok(has('CompareDetail.svelte'), 'CompareDetail.svelte fehlt');
	const src = read('CompareDetail.svelte');
	assert.ok(src.includes('Nächster Versand'), 'CompareDetail.svelte hat kein "Nächster Versand"-Feld im Monitoring-Streifen');
	assert.ok(src.includes('Zuletzt'), 'CompareDetail.svelte hat kein "Zuletzt"-Feld im Monitoring-Streifen');
	assert.ok(src.includes('empfaenger'), 'CompareDetail.svelte referenziert kein "empfaenger"-Feld');
});

test('#491 AC-3: CompareDetail.svelte hat location_ids-Iteration', () => {
	assert.ok(has('CompareDetail.svelte'), 'CompareDetail.svelte fehlt');
	const src = read('CompareDetail.svelte');
	assert.ok(src.includes('location_ids'), 'CompareDetail.svelte iteriert nicht über "location_ids"');
	assert.ok(src.includes('elevation_m'), 'CompareDetail.svelte zeigt keine Höhe ("elevation_m") aus dem Location-Lookup');
});

test('#491 AC-5: +page.server.ts existiert', () => {
	const serverPath = '../../../routes/compare/[id]/+page.server.ts';
	assert.ok(has(serverPath), 'frontend/src/routes/compare/[id]/+page.server.ts fehlt');
});

test('#491 AC-1: +page.svelte hat StatusPill-Stub', () => {
	const pagePath = '../../../routes/compare/[id]/+page.svelte';
	assert.ok(has(pagePath), 'frontend/src/routes/compare/[id]/+page.svelte fehlt');
	const src = read(pagePath);
	assert.ok(
		src.includes('statusInfo') || src.includes('deriveStatusFromPreset'),
		'+page.svelte hat keinen StatusPill-Stub (statusInfo oder deriveStatusFromPreset fehlt)'
	);
});

test('#491 AC-1: +page.svelte hat Sub-Zeile mit Profil und N Orte', () => {
	const pagePath = '../../../routes/compare/[id]/+page.svelte';
	assert.ok(has(pagePath), 'frontend/src/routes/compare/[id]/+page.svelte fehlt');
	const src = read(pagePath);
	assert.ok(src.includes('profil'), '+page.svelte enthält kein "profil"-Feld in der Sub-Zeile');
	assert.ok(src.includes('location_ids.length'), '+page.svelte enthält kein "location_ids.length" für N Orte');
});
