// doc-compliance-test (Ratschen-Test: liest die Allowlist als DATEN)
//
// Issue #2661 (i18n F12, Epic #2644) — AC-1: nach F1–F11 und F12 ist die
// Frontend-Allowlist leer und bleibt leer. Ein neuer hartkodierter Nutzertext
// faellt damit sofort in der Ratsche (keine_hartkodierten_nutzertexte.test.ts)
// als Treffer ohne Eintrag auf; ein Ausweg ueber einen neuen Eintrag ist rot.
// Spec: docs/specs/modules/i18n_f12_frontend_abschluss_2661.md
//
//   cd frontend && npm test -- src/lib/i18n/__tests__/hardcode_allowlist_leer.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { pruefeVerzeichnis } from './hardcode_scan.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const ROH = readFileSync(join(HIER, '..', 'hardcode_allowlist.json'), 'utf8');

test('AC-1: hardcode_allowlist.json lautet exakt []', () => {
	assert.deepEqual(JSON.parse(ROH), []);
	assert.equal(ROH.trim(), '[]');
});

test('AC-1: ohne Allowlist hat frontend/src keinen hartkodierten Nutzertext', () => {
	const ergebnis = pruefeVerzeichnis(join(HIER, '..', '..', '..'), []);
	assert.deepEqual(ergebnis.ohneEintrag, [], ergebnis.ohneEintrag.join('\n'));
});
