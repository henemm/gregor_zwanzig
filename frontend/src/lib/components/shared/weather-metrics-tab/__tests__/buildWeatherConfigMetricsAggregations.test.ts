// Migriert aus aggregation_selection.test.ts (Issue #1728 Scheibe 2, DEC-4).
//
// Der Bedienabschnitt "05 -- Auswertungen" (vormals Issue #1357, Epic #1372
// S4a) faellt mit dieser Scheibe komplett weg. `buildWeatherConfigMetrics`
// selbst (der reine Payload-Bau mit dem `aggregationsMap`-Parameter) lebt
// aber unveraendert weiter -- `aggregationsMap` bleibt bis Scheibe 3 im
// Speicherweg (DEC-3 der Spec). Diese Datei uebernimmt ausschliesslich die
// UI-unabhaengigen Faelle (vormals Teile von AC-6/AC-8, #1357). Kein
// Rendering, kein Quelltext-Grep auf UI-Elemente -- der Rest der alten Datei
// (05-Block-Sichtbarkeit, Quelltext-Grep auf WeatherMetricsTab.svelte /
// AggregationMetricRow.svelte) ist mit dem entfernten Block hinfaellig und
// faellt ersatzlos weg.
//
// BESTANDSSCHUTZ: alle Faelle hier sind heute bereits gruen -- die geprueft
// Funktion aendert sich durch diese Scheibe nicht (DEC-3). Kein
// RED-Nachweis; diese Datei bewacht, dass die Migration den bestehenden
// Payload-Bau nicht bricht.
//
// Spec: docs/specs/modules/feat_1728_s2_editor.md § DEC-4, AC-11
// Kontext: docs/context/feat-1728-s2-editor.md
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/weather-metrics-tab/__tests__/buildWeatherConfigMetricsAggregations.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { buildWeatherConfigMetrics } from '../../../trip-detail/metricsEditor.ts';

// So liefert /api/metrics die Groessen seit #1357 (aus metric_catalog.py).
const TEMPERATURE = {
	id: 'temperature', label: 'Temperatur', unit: '°C', category: 'temperature',
	default_enabled: true, has_friendly_format: false,
	aggregations: [
		{ id: 'min', label: 'Minimum' },
		{ id: 'max', label: 'Maximum' },
		{ id: 'avg', label: 'Mittel' },
	],
};
const WIND_CHILL = {
	id: 'wind_chill', label: 'Gefühlte Temperatur', unit: '°C', category: 'temperature',
	default_enabled: false, has_friendly_format: false,
	aggregations: [
		{ id: 'min', label: 'Minimum' },
		{ id: 'max', label: 'Maximum' },
	],
};
const WIND = {
	id: 'wind', label: 'Wind', unit: 'km/h', category: 'wind',
	default_enabled: true, has_friendly_format: false,
	aggregations: [{ id: 'max', label: 'Maximum' }],
};

describe('AC-11: die Wahl ueberlebt den Speicherweg (buildWeatherConfigMetrics, migriert aus AC-6/#1357)', () => {
	const catalog = { temperature: [TEMPERATURE, WIND_CHILL], wind: [WIND] };
	const buckets = { primary: ['temperature', 'wind_chill'], secondary: [], off: ['wind'] };

	// BESTANDSSCHUTZ: heute bereits gruen -- bewacht, dass diese Scheibe das nicht bricht. Kein RED-Nachweis.
	test('gewaehlte Auswertungen landen im PUT-Payload', () => {
		const out = buildWeatherConfigMetrics(buckets, {}, {}, catalog, {
			wind_chill: ['max'],
		});
		const wc = out.find((m) => m.metric_id === 'wind_chill');
		assert.deepEqual(wc?.aggregations, ['max'],
			`AC-6 FAIL: Auswertungswahl geht beim Speichern verloren — ${JSON.stringify(wc)}`);
	});

	// BESTANDSSCHUTZ: heute bereits gruen -- bewacht, dass diese Scheibe das nicht bricht. Kein RED-Nachweis.
	test('AC-8: die leere Wahl wird als leere Liste gespeichert, nicht weggelassen', () => {
		const out = buildWeatherConfigMetrics(buckets, {}, {}, catalog, { wind_chill: [] });
		const wc = out.find((m) => m.metric_id === 'wind_chill');
		assert.deepEqual(wc?.aggregations, [],
			'AC-8 FAIL: leere Wahl wird nicht gespeichert und faellt auf die Vorgabe zurueck');
	});

	// BESTANDSSCHUTZ: heute bereits gruen -- bewacht, dass diese Scheibe das nicht bricht. Kein RED-Nachweis.
	test('unberuehrte Groessen tragen das Feld gar nicht (Katalog-Vorgabe greift)', () => {
		const out = buildWeatherConfigMetrics(buckets, {}, {}, catalog, { wind_chill: ['max'] });
		const temp = out.find((m) => m.metric_id === 'temperature');
		assert.equal(temp?.aggregations, undefined,
			'unberuehrte Groesse bekommt eine erfundene Einschraenkung');
	});

	// BESTANDSSCHUTZ: heute bereits gruen -- bewacht, dass diese Scheibe das nicht bricht. Kein RED-Nachweis.
	test('Bestandsaufrufer ohne den neuen Parameter bleiben unveraendert (additiv)', () => {
		const out = buildWeatherConfigMetrics(buckets, {}, {}, catalog);
		assert.ok(out.every((m) => m.aggregations === undefined));
	});
});
