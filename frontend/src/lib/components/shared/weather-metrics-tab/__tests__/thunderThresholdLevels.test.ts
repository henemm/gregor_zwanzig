// Issue #1911 (Ableitung statt Doppel-Kopie): dieser Test parste bisher
// (#1474 Nachtrag) das hart codierte `levels={[...]}`-Literal in
// WeatherMetricsTab.svelte per Regex. Nach der Umstellung auf
// `deriveThunderThresholdLevels(...)` findet die Regex nichts mehr -- der
// Test verliert seine Zusicherung nicht, sondern prueft jetzt die ECHTE
// Ableitungsfunktion gegen echte Backend-Daten (Vorbild:
// corridor-editor/__tests__/compareMetricCatalogParity.test.ts, Live-Read
// per `execFileSync('uv', ...)`).
//
// Spec: docs/specs/modules/thunder_threshold_katalog.md AC-1, AC-2, AC-3,
// AC-6, AC-7 (Funktionsebene).
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/weather-metrics-tab/__tests__/thunderThresholdLevels.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
// __tests__ -> weather-metrics-tab -> shared
const WEATHER_METRICS_TAB = join(here, '..', '..', 'WeatherMetricsTab.svelte');
// __tests__ -> weather-metrics-tab -> shared -> corridor-editor
const MODULE_SPECIFIER = '../../corridor-editor/compareMetricCatalogLoader.ts';
const REPO_ROOT = resolve(here, ...Array(7).fill('..'));

interface Level {
	id: string;
	label: string;
	float: number;
}

type DeriveFn = (ordinalLabels: string[] | undefined) => Level[];

/**
 * Laedt `deriveThunderThresholdLevels` aus compareMetricCatalogLoader.ts.
 * Bricht sprechend (kein rohes ENOENT/undefined-Crash), solange die
 * Funktion noch nicht existiert -- Vorbild:
 * compareMetricCatalogParity.test.ts::loadDeriveActiveAlertMetricsForTrip.
 */
async function loadDerive(): Promise<DeriveFn> {
	const mod = await import(MODULE_SPECIFIER);
	const fn = (mod as Record<string, unknown>).deriveThunderThresholdLevels;
	if (typeof fn !== 'function') {
		assert.fail(
			'#1911 FAIL: `deriveThunderThresholdLevels` ist in ' +
				'shared/corridor-editor/compareMetricCatalogLoader.ts nicht exportiert -- ' +
				'die Ableitungsfunktion (Spec Implementation Details Punkt 3) fehlt noch.'
		);
	}
	return fn as DeriveFn;
}

// Live-Read gegen den ECHTEN Backend-Katalog UND die kanonische Stufenquelle
// (kein Fixture -- Issue #1424 F001 Praezedenz: eine hartkodierte
// Erwartungsliste ist kein Drift-Waechter).
const PY_SCRIPT =
	'import sys, json\n' +
	"sys.path.insert(0, 'src')\n" +
	'from output.renderers.compare_metric_catalog import get_compare_metric_catalog\n' +
	'from output.metric_format import THUNDER_LABEL_DE, thunder_ordinal\n' +
	'from app.models import ThunderLevel\n' +
	"catalog = get_compare_metric_catalog()\n" +
	"thunder = next(e for e in catalog if e['key'] == 'thunder_level_max')\n" +
	'ordered = sorted(ThunderLevel, key=thunder_ordinal)\n' +
	'canonical = [THUNDER_LABEL_DE[l] for l in ordered]\n' +
	"print(json.dumps({'ordinalLabels': thunder['ordinalLabels'], 'canonical': canonical}))\n";

function fetchLive(): { ordinalLabels: string[]; canonical: string[] } {
	const stdout = execFileSync('uv', ['run', 'python3', '-c', PY_SCRIPT], {
		cwd: REPO_ROOT,
		encoding: 'utf-8'
	});
	return JSON.parse(stdout.trim());
}

describe('#1911 AC-1/AC-2 (KRITISCH): deriveThunderThresholdLevels(Live-Katalog) -> 3 Stufen, korrekte floats', () => {
	test('genau 3 Stufen, "kein" nicht dabei, float 1.0/2.0/3.0 -> leicht/mittel/hoch', async () => {
		const derive = await loadDerive();
		const live = fetchLive();
		assert.deepEqual(
			live.ordinalLabels,
			['kein', 'leicht', 'mittel', 'hoch'],
			`Vorbedingung verletzt: der Backend-Katalog liefert nicht die erwarteten vier ` +
				`Stufen (ueberraschende Baseline-Aenderung?): ${JSON.stringify(live.ordinalLabels)}`
		);

		const levels = derive(live.ordinalLabels);

		assert.equal(
			levels.length,
			3,
			`AC-1 FAIL: erwartet genau 3 waehlbare Stufen, erhalten ${JSON.stringify(levels)}`
		);
		assert.ok(
			!levels.some((l) => l.id === 'kein' || l.label.toLowerCase() === 'kein'),
			`AC-1 FAIL: die Nullstufe "kein" darf keine waehlbare Alarmschwelle sein: ${JSON.stringify(levels)}`
		);

		// AC-2 (KRITISCH, Bestandsdaten-Risiko): Feld fuer Feld, nicht nur Laenge.
		// Ein Offset um eins wuerde still bei der falschen Stufe alarmieren.
		assert.deepEqual(
			levels.map((l) => l.float),
			[1.0, 2.0, 3.0],
			`AC-2 FAIL: float-Werte weichen von 1.0/2.0/3.0 ab (Bestandsdaten-Risiko!): ${JSON.stringify(levels)}`
		);
		assert.equal(
			levels[0].label.toLowerCase(),
			'leicht',
			`AC-2 FAIL: float 1.0 zeigt nicht auf "leicht", sondern auf "${levels[0].label}"`
		);
		assert.equal(
			levels[1].label.toLowerCase(),
			'mittel',
			`AC-2 FAIL: float 2.0 zeigt nicht auf "mittel", sondern auf "${levels[1].label}"`
		);
		assert.equal(
			levels[2].label.toLowerCase(),
			'hoch',
			`AC-2 FAIL: float 3.0 zeigt nicht auf "hoch", sondern auf "${levels[2].label}"`
		);
	});

	test('Bestandswert 1.0 bleibt "leicht", 2.0 bleibt "mittel" (Reverse-Mapping wie ThresholdMetricRow.svelte:28)', async () => {
		const derive = await loadDerive();
		const levels = derive(['kein', 'leicht', 'mittel', 'hoch']);
		const activeLabelFor = (float: number) => levels.find((l) => l.float === float)?.label;
		assert.equal(activeLabelFor(1.0)?.toLowerCase(), 'leicht');
		assert.equal(activeLabelFor(2.0)?.toLowerCase(), 'mittel');
		assert.equal(activeLabelFor(3.0)?.toLowerCase(), 'hoch');
	});
});

describe('#1911 AC-3: Labels stammen aus THUNDER_LABEL_DE, einzig zulaessige Abweichung ist der Anfangsbuchstabe', () => {
	test('deriveThunderThresholdLevels-Labels == THUNDER_LABEL_DE (Live-Read), nur Grossschreibung weicht ab', async () => {
		const derive = await loadDerive();
		const live = fetchLive();
		const levels = derive(live.ordinalLabels);
		const canonicalWithoutNone = live.canonical.slice(1); // Index 0 = NONE/"kein", verworfen

		levels.forEach((l, i) => {
			assert.equal(
				l.label.toLowerCase(),
				canonicalWithoutNone[i].toLowerCase(),
				`AC-3 FAIL: Level[${i}] ("${l.label}") weicht inhaltlich von THUNDER_LABEL_DE ` +
					`("${canonicalWithoutNone[i]}") ab -- jede Abweichung ausser der ` +
					'Anfangsbuchstaben-Grossschreibung ist ein Verstoss.'
			);
			assert.equal(
				l.label[0],
				l.label[0].toUpperCase(),
				`AC-3 FAIL: Level[${i}] ("${l.label}") beginnt nicht mit einem Grossbuchstaben.`
			);
		});
	});

	// doc-compliance-test: Abwesenheits-Nachweis ist per Verhalten nicht
	// pruefbar, nur per Dateiinhalt (CLAUDE.md-Ausnahme).
	test('# doc-compliance-test: das alte hart codierte Level-Literal steht nicht mehr in WeatherMetricsTab.svelte', () => {
		const source = readFileSync(WEATHER_METRICS_TAB, 'utf-8');
		const oldLiteral =
			/\{\s*id:\s*'leicht',\s*label:\s*'Leicht',\s*float:\s*1\.0\s*\}/;
		assert.equal(
			oldLiteral.test(source),
			false,
			'AC-3 FAIL: das hart codierte Level-Literal ' +
				"{ id: 'leicht', label: 'Leicht', float: 1.0 } steht weiterhin in " +
				'WeatherMetricsTab.svelte -- die Gewitter-Schwellenliste muss aus dem ' +
				'Backend-Katalog abgeleitet werden (deriveThunderThresholdLevels), nicht ' +
				'lokal getippt sein.'
		);
	});
});

describe('#1911 AC-6: eine synthetische fuenfte Stufe erscheint ohne Aenderung an der Funktion selbst', () => {
	test('5-Stufen-Fixture ["kein","leicht","mittel","hoch","extrem"] -> 4 Eintraege, floats 1.0..4.0', async () => {
		const derive = await loadDerive();
		const levels = derive(['kein', 'leicht', 'mittel', 'hoch', 'extrem']);
		assert.equal(
			levels.length,
			4,
			`AC-6 FAIL: erwartet 4 Eintraege (5 Katalog-Stufen minus Nullstufe), erhalten ${JSON.stringify(levels)}`
		);
		assert.deepEqual(
			levels.map((l) => l.float),
			[1, 2, 3, 4],
			`AC-6 FAIL: floats weichen von 1..4 ab: ${JSON.stringify(levels)}`
		);
		assert.equal(levels[3].label.toLowerCase(), 'extrem', 'AC-6 FAIL: die fuenfte Stufe fehlt/ist falsch benannt.');
	});
});

describe('#1911 AC-7 (Funktionsebene): kein Absturz bei fehlendem/leerem Katalog', () => {
	test('leeres Array -> leere Liste, kein Wurf', async () => {
		const derive = await loadDerive();
		assert.doesNotThrow(() => derive([]));
		assert.deepEqual(derive([]), []);
	});

	test('undefined (Katalog noch nicht geladen) -> leere Liste, kein Wurf', async () => {
		const derive = await loadDerive();
		assert.doesNotThrow(() => derive(undefined));
		assert.deepEqual(derive(undefined), []);
	});
});
