// Auth-Guard — publicPaths-Allowlist (hooks.server.ts)
//
// Spec: docs/specs/modules/fix_1219_verify_flow_2b.md — Staging-Fund: /verify-email
// fehlte in publicPaths, nicht eingeloggte Mail-Klicker landeten auf /login.
//
// `publicPaths` ist lokal in `handle` gekapselt (kein Export) — daher
// Source-Sentinel statt echtem Import (mock-frei: liest die reale Datei).
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/hooks.server.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(__dirname, 'hooks.server.ts'), 'utf-8');

function extractPublicPaths(source: string): string[] {
	const match = source.match(/const publicPaths = \[([^\]]*)\]/);
	assert.ok(match, 'publicPaths-Array nicht gefunden in hooks.server.ts');
	return [...match![1].matchAll(/'([^']+)'/g)].map((m) => m[1]);
}

// doc-compliance-test
test('publicPaths enthaelt /verify-email (Mail-Klicker duerfen nicht auf /login landen)', () => {
	// GIVEN: der Source-Text von hooks.server.ts
	// WHEN: das publicPaths-Array extrahiert wird
	// THEN: enthaelt es /verify-email
	const paths = extractPublicPaths(src);
	assert.ok(
		paths.includes('/verify-email'),
		`'/verify-email' fehlt in publicPaths: ${JSON.stringify(paths)}`
	);
});

// doc-compliance-test
test('publicPaths enthaelt weiterhin /reset-password (Gegenprobe gegen versehentliches Entfernen)', () => {
	// GIVEN: der Source-Text von hooks.server.ts
	// WHEN: das publicPaths-Array extrahiert wird
	// THEN: enthaelt es weiterhin /reset-password
	const paths = extractPublicPaths(src);
	assert.ok(
		paths.includes('/reset-password'),
		`'/reset-password' fehlt in publicPaths: ${JSON.stringify(paths)}`
	);
});
