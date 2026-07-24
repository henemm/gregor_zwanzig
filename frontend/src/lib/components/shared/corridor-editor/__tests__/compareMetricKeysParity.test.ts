// TDD — Issue #1351 F003 (Adversary-Fund) + F003b Fix-Loop 2: `COMPARE_METRIC_KEYS`
// (corridorEditorState.ts) ist eine DRITTE Kopie der Compare-Metrik-Keys
// neben Backend-Katalog (compare_metric_catalog.py) + Drift-Mapping
// (compare_metric_ids.py). Der bestehende Python-Drift-assert schuetzt nur
// die zwei Python-Module — diese Frontend-Fallback-Liste ("active_metrics
// === null => alle Metriken aktiv", genutzt von
// hydrateWeatherMetricsFromPreset in
// shared/weather-metrics-tab/weatherMetricsCompareSave.ts:22-26) kann
// unbemerkt hinter den Backend-Katalog zurueckfallen (genau das ist #1351
// F003 passiert: `wind_chill_max_c` fehlte).
//
// F003b-Fix (Adversary Runde 2): eine hartkodierte Erwartungsliste im Testfile
// ist KEIN echter Drift-Waechter -- sie schlaegt nur an, wenn jemand diese
// Liste selbst nachzieht (identischer Fehlermodus wie F003). Dieser Test
// liest daher die LIVE-Quelle: `uv run python3` importiert
// `compare_metric_catalog.get_compare_metric_catalog()` und liefert die
// tatsaechlichen Keys als JSON. Damit schlaegt der Test automatisch an,
// sobald sich der Backend-Katalog aendert, ohne dass jemand eine zweite
// Kopie von Hand pflegen muss -- analog zum Python-seitigen Import-Assert
// in compare_metric_catalog.py:94-99.
//
// Kein Mock, kein Dateiinhalt-Grep: der Python-Prozess FUEHRT den echten
// Katalog-Code aus (inkl. dessen eigener Drift-Assertions gegen
// compare_metric_ids.py) -- ein Paritaets-/Drift-Test, kein Verhaltensnachweis
// per String-Suche.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/corridor-editor/__tests__/compareMetricKeysParity.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import { COMPARE_METRIC_KEYS } from '../corridorEditorState.ts';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> corridor-editor -> shared -> components -> lib -> src -> frontend -> repoRoot
const REPO_ROOT = path.resolve(__dirname, ...Array(7).fill('..'));

const PY_SCRIPT =
	"import sys, json\n" +
	"sys.path.insert(0, 'src')\n" +
	"from output.renderers.compare_metric_catalog import get_compare_metric_catalog\n" +
	"print(json.dumps(sorted(e['key'] for e in get_compare_metric_catalog())))\n";

/** Liest die LIVE-Backend-Keys via `uv run python3` (echte Quelle, kein Fixture). */
function fetchBackendCatalogKeys(): string[] {
	const stdout = execFileSync('uv', ['run', 'python3', '-c', PY_SCRIPT], {
		cwd: REPO_ROOT,
		encoding: 'utf-8'
	});
	return JSON.parse(stdout.trim());
}

describe('COMPARE_METRIC_KEYS — Paritaet mit Backend-Katalog (#1351 F003/F003b)', () => {
	test('enthaelt exakt dieselben Keys wie die LIVE compare_metric_catalog.py', () => {
		const backendKeys = fetchBackendCatalogKeys();
		const actual = [...COMPARE_METRIC_KEYS].sort();
		const expected = [...backendKeys].sort();
		assert.deepEqual(
			actual,
			expected,
			`COMPARE_METRIC_KEYS weicht vom LIVE-Backend-Katalog ab -- fehlend: ` +
				`${expected.filter((k) => !actual.includes(k))}, zusaetzlich: ` +
				`${actual.filter((k) => !expected.includes(k))}`
		);
	});

	test('kennt wind_chill_max_c (#1351 Teil 1)', () => {
		assert.ok(
			COMPARE_METRIC_KEYS.includes('wind_chill_max_c'),
			'COMPARE_METRIC_KEYS fehlt wind_chill_max_c -- Alt-Vergleiche mit ' +
				'active_metrics=null wuerden die neue Metrik faelschlich als ' +
				'inaktiv behandeln (F003)'
		);
	});
});
