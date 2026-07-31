// TDD RED — Feature #1435 Etappe E1b (AC-1, AC-2, AC-3, AC-5, AC-10): welche
// vom Nutzer gewaehlten Wettergroessen KEINEN Alarm ausloesen koennen, sagt das
// zentrale Namensregister — nicht eine neue Textliste im Frontend. Der
// Klammerzusatz mit der Auswertung erscheint NUR bei Groessen, deren `label`
// im Register mehrfach vorkommt (PO-Nachbesserung 2 vom 2026-07-31).
// Spec: docs/specs/modules/feat_1435_e1b_alarm_erklaersatz.md
//
// RED heute: `deriveUnalertableSelectedMetricNames` ist in
// alarme-tab/activeAlertMetricsFromCatalog.ts noch nicht exportiert. Geladen
// wird per dynamischem Import je Test (Muster: alarme_tab_alert_metrics_from
// _catalog.test.ts), damit der fehlende Export als benannter Befund erscheint
// statt als nackter Auflose-Fehler die ganze Datei zu verschlucken.
//
// Pfadregel #1409: alle Importe relativ zu DIESER Datei — ein fester
// Hauptrepo-Pfad wuerde aus dem Worktree die unveraenderte Kopie pruefen.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/alarme-tab/__tests__/unalertableSelectedMetricNames.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { toCompareSelectionEntries } from '../../weather-metrics-tab/compareMetricSelection.ts';
import type { CompareSelectionEntry } from '../../weather-metrics-tab/compareMetricSelection.ts';
import type { CompareMetricCatalogEntry } from '../../../../types.ts';

// ── Fixture ────────────────────────────────────────────────────────────────
// Wortwoertlicher Ausschnitt der ECHTEN Antwort von GET /api/compare/metrics
// (src/output/renderers/compare_metric_catalog.py::get_compare_metric_catalog(),
// Stand 2026-07-31, 26 Eintraege) — Reihenfolge unveraendert, keine erfundenen
// Werte. Enthaelt beide Sorten (alarmfaehig/nicht), eindeutige `label` (z.B.
// „Sonnenstunden") und BEIDE Namens-Duplikate des echten Registers:
// „Temperatur" und „Gefuehlte Temperatur", je Minimum/Maximum (AC-2, AC-10).
// Jeder Eintrag traegt ein `aggregation_label` — genau deshalb reicht dessen
// blosses Vorhandensein nicht als Bedingung fuer den Klammerzusatz.
const REAL_COMPARE_METRICS_RESPONSE: { metrics: CompareMetricCatalogEntry[] } = {
	metrics: [
		{key: 'snow_depth_cm', unit: 'cm', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 200, step: 5, metric_id: 'snow_depth', aggregation: 'max', label: 'Schneehöhe', aggregation_label: 'Maximum', alertMetric: null, alarmCapable: false},
		{key: 'sunny_hours_h', unit: 'h', decimals: 1, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 12, step: 0.5, metric_id: 'sunshine', aggregation: 'sum', label: 'Sonnenstunden', aggregation_label: 'Summe', alertMetric: null, alarmCapable: false},
		{key: 'wind_max_kmh', unit: 'km/h', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, metric_id: 'wind', aggregation: 'max', label: 'Wind', aggregation_label: 'Maximum', alertMetric: 'wind_change', alarmCapable: true},
		{key: 'cloud_avg_pct', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, metric_id: 'cloud_total', aggregation: 'avg', label: 'Bewölkung', aggregation_label: 'Mittel', alertMetric: null, alarmCapable: false},
		{key: 'uv_index_max', unit: '', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 12, step: 1, metric_id: 'uv_index', aggregation: 'max', label: 'UV-Index', aggregation_label: 'Maximum', alertMetric: null, alarmCapable: false},
		{key: 'temp_max_c', unit: '°C', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: -20, rangeMax: 45, step: 1, metric_id: 'temperature', aggregation: 'max', label: 'Temperatur', aggregation_label: 'Maximum', alertMetric: 'temperature_max', alarmCapable: true},
		{key: 'temp_min_c', unit: '°C', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: -30, rangeMax: 30, step: 1, metric_id: 'temperature', aggregation: 'min', label: 'Temperatur', aggregation_label: 'Minimum', alertMetric: 'temperature_min', alarmCapable: true},
		{key: 'gust_max_kmh', unit: 'km/h', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 150, step: 5, metric_id: 'gust', aggregation: 'max', label: 'Böen', aggregation_label: 'Maximum', alertMetric: 'wind_gust', alarmCapable: true},
		{key: 'pop_max_pct', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, metric_id: 'rain_probability', aggregation: 'max', label: 'Regenwahrscheinlichkeit', aggregation_label: 'Maximum', alertMetric: null, alarmCapable: false},
		{key: 'wind_chill_min_c', unit: '°C', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: -30, rangeMax: 30, step: 1, metric_id: 'wind_chill', aggregation: 'min', label: 'Gefühlte Temperatur', aggregation_label: 'Minimum', alertMetric: null, alarmCapable: false},
		{key: 'wind_chill_max_c', unit: '°C', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: -20, rangeMax: 45, step: 1, metric_id: 'wind_chill', aggregation: 'max', label: 'Gefühlte Temperatur', aggregation_label: 'Maximum', alertMetric: null, alarmCapable: false},
		{key: 'humidity_avg_pct', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, metric_id: 'humidity', aggregation: 'avg', label: 'Luftfeuchtigkeit', aggregation_label: 'Mittel', alertMetric: null, alarmCapable: false}
	]
};

type NamesFn = (activeMetricKeys: string[], catalog: CompareSelectionEntry[]) => string[];

/** Laedt die neue Ableitung. Fehlt sie, ist DAS der Befund — mit Grund statt
 *  nacktem Auflose-Fehler. */
async function loadDerive(): Promise<NamesFn> {
	try {
		const mod = await import('../activeAlertMetricsFromCatalog.ts');
		const fn = (mod as Record<string, unknown>).deriveUnalertableSelectedMetricNames;
		if (typeof fn !== 'function') {
			assert.fail(
				'`deriveUnalertableSelectedMetricNames` ist in ' +
					'shared/alarme-tab/activeAlertMetricsFromCatalog.ts nicht exportiert — ohne sie ' +
					'verschwinden nicht alarmfaehige Groessen weiter kommentarlos aus dem ' +
					'Alarme-Reiter (#1435 E1b, Spec Implementation Details Punkt 2).'
			);
		}
		return fn as NamesFn;
	} catch (err) {
		assert.fail(
			'Die Gegenstueck-Ableitung fehlt noch: erwartet wird ' +
				'`deriveUnalertableSelectedMetricNames(activeMetricKeys, catalog)` neben ' +
				`\`deriveActiveAlertMetricsFromCatalog\` (#1435 E1b). Ursache: ${String(err)}`
		);
	}
}

/** Die Katalogantwort auf dem ECHTEN Weg — deckt mit auf, wenn `label`,
 *  `aggregation_label` oder `alertMetric` unterwegs verloren gehen. */
function catalogEntries(): CompareSelectionEntry[] {
	return toCompareSelectionEntries(REAL_COMPARE_METRICS_RESPONSE);
}

describe('#1435 E1b AC-1: die nicht alarmfaehigen Groessen werden namentlich genannt', () => {
	test('Gemischte Auswahl nennt genau die nicht alarmfaehigen Groessen', async () => {
		const derive = await loadDerive();
		// Nutzungsbeispiel der Spec (Expected Behavior A): Wind (alarmfaehig) plus
		// vier nicht alarmfaehige, davon zwei mit mehrdeutigem `label`.
		assert.deepEqual(
			derive(
				['wind_max_kmh', 'sunny_hours_h', 'cloud_avg_pct', 'wind_chill_min_c', 'wind_chill_max_c'],
				catalogEntries()
			),
			['Sonnenstunden', 'Bewölkung', 'Gefühlte Temperatur (Minimum)', 'Gefühlte Temperatur (Maximum)'],
			'Der Erklaersatz muss genau die gewaehlten Groessen ohne Alarm nennen — keine ' +
				'alarmfaehige darf mitgenannt werden, keine nicht alarmfaehige fehlen (AC-1).'
		);
	});

	test('Ein fehlendes `alertMetric`-Feld zaehlt wie „nicht alarmfaehig"', async () => {
		const derive = await loadDerive();
		// Katalog eines aelteren Servers: das Feld fehlt ganz statt `null` zu sein.
		const ohneFeld: CompareSelectionEntry[] = [
			{ metric: 'sunny_hours_h', label: 'Sonnenstunden', aggregation_label: 'Summe' }
		];
		assert.deepEqual(derive(['sunny_hours_h'], ohneFeld), ['Sonnenstunden']);
	});

	test('Unbekannte Schluessel und leere Eingaben laufen ins Leere, nicht in den Fehler', async () => {
		const derive = await loadDerive();
		assert.deepEqual(derive(['gibt_es_nicht'], catalogEntries()), []);
		assert.deepEqual(derive([], catalogEntries()), []);
		assert.deepEqual(
			derive(['cloud_avg_pct'], []),
			[],
			'Bei noch nicht geladenem Katalog darf die Ableitung nicht raten (Fehlerklasse #1320).'
		);
	});
});

describe('#1435 E1b AC-2: Klammerzusatz nur bei mehrdeutigem Namen', () => {
	test('Mehrdeutige Groessen mit Zusatz, eindeutige ohne — in EINER Auswahl', async () => {
		const derive = await loadDerive();
		// Beide Seiten der Regel gleichzeitig: „Gefuehlte Temperatur" kommt im
		// Register zweimal vor, „Sonnenstunden" genau einmal.
		const got = derive(['sunny_hours_h', 'wind_chill_min_c', 'wind_chill_max_c'], catalogEntries());
		assert.deepEqual(got, [
			'Sonnenstunden',
			'Gefühlte Temperatur (Minimum)',
			'Gefühlte Temperatur (Maximum)'
		]);
		assert.equal(
			new Set(got).size,
			3,
			'Die beiden „Gefuehlte Temperatur"-Eintraege tragen dasselbe `label` — ohne die ' +
				'Auswertung im Namen stuende derselbe Text zweimal im Satz und der Nutzer ' +
				'wuesste nicht, welche Groesse gemeint ist (AC-2).'
		);
		assert.equal(
			got.includes('Sonnenstunden (Summe)'),
			false,
			'„Sonnenstunden" traegt zwar ein `aggregation_label` („Summe"), ist im Register ' +
				'aber eindeutig — der Klammerzusatz haengt an der Mehrdeutigkeit, nicht am ' +
				'blossen Vorhandensein der Auswertung (AC-2).'
		);
	});

	test('Die Regel zaehlt Namen, sie kennt keine Namensliste', async () => {
		const derive = await loadDerive();
		// Gedachter kuenftiger Registerstand (Known Limitation „datengetrieben"):
		// „Bewoelkung" doppelt, „Gefuehlte Temperatur" nur einmal — die Regel muss
		// sich umdrehen, ohne dass jemand Code anfasst.
		const kuenftig: CompareSelectionEntry[] = [
			{ metric: 'cloud_avg_pct', label: 'Bewölkung', aggregation_label: 'Mittel', alertMetric: null },
			{ metric: 'cloud_max_pct', label: 'Bewölkung', aggregation_label: 'Maximum', alertMetric: null },
			{ metric: 'wind_chill_min_c', label: 'Gefühlte Temperatur', aggregation_label: 'Minimum', alertMetric: null }
		];
		assert.deepEqual(
			derive(['cloud_avg_pct', 'cloud_max_pct', 'wind_chill_min_c'], kuenftig),
			['Bewölkung (Mittel)', 'Bewölkung (Maximum)', 'Gefühlte Temperatur'],
			'Die Funktion darf „Temperatur"/„Gefuehlte Temperatur" nicht namentlich kennen — ' +
				'sie zaehlt die `label`-Haeufigkeit im gelieferten Katalog (AC-2, Known Limitation).'
		);
	});
});

describe('#1435 E1b AC-3: nur alarmfaehige Groessen gewaehlt → kein Satz', () => {
	test('Ausschliesslich alarmfaehige Auswahl liefert eine leere Liste', async () => {
		const derive = await loadDerive();
		assert.deepEqual(
			derive(['wind_max_kmh', 'temp_max_c', 'temp_min_c', 'gust_max_kmh'], catalogEntries()),
			[],
			'Ohne nicht alarmfaehige Groesse darf kein Erklaersatz entstehen (AC-3).'
		);
	});
});

describe('#1435 E1b AC-5: die Reihenfolge folgt dem Katalog, nicht den Klicks', () => {
	test('Umgekehrt angeklickte Auswahl erscheint dennoch in Katalog-Reihenfolge', async () => {
		const derive = await loadDerive();
		assert.deepEqual(
			derive(
				['humidity_avg_pct', 'pop_max_pct', 'uv_index_max', 'cloud_avg_pct', 'sunny_hours_h'],
				catalogEntries()
			),
			['Sonnenstunden', 'Bewölkung', 'UV-Index', 'Regenwahrscheinlichkeit', 'Luftfeuchtigkeit'],
			'Der Satz muss die Groessen in derselben stabilen Reihenfolge nennen, in der die ' +
				'Wetter-Metriken-Tabelle sie zeigt — nicht in der Klick-Reihenfolge (AC-5).'
		);
	});

	test('Die Ableitung merkt sich nichts und veraendert ihre Eingaben nicht', async () => {
		const derive = await loadDerive();
		const aktiv = ['cloud_avg_pct', 'uv_index_max'];
		const katalog = catalogEntries();
		assert.deepEqual(derive(aktiv, katalog), ['Bewölkung', 'UV-Index']);
		assert.deepEqual(
			derive(aktiv, []),
			[],
			'Die Ableitung merkt sich den Katalog intern — dann rechnet ein $derived beim ' +
				'Wechsel der Prop nicht neu (Fehlerklasse #1320).'
		);
		assert.deepEqual(aktiv, ['cloud_avg_pct', 'uv_index_max']);
		assert.equal(katalog.length, REAL_COMPARE_METRICS_RESPONSE.metrics.length);
	});
});

describe('#1435 E1b AC-10: mehrdeutig ist, was im KATALOG mehrfach vorkommt', () => {
	test('Nur eine der beiden Varianten gewaehlt — der Zusatz bleibt trotzdem', async () => {
		const derive = await loadDerive();
		// Voller Katalog (beide „Gefuehlte Temperatur"-Eintraege), aber nur der
		// Minimum-Schluessel aktiv. Zaehlte die Regel ueber die AUSWAHL (oder ueber
		// die bereits gebildete Namensliste), kaeme hier faelschlich „1" heraus.
		const got = derive(['wind_chill_min_c'], catalogEntries());
		assert.deepEqual(
			got,
			['Gefühlte Temperatur (Minimum)'],
			'Die Haeufigkeit wird gegen die Auswahl statt gegen den vollen Katalog geprueft — ' +
				'dann heisst dieselbe Groesse mal „Gefühlte Temperatur" und mal „Gefühlte ' +
				'Temperatur (Minimum)", je nachdem was der Nutzer sonst angehakt hat, und weicht ' +
				'vom Reiter „Wetter-Metriken" ab (AC-10).'
		);
		assert.equal(
			got.includes('Gefühlte Temperatur'),
			false,
			'Der blosse Name ohne Auswertung ist hier mehrdeutig: das Register kennt zwei ' +
				'Eintraege dieses Namens (AC-10).'
		);
	});

	test('Die Schreibweise einer Groesse haengt nicht an der uebrigen Auswahl', async () => {
		const derive = await loadDerive();
		const katalog = catalogEntries();
		const alleinPrefix = derive(['wind_chill_max_c'], katalog);
		const mitAnderen = derive(['sunny_hours_h', 'wind_chill_max_c', 'humidity_avg_pct'], katalog);
		assert.deepEqual(alleinPrefix, ['Gefühlte Temperatur (Maximum)']);
		assert.deepEqual(mitAnderen, [
			'Sonnenstunden',
			'Gefühlte Temperatur (Maximum)',
			'Luftfeuchtigkeit'
		]);
		assert.equal(
			mitAnderen[1],
			alleinPrefix[0],
			'Dieselbe Groesse wird je nach uebriger Auswahl unterschiedlich geschrieben — ' +
				'genau das schliesst AC-10 aus.'
		);
	});
});
