// Issue #1265 Fix-Loop 1 — Adversary Finding F005 (CRITICAL)
//
// Spec: docs/specs/modules/issue_1265_prod_testdata_cleanup.md, AC-5.
//
// F005: `frontend/e2e/global.setup.ts` ist NICHT der einzige
// datenanlegende Playwright-Einstiegspunkt — mindestens 20 weitere
// `*.staging.setup.ts`-Dateien binden sich über eigene
// `playwright.*.staging.config.ts`-Configs als eigenständige `setup`-
// Projekte ein und seeden Daten via API, komplett unabhängig von
// `global.setup.ts`. Dieser Struktur-Test scannt ALLE
// `frontend/e2e/*setup*.ts`-Dateien, die eine Base-URL verwenden
// (`process.env.GZ_SVELTE_BASE` bzw. `baseURL`), und FAILT, wenn eine
// davon `assertNotProdBaseURL` weder importiert noch aufruft —
// verhindert künftige Setups ohne Guard. Muster: bestehende
// Source-Scan-Tests wie legacy_wizard_removed.test.ts.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const E2E = join(here, '..', '..', '..', 'e2e'); // frontend/e2e

const read = (p: string) => readFileSync(p, 'utf-8');

test('#1265 F005: jede Setup-Datei mit Base-URL ruft assertNotProdBaseURL vor jeder Base-URL-Nutzung auf', () => {
	const setupFiles = readdirSync(E2E).filter(
		(f) => f.includes('setup') && f.endsWith('.ts') && f !== 'prodUrlGuard.ts'
	);
	assert.ok(setupFiles.length >= 20, `Erwartet >=20 Setup-Dateien, gefunden: ${setupFiles.length}`);

	const missing: string[] = [];
	for (const f of setupFiles) {
		const src = read(join(E2E, f));
		const usesBaseURL = /GZ_SVELTE_BASE|baseURL/.test(src);
		if (!usesBaseURL) continue; // Setup ohne eigene Base-URL-Quelle betrifft F005 nicht
		const hasGuardImport = /assertNotProdBaseURL/.test(src) && /from ['"]\.\/prodUrlGuard['"]/.test(src);
		const hasGuardCall = /assertNotProdBaseURL\(/.test(src);
		if (!hasGuardImport || !hasGuardCall) missing.push(f);
	}

	assert.deepEqual(
		missing,
		[],
		`F005: Setup-Dateien ohne assertNotProdBaseURL-Guard: ${missing.join(', ')}`
	);
});
