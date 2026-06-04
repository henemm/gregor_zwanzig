// TDD RED — Bug #591: "Pausieren"-Button ohne Funktion
//
// Spec: docs/specs/bugfix/bug_591_pausieren_button.md
//
// Source-Inspection-Tests: prüfen Soll-Zustand nach Implementation.
//
// RED-Erwartung (vor Fix):
//   AC-3: FAIL — status wird aus unveränderlichem preset-Prop abgeleitet,
//                nicht aus localSchedule
//   AC-4: FAIL — catch-Block in handleToggleActive ist leer, kein console.error
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/bug_591_pausieren_button.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const COMPARE_DIR = join(dirname(fileURLToPath(import.meta.url)), '..');
const TABS_FILE = join(COMPARE_DIR, 'CompareTabs.svelte');

function src(): string {
	assert.ok(existsSync(TABS_FILE), 'CompareTabs.svelte existiert nicht');
	return readFileSync(TABS_FILE, 'utf-8');
}

// ── AC-3: Status reaktiv auf localSchedule ─────────────────────────────────

describe('AC-3: status leitet sich aus localSchedule ab (nicht aus preset)', () => {
	test('status-Ableitung enthält localSchedule', () => {
		const code = src();
		// Nach dem Fix muss status aus einem Objekt abgeleitet werden das
		// localSchedule enthält, z.B.:
		//   $derived(deriveStatusFromPreset({ ...preset, schedule: localSchedule ... }))
		assert.match(
			code,
			/deriveStatusFromPreset\(\s*\{[^}]*localSchedule/,
			'AC-3 FAIL: status ist nicht auf localSchedule basiert. ' +
			'Erwartet: deriveStatusFromPreset({ ...preset, schedule: localSchedule ... })'
		);
	});

	test('status darf nicht direkt aus unveränderlichem preset abgeleitet werden', () => {
		const code = src();
		// Sicherstellen dass kein einfaches deriveStatusFromPreset(preset) mehr da ist
		// (ohne localSchedule-Einbindung)
		const simpleDerivation = /deriveStatusFromPreset\(\s*preset\s*\)/;
		assert.ok(
			!simpleDerivation.test(code),
			'AC-3 FAIL: status wird noch direkt aus unveränderlichem preset abgeleitet. ' +
			'Nach Fix muss localSchedule einbezogen werden.'
		);
	});
});

// ── AC-4: Fehler-Logging im catch-Block ───────────────────────────────────

describe('AC-4: handleToggleActive loggt Fehler in catch-Block', () => {
	test('catch-Block in handleToggleActive enthält console.error', () => {
		const code = src();
		// Prüft dass nach handleToggleActive ein catch-Block mit console.error existiert
		// mit dem Präfix "[CompareTabs]"
		assert.match(
			code,
			/console\.error\s*\(\s*['"`]\[CompareTabs\]/,
			'AC-4 FAIL: catch-Block in handleToggleActive enthält kein console.error mit ' +
			'Präfix "[CompareTabs]". Fehlschlagende API-Calls sind nicht sichtbar.'
		);
	});
});
