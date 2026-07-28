// Issue #1357 (Epic #1372 S4a) — Auswertungswahl im Trip-Editor.
// Spec: docs/specs/modules/trip_aggregation_selection.md (AC-5, AC-6, AC-8, AC-9)
//
// Zwei Nachweise:
//  1. AC-5 — die Auswahl erscheint NUR bei Groessen mit mehr als einer
//     berechenbaren Auswertung (kein wirkungsloses Bedienelement).
//  2. AC-6 — die getroffene Wahl ueberlebt den Speicherweg. Genau hier lag der
//     Datenverlust: `buildWeatherConfigMetrics` baut jeden Metrik-Eintrag beim
//     Speichern NEU auf; zusammen mit `mergeConfigMap` (Go, ersetzt den
//     Schluessel `metrics` komplett) waere die Wahl nach dem ersten Speichern
//     weg.
//
// Kein Rendering-Harness fuer Svelte-5-Runen im node:test-Setup — die
// Sichtbarkeits-Regel wird deshalb an der reinen Funktion geprueft, die die
// Komponente dafuer benutzt (Praezedenz: day_window_card.test.ts).

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import {
	aggregationChoices, aggregationOptions, choiceAggregations, defaultAggregations,
	effectiveAggregations, selectedChoiceId, showsAggregationChoice,
} from '../aggregationSelection.ts';
import { buildWeatherConfigMetrics } from '../../../trip-detail/metricsEditor.ts';
import { weatherMetricsTabSections } from '../weatherMetricsTabSections.ts';

const here = dirname(fileURLToPath(import.meta.url));
const TAB = join(here, '..', '..', 'WeatherMetricsTab.svelte');
const ROW = join(here, '..', 'AggregationMetricRow.svelte');

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
const PRECIPITATION = {
	id: 'precipitation', label: 'Niederschlag', unit: 'mm', category: 'precipitation',
	default_enabled: true, has_friendly_format: false,
	aggregations: [{ id: 'sum', label: 'Summe' }],
};

describe('AC-5: Auswahl nur, wo es etwas zu waehlen gibt', () => {
	test('Temperatur und gefuehlte Temperatur bekommen eine Auswahl', () => {
		assert.equal(showsAggregationChoice(TEMPERATURE), true);
		assert.equal(showsAggregationChoice(WIND_CHILL), true);
	});

	test('Wind und Niederschlag (genau eine Auswertung) bekommen KEINE Auswahl', () => {
		assert.equal(showsAggregationChoice(WIND), false, 'Wind zeigt ein wirkungsloses Bedienelement');
		assert.equal(showsAggregationChoice(PRECIPITATION), false);
	});

	test('unbekannte Groesse / fehlender Katalog-Eintrag: keine Auswahl, kein Absturz', () => {
		assert.equal(showsAggregationChoice(undefined), false);
		assert.deepEqual(aggregationOptions(undefined), []);
	});

	test('die Komponente filtert ueber genau diese Funktion, nicht ueber eine getippte Metrik-Liste', () => {
		const src = readFileSync(TAB, 'utf8');
		assert.match(src, /showsAggregationChoice\(metricById\[id\]\)/,
			'AC-5 FAIL: Sichtbarkeit haengt nicht an showsAggregationChoice()');
		assert.ok(!/aggregationMetricIds\s*=\s*\[\s*'temperature'/.test(src),
			'AC-5 FAIL: getippte Metrik-Liste statt Katalog-Ableitung');
	});
});

describe('Vorbelegung', () => {
	test('ohne Nutzereinschraenkung: Tiefst- UND Hoechstwert, nie zusaetzlich der Mittelwert', () => {
		assert.deepEqual(defaultAggregations(TEMPERATURE), ['min', 'max']);
		assert.deepEqual(defaultAggregations(WIND_CHILL), ['min', 'max']);
	});

	test('AC-8: eine ausdruecklich geleerte Wahl bleibt leer (kein Auffuellen mit der Vorgabe)', () => {
		assert.deepEqual(effectiveAggregations(WIND_CHILL, []), []);
	});

	test('gespeicherte Wahl gewinnt, unbekannte Eintraege fallen raus', () => {
		assert.deepEqual(effectiveAggregations(WIND_CHILL, ['max']), ['max']);
		assert.deepEqual(effectiveAggregations(WIND_CHILL, ['avg', 'max']), ['max']);
	});

});

// PO 2026-07-28: „Es gibt kein zusaetzlich: entweder oder." Die Wahl ist eine
// Einzelwahl — die gemischte Kombination, aus der die Kachel nur einen Teil
// zeigen konnte (Adversary-Befund F001), kann gar nicht mehr entstehen.
describe('Einzelwahl: die Moeglichkeiten kommen aus dem Katalog', () => {
	test('Temperatur bietet vier Moeglichkeiten, gefuehlte Temperatur drei', () => {
		assert.deepEqual(
			aggregationChoices(TEMPERATURE).map((c) => c.id),
			['range', 'min', 'max', 'avg'],
		);
		assert.deepEqual(
			aggregationChoices(WIND_CHILL).map((c) => c.id),
			['range', 'min', 'max'],
			'gefuehlte Temperatur bekommt „nur Mittelwert", obwohl der Katalog dort kein avg fuehrt',
		);
	});

	test('jede Moeglichkeit bildet auf genau eine gespeicherte Liste ab', () => {
		assert.deepEqual(choiceAggregations(TEMPERATURE, 'range'), ['min', 'max']);
		assert.deepEqual(choiceAggregations(TEMPERATURE, 'min'), ['min']);
		assert.deepEqual(choiceAggregations(TEMPERATURE, 'max'), ['max']);
		assert.deepEqual(choiceAggregations(TEMPERATURE, 'avg'), ['avg']);
		assert.deepEqual(choiceAggregations(WIND_CHILL, 'avg'), [],
			'gefuehlte Temperatur laesst sich auf den dort unmoeglichen Mittelwert stellen');
	});

	test('eine Groesse mit nur einer Auswertung hat auch nur eine Moeglichkeit', () => {
		assert.deepEqual(aggregationChoices(WIND).map((c) => c.id), ['max']);
		assert.equal(showsAggregationChoice(WIND), false);
	});

	test('gespeicherte Wahl -> ausgewaehlte Moeglichkeit (hin und zurueck)', () => {
		for (const id of ['range', 'min', 'max', 'avg']) {
			const saved = choiceAggregations(TEMPERATURE, id);
			assert.equal(selectedChoiceId(TEMPERATURE, saved), id,
				`Moeglichkeit ${id} kommt nach dem Speichern nicht zurueck`);
		}
	});

	test('AC-8: die leere Wahl waehlt nichts aus, statt ungefragt etwas anzuhaken', () => {
		assert.equal(selectedChoiceId(WIND_CHILL, []), null);
	});

	test('ohne Nutzereinschraenkung ist die Spanne ausgewaehlt', () => {
		assert.equal(selectedChoiceId(TEMPERATURE, undefined), 'range');
		assert.equal(selectedChoiceId(WIND_CHILL, undefined), 'range');
	});
});

describe('Altbestand: Listen ohne Entsprechung werden nicht still verworfen', () => {
	test('["min","max","avg"] (Katalog-Vorgabe) bedeutet Spanne', () => {
		assert.deepEqual(effectiveAggregations(TEMPERATURE, ['min', 'max', 'avg']), ['min', 'max']);
		assert.equal(selectedChoiceId(TEMPERATURE, ['min', 'max', 'avg']), 'range');
	});

	test('["min","avg"] wird auf die naechstliegende Moeglichkeit abgebildet, nicht auf leer', () => {
		assert.deepEqual(effectiveAggregations(TEMPERATURE, ['min', 'avg']), ['min']);
		assert.equal(selectedChoiceId(TEMPERATURE, ['min', 'avg']), 'min');
	});

	test('["max","avg"] bevorzugt ebenfalls den Extremwert', () => {
		assert.equal(selectedChoiceId(TEMPERATURE, ['max', 'avg']), 'max');
	});

	test('nur der Mittelwert bleibt der Mittelwert', () => {
		assert.equal(selectedChoiceId(TEMPERATURE, ['avg']), 'avg');
	});
});

describe('AC-6: die Wahl ueberlebt den Speicherweg (buildWeatherConfigMetrics)', () => {
	const catalog = { temperature: [TEMPERATURE, WIND_CHILL], wind: [WIND] };
	const buckets = { primary: ['temperature', 'wind_chill'], secondary: [], off: ['wind'] };

	test('gewaehlte Auswertungen landen im PUT-Payload', () => {
		const out = buildWeatherConfigMetrics(buckets, {}, {}, catalog, {
			wind_chill: ['max'],
		});
		const wc = out.find((m) => m.metric_id === 'wind_chill');
		assert.deepEqual(wc?.aggregations, ['max'],
			`AC-6 FAIL: Auswertungswahl geht beim Speichern verloren — ${JSON.stringify(wc)}`);
	});

	test('AC-8: die leere Wahl wird als leere Liste gespeichert, nicht weggelassen', () => {
		const out = buildWeatherConfigMetrics(buckets, {}, {}, catalog, { wind_chill: [] });
		const wc = out.find((m) => m.metric_id === 'wind_chill');
		assert.deepEqual(wc?.aggregations, [],
			'AC-8 FAIL: leere Wahl wird nicht gespeichert und faellt auf die Vorgabe zurueck');
	});

	test('unberuehrte Groessen tragen das Feld gar nicht (Katalog-Vorgabe greift)', () => {
		const out = buildWeatherConfigMetrics(buckets, {}, {}, catalog, { wind_chill: ['max'] });
		const temp = out.find((m) => m.metric_id === 'temperature');
		assert.equal(temp?.aggregations, undefined,
			'unberuehrte Groesse bekommt eine erfundene Einschraenkung');
	});

	test('Bestandsaufrufer ohne den neuen Parameter bleiben unveraendert (additiv)', () => {
		const out = buildWeatherConfigMetrics(buckets, {}, {}, catalog);
		assert.ok(out.every((m) => m.aggregations === undefined));
	});

	test('die Komponente reicht aggregationsMap in den Payload durch', () => {
		const src = readFileSync(TAB, 'utf8');
		assert.match(src, /buildWeatherConfigMetrics\([^)]*aggregationsMap\)/,
			'AC-6 FAIL: WeatherMetricsTab uebergibt die Auswahl nicht an den Payload-Bau');
		assert.match(src, /aggregationsMap,\s*reportConfig/,
			'AC-6 FAIL: aggregationsMap fehlt im Dirty-Vergleich — die Wahl waere unspeicherbar');
	});
});

describe('AC-9: der Ortsvergleich bekommt die Flaeche NICHT', () => {
	test("'auswertungen' ist nur im Trip-Kontext sichtbar", () => {
		assert.ok(weatherMetricsTabSections('route').includes('auswertungen'));
		assert.ok(!weatherMetricsTabSections('vergleich').includes('auswertungen'),
			'AC-9 FAIL: Ortsvergleich zeigt eine Flaeche ohne Mail-Wirkung (Attrappe)');
	});

	test('die Zeilen-Komponente liegt im geteilten Baustein-Ordner, nicht unter trip-detail/', () => {
		const src = readFileSync(ROW, 'utf8');
		assert.match(src, /AggregationChoice/,
			'Zeilen-Komponente nutzt nicht den geteilten Typ aus aggregationSelection.ts');
	});
});
