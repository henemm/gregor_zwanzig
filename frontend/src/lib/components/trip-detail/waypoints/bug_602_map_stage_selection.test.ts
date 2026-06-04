// HINWEIS: Die TDD-Tests für Bug #602 sind als Playwright-E2E-Tests implementiert.
// Verhaltensnachweis-Pflicht (CLAUDE.md): Frontend-Bugs müssen via Playwright
// gegen Staging verifiziert werden, nicht durch Dateiinhalt-Checks.
//
// Echte Tests: frontend/e2e/bug-602-map-stage-selection.spec.ts
//
// Ausführung:
//   cd frontend && npx playwright test bug-602-map-stage-selection.spec.ts

// doc-compliance-test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

test('Pflicht-Verweis: Playwright-E2E-Testdatei für Bug #602 existiert', () => {
	const e2eTest = join(
		fileURLToPath(new URL('../../../../..', import.meta.url)),
		'e2e/bug-602-map-stage-selection.spec.ts'
	);
	assert.ok(
		existsSync(e2eTest),
		'frontend/e2e/bug-602-map-stage-selection.spec.ts muss existieren — Verhaltensnachweis für Bug #602'
	);
});
