// TDD RED — Issue #1250 Scheibe 0: Legacy-CompareSubscription-Stack stilllegen (#1131).
// Spec: docs/specs/modules/issue_1250_briefing_subscription.md § AC-3
//
// AC-3: `wiz.save()`/`wiz.toggleEnabled()` (compareWizardState.svelte.ts:85,161) sind
// FE-Totcode — sie schreiben in den Legacy-Store `/api/subscriptions`, der mit
// Scheibe 0 abgeschafft wird. Dieser Test ist eine echte Verhaltens-Assertion
// (Prototype-Inspektion der importierten Klasse), KEIN Dateiinhalt-Grep.
//
// Direkt-Import von compareWizardState.svelte.ts (statt readFileSync-Grep wie in
// issue_683_wizard_remove.test.ts) ist moeglich, weil Object.getOwnPropertyNames
// auf dem Prototype arbeitet — die $state-Runen-Felder werden dabei NICHT
// instanziiert (kein Svelte-Runtime-Kontext noetig), nur die Methoden-Namen auf
// dem Prototype werden gelesen.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/wizard_state_no_legacy_save.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { CompareWizardState } from '../compareWizardState.svelte.ts';

describe('CompareWizardState — Legacy-Save-Totcode entfernt (AC-3, Issue #1250 Scheibe 0)', () => {
	const protoMethods = Object.getOwnPropertyNames(CompareWizardState.prototype);

	test('besitzt KEINE save()-Methode mehr (schrieb in Legacy-Store /api/subscriptions)', () => {
		assert.strictEqual(
			protoMethods.includes('save'),
			false,
			`CompareWizardState.prototype.save muss entfernt sein (Legacy-Totcode), ` +
				`gefundene Methoden: ${protoMethods.join(', ')}`
		);
	});

	test('besitzt KEINE toggleEnabled()-Methode mehr (schrieb in Legacy-Store /api/subscriptions)', () => {
		assert.strictEqual(
			protoMethods.includes('toggleEnabled'),
			false,
			`CompareWizardState.prototype.toggleEnabled muss entfernt sein (Legacy-Totcode), ` +
				`gefundene Methoden: ${protoMethods.join(', ')}`
		);
	});

	// Gegenprobe: der aktive, auf ComparePreset zielende Anlege-Pfad bleibt
	// erhalten — dieser Test darf durch Scheibe 0 NICHT rot werden.
	//
	// Issue #2276 Scheibe S6a (AC-4): Die Assertion auf `saveComparePreset` ist
	// hier ENTFALLEN. Die Methode hatte beim Stand `73f504c9` null Aufrufer und
	// wird als Totcode zurueckgebaut (Befund 5 der Analyse; Nachweis in
	// totcode_rueckbau_speicherweg.test.ts). Die eigentliche #1250-Zusicherung
	// liegt in Test 1 und Test 2 oben — die sind UNVERAENDERT und bewachen
	// weiterhin, dass `save()`/`toggleEnabled()` (Legacy-Store
	// /api/subscriptions) nicht zurueckkehren. `saveNewPreset` bleibt gefordert:
	// der Anlege-Pfad (POST /api/compare/presets) ist aktiv.
	test('behaelt saveNewPreset() (aktiver ComparePreset-Anlege-Pfad)', () => {
		assert.ok(
			protoMethods.includes('saveNewPreset'),
			'saveNewPreset() muss erhalten bleiben (zielt auf /api/compare/presets)'
		);
	});
});
