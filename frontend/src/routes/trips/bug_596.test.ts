// TDD RED: Bug #596 — Breadcrumb zeigt "MEINE TOUREN" statt "MEINE TRIPS"
//
// Spec:  docs/specs/modules/bug_596_breadcrumb_touren.md
// Datei: frontend/src/lib/components/edit/TripEditView.svelte
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/routes/trips/bug_596.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { join, dirname, resolve } from 'node:path';

const TRIPS_DIR = dirname(fileURLToPath(import.meta.url));
const TRIP_EDIT_VIEW = resolve(TRIPS_DIR, '../../lib/components/edit/TripEditView.svelte');
const FRONTEND_SRC = resolve(TRIPS_DIR, '../..');

test('AC-1: edit-breadcrumb enthält "MEINE TRIPS", nicht "MEINE TOUREN"', () => {
	const src = readFileSync(TRIP_EDIT_VIEW, 'utf-8');
	assert.ok(
		!src.includes('MEINE TOUREN'),
		'TripEditView.svelte enthält noch "MEINE TOUREN" — muss "MEINE TRIPS" sein'
	);
	assert.ok(
		src.includes('MEINE TRIPS'),
		'TripEditView.svelte enthält kein "MEINE TRIPS" im Breadcrumb'
	);
});

test('AC-2: Keine Svelte-Komponente enthält noch "Touren" als Trip-Label (case-insensitiv)', () => {
	const result = execSync(
		'grep -ri "meine touren" . --include="*.svelte" || true',
		{ cwd: FRONTEND_SRC, encoding: 'utf-8' }
	);
	assert.strictEqual(
		result.trim(),
		'',
		`Svelte-Dateien enthalten noch "Meine Touren" / "MEINE TOUREN":\n${result}`
	);
});
