// TDD RED — Issue #1261 Teil (b): Compare-Editor Autospeichern, #1234-Gesten-
// Gate kombiniert mit dem Dirty-Zustand des Editors.
//
// Spec: docs/specs/modules/issue_1261_compare_edit_autosave.md
//   § Implementation Details (b).3, § Acceptance Criteria AC-5/AC-7
//
// Vorbild (wiederverwendet, NICHT neu implementiert):
//   trip-detail/weatherSaveGate.ts `weatherSaveGate({catalogLoaded, userTouched})`
//
// `computeCompareAutoSaveAction` kombiniert das bestehende Gesten-Gate mit dem
// `dirty`-Flag des Compare-Editors: nur wenn tatsächlich etwas geändert wurde
// UND das Gesten-Gate "save" liefert, darf automatisch geschrieben werden.
// Ohne echte Nutzergeste (AC-7) oder ohne geladenen Katalog bleibt es bei
// "skip" — exakt die #1234-Fehlerklasse (GR221-Datenverlust durch
// Hydrations-Effekte, die ungewollt schreiben).
//
// Das Modul `../compareAutosave` existiert noch NICHT → der Import wirft
// einen Modul-Resolve-Fehler und alle Tests scheitern (RED).
//
// Reine Verhaltenstests (echter Funktionsaufruf, KEIN Mock, KEINE
// Datei-Inhalt-Prüfung).
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compareAutosaveGate.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

// Direkter Funktionsaufruf — kein Mock, kein DOM.
const { computeCompareAutoSaveAction } = await import('../compareAutosave.ts');

describe('AC-5: dirty + echte Nutzergeste + Katalog geladen → "save"', () => {
	test('dirty=true, userTouched=true, catalogLoaded=true → "save"', () => {
		const action = computeCompareAutoSaveAction({ dirty: true, userTouched: true, catalogLoaded: true });
		assert.equal(action, 'save', 'eine echte Nutzeränderung mit Dirty-Zustand muss automatisch speichern');
	});
});

describe('AC-7: dirty ohne Nutzergeste → "skip" (kein Schreibzugriff ohne echte Nutzeraktion)', () => {
	test('dirty=true, userTouched=false, catalogLoaded=true → "skip"', () => {
		const action = computeCompareAutoSaveAction({ dirty: true, userTouched: false, catalogLoaded: true });
		assert.equal(
			action,
			'skip',
			'AC-7: ohne echte Nutzergeste darf trotz dirty=true kein PUT ausgelöst werden — sonst würden ' +
				'Hydrations-Effekte der geteilten Tabs (z.B. CorridorEditor-Dual-Write) ungewollt schreiben'
		);
	});
});

describe('nicht dirty → "skip" (nichts zu speichern, auch bei vorhandener Geste)', () => {
	test('dirty=false, userTouched=true, catalogLoaded=true → "skip"', () => {
		const action = computeCompareAutoSaveAction({ dirty: false, userTouched: true, catalogLoaded: true });
		assert.equal(action, 'skip', 'ohne geänderten Zustand gibt es nichts zu speichern');
	});
});

describe('Katalog nicht geladen → "skip" (Gesten-Gate-Zeile 1, unabhängig von dirty/userTouched)', () => {
	test('dirty=true, userTouched=true, catalogLoaded=false → "skip"', () => {
		const action = computeCompareAutoSaveAction({ dirty: true, userTouched: true, catalogLoaded: false });
		assert.equal(
			action,
			'skip',
			'ohne geladenen Katalog darf niemals gespeichert werden — analog weatherSaveGate Zeile 1'
		);
	});
});
