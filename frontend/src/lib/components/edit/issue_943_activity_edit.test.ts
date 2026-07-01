// HINWEIS: Die Verhaltens-Tests für Issue #943 (Aktivitätstyp im Edit-Modus
// änderbar & persistent) sind als Playwright-E2E-Tests implementiert.
//
// Verhaltensnachweis-Pflicht (CLAUDE.md): Frontend-Verhalten muss via Playwright
// gegen einen echten Server als eingeloggter Nutzer verifiziert werden — nicht
// durch Dateiinhalt-Checks und nicht mit Mocks. Im Unit-Test-Kontext (node:test)
// steht kein Server zur Verfügung, daher liegt der Verhaltensnachweis im
// Playwright-Spec.
//
// Echte Tests (alle 3 ACs): frontend/e2e/issue-943-activity-edit.spec.ts
//   AC-1: Dropdown data-testid="edit-activity-dropdown" sichtbar, Wert vorausgewählt
//   AC-2: Wechsel + Speichern → nach Reload korrekt persistiert
//   AC-3: Wechsel wirkt reaktiv auf Etappen-Ankunftszeiten (ohne Seitenneuladen)
//
// Ausführung:
//   cd frontend && npx playwright test issue-943-activity-edit.spec.ts

// doc-compliance-test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const frontendRoot = fileURLToPath(new URL('../../../..', import.meta.url));

test('Pflicht-Verweis: Playwright-E2E-Testdatei für Issue #943 existiert', () => {
	const e2eTest = join(frontendRoot, 'e2e/issue-943-activity-edit.spec.ts');
	assert.ok(
		existsSync(e2eTest),
		'frontend/e2e/issue-943-activity-edit.spec.ts muss existieren — Verhaltensnachweis für Issue #943'
	);
});

test('Pflicht-Verweis: E2E-Spec deckt alle drei ACs (AC-1/AC-2/AC-3) ab', () => {
	const e2eTest = join(frontendRoot, 'e2e/issue-943-activity-edit.spec.ts');
	const src = readFileSync(e2eTest, 'utf8');
	for (const ac of ['AC-1:', 'AC-2:', 'AC-3:']) {
		assert.ok(src.includes(ac), `E2E-Spec muss ${ac} adressieren`);
	}
	// Das AC-Ziel-Element (Dropdown) muss über die vereinbarte testid angesteuert werden.
	assert.ok(
		src.includes('edit-activity-dropdown'),
		'E2E-Spec muss das Dropdown über data-testid="edit-activity-dropdown" ansteuern'
	);
});
