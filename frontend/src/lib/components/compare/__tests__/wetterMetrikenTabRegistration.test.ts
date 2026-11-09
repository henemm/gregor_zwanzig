// TDD RED — Issue #1311, Scheibe C1 von Epic #1301: neuer Tab „Wetter-Metriken"
// zwischen Orte und Wertebereiche im Ortsvergleich-Editor.
//
// Spec: docs/specs/modules/compare_weather_metrics_tab.md § AC-1, Dependencies
//   (subscriptionTabs.ts)
//
// Issue #2794 S3a (Spec feat_2794_s3a_teil2_leiste.md AC-2/AC-5): Wetter-Metriken und Wertebereiche
// gehen im Reiter „Wetter" (Kennung `wetter`) auf, Alarme im Reiter „Zustellung". Die Alt-Kennung
// `wetter-metriken` bleibt als Eingabe gueltig und fuehrt in den Reiter Wetter.
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

describe('AC-1: COMPARE_TABS registriert den Reiter "Wetter"', () => {
	test('enthaelt einen Eintrag mit value="wetter"', () => {
		const entry = COMPARE_TABS.find((t) => t.value === 'wetter');
		assert.ok(entry, 'AC-1 FAIL: COMPARE_TABS hat keinen Eintrag "wetter"');
	});

	test('Label lautet "Wetter"', () => {
		const entry = COMPARE_TABS.find((t) => t.value === 'wetter');
		assert.equal(entry?.label, 'Wetter', 'AC-1 FAIL: falsches oder fehlendes Label fuer den Reiter');
	});

	test('liegt zwischen "orte" und "zustellung" (Dependencies: subscriptionTabs.ts)', () => {
		const values = COMPARE_TABS.map((t) => t.value);
		const orteIdx = values.indexOf('orte');
		const zustellungIdx = values.indexOf('zustellung');
		const wetterIdx = values.indexOf('wetter');
		assert.notEqual(orteIdx, -1, 'Vorbedingung verletzt: "orte" fehlt in COMPARE_TABS');
		assert.notEqual(zustellungIdx, -1, 'Vorbedingung verletzt: "zustellung" fehlt in COMPARE_TABS');
		assert.ok(
			wetterIdx > orteIdx && wetterIdx < zustellungIdx,
			`AC-1 FAIL: "wetter" (Index ${wetterIdx}) liegt nicht zwischen "orte" (${orteIdx}) ` +
				`und "zustellung" (${zustellungIdx})`
		);
	});

	test('COMPARE_TAB_VALUES enthaelt "wetter"; die Alt-Kennung "wetter-metriken" fuehrt dorthin', () => {
		assert.ok(COMPARE_TAB_VALUES.includes('wetter'), 'AC-1 FAIL: COMPARE_TAB_VALUES kennt "wetter" nicht');
		assert.equal(resolveCompareTab('wetter'), 'wetter');
		assert.ok(!COMPARE_TAB_VALUES.includes('wetter-metriken'), '"wetter-metriken" ist kein Reiter mehr');
		assert.equal(
			resolveCompareTab('wetter-metriken'),
			'wetter',
			'AC-5 FAIL: die Alt-Kennung "wetter-metriken" faellt nicht in den Reiter Wetter'
		);
	});

	// Regressions-Anker: die Bestands-Tabs (inkl. Reihenfolge relativ zueinander).
	// Issue #1360: 'layout' ist aufgeloest. #1743 (AC-2): Versand und Vorschau sind keine Reiter mehr.
	// #2794 S3a: vier Reiter.
	test('Regressions-Anker: genau die 4 Reiter Uebersicht · Orte · Wetter · Zustellung', () => {
		const values = COMPARE_TABS.map((t) => t.value);
		assert.deepEqual(values, ['uebersicht', 'orte', 'wetter', 'zustellung']);
		for (const v of ['versand', 'vorschau', 'wertebereiche', 'alarme']) {
			assert.ok(!values.includes(v), `"${v}" darf kein Reiter mehr sein`);
		}
	});
});
