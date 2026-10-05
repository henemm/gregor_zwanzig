// TDD RED — Issue #1311, Scheibe C1 von Epic #1301: neuer Tab „Wetter-Metriken"
// zwischen Orte und Wertebereiche im Ortsvergleich-Editor.
//
// Spec: docs/specs/modules/compare_weather_metrics_tab.md § AC-1, Dependencies
//   (subscriptionTabs.ts)
//
// RED-Erwartung (vor Implementation): COMPARE_TABS enthaelt heute 7 Tabs ohne
// 'wetter-metriken' — jede Assertion hier schlaegt fehl, bis der Tab
// registriert ist.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/compare/__tests__/wetterMetrikenTabRegistration.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { subscriptionTabs, resolveTab } from '../../shared/subscriptionTabs.ts';

// Feature #2287: die Vergleich-Reiterleiste kommt aus dem geteilten Modul
// (`compareTabsResolve.ts` entfaellt); die Pruefungen bleiben inhaltlich gleich.
const COMPARE_TABS = subscriptionTabs('vergleich').map((t) => ({ value: t.id, label: t.label }));
const COMPARE_TAB_VALUES: readonly string[] = COMPARE_TABS.map((t) => t.value);
const resolveCompareTab = (v: string): string => resolveTab('vergleich', v).tab;

describe('AC-1: COMPARE_TABS registriert den neuen Tab "Wetter-Metriken"', () => {
	test('enthaelt einen Eintrag mit value="wetter-metriken"', () => {
		const entry = COMPARE_TABS.find((t) => t.value === 'wetter-metriken');
		assert.ok(
			entry,
			'AC-1 FAIL: COMPARE_TABS hat keinen Eintrag "wetter-metriken" — der neue Tab ist noch nicht registriert'
		);
	});

	test('Label lautet "Wetter-Metriken"', () => {
		const entry = COMPARE_TABS.find((t) => t.value === 'wetter-metriken');
		assert.equal(
			entry?.label,
			'Wetter-Metriken',
			'AC-1 FAIL: falsches oder fehlendes Label fuer den neuen Tab'
		);
	});

	test('liegt zwischen "orte" und "wertebereiche" (Dependencies: subscriptionTabs.ts)', () => {
		const values = COMPARE_TABS.map((t) => t.value);
		const orteIdx = values.indexOf('orte');
		const wertebereicheIdx = values.indexOf('wertebereiche');
		const wetterIdx = values.indexOf('wetter-metriken');
		assert.notEqual(orteIdx, -1, 'Vorbedingung verletzt: "orte" fehlt in COMPARE_TABS');
		assert.notEqual(wertebereicheIdx, -1, 'Vorbedingung verletzt: "wertebereiche" fehlt in COMPARE_TABS');
		assert.ok(
			wetterIdx > orteIdx && wetterIdx < wertebereicheIdx,
			`AC-1 FAIL: "wetter-metriken" (Index ${wetterIdx}) liegt nicht zwischen "orte" (${orteIdx}) ` +
				`und "wertebereiche" (${wertebereicheIdx})`
		);
	});

	test('COMPARE_TAB_VALUES enthaelt "wetter-metriken" (resolveCompareTab akzeptiert ihn)', () => {
		assert.ok(
			COMPARE_TAB_VALUES.includes('wetter-metriken'),
			'AC-1 FAIL: COMPARE_TAB_VALUES kennt "wetter-metriken" nicht'
		);
		assert.equal(
			resolveCompareTab('wetter-metriken'),
			'wetter-metriken',
			'AC-1 FAIL: resolveCompareTab faellt fuer "wetter-metriken" auf "uebersicht" zurueck (Tab nicht registriert)'
		);
	});

	// Regressions-Anker: die Bestands-Tabs (inkl. Reihenfolge relativ zueinander)
	// bleiben unangetastet — nur EIN neuer Eintrag wird eingefuegt.
	// Issue #1360: 'layout' ist aus dem Anker entfernt, der Reiter ist aufgeloest
	// (Spec compare_layout_tab_dissolution, AC-1).
	test('Regressions-Anker: alle 6 Bestands-Tabs sind weiterhin vorhanden', () => {
		const values = COMPARE_TABS.map((t) => t.value);
		for (const v of ['uebersicht', 'orte', 'wertebereiche', 'alarme', 'versand', 'vorschau']) {
			assert.ok(values.includes(v), `Regression: Bestands-Tab "${v}" fehlt in COMPARE_TABS`);
		}
	});
});
