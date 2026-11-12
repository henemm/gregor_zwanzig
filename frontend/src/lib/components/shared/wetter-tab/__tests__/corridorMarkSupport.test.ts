// TDD RED — Issue #1425 Schritt 2, Teil 2, Scheibe A (Spec:
// docs/specs/modules/fix_1425_s2b_markier_wirkung.md, AC-4 Frontend-Teil).
//
// Der Reiter "Wertebereiche" bietet im TRIP (context='route') auch fuer die
// drei Tages-Summen einen "Markieren"-Schalter an, obwohl die Markierung dort
// nie wirken kann (kein 1:1-Stundenpendant) — Bedienelement ohne Wirkung, die
// Fehlerklasse aus #1384. Im ORTSVERGLEICH bleibt derselbe Schalter richtig.
//
// Geprueft wird EINE geteilte, exportierte Entscheidungsfunktion
// `supportsMark(metric, context)` in corridorEditorState.ts — bewusst NICHT
// zweimal als Komponententest fuer CorridorEditor.svelte (Desktop) und
// CorridorEditorMobile.svelte (Mobil): das wuerden zwei Kopien derselben
// Bedingung (Teilungs-Invariante CLAUDE.md, Anti-Pattern #1170). Die beiden
// Komponenten reichen nur noch durch.
//
// Ausfuehrung: cd frontend && npm test -- \
//   src/lib/components/shared/corridor-editor/__tests__/corridorMarkSupport.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

import { ROUTE_METRIC_DEFS } from '../corridorEditorState.ts';

const STATE_MODULE = '../corridorEditorState.ts';
const LOADER_MODULE = '../compareMetricCatalogLoader.ts';

// Pfadregel #1409: Prueflings-Wurzel relativ zur EIGENEN Testdatei (Worktree),
// nicht ueber einen festen Hauptrepo-Pfad — sonst prueft der Test aus dem
// Worktree die unveraenderte Hauptrepo-Kopie und meldet falsches Gruen.
const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), ...Array(7).fill('..'));
const PY_SCRIPT =
	'import sys, json\n' +
	"sys.path.insert(0, 'src')\n" +
	'from output.renderers.compare_metric_catalog import get_compare_metric_catalog\n' +
	"print(json.dumps({'metrics': get_compare_metric_catalog()}))\n";

type CatalogEntry = { key: string; metric_id?: string; aggregation?: string };

/** Liest den LIVE-Katalog (echte Quelle, kein handgetipptes Fixture). */
function fetchLiveCatalogEntries(): CatalogEntry[] {
	const stdout = execFileSync('uv', ['run', 'python3', '-c', PY_SCRIPT], {
		cwd: REPO_ROOT,
		encoding: 'utf-8'
	});
	return JSON.parse(stdout.trim()).metrics as CatalogEntry[];
}

type CorridorContext = 'route' | 'vergleich';
type SupportsMark = (metric: string, context: CorridorContext) => boolean;

async function loadSupportsMark(): Promise<SupportsMark> {
	const mod = (await import(STATE_MODULE)) as Record<string, unknown>;
	assert.equal(
		typeof mod.supportsMark,
		'function',
		'AC-4 FAIL: corridorEditorState.ts exportiert kein supportsMark(metric, context) — ' +
			'die Schalter-Sichtbarkeit ist noch in den beiden Svelte-Komponenten verdrahtet ' +
			'(Issue #1425 Schritt 2, Teil 2, Scheibe A noch nicht implementiert).'
	);
	return mod.supportsMark as SupportsMark;
}

// Die drei Tages-Summen, die im Trip-Reiter angeboten werden:
//   precipitation_sum  — Route-Key aus ROUTE_METRIC_DEFS (kein Katalog-Key)
//   snow_new_sum_cm    — Katalog-Key, aggregation='sum'
//   sunny_hours_h      — Katalog-Key, aggregation='sum'
const TRIP_SUM_METRICS = ['precipitation_sum', 'snow_new_sum_cm', 'sunny_hours_h'];

// Vertreter der Groessen, die im Trip weiterhin markieren duerfen
// (Extrema + Mittelwerte, alte Route-Keys UND neue Katalog-Keys).
const TRIP_MARKABLE_METRICS = [
	'wind_gust', 'temperature_min', 'temperature_max', 'thunder_level', 'snow_line',
	'cape_max_jkg', 'humidity_avg_pct', 'wind_chill_min_c', 'uv_index_max', 'pressure_avg_hpa'
];

describe('AC-4 (Frontend): supportsMark() blendet den Markieren-Schalter nur im Trip aus', () => {
	test('exportiert supportsMark als Funktion', async () => {
		await loadSupportsMark();
	});

	test('Trip (context="route"): die drei Tages-Summen bieten KEINEN Markieren-Schalter', async () => {
		const supportsMark = await loadSupportsMark();
		for (const metric of TRIP_SUM_METRICS) {
			assert.equal(supportsMark(metric, 'route'), false,
				`AC-4 FAIL: "${metric}" ist eine Tages-Summe — im Trip-Briefing gibt es keine Zeile, ` +
				'an der eine Markierung andocken koennte (Schalter ohne Wirkung).');
		}
	});

	test('Ortsvergleich (context="vergleich"): dieselben Groessen bleiben markierbar', async () => {
		const supportsMark = await loadSupportsMark();
		for (const metric of [...TRIP_SUM_METRICS, 'precip_sum_mm']) {
			assert.equal(supportsMark(metric, 'vergleich'), true,
				`AC-4 FAIL: "${metric}" muss im Ortsvergleich markierbar bleiben — dort markiert die ` +
				'Uebersichtszeile Tages-Aggregate korrekt (CORRIDOR_METRIC_TO_HOUR_KEY unberuehrt).');
		}
	});

	test('Trip: Extrema und Mittelwerte behalten den Markieren-Schalter', async () => {
		const supportsMark = await loadSupportsMark();
		for (const metric of TRIP_MARKABLE_METRICS) {
			assert.equal(supportsMark(metric, 'route'), true,
				`AC-4 FAIL: "${metric}" ist keine Tages-Summe — der Schalter muss sichtbar bleiben ` +
				'(Regressionsschutz: 5 alte Route-Keys + 15 neue Katalog-Groessen).');
		}
	});

	test('unbekannte Metrik-ID: Schalter bleibt sichtbar (kein stilles Verstecken)', async () => {
		const supportsMark = await loadSupportsMark();
		assert.equal(supportsMark('voellig_unbekannte_groesse_xyz', 'route'), true,
			'AC-4 FAIL: ausgeblendet wird ausschliesslich fuer die drei bekannten Tages-Summen.');
		assert.equal(supportsMark('voellig_unbekannte_groesse_xyz', 'vergleich'), true);
	});
});

describe('AC-4 Drift-Waechter: die Ausnahme folgt der Auswertung im LIVE-Katalog', () => {
	test('jede im Trip angebotene Groesse mit aggregation="sum" ist nicht markierbar, jede andere schon', async () => {
		const supportsMark = await loadSupportsMark();
		const loader = (await import(LOADER_MODULE)) as Record<string, unknown>;
		const buildRouteMetricDefsFromCatalog = loader.buildRouteMetricDefsFromCatalog as
			(entries: unknown[]) => Array<{ metric: string }>;
		const entries = fetchLiveCatalogEntries();
		const aggregationByKey = new Map(entries.map((e) => [e.key, e.aggregation]));

		// Genau das Angebot des Trip-Reiters: 6 fest verdrahtete Route-Defs +
		// die Katalog-Zusaetze (Teil 1). Keine zweite, driftende Liste.
		const offered = [
			...ROUTE_METRIC_DEFS.map((d) => d.metric),
			...buildRouteMetricDefsFromCatalog(entries as unknown[]).map((d) => d.metric)
		];
		assert.ok(offered.length >= 20, `Erwartet >=20 angebotene Groessen, gefunden ${offered.length}`);

		const wrong: string[] = [];
		for (const metric of offered) {
			// precipitation_sum ist der Route-Key derselben Tages-Summe wie der
			// Katalog-Key precip_sum_mm (aggregation='sum') — er steht nicht im
			// Katalog und wird deshalb hier namentlich gefuehrt (Kommentar
			// html.py:560-562: "Tages-Summe hat keine 1:1-Stundenspalte").
			const isSum = aggregationByKey.get(metric) === 'sum' || metric === 'precipitation_sum';
			if (supportsMark(metric, 'route') !== !isSum) {
				wrong.push(`${metric} (aggregation=${aggregationByKey.get(metric) ?? 'route-key'})`);
			}
		}
		assert.deepEqual(
			wrong,
			[],
			'AC-4 FAIL: die Markieren-Ausnahme deckt sich nicht mit der Auswertung im ' +
				'zentralen Katalog. Abweichungen: ' + wrong.join(', ')
		);
	});

	test('im Ortsvergleich ist keine einzige Katalog-Groesse vom Markieren ausgeschlossen', async () => {
		const supportsMark = await loadSupportsMark();
		const entries = fetchLiveCatalogEntries();
		const excluded = entries.map((e) => e.key).filter((m) => !supportsMark(m, 'vergleich'));
		assert.deepEqual(
			excluded,
			[],
			'AC-4 FAIL: der Ortsvergleich darf keinen Markieren-Schalter verlieren — ' +
				'ausgeschlossen: ' + excluded.join(', ')
		);
	});
});
