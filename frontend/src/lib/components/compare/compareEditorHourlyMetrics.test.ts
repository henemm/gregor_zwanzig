// TDD — Issue #1106: Ortsvergleich C — Metriken im Stundenverlauf konfigurierbar.
//
// Spec: docs/specs/modules/issue_1106_hourly_metrics_config.md (AC-2/AC-8)
//
// Pure-Function Round-Trip-Test fuer hourlyMetricKeys in
// buildComparePresetSavePayload() — analog compareEditorSlice3.test.ts (AC-10,
// activeMetricKeys).
//
// Ausfuehren:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/compareEditorHourlyMetrics.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { buildComparePresetSavePayload } from './compareEditorSave.ts';
import type { ComparePreset } from '../../types.ts';

// Issue #3301: die Umschalt-/Reihenfolge-Bloecke (applyHourlyMetricToggle,
// applyHourlyMetricToggleFromState, orderableHourlyMetricKeys, applyHourlyReorder)
// sind mit compareHourlyMetricDefs.ts entfallen — kein Produktionscode nutzte sie
// mehr (Kanal-Layout-Karte mit WeatherMetricsTab in #3297 geloescht).

function makePreset(): ComparePreset {
	return {
		id: 'preset-1106-test',
		name: 'Hourly Metrics Test',
		location_ids: ['loc-a', 'loc-b'],
		schedule: 'daily',
		previous_schedule: 'daily',
		weekday: 3,
		profil: 'wintersport',
		hour_from: 7,
		hour_to: 16,
		empfaenger: ['test@example.com'],
		created_at: '2026-06-09T00:00:00Z',
		display_config: {
			region: 'Hochkönig',
			hourly_metrics: ['temp_c', 'wind_kmh']
		}
	};
}

// Issue #3276 (Spec-AC-38, AC-2): `hourly_metrics` ist Altschluessel. Der Speicher-Payload setzt
// das Feld nie mehr aus dem Editor; ein vorhandener Bestandswert reist nur ueber den
// Read-Modify-Write-Spread unveraendert mit (vorher: #1106 schrieb `hourlyMetricKeys`,
// #1299/C2 auch `[]` — beides entfaellt, die drei Schreib-Tests sind durch diese ersetzt).
describe('buildComparePresetSavePayload — hourly_metrics (Issue #1106, seit #3276 nur Bestand)', () => {
	test('ein Editor-Wert hourlyMetricKeys ueberschreibt den Bestand nicht mehr', () => {
		const { body } = buildComparePresetSavePayload(makePreset(), {
			name: 'Hourly Metrics Test',
			activityProfile: 'wintersport',
			pickedIds: ['loc-a', 'loc-b'],
			region: 'Hochkönig',
			idealRanges: {},
			hourlyMetricKeys: ['visibility_m', 'temp_c']
		} as never);
		assert.deepEqual((body.display_config as Record<string, unknown>).hourly_metrics, ['temp_c', 'wind_kmh']);
	});

	test('ohne Bestand entsteht kein hourly_metrics (auch nicht als [])', () => {
		const preset = makePreset();
		delete (preset.display_config as Record<string, unknown>).hourly_metrics;
		const { body } = buildComparePresetSavePayload(preset, {
			name: 'Hourly Metrics Test',
			activityProfile: 'wintersport',
			pickedIds: ['loc-a', 'loc-b'],
			region: 'Hochkönig',
			idealRanges: {},
			hourlyMetricKeys: []
		} as never);
		assert.ok(!('hourly_metrics' in (body.display_config as Record<string, unknown>)));
	});

	test('bestehendes display_config.hourly_metrics bleibt per RMW erhalten, wenn hourlyMetricKeys fehlt', () => {
		assert.doesNotThrow(() => {
			const { body } = buildComparePresetSavePayload(makePreset(), {
				name: 'Hourly Metrics Test',
				activityProfile: 'wintersport',
				pickedIds: ['loc-a', 'loc-b'],
				region: 'Hochkönig',
				idealRanges: {},
				// hourlyMetricKeys absichtlich weggelassen -> Rueckwaertskompatibilitaet
			});
			const dc = body.display_config as Record<string, unknown>;
			assert.deepEqual(dc.hourly_metrics, ['temp_c', 'wind_kmh']);
		});
	});
});
