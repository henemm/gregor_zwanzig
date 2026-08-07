// TDD RED — Fix #1544/#1545: trip-weite Ableitung der Alarme-Reiter-Zeilen
// aus Auswahl (`trip.display_config.metrics`) x Alarmfaehigkeit-aus-dem-
// Register (Katalog), statt aus `Object.keys(metric_alert_levels)`
// (AlarmeScheduleTab.svelte:36-42, "Der Fehler").
// Spec: docs/specs/modules/fix_1544_1545_trip_alarm_zeilen_ableitung.md
//   Implementation Details Punkt 2/3, Acceptance Criteria AC-3, AC-4, AC-5,
//   AC-8, AC-9, AC-10.
//
// RED heute: `deriveActiveAlertMetricsForTrip` ist in
// `shared/alarme-tab/tripAlertMetricsFromCatalog.ts` noch nicht exportiert
// (dieselbe Datei wie `alertIdentitiesForMetricEntry`, s.
// alert_identities_from_metric_entry.test.ts).
//
// Pfadregel #1409: alle Importe relativ zu DIESER Datei.
//
// Kein Mock-Theater: das `MetricCatalog`-Fixture (Record<category,
// MetricEntry[]>) hat exakt die Struktur der echten `GET /api/metrics`-
// Antwort (api/routers/config.py:58-107); die enthaltenen Register-Werte
// (Temperatur, Boeen, Luftfeuchtigkeit) sind dieselben wie in
// alert_identities_from_metric_entry.test.ts, aus src/app/metric_catalog.py
// abgelesen -- keine erfundenen Werte.
//
// AC-9-Describe-Block unten: liest `fixtures/ac9_trip_state.json`, DIESELBE
// Datei, die `tests/unit/services/
// test_deviation_alert_engine_matches_frontend_derivation.py` gegen den
// ECHTEN Backend-Regel-Erzeuger (`expand_per_metric_levels()`) verifiziert.
// Beide Seiten rechnen unabhaengig gegen ihre eigene Produktivrealitaet und
// treffen sich an `expected_alert_identities` -- kein Mock, keine RPC. Der
// Python-Test ist heute bereits gruen (Backend unveraendert); das
// RED-Signal fuer AC-9 liegt HIER, weil `deriveActiveAlertMetricsForTrip`
// fehlt.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/alarme-tab/__tests__/trip_active_alert_metrics_derivation.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import type { AlertMetric, MetricEntry, WeatherConfigMetric } from '../../../../types.ts';
import type { MetricCatalog } from '../../../trip-detail/metricsEditor.ts';

const here = dirname(fileURLToPath(import.meta.url));

type DeriveTripFn = (
	metrics: WeatherConfigMetric[] | undefined,
	catalog: MetricCatalog
) => AlertMetric[];

/** Laedt die neue trip-weite Ableitung. Fehlt sie noch, ist DAS der Befund. */
async function loadDeriveActiveAlertMetricsForTrip(): Promise<DeriveTripFn> {
	try {
		const mod = await import('../tripAlertMetricsFromCatalog.ts');
		const fn = (mod as Record<string, unknown>).deriveActiveAlertMetricsForTrip;
		if (typeof fn !== 'function') {
			assert.fail(
				'`deriveActiveAlertMetricsForTrip` ist in ' +
					'shared/alarme-tab/tripAlertMetricsFromCatalog.ts nicht exportiert ' +
					'(#1544/#1545, Spec Implementation Details Punkt 2).'
			);
		}
		return fn as DeriveTripFn;
	} catch (err) {
		assert.fail(
			'Die trip-weite Ableitung fehlt noch: erwartet wird ' +
				'`shared/alarme-tab/tripAlertMetricsFromCatalog.ts` mit ' +
				'`deriveActiveAlertMetricsForTrip(metrics, catalog)` (#1544/#1545). ' +
				`Ursache: ${String(err)}`
		);
	}
}

// ── Fixture: Register-Ausschnitt wie GET /api/metrics ──────────────────────
// Temperatur (3 Identitaeten), Boeen (1 Identitaet), Luftfeuchtigkeit (0 --
// ADR-0010). Werte wie in alert_identities_from_metric_entry.test.ts.
const CATALOG: MetricCatalog = {
	temperature: [
		{
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
		} as unknown as MetricEntry,
		{
			id: 'humidity',
			label: 'Luftfeuchtigkeit',
			unit: '%',
			category: 'temperature',
			default_enabled: false,
			has_friendly_format: false,
			change_alert_metric: null,
			aggregations: [{ id: 'avg', label: 'Mittel', alert_metric: null }]
		} as unknown as MetricEntry
	],
	wind: [
		{
			id: 'gust',
			label: 'Böen',
			unit: 'km/h',
			category: 'wind',
			default_enabled: true,
			has_friendly_format: false,
			change_alert_metric: null,
			aggregations: [{ id: 'max', label: 'Maximum', alert_metric: 'wind_gust' }]
		} as unknown as MetricEntry
	]
};

// Vollstaendige Menge alarmfaehiger Identitaeten in CATALOG, in
// ALERTABLE_METRICS-Reihenfolge (wind_gust steht dort vor den drei
// Temperatur-Identitaeten).
const ALL_ALARMABLE_IN_CATALOG: AlertMetric[] = [
	'wind_gust',
	'temperature_min',
	'temperature_max',
	'temperature_change'
];

describe('#1544/#1545 AC-3: gesetzte Stufe ohne aktive Wetter-Metrik zeigt keine Zeile', () => {
	test('Temperatur ist im Wetter-Reiter deaktiviert -> keine Temperatur-Zeilen, Böen bleibt', async () => {
		const derive = await loadDeriveActiveAlertMetricsForTrip();
		const metrics: WeatherConfigMetric[] = [
			{ metric_id: 'temperature', enabled: false },
			{ metric_id: 'gust', enabled: true }
		];
		const got = derive(metrics, CATALOG);
		assert.deepEqual(
			got,
			['wind_gust'],
			'Eine im Wetter-Reiter deaktivierte Groesse darf keine Alarm-Zeile mehr ' +
				`zeigen, selbst wenn sie frueher eine echte Stufe hatte (AC-3). Erhalten: ${JSON.stringify(got)}`
		);
	});
});

describe('#1544/#1545 AC-4 (Normalfall zu AC-3): Reaktivierung bringt die Zeile zurueck', () => {
	test('Dieselbe Groesse wird wieder aktiviert -> ihre Identitaeten erscheinen wieder', async () => {
		const derive = await loadDeriveActiveAlertMetricsForTrip();
		const vorher = derive(
			[
				{ metric_id: 'temperature', enabled: false },
				{ metric_id: 'gust', enabled: true }
			],
			CATALOG
		);
		assert.ok(
			!vorher.includes('temperature_max'),
			'Vorbedingung: vor der Reaktivierung ist keine Temperatur-Zeile da.'
		);

		const nachher = derive(
			[
				{ metric_id: 'temperature', enabled: true },
				{ metric_id: 'gust', enabled: true }
			],
			CATALOG
		);
		assert.deepEqual(
			nachher,
			ALL_ALARMABLE_IN_CATALOG,
			`Nach der Reaktivierung muessen alle drei Temperatur-Identitaeten UND ` +
				`Böen erscheinen (AC-4). Erhalten: ${JSON.stringify(nachher)}`
		);

		// AC-4 zweiter Teil: die vorher gespeicherte Stufe darf nicht auf
		// "standard" zurueckgesetzt worden sein. Diese Ableitung kennt gar kein
		// `metric_alert_levels` -- sie darf es folglich auch nicht anfassen. Der
		// gespeicherte Stand bleibt daher unveraendert, unabhaengig vom Aufruf
		// hier (separater, ungefilterter Wert, s. AC-6/Falle 4).
		const gespeicherteStufen = { temperature_max: 'sensibel' };
		const vorherJson = JSON.stringify(gespeicherteStufen);
		derive(
			[
				{ metric_id: 'temperature', enabled: true },
				{ metric_id: 'gust', enabled: true }
			],
			CATALOG
		);
		assert.equal(
			JSON.stringify(gespeicherteStufen),
			vorherJson,
			'Die Zeilen-Ableitung hat einen aussenstehenden Stufen-Stand veraendert -- ' +
				'sie darf `metric_alert_levels` nicht einmal kennen (AC-4/AC-6).'
		);
	});
});

describe('#1544/#1545 AC-5: Altbestands-Sonderfall (leere/fehlende Wetter-Metriken-Auswahl)', () => {
	test('metrics === [] liefert ALLE alarmfaehigen Register-Eintraege, nicht leer', async () => {
		const derive = await loadDeriveActiveAlertMetricsForTrip();
		const got = derive([], CATALOG);
		assert.deepEqual(
			got,
			ALL_ALARMABLE_IN_CATALOG,
			'Ein Trip, dessen Wetter-Reiter nie angefasst wurde (leeres metrics[]), ' +
				'muss ALLE alarmfaehigen Groessen als Zeile zeigen -- das Backend ' +
				'(is_alert_metric_active, weather_change_detection.py:213-216) haelt ' +
				`in diesem Zustand ebenfalls alles fuer aktiv. Erhalten: ${JSON.stringify(got)}`
		);
	});

	test('metrics === undefined liefert dasselbe wie []', async () => {
		const derive = await loadDeriveActiveAlertMetricsForTrip();
		const got = derive(undefined, CATALOG);
		assert.deepEqual(got, ALL_ALARMABLE_IN_CATALOG);
	});

	test('Gegenprobe: bei GESETZTER Auswahl greift der Sonderfall NICHT mehr', async () => {
		const derive = await loadDeriveActiveAlertMetricsForTrip();
		// Sobald mindestens ein Eintrag existiert, gilt die normale
		// Aktivierungslogik -- ein einzelnes deaktiviertes metrics[] darf NICHT
		// wie der leere Sonderfall behandelt werden (sonst waere AC-3 nie
		// pruefbar).
		const got = derive([{ metric_id: 'gust', enabled: false }], CATALOG);
		assert.deepEqual(
			got,
			[],
			'Ein bewusst leeres Auswahl-Ergebnis (Eintrag vorhanden, aber aus) ist ' +
				`NICHT der Altbestands-Sonderfall. Erhalten: ${JSON.stringify(got)}`
		);
	});
});

describe('#1544/#1545 AC-8: stabile Reihenfolge, nicht Einfuege-Reihenfolge', () => {
	// Eingabe bewusst mit Temperatur VOR Böen -- eine naive Implementierung,
	// die einfach `metrics` durchlaeuft, wuerde die Temperatur-Identitaeten
	// zuerst liefern. ALERTABLE_METRICS fuehrt aber `wind_gust` vor den
	// Temperatur-Identitaeten (alertMetricTable.ts:185-199) -- nur eine
	// Sortierung ueber diese Liste besteht den Test.
	const metrics: WeatherConfigMetric[] = [
		{ metric_id: 'temperature', enabled: true },
		{ metric_id: 'gust', enabled: true }
	];

	test('Reihenfolge folgt ALERTABLE_METRICS, nicht der Eingabe-Reihenfolge', async () => {
		const derive = await loadDeriveActiveAlertMetricsForTrip();
		const got = derive(metrics, CATALOG);
		assert.deepEqual(
			got,
			ALL_ALARMABLE_IN_CATALOG,
			`Erwartete ALERTABLE_METRICS-Reihenfolge (wind_gust zuerst). Erhalten: ${JSON.stringify(got)}`
		);
	});

	test('Zweiter Aufruf auf identischem Zustand liefert exakt dieselbe Reihenfolge', async () => {
		const derive = await loadDeriveActiveAlertMetricsForTrip();
		const erst = derive(metrics, CATALOG);
		const zweit = derive(metrics, CATALOG);
		assert.deepEqual(
			zweit,
			erst,
			'Zwei Aufrufe auf demselben Trip-Zustand (auch nach einem ' +
				'Speichervorgang, der die Auswahl nicht aendert) muessen identische ' +
				'Reihenfolge liefern -- sonst springen Zeilen bei jedem Oeffnen (AC-8).'
		);
	});
});

describe('#1544/#1545 AC-10: Bestandsschutz — nur Sichtbarkeit aendert sich, keine Stufe', () => {
	test('Ein eingefrorenes metric_alert_levels-Objekt bleibt unangetastet', async () => {
		const derive = await loadDeriveActiveAlertMetricsForTrip();
		// Ein Trip mit bereits sinnvoll gesetzten Stufen fuer AKTIVE UND eine
		// inaktive Groesse (Bestand vor der Umstellung). Object.freeze macht aus
		// jedem Schreibversuch der neuen Ableitung einen harten Fehlschlag (die
		// Frontend-Test-Module laufen strict, ESM ist immer strict) statt eines
		// stillen, unbemerkten Datenverlusts.
		const bestehendeStufen = Object.freeze({
			wind_gust: 'sensibel',
			temperature_max: 'entspannt',
			temperature_min: 'standard'
		});
		const vorherJson = JSON.stringify(bestehendeStufen);

		const metrics: WeatherConfigMetric[] = [
			{ metric_id: 'gust', enabled: true },
			{ metric_id: 'temperature', enabled: true }
		];
		const zeilen = derive(metrics, CATALOG);

		assert.deepEqual(
			zeilen,
			ALL_ALARMABLE_IN_CATALOG,
			'Vorbedingung: alle drei bereits konfigurierten Groessen sind weiterhin ' +
				'aktiv und muessen als Zeile erscheinen.'
		);
		assert.equal(
			JSON.stringify(bestehendeStufen),
			vorherJson,
			'Die neue Ableitung hat das eingefrorene Stufen-Objekt veraendert oder ' +
				'einen Schreibzugriff darauf versucht -- AC-10 verlangt, dass NUR die ' +
				'Zeilen-Sichtbarkeit sich aendert, niemals eine gespeicherte Stufe.'
		);
	});
});

// ── Adversary Fix-Loop, F002: auch trip-weit wird das Register GELESEN ──────
// Trip-weites Gegenstueck zum F002-Block in
// alert_identities_from_metric_entry.test.ts. Erfundene Katalog-Kennung
// (`boeen_pilot_2027`), aber ECHTE Alarm-Identitaet (`wind_gust`) -- nur so
// ueberlebt sie den ALERTABLE_METRICS-Filter aus AC-8. Eine Handliste ueber
// Katalog-Kennungen findet den Eintrag nicht und liefert leer.
describe('#1544/#1545 F002: unbekannte Katalog-Kennung wird strukturell aufgeloest', () => {
	const PILOT_CATALOG: MetricCatalog = {
		wind: [
			{
				id: 'boeen_pilot_2027',
				label: 'Böen (Pilotquelle)',
				unit: 'km/h',
				category: 'wind',
				default_enabled: false,
				has_friendly_format: false,
				change_alert_metric: null,
				aggregations: [{ id: 'max', label: 'Maximum', alert_metric: 'wind_gust' }]
			} as unknown as MetricEntry
		]
	};

	test('Aktivierte Groesse mit unbekannter Kennung liefert ihre Identitaet', async () => {
		const derive = await loadDeriveActiveAlertMetricsForTrip();
		const got = derive([{ metric_id: 'boeen_pilot_2027', enabled: true }], PILOT_CATALOG);
		assert.deepEqual(
			got,
			['wind_gust'],
			'Die trip-weite Ableitung muss die Alarm-Identitaet aus dem Katalog-' +
				'Eintrag lesen, egal wie die Groesse heisst. Leeres Ergebnis heisst: ' +
				`irgendwo wird eine Namensliste gefuehrt (F002). Erhalten: ${JSON.stringify(got)}`
		);
	});

	test('Gegenprobe: dieselbe unbekannte Kennung deaktiviert liefert leer', async () => {
		const derive = await loadDeriveActiveAlertMetricsForTrip();
		assert.deepEqual(derive([{ metric_id: 'boeen_pilot_2027', enabled: false }], PILOT_CATALOG), []);
	});
});

// ── Adversary Runde 2, F-ADV1: die Absicherung muss am AUFRUFER greifen ─────
// Der F002-Block oben faellt NICHT, wenn `deriveActiveAlertMetricsForTrip`
// `alertIdentitiesForMetricEntry` gar nicht mehr aufruft, sondern eine eigene
// Handtabelle fuehrt, die `boeen_pilot_2027` einfach mit aufnimmt (Mutation
// M8b: 23 von 23 gruen). Eine laengere Kennungsliste schliesst diese Luecke
// nicht -- nur die Konstruktion, die den Kern-Test robust macht: DIESELBE
// Katalog-Kennung in mehreren Varianten, die sich ausschliesslich in der
// hinterlegten Struktur unterscheiden, mit GEGENSAETZLICHEN erwarteten
// Ergebnissen. Eine Tabelle ueber Kennungen kann das nicht aufloesen: sie
// liefert je Kennung immer dasselbe, egal wie lang sie ist.
describe('#1544/#1545 F-ADV1: auch der trip-weite Aufrufer liest Struktur, nicht Namen', () => {
	const KENNUNG = 'strahlungsbilanz_2031';
	const AKTIV: WeatherConfigMetric[] = [{ metric_id: KENNUNG, enabled: true }];

	/** Register mit genau EINEM Eintrag unter immer derselben Kennung. */
	function registerMit(agg: string | null, change: string | null): MetricCatalog {
		return {
			atmosphere: [
				{
					id: KENNUNG,
					label: 'Strahlungsbilanz',
					unit: 'W/m²',
					category: 'atmosphere',
					default_enabled: false,
					has_friendly_format: false,
					change_alert_metric: change,
					aggregations: [
						{ id: 'max', label: 'Maximum', alert_metric: agg },
						{ id: 'avg', label: 'Mittel', alert_metric: null }
					]
				} as unknown as MetricEntry
			]
		};
	}

	test('Gleiche Kennung, einmal mit und einmal ohne Identitaet -> gegensaetzliches Ergebnis', async () => {
		const derive = await loadDeriveActiveAlertMetricsForTrip();
		const mit = derive(AKTIV, registerMit('wind_gust', null));
		const ohne = derive(AKTIV, registerMit(null, null));
		assert.deepEqual(mit, ['wind_gust'], `Erhalten: ${JSON.stringify(mit)}`);
		assert.deepEqual(
			ohne,
			[],
			`Dieselbe Kennung OHNE hinterlegte Identitaet muss zeilenlos bleiben. Erhalten: ${JSON.stringify(ohne)}`
		);
		assert.notDeepEqual(
			mit,
			ohne,
			`Zwei Register-Eintraege mit IDENTISCHER Kennung (${KENNUNG}) und ` +
				'unterschiedlicher Struktur liefern dasselbe Ergebnis -- dann liest die ' +
				'trip-weite Ableitung Namen statt Struktur (F-ADV1, Mutation M8b).'
		);
	});

	test('Gleiche Kennung, ANDERE hinterlegte Identitaet -> anderes Ergebnis', async () => {
		const derive = await loadDeriveActiveAlertMetricsForTrip();
		// Schlaegt jede Tabelle, die je Kennung einen festen Wert liefert und
		// hoechstens noch prueft, OB ueberhaupt eine Identitaet hinterlegt ist.
		const ausAggregation = derive(AKTIV, registerMit('temperature_max', null));
		assert.deepEqual(
			ausAggregation,
			['temperature_max'],
			`Die Ableitung muss den hinterlegten WERT lesen. Erhalten: ${JSON.stringify(ausAggregation)}`
		);
		// Zweite Quelle am selben Eintrag (`change_alert_metric`), Aggregationen
		// stumm -- faengt zusaetzlich einen Fork, der nur eine der beiden Quellen
		// liest (die verschluckte Zeile aus AC-7).
		const ausAenderungsrate = derive(AKTIV, registerMit(null, 'temperature_change'));
		assert.deepEqual(
			ausAenderungsrate,
			['temperature_change'],
			`Erhalten: ${JSON.stringify(ausAenderungsrate)}`
		);
	});
});

describe('#1544/#1545 AC-9: Deckungsgleichheit mit dem echten Backend-Regel-Erzeuger', () => {
	// Register-Ausschnitt inkl. CAPE (im Fixture-Zustand deaktiviert) --
	// bewusst eine EIGENE Katalog-Konstante, damit die "alle alarmfaehigen
	// Eintraege"-Erwartung von AC-5 oben (ALL_ALARMABLE_IN_CATALOG) nicht
	// durch das zusaetzliche CAPE verfaelscht wird. Register-Werte wie in
	// alert_identities_from_metric_entry.test.ts (cape: metric_catalog.py
	// :328-338, summary_fields={"max":"cape_max_jkg"}, alert_metrics=
	// {"max":"cape"}, kein change_alert_metric).
	const AC9_CATALOG: MetricCatalog = {
		...CATALOG,
		precipitation: [
			{
				id: 'cape',
				label: 'Gewitterenergie (CAPE)',
				unit: 'J/kg',
				category: 'precipitation',
				default_enabled: false,
				has_friendly_format: false,
				change_alert_metric: null,
				aggregations: [{ id: 'max', label: 'Maximum', alert_metric: 'cape' }]
			} as unknown as MetricEntry
		]
	};

	function loadFixture(): {
		metrics: WeatherConfigMetric[];
		metric_alert_levels: Record<string, string>;
		expected_alert_identities: AlertMetric[];
	} {
		const path = join(here, 'fixtures', 'ac9_trip_state.json');
		return JSON.parse(readFileSync(path, 'utf-8'));
	}

	test('Frontend-Ableitung liefert exakt die vom echten Backend erzeugte Identitaeten-Menge', async () => {
		const derive = await loadDeriveActiveAlertMetricsForTrip();
		const fixture = loadFixture();

		const got = derive(fixture.metrics, AC9_CATALOG);

		assert.deepEqual(
			[...got].sort(),
			[...fixture.expected_alert_identities].sort(),
			'Die Frontend-Ableitung weicht von der Menge ab, die ' +
				'`expand_per_metric_levels()` fuer denselben Trip-Zustand ' +
				'tatsaechlich auswertet (belegt in tests/unit/services/' +
				'test_deviation_alert_engine_matches_frontend_derivation.py). ' +
				`Erhalten: ${JSON.stringify(got)}, erwartet: ${JSON.stringify(fixture.expected_alert_identities)} (AC-9).`
		);
	});

	test('Gegenprobe: die deaktivierte Groesse (CAPE) UND die nicht-alarmfaehige (Luftfeuchtigkeit) fehlen', async () => {
		const derive = await loadDeriveActiveAlertMetricsForTrip();
		const fixture = loadFixture();
		const got = derive(fixture.metrics, AC9_CATALOG);

		assert.ok(!got.includes('cape' as AlertMetric), 'CAPE ist im Fixture-Zustand deaktiviert.');
		assert.ok(
			!got.includes('humidity' as AlertMetric),
			'Luftfeuchtigkeit ist strukturell nicht alarmfaehig (ADR-0010).'
		);
	});
});
