// Issue #488: CompareTile + CompareStatusPill + CompareKebab + compareActions
//
// Spec: docs/specs/modules/issue_488_compare_tile_atoms.md
//
// Verhaltens-Tests für compareActions() (direkter Funktionsaufruf, kein Mock).
// Die ursprünglichen Source-Inspection-Tests (readFileSync/existsSync gegen
// CompareTile.svelte / CompareStatusPill.svelte / CompareKebab.svelte /
// molecules/index.ts) wurden entfernt — Dateiinhalt-Checks sind laut CLAUDE.md
// verboten (Präzedenz #893).
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_488_compare_tile_atoms.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

// ── compareActions (Funktionsaufruf-Tests) ────────────────────────────────────
// #627 (closed, commit s.o. bug_626_compare_menu_actions.test.ts): "send" wieder
// aufgenommen. Issue #1256 Scheibe 1 (2026-07-13): "archive" wieder entfernt
// (Soll molecules.jsx:1018-1027, wandert in Hub-Lifecycle-Kebab Scheibe 3) ->
// compareActions("active"/"paused") liefern 5 Einträge.

test('#488 AC-4: compareActions("active") liefert 5 Einträge', async () => {
	const { compareActions } = await import('../subscriptionHelpers.ts');
	const actions = compareActions('active');
	assert.equal(actions.length, 5, 'compareActions("active") muss genau 5 Aktionen liefern');
});

test('#488 AC-4: compareActions("active") enthält pause, send, preview, edit, delete — NICHT archive', async () => {
	const { compareActions } = await import('../subscriptionHelpers.ts');
	const actions = compareActions('active');
	const ids = actions.map((a: { id: string }) => a.id);
	assert.ok(ids.includes('pause'),   'compareActions("active") muss "pause" enthalten');
	assert.ok(ids.includes('send'),    'compareActions("active") muss "send" enthalten (#627)');
	assert.ok(ids.includes('preview'), 'compareActions("active") muss "preview" enthalten');
	assert.ok(ids.includes('edit'),    'compareActions("active") muss "edit" enthalten');
	assert.ok(ids.includes('delete'),  'compareActions("active") muss "delete" enthalten');
	assert.ok(!ids.includes('archive'), 'compareActions("active") darf "archive" nicht mehr enthalten (#1256 Scheibe 1)');
});

test('#488 AC-4: compareActions("paused") liefert 5 Einträge (identisch zu active)', async () => {
	const { compareActions } = await import('../subscriptionHelpers.ts');
	const actions = compareActions('paused');
	assert.equal(actions.length, 5, 'compareActions("paused") muss genau 5 Aktionen liefern');
});

test('#488 AC-4: compareActions("draft") liefert 2 Einträge', async () => {
	const { compareActions } = await import('../subscriptionHelpers.ts');
	const actions = compareActions('draft');
	assert.equal(actions.length, 2, 'compareActions("draft") muss genau 2 Aktionen liefern');
});

test('#488 AC-4: compareActions("draft") enthält setup und delete', async () => {
	const { compareActions } = await import('../subscriptionHelpers.ts');
	const actions = compareActions('draft');
	const ids = actions.map((a: { id: string }) => a.id);
	assert.ok(ids.includes('setup'),  'compareActions("draft") muss "setup" enthalten');
	assert.ok(ids.includes('delete'), 'compareActions("draft") muss "delete" enthalten');
});

test('#488 AC-4: compareActions("draft") delete hat danger=true', async () => {
	const { compareActions } = await import('../subscriptionHelpers.ts');
	const actions = compareActions('draft');
	const del = actions.find((a: { id: string }) => a.id === 'delete');
	assert.ok(del?.danger === true, 'compareActions("draft") delete muss danger=true haben');
});

test('#488 AC-4: compareActions("active") delete hat danger=true', async () => {
	const { compareActions } = await import('../subscriptionHelpers.ts');
	const actions = compareActions('active');
	const del = actions.find((a: { id: string }) => a.id === 'delete');
	assert.ok(del?.danger === true, 'compareActions("active") delete muss danger=true haben');
});
