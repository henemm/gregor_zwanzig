// Public-Route-Allowlists — hooks.server.ts (Auth-Guard) + +layout.svelte
// (App-Chrome).
//
// Spec: docs/specs/modules/fix_1219_verify_flow_2b.md — Staging-/Fresh-Eyes-Fund:
// /verify-email fehlte in ZWEI getrennten Allowlists. hooks.server.ts:
// publicPaths steuert den Auth-Redirect (fehlend → Redirect auf /login).
// +layout.svelte: publicPages steuert die App-Chrome (fehlend → Sidebar/TopBar
// rendern trotz Standalone-Auth-Seite).
//
// Beide Arrays sind lokal gekapselt (kein Export) — daher Source-Sentinel
// statt echtem Import (mock-frei: liest die realen Dateien).
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
const layoutSrc = readFileSync(join(__dirname, 'routes', '+layout.svelte'), 'utf-8');

function extractPublicPaths(source: string): string[] {
	const match = source.match(/const publicPaths = \[([^\]]*)\]/);
	assert.ok(match, 'publicPaths-Array nicht gefunden in hooks.server.ts');
	return [...match![1].matchAll(/'([^']+)'/g)].map((m) => m[1]);
}

function extractPublicPages(source: string): string[] {
	const match = source.match(/const publicPages = \[([^\]]*)\]/);
	assert.ok(match, 'publicPages-Array nicht gefunden in +layout.svelte');
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

// doc-compliance-test
test('+layout.svelte publicPages enthaelt /verify-email UND /reset-password (App-Chrome-Allowlist)', () => {
	// GIVEN: der Source-Text von +layout.svelte
	// WHEN: das publicPages-Array extrahiert wird
	// THEN: enthaelt es /verify-email (steuert isLogin -> Standalone-Rendering
	//   ohne Sidebar/TopAppBar/BottomNav) sowie weiterhin /reset-password als
	//   Gegenprobe gegen versehentliches Entfernen
	const pages = extractPublicPages(layoutSrc);
	assert.ok(
		pages.includes('/verify-email'),
		`'/verify-email' fehlt in publicPages (+layout.svelte): ${JSON.stringify(pages)}`
	);
	assert.ok(
		pages.includes('/reset-password'),
		`'/reset-password' fehlt in publicPages (+layout.svelte): ${JSON.stringify(pages)}`
	);
});
