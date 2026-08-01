// TDD RED — Feature #1435 Etappe E3a: geteilte Drei-Zustands-Namensauflösung
// für den neuen Wetter-Metriken-Block im Übersichts-Reiter einer Tour.
// Spec: docs/specs/modules/feat_1435_e3a_uebersicht_wetter_block.md
// Implementation Details Punkt 1, Acceptance Criteria AC-1/AC-2/AC-3.
//
// RED heute: `tripActiveMetricNames.ts` existiert noch nicht — der Import
// unten schlägt fehl (Modul nicht gefunden), NICHT wegen fehlendem Loader.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/trip-metrics/__tests__/tripActiveMetricNames.test.ts
//
// Kein Mock-Theater: reine Funktion gegen ein realistisches Katalog-Fixture,
// dessen Struktur der echten `GET /api/metrics`-Antwort entspricht
// (api/routers/config.py:58ff) — Register-Werte (id/label/category) aus
// `src/app/metric_catalog.py` übernommen (temperature, wind, gust,
// precipitation, thunder, freezing_level, visibility).

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { resolveTripMetricsOverviewState } from '../tripActiveMetricNames.ts';
import type { MetricCatalog } from '../../../trip-detail/metricsEditor.ts';
import type { WeatherConfigMetric } from '$lib/types';

// Realistisches Katalog-Fixture — Struktur wie GET /api/metrics:
// Record<category, MetricEntry[]>. Kategorien in CATEGORY_ORDER-Reihenfolge
// (metricsEditor.ts): temperature, wind, precipitation, atmosphere, winter.
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
	],
	wind: [
		{
			id: 'wind',
			label: 'Wind',
			unit: 'km/h',
			category: 'wind',
			default_enabled: true,
			has_friendly_format: false
		},
		{
			id: 'gust',
			label: 'Böen',
			unit: 'km/h',
			category: 'wind',
			default_enabled: true,
			has_friendly_format: false
		}
	],
	precipitation: [
		{
			id: 'precipitation',
			label: 'Niederschlag',
			unit: 'mm',
			category: 'precipitation',
			default_enabled: true,
			has_friendly_format: true
		},
		{
			id: 'thunder',
			label: 'Gewitter',
			unit: '',
			category: 'precipitation',
			default_enabled: true,
			has_friendly_format: true
		}
	],
	atmosphere: [
		{
			id: 'visibility',
			label: 'Sichtweite',
			unit: 'm',
			category: 'atmosphere',
			default_enabled: false,
			has_friendly_format: false
		}
	],
	winter: [
		{
			id: 'freezing_level',
			label: 'Nullgradgrenze',
			unit: 'm',
			category: 'winter',
			default_enabled: false,
			has_friendly_format: false
		}
	]
};

describe('AC-1: aktivierte Größen erscheinen in Register-Reihenfolge, nicht Einfüge-Reihenfolge', () => {
	// AC-1: Eingabe in umgekehrter Register-Reihenfolge (gust, wind, temperature)
	// -> Ausgabe folgt der Katalog-Reihenfolge (Temperatur, Wind); "gust" ist
	// enabled:false und fehlt daher in der Namensliste (Expected Behavior Input A).
	test('Reverse-Reihenfolge-Eingabe liefert Register-Reihenfolge in der Ausgabe', () => {
		const metrics: WeatherConfigMetric[] = [
			{ metric_id: 'gust', enabled: false },
			{ metric_id: 'wind', enabled: true },
			{ metric_id: 'temperature', enabled: true }
		];
		const result = resolveTripMetricsOverviewState(metrics, catalog);
		assert.deepEqual(result, { kind: 'selected', names: ['Temperatur', 'Wind'], unknownCount: 0 });
	});
});

describe('AC-2: keine gespeicherte Auswahl -> Altbestand ohne Namensaufzählung', () => {
	// AC-2: `display_config.metrics` fehlt oder ist leer -> {kind:'altbestand'},
	// OHNE die sieben Standard-Größen aufzuzählen (die Funktion kennt sie nicht).
	test('metrics undefined liefert Altbestand', () => {
		assert.deepEqual(resolveTripMetricsOverviewState(undefined, catalog), { kind: 'altbestand' });
	});

	test('metrics als leeres Array liefert ebenfalls Altbestand', () => {
		assert.deepEqual(resolveTripMetricsOverviewState([], catalog), { kind: 'altbestand' });
	});

	test('Altbestand-Zustand trägt keine names-Liste', () => {
		const result = resolveTripMetricsOverviewState(undefined, catalog) as Record<string, unknown>;
		assert.equal('names' in result, false, 'Altbestand darf keine Namensliste tragen — sonst müsste die Funktion die Standard-Metriken kennen (Known Limitations)');
	});
});

describe('AC-3: bewusste Leerauswahl (alle enabled:false) ist vom Altbestand unterscheidbar', () => {
	// AC-3: Einträge vorhanden, aber ALLE enabled:false -> {kind:'empty'},
	// mit eigenem Wortlaut/Testid, nicht zu verwechseln mit AC-2 (Altbestand).
	test('alle Einträge enabled:false liefert kind empty', () => {
		const metrics: WeatherConfigMetric[] = [
			{ metric_id: 'temperature', enabled: false },
			{ metric_id: 'wind', enabled: false }
		];
		assert.deepEqual(resolveTripMetricsOverviewState(metrics, catalog), { kind: 'empty' });
	});

	test('empty und altbestand sind strukturell unterscheidbare Zustände', () => {
		const empty = resolveTripMetricsOverviewState([{ metric_id: 'temperature', enabled: false }], catalog);
		const altbestand = resolveTripMetricsOverviewState(undefined, catalog);
		assert.notEqual(empty.kind, altbestand.kind);
	});
});
