// TDD RED — Issue #680 (Epic #677): Compare-Editor Slice 3 — Logik-Tests
//
// Spec: docs/specs/modules/issue_680_compare_editor_slice3.md
//
// Prüft die reinen Logik-Bausteine, die für Slice 3 neu hinzukommen:
//   1. ALL_METRICS-Katalog in compareMetricDefs.ts (AC-8/AC-9)
//   2. Ideal-Text-Ableitung aus min/max + unit (AC-6)
//   3. active_metrics im Save-Payload (AC-10)
//
// RED: Alle Tests schlagen fehl, weil
//   a) ALL_METRICS nicht exportiert wird
//   b) deriveIdealText() nicht existiert
//   c) buildComparePresetSavePayload() activeMetricKeys noch nicht kennt
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/compareEditorSlice3.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

// ── Import 1: ALL_METRICS (neu in AC-8) ─────────────────────────────────────
// RED: Export existiert noch nicht → Modul-Fehler oder fehlender Export
import { ALL_METRICS } from './compareMetricDefs.ts';

// ── Import 2: Ideal-Text-Ableitung (neu) ────────────────────────────────────
// RED: Funktion existiert noch nicht in compareMetricDefs.ts
import { deriveIdealText } from './compareMetricDefs.ts';

// ── Import 3: Save-Payload mit activeMetricKeys (AC-10) ─────────────────────
import { buildComparePresetSavePayload } from './compareEditorSave.ts';
import type { ComparePreset } from '../../types.ts';

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
// AC-8/AC-9: ALL_METRICS-Katalog
// ─────────────────────────────────────────────────────────────────────────────
describe('ALL_METRICS — vollständiger Metrik-Katalog (AC-8/AC-9)', () => {
	test('ALL_METRICS ist ein Array mit mindestens 10 Einträgen', () => {
		assert.ok(Array.isArray(ALL_METRICS), 'ALL_METRICS muss Array sein');
		assert.ok(ALL_METRICS.length >= 10, `Zu wenige Metriken: ${ALL_METRICS.length}`);
	});

	test('jede Metrik hat key + label + unit + kind', () => {
		for (const m of ALL_METRICS) {
			assert.ok(typeof m.key === 'string' && m.key.length > 0, `key fehlt: ${JSON.stringify(m)}`);
			assert.ok(typeof m.label === 'string' && m.label.length > 0, `label fehlt für key=${m.key}`);
			assert.ok(typeof m.unit === 'string', `unit fehlt für key=${m.key}`);
			assert.ok(m.kind === 'range' || m.kind === 'enum', `kind ungültig für key=${m.key}`);
		}
	});

	test('ALL_METRICS enthält alle Profile-Metriken (snow_depth, wind, precip, thunder)', () => {
		const keys = ALL_METRICS.map((m) => m.key);
		assert.ok(keys.includes('snow_depth_cm'), 'snow_depth_cm fehlt');
		assert.ok(keys.includes('wind_max_kmh'), 'wind_max_kmh fehlt');
		assert.ok(keys.includes('precip_sum_mm'), 'precip_sum_mm fehlt');
		assert.ok(keys.includes('thunder_level_max'), 'thunder_level_max fehlt');
	});

	test('keine doppelten keys in ALL_METRICS', () => {
		const keys = ALL_METRICS.map((m) => m.key);
		const unique = new Set(keys);
		assert.equal(unique.size, keys.length, 'Doppelte keys in ALL_METRICS');
	});
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-6: Ideal-Text-Ableitung
// ─────────────────────────────────────────────────────────────────────────────
describe('deriveIdealText — Ideal-Text aus min/max + unit (AC-6)', () => {
	test('min + max vorhanden → "min–max unit"', () => {
		assert.equal(deriveIdealText({ min: 30, max: 200 }, 'cm'), '30–200 cm');
	});

	test('nur min → "≥ min unit"', () => {
		assert.equal(deriveIdealText({ min: 5, max: null }, 'h'), '≥ 5 h');
	});

	test('nur max → "≤ max unit"', () => {
		assert.equal(deriveIdealText({ min: null, max: 40 }, 'km/h'), '≤ 40 km/h');
	});

	test('weder min noch max → "–"', () => {
		assert.equal(deriveIdealText({ min: null, max: null }, 'mm'), '–');
	});

	test('leeres Objekt → "–"', () => {
		assert.equal(deriveIdealText({}, '%'), '–');
	});

	test('min === 0 ist gültig (nicht falsy-gecheckt!)', () => {
		// 0 ist ein gültiger Wert — "0–5 mm" statt "≤ 5 mm"
		assert.equal(deriveIdealText({ min: 0, max: 5 }, 'mm'), '0–5 mm');
	});

	test('unit leer → kein führendes Leerzeichen', () => {
		const text = deriveIdealText({ min: 1, max: 5 }, '');
		assert.ok(!text.endsWith(' '), `unerwartetes Leerzeichen: "${text}"`);
	});
});

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
// AC-4/AC-5: Profil-Default-Mapping (activeMetricKeys aus PROFILE_METRICS)
// ─────────────────────────────────────────────────────────────────────────────
describe('Profil-Default-Metriken (AC-4/AC-5)', () => {
	// Importiere PROFILE_METRICS_WITH_SCALES direkt — keine Logik, reine Daten-Prüfung
	test('WINTERSPORT-Profil hat snow_depth_cm in seinen Default-Metriken', async () => {
		const { PROFILE_METRICS_WITH_SCALES } = await import('./compareMetricDefs.ts');
		const keys = PROFILE_METRICS_WITH_SCALES.WINTERSPORT.map((m) => m.key);
		assert.ok(keys.includes('snow_depth_cm'), 'snow_depth_cm fehlt in WINTERSPORT');
	});

	test('SUMMER_TREKKING-Profil hat thunder_level_max', async () => {
		const { PROFILE_METRICS_WITH_SCALES } = await import('./compareMetricDefs.ts');
		const keys = PROFILE_METRICS_WITH_SCALES.SUMMER_TREKKING.map((m) => m.key);
		assert.ok(keys.includes('thunder_level_max'), 'thunder_level_max fehlt in SUMMER_TREKKING');
	});
});
