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
import { ALL_HOURLY_METRICS } from './compareHourlyMetricDefs.ts';
import type { ComparePreset } from '../../types.ts';

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

describe('ALL_HOURLY_METRICS — Katalog (Issue #1106)', () => {
	test('enthaelt genau 9 Eintraege, "Zeit" nicht dabei', () => {
		assert.equal(ALL_HOURLY_METRICS.length, 9);
		assert.ok(!ALL_HOURLY_METRICS.some((m) => m.label === 'Zeit'));
	});

	test('jede Metrik hat key + label', () => {
		for (const m of ALL_HOURLY_METRICS) {
			assert.ok(typeof m.key === 'string' && m.key.length > 0);
			assert.ok(typeof m.label === 'string' && m.label.length > 0);
		}
	});

	test('keine doppelten keys', () => {
		const keys = ALL_HOURLY_METRICS.map((m) => m.key);
		assert.equal(new Set(keys).size, keys.length);
	});
});

describe('buildComparePresetSavePayload — hourly_metrics (Issue #1106)', () => {
	test('hourlyMetricKeys wird als display_config.hourly_metrics uebergeben', () => {
		const { body } = buildComparePresetSavePayload(makePreset(), {
			name: 'Hourly Metrics Test',
			activityProfile: 'wintersport',
			pickedIds: ['loc-a', 'loc-b'],
			region: 'Hochkönig',
			idealRanges: {},
			channelLayouts: null,
			hourlyMetricKeys: ['temp_c', 'wind_kmh', 'thunder_level']
		});
		assert.deepEqual(
			(body.display_config as Record<string, unknown>).hourly_metrics,
			['temp_c', 'wind_kmh', 'thunder_level'],
			'hourly_metrics fehlt im display_config'
		);
	});

	test('leere hourlyMetricKeys -> hourly_metrics als [] im Payload (Default = alle, Bug #1299/C2)', () => {
		// Server-Merge (mergeConfigMap, config_merge.go) kann Keys nur ueberschreiben,
		// nie loeschen -> [] muss explizit gesendet werden (analog active_metrics,
		// #1191). Renderer-seitig bedeutet [] "kein Filter gesetzt" -> alle sichtbar.
		const { body } = buildComparePresetSavePayload(makePreset(), {
			name: 'Hourly Metrics Test',
			activityProfile: 'wintersport',
			pickedIds: ['loc-a', 'loc-b'],
			region: 'Hochkönig',
			idealRanges: {},
			channelLayouts: null,
			hourlyMetricKeys: []
		});
		const dc = body.display_config as Record<string, unknown>;
		assert.deepEqual(
			dc.hourly_metrics,
			[],
			'leere Auswahl soll hourly_metrics als [] persistieren, nicht loeschen'
		);
	});

	test('bestehendes display_config.hourly_metrics bleibt per RMW erhalten, wenn hourlyMetricKeys fehlt', () => {
		assert.doesNotThrow(() => {
			const { body } = buildComparePresetSavePayload(makePreset(), {
				name: 'Hourly Metrics Test',
				activityProfile: 'wintersport',
				pickedIds: ['loc-a', 'loc-b'],
				region: 'Hochkönig',
				idealRanges: {},
				channelLayouts: null
				// hourlyMetricKeys absichtlich weggelassen -> Rueckwaertskompatibilitaet
			});
			const dc = body.display_config as Record<string, unknown>;
			assert.deepEqual(dc.hourly_metrics, ['temp_c', 'wind_kmh']);
		});
	});

	test('Reihenfolge der Auswahl bleibt im Payload erhalten (Renderer sortiert kanonisch, nicht der Editor)', () => {
		const { body } = buildComparePresetSavePayload(makePreset(), {
			name: 'Hourly Metrics Test',
			activityProfile: 'wintersport',
			pickedIds: ['loc-a', 'loc-b'],
			region: 'Hochkönig',
			idealRanges: {},
			channelLayouts: null,
			hourlyMetricKeys: ['visibility_m', 'temp_c']
		});
		assert.deepEqual(
			(body.display_config as Record<string, unknown>).hourly_metrics,
			['visibility_m', 'temp_c']
		);
	});
});
