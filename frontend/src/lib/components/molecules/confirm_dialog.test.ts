// TDD RED: Issue #478 — Trip-Detail Dialog-Migration (Atomic Design Phase 2 Restposten)
//
// Spec: docs/specs/modules/issue_478_trip_detail_dialog_migration.md
//
// Source-Inspection-Tests (kein Render, keine Mocks): Datei-Existenz, index.ts-
// Re-Export, Props-Schnittstelle, data-testid-Passthrough, kein ui/-Import in +page.svelte.
//
// RED vor Implementierung:
//   - ConfirmDialog.svelte fehlt → Existenz-Asserts schlagen fehl
//   - molecules/index.ts exportiert ConfirmDialog nicht → Export-Assert schlägt fehl
//   - +page.svelte importiert noch $lib/components/ui/dialog → AC-1-Assert schlägt fehl
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/molecules/confirm_dialog.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
// here = frontend/src/lib/components/molecules — 4 Ebenen hoch = frontend/
const frontendRoot = join(here, '../../../..');
const read = (rel: string) => readFileSync(join(frontendRoot, rel), 'utf-8');
const readHere = (f: string) => readFileSync(join(here, f), 'utf-8');
const has = (rel: string) => existsSync(join(frontendRoot, rel));

const MOLECULE_DIR = 'src/lib/components/molecules';
const PAGE_FILE = 'src/routes/trips/[id]/+page.svelte';

// --- AC-1: ConfirmDialog.svelte existiert in molecules/ ---

test('#478 AC-1a: ConfirmDialog.svelte existiert in molecules/', () => {
	assert.ok(
		has(`${MOLECULE_DIR}/ConfirmDialog.svelte`),
		'molecules/ConfirmDialog.svelte fehlt — noch nicht implementiert'
	);
});

// --- AC-1: ConfirmDialog wird aus molecules/index.ts exportiert ---

test('#478 AC-1b: molecules/index.ts exportiert ConfirmDialog', () => {
	const idx = readHere('index.ts');
	assert.ok(
		/\bConfirmDialog\b/.test(idx),
		'molecules/index.ts enthält keinen ConfirmDialog-Export'
	);
});

// --- AC-1: ConfirmDialog.svelte nutzt ui/dialog intern (nicht atoms direkt) ---

test('#478 AC-1c: ConfirmDialog.svelte kapselt ui/dialog intern', () => {
	const src = read(`${MOLECULE_DIR}/ConfirmDialog.svelte`);
	assert.ok(
		/\$lib\/components\/ui\/dialog/.test(src),
		'ConfirmDialog.svelte nutzt ui/dialog nicht — Bits-UI-Fundament fehlt'
	);
});

// --- AC-1: ConfirmDialog.svelte hat alle geforderten Props ---

test('#478 AC-1d: ConfirmDialog.svelte deklariert alle geforderten Props', () => {
	const src = read(`${MOLECULE_DIR}/ConfirmDialog.svelte`);
	const requiredProps = ['open', 'title', 'description', 'confirmLabel', 'onConfirm', 'onCancel', 'onOpenChange'];
	for (const prop of requiredProps) {
		assert.ok(
			new RegExp(`\\b${prop}\\b`).test(src),
			`ConfirmDialog.svelte: Prop "${prop}" fehlt`
		);
	}
});

// --- AC-1: ConfirmDialog.svelte nutzt Btn aus atoms (keine Inline-Buttons) ---

test('#478 AC-1e: ConfirmDialog.svelte importiert Btn aus atoms/', () => {
	const src = read(`${MOLECULE_DIR}/ConfirmDialog.svelte`);
	assert.ok(
		/import\b[^;]*\bBtn\b[^;]*\bfrom\b/.test(src),
		'ConfirmDialog.svelte: Btn wird nicht aus atoms/ importiert'
	);
});

// --- AC-2: +page.svelte hat keinen direkten ui/-Import mehr ---

test('#478 AC-2: +page.svelte hat keinen direkten $lib/components/ui/-Import', () => {
	const src = read(PAGE_FILE);
	const uiImports = src
		.split('\n')
		.filter(line => /import\b/.test(line) && /\$lib\/components\/ui\//.test(line));
	assert.strictEqual(
		uiImports.length,
		0,
		`+page.svelte hat noch direkte ui/-Importe:\n${uiImports.join('\n')}`
	);
});

// --- AC-2: +page.svelte importiert ConfirmDialog aus molecules ---

test('#478 AC-2b: +page.svelte importiert ConfirmDialog aus molecules', () => {
	const src = read(PAGE_FILE);
	assert.ok(
		/\bConfirmDialog\b/.test(src) && /\$lib\/components\/molecules/.test(src),
		'+page.svelte importiert ConfirmDialog nicht aus $lib/components/molecules'
	);
});

// --- AC-2: data-testids bleiben erhalten ---

test('#478 AC-2c: data-testids für Archive-Dialog bleiben erhalten', () => {
	const src = read(PAGE_FILE);
	const archiveTestids = [
		'trip-detail-archive-confirm-dialog',
		'trip-detail-archive-confirm-cancel',
		'trip-detail-archive-confirm-yes',
	];
	for (const testid of archiveTestids) {
		assert.ok(
			src.includes(testid),
			`+page.svelte: data-testid "${testid}" fehlt nach Migration`
		);
	}
});

test('#478 AC-2d: data-testids für Delete-Dialog bleiben erhalten', () => {
	const src = read(PAGE_FILE);
	const deleteTestids = [
		'trip-detail-delete-confirm-dialog',
		'trip-detail-delete-confirm-cancel',
		'trip-detail-delete-confirm-yes',
	];
	for (const testid of deleteTestids) {
		assert.ok(
			src.includes(testid),
			`+page.svelte: data-testid "${testid}" fehlt nach Migration`
		);
	}
});
