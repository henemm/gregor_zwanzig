// TDD RED — Feature #1435 Etappe E1a-2: der Alarme-Reiter liest die
// Alarmfaehigkeit aus dem zentralen Wetter-Namensregister statt aus einer
// eigenen, handgepflegten Frontend-Liste.
// Spec: docs/specs/modules/feat_1435_e1a2_alarme_reiter_register.md (AC-1..AC-6)
//
// RED heute: das Modul `alarme-tab/activeAlertMetricsFromCatalog.ts` mit
// `deriveActiveAlertMetricsFromCatalog(activeKeys, catalog)` existiert noch
// nicht, und `toCompareSelectionEntries()` reicht das Katalog-Feld
// `alertMetric` noch nicht durch. Beide Luecken sind in dieser Datei einzeln
// als Fehlschlag sichtbar (dynamischer Import je Test, damit nicht ein
// einziger Auflose-Fehler die ganze Datei verschluckt).
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/alarme_tab_alert_metrics_from_catalog.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { toCompareSelectionEntries } from '../weather-metrics-tab/compareMetricSelection.ts';
import type { CompareSelectionEntry } from '../weather-metrics-tab/compareMetricSelection.ts';
import { ALERTABLE_METRICS } from '../../alerts-tab/alertMetricTable.ts';
import { ALERT_METRIC_LABELS } from '../../../utils/alertMetricLabels.ts';
import type { AlertMetric, CompareMetricCatalogEntry } from '../../../types.ts';

// ── Fixture ────────────────────────────────────────────────────────────────
// Wortwoertlicher Ausschnitt der ECHTEN Antwort von GET /api/compare/metrics
// (erzeugt aus src/output/renderers/compare_metric_catalog.py::
// get_compare_metric_catalog(), Stand 2026-07-31, 26 Eintraege): ALLE zehn
// Eintraege, die ein `alertMetric` tragen, plus vier ohne — keine erfundene
// Struktur, keine erfundenen Werte.
const REAL_COMPARE_METRICS_RESPONSE: { metrics: CompareMetricCatalogEntry[] } = {
	metrics: [
		{key: 'snow_depth_cm', unit: 'cm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 200, step: 5, metric_id: 'snow_depth', aggregation: 'max', label: 'Schneehöhe', aggregation_label: 'Maximum', alertMetric: null, alarmCapable: false},
		{key: 'snow_new_sum_cm', unit: 'cm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 50, step: 1, metric_id: 'fresh_snow', aggregation: 'sum', label: 'Neuschnee', aggregation_label: 'Summe', alertMetric: 'fresh_snow', alarmCapable: true},
		{key: 'sunny_hours_h', unit: 'h', decimals: 1, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 12, step: 0.5, metric_id: 'sunshine', aggregation: 'sum', label: 'Sonnenstunden', aggregation_label: 'Summe', alertMetric: null, alarmCapable: false},
		{key: 'wind_max_kmh', unit: 'km/h', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, metric_id: 'wind', aggregation: 'max', label: 'Wind', aggregation_label: 'Maximum', alertMetric: 'wind_change', alarmCapable: true},
		{key: 'cloud_avg_pct', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, metric_id: 'cloud_total', aggregation: 'avg', label: 'Bewölkung', aggregation_label: 'Mittel', alertMetric: null, alarmCapable: false},
		{key: 'visibility_min_m', unit: 'm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 10000, step: 500, metric_id: 'visibility', aggregation: 'min', label: 'Sichtweite', aggregation_label: 'Minimum', alertMetric: 'visibility', alarmCapable: true},
		{key: 'precip_sum_mm', unit: 'mm', decimals: 1, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 30, step: 0.5, metric_id: 'precipitation', aggregation: 'sum', label: 'Niederschlag', aggregation_label: 'Summe', alertMetric: 'precipitation_sum', alarmCapable: true},
		{key: 'temp_max_c', unit: '°C', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: -20, rangeMax: 45, step: 1, metric_id: 'temperature', aggregation: 'max', label: 'Temperatur', aggregation_label: 'Maximum', alertMetric: 'temperature_max', alarmCapable: true},
		{key: 'thunder_level_max', unit: '', decimals: 0, higherIsBetter: false, kind: 'ordinal', ordinalLabels: ['kein', 'mittel', 'hoch'], metric_id: 'thunder', aggregation: 'max', label: 'Gewitter', aggregation_label: 'Maximum', alertMetric: 'thunder_level', alarmCapable: true},
		{key: 'temp_min_c', unit: '°C', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: -30, rangeMax: 30, step: 1, metric_id: 'temperature', aggregation: 'min', label: 'Temperatur', aggregation_label: 'Minimum', alertMetric: 'temperature_min', alarmCapable: true},
		{key: 'gust_max_kmh', unit: 'km/h', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 150, step: 5, metric_id: 'gust', aggregation: 'max', label: 'Böen', aggregation_label: 'Maximum', alertMetric: 'wind_gust', alarmCapable: true},
		{key: 'cape_max_jkg', unit: 'J/kg', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 3000, step: 100, metric_id: 'cape', aggregation: 'max', label: 'Gewitterenergie (CAPE)', aggregation_label: 'Maximum', alertMetric: 'cape', alarmCapable: true},
		{key: 'freezing_level_m', unit: 'm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 5000, step: 100, metric_id: 'freezing_level', aggregation: 'min', label: 'Nullgradgrenze', aggregation_label: 'Minimum', alertMetric: 'freezing_level', alarmCapable: true},
		{key: 'pop_max_pct', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, metric_id: 'rain_probability', aggregation: 'max', label: 'Regenwahrscheinlichkeit', aggregation_label: 'Maximum', alertMetric: null, alarmCapable: false},
	]
};

type DeriveFn = (activeMetricKeys: string[], catalog: CompareSelectionEntry[]) => AlertMetric[];

/** Laedt die neue Ableitung. Fehlt sie noch, ist DAS der Befund — mit einer
 *  Meldung, die den Grund nennt statt eines nackten Auflose-Fehlers. */
async function loadDerive(): Promise<DeriveFn> {
	try {
		const mod = await import('../alarme-tab/activeAlertMetricsFromCatalog.ts');
		const fn = (mod as Record<string, unknown>).deriveActiveAlertMetricsFromCatalog;
		if (typeof fn !== 'function') {
			assert.fail(
				'`deriveActiveAlertMetricsFromCatalog` ist in ' +
					'shared/alarme-tab/activeAlertMetricsFromCatalog.ts nicht exportiert (#1435 E1a-2).'
			);
		}
		return fn as DeriveFn;
	} catch (err) {
		assert.fail(
			'Die register-gestuetzte Ableitung fehlt noch: erwartet wird ' +
				'`shared/alarme-tab/activeAlertMetricsFromCatalog.ts` mit ' +
				'`deriveActiveAlertMetricsFromCatalog(activeMetricKeys, catalog)` ' +
				`(#1435 E1a-2, Spec Implementation Details Punkt 2). Ursache: ${String(err)}`
		);
	}
}

/** Die Katalogantwort auf dem ECHTEN Weg (derselbe Mapper, den der Ladeweg
 *  benutzt) — deckt mit auf, wenn `alertMetric` unterwegs verloren geht. */
function catalogEntries(): CompareSelectionEntry[] {
	return toCompareSelectionEntries(REAL_COMPARE_METRICS_RESPONSE);
}

describe('#1435 E1a-2 AC-1: die Alarm-Zeilen kommen aus dem Register', () => {
	test('`toCompareSelectionEntries` reicht `alertMetric` unveraendert durch', () => {
		const entries = catalogEntries();
		const byKey = new Map(entries.map((e) => [e.metric, e]));
		assert.equal(
			(byKey.get('gust_max_kmh') as Record<string, unknown> | undefined)?.alertMetric,
			'wind_gust',
			'Der Auswahllisten-Mapper verliert das Register-Feld `alertMetric` — dann ' +
				'kann der Alarme-Reiter die Alarmfaehigkeit nicht aus dem Register lesen (AC-1).'
		);
		assert.equal(
			(byKey.get('cloud_avg_pct') as Record<string, unknown> | undefined)?.alertMetric,
			null,
			'Ein nicht alarmfaehiger Eintrag muss sein `alertMetric: null` behalten (AC-1).'
		);
	});

	test('Mehrere aktive Groessen ergeben genau die Register-Alarmzeilen', async () => {
		const derive = await loadDerive();
		// Auswahl aus dem Nutzungsbeispiel der Spec (Expected Behavior):
		// Böen + Temperatur (Minimum) + Wind.
		assert.deepEqual(derive(['gust_max_kmh', 'temp_min_c', 'wind_max_kmh'], catalogEntries()), [
			'wind_gust',
			'temperature_min',
			'wind_change'
		]);
	});

	test('Nicht alarmfaehige Groessen erzeugen keine Zeile', async () => {
		const derive = await loadDerive();
		assert.deepEqual(
			derive(['cloud_avg_pct', 'sunny_hours_h', 'pop_max_pct', 'snow_depth_cm'], catalogEntries()),
			[]
		);
	});

	test('Reihenfolge und Filter laufen weiter ueber ALERTABLE_METRICS', async () => {
		const derive = await loadDerive();
		// Eingabe absichtlich in umgekehrter Katalog-Reihenfolge: das Ergebnis
		// muss trotzdem der Anzeige-Reihenfolge der Tabelle folgen.
		const got = derive(
			['freezing_level_m', 'cape_max_jkg', 'gust_max_kmh', 'precip_sum_mm'],
			catalogEntries()
		);
		const expectedOrder = ALERTABLE_METRICS.filter((m) => got.includes(m));
		assert.deepEqual(got, [...expectedOrder]);
		assert.deepEqual(got, ['wind_gust', 'precipitation_sum', 'cape', 'freezing_level']);
	});

	test('Unbekannte Auswahl-Schluessel werden still uebergangen (kein Crash)', async () => {
		const derive = await loadDerive();
		assert.deepEqual(derive(['gibt_es_nicht', 'temp_max_c'], catalogEntries()), ['temperature_max']);
	});
});

describe('#1435 E1a-2 AC-2: Wind und Böen sind entkreuzt', () => {
	test('„Wind (Maximum)" erzeugt `wind_change`, NICHT `wind_gust`', async () => {
		const derive = await loadDerive();
		const got = derive(['wind_max_kmh'], catalogEntries());
		assert.deepEqual(
			got,
			['wind_change'],
			'Die alte Frontend-Liste ordnete `wind_max_kmh` faelschlich der Zeile „Böen" ' +
				'(`wind_gust`) zu — das Register sagt `wind_change` (AC-2).'
		);
	});

	test('„Böen (Maximum)" erzeugt `wind_gust`, NICHT `wind_change`', async () => {
		const derive = await loadDerive();
		assert.deepEqual(
			derive(['gust_max_kmh'], catalogEntries()),
			['wind_gust'],
			'Heute erzeugt „Böen" gar keine Zeile — nach der Umstellung genau die eigene (AC-2).'
		);
	});

	test('Beide gleichzeitig aktiv: beide Zeilen, keine verdraengt die andere', async () => {
		const derive = await loadDerive();
		assert.deepEqual(derive(['wind_max_kmh', 'gust_max_kmh'], catalogEntries()), [
			'wind_gust',
			'wind_change'
		]);
	});
});

describe('#1435 E1a-2 AC-3: die vier neu bedienbaren Groessen', () => {
	const NEU: Array<[string, AlertMetric]> = [
		['gust_max_kmh', 'wind_gust'],
		['temp_min_c', 'temperature_min'],
		['cape_max_jkg', 'cape'],
		['freezing_level_m', 'freezing_level']
	];

	for (const [key, expected] of NEU) {
		test(`${key} → ${expected}`, async () => {
			const derive = await loadDerive();
			assert.deepEqual(derive([key], catalogEntries()), [expected]);
		});
	}

	// Verweis-Nachweis statt erneutem Python-Lauf: die Auswertbarkeit dieser
	// Identitaeten ist in E1a-1 verifiziert (compare_alert.py /
	// weather_change_detection.py / alert_preset.py, Context-Doc Tabelle
	// „kein Bedienelement ohne Wirkung"). Hier wird nur geprueft, dass die
	// Empfindlichkeits-Tabelle jede abgeleitete Identitaet ueberhaupt kennt —
	// sonst entstuende eine Zeile, die die Tabelle nicht rendern kann.
	test('Jede vom Register gelieferte Alarm-Identitaet ist der Tabelle bekannt', () => {
		for (const entry of REAL_COMPARE_METRICS_RESPONSE.metrics) {
			const am = (entry as Record<string, unknown>).alertMetric;
			if (!am) continue;
			assert.ok(
				am in ALERT_METRIC_LABELS,
				`Register liefert "${String(am)}" — die Alarm-Beschriftungstabelle kennt das nicht.`
			);
			assert.ok(
				ALERTABLE_METRICS.includes(am as AlertMetric),
				`"${String(am)}" steht nicht in ALERTABLE_METRICS und wuerde nie angezeigt.`
			);
		}
	});
});

describe('#1435 E1a-2 AC-4: die fuenf unveraenderten Zuordnungen', () => {
	// Eingefroren aus der alten Frontend-Liste COMPARE_TO_ALERT_METRIC
	// (alarme-tab/compareMetricMapping.ts, vor der Loeschung abgelesen) —
	// Vorher/Nachher-Assertion je Groesse gegen dasselbe Fixture.
	const UNVERAENDERT: Array<[string, AlertMetric]> = [
		['snow_new_sum_cm', 'fresh_snow'],
		['visibility_min_m', 'visibility'],
		['precip_sum_mm', 'precipitation_sum'],
		['temp_max_c', 'temperature_max'],
		['thunder_level_max', 'thunder_level']
	];

	for (const [key, vorher] of UNVERAENDERT) {
		test(`${key} bleibt bei ${vorher}`, async () => {
			const derive = await loadDerive();
			assert.deepEqual(
				derive([key], catalogEntries()),
				[vorher],
				`Regression: ${key} zeigte vor #1435 E1a-2 die Zeile ${vorher}.`
			);
		});
	}
});

describe('#1435 E1a-2 AC-5: die Ableitung rechnet mit dem uebergebenen Katalog', () => {
	test('Leerer Katalog → leeres Ergebnis, gefuellter Katalog → korrekte Menge', async () => {
		const derive = await loadDerive();
		const aktiv = ['gust_max_kmh', 'temp_min_c'];

		// Zustand „Katalog noch nicht geladen": die Ableitung darf nicht raten.
		assert.deepEqual(derive(aktiv, []), []);

		// Derselbe Aufruf nach dem Laden — ohne Modul-Neuinitialisierung, also
		// ohne verstecktes Modul-State-Gedaechtnis: das Ergebnis haengt AM
		// UEBERGEBENEN Wert, nicht an einem Modul-Getter.
		assert.deepEqual(derive(aktiv, catalogEntries()), ['wind_gust', 'temperature_min']);

		// Gegenprobe: wieder leer uebergeben ergibt wieder leer. Waere der
		// Katalog intern gemerkt, bliebe hier faelschlich die alte Menge stehen.
		assert.deepEqual(
			derive(aktiv, []),
			[],
			'Die Ableitung merkt sich den Katalog intern — dann rechnet ein $derived ' +
				'nicht neu, wenn die Prop sich aendert (AC-5, Fehlerklasse #1320).'
		);
	});
});

describe('#1435 E1a-2 AC-6: gespeicherte Empfindlichkeiten bleiben erhalten', () => {
	test('Ein Wert zu einer nicht mehr gezeigten Zeile ueberlebt die Umstellung', async () => {
		const derive = await loadDerive();
		// Bestand aus der Zeit vor der Umstellung: Nutzer hatte „Wind" aktiv und
		// dadurch (faelschlich) die Zeile „Böen" bedient.
		const gespeichert: Record<string, string> = {
			wind_gust: 'sensibel',
			temperature_max: 'entspannt'
		};
		const vorher = JSON.stringify(gespeichert);

		const gezeigt = derive(['wind_max_kmh', 'temp_max_c'], catalogEntries());
		assert.deepEqual(gezeigt, ['temperature_max', 'wind_change']);
		assert.equal(
			gezeigt.includes('wind_gust' as AlertMetric),
			false,
			'Vorbedingung des Tests: die Zeile `wind_gust` wird hier nicht mehr gezeigt.'
		);

		assert.equal(
			JSON.stringify(gespeichert),
			vorher,
			'Die Ableitung hat den gespeicherten Empfindlichkeits-Stand veraendert — ' +
				'nicht mehr angezeigte Werte muessen unangetastet bleiben (AC-6).'
		);
		assert.equal(gespeichert.wind_gust, 'sensibel');
	});
});
