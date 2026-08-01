// TDD RED — Feature #1435 Etappe E3a, AC-11: eine gespeicherte Größe, die das
// zentrale Register nicht (mehr) kennt, darf nicht still verschwinden.
// Spec: docs/specs/modules/feat_1435_e3a_uebersicht_wetter_block.md AC-11.
//
// Begründung (aus der Spec übernommen): "still verschwindende Größe" ist
// exakt die Fehlerklasse, gegen die #1435 insgesamt antritt. Ein Block, der
// unbekannte Kennungen wortlos wegfiltert, wäre eine neue solche Stelle; die
// rohe Kennung anzuzeigen wäre der Rückfall in den vom Ticket beklagten
// Zustand. Deshalb: bekannte Namen bleiben, unbekannte werden separat gezählt.
//
// RED heute: `tripActiveMetricNames.ts` existiert noch nicht.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/trip-metrics/__tests__/tripActiveMetricNamesUnknownId.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { resolveTripMetricsOverviewState } from '../tripActiveMetricNames.ts';
import type { MetricCatalog } from '../../../trip-detail/metricsEditor.ts';
import type { WeatherConfigMetric } from '$lib/types';

// Katalog OHNE 'soil_temp' — simuliert eine umbenannte/entfernte Größe, deren
// Kennung in einer alten Tour noch gespeichert ist.
const catalog: MetricCatalog = {
	temperature: [
		{
			id: 'temperature',
			label: 'Temperatur',
			unit: '°C',
			category: 'temperature',
			default_enabled: true,
			has_friendly_format: true
		}
	]
};

describe('AC-11: unbekannte gespeicherte Kennung verschwindet nicht still', () => {
	// AC-11: bekannte Namen bleiben ('Temperatur'), die unbekannte Kennung
	// ('soil_temp') wird gesondert gezählt statt kommentarlos gefiltert.
	test('bekannte Namen bleiben, unbekannte Kennung erhöht einen eigenen Zähler', () => {
		const metrics: WeatherConfigMetric[] = [
			{ metric_id: 'temperature', enabled: true },
			{ metric_id: 'soil_temp', enabled: true }
		];
		const result = resolveTripMetricsOverviewState(metrics, catalog);
		assert.equal(result.kind, 'selected');
		assert.deepEqual((result as { names: string[] }).names, ['Temperatur']);
		assert.equal((result as { unknownCount: number }).unknownCount, 1);
	});

	// Gegenprobe (AC-11): die rohe, englische Kennung darf NIRGENDS in der
	// Namensliste auftauchen — das wäre der Rückfall in den Ticket-Zustand.
	test('Gegenprobe: die rohe Kennung soil_temp steht in keiner Namensliste', () => {
		const metrics: WeatherConfigMetric[] = [
			{ metric_id: 'temperature', enabled: true },
			{ metric_id: 'soil_temp', enabled: true }
		];
		const result = resolveTripMetricsOverviewState(metrics, catalog) as { names: string[] };
		assert.equal(result.names.includes('soil_temp'), false);
	});
});
