// TDD RED — Issue #1425 Schritt 2, Teil 1 (Spec:
// docs/specs/modules/fix_1425_s2_corridor_pool.md): der Trip-Korridor-Editor
// (Reiter "Wertebereiche", context="route") bietet heute nur die 6 fest
// verdrahteten ROUTE_METRIC_DEFS an. Diese Suite verankert die Erweiterung um
// die uebrigen Katalog-Groessen aus GET /api/compare/metrics, OHNE die
// Gewitter-Skalen-Vereinheitlichung anzufassen (separater Folge-Workflow).
//
// buildRouteMetricDefsFromCatalog() existiert in RED noch nicht (Naht analog
// __tests__/compareMetricCatalogParity.test.ts) -- Modul-Existenz-Tests machen
// das bewusst sprechend rot statt den Runner mit rohem ENOENT/undefined
// abzubrechen. buildRoutePool() bekommt einen dritten, optionalen Parameter
// `extraDefs` -- ohne ihn bleibt das bisherige 6er-Verhalten unveraendert
// (Testschutz fuer corridorEditorState.test.ts + test_alert_metric_mapping_parity.py).
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/corridor-editor/__tests__/routeCorridorPoolCatalogExpansion.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

import {
	buildRoutePool,
	buildCorridorSavePayload,
	patchRow,
	ROUTE_METRIC_DEFS,
	type RouteMetricDef,
} from '../corridorEditorState.ts';

const MODULE_SPECIFIER = '../compareMetricCatalogLoader.ts';

// Issue #1425 F002 (Adversary, MEDIUM): eine handgetippte Fixture ist kein
// echter Drift-Waechter — waechst der Backend-Katalog um eine Groesse ohne
// _COMPARE_DEFAULTS-Eintrag, reproduziert der route-Pfad den #1424-Fehler
// unbemerkt. Analog compareMetricCatalogParity.test.ts:283-297 liest dieser
// Test daher den LIVE-Katalog per `uv run python3`.
// Pfadregel #1409: Prueflings-Wurzel relativ zur EIGENEN Testdatei (Worktree),
// nicht ueber einen festen Hauptrepo-Pfad.
const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), ...Array(7).fill('..'));
const PY_SCRIPT =
	'import sys, json\n' +
	"sys.path.insert(0, 'src')\n" +
	'from output.renderers.compare_metric_catalog import get_compare_metric_catalog\n' +
	"print(json.dumps({'metrics': get_compare_metric_catalog()}))\n";

/** Liest die LIVE-Katalog-Antwort via `uv run python3` (echte Quelle, kein Fixture). */
function fetchLiveCatalogResponse(): { metrics: Array<Record<string, unknown>> } {
	const stdout = execFileSync('uv', ['run', 'python3', '-c', PY_SCRIPT], {
		cwd: REPO_ROOT,
		encoding: 'utf-8'
	});
	return JSON.parse(stdout.trim());
}

// 26 Roh-Eintraege 1:1 aus src/output/renderers/compare_metric_catalog.py::
// COMPARE_METRIC_CATALOG, inkl. `metric_id` (#1373 S2 Scheibe A) -- das Feld,
// gegen das der Duplikat-Filter laeuft. Reihenfolge = Katalog-Reihenfolge.
const CATALOG_ENTRIES_FIXTURE: Array<Record<string, unknown>> = [
	{ key: 'snow_depth_cm', label: 'Schneehöhe', unit: 'cm', kind: 'range', rangeMin: 0, rangeMax: 200, step: 5, metric_id: 'snow_depth' },
	{ key: 'snow_new_sum_cm', label: 'Neuschnee', unit: 'cm', kind: 'range', rangeMin: 0, rangeMax: 50, step: 1, metric_id: 'fresh_snow' },
	{ key: 'sunny_hours_h', label: 'Sonnenstunden', unit: 'h', kind: 'range', rangeMin: 0, rangeMax: 12, step: 0.5, metric_id: 'sunshine' },
	{ key: 'wind_max_kmh', label: 'Wind', unit: 'km/h', kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, metric_id: 'wind' },
	{ key: 'cloud_avg_pct', label: 'Bewölkung', unit: '%', kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, metric_id: 'cloud_total' },
	{ key: 'visibility_min_m', label: 'Sichtweite', unit: 'm', kind: 'range', rangeMin: 0, rangeMax: 10000, step: 500, metric_id: 'visibility' },
	// Duplikat: metric_id "precipitation" deckt sich mit ROUTE_CORRIDOR_CATALOG_IDS -> ausschliessen.
	{ key: 'precip_sum_mm', label: 'Niederschlag', unit: 'mm', kind: 'range', rangeMin: 0, rangeMax: 30, step: 0.5, metric_id: 'precipitation' },
	{ key: 'uv_index_max', label: 'UV-Index', unit: '', kind: 'range', rangeMin: 0, rangeMax: 12, step: 1, metric_id: 'uv_index' },
	// Duplikat: "temperature" (temperature_max/_min existieren schon in ROUTE_METRIC_DEFS).
	{ key: 'temp_max_c', label: 'Temperatur', unit: '°C', kind: 'range', rangeMin: -20, rangeMax: 45, step: 1, metric_id: 'temperature' },
	// Duplikat + AUSGEKLAMMERT (Gewitter-Skalen-Migration ist Folge-Workflow): metric_id "thunder".
	{ key: 'thunder_level_max', label: 'Gewitter', unit: '', kind: 'ordinal', ordinalLabels: ['kein', 'mittel', 'hoch'], metric_id: 'thunder' },
	{ key: 'temp_min_c', label: 'Temperatur', unit: '°C', kind: 'range', rangeMin: -30, rangeMax: 30, step: 1, metric_id: 'temperature' },
	// Duplikat: "gust".
	{ key: 'gust_max_kmh', label: 'Böen', unit: 'km/h', kind: 'range', rangeMin: 0, rangeMax: 150, step: 5, metric_id: 'gust' },
	{ key: 'cape_max_jkg', label: 'Gewitterenergie (CAPE)', unit: 'J/kg', kind: 'range', rangeMin: 0, rangeMax: 3000, step: 100, metric_id: 'cape' },
	// Duplikat: "freezing_level".
	{ key: 'freezing_level_m', label: 'Nullgradgrenze', unit: 'm', kind: 'range', rangeMin: 0, rangeMax: 5000, step: 100, metric_id: 'freezing_level' },
	{ key: 'pop_max_pct', label: 'Regenwahrscheinlichkeit', unit: '%', kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, metric_id: 'rain_probability' },
	// _COMPARE_RANGE_UNSUPPORTED (zyklisch, kein Von/Bis-Bereich) -> ausschliessen.
	{ key: 'wind_direction_deg', label: 'Windrichtung', unit: '°', kind: 'range', rangeMin: 0, rangeMax: 360, step: 10, metric_id: 'wind_direction' },
	{ key: 'wind_chill_min_c', label: 'Gefühlte Temperatur', unit: '°C', kind: 'range', rangeMin: -30, rangeMax: 30, step: 1, metric_id: 'wind_chill' },
	{ key: 'wind_chill_max_c', label: 'Gefühlte Temperatur', unit: '°C', kind: 'range', rangeMin: -20, rangeMax: 45, step: 1, metric_id: 'wind_chill' },
	{ key: 'humidity_avg_pct', label: 'Luftfeuchtigkeit', unit: '%', kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, metric_id: 'humidity' },
	{ key: 'dewpoint_avg_c', label: 'Taupunkt', unit: '°C', kind: 'range', rangeMin: -20, rangeMax: 30, step: 1, metric_id: 'dewpoint' },
	// Duplikat: "snowfall_limit" (deckt sich mit snow_line, ROUTE_CORRIDOR_CATALOG_IDS).
	{ key: 'snowfall_limit_m', label: 'Schneefallgrenze', unit: 'm', kind: 'range', rangeMin: 0, rangeMax: 5000, step: 100, metric_id: 'snowfall_limit' },
	// _COMPARE_RANGE_UNSUPPORTED (Enum ohne Zahlenskala) -> ausschliessen.
	{ key: 'precip_type_dominant', label: 'Niederschlagsart', unit: '', kind: 'enum', enumValues: ['RAIN', 'SNOW', 'MIXED', 'FREEZING_RAIN'], metric_id: 'precip_type' },
	{ key: 'cloud_low_avg_pct', label: 'Tiefe Wolken', unit: '%', kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, metric_id: 'cloud_low' },
	{ key: 'cloud_mid_avg_pct', label: 'Mittelhohe Wolken', unit: '%', kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, metric_id: 'cloud_mid' },
	{ key: 'cloud_high_avg_pct', label: 'Hohe Wolken', unit: '%', kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, metric_id: 'cloud_high' },
	{ key: 'pressure_avg_hpa', label: 'Luftdruck', unit: 'hPa', kind: 'range', rangeMin: 950, rangeMax: 1050, step: 5, metric_id: 'pressure' },
];

// Erwartete 17 neuen Metriken, Katalog-Reihenfolge (PO-Entscheidung).
const EXPECTED_NEW_KEYS = [
	'snow_depth_cm', 'snow_new_sum_cm', 'sunny_hours_h', 'wind_max_kmh', 'cloud_avg_pct',
	'visibility_min_m', 'uv_index_max', 'cape_max_jkg', 'pop_max_pct', 'wind_chill_min_c',
	'wind_chill_max_c', 'humidity_avg_pct', 'dewpoint_avg_c', 'cloud_low_avg_pct',
	'cloud_mid_avg_pct', 'cloud_high_avg_pct', 'pressure_avg_hpa',
];

// Ausgeschlossen: 7 Duplikate (metric_id deckt sich mit ROUTE_CORRIDOR_CATALOG_IDS)
// + 2 _COMPARE_RANGE_UNSUPPORTED (kein Von/Bis-Bereich darstellbar).
const EXPECTED_EXCLUDED_KEYS = [
	'precip_sum_mm', 'temp_max_c', 'thunder_level_max', 'temp_min_c', 'gust_max_kmh',
	'freezing_level_m', 'snowfall_limit_m', 'wind_direction_deg', 'precip_type_dominant',
];

async function loadCatalogLoaderModule(): Promise<typeof import('../compareMetricCatalogLoader.ts')> {
	try {
		return await import(MODULE_SPECIFIER);
	} catch (e) {
		assert.fail(
			`compareMetricCatalogLoader.ts kann nicht importiert werden: ${(e as Error).message}`
		);
		throw e;
	}
}

describe('AC-1/AC-2/AC-3: buildRouteMetricDefsFromCatalog() existiert und filtert korrekt', () => {
	test('exportiert buildRouteMetricDefsFromCatalog als Funktion', async () => {
		const mod = await loadCatalogLoaderModule();
		assert.equal(
			typeof (mod as Record<string, unknown>).buildRouteMetricDefsFromCatalog,
			'function',
			'AC-1 FAIL: kein Export buildRouteMetricDefsFromCatalog gefunden — der Trip-Pool kann noch keine ' +
				'Zusatz-Metriken aus dem zentralen Katalog beziehen (Issue #1425 Schritt 2 noch nicht implementiert).'
		);
	});

	test('liefert genau 17 RouteMetricDef-Objekte in Katalog-Reihenfolge (AC-1)', async () => {
		const mod = await loadCatalogLoaderModule();
		const buildRouteMetricDefsFromCatalog = (mod as Record<string, unknown>)
			.buildRouteMetricDefsFromCatalog as ((entries: unknown[]) => RouteMetricDef[]) | undefined;
		assert.ok(buildRouteMetricDefsFromCatalog, 'buildRouteMetricDefsFromCatalog fehlt noch');

		const result = buildRouteMetricDefsFromCatalog!(CATALOG_ENTRIES_FIXTURE);

		assert.deepEqual(
			result.map((d) => d.metric),
			EXPECTED_NEW_KEYS,
			'AC-1 FAIL: erwartet exakt die 17 neuen Metriken in Katalog-Reihenfolge'
		);
	});

	test('schliesst alle 7 Duplikate + 2 unterstuetzungslose Groessen aus (AC-2 + AC-3)', async () => {
		const mod = await loadCatalogLoaderModule();
		const buildRouteMetricDefsFromCatalog = (mod as Record<string, unknown>)
			.buildRouteMetricDefsFromCatalog as ((entries: unknown[]) => RouteMetricDef[]) | undefined;
		assert.ok(buildRouteMetricDefsFromCatalog, 'buildRouteMetricDefsFromCatalog fehlt noch');

		const result = buildRouteMetricDefsFromCatalog!(CATALOG_ENTRIES_FIXTURE);
		const resultKeys = result.map((d) => d.metric);

		for (const excluded of EXPECTED_EXCLUDED_KEYS) {
			assert.equal(
				resultKeys.includes(excluded),
				false,
				`AC-2/AC-3 FAIL: "${excluded}" haette ausgeschlossen werden muessen (Duplikat oder kein Von/Bis-Bereich)`
			);
		}
	});

	test('thunder_level_max erscheint NICHT in den Zusatz-Defs — Gewitter bleibt exklusiv die alte Prozent-Definition (AC-3)', async () => {
		const mod = await loadCatalogLoaderModule();
		const buildRouteMetricDefsFromCatalog = (mod as Record<string, unknown>)
			.buildRouteMetricDefsFromCatalog as ((entries: unknown[]) => RouteMetricDef[]) | undefined;
		assert.ok(buildRouteMetricDefsFromCatalog, 'buildRouteMetricDefsFromCatalog fehlt noch');

		const result = buildRouteMetricDefsFromCatalog!(CATALOG_ENTRIES_FIXTURE);
		assert.equal(
			result.some((d) => d.metric === 'thunder_level_max' || d.metric === 'thunder_level'),
			false,
			'AC-3 FAIL: eine Gewitter-Variante ist in den Zusatz-Defs aufgetaucht — sie muss ' +
				'ausschliesslich ueber ROUTE_METRIC_DEFS (Prozent-Skala) kommen, nicht dupliziert werden'
		);
	});

	test('jede Zusatz-Def traegt eine sinnvolle Von/Bis-Vorgabe (mind. eine Grenze gesetzt, analog #1424)', async () => {
		const mod = await loadCatalogLoaderModule();
		const buildRouteMetricDefsFromCatalog = (mod as Record<string, unknown>)
			.buildRouteMetricDefsFromCatalog as ((entries: unknown[]) => RouteMetricDef[]) | undefined;
		assert.ok(buildRouteMetricDefsFromCatalog, 'buildRouteMetricDefsFromCatalog fehlt noch');

		const result = buildRouteMetricDefsFromCatalog!(CATALOG_ENTRIES_FIXTURE);
		const beidseitigOffen = result.filter((d) => d.defaultMin == null && d.defaultMax == null);
		assert.deepEqual(
			beidseitigOffen.map((d) => d.metric),
			[],
			'AC-6-Analogie FAIL: diese neuen Metriken haben keine Von/Bis-Vorgabe (beidseitig offen -> ' +
				'validateCorridorRows blockt direkt nach dem Hinzufuegen): ' +
				beidseitigOffen.map((d) => d.metric).join(', ')
		);
	});
});

describe('buildRoutePool — extraDefs-Parameter (AC-1, AC-4 Datenerhalt)', () => {
	test('ohne extraDefs bleibt das Verhalten byte-identisch zu heute (Testschutz test_alert_metric_mapping_parity.py)', () => {
		const { poolLeft } = buildRoutePool([]);
		assert.equal(poolLeft.length, 6, 'Regressions-FAIL: ohne extraDefs muessen weiterhin genau 6 Metriken im Pool stehen');
	});

	test('mit extraDefs erscheinen die neuen Metriken zusaetzlich zu den 6 alten (23 insgesamt, AC-1)', () => {
		const extraDefs: RouteMetricDef[] = [
			{ metric: 'cape_max_jkg', label: 'Gewitterenergie (CAPE)', unit: 'J/kg', scale: [0, 3000], step: 100, defaultMin: null, defaultMax: 500 },
			{ metric: 'pressure_avg_hpa', label: 'Luftdruck', unit: 'hPa', scale: [950, 1050], step: 5, defaultMin: 1010, defaultMax: null },
		];
		const { poolLeft } = buildRoutePool([], undefined, extraDefs);
		assert.equal(
			poolLeft.length,
			8,
			'AC-1 FAIL: buildRoutePool nimmt den dritten Parameter extraDefs noch nicht entgegen'
		);
		assert.ok(poolLeft.some((m) => m.metric === 'cape_max_jkg'));
		assert.ok(poolLeft.some((m) => m.metric === 'pressure_avg_hpa'));
	});

	test('gespeicherter Korridor einer der alten 6 Metriken bleibt unveraendert sichtbar, wenn extraDefs gesetzt ist (AC-4 Datenerhalt)', () => {
		const extraDefs: RouteMetricDef[] = [
			{ metric: 'cape_max_jkg', label: 'Gewitterenergie (CAPE)', unit: 'J/kg', scale: [0, 3000], step: 100, defaultMin: null, defaultMax: 500 },
		];
		const { rows, poolLeft } = buildRoutePool(
			[{ metric: 'precipitation_sum', range: [null, 5], notify: true, mark: false }],
			undefined,
			extraDefs
		);
		assert.equal(rows.length, 1, 'AC-4 FAIL: gespeicherter Korridor fehlt, sobald extraDefs gesetzt ist');
		assert.equal(rows[0].min, null);
		assert.equal(rows[0].max, 5);
		assert.equal(poolLeft.length, 6, 'AC-4 FAIL: die uebrigen 5 alten + 1 neue Metrik muessen im Pool stehen');
	});

	test('ROUTE_METRIC_DEFS bleibt byte-identisch (6 Eintraege, Testschutz)', () => {
		assert.equal(ROUTE_METRIC_DEFS.length, 6, 'Testschutz-FAIL: ROUTE_METRIC_DEFS darf nicht wachsen/schrumpfen');
	});
});

// ════════════════════════════════════════════════════════════════════════
// F001 (Adversary, HIGH) — Datenerhalt im route-Pfad. Spec § Implementation
// Details Punkt 4: "unbekannte Metrik-IDs in gespeicherten Korridoren nicht
// still verwerfen, sondern über das bestehende unknownCorridors-Pattern
// durchreichen". buildComparePool/buildCompareCorridorSavePayload koennen das
// seit Slice 4 (#1231 F003) — der route-Zweig noch nicht: ein gespeicherter
// Trip-Korridor mit einer Metrik-ID ausserhalb von
// ROUTE_METRIC_DEFS ∪ extraDefs fiel aus rows heraus und war beim naechsten
// Speichern dauerhaft geloescht (BUG-DATALOSS-Klasse, CLAUDE.md).
// ════════════════════════════════════════════════════════════════════════

const CAPE_EXTRA_DEF: RouteMetricDef = {
	metric: 'cape_max_jkg', label: 'Gewitterenergie (CAPE)', unit: 'J/kg',
	scale: [0, 3000], step: 100, defaultMin: null, defaultMax: 500,
};

describe('F001: buildRoutePool — unknownCorridors (Pass-Through, Datenerhalt)', () => {
	test('Corridor mit unbekannter Metrik-ID landet in unknownCorridors, nicht in rows/poolLeft', () => {
		const result = buildRoutePool(
			[
				{ metric: 'wind_gust', range: [null, 70], notify: true, mark: false },
				{ metric: 'foo_future_metric', range: [null, 42], notify: false, mark: true },
			],
			undefined,
			[CAPE_EXTRA_DEF]
		);
		assert.equal(
			result.rows.some((r) => r.metric === 'foo_future_metric'),
			false,
			'F001: eine unbekannte Metrik darf keine UI-Zeile erzeugen'
		);
		assert.equal(
			result.poolLeft.some((m) => m.metric === 'foo_future_metric'),
			false,
			'F001: eine unbekannte Metrik darf nicht im "+ Metrik"-Pool auftauchen'
		);
		assert.deepEqual(
			(result as { unknownCorridors?: unknown[] }).unknownCorridors,
			[{ metric: 'foo_future_metric', range: [null, 42], notify: false, mark: true }],
			'F001 FAIL: buildRoutePool liefert kein unknownCorridors-Pass-Through — der ' +
				'gespeicherte Korridor waere beim naechsten Speichern dauerhaft verloren'
		);
		// Die bekannte Zeile bleibt unberuehrt.
		assert.equal(result.rows.length, 1);
		assert.equal(result.rows[0].metric, 'wind_gust');
	});

	test('ohne unbekannte Metrik bleibt unknownCorridors leer (kein Fehlalarm)', () => {
		const result = buildRoutePool(
			[{ metric: 'precipitation_sum', range: [null, 5], notify: true, mark: false }],
			undefined,
			[CAPE_EXTRA_DEF]
		);
		assert.deepEqual((result as { unknownCorridors?: unknown[] }).unknownCorridors, []);
	});

	test('eine per extraDefs bekannte Katalog-Metrik gilt NICHT als unbekannt', () => {
		const result = buildRoutePool(
			[{ metric: 'cape_max_jkg', range: [null, 500], notify: false, mark: true }],
			undefined,
			[CAPE_EXTRA_DEF]
		);
		assert.equal(result.rows.length, 1, 'cape_max_jkg muss als normale Zeile erscheinen');
		assert.deepEqual((result as { unknownCorridors?: unknown[] }).unknownCorridors, []);
	});
});

describe('F001: buildCorridorSavePayload — unknownCorridors bleiben beim Speichern erhalten', () => {
	test('uebergebene unknownCorridors werden unveraendert an corridors[] angehaengt', () => {
		const { rows } = buildRoutePool(
			[{ metric: 'wind_gust', range: [null, 70], notify: true, mark: false }],
			undefined,
			[CAPE_EXTRA_DEF]
		);
		const unknown = [
			{ metric: 'foo_future_metric', range: [null, 42] as [number | null, number | null], notify: false, mark: true },
		];
		const payload = buildCorridorSavePayload(rows, {}, unknown);
		assert.deepEqual(
			payload.corridors,
			[
				{ metric: 'wind_gust', range: [null, 70], notify: true, mark: false },
				{ metric: 'foo_future_metric', range: [null, 42], notify: false, mark: true },
			],
			'F001 FAIL: buildCorridorSavePayload nimmt die unknownCorridors nicht entgegen bzw. haengt sie nicht an'
		);
	});

	test('Rueckwaertskompatibel: Aufruf ohne den neuen Parameter bleibt unveraendert', () => {
		const { rows } = buildRoutePool(
			[{ metric: 'wind_gust', range: [null, 70], notify: true, mark: false }],
			undefined,
			[]
		);
		const payload = buildCorridorSavePayload(rows, { wind_gust: 'medium' } as never);
		assert.deepEqual(payload.corridors, [
			{ metric: 'wind_gust', range: [null, 70], notify: true, mark: false },
		]);
		assert.deepEqual(payload.metric_alert_levels, { wind_gust: 'medium' });
	});

	test('End-to-End: bekannte Zeile aendern -> unbekannter Korridor ueberlebt byte-gleich', () => {
		const loaded = buildRoutePool(
			[
				{ metric: 'foo_future_metric', range: [1, 2], notify: false, mark: true },
				{ metric: 'wind_gust', range: [null, 70], notify: true, mark: false },
			],
			undefined,
			[CAPE_EXTRA_DEF]
		);
		// Nutzer:in aendert NUR die bekannte Zeile.
		const changedRows = patchRow(loaded.rows, 'wind_gust', { max: 85 });
		const payload = buildCorridorSavePayload(
			changedRows,
			{},
			(loaded as { unknownCorridors?: unknown[] }).unknownCorridors as never
		);
		assert.deepEqual(
			payload.corridors.find((c) => c.metric === 'foo_future_metric'),
			{ metric: 'foo_future_metric', range: [1, 2], notify: false, mark: true },
			'F001 FAIL: der unbekannte Korridor ist beim Speichern verloren gegangen oder veraendert worden'
		);
		assert.equal(payload.corridors.find((c) => c.metric === 'wind_gust')?.range[1], 85);
	});
});

// ════════════════════════════════════════════════════════════════════════
// F002 (Adversary, MEDIUM) — Live-Katalog statt handgetippter Fixture.
// ════════════════════════════════════════════════════════════════════════

describe('F002: buildRouteMetricDefsFromCatalog gegen den LIVE-Backend-Katalog', () => {
	test('jede angebotene Zusatz-Groesse traegt mindestens eine Grenze — verhindert Rueckfall, sobald der Katalog waechst', async () => {
		const mod: typeof import('../compareMetricCatalogLoader.ts') = await import(MODULE_SPECIFIER);
		const liveResponse = fetchLiveCatalogResponse();
		const result = mod.buildRouteMetricDefsFromCatalog(liveResponse.metrics as never);
		assert.ok(result.length > 0, 'F002 FAIL: der Live-Katalog liefert keine Zusatz-Groessen');
		const missing = result.filter((d) => d.defaultMin == null && d.defaultMax == null);
		assert.deepEqual(
			missing.map((d) => d.metric),
			[],
			'F002 FAIL: diese Zusatz-Groessen haben KEINE Von/Bis-Vorgabe (beidseitig offen -> ' +
				'validateCorridorRows blockt -> Speichern des Reiters bleibt aus): ' +
				missing.map((d) => d.metric).join(', ')
		);
	});

	test('LIVE-Katalog: keine Duplikate und keine der 6 fest verdrahteten Groessen (AC-2/AC-3)', async () => {
		const mod: typeof import('../compareMetricCatalogLoader.ts') = await import(MODULE_SPECIFIER);
		const liveResponse = fetchLiveCatalogResponse();
		const result = mod.buildRouteMetricDefsFromCatalog(liveResponse.metrics as never);
		const ids = result.map((d) => d.metric);
		assert.equal(new Set(ids).size, ids.length, 'F002 FAIL: doppelte Metrik-ID in den Zusatz-Defs');
		for (const hardwired of ROUTE_METRIC_DEFS) {
			assert.equal(
				ids.includes(hardwired.metric),
				false,
				`F002 FAIL: "${hardwired.metric}" kommt doppelt (fest verdrahtet + Katalog)`
			);
		}
		// Gewitter bleibt exklusiv die alte Prozent-Definition (AC-3).
		assert.equal(ids.includes('thunder_level_max'), false, 'F002 FAIL: Gewitter-Ordinalvariante im Angebot');
		// Der erweiterte Pool bleibt duplikatfrei, wenn beide Quellen zusammenkommen.
		const { poolLeft } = buildRoutePool([], undefined, result);
		const poolIds = poolLeft.map((m) => m.metric);
		assert.equal(new Set(poolIds).size, poolIds.length, 'F002 FAIL: Duplikat im erweiterten Pool');
		assert.equal(poolIds.length, ROUTE_METRIC_DEFS.length + result.length);
	});
});
