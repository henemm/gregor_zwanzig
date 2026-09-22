// TDD RED — Issue #2276 Scheibe S6f (Epic #2345): Bridge-Umzug. Dieser Teil
// der ehemaligen `compare_hub_wizard_bridge.test.ts` (Issue #1256 Scheibe 6,
// AC-16) testet ausschliesslich `hydrateHubFieldsFromPreset` (vormals
// `hydrateWizardStateFromPreset`), jetzt aus `../compareHubHydration.ts`.
//
// Spec: docs/specs/modules/rework_2276_s6f_bridge_umzug.md — AC-1 (Test-Plan:
//   `compare_hub_wizard_bridge.test.ts` SPLIT + RENAME)
// Vorgaenger-Spec (Funktions-API/Zusicherungen unveraendert):
//   docs/specs/modules/issue_1256_compare_ui_rewire.md § Scheibe 6 (AC-16)
//
// Ist: `CorridorEditor.svelte` liest im vergleich-Kontext
// `getContext('compare-wizard-state')` und erwartet dort GENAU 6 Felder
// (isEditMode, corridors, activityProfile, idealRanges, activeMetricKeys,
// metricAlertLevels — CorridorEditor.svelte:41-113).
//
// `compareHubHydration.ts` existiert noch NICHT — der Import schlaegt heute
// fehl (RED), bis S6f das Modul anlegt (Umzug byte-identisch aus der
// aufgeloesten Compare-Hub-Klebeschicht).
//
// Reine Verhaltenstests (echter Funktionsaufruf, KEIN Mock, KEINE
// Datei-Inhalt-Pruefung, KEIN DOM-Rendering — Projekt-Idiom analog
// channel_names_label.test.ts).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_hub_idealwerte_hydration.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import type { ComparePreset } from '../../../types.ts';
import { hydrateHubFieldsFromPreset } from '../compareHubHydration.ts';

// Fixture nach dem echten DTO (compareEditorSave.ts:71-162, routes/compare/[id]/edit/+page.svelte:19-86):
// location_ids/schedule/profil/display_config (region, ideal_ranges, active_metrics,
// metric_alert_levels) + Top-Level `corridors` (Issue #1231 Slice 4). channel_layouts
// ist seit #1351 (AC-6) kein Compare-Feld mehr — ein realistisches Preset führt es nicht.
function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cmp-42',
		name: 'Skigebiete Tirol',
		location_ids: ['loc-1', 'loc-2', 'loc-3'],
		schedule: 'daily',
		weekday: 0,
		profil: 'wintersport',
		hour_from: 6,
		hour_to: 9,
		empfaenger: ['urlauber@example.com'],
		forecast_hours: 48,
		letzter_versand: undefined,
		top_ort_letzter_versand: null,
		created_at: '2026-01-01T00:00:00Z',
		corridors: [{ metric: 'snow_depth_cm', range: [20, null], notify: true, mark: true, prio: 'hoch' }],
		display_config: {
			region: 'Tirol',
			ideal_ranges: { snow_depth_cm: { min: 20, max: null } },
			active_metrics: ['snow_depth_cm', 'wind_gust'],
			metric_alert_levels: { snow_depth_cm: 'warn', wind_gust: 'mark' }
		},
		...overrides
	};
}

describe('AC-16: hydrateHubFieldsFromPreset — Teil-Hydration der 6 CorridorEditor-Felder', () => {
	test('liefert ein Objekt mit GENAU den 6 erwarteten Feldern (keine mehr, keine weniger)', () => {
		const hydrated = hydrateHubFieldsFromPreset(makePreset());
		assert.deepStrictEqual(
			Object.keys(hydrated).sort(),
			['activeMetricKeys', 'activityProfile', 'corridors', 'idealRanges', 'isEditMode', 'metricAlertLevels'].sort(),
			`erwartet genau 6 Felder, gefunden: ${Object.keys(hydrated).join(', ')}`
		);
	});

	test('isEditMode ist immer true (Hub mountet den Organism wie den Editor)', () => {
		const hydrated = hydrateHubFieldsFromPreset(makePreset());
		assert.strictEqual(hydrated.isEditMode, true);
	});

	test('corridors kommt unveraendert vom Top-Level-Feld des Presets', () => {
		const preset = makePreset();
		const hydrated = hydrateHubFieldsFromPreset(preset);
		assert.deepStrictEqual(hydrated.corridors, preset.corridors);
	});

	test('activityProfile kommt aus preset.profil', () => {
		const hydrated = hydrateHubFieldsFromPreset(makePreset({ profil: 'wandern' }));
		assert.strictEqual(hydrated.activityProfile, 'wandern');
	});

	test('idealRanges kommt aus display_config.ideal_ranges', () => {
		const preset = makePreset();
		const hydrated = hydrateHubFieldsFromPreset(preset);
		assert.deepStrictEqual(hydrated.idealRanges, preset.display_config!.ideal_ranges);
	});

	test('metricAlertLevels kommt aus display_config.metric_alert_levels', () => {
		const preset = makePreset();
		const hydrated = hydrateHubFieldsFromPreset(preset);
		assert.deepStrictEqual(hydrated.metricAlertLevels, preset.display_config!.metric_alert_levels);
	});

	test('#1191-Semantik: VORHANDENES leeres active_metrics-Array bleibt [] (keine Profil-Default-Ueberschreibung)', () => {
		const preset = makePreset({ display_config: { active_metrics: [] } });
		const hydrated = hydrateHubFieldsFromPreset(preset);
		assert.deepStrictEqual(hydrated.activeMetricKeys, []);
	});

	test('#1191-Semantik: FEHLENDES active_metrics-Feld liefert null (Signal fuer Profil-Default-Pfad, kein stilles [])', () => {
		const preset = makePreset({ display_config: { region: 'Tirol' } });
		const hydrated = hydrateHubFieldsFromPreset(preset);
		assert.strictEqual(
			hydrated.activeMetricKeys,
			null,
			'fehlendes active_metrics darf NICHT als leeres Array getarnt werden (rehydrateActiveMetrics-Semantik #1191)'
		);
	});
});
