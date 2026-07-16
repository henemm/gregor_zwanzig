// TDD RED: Issue #1265 — E2E-Prod-Sperre (Teil D)
//
// Spec: docs/specs/modules/issue_1265_prod_testdata_cleanup.md, AC-5.
//
// `frontend/e2e/global.setup.ts` (und damit alle datenanlegenden Specs) soll
// hart abbrechen, wenn die Base-URL auf die Prod-Domain
// (gregor20.henemm.com ohne staging.-Präfix) zeigt.
//
// Dieser Test ist ABSICHTLICH ROT: `frontend/e2e/prodUrlGuard.ts` und die
// darin erwartete Funktion `assertNotProdBaseURL` existieren noch nicht.
// Erwarteter Fehler heute: ERR_MODULE_NOT_FOUND beim Import.
//
// Ausführen (aus frontend/):
//   npm test -- "src/lib/__tests__/e2e_prod_url_guard.test.ts"

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { assertNotProdBaseURL } from '../../../e2e/prodUrlGuard.ts';

test('#1265 AC-5: Prod-Domain (ohne staging.-Präfix) wirft', () => {
	assert.throws(() => assertNotProdBaseURL('https://gregor20.henemm.com'));
});

test('#1265 AC-5: Staging-Domain läuft unverändert an (kein Throw)', () => {
	assert.doesNotThrow(() => assertNotProdBaseURL('https://staging.gregor20.henemm.com'));
});

test('#1265 AC-5: lokale Dev-URL läuft unverändert an (kein Throw)', () => {
	assert.doesNotThrow(() => assertNotProdBaseURL('http://localhost:5173'));
});
