// TDD RED — Issue #1299 (Scheibe C2 von Epic #1301): Fehlerpfad-Rollback fuer
// den Hub-Layout-Tab (Stundenverlauf-Metriken + "Stundenverlauf ein/aus").
//
// Spec: docs/specs/modules/compare_hub_hourly_metrics.md § AC-6
//
// `hourlyMetricKeys`/`hourlyEnabled` sind EXKLUSIV Layout-Tab-Eigentum (anders
// als die H3-Kreuzeffekt-Felder im Alarme-Snapshot, s. `rollbackAlarmSnapshot`)
// — deshalb reicht direkte Feldzuweisung statt diff-basiertem Rollback (Spec
// § Implementation Details Abschnitt 2). Dieser Test beweist, dass NUR die
// beiden Layout-Felder veraendert werden, alle anderen Felder desselben
// `wizardState`-Objekts unangetastet bleiben.
//
// RED-Erwartung (vor Implementierung):
//   `rollbackLayoutSnapshot` existiert in `compareHubWizardBridge.ts` noch
//   NICHT — der Import schlaegt fehl ("does not provide an export named
//   'rollbackLayoutSnapshot'"), das gesamte File kann nicht laufen. Das IST
//   der RED-Beweis fuer AC-6.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_hub_layout_rollback.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { rollbackLayoutSnapshot, type LayoutSnapshot } from '../compareHubWizardBridge.ts';

/** State-Stub analog dem echten `wizardState` (CompareWizardState-Instanz) —
 * traegt neben den beiden Layout-Feldern auch unrelated Felder aus anderen
 * Hub-Tabs (Idealwerte/Versand), um zu beweisen, dass der Rollback NICHT ueber
 * das gesamte Objekt hinweggeht. */
function makeStateWithUnrelatedFields(): {
	hourlyMetricKeys: string[];
	hourlyEnabled: boolean;
	activeMetricKeys: string[];
	corridors: { metric_id: string; min?: number; max?: number }[];
	sendTelegram: boolean;
} {
	return {
		hourlyMetricKeys: ['temp_c', 'wind_kmh'],
		hourlyEnabled: false,
		activeMetricKeys: ['wind_max_kmh', 'temp_max_c'],
		corridors: [{ metric_id: 'wind_max_kmh', min: 0, max: 40 }],
		sendTelegram: true
	};
}

describe('C2 AC-6: rollbackLayoutSnapshot — nur Layout-Felder zuruecksetzen', () => {
	test('hourlyMetricKeys/hourlyEnabled werden exakt auf "before" zurueckgesetzt', () => {
		// GIVEN: ein State mit abweichenden Layout-Feldern (in-flight geaendert)
		// WHEN: rollbackLayoutSnapshot(state, before) nach einem PUT-Fehler aufgerufen wird
		// THEN: state.hourlyMetricKeys/state.hourlyEnabled entsprechen exakt "before"
		// RED heute: Import schlaegt fehl (rollbackLayoutSnapshot existiert nicht).
		const state = makeStateWithUnrelatedFields();
		const before: LayoutSnapshot = { hourlyMetricKeys: ['temp_c'], hourlyEnabled: true };

		rollbackLayoutSnapshot(state, before);

		assert.deepEqual(state.hourlyMetricKeys, ['temp_c']);
		assert.equal(state.hourlyEnabled, true);
	});

	test('unrelated Felder (activeMetricKeys, corridors, sendTelegram) bleiben unveraendert', () => {
		// GIVEN: derselbe State wie oben, mit Fremd-Feldern aus Idealwerte-/Versand-Tab
		// WHEN: rollbackLayoutSnapshot aufgerufen wird
		// THEN: alle unrelated Felder sind wertgleich zum Zustand vor dem Aufruf —
		// der Layout-Rollback darf NIE in andere Tabs hineinregieren.
		// RED heute: Import schlaegt fehl.
		const state = makeStateWithUnrelatedFields();
		const before: LayoutSnapshot = { hourlyMetricKeys: ['temp_c'], hourlyEnabled: true };

		const expectedActiveMetricKeys = [...state.activeMetricKeys];
		const expectedCorridors = JSON.parse(JSON.stringify(state.corridors));
		const expectedSendTelegram = state.sendTelegram;

		rollbackLayoutSnapshot(state, before);

		assert.deepEqual(
			state.activeMetricKeys,
			expectedActiveMetricKeys,
			'activeMetricKeys darf vom Layout-Rollback nicht veraendert werden'
		);
		assert.deepEqual(state.corridors, expectedCorridors, 'corridors darf vom Layout-Rollback nicht veraendert werden');
		assert.equal(
			state.sendTelegram,
			expectedSendTelegram,
			'sendTelegram darf vom Layout-Rollback nicht veraendert werden'
		);
	});
});
