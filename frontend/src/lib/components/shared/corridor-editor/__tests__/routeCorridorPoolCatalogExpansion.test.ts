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
import { readFileSync, writeFileSync, rmSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, resolve } from 'node:path';

import {
	buildRoutePool,
	buildCorridorSavePayload,
	patchRow,
	addRow,
	ROUTE_CTX_DEFAULTS,
	ROUTE_METRIC_DEFS,
	ORDINAL_ENUM,
	type RouteMetricDef,
} from '../corridorEditorState.ts';

// AC-6 Test A: Zielstufen der Migration werden gegen die kanonische Enum-
// Quelle abgeleitet, nicht gegen eigene Zahlenliterale — eine zusaetzliche
// Stufe in ORDINAL_ENUM verschiebt die Bedeutung nicht still.
const MED_ORDINAL = ORDINAL_ENUM.indexOf('MED');
const HIGH_ORDINAL = ORDINAL_ENUM.indexOf('HIGH');

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
	// Issue #1425 S2 Teil 2 Scheibe B: NICHT mehr ausgeklammert — Gewitter zieht
	// auf genau diesen ordinalen Katalog-Eintrag um (metric_id "thunder" ist
	// seither KEIN Bruecken-Schluessel mehr).
	{ key: 'thunder_level_max', label: 'Gewitter', unit: '', kind: 'ordinal', ordinalLabels: ['kein', 'leicht', 'mittel', 'hoch'], metric_id: 'thunder' },
	{ key: 'temp_min_c', label: 'Temperatur', unit: '°C', kind: 'range', rangeMin: -30, rangeMax: 30, step: 1, metric_id: 'temperature' },
	// Duplikat: "gust".
	{ key: 'gust_max_kmh', label: 'Böen', unit: 'km/h', kind: 'range', rangeMin: 0, rangeMax: 150, step: 5, metric_id: 'gust' },
	// Issue #1585: cape_max_jkg entfallen — CAPE ist zentral nicht mehr waehlbar,
	// der Katalog-Endpoint liefert die Zeile nicht mehr aus.
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

// Erwartete 18 neuen Metriken, Katalog-Reihenfolge (PO-Entscheidung).
// Issue #1425 S2 Teil 2 Scheibe B: thunder_level_max kommt hinzu (Gewitter zieht
// von der Trip-eigenen Prozent-Definition auf den Katalog-Eintrag um).
const EXPECTED_NEW_KEYS = [
	'snow_depth_cm', 'snow_new_sum_cm', 'sunny_hours_h', 'wind_max_kmh', 'cloud_avg_pct',
	'visibility_min_m', 'uv_index_max', 'thunder_level_max', 'pop_max_pct',
	'wind_chill_min_c', 'wind_chill_max_c', 'humidity_avg_pct', 'dewpoint_avg_c',
	'cloud_low_avg_pct', 'cloud_mid_avg_pct', 'cloud_high_avg_pct', 'pressure_avg_hpa',
];

// Ausgeschlossen: 6 Duplikate (metric_id deckt sich mit ROUTE_CORRIDOR_CATALOG_IDS)
// + 2 _COMPARE_RANGE_UNSUPPORTED (kein Von/Bis-Bereich darstellbar).
const EXPECTED_EXCLUDED_KEYS = [
	'precip_sum_mm', 'temp_max_c', 'temp_min_c', 'gust_max_kmh',
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

	test('schliesst alle 6 Duplikate + 2 unterstuetzungslose Groessen aus (AC-2 + AC-3)', async () => {
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

	// Issue #1425 S2 Teil 2, Scheibe B: DIESE BEHAUPTUNG KEHRT SICH UM. In Teil 1
	// war Gewitter absichtlich ausgeklammert (die Prozent-Definition blieb
	// exklusiv in ROUTE_METRIC_DEFS). Ab Scheibe B ist genau das der Fehler:
	// Prozent-Bereich gegen Ordinal-Stundenwert markierte gerade DANN, wenn
	// Gewitter herrschte.
	test('thunder_level_max erscheint als ORDINALE Zusatz-Def — die alte Prozent-Definition faellt (Scheibe B, AC-2)', async () => {
		const mod = await loadCatalogLoaderModule();
		const buildRouteMetricDefsFromCatalog = (mod as Record<string, unknown>)
			.buildRouteMetricDefsFromCatalog as ((entries: unknown[]) => RouteMetricDef[]) | undefined;
		assert.ok(buildRouteMetricDefsFromCatalog, 'buildRouteMetricDefsFromCatalog fehlt noch');

		const result = buildRouteMetricDefsFromCatalog!(CATALOG_ENTRIES_FIXTURE);
		const thunder = result.find((d) => d.metric === 'thunder_level_max');
		assert.ok(
			thunder,
			'Scheibe B FAIL: Gewitter fehlt in den Zusatz-Defs — der Trip-Wertebereich ' +
				'haengt weiter an der Prozent-Skala und markiert invertiert'
		);
		assert.equal(
			(thunder as RouteMetricDef & { kind?: string }).kind,
			'ordinal',
			'Scheibe B FAIL: die Zusatz-Def traegt kein kind="ordinal" — der bereits ' +
				'vorhandene Ordinal-Zweig des Editors kann so nie greifen'
		);
		assert.deepEqual(
			(thunder as RouteMetricDef & { ordinalLabels?: string[] }).ordinalLabels,
			['kein', 'leicht', 'mittel', 'hoch'],
			'Scheibe B FAIL: ohne ordinalLabels haette der Editor keine Stufen-Beschriftungen'
		);
		assert.deepEqual(
			thunder!.scale,
			[0, 3],
			'Scheibe B FAIL: die Skala muss aus den Stufen abgeleitet werden ([0, labels-1]); ' +
				'der Zahlen-Fallback [0,100] waere wieder die Prozent-Falle'
		);
		assert.equal(
			result.some((d) => d.metric === 'thunder_level'),
			false,
			'Scheibe B FAIL: der alte Prozent-Schluessel darf nirgends mehr angeboten werden'
		);
		// Die alte Prozent-Definition ist aus der fest verdrahteten Liste raus.
		assert.equal(
			ROUTE_METRIC_DEFS.some((d) => d.metric === 'thunder_level'),
			false,
			'Scheibe B FAIL: ROUTE_METRIC_DEFS fuehrt Gewitter weiterhin als Prozent 0-100'
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
	// Scheibe B: 6 -> 5 fest verdrahtete Route-Groessen (thunder_level faellt).
	test('ohne extraDefs bleiben genau die 5 fest verdrahteten Groessen im Pool', () => {
		const { poolLeft } = buildRoutePool([]);
		assert.equal(poolLeft.length, 5, 'Regressions-FAIL: ohne extraDefs muessen genau 5 Metriken im Pool stehen (Gewitter ist Katalog-Groesse)');
		assert.equal(poolLeft.some((m) => m.metric === 'thunder_level'), false);
	});

	test('mit extraDefs erscheinen die neuen Metriken zusaetzlich zu den 5 alten (AC-1)', () => {
		const extraDefs: RouteMetricDef[] = [
			{ metric: 'cape_max_jkg', label: 'Gewitterenergie (CAPE)', unit: 'J/kg', scale: [0, 3000], step: 100, defaultMin: null, defaultMax: 500 },
			{ metric: 'pressure_avg_hpa', label: 'Luftdruck', unit: 'hPa', scale: [950, 1050], step: 5, defaultMin: 1010, defaultMax: null },
		];
		const { poolLeft } = buildRoutePool([], undefined, extraDefs);
		assert.equal(
			poolLeft.length,
			7,
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
		assert.equal(poolLeft.length, 5, 'AC-4 FAIL: die uebrigen 4 alten + 1 neue Metrik muessen im Pool stehen');
	});

	test('ROUTE_METRIC_DEFS fuehrt nach Scheibe B genau 5 Eintraege, kein Gewitter mehr', () => {
		assert.equal(ROUTE_METRIC_DEFS.length, 5, 'Scheibe B FAIL: ROUTE_METRIC_DEFS muss auf 5 Eintraege schrumpfen');
		assert.deepEqual(
			ROUTE_METRIC_DEFS.map((d) => d.metric).sort(),
			['precipitation_sum', 'snow_line', 'temperature_max', 'temperature_min', 'wind_gust']
		);
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

	test('LIVE-Katalog: keine Duplikate und keine der fest verdrahteten Groessen (AC-2/AC-3)', async () => {
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
		// Scheibe B: Gewitter kommt jetzt AUS dem Katalog (ordinal), nicht mehr
		// als Trip-eigene Prozent-Definition.
		assert.equal(
			ids.includes('thunder_level_max'),
			true,
			'Scheibe B FAIL: der LIVE-Katalog liefert Gewitter nicht als Zusatz-Groesse — ' +
				'im echten Betrieb bliebe der Trip-Wertebereich auf der Prozent-Skala'
		);
		// Der erweiterte Pool bleibt duplikatfrei, wenn beide Quellen zusammenkommen.
		const { poolLeft } = buildRoutePool([], undefined, result);
		const poolIds = poolLeft.map((m) => m.metric);
		assert.equal(new Set(poolIds).size, poolIds.length, 'F002 FAIL: Duplikat im erweiterten Pool');
		assert.equal(poolIds.length, ROUTE_METRIC_DEFS.length + result.length);
	});
});

// ════════════════════════════════════════════════════════════════════════
// Issue #1425 Schritt 2, Teil 2, SCHEIBE B — Gewitter-Skala vereinheitlichen.
// Spec: docs/specs/modules/fix_1425_s2b_gewitter_skala.md
//
// Der Trip fuehrte Gewitter als Prozent 0-100 ("bis 40"), der Stundenwert ist
// aber immer ein Ordinal 0/1/2 — jeder Prozent-Bereich schloss deshalb JEDEN
// Gewittergrad ein und markierte gerade dann, wenn Gewitter herrschte
// (Umkehrung, nicht bloss Wirkungslosigkeit).
//
// Die Zusatz-Defs kommen hier bewusst aus dem ECHTEN Mapper
// (buildRouteMetricDefsFromCatalog gegen die Katalog-Fixture) statt aus einer
// handgetippten Def — sonst pruefte der Test seine eigene Annahme.
// ════════════════════════════════════════════════════════════════════════

async function routeExtraDefs(): Promise<RouteMetricDef[]> {
	const mod = await loadCatalogLoaderModule();
	return mod.buildRouteMetricDefsFromCatalog(CATALOG_ENTRIES_FIXTURE as never);
}

describe('Scheibe B / AC-2: der Zeilenzustand traegt kind + ordinalLabels (Ordinal-Zweig wird erreichbar)', () => {
	test('gespeicherter Gewitter-Wertebereich wird als ordinale Zeile gebaut, nicht als Zahlen-Zeile', async () => {
		const extraDefs = await routeExtraDefs();
		const { rows } = buildRoutePool(
			[{ metric: 'thunder_level_max', range: [null, 0], notify: true, mark: true }],
			undefined,
			extraDefs
		);
		const row = rows.find((r) => r.metric === 'thunder_level_max');
		assert.ok(row, 'AC-2 FAIL: die Gewitter-Zeile fehlt komplett');
		assert.equal(
			row!.kind,
			'ordinal',
			'AC-2 FAIL: buildRoutePool reicht kind nicht in den Zeilenzustand durch — der ' +
				'Ordinal-Zweig (CorridorEditor.svelte, row.kind === "ordinal") kann im Trip ' +
				'strukturell nie greifen, der Nutzer sieht weiterhin ein Zahlenfeld'
		);
		assert.deepEqual(
			row!.ordinalLabels,
			['kein', 'leicht', 'mittel', 'hoch'],
			'AC-2 FAIL: ohne ordinalLabels rendert der Ordinal-Zweig eine LEERE Schaltflaechen-Gruppe'
		);
		assert.deepEqual(row!.scale, [0, 3], 'AC-2 FAIL: die Zeile traegt weiterhin eine Prozent-Skala');
	});

	test('eine gewoehnliche Zahlen-Groesse bekommt KEIN kind="ordinal" (Gegenprobe)', async () => {
		const extraDefs = await routeExtraDefs();
		// Issue #1585: Traeger-Groesse von cape_max_jkg auf humidity_avg_pct
		// gewechselt — CAPE ist zentral nicht mehr waehlbar und erreicht den
		// Pool nicht mehr. Der Pruefgegenstand (Zahlen-Groesse bekommt kein
		// kind="ordinal") ist unveraendert.
		const { rows } = buildRoutePool(
			[{ metric: 'humidity_avg_pct', range: [30, null], notify: false, mark: true }],
			undefined,
			extraDefs
		);
		const row = rows.find((r) => r.metric === 'humidity_avg_pct');
		assert.ok(row);
		assert.notEqual(row!.kind, 'ordinal', 'Luftfeuchtigkeit ist eine Zahlen-Groesse und darf keine Stufen-Buttons bekommen');
	});

	test('addRow uebernimmt kind/ordinalLabels ebenfalls (frisch hinzugefuegte Zeile)', async () => {
		const extraDefs = await routeExtraDefs();
		const { rows, poolLeft } = buildRoutePool([], undefined, extraDefs);
		const next = addRow(rows, poolLeft, 'thunder_level_max', ROUTE_CTX_DEFAULTS);
		const row = next.rows.find((r) => r.metric === 'thunder_level_max');
		assert.ok(row, 'AC-2 FAIL: "+ Metrik" legt keine Gewitter-Zeile an');
		assert.equal(row!.kind, 'ordinal', 'AC-2 FAIL: frisch hinzugefuegte Gewitter-Zeile zeigt ein Zahlenfeld');
		assert.deepEqual(row!.ordinalLabels, ['kein', 'leicht', 'mittel', 'hoch']);
	});
});

describe('Scheibe B / AC-4: Standardwert einer neu hinzugefuegten Gewitter-Zeile', () => {
	test('addRow(thunder_level_max) liefert min=null, max=0 ("bis kein Gewitter")', async () => {
		const extraDefs = await routeExtraDefs();
		const { rows, poolLeft } = buildRoutePool([], undefined, extraDefs);
		const next = addRow(rows, poolLeft, 'thunder_level_max', ROUTE_CTX_DEFAULTS);
		const row = next.rows.find((r) => r.metric === 'thunder_level_max');
		assert.ok(row, 'AC-4 FAIL: Gewitter steht nicht im "+ Metrik"-Pool');
		assert.equal(row!.min, null, 'AC-4 FAIL: die Untergrenze muss offen bleiben');
		assert.equal(
			row!.max,
			0,
			'AC-4 FAIL: Standardwert ist "bis kein Gewitter" (Ordinal 0) — identisch zum ' +
				'Ortsvergleich (_COMPARE_DEFAULTS.thunder_level_max)'
		);
		assert.equal(next.poolLeft.some((m) => m.metric === 'thunder_level_max'), false);
	});
});

describe('Scheibe B / AC-3: Alt-Korridore werden beim Laden umgeschluesselt und umgerechnet', () => {
	// Prozent -> Stufe (Spec § Implementation Details Punkt 1, #2012-Korrektur):
	//   null -> null · JEDE Zahl als Prozent gedeutet (kein "schon ordinal"-
	//   Sonderzweig mehr) · 0-33 -> 0 (kein) · 34-66 -> 2 (mittel) · 67-100 -> 3 (hoch)
	//   Stufe 1 ("leicht") ist ueber die Migration nie erreichbar (Spec Punkt 4).
	const MIGRATION_CASES: Array<{
		from: [number | null, number | null];
		to: [number | null, number | null];
		why: string;
		word?: string;
	}> = [
		{ from: [null, 40], to: [null, MED_ORDINAL], why: 'die alte Vorgabe "bis 40 %" wird "bis mittel" (AC-1)', word: 'mittel' },
		{ from: [null, 0], to: [null, 0], why: '0 Prozent liegt im ersten Drittel -> kein' },
		{
			from: [null, 1],
			to: [null, 0],
			why: 'der einzige Produktivwert (1 Prozent) liegt im ersten Drittel -> kein, NICHT mehr "bereits ordinal (mittel)" (AC-2)',
			word: 'kein',
		},
		{ from: [null, 2], to: [null, 0], why: '2 Prozent liegt im ersten Drittel -> kein, NICHT mehr "bereits ordinal (hoch)"' },
		{ from: [null, 33], to: [null, 0], why: 'oberes Ende des ersten Drittels -> kein' },
		{ from: [null, 34], to: [null, MED_ORDINAL], why: 'unteres Ende des zweiten Drittels -> mittel' },
		{ from: [null, 66], to: [null, MED_ORDINAL], why: 'oberes Ende des zweiten Drittels -> mittel' },
		{ from: [null, 67], to: [null, HIGH_ORDINAL], why: 'unteres Ende des dritten Drittels -> hoch' },
		{ from: [null, 100], to: [null, HIGH_ORDINAL], why: 'Prozent-Maximum -> hoch (AC-3, Stufe "hoch" erstmals erreichbar)', word: 'hoch' },
		{ from: [null, null], to: [null, null], why: 'beidseitig offen bleibt beidseitig offen' },
		{ from: [50, null], to: [MED_ORDINAL, null], why: 'auch die Untergrenze wird umgerechnet' },
		{ from: [0, 100], to: [0, HIGH_ORDINAL], why: 'beide Grenzen unabhaengig voneinander (AC-5)' },
	];

	for (const c of MIGRATION_CASES) {
		test(`gespeichert {thunder_level, [${c.from[0]}, ${c.from[1]}]} -> {thunder_level_max, [${c.to[0]}, ${c.to[1]}]} — ${c.why}`, async () => {
			const extraDefs = await routeExtraDefs();
			const result = buildRoutePool(
				[{ metric: 'thunder_level', range: c.from, notify: true, mark: true }],
				undefined,
				extraDefs
			);
			const row = result.rows.find((r) => r.metric === 'thunder_level_max');
			assert.ok(
				row,
				'AC-3 FAIL: der gespeicherte Alt-Korridor erscheint nicht als ordinale Zeile — ' +
					'er verschwindet damit lautlos aus dem Editor UND aus der Markierung'
			);
			assert.equal(row!.min, c.to[0], `AC-3 FAIL (Untergrenze): ${c.why}`);
			assert.equal(row!.max, c.to[1], `AC-3 FAIL (Obergrenze): ${c.why}`);
			assert.equal(
				result.rows.some((r) => r.metric === 'thunder_level'),
				false,
				'AC-3 FAIL: die Zeile traegt noch den alten Prozent-Schluessel'
			);
			// AC-1/AC-2: das ANGEZEIGTE Stufenwort pruefen, nicht nur den nackten
			// Index — der Alt-Test blieb seit #1474 gruen, weil er nur Zahlen verglich.
			if (c.word != null && c.to[1] != null) {
				assert.equal(
					row!.ordinalLabels?.[c.to[1] as number],
					c.word,
					`AC-1/AC-2 FAIL: angezeigtes Stufenwort fuer Index ${c.to[1]} ist nicht "${c.word}"`
				);
			}
		});
	}

	// Risiko #2 der Spec / F001-Analogie aus Teil 1: die Umschluesselung muss VOR
	// der present-Map-Bildung laufen. Sonst gilt "thunder_level" als unbekannt,
	// landet im Pass-Through und wird beim naechsten Speichern ZUSAETZLICH zur
	// neuen Zeile persistiert (Doppel-Speicherung).
	test('der Alt-Korridor landet NICHT zusaetzlich in unknownCorridors (keine Doppel-Speicherung)', async () => {
		const extraDefs = await routeExtraDefs();
		const result = buildRoutePool(
			[{ metric: 'thunder_level', range: [null, 40], notify: true, mark: true }],
			undefined,
			extraDefs
		);
		assert.deepEqual(
			result.unknownCorridors,
			[],
			'AC-3 FAIL: der migrierte Alt-Korridor wird als "unbekannt" durchgereicht — beim ' +
				'naechsten Speichern staende er ein zweites Mal in corridors[]'
		);
	});

	test('Speichern nach der Migration schreibt genau EINEN Gewitter-Eintrag, unter dem neuen Schluessel', async () => {
		const extraDefs = await routeExtraDefs();
		const loaded = buildRoutePool(
			[
				{ metric: 'wind_gust', range: [null, 70], notify: true, mark: false },
				{ metric: 'thunder_level', range: [null, 40], notify: true, mark: true },
			],
			undefined,
			extraDefs
		);
		const payload = buildCorridorSavePayload(loaded.rows, {}, loaded.unknownCorridors);
		const gewitter = payload.corridors.filter(
			(c) => c.metric === 'thunder_level' || c.metric === 'thunder_level_max'
		);
		assert.equal(gewitter.length, 1, `AC-3 FAIL: ${gewitter.length} Gewitter-Eintraege gespeichert statt genau einem`);
		assert.equal(gewitter[0].metric, 'thunder_level_max');
		assert.deepEqual(gewitter[0].range, [null, MED_ORDINAL]);
		assert.equal(gewitter[0].notify, true, 'notify/mark der Alt-Zeile muessen erhalten bleiben');
		assert.equal(gewitter[0].mark, true);
		// Die Nachbar-Zeile bleibt unberuehrt.
		assert.deepEqual(
			payload.corridors.find((c) => c.metric === 'wind_gust'),
			{ metric: 'wind_gust', range: [null, 70], notify: true, mark: false }
		);
	});

	test('ein bereits migrierter Korridor bleibt beim erneuten Laden unveraendert (idempotent)', async () => {
		const extraDefs = await routeExtraDefs();
		const result = buildRoutePool(
			[{ metric: 'thunder_level_max', range: [null, 1], notify: true, mark: true }],
			undefined,
			extraDefs
		);
		const row = result.rows.find((r) => r.metric === 'thunder_level_max');
		assert.ok(row);
		assert.equal(row!.min, null);
		assert.equal(row!.max, 1, 'ein zweiter Ladevorgang darf den Wert nicht erneut umrechnen');
		assert.deepEqual(result.unknownCorridors, []);
	});

	test('andere Metriken werden von der Umschluesselung nicht angefasst (Gegenprobe)', async () => {
		const extraDefs = await routeExtraDefs();
		const result = buildRoutePool(
			[{ metric: 'wind_gust', range: [null, 40], notify: true, mark: false }],
			undefined,
			extraDefs
		);
		const row = result.rows.find((r) => r.metric === 'wind_gust');
		assert.ok(row);
		assert.equal(row!.max, 40, 'die 40 km/h Boeen-Grenze darf nicht zu einer Stufe verrechnet werden');
	});
});

// AC-6 Test A-2 (F001-Fix, Adversary-Mutation): Test A oben vergleicht das
// Migrationsergebnis gegen MED_ORDINAL/HIGH_ORDINAL — beides Werte, die die
// Testdatei SELBST per ORDINAL_ENUM.indexOf(...) berechnet und die mit dem
// heutigen Stand ['NONE','LOW','MED','HIGH'] zufaellig mit den Zahlenliteralen
// 2/3 uebereinstimmen. Ein Produktivcode, der `return (1 + 1);` /
// `return (1 + 2);` statt `ORDINAL_ENUM.indexOf('MED'|'HIGH')` zurueckgibt,
// bleibt fuer Test A unsichtbar, weil BEIDE Seiten denselben Zahlenwert
// liefern. Dieser Test verschiebt die kanonische Skala selbst (eine
// eingeschobene Zwischenstufe VOR 'MED' verschiebt MED UND HIGH je um +1
// Index) und importiert eine Kopie des Moduls mit der verschobenen Skala
// dynamisch — nur eine echte `ORDINAL_ENUM.indexOf(...)`-Kopplung liefert
// dann noch die richtigen, neuen Indizes.
describe('AC-6 Test A-2: die Migration folgt einer VERSCHOBENEN ORDINAL_ENUM (Kopplungsnachweis)', () => {
	const CORRIDOR_STATE_PATH = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'corridorEditorState.ts');
	const ENUM_LINE = "export const ORDINAL_ENUM = ['NONE', 'LOW', 'MED', 'HIGH'] as const;";
	const SHIFTED_ENUM_LINE = "export const ORDINAL_ENUM = ['NONE', 'LOW', 'SEVERE', 'MED', 'HIGH'] as const;";
	// F003 (Adversary Runde 2): die temporaere Modulkopie darf NICHT in
	// corridor-editor/ selbst liegen -- genau diesen Ordner scannt
	// thunderScaleLocalCopyGuard.test.ts unter Regel A/P/C als Produktivcode.
	// Bricht dieser Testprozess vor dem `finally` hart ab (CI-Timeout,
	// SIGKILL), bleibt die Kopie liegen und der Waechter meldet sie
	// faelschlich als neuen lokalen ORDINAL_ENUM-Nachbau -- ein fälschlich
	// blockierendes Gate fuer eine ANDERE Sitzung. Ablage daher im eigenen
	// __tests__-Verzeichnis: istTestdatei() in thunderScaleLocalCopyGuard
	// schliesst jeden Pfad mit "__tests__" von der A/P/C-Scanflaeche aus
	// (nur Regel D laeuft dort, und die verlangt eine Paritaets-BEHAUPTUNG im
	// Kommentar, die diese Datei nicht traegt). corridorEditorState.ts
	// importiert ausschliesslich ueber die $lib/*-Aliasse (global per
	// test-lib-loader.mjs aufgeloest, nicht relativ zum Dateiort) -- die
	// Ablage im __tests__-Ordner aendert an der Aufloesbarkeit nichts.
	const TMP_PATH = resolve(
		dirname(fileURLToPath(import.meta.url)),
		`corridorEditorState.__tmp_ac6_shifted_${process.pid}.ts`
	);

	test('eine vor "MED" eingeschobene Stufe verschiebt MED (2->3) UND HIGH (3->4) — die Migration muss folgen', async () => {
		const original = readFileSync(CORRIDOR_STATE_PATH, 'utf-8');
		assert.ok(
			original.includes(ENUM_LINE),
			'Testannahme verletzt: ORDINAL_ENUM-Deklaration in corridorEditorState.ts hat sich veraendert — Test anpassen'
		);
		const shiftedSource = original.replace(ENUM_LINE, SHIFTED_ENUM_LINE);
		writeFileSync(TMP_PATH, shiftedSource, 'utf-8');
		try {
			const mod: typeof import('../corridorEditorState.ts') = await import(pathToFileURL(TMP_PATH).href);
			const shiftedMed = mod.ORDINAL_ENUM.indexOf('MED' as never);
			const shiftedHigh = mod.ORDINAL_ENUM.indexOf('HIGH' as never);
			assert.equal(shiftedMed, 3, 'Testannahme verletzt: MED verschiebt sich nicht wie erwartet von 2 auf 3');
			assert.equal(shiftedHigh, 4, 'Testannahme verletzt: HIGH verschiebt sich nicht wie erwartet von 3 auf 4');

			const extraDefs = await routeExtraDefs();
			const rowMed = mod
				.buildRoutePool([{ metric: 'thunder_level', range: [null, 40], notify: true, mark: true }], undefined, extraDefs)
				.rows.find((r) => r.metric === 'thunder_level_max');
			assert.ok(rowMed, 'AC-6 FAIL: die migrierte Zeile fehlt in der verschobenen Skala (MED-Fall)');
			assert.equal(
				rowMed!.max,
				shiftedMed,
				'AC-6 FAIL: "bis 40%" migriert nicht auf den NEUEN Index von MED (3) — die Migration ' +
					'haengt an einer festen Zahl statt an ORDINAL_ENUM.indexOf(\'MED\')'
			);

			const rowHigh = mod
				.buildRoutePool([{ metric: 'thunder_level', range: [null, 100], notify: true, mark: true }], undefined, extraDefs)
				.rows.find((r) => r.metric === 'thunder_level_max');
			assert.ok(rowHigh, 'AC-6 FAIL: die migrierte Zeile fehlt in der verschobenen Skala (HIGH-Fall)');
			assert.equal(
				rowHigh!.max,
				shiftedHigh,
				'AC-6 FAIL: "bis 100%" migriert nicht auf den NEUEN Index von HIGH (4) — die Migration ' +
					'haengt an einer festen Zahl statt an ORDINAL_ENUM.indexOf(\'HIGH\')'
			);
		} finally {
			rmSync(TMP_PATH, { force: true });
		}
	});
});

// AC-6 Test B (reiner Quelltext-Scan auf percentBoundToOrdinal()) ist mit
// #2012-Adversary-Runde-2/F002 ersatzlos entfernt: sechs Mutationen fanden
// keinen Fall, den Test B fing und Test A-2 oben (Verhaltensprüfung gegen
// eine VERSCHOBENE ORDINAL_ENUM) nicht auch fing — Test B blockierte
// zugleich korrekten, aequivalenten Code (z. B. eine ausgelagerte Konstante
// `const MED_STAGE = ORDINAL_ENUM.indexOf('MED'); return MED_STAGE;`) als
// Falsch-Positiv. Test A-2 traegt die Zusicherung jetzt allein — Nachweis
// (3 Mutationen, alle von Test A-2 gefangen) in
// docs/specs/modules/fix_2012_gewitter_stufen_migration.md, AC-6.
