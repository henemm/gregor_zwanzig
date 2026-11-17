// Issue #3097 (W11, Epic #3058) — Roh/Einfach je Zeile im Orte-Stundenverlauf.
// SPEC: docs/specs/modules/feat_3097_orte_stundenverlauf_darstellung.md (AC-7, AC-8)
//
// Analog compare_outlook_metric_formats_persistenz.test.ts (#2049):
//   AC-8: `display_config.hourly_metric_formats` wird per Read-Modify-Write
//         gespeichert; alle uebrigen display_config-Felder bleiben erhalten,
//         und eine reine Umschaltung gilt als Aenderung (PUT entsteht).
//   AC-7: der Umschalter (`friendlyMap`) erscheint nur fuer Groessen mit
//         Einfachform -- nie fuer Temperatur oder Gewitter.
//
// Reine Verhaltenstests, kein Mock: echte ComparePreset-Objekte durch die
// echten Pure Functions, geprueft wird der erzeugte PUT-Payload.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/compare/__tests__/compare_hourly_metric_formats_persistenz.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { buildComparePresetSavePayload } from '../compareEditorSave.ts';
import { flushPendingLayoutSave, type LayoutSnapshot } from '../../shared/weather-metrics-tab/weatherMetricsCompareSave.ts';
import { buildHourlyFriendlyMap } from '../hourlyFriendlyMap.ts';
import type { ComparePreset } from '../../../types.ts';

function makePreset(): ComparePreset {
	return {
		id: 'preset-3097-hourly-formats',
		name: 'Ortsvergleich Stundenverlauf',
		location_ids: ['loc-a', 'loc-b'],
		schedule: 'daily',
		previous_schedule: 'daily',
		weekday: 3,
		profil: 'wandern',
		hour_from: 6,
		hour_to: 20,
		empfaenger: ['gregor-test@henemm.com'],
		forecast_hours: 72,
		created_at: '2026-08-01T08:00:00Z',
		hourly_enabled: true,
		outlook_enabled: true,
		display_config: {
			region: 'Dolomiten',
			active_metrics: ['temperature', 'wind'],
			hourly_metrics: ['wind', 'temperature', 'precipitation'],
			outlook_metrics: ['gust', 'sunshine'],
			outlook_metric_formats: { gust: true },
			channel_layouts: { email: [{ metric_id: 'wind', enabled: true, use_friendly_format: false }] },
			metric_alert_levels: { wind_max_kmh: 'sensibel' }
		}
	} as ComparePreset;
}

const UNBETEILIGTE_FELDER: Record<string, unknown> = {
	active_metrics: ['temperature', 'wind'],
	hourly_metrics: ['wind', 'temperature', 'precipitation'],
	outlook_metrics: ['gust', 'sunshine'],
	outlook_metric_formats: { gust: true },
	channel_layouts: { email: [{ metric_id: 'wind', enabled: true, use_friendly_format: false }] },
	metric_alert_levels: { wind_max_kmh: 'sensibel' }
};

describe('#3097 AC-8 — Speichern von hourly_metric_formats (Read-Modify-Write)', () => {
	test('nur hourlyMetricFormats editiert -> Feld im Payload, alle uebrigen Felder unveraendert', () => {
		const original = makePreset();
		const { body } = buildComparePresetSavePayload(original, {
			name: original.name,
			activityProfile: 'wandern',
			pickedIds: original.location_ids,
			region: 'Dolomiten',
			idealRanges: {},
			hourlyMetricFormats: { wind: true }
		});
		const dc = body.display_config as Record<string, unknown>;
		assert.deepEqual(dc.hourly_metric_formats, { wind: true }, 'Stundenverlauf-Zuordnung fehlt im Payload');
		for (const [key, wert] of Object.entries(UNBETEILIGTE_FELDER)) {
			assert.deepEqual(dc[key], wert, `display_config.${key} ging verloren (Read-Modify-Write verletzt)`);
		}
	});

	test('nicht editiert (undefined) -> gespeicherter Stand bleibt', () => {
		const original = makePreset();
		(original.display_config as Record<string, unknown>).hourly_metric_formats = { wind: true };
		const { body } = buildComparePresetSavePayload(original, {
			name: original.name,
			activityProfile: 'wandern',
			pickedIds: original.location_ids,
			region: 'Dolomiten',
			idealRanges: {}
		});
		assert.deepEqual((body.display_config as Record<string, unknown>).hourly_metric_formats, { wind: true });
	});

	test('reine Umschaltung im Stundenverlauf gilt als Aenderung (PUT entsteht)', () => {
		const basis = {
			hourlyMetricKeys: ['wind', 'temperature'],
			hourlyEnabled: true,
			hourlyMetricFormats: null,
			outlookMetricKeys: ['gust', 'sunshine'],
			outlookMetricFormats: null,
			outlookEnabled: true
		} as unknown as LayoutSnapshot;
		const jetzt = { ...basis, hourlyMetricFormats: { wind: true } } as unknown as LayoutSnapshot;
		const payload = flushPendingLayoutSave(makePreset(), jetzt, basis);
		assert.ok(payload, 'reine Roh/Einfach-Umschaltung im Stundenverlauf wird nie gespeichert');
		assert.deepEqual(
			(payload.body.display_config as Record<string, unknown>).hourly_metric_formats,
			{ wind: true }
		);
	});
});

describe('#3097 AC-7 — Umschalter nur fuer Groessen mit Einfachform', () => {
	test('Temperatur und Gewitter bekommen keinen Umschalter, Wind/Niederschlag/Wolken schon', () => {
		const map = buildHourlyFriendlyMap(
			['temperature', 'thunder', 'wind', 'gust', 'precipitation', 'cloud_total', 'rain_probability'],
			{ wind: true, temperature: true, thunder: true }
		);
		assert.ok(!('temperature' in map), 'Temperatur hat keine Einfachform');
		assert.ok(!('thunder' in map), 'Gewitter ist roh bereits Text (#1475)');
		assert.equal(map.wind, true);
		for (const id of ['gust', 'precipitation', 'cloud_total', 'rain_probability']) {
			assert.equal(map[id], false, `${id}: Umschalter fehlt oder steht nicht auf Roh`);
		}
	});
});
