// #1401 Scheibe B, Teil 1 — AC-1 + AC-7.
// Spec: docs/specs/modules/fix_1401b_register_stundenverlauf_alarme.md
//
// AC-1: Die Stundenverlauf-Beschriftungen kommen aus dem zentralen Metrik-
// Register (src/app/metric_catalog.py, ueber GET /api/metrics), nicht mehr aus
// dem eigenstaendigen Text in compareHourlyMetricDefs.ts. Zwei Namen aendern
// sich dadurch sichtbar (thunder_level, visibility_m), die uebrigen acht duerfen
// sich NICHT aendern.
// AC-7: Fail-Soft — ohne geladenen Katalog bleibt der bisherige Text stehen.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/compareHourlyCatalogIds.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { ALL_HOURLY_METRICS } from './compareHourlyMetricDefs.ts';
import {
	HOURLY_KEY_TO_CATALOG_ID,
	resolveHourlyMetricLabel
} from './compareHourlyCatalogIds.ts';

// Auszug aus src/app/metric_catalog.py (label_de), zitiert mit Zeilenangabe:
//   temperature 78 · wind_chill 109 · wind 159 · gust 175 · wind_direction 194
//   precipitation 210 · rain_probability 224 · thunder 256 · visibility 384
//   uv_index 426
const CATALOG_FIXTURE: Record<string, { label: string }> = {
	temperature: { label: 'Temperatur' },
	wind_chill: { label: 'Gefühlte Temperatur' },
	wind: { label: 'Wind' },
	gust: { label: 'Böen' },
	precipitation: { label: 'Niederschlag' },
	uv_index: { label: 'UV-Index' },
	thunder: { label: 'Gewitter' },
	rain_probability: { label: 'Regenwahrscheinlichkeit' },
	visibility: { label: 'Sichtweite' },
	wind_direction: { label: 'Windrichtung' }
};

// Erwartete Anzeige je Hourly-Key bei geladenem Katalog.
const EXPECTED_WITH_CATALOG: Record<string, string> = {
	temp_c: 'Temperatur',
	wind_chill_c: 'Gefühlte Temperatur',
	wind_kmh: 'Wind',
	gust_kmh: 'Böen',
	precip_mm: 'Niederschlag',
	uv_index: 'UV-Index',
	// sichtbare Aenderung: bisher "Gewitter-Risiko"
	thunder_level: 'Gewitter',
	pop_pct: 'Regenwahrscheinlichkeit',
	// sichtbare Aenderung: bisher "Sicht"
	visibility_m: 'Sichtweite',
	wind_dir_deg: 'Windrichtung'
};

describe('#1401b AC-1: Stundenverlauf-Labels kommen aus dem Register', () => {
	test('Crosswalk deckt alle 10 Hourly-Keys ab (keine Luecke, kein Ueberschuss)', () => {
		const catalogKeys = Object.keys(HOURLY_KEY_TO_CATALOG_ID).sort();
		const hourlyKeys = ALL_HOURLY_METRICS.map((m) => m.key).sort();
		assert.deepEqual(catalogKeys, hourlyKeys);
	});

	test('Jede Crosswalk-Ziel-ID existiert im Register', () => {
		for (const [key, catalogId] of Object.entries(HOURLY_KEY_TO_CATALOG_ID)) {
			assert.ok(
				catalogId in CATALOG_FIXTURE,
				`Hourly-Key ${key} zeigt auf Katalog-ID "${catalogId}", die es dort nicht gibt.`
			);
		}
	});

	test('resolveHourlyMetricLabel liefert je Key den Register-Text', () => {
		for (const metric of ALL_HOURLY_METRICS) {
			const resolved = resolveHourlyMetricLabel(metric.key, CATALOG_FIXTURE, metric.label);
			assert.equal(
				resolved,
				EXPECTED_WITH_CATALOG[metric.key],
				`Label fuer ${metric.key} weicht vom Register ab.`
			);
		}
	});

	test('Die zwei sichtbaren Aenderungen sind genau thunder_level und visibility_m', () => {
		const changed = ALL_HOURLY_METRICS.filter(
			(m) => resolveHourlyMetricLabel(m.key, CATALOG_FIXTURE, m.label) !== m.label
		).map((m) => m.key);
		assert.deepEqual(changed.sort(), ['thunder_level', 'visibility_m']);
	});
});

describe('#1401b AC-7: Fail-Soft ohne geladenen Katalog', () => {
	test('Leeres Katalog-Objekt: alle 10 Keys behalten ihren Fallback-Text', () => {
		for (const metric of ALL_HOURLY_METRICS) {
			assert.equal(resolveHourlyMetricLabel(metric.key, {}, metric.label), metric.label);
		}
	});

	test('Teil-geladener Katalog: nur die vorhandene Groesse wird ersetzt', () => {
		const partial = { thunder: { label: 'Gewitter' } };
		assert.equal(resolveHourlyMetricLabel('thunder_level', partial, 'Gewitter-Risiko'), 'Gewitter');
		assert.equal(resolveHourlyMetricLabel('visibility_m', partial, 'Sicht'), 'Sicht');
	});

	test('Unbekannter Key faellt auf den uebergebenen Text zurueck (kein leerer Text)', () => {
		assert.equal(resolveHourlyMetricLabel('gibts_nicht', CATALOG_FIXTURE, 'Ersatztext'), 'Ersatztext');
	});
});
