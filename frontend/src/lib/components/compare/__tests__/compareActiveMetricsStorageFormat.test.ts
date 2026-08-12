// Issue #1373 (S2 Scheibe B) — Speicherformat der Metrik-Auswahl im Frontend.
// Spec: docs/specs/modules/feat_1373_s2b_metrik_speicherformat.md
//   AC-9  (beide Schreibstellen schreiben nur noch Groesse + Auswertung)
//   AC-12 (Bestandsrueckfall: Speichern eines ANDEREN Reiters beschaedigt die
//          Metrik-Auswahl nicht — echter Datenverlust-Pfad der Klasse #102)
//   AC-3/AC-4/AC-5 (Lesen: Altformat, Neuformat, Mischliste, [] vs. fehlend)
//
// Kein Mock: die Uebersetzungsquelle ist die ECHTE Endpoint-Antwortform von
// GET /api/compare/metrics, durch die ECHTE Naht `toCompareSelectionEntries()`
// gefuehrt (die den Umkehr-Index im Browser fuellt) — genau wie im Betrieb.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/compare/__tests__/compareActiveMetricsStorageFormat.test.ts

import { test, describe, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

import { buildComparePresetSavePayload, buildNewComparePresetPayload } from '../compareEditorSave.ts';
import {
	buildHubPutPayload,
	hydrateAlarmFieldsFromPreset,
	hydrateWizardStateFromPreset
} from '../compareHubWizardBridge.ts';
import { buildCompareCorridorSavePayload } from '../../shared/corridor-editor/corridorEditorState.ts';
import { rehydrateActiveMetrics } from '../compareEditorLoad.ts';
import {
	normalizeStoredActiveMetrics,
	registerCompareMetricCatalog,
	toCompareSelectionEntries,
	toStoredActiveMetrics,
	type CompareSelectionEntry
} from '../../shared/weather-metrics-tab/compareMetricSelection.ts';
import {
	hydrateWeatherMetricsFromPreset,
	flushPendingWeatherMetricsSave,
	type WeatherMetricsSnapshot
} from '../../shared/weather-metrics-tab/weatherMetricsCompareSave.ts';
import type { ComparePreset } from '../../../types.ts';

// Auszug der echten Antwort von GET /api/compare/metrics (Scheibe A ergaenzte
// metric_id/aggregation je Eintrag). Bewusst MIT beiden Zwillingspaaren, die
// dieselbe Groesse in zwei Auswertungen tragen — genau die Verschmelzungsfalle.
const CATALOG_RESPONSE = {
	metrics: [
		{ key: 'temp_max_c', label: 'Temperatur', aggregation_label: 'Maximum', metric_id: 'temperature', aggregation: 'max' },
		{ key: 'temp_min_c', label: 'Temperatur', aggregation_label: 'Minimum', metric_id: 'temperature', aggregation: 'min' },
		{ key: 'wind_chill_min_c', label: 'Gefühlte Temperatur', aggregation_label: 'Minimum', metric_id: 'wind_chill', aggregation: 'min' },
		{ key: 'wind_chill_max_c', label: 'Gefühlte Temperatur', aggregation_label: 'Maximum', metric_id: 'wind_chill', aggregation: 'max' },
		{ key: 'wind_max_kmh', label: 'Wind', aggregation_label: 'Maximum', metric_id: 'wind', aggregation: 'max' },
		{ key: 'snow_depth_cm', label: 'Schneehöhe', aggregation_label: 'Maximum', metric_id: 'snow_depth', aggregation: 'max' },
		{ key: 'precip_sum_mm', label: 'Niederschlag', aggregation_label: 'Summe', metric_id: 'precipitation', aggregation: 'sum' }
	]
};

/** Laedt die Katalogantwort so, wie es der Editor beim Oeffnen tut (und fuellt
 *  dabei den Umkehr-Index). Liefert die Eintraege auch direkt zurueck, damit
 *  Tests sie explizit weitergeben koennen. */
function loadCatalog(): CompareSelectionEntry[] {
	return toCompareSelectionEntries(
		CATALOG_RESPONSE as unknown as Parameters<typeof toCompareSelectionEntries>[0]
	);
}

// Adversary-Befund F002 (Fix-Runde 1): der Umkehr-Index ist Modulzustand. JEDER
// Test startet deshalb mit einem LEEREN Index und laedt den Katalog selbst,
// wenn er ihn braucht — kein Test ist von der Reihenfolge eines anderen
// abhaengig.
beforeEach(() => {
	registerCompareMetricCatalog([]);
});

const TEMP_MAX = { metric_id: 'temperature', aggregation: 'max' };
const TEMP_MIN = { metric_id: 'temperature', aggregation: 'min' };
const WIND_CHILL_MIN = { metric_id: 'wind_chill', aggregation: 'min' };
const WIND_MAX = { metric_id: 'wind', aggregation: 'max' };

function makePreset(displayConfig: Record<string, unknown>): ComparePreset {
	return {
		id: 'cp-1373',
		name: 'Vergleich 1373',
		location_ids: ['loc-a', 'loc-b', 'loc-c'],
		schedule: 'daily',
		weekday: 2,
		profil: 'wandern',
		empfaenger: ['urlauber@example.com'],
		created_at: '2026-07-01T00:00:00Z',
		display_config: displayConfig
	} as unknown as ComparePreset;
}

const baseEdits = {
	name: 'Vergleich 1373',
	activityProfile: null,
	pickedIds: ['loc-a', 'loc-b', 'loc-c'],
	region: 'Korsika',
	idealRanges: {}
};

function activeMetricsOf(body: ComparePreset): unknown {
	return (body.display_config as Record<string, unknown>).active_metrics;
}

// ===========================================================================
// AC-9 — beide Schreibstellen schreiben Groesse + Auswertung
// ===========================================================================

describe('AC-9: Bearbeiten schreibt die Metrik-Auswahl als Groesse + Auswertung', () => {
	test('drei Groessen, zwei davon dieselbe Groesse in zwei Auswertungen', () => {
		loadCatalog();
		const { body } = buildComparePresetSavePayload(makePreset({ region: 'Korsika' }), {
			...baseEdits,
			activeMetricKeys: ['temp_max_c', 'temp_min_c', 'wind_chill_min_c']
		});

		assert.deepEqual(activeMetricsOf(body), [TEMP_MAX, TEMP_MIN, WIND_CHILL_MIN],
			'AC-9: Hoechst- und Tiefsttemperatur muessen als ZWEI Eintraege mit gleicher ' +
			'Groesse und verschiedener Auswertung geschrieben werden — nichts darf verschmelzen'
		);
		assert.equal(
			(activeMetricsOf(body) as unknown[]).some((e) => typeof e === 'string'),
			false,
			'AC-9: keine Zeichenkette mehr im gespeicherten Format'
		);
	});

	test('Reihenfolge der Auswahl bleibt positionsgetreu (#1335/#1359)', () => {
		loadCatalog();
		const keys = ['wind_max_kmh', 'temp_min_c', 'snow_depth_cm', 'precip_sum_mm'];
		const { body } = buildComparePresetSavePayload(makePreset({}), {
			...baseEdits,
			activeMetricKeys: keys
		});

		assert.deepEqual(
			(activeMetricsOf(body) as { metric_id: string }[]).map((e) => e.metric_id),
			['wind', 'temperature', 'snow_depth', 'precipitation'],
			'AC-9/AC-2: die Reihenfolge der Nutzerauswahl darf sich nicht aendern'
		);
	});

	test('bewusst leere Auswahl wird EXPLIZIT als [] geschrieben (#1191)', () => {
		loadCatalog();
		const { body } = buildComparePresetSavePayload(makePreset({}), {
			...baseEdits,
			activeMetricKeys: []
		});

		assert.ok(
			'active_metrics' in (body.display_config as Record<string, unknown>),
			'#1191: "alles abgewaehlt" muss vom fehlenden Feld unterscheidbar bleiben'
		);
		assert.deepEqual(activeMetricsOf(body), []);
	});
});

describe('AC-9: Neuanlage schreibt dasselbe Format wie der Edit-Pfad', () => {
	const newFields = {
		name: 'Neu',
		pickedIds: ['loc-a', 'loc-b', 'loc-c'],
		activityProfile: null,
		schedule: 'daily_morning' as const,
		officialAlertsEnabled: false,
		radarAlertEnabled: false,
		hourlyEnabled: false,
		officialAlertTriggersEnabled: false,
		sendTelegram: false,
		sendSms: false,
		sendPremiumSms: false,
		officialWarningsEnabled: false,
		morningEnabled: true,
		morningTime: '07:00',
		eveningEnabled: false,
		eveningTime: '18:00',
		endDate: null,
		dayWindowStartHour: 4,
		dayWindowEndHour: 19,
		corridors: [],
		region: 'Korsika',
		idealRanges: {},
		activeMetricKeys: ['temp_max_c', 'temp_min_c'],
		hourlyMetricKeys: [],
		metricAlertLevels: {},
		telegramStyle: 'rich' as const
	};

	test('gewaehlte Groessen erscheinen als {metric_id, aggregation}', () => {
		loadCatalog();
		const payload = buildNewComparePresetPayload(newFields);

		assert.deepEqual(
			(payload.display_config as Record<string, unknown>).active_metrics,
			[TEMP_MAX, TEMP_MIN],
			'AC-9: die Neuanlage muss dasselbe Neuformat schreiben wie der Edit-Pfad'
		);
	});

	test('leere Auswahl schreibt den Schluessel explizit als [] (Issue #1366: Asymmetrie behoben)', () => {
		loadCatalog();
		const payload = buildNewComparePresetPayload({ ...newFields, activeMetricKeys: [] });

		assert.deepEqual(
			(payload.display_config as Record<string, unknown>).active_metrics,
			[],
			'#1366: die Neuanlage muss eine bewusste Leerauswahl wie der Edit-Pfad als [] ' +
				'persistieren, nicht den Schluessel weglassen (sonst kippt sie in "alle")'
		);
	});
});

// ===========================================================================
// Lesen — Altformat, Neuformat, Mischliste, [] vs. fehlend
// ===========================================================================

describe('AC-3/AC-4/AC-5: der Lade-Pfad liest beide Speicherformate', () => {
	test('Altformat (Zeichenketten) bleibt unveraendert lesbar', () => {
		loadCatalog();
		assert.deepEqual(rehydrateActiveMetrics(['temp_max_c', 'temp_min_c']), {
			activeMetricKeys: ['temp_max_c', 'temp_min_c'],
			metricsManuallyEdited: true
		});
	});

	test('Neuformat wird auf dieselbe Auswahl zurueckgefuehrt', () => {
		loadCatalog();
		assert.deepEqual(rehydrateActiveMetrics([TEMP_MAX, TEMP_MIN, WIND_CHILL_MIN]), {
			activeMetricKeys: ['temp_max_c', 'temp_min_c', 'wind_chill_min_c'],
			metricsManuallyEdited: true
		});
	});

	test('Mischliste (stehengebliebene Browser-Sitzung, R1) verliert keinen Eintrag', () => {
		loadCatalog();
		assert.deepEqual(rehydrateActiveMetrics(['temp_max_c', TEMP_MIN]), {
			activeMetricKeys: ['temp_max_c', 'temp_min_c'],
			metricsManuallyEdited: true
		});
	});

	test('leere Auswahl bleibt leer, fehlendes Feld bleibt "nie konfiguriert" (#1191)', () => {
		loadCatalog();
		assert.deepEqual(rehydrateActiveMetrics([]), {
			activeMetricKeys: [],
			metricsManuallyEdited: true
		});
		assert.equal(rehydrateActiveMetrics(undefined), null);
		assert.equal(rehydrateActiveMetrics(null), null);
	});
});

// ===========================================================================
// AC-12 — Speichern eines ANDEREN Reiters beschaedigt die Auswahl nicht
// ===========================================================================

describe('AC-12: Bestandsrueckfall beim Speichern eines anderen Reiters', () => {
	test('bereits umgestellte Auswahl bleibt beim Orte-Speichern unveraendert', () => {
		loadCatalog();
		const stored = [TEMP_MAX, TEMP_MIN, WIND_CHILL_MIN];
		const preset = makePreset({ region: 'Korsika', active_metrics: stored });

		const { body } = buildHubPutPayload(preset, { pickedIds: ['loc-a', 'loc-c'] });

		assert.deepEqual(activeMetricsOf(body), stored,
			'AC-12: die gespeicherte Metrik-Auswahl darf beim Speichern eines anderen ' +
			'Reiters weder beschaedigt noch geleert noch doppelt umgewandelt werden'
		);
		assert.deepEqual(body.location_ids, ['loc-a', 'loc-c'], 'der eigentliche Edit muss ankommen');
	});

	test('Altformat-Bestand verliert beim Speichern eines anderen Reiters keine Groesse', () => {
		loadCatalog();
		const preset = makePreset({
			region: 'Korsika',
			active_metrics: ['temp_max_c', 'temp_min_c', 'wind_chill_min_c']
		});

		const { body } = buildHubPutPayload(preset, { pickedIds: ['loc-a'] });

		assert.deepEqual(activeMetricsOf(body), [TEMP_MAX, TEMP_MIN, WIND_CHILL_MIN],
			'AC-12: dieselben drei Groessen, nur im neuen Format — keine verschwindet'
		);
	});

	test('fehlendes active_metrics wird nicht als leere Auswahl getarnt (#1191)', () => {
		loadCatalog();
		const { body } = buildHubPutPayload(makePreset({ region: 'Korsika' }), {
			pickedIds: ['loc-a']
		});

		assert.equal(
			'active_metrics' in (body.display_config as Record<string, unknown>),
			false,
			'#1191: aus einem fehlenden Feld darf kein [] werden'
		);
	});

	test('noch nicht geladener Katalog reicht die Auswahl unveraendert durch (verlustfrei)', () => {
		// Zustand vor dem Eintreffen von GET /api/compare/metrics (leerer Index
		// aus beforeEach, dieser Test laedt bewusst nicht). Selbst dann darf ein
		// Speichervorgang die gespeicherte Auswahl nicht verlieren — sie wird
		// unveraendert weitergereicht (der Backend-Aufloeser liest beide Formate).
		const stored = [TEMP_MAX, WIND_MAX];
		const { body } = buildHubPutPayload(
			makePreset({ region: 'Korsika', active_metrics: stored }),
			{ pickedIds: ['loc-b'] }
		);

		assert.deepEqual(activeMetricsOf(body), stored,
			'Ohne geladenen Katalog muss die gespeicherte Auswahl unveraendert ' +
			'durchlaufen — niemals verworfen oder geleert'
		);
	});

	test('nachtraeglich geladener Katalog loest eine kalt gelesene Auswahl auf', () => {
		// Ohne Katalog bleibt die gespeicherte Auswahl unveraendert in der Liste
		// stehen (verlustfrei); mit Katalog loest dieselbe Liste auf
		// Auswahl-Schluessel auf. Das ist die Eigenschaft, auf der die
		// katalog-gebundene Hydration aufsetzt.
		const kalt = rehydrateActiveMetrics([TEMP_MAX, TEMP_MIN]);
		assert.deepEqual(kalt?.activeMetricKeys, [TEMP_MAX, TEMP_MIN] as unknown as string[],
			'kalt: verlustfreier Durchlauf, nichts wird verworfen'
		);

		const catalog = loadCatalog();
		assert.deepEqual(
			normalizeStoredActiveMetrics(kalt!.activeMetricKeys, catalog),
			['temp_max_c', 'temp_min_c'],
			'nach dem Laden muss die Auswahl auf die angehakten Zeilen aufloesen'
		);
	});
});

// ===========================================================================
// Vertrag der Hydrations- und Speicher-Hilfsfunktionen
// ===========================================================================
//
// GELTUNGSBEREICH — bitte nicht mehr hineinlesen, als hier steht: geprueft
// werden AUSSCHLIESSLICH die reinen Funktionen
// `hydrateWeatherMetricsFromPreset`, `hydrateAlarmFieldsFromPreset`,
// `hydrateWizardStateFromPreset`, `flushPendingWeatherMetricsSave` und
// `buildCompareCorridorSavePayload`. Ihr Vertrag: mit geladener Katalogantwort
// liefert die Hydration Auswahl-Schluessel (nie die Rohform), und der
// Dirty-Guard erzeugt nur bei echter Aenderung einen PUT.
//
// AUSDRUECKLICH NICHT geprueft ist die Verdrahtung in `CompareTabs.svelte`
// (Reihenfolge "Katalog abwarten -> hydrieren -> Grundzustand aufnehmen" und
// das Ruecksetzen bei fehlgeschlagenem PUT). `.svelte`-Dateien sind unter
// `node --test` nicht importierbar (test-lib-loader.mjs hat keinen
// Svelte-Transform) — dieser Nachweis liegt in
// `frontend/e2e/compare-active-metrics-format.staging.spec.ts`: echter Klick,
// echter PUT-Zaehler, echtes Route-Abfangen gegen Staging.

describe('Vertrag: Hydration liefert Auswahl-Schluessel, Dirty-Guard schreibt nur bei echter Aenderung', () => {
	const STORED = [TEMP_MAX, TEMP_MIN, WIND_CHILL_MIN];
	const RESOLVED = ['temp_max_c', 'temp_min_c', 'wind_chill_min_c'];

	function makeMigratedPreset(): ComparePreset {
		return makePreset({ region: 'Korsika', active_metrics: STORED });
	}

	function snapshot(keys: string[]): WeatherMetricsSnapshot {
		return {
			activeMetricKeys: [...keys],
			officialAlertsEnabled: true,
			dayWindowStartHour: 4,
			dayWindowEndHour: 19
		};
	}

	test('mit geladenem Katalog hydriert: Auswahl-Schluessel, und ohne Aenderung kein PUT', () => {
		const preset = makeMigratedPreset();
		const catalog = loadCatalog();

		const keys = hydrateWeatherMetricsFromPreset(preset, catalog);
		// Grundzustand und laufender Zustand werden aus DEMSELBEN hydrierten
		// Ergebnis gebildet — so nimmt der Aufrufer sie auf
		// (CompareTabs.svelte::hydrateWetterMetrikenTab). Der Test sagt nichts
		// darueber, WANN der Aufrufer das tut (s. Geltungsbereich oben).
		const current = snapshot(keys);
		const baseline = snapshot(keys);

		assert.deepEqual(keys, RESOLVED,
			'die gespeicherte Auswahl muss als Auswahl-Schluessel hydriert werden, nicht als Rohform'
		);
		assert.equal(
			keys.every((k) => typeof k === 'string'),
			true,
			'kein rohes Objekt im hydrierten Zustand — sonst passt kein Haekchen'
		);
		assert.equal(
			flushPendingWeatherMetricsSave(preset, current, baseline),
			null,
			'ohne Nutzeraenderung darf der Dirty-Guard keinen PUT ergeben'
		);
	});

	test('eine Aenderung ergibt genau EINEN PUT — der Ruecksetzwert traegt Auswahl-Schluessel', () => {
		const preset = makeMigratedPreset();
		const catalog = loadCatalog();

		const hydrated = hydrateWeatherMetricsFromPreset(preset, catalog);
		const baseline = snapshot(hydrated);
		let puts = 0;

		// Eine Aenderung an der Auswahl (wie sie die Grundauswahl-Checkbox macht).
		const geaendert = snapshot([...hydrated, 'wind_max_kmh']);

		const payload = flushPendingWeatherMetricsSave(preset, geaendert, baseline);
		assert.ok(payload, 'eine echte Aenderung MUSS einen PUT ergeben');
		puts += 1;
		assert.deepEqual(
			(payload!.body.display_config as Record<string, unknown>).active_metrics,
			[TEMP_MAX, TEMP_MIN, WIND_CHILL_MIN, WIND_MAX],
			'der PUT schreibt die vollstaendige Auswahl im neuen Speicherformat'
		);

		// Bei einem fehlgeschlagenen PUT setzt der Aufrufer auf genau diesen
		// Grundzustand zurueck (CompareTabs.svelte, Zweig `catch` im
		// Wetter-Metriken-Commit). Geprueft wird hier NUR, dass dieser Wert
		// Auswahl-Schluessel traegt — dass der Aufrufer ihn wirklich verwendet,
		// deckt der Playwright-Nachweis ab.
		assert.deepEqual(baseline.activeMetricKeys, RESOLVED,
			'der Ruecksetzwert darf nicht die unaufgeloeste Rohform sein'
		);
		for (const key of RESOLVED) {
			assert.ok(
				baseline.activeMetricKeys.includes(key),
				`nach dem Ruecksetzen muss ${key} weiterhin als angehakt erkennbar sein`
			);
		}

		// Deckungsgleicher Zustand: kein weiterer PUT.
		if (flushPendingWeatherMetricsSave(preset, snapshot(baseline.activeMetricKeys), baseline)) {
			puts += 1;
		}
		assert.equal(puts, 1, 'genau EIN PUT fuer eine Aenderung — kein Nachschlag');
	});

	test('Alarme-Reiter als Deep-Link: Empfindlichkeits-Tabelle sieht dieselbe Auswahl', () => {
		// #1320: der Alarme-Reiter hydriert `activeMetricKeys` eigenstaendig
		// (CompareTabs.svelte::hydrateAlarmeTab -> hydrateAlarmFieldsFromPreset).
		// Auch dieser Weg braucht die Katalogantwort, sonst zeigte die
		// Empfindlichkeits-Tabelle bei einem umgestellten Vergleich "keine
		// Metriken".
		const catalog = loadCatalog();
		const state = {
			officialAlertsEnabled: false,
			officialWarningsEnabled: false,
			radarAlertEnabled: false,
			metricAlertLevels: {},
			activeMetricKeys: [] as string[],
			corridors: [],
			telegramStyle: 'rich' as const
		};

		hydrateAlarmFieldsFromPreset(
			state as unknown as Parameters<typeof hydrateAlarmFieldsFromPreset>[0],
			makeMigratedPreset(),
			catalog
		);

		assert.deepEqual(state.activeMetricKeys, RESOLVED,
			'der Alarme-Reiter muss dieselbe Auswahl sehen wie der Wetter-Metriken-Reiter'
		);
	});

	test('Idealwerte-Reiter: ✕-Entfernen trifft die aufgeloeste Auswahl', () => {
		// Dritte Hydrationsstelle (CompareTabs.svelte::hydrateIdealwerteTab ->
		// hydrateWizardStateFromPreset). Ohne aufgeloeste Auswahl wuerde
		// `activeSet.delete(key)` in buildCompareCorridorSavePayload eine
		// Rohform-Auswahl nicht treffen — die entfernte Zeile blieb in der Mail.
		const catalog = loadCatalog();
		const hydrated = hydrateWizardStateFromPreset(makeMigratedPreset(), catalog);

		assert.deepEqual(hydrated.activeMetricKeys, RESOLVED,
			'der Idealwerte-Reiter muss dieselbe aufgeloeste Auswahl sehen'
		);

		const payload = buildCompareCorridorSavePayload([], ['temp_min_c'], {
			idealRanges: {},
			activeMetricKeys: hydrated.activeMetricKeys!,
			metricAlertLevels: {}
		});
		assert.deepEqual(payload.activeMetricKeys, ['temp_max_c', 'wind_chill_min_c'],
			'die entfernte Groesse muss aus der Auswahl fallen, die anderen bleiben'
		);
	});

	test('ohne Katalog bleibt die Hydration verlustfrei und erzeugt ebenfalls keinen PUT', () => {
		// Fehlerfall (Katalog-Fetch gescheitert, hydrateWetterMetrikenTab faengt ab
		// und hydriert mit []): die Auswahl bleibt in der Rohform stehen — nicht
		// schoen, aber verlustfrei, und Grundzustand und laufender Zustand sind
		// deckungsgleich, es entsteht also weiterhin kein PUT ohne Aenderung.
		const preset = makeMigratedPreset();
		const keys = hydrateWeatherMetricsFromPreset(preset, []);
		const current = snapshot(keys);
		const baseline = snapshot(keys);

		assert.deepEqual(keys, STORED as unknown as string[], 'verlustfrei: nichts verworfen');
		assert.equal(
			flushPendingWeatherMetricsSave(preset, current, baseline),
			null,
			'kein PUT ohne Nutzergeste, auch im Katalog-Fehlerfall'
		);
	});
});

// ════════════════════════════════════════════════════════════════════════
// Issue #1401 Scheibe A1 (AC-5): die Umbenennung darf die gespeicherte
// Auswahl nicht anfassen. Der Katalog oben traegt bereits die NEUEN Namen
// ("Temperatur" statt "Temperatur max") — beide Speicherformate muessen
// trotzdem unveraendert geladen und zurueckgeschrieben werden, weil die
// Aufloesung ueber den Schluessel bzw. Groesse+Auswertung laeuft, nie ueber
// den Namen. Spec: docs/specs/modules/fix_1401_a1_namensregister.md § AC-5
// ════════════════════════════════════════════════════════════════════════
describe('#1401 AC-5: Umbenennung laesst beide Speicherformate unveraendert', () => {
	test('Altformat (Zeichenketten) laedt und schreibt sich unveraendert zurueck', () => {
		const catalog = loadCatalog();
		const gespeichert = ['temp_max_c', 'temp_min_c', 'wind_max_kmh'];
		const geladen = normalizeStoredActiveMetrics(gespeichert, catalog);
		assert.deepEqual(geladen, gespeichert, 'Laden hat die Auswahl veraendert');
		assert.deepEqual(
			toStoredActiveMetrics(geladen!, catalog),
			[
				{ metric_id: 'temperature', aggregation: 'max' },
				{ metric_id: 'temperature', aggregation: 'min' },
				{ metric_id: 'wind', aggregation: 'max' }
			],
			'Zurueckschreiben trifft nicht mehr dieselben Groessen/Auswertungen'
		);
	});

	test('Neuformat laedt und schreibt sich unveraendert zurueck', () => {
		const catalog = loadCatalog();
		const gespeichert = [
			{ metric_id: 'temperature', aggregation: 'max' },
			{ metric_id: 'temperature', aggregation: 'min' },
			{ metric_id: 'wind_chill', aggregation: 'min' }
		];
		const geladen = normalizeStoredActiveMetrics(gespeichert, catalog);
		assert.deepEqual(geladen, ['temp_max_c', 'temp_min_c', 'wind_chill_min_c']);
		assert.deepEqual(toStoredActiveMetrics(geladen!, catalog), gespeichert,
			'Laden+Speichern ohne Nutzergeste hat die gespeicherte Auswahl veraendert'
		);
	});

	test('kein Anzeigename ist ein gueltiger Auswahl-Schluessel (Namen sind entkoppelt)', () => {
		const catalog = loadCatalog();
		const namen = catalog.map((e) => e.label);
		// Zwei Eintraege tragen jetzt DENSELBEN Namen — waere der Name der
		// Schluessel, verschmoelzen sie beim Speichern.
		assert.ok(namen.filter((n) => n === 'Temperatur').length === 2);
		const alsAuswahl = normalizeStoredActiveMetrics(namen, catalog);
		assert.deepEqual(alsAuswahl, namen, 'Namen werden als Auswahl-Schluessel gedeutet');
		assert.deepEqual(
			toStoredActiveMetrics(namen, catalog),
			namen,
			'ein Anzeigename wurde in ein Groesse/Auswertung-Paar uebersetzt — die ' +
				'Auswahl haengt damit am Namen statt am Schluessel'
		);
	});
});
