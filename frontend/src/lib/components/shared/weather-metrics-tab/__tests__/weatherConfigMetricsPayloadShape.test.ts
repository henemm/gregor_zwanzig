// Issue #1728 Scheibe 3 — AC-8: der Trip-Editor-Payload traegt fuer KEINEN
// Bucket-Zustand ein `aggregations`-Feld.
//
// Spec: docs/specs/modules/feat_1728_s3_aggregations_cleanup.md (AC-8, DEC-5)
//
// Warum diese Datei existiert: die Zusicherung stand bis Scheibe 3 in
// `buildWeatherConfigMetricsAggregations.test.ts` (dort der letzte Fall,
// "Bestandsaufrufer ohne den neuen Parameter"). Jene Datei wird mit DEC-5
// geloescht, weil ihr Pruefling — der 5. Parameter `aggregationsMap` —
// entfaellt. Ohne diesen Umzug haette AC-8 nach der Implementierung KEINEN
// Waechter mehr; die in AC-8 genannten Bestandsfaelle in
// `metricsEditor.test.ts` pruefen bucket/order/friendly/horizons, aber nicht
// die Abwesenheit des Feldes.
//
// BESTANDSSCHUTZ: heute bereits gruen (der 5. Parameter hat den Default `{}`).
// Kein RED-Nachweis — die Datei sichert das Zielverhalten gegen den Wegfall
// ihres bisherigen Waechters.
//
// Lauf:
//     cd frontend && npm test -- \
//       src/lib/components/shared/weather-metrics-tab/__tests__/weatherConfigMetricsPayloadShape.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { buildWeatherConfigMetrics } from '../../../trip-detail/metricsEditor.ts';

// So liefert /api/metrics die Groessen (nach Kategorie gruppiert).
const catalog = {
	temperature: [
		{
			id: 'temperature', label: 'Temperatur', unit: '°C', category: 'temperature',
			default_enabled: true, has_friendly_format: false,
			aggregations: [{ id: 'min', label: 'Minimum' }, { id: 'max', label: 'Maximum' }],
		},
		{
			id: 'wind_chill', label: 'Gefühlte Temperatur', unit: '°C', category: 'temperature',
			default_enabled: false, has_friendly_format: false,
			aggregations: [{ id: 'min', label: 'Minimum' }, { id: 'max', label: 'Maximum' }],
		},
	],
	humidity: [
		{
			id: 'humidity', label: 'Luftfeuchte', unit: '%', category: 'humidity',
			default_enabled: false, has_friendly_format: false,
			aggregations: [{ id: 'avg', label: 'Mittel' }],
		},
	],
};

describe('AC-8: Speicherweg ohne Auswertungswahl', () => {
	test('kein Metrik-Objekt traegt ein aggregations-Feld', () => {
		const buckets = {
			primary: ['temperature'],
			secondary: ['wind_chill'],
			off: ['humidity'],
		};
		const out = buildWeatherConfigMetrics(buckets, {}, {}, catalog);

		assert.ok(out.length >= 3, `Payload unerwartet leer: ${JSON.stringify(out)}`);
		const mitFeld = out
			.filter((m) => 'aggregations' in (m as unknown as Record<string, unknown>))
			.map((m) => m.metric_id);
		assert.deepEqual(
			mitFeld,
			[],
			`Diese Metriken tragen noch ein aggregations-Feld: ${mitFeld.join(', ')} — ` +
				'das Feld ist mit #1728 S3 aus Typ und Speicherweg entfernt (DEC-4/DEC-5).',
		);
	});
});
