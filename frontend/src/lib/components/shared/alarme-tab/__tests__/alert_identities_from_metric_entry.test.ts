// TDD RED — Fix #1544/#1545: der Trip-Alarme-Reiter leitet seine Zeilen aus
// Auswahl x Alarmfaehigkeit-aus-dem-zentralen-Register ab statt aus den
// persistierten Schluesseln von `metric_alert_levels` (Fehlerklassen 1-3,
// s. Kontext-Dokument).
// Spec: docs/specs/modules/fix_1544_1545_trip_alarm_zeilen_ableitung.md
//   Implementation Details Punkt 2, Acceptance Criteria AC-1, AC-2, AC-7.
//
// Diese Datei prueft den atomaren Baustein: `alertIdentitiesForMetricEntry`
// liest `aggregations[].alert_metric` UND `change_alert_metric` eines
// EINZELNEN Katalog-Eintrags (MetricEntry) und liefert die zugehoerigen
// Alarm-Identitaeten, dedupliziert. Die zweite, trip-weite Ableitung
// (Auswahl x Katalog, inkl. Altbestands-Sonderfall und Reihenfolge) steht in
// `trip_active_alert_metrics_derivation.test.ts` (AC-3/4/5/8).
//
// RED heute: `frontend/src/lib/components/shared/alarme-tab/
// tripAlertMetricsFromCatalog.ts` mit dem Export
// `alertIdentitiesForMetricEntry(entry: MetricEntry): AlertMetric[]`
// existiert noch nicht.
//
// Pfadregel #1409: alle Importe relativ zu DIESER Datei.
//
// Kein Mock-Theater: reine Funktionstests gegen Katalog-Fixtures, deren
// Struktur UND Werte der echten `GET /api/metrics`-Antwort entsprechen
// (api/routers/config.py:58-107), abgeleitet aus dem echten Register
// `src/app/metric_catalog.py` (Temperatur :95-115, Boeen/"gust" :222-231,
// Luftfeuchtigkeit :174-186). `alert_metric_for()`/`available_aggregations()`
// (:591-632) wurden von Hand nachvollzogen, um die `aggregations[]`-Werte zu
// bilden — siehe Kommentare je Fixture.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/alarme-tab/__tests__/alert_identities_from_metric_entry.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import type { AlertMetric, MetricEntry } from '../../../../types.ts';

type AlertIdentitiesFn = (entry: MetricEntry) => AlertMetric[];

/** Laedt die neue Ableitung. Fehlt sie noch, ist DAS der Befund — mit einer
 *  Meldung, die den Grund nennt statt eines nackten Auflose-Fehlers. */
async function loadAlertIdentitiesForMetricEntry(): Promise<AlertIdentitiesFn> {
	try {
		const mod = await import('../tripAlertMetricsFromCatalog.ts');
		const fn = (mod as Record<string, unknown>).alertIdentitiesForMetricEntry;
		if (typeof fn !== 'function') {
			assert.fail(
				'`alertIdentitiesForMetricEntry` ist in ' +
					'shared/alarme-tab/tripAlertMetricsFromCatalog.ts nicht exportiert ' +
					'(#1544/#1545, Spec Implementation Details Punkt 2).'
			);
		}
		return fn as AlertIdentitiesFn;
	} catch (err) {
		assert.fail(
			'Die register-gestuetzte Identitaets-Ableitung fehlt noch: erwartet wird ' +
				'`shared/alarme-tab/tripAlertMetricsFromCatalog.ts` mit ' +
				'`alertIdentitiesForMetricEntry(entry)` (#1544/#1545). ' +
				`Ursache: ${String(err)}`
		);
	}
}

// ── Fixtures — wortwoertlich aus dem echten Register abgeleitet ────────────

// Temperatur (metric_catalog.py:95-115): summary_fields hat min/max/avg ->
// available_aggregations() liefert genau diese drei in dieser Reihenfolge
// (_AGGREGATION_ORDER = min,max,avg,sum). alert_metrics={"min":
// "temperature_min","max":"temperature_max"} -> alert_metric_for() liefert
// fuer "avg" NICHT den change-Fallback (die Groesse deklariert eigene
// Identitaeten), sondern None -- siehe alert_metric_for() Docstring
// Adversary-Fund F001. change_alert_metric="temperature_change" steht
// SEPARAT am Eintrag (nicht an einer Auswertung).
const TEMPERATURE_ENTRY: MetricEntry = {
	id: 'temperature',
	label: 'Temperatur',
	unit: '°C',
	category: 'temperature',
	default_enabled: true,
	has_friendly_format: false,
	change_alert_metric: 'temperature_change',
	aggregations: [
		{ id: 'min', label: 'Minimum', alert_metric: 'temperature_min' },
		{ id: 'max', label: 'Maximum', alert_metric: 'temperature_max' },
		{ id: 'avg', label: 'Mittel', alert_metric: null }
	]
} as unknown as MetricEntry;

// Boeen / "gust" (metric_catalog.py:222-231): summary_fields nur "max" ->
// eine Auswertung, alert_metrics={"max":"wind_gust"}. Kein
// change_alert_metric an dieser Groesse.
const GUST_ENTRY: MetricEntry = {
	id: 'gust',
	label: 'Böen',
	unit: 'km/h',
	category: 'wind',
	default_enabled: true,
	has_friendly_format: false,
	change_alert_metric: null,
	aggregations: [{ id: 'max', label: 'Maximum', alert_metric: 'wind_gust' }]
} as unknown as MetricEntry;

// Luftfeuchtigkeit (metric_catalog.py:174-186, ADR-0010 Vorboten-Metrik):
// alert_metrics={} (nie gesetzt) UND change_alert_metric=None -> KEINE
// Alarm-Identitaet, strukturell -- nicht nur "off" per Konvention.
const HUMIDITY_ENTRY: MetricEntry = {
	id: 'humidity',
	label: 'Luftfeuchtigkeit',
	unit: '%',
	category: 'temperature',
	default_enabled: false,
	has_friendly_format: false,
	change_alert_metric: null,
	aggregations: [{ id: 'avg', label: 'Mittel', alert_metric: null }]
} as unknown as MetricEntry;

describe('#1544/#1545 AC-7: Temperatur traegt alle drei Identitaeten gleichzeitig', () => {
	test('Minimum, Maximum UND Aenderungsrate erscheinen zusammen, dedupliziert', async () => {
		const fn = await loadAlertIdentitiesForMetricEntry();
		const got = fn(TEMPERATURE_ENTRY);
		assert.deepEqual(
			[...got].sort(),
			['temperature_change', 'temperature_max', 'temperature_min'].sort(),
			'Eine aktivierte Temperatur-Metrik muss alle drei zugehoerigen Alarm-' +
				`Identitaeten liefern (AC-7). Erhalten: ${JSON.stringify(got)}`
		);
		assert.equal(
			new Set(got).size,
			got.length,
			`Ergebnis enthaelt Duplikate: ${JSON.stringify(got)}`
		);
	});
});

describe('#1544/#1545 AC-1: eine einfache alarmfaehige Groesse liefert ihre Identitaet', () => {
	test('Boeen ("gust") liefert `wind_gust` — unabhaengig von jeder gespeicherten Stufe', async () => {
		const fn = await loadAlertIdentitiesForMetricEntry();
		const got = fn(GUST_ENTRY);
		assert.deepEqual(
			got,
			['wind_gust'],
			'Diese Ableitung kennt gar kein `metric_alert_levels` -- die Identitaet ' +
				'muss allein aus der Aktivierung + Register kommen (Fehlerklasse 1, ' +
				`unsichtbare Scharfschaltung). Erhalten: ${JSON.stringify(got)}`
		);
	});
});

describe('#1544/#1545 AC-2: Luftfeuchtigkeit erzeugt strukturell keine Zeile', () => {
	test('Weder aus `aggregations[]` noch aus `change_alert_metric` entsteht eine Identitaet', async () => {
		const fn = await loadAlertIdentitiesForMetricEntry();
		const got = fn(HUMIDITY_ENTRY);
		assert.deepEqual(
			got,
			[],
			'Luftfeuchtigkeit ist laut Register nicht alarmfaehig (ADR-0010) -- eine ' +
				'nicht-leere Rueckgabe waere die Geisterzeile aus #1545. ' +
				`Erhalten: ${JSON.stringify(got)}`
		);
	});

	test('Ein Eintrag ganz ohne Aggregations-Daten stuerzt nicht ab und liefert leer', async () => {
		const fn = await loadAlertIdentitiesForMetricEntry();
		const minimal = {
			id: 'sunshine',
			label: 'Sonnenstunden',
			unit: 'h',
			category: 'atmosphere',
			default_enabled: true,
			has_friendly_format: false
		} as unknown as MetricEntry;
		assert.deepEqual(fn(minimal), []);
	});
});

// ── Adversary Fix-Loop, F002: Register-LESUNG statt Namensliste ─────────────
// Befund: Ersetzt man den generischen Durchlauf durch `aggregations[]` /
// `change_alert_metric` durch eine Handliste mit den vier Kennungen, die in
// allen Fixtures vorkommen (`temperature`, `gust`, `cape`, `humidity`),
// bleiben alle 18 betroffenen Tests gruen -- dieselbe Krankheit wie #1435 E4.
// Die Eintraege unten sind darum BEWUSST erfunden (kein Mensch haette sie in
// einer solchen Handliste), tragen aber echte `MetricEntry`-Struktur (Form aus
// api/routers/config.py:58-107).
describe('#1544/#1545 F002: die Ableitung LIEST das Register, sie zaehlt keine Namen auf', () => {
	test('Eine im Fixture-Bestand unbekannte Kennung wird korrekt aufgeloest', async () => {
		const fn = await loadAlertIdentitiesForMetricEntry();
		const unbekannt = {
			id: 'zenitstrahlung',
			label: 'Zenitstrahlung',
			unit: 'W/m²',
			category: 'atmosphere',
			default_enabled: false,
			has_friendly_format: false,
			change_alert_metric: 'zenitstrahlung_change',
			aggregations: [
				{ id: 'max', label: 'Maximum', alert_metric: 'zenitstrahlung_max' },
				{ id: 'avg', label: 'Mittel', alert_metric: null }
			]
		} as unknown as MetricEntry;
		const got = fn(unbekannt);
		assert.deepEqual(
			got,
			['zenitstrahlung_max', 'zenitstrahlung_change'],
			'Eine Groesse, die in KEINER plausiblen Handliste stuende, muss allein ' +
				'aus ihrer Struktur (`aggregations[].alert_metric` + ' +
				'`change_alert_metric`) aufgeloest werden. Leeres oder unvollstaendiges ' +
				'Ergebnis heisst: die Ableitung zaehlt Namen auf, statt das Register zu ' +
				`lesen (F002). Erhalten: ${JSON.stringify(got)}`
		);
	});

	test('Gegenprobe: dieselbe unbekannte Kennung OHNE Identitaeten liefert leer', async () => {
		// Sonst bestuende der Test oben auch eine Implementierung, die bei jeder
		// unbekannten Kennung einfach etwas erfindet.
		const fn = await loadAlertIdentitiesForMetricEntry();
		const stumm = {
			id: 'zenitstrahlung',
			label: 'Zenitstrahlung',
			unit: 'W/m²',
			category: 'atmosphere',
			default_enabled: false,
			has_friendly_format: false,
			change_alert_metric: null,
			aggregations: [{ id: 'max', label: 'Maximum', alert_metric: null }]
		} as unknown as MetricEntry;
		assert.deepEqual(
			fn(stumm),
			[],
			'Unbekannt heisst nicht automatisch alarmfaehig -- ohne hinterlegte ' +
				'Identitaet bleibt die Groesse ohne Zeile (Geisterzeile aus #1545).'
		);
	});
});
