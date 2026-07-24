// TDD RED — Issue #1311, Scheibe C1 von Epic #1301: Entkopplung notify <->
// active_metrics (AC-3) + #1293-Wurzelfix buildRoutePool (AC-5, inkl.
// snow_line-Namensraum-Bruecke). AC-9/AC-4/AC-7-Anteile, die schon heute
// gruen sind, laufen hier als markierte Regressions-Anker mit — sie duerfen
// durch die C1-Aenderung NICHT brechen.
//
// Spec: docs/specs/modules/compare_weather_metrics_tab.md
//   § Implementation Details Abschnitt 3 (notify-Entkopplung),
//     Abschnitt 4 (buildRoutePool-Filter + ROUTE_CORRIDOR_CATALOG_IDS)
//   § AC-3, AC-4, AC-5, AC-7, AC-9
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/weatherMetricsTabCorridorCoupling.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import {
	buildRoutePool,
	buildComparePool,
	buildCompareCorridorSavePayload,
} from '../corridor-editor/corridorEditorState.ts';
import { buildComparePresetSavePayload, type CompareEditorEdits } from '../../compare/compareEditorSave.ts';
import type { ComparePreset } from '../../../types.ts';
// Issue #1350 Teil 3: buildComparePool() braucht seit der SSoT-Migration ein
// explizites `defs`-Argument (vorher Modul-Konstante COMPARE_METRIC_DEFS).
// Dieser Test braucht nur wind_max_kmh -> minimale, lokale Fixture statt des
// vollen 25-Eintraege-Katalogs (der lebt in corridorEditorState.test.ts).
import { buildCompareMetricDefs } from '../corridor-editor/compareMetricCatalogLoader.ts';

const TEST_DEFS = buildCompareMetricDefs({
	metrics: [
		{ key: 'wind_max_kmh', label: 'Windspitzen', unit: 'km/h', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, alarmCapable: true },
	],
});

// ════════════════════════════════════════════════════════════════════════
// AC-3: notify entkoppelt von active_metrics — Alarm-Funktion bleibt.
// ════════════════════════════════════════════════════════════════════════
describe('buildCompareCorridorSavePayload — AC-3 Entkopplung notify <-> active_metrics', () => {
	test('notify=true veraendert activeMetricKeys NICHT MEHR (reiner Pass-Through von original.activeMetricKeys)', () => {
		const { rows } = buildComparePool([
			{ metric: 'wind_max_kmh', range: [0, 50], notify: true, mark: false },
		], TEST_DEFS);
		const payload = buildCompareCorridorSavePayload(rows, [], {
			idealRanges: {},
			activeMetricKeys: [], // original hatte die Metrik NICHT aktiv
			metricAlertLevels: {},
		});
		assert.deepEqual(
			payload.activeMetricKeys,
			[],
			'AC-3 FAIL: notify=true hat wind_max_kmh trotzdem in active_metrics eingetragen — ' +
				'die Alarm-Checkbox darf die Mail-Metrikauswahl nicht mehr steuern (Ist: activeSet.add via notify, corridorEditorState.ts:432)'
		);
	});

	test('notify=false entfernt eine Metrik NICHT MEHR aus activeMetricKeys', () => {
		const { rows } = buildComparePool([
			{ metric: 'wind_max_kmh', range: [0, 50], notify: false, mark: true },
		], TEST_DEFS);
		const payload = buildCompareCorridorSavePayload(rows, [], {
			idealRanges: {},
			activeMetricKeys: ['wind_max_kmh'], // original hatte die Metrik aktiv (z.B. ueber den neuen Wetter-Tab gesetzt)
			metricAlertLevels: {},
		});
		assert.deepEqual(
			payload.activeMetricKeys,
			['wind_max_kmh'],
			'AC-3 FAIL: notify=false hat wind_max_kmh aus active_metrics entfernt — das darf nur noch der ' +
				'Wetter-Metriken-Tab tun, nicht das Alarm-Haekchen (Ist: activeSet.delete via notify, corridorEditorState.ts:432)'
		);
	});

	// Regressions-Anker (muss GRUEN bleiben): notify steuert weiterhin die
	// Alarm-Stufe (metric_alert_levels) — nur die active_metrics-Kopplung entfaellt.
	test('Regressions-Anker: notify steuert weiterhin metricAlertLevels (Δ-Wächter-Alarm bleibt aktiv)', () => {
		const { rows } = buildComparePool([
			{ metric: 'wind_max_kmh', range: [0, 50], notify: true, mark: false },
		], TEST_DEFS);
		const payload = buildCompareCorridorSavePayload(rows, [], {
			idealRanges: {},
			activeMetricKeys: [],
			metricAlertLevels: {},
		});
		assert.equal(
			payload.metricAlertLevels.wind_max_kmh,
			'standard',
			'Regression: notify=true muss weiterhin metric_alert_levels != "off" setzen (Alarm-Funktion bleibt erhalten)'
		);
	});

	test('Regressions-Anker: notify=false setzt metricAlertLevels weiterhin auf "off"', () => {
		const { rows } = buildComparePool([
			{ metric: 'wind_max_kmh', range: [0, 50], notify: false, mark: true },
		], TEST_DEFS);
		const payload = buildCompareCorridorSavePayload(rows, [], {
			idealRanges: {},
			activeMetricKeys: ['wind_max_kmh'],
			metricAlertLevels: { wind_max_kmh: 'sensibel' },
		});
		assert.equal(
			payload.metricAlertLevels.wind_max_kmh,
			'off',
			'Regression: notify=false muss weiterhin metric_alert_levels="off" setzen'
		);
	});

	// Regressions-Anker (F003, AC-7-Kern): unknownCorridors-Pass-Through darf
	// durch die notify-Entkopplung nicht angetastet werden.
	test('Regressions-Anker (AC-7): unknownCorridors bleiben unveraendert an corridors[] angehaengt', () => {
		const { rows } = buildComparePool([
			{ metric: 'wind_max_kmh', range: [0, 50], notify: true, mark: false },
		], TEST_DEFS);
		const unknown = [{ metric: 'foo_bar', range: [1, 2] as [number, number], notify: false, mark: true }];
		const payload = buildCompareCorridorSavePayload(
			rows,
			[],
			{ idealRanges: {}, activeMetricKeys: [], metricAlertLevels: {} },
			unknown
		);
		assert.deepEqual(
			payload.corridors.find((c) => c.metric === 'foo_bar'),
			{ metric: 'foo_bar', range: [1, 2], notify: false, mark: true },
			'Regression (AC-7): unknownCorridors-Pass-Through ist nach der notify-Entkopplung nicht mehr intakt'
		);
	});
});

// ════════════════════════════════════════════════════════════════════════
// AC-4 (teilbarer Kern-Anteil): compareEditorSave.ts's undefined-Check fuer
// activeMetricKeys ist HEUTE schon korrekt (Round-Trip via `...original`).
// Kein neuer RED-Test noetig — hier als Regressions-Anker dokumentiert, damit
// die C1-Aenderung an corridorEditorState.ts diesen Pfad nicht versehentlich
// mit-beeinflusst (die beiden Module sind unabhaengig, buildCompareCorridorSavePayload
// liefert IMMER ein activeMetricKeys-Array, den Aufrufer (Wetter-Tab) muss
// selbst entscheiden, ob er `edits.activeMetricKeys` ueberhaupt setzt).
// ════════════════════════════════════════════════════════════════════════
describe('buildComparePresetSavePayload — AC-4 Regressions-Anker (bereits heute gruen)', () => {
	test('activeMetricKeys=undefined (Tab nie geoeffnet) laesst display_config.active_metrics unangetastet', () => {
		const original: ComparePreset = {
			id: 'p1',
			name: 'Test',
			location_ids: ['a', 'b'],
			profil: 'ALLGEMEIN',
			display_config: { active_metrics: ['temp_max_c'], region: 'gr20' },
		} as ComparePreset;
		const edits: CompareEditorEdits = {
			name: 'Test',
			activityProfile: null,
			pickedIds: ['a', 'b'],
			region: 'gr20',
			idealRanges: {},
			// activeMetricKeys bewusst NICHT gesetzt (Tab nie geoeffnet, kein Klick)
		};
		const { body } = buildComparePresetSavePayload(original, edits);
		assert.deepEqual(
			(body.display_config as Record<string, unknown>).active_metrics,
			['temp_max_c'],
			'AC-4 Regression: display_config.active_metrics wurde veraendert, obwohl der Wetter-Metriken-Tab nie geoeffnet wurde'
		);
	});
});

// ════════════════════════════════════════════════════════════════════════
// AC-5 / #1293-Wurzelfix: buildRoutePool folgt der Tab-Auswahl.
// ════════════════════════════════════════════════════════════════════════
describe('buildRoutePool — AC-5 #1293 Wurzelfix: Pool folgt der Wetter-Tab-Auswahl', () => {
	test('ohne zweiten Parameter -> Alt-Verhalten bleibt erhalten (alle 6 im poolLeft, Regressions-Anker)', () => {
		const { poolLeft } = buildRoutePool([]);
		assert.equal(poolLeft.length, 6, 'Regression: buildRoutePool(corridors) ohne Filter muss weiterhin alle 6 Metriken anbieten');
	});

	test('activeCatalogMetrics filtert poolLeft auf die aus dem Wetter-Tab aktiven Metriken', () => {
		const activeCatalogMetrics = [
			{ metric_id: 'gust', enabled: true },
			{ metric_id: 'temperature', enabled: true },
			{ metric_id: 'precipitation', enabled: false }, // im Wetter-Tab abgewaehlt
			// 'thunder' und 'snowfall_limit' fehlen komplett im Katalog des Nutzers
		];
		const { poolLeft } = buildRoutePool([], activeCatalogMetrics);
		const ids = poolLeft.map((m) => m.metric).sort();
		assert.deepEqual(
			ids,
			['temperature_max', 'temperature_min', 'wind_gust'],
			'AC-5 FAIL: buildRoutePool(corridors, activeCatalogMetrics) filtert den Pool noch nicht — ' +
				`Ist: ${JSON.stringify(ids)}. Erwartet nur die Metriken, die im Wetter-Metriken-Tab aktiv sind ` +
				'(gust->wind_gust, temperature->temperature_min/max), NICHT precipitation (enabled=false), ' +
				'thunder/snowfall_limit (fehlen im Katalog)'
		);
	});

	test('leerer activeCatalogMetrics-Array -> poolLeft ist komplett leer (keine Metrik im Wetter-Tab aktiv)', () => {
		const { poolLeft } = buildRoutePool([], []);
		assert.equal(
			poolLeft.length,
			0,
			'AC-5 FAIL: bei leerer Metrik-Auswahl im Wetter-Tab muss der "+ Metrik hinzufuegen"-Pool leer sein'
		);
	});

	// Known Limitations / Adversary-Pflichtpunkt: snow_line-Namensraum-Bruecke.
	// alertMetricTable.ts::CATALOG_TO_ALERT_METRICS kennt snow_line seit #959
	// NICHT mehr (in freezing_level konsolidiert) — buildRoutePool braucht eine
	// EIGENE Mapping-Konstante (ROUTE_CORRIDOR_CATALOG_IDS), sonst verschwindet
	// der Schneefallgrenze-Korridor nach dem #1293-Fix dauerhaft.
	test('#1293 Namensraum-Bruecke: Katalog-ID "snowfall_limit" aktiv -> snow_line-Korridor bleibt im Pool waehlbar', () => {
		const activeCatalogMetrics = [{ metric_id: 'snowfall_limit', enabled: true }];
		const { poolLeft } = buildRoutePool([], activeCatalogMetrics);
		assert.ok(
			poolLeft.some((m) => m.metric === 'snow_line'),
			'AC-5 FAIL (Known-Limitations-Punkt snow_line-Mapping): snow_line-Korridor fehlt im Pool, obwohl ' +
				'die Katalog-Metrik "snowfall_limit" im Wetter-Tab aktiv ist — ' +
				'CATALOG_TO_ALERT_METRICS reicht NICHT, es braucht die eigene ROUTE_CORRIDOR_CATALOG_IDS-Bruecke'
		);
	});

	test('snowfall_limit deaktiviert (enabled=false) -> snow_line NICHT im Pool', () => {
		const activeCatalogMetrics = [{ metric_id: 'snowfall_limit', enabled: false }];
		const { poolLeft } = buildRoutePool([], activeCatalogMetrics);
		assert.equal(
			poolLeft.some((m) => m.metric === 'snow_line'),
			false,
			'AC-5 FAIL: eine im Wetter-Tab deaktivierte snowfall_limit-Metrik darf snow_line nicht im Pool anbieten'
		);
	});

	// AC-9 (Datenerhalt bei De-Selektion): ein bereits gespeicherter Korridor
	// bleibt als Zeile bestehen, auch wenn seine Metrik im Wetter-Tab nicht
	// mehr aktiv ist — nur poolLeft ("+ hinzufuegen") wird gefiltert, rows
	// (bereits gespeicherte Wertebereiche) NIE. Mit der heutigen Implementierung
	// (Filter-Parameter existiert nicht) ist dies zufaellig bereits erfuellt;
	// dieser Test ist der Regressions-Anker, der sicherstellen soll, dass die
	// #1293-Filterung in buildRoutePool NIE auf `rows` angewendet wird.
	test('AC-9 Regressions-Anker: gespeicherter snow_line-Korridor bleibt Zeile, auch wenn snowfall_limit im Filter fehlt', () => {
		const corridors = [{ metric: 'snow_line', range: [1500, null], notify: true, mark: false }];
		const activeCatalogMetrics = [{ metric_id: 'gust', enabled: true }]; // snowfall_limit NICHT aktiv
		const { rows, poolLeft } = buildRoutePool(corridors, activeCatalogMetrics);
		assert.ok(
			rows.some((r) => r.metric === 'snow_line'),
			'AC-9 FAIL: der bereits gespeicherte snow_line-Korridor verschwindet aus rows, wenn die Metrik ' +
				'im Wetter-Tab abgewaehlt ist — das waere ein stiller Datenverlust (BUG-DATALOSS-Klasse)'
		);
		assert.equal(
			poolLeft.some((m) => m.metric === 'snow_line'),
			false,
			'snow_line darf nicht gleichzeitig im "+ hinzufuegen"-Pool erscheinen, wenn es bereits eine Zeile ist'
		);
	});
});
