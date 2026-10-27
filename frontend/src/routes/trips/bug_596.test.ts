// TDD RED: Bug #596 — Breadcrumb zeigt "MEINE TOUREN" statt "MEINE TRIPS"
//
// Spec:  docs/specs/modules/bug_596_breadcrumb_touren.md
// (AC-1 entfiel mit TripEditView, #2277 S3; AC-2 bleibt einziger Waechter)
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/routes/trips/bug_596.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { join, dirname, resolve } from 'node:path';

const TRIPS_DIR = dirname(fileURLToPath(import.meta.url));
const FRONTEND_SRC = resolve(TRIPS_DIR, '../..');

test('AC-2: Keine Svelte-Komponente enthält noch "Trips" als Trip-Label (case-insensitiv)', () => {
	const result = execSync(
		'grep -ri "meine touren" . --include="*.svelte" || true',
		{ cwd: FRONTEND_SRC, encoding: 'utf-8' }
	);
	assert.strictEqual(
		result.trim(),
		'',
		`Svelte-Dateien enthalten noch "Meine Trips" / "MEINE TOUREN":\n${result}`
	);
});
