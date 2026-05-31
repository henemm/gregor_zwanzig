// TDD RED — Issue #488: CompareTile + CompareStatusPill + CompareKebab + compareActions
//
// Spec: docs/specs/modules/issue_488_compare_tile_atoms.md
//
// Source-Inspection-Tests (kein DOM-Rendering, keine Mocks).
// compareActions: direkter Funktionsaufruf-Test.
//
// RED-Erwartung (vor Implementation):
//   - CompareTile.svelte fehlt → existsSync FAIL
//   - CompareStatusPill.svelte fehlt → existsSync FAIL
//   - CompareKebab.svelte fehlt → existsSync FAIL
//   - compareActions fehlt → Import-Fehler FAIL
//   - molecules/index.ts hat keine Compare*-Exporte → match FAIL
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_488_compare_tile_atoms.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const COMPARE = fileURLToPath(new URL('../', import.meta.url));
const MOLECULES = fileURLToPath(new URL('../../molecules/', import.meta.url));

const TILE        = join(COMPARE, 'CompareTile.svelte');
const STATUS_PILL = join(COMPARE, 'CompareStatusPill.svelte');
const KEBAB       = join(COMPARE, 'CompareKebab.svelte');
const HELPERS     = join(COMPARE, 'subscriptionHelpers.ts');
const MOL_INDEX   = join(MOLECULES, 'index.ts');

// ── Datei-Existenz ────────────────────────────────────────────────────────────

test('#488 AC-1: CompareTile.svelte existiert', () => {
	assert.ok(existsSync(TILE), 'CompareTile.svelte fehlt in compare/');
});

test('#488 AC-2: CompareStatusPill.svelte existiert', () => {
	assert.ok(existsSync(STATUS_PILL), 'CompareStatusPill.svelte fehlt in compare/');
});

test('#488 AC-3: CompareKebab.svelte existiert', () => {
	assert.ok(existsSync(KEBAB), 'CompareKebab.svelte fehlt in compare/');
});

// ── AC-1: CompareTile ─────────────────────────────────────────────────────────

test('#488 AC-1: CompareTile hat border-left mit --g-accent bei accent=true', () => {
	const src = readFileSync(TILE, 'utf-8');
	assert.match(
		src,
		/border-left.*g-accent|g-accent.*border-left/,
		'CompareTile.svelte muss border-left mit var(--g-accent) für accent=true implementieren'
	);
});

test('#488 AC-1: CompareTile hat dense-Prop', () => {
	const src = readFileSync(TILE, 'utf-8');
	assert.match(src, /dense/, 'CompareTile.svelte muss dense-Prop haben');
});

test('#488 AC-1: CompareTile hat compact-Prop', () => {
	const src = readFileSync(TILE, 'utf-8');
	assert.match(src, /compact/, 'CompareTile.svelte muss compact-Prop haben');
});

test('#488 AC-1: CompareTile hat accent-Prop', () => {
	const src = readFileSync(TILE, 'utf-8');
	assert.match(src, /accent/, 'CompareTile.svelte muss accent-Prop haben');
});

test('#488 AC-1: CompareTile importiert ComparePreset-Typ', () => {
	const src = readFileSync(TILE, 'utf-8');
	assert.match(
		src,
		/ComparePreset/,
		'CompareTile.svelte muss ComparePreset als Prop-Typ verwenden'
	);
});

// ── AC-2: CompareStatusPill ───────────────────────────────────────────────────

test('#488 AC-2: CompareStatusPill ist auf CompareStatus typisiert', () => {
	const src = readFileSync(STATUS_PILL, 'utf-8');
	assert.match(
		src,
		/CompareStatus/,
		'CompareStatusPill.svelte muss CompareStatus als Prop-Typ verwenden'
	);
});

test('#488 AC-2: CompareStatusPill hat status-Prop', () => {
	const src = readFileSync(STATUS_PILL, 'utf-8');
	assert.match(src, /status/, 'CompareStatusPill.svelte muss status-Prop haben');
});

test('#488 AC-2: CompareStatusPill enthält Filled-Variante (active/grün)', () => {
	const src = readFileSync(STATUS_PILL, 'utf-8');
	// Filled kann via tone="success", g-success, g-good, oder success-Klasse implementiert sein
	assert.match(
		src,
		/success|g-good|g-accent|filled/i,
		'CompareStatusPill.svelte muss eine grüngefüllte Variante für active-Status haben'
	);
});

test('#488 AC-2: CompareStatusPill enthält Outline-Variante (paused/draft)', () => {
	const src = readFileSync(STATUS_PILL, 'utf-8');
	// Outline kann via border, outline, ghost, paused, draft implementiert sein
	assert.match(
		src,
		/outline|paused|draft|border/i,
		'CompareStatusPill.svelte muss eine Outline-Variante für paused/draft-Status haben'
	);
});

// ── AC-3: CompareKebab ────────────────────────────────────────────────────────

test('#488 AC-3: CompareKebab importiert DropdownMenu aus bits-ui', () => {
	const src = readFileSync(KEBAB, 'utf-8');
	assert.match(
		src,
		/DropdownMenu/,
		'CompareKebab.svelte muss DropdownMenu aus bits-ui importieren'
	);
});

test('#488 AC-3: CompareKebab enthält stopPropagation im Trigger', () => {
	const src = readFileSync(KEBAB, 'utf-8');
	assert.match(
		src,
		/stopPropagation/,
		'CompareKebab.svelte muss e.stopPropagation() im Trigger implementieren'
	);
});

test('#488 AC-3: CompareKebab importiert Ellipsis-Icon', () => {
	const src = readFileSync(KEBAB, 'utf-8');
	assert.match(
		src,
		/ellipsis/i,
		'CompareKebab.svelte muss ein Ellipsis-Icon importieren'
	);
});

test('#488 AC-3: CompareKebab nutzt bits-ui Snippet-Trigger-Pattern', () => {
	const src = readFileSync(KEBAB, 'utf-8');
	assert.match(
		src,
		/snippet\s+child|#snippet/,
		'CompareKebab.svelte muss das bits-ui v2 {#snippet child({ props })} Pattern nutzen'
	);
});

// ── AC-4: compareActions (Funktionsaufruf-Tests) ──────────────────────────────

test('#488 AC-4: compareActions ist in subscriptionHelpers.ts exportiert', () => {
	const src = readFileSync(HELPERS, 'utf-8');
	assert.match(
		src,
		/export function compareActions|export const compareActions/,
		'subscriptionHelpers.ts muss compareActions exportieren'
	);
});

test('#488 AC-4: CompareAction-Typ ist in subscriptionHelpers.ts exportiert', () => {
	const src = readFileSync(HELPERS, 'utf-8');
	assert.match(
		src,
		/export type CompareAction/,
		'subscriptionHelpers.ts muss CompareAction-Typ exportieren'
	);
});

// Direkter Funktionsaufruf — scheitert im RED weil compareActions noch nicht existiert
test('#488 AC-4: compareActions("active") liefert 5 Einträge', async () => {
	const { compareActions } = await import('../subscriptionHelpers.ts');
	const actions = compareActions('active');
	assert.equal(actions.length, 5, 'compareActions("active") muss genau 5 Aktionen liefern');
});

test('#488 AC-4: compareActions("active") enthält pause, send, preview, edit, delete', async () => {
	const { compareActions } = await import('../subscriptionHelpers.ts');
	const actions = compareActions('active');
	const ids = actions.map((a: { id: string }) => a.id);
	assert.ok(ids.includes('pause'),   'compareActions("active") muss "pause" enthalten');
	assert.ok(ids.includes('send'),    'compareActions("active") muss "send" enthalten');
	assert.ok(ids.includes('preview'), 'compareActions("active") muss "preview" enthalten');
	assert.ok(ids.includes('edit'),    'compareActions("active") muss "edit" enthalten');
	assert.ok(ids.includes('delete'),  'compareActions("active") muss "delete" enthalten');
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

// ── molecules/index.ts Re-Exporte ─────────────────────────────────────────────

test('#488 AC-5: molecules/index.ts re-exportiert CompareTile', () => {
	const src = readFileSync(MOL_INDEX, 'utf-8');
	assert.match(src, /CompareTile/, 'molecules/index.ts muss CompareTile re-exportieren');
});

test('#488 AC-5: molecules/index.ts re-exportiert CompareStatusPill', () => {
	const src = readFileSync(MOL_INDEX, 'utf-8');
	assert.match(src, /CompareStatusPill/, 'molecules/index.ts muss CompareStatusPill re-exportieren');
});

test('#488 AC-5: molecules/index.ts re-exportiert CompareKebab', () => {
	const src = readFileSync(MOL_INDEX, 'utf-8');
	assert.match(src, /CompareKebab/, 'molecules/index.ts muss CompareKebab re-exportieren');
});
