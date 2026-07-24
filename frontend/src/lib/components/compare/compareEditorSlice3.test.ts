// TDD — Issue #680 (Epic #677): Compare-Editor Slice 3 — Logik-Tests
//
// Spec: docs/specs/modules/issue_680_compare_editor_slice3.md
//
// Prüft verbleibende reine Logik-Bausteine:
//   1. active_metrics im Save-Payload (AC-10)
//   2. Lade-Pfad-Rehydrierung (#1191)
//   3. Profil-Default-Metriken (AC-4/AC-5)
//
// Issue #1350 Teil 3 (2026-07-24): die Bloecke "ALL_METRICS — vollstaendiger
// Metrik-Katalog" (AC-8/AC-9) und "deriveIdealText" (AC-6) sind mit
// compareMetricDefs.ts geloescht (ersatzlos, s.
// docs/specs/modules/compare_metric_ssot_final.md Punkt 7/8) — der Katalog
// lebt jetzt ausschliesslich im Backend (compare_metric_catalog.py) bzw. im
// FE-Loader (compareMetricCatalogLoader.ts, eigene Paritaets-Tests).
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/compareEditorSlice3.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

// ── Import: Save-Payload mit activeMetricKeys (AC-10) ────────────────────────
import { buildComparePresetSavePayload } from './compareEditorSave.ts';
import type { ComparePreset } from '../../types.ts';

// ── Import 4: Lade-Pfad-Rehydrierung (Issue #1191) ──────────────────────────
import { rehydrateActiveMetrics } from './compareEditorLoad.ts';

// ─────────────────────────────────────────────────────────────────────────────
// Fixture
// ─────────────────────────────────────────────────────────────────────────────
function makePreset(): ComparePreset {
	return {
		id: 'preset-680-test',
		name: 'Slice3 Test',
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
			ideal_ranges: { snow_depth_cm: { min: 30, max: 200 } },
			active_metrics: ['snow_depth_cm', 'wind_max_kmh']
		}
	};
}

// ─────────────────────────────────────────────────────────────────────────────
// AC-10: active_metrics im Save-Payload
// ─────────────────────────────────────────────────────────────────────────────
describe('buildComparePresetSavePayload — active_metrics (AC-10)', () => {
	test('activeMetricKeys wird als display_config.active_metrics übergeben', () => {
		const { body } = buildComparePresetSavePayload(makePreset(), {
			name: 'Slice3 Test',
			activityProfile: 'wintersport',
			pickedIds: ['loc-a', 'loc-b'],
			region: 'Hochkönig',
			idealRanges: { snow_depth_cm: { min: 30, max: 200 } },
			channelLayouts: null,
			activeMetricKeys: ['snow_depth_cm', 'wind_max_kmh', 'precip_sum_mm']
		});
		assert.deepEqual(
			(body.display_config as Record<string, unknown>).active_metrics,
			['snow_depth_cm', 'wind_max_kmh', 'precip_sum_mm'],
			'active_metrics fehlt im display_config'
		);
	});

	test('leere activeMetricKeys → active_metrics nicht im Payload (kein Datenschrott)', () => {
		const { body } = buildComparePresetSavePayload(makePreset(), {
			name: 'Slice3 Test',
			activityProfile: 'wintersport',
			pickedIds: ['loc-a', 'loc-b'],
			region: 'Hochkönig',
			idealRanges: {},
			channelLayouts: null,
			activeMetricKeys: []
		});
		const dc = body.display_config as Record<string, unknown>;
		assert.ok(
			!('active_metrics' in dc) || (dc.active_metrics as unknown[]).length === 0,
			'leere Metrik-Liste soll nicht als active_metrics=[] persistiert werden (oder leer ist ok)'
		);
	});

	test('bestehende display_config-Felder (ideal_ranges, region) bleiben per RMW erhalten', () => {
		const { body } = buildComparePresetSavePayload(makePreset(), {
			name: 'Slice3 Test',
			activityProfile: 'wintersport',
			pickedIds: ['loc-a', 'loc-b'],
			region: 'Hochkönig',
			idealRanges: { snow_depth_cm: { min: 30, max: 200 } },
			channelLayouts: null,
			activeMetricKeys: ['snow_depth_cm']
		});
		const dc = body.display_config as Record<string, unknown>;
		assert.deepEqual(
			(dc.ideal_ranges as Record<string, unknown>)?.snow_depth_cm,
			{ min: 30, max: 200 },
			'ideal_ranges gehen durch RMW verloren'
		);
	});

	test('activeMetricKeys fehlt im Aufruf → rückwärtskompatibel, kein Fehler', () => {
		// Alte Aufruf-Signatur ohne activeMetricKeys → kein TypeError
		assert.doesNotThrow(() => {
			buildComparePresetSavePayload(makePreset(), {
				name: 'Slice3 Test',
				activityProfile: 'wintersport',
				pickedIds: ['loc-a', 'loc-b'],
				region: 'Hochkönig',
				idealRanges: {},
				channelLayouts: null
				// activeMetricKeys absichtlich weggelassen
			});
		});
	});
});

// ─────────────────────────────────────────────────────────────────────────────
// Issue #1191: Lade-Pfad — leeres active_metrics[] ist bewusste Nutzerwahl
// ─────────────────────────────────────────────────────────────────────────────
describe('rehydrateActiveMetrics — Lade-Pfad-Rehydrierung (#1191)', () => {
	test('vorhandenes leeres [] → activeMetricKeys=[] UND metricsManuallyEdited=true (keine Default-Auffüllung)', () => {
		// Bug-Repro: "alles abgewählt" persistiert als [] und muss beim Reload
		// erhalten bleiben — NICHT auf Profil-Defaults zurückspringen.
		const result = rehydrateActiveMetrics([]);
		assert.notEqual(result, null, 'leeres [] darf nicht als "nie gesetzt" behandelt werden');
		assert.deepEqual(result?.activeMetricKeys, [], 'activeMetricKeys muss leer bleiben');
		assert.equal(result?.metricsManuallyEdited, true, 'metricsManuallyEdited muss true sein');
	});

	test('vorhandenes befülltes Array → 1:1 übernommen + metricsManuallyEdited=true', () => {
		const result = rehydrateActiveMetrics(['snow_depth_cm', 'wind_max_kmh']);
		assert.deepEqual(result?.activeMetricKeys, ['snow_depth_cm', 'wind_max_kmh']);
		assert.equal(result?.metricsManuallyEdited, true);
	});

	test('fehlendes Array (undefined) → null (Legacy → Profil-Defaults greifen)', () => {
		assert.equal(rehydrateActiveMetrics(undefined), null);
	});

	test('fehlendes Array (null) → null (Legacy → Profil-Defaults greifen)', () => {
		assert.equal(rehydrateActiveMetrics(null), null);
	});
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-4/AC-5: Profil-Default-Mapping (activeMetricKeys aus PROFILE_METRICS)
// ─────────────────────────────────────────────────────────────────────────────
describe('Profil-Default-Metriken (AC-4/AC-5)', () => {
	// Importiere PROFILE_METRICS_WITH_SCALES direkt — keine Logik, reine Daten-Prüfung
	test('WINTERSPORT-Profil hat snow_depth_cm in seinen Default-Metriken', async () => {
		const { PROFILE_METRICS_WITH_SCALES } = await import('../shared/corridor-editor/corridorEditorState.ts');
		const keys = PROFILE_METRICS_WITH_SCALES.WINTERSPORT.map((m) => m.key);
		assert.ok(keys.includes('snow_depth_cm'), 'snow_depth_cm fehlt in WINTERSPORT');
	});

	test('SUMMER_TREKKING-Profil hat thunder_level_max', async () => {
		const { PROFILE_METRICS_WITH_SCALES } = await import('../shared/corridor-editor/corridorEditorState.ts');
		const keys = PROFILE_METRICS_WITH_SCALES.SUMMER_TREKKING.map((m) => m.key);
		assert.ok(keys.includes('thunder_level_max'), 'thunder_level_max fehlt in SUMMER_TREKKING');
	});
});
