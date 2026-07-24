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
import {
	ALL_HOURLY_METRICS,
	DEFAULT_HOURLY_METRIC_KEYS,
	applyHourlyMetricToggle
} from './compareHourlyMetricDefs.ts';
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
	test('enthaelt genau 10 Eintraege, "Zeit" nicht dabei', () => {
		// Issue #1335 Scheibe 1: 9 -> 10 (neuer Windrichtungs-Eintrag, AC-8).
		assert.equal(ALL_HOURLY_METRICS.length, 10);
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

	test('Issue #1335 Scheibe 1 (AC-8): Windrichtungs-Eintrag wind_dir_deg vorhanden', () => {
		const entry = ALL_HOURLY_METRICS.find((m) => m.key === 'wind_dir_deg');
		assert.ok(entry, 'ALL_HOURLY_METRICS enthaelt keinen Eintrag mit key "wind_dir_deg"');
		assert.equal(entry?.label, 'Windrichtung');
	});
});

describe('applyHourlyMetricToggle — kein stiller Windrichtungs-Merge (Issue #1335 Adversary F002)', () => {
	test('DEFAULT_HOURLY_METRIC_KEYS enthaelt wind_dir_deg NICHT (9 von 10 Katalog-Eintraegen)', () => {
		assert.equal(DEFAULT_HOURLY_METRIC_KEYS.length, 9);
		assert.ok(!DEFAULT_HOURLY_METRIC_KEYS.includes('wind_dir_deg'));
	});

	test('Toggle einer ANDEREN Metrik aus Leer-Auswahl materialisiert wind_dir_deg NICHT mit', () => {
		// GIVEN: Bestandsnutzer ohne je konfigurierte Stundenmetriken (leere Auswahl)
		// WHEN: er tickt "Sicht" an (echter Klick-Handler-Pfad, wie im Adversary-Fund F002)
		const result = applyHourlyMetricToggle([], 'visibility_m', true);
		// THEN: die materialisierte Auswahl enthaelt die getoggelte Metrik ...
		assert.ok(result.includes('visibility_m'));
		// ... aber KEINE stille Windrichtungs-Aktivierung (kein Server-Merge-Trigger)
		assert.ok(
			!result.includes('wind_dir_deg'),
			'wind_dir_deg wurde still mitmaterialisiert -- stiller Merge-Regress F002'
		);
	});

	test('expliziter Toggle von Windrichtung aktiviert sie (AC-8 bleibt erfuellt)', () => {
		const result = applyHourlyMetricToggle([], 'wind_dir_deg', true);
		assert.ok(result.includes('wind_dir_deg'));
	});

	test('Windrichtung laesst sich nach explizitem Aktivieren wieder abwaehlen', () => {
		const withWindDir = applyHourlyMetricToggle([], 'wind_dir_deg', true);
		const withoutWindDir = applyHourlyMetricToggle(withWindDir, 'wind_dir_deg', false);
		assert.ok(!withoutWindDir.includes('wind_dir_deg'));
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
			hourlyMetricKeys: ['visibility_m', 'temp_c']
		});
		assert.deepEqual(
			(body.display_config as Record<string, unknown>).hourly_metrics,
			['visibility_m', 'temp_c']
		);
	});
});
