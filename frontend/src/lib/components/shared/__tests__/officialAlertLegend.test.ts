// TDD RED — Scheibe B von #1318: Kürzel-Legende in der Konfigurationsoberfläche.
//
// Spec: docs/specs/modules/sms_official_alert_tokens.md — AC-9,
// Implementation Details Abschnitt 5.
//
// Geprüft wird die Invariante, um die es in AC-9 eigentlich geht: die
// angezeigten Kürzel stammen aus dem BACKEND-Katalog
// (`src/output/tokens/hazard_symbols.py`), es gibt KEINE zweite hartkodierte
// Liste im Frontend. Der Katalog wird deshalb im selben Testlauf aus der
// Backend-Quelle gelesen, nicht im Test hartkodiert.
//
// Schicht-Hinweis (ehrlich): Svelte-5-Komponenten sind in diesem Setup nicht
// mountbar (kein @testing-library/svelte, Muster wie
// official_alerts_single_control_ui.test.ts). Geprüft wird daher die Struktur
// der Quelle plus die Auslieferungskette Backend -> Frontend. Der Abgleich
// „gerenderter DOM-Text == Backend-Antwort" gehört in die Staging-Playwright-
// Prüfung der Phase 6 (die Spec lässt beide Wege ausdrücklich zu).
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/officialAlertLegend.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { parse } from 'svelte/compiler';

const here = dirname(fileURLToPath(import.meta.url));
const SHARED_DIR = join(here, '..');
// __tests__ -> shared -> components -> lib -> src -> frontend -> repo
const REPO_ROOT = join(here, '..', '..', '..', '..', '..', '..');
const FRONTEND_SRC = join(REPO_ROOT, 'frontend', 'src');
const WEATHER_METRICS_TAB = join(SHARED_DIR, 'WeatherMetricsTab.svelte');
const HAZARD_SYMBOLS_PY = join(REPO_ROOT, 'src', 'output', 'tokens', 'hazard_symbols.py');

const LEGEND_TESTID = 'official-alerts-symbol-legend';

// Die 7 SMS-schwellenwertfähigen Metriken (Spec Abschnitt 5a). Quelle der
// Kürzel ist `SMS_SYMBOL_BY_METRIC` in src/output/renderers/sms_trip.py.
const SMS_THRESHOLD_METRIC_IDS = [
	'precipitation', 'rain_probability', 'wind', 'gust', 'thunder',
	'snow_depth', 'snowfall_limit'
];

function read(path: string): string {
	return readFileSync(path, 'utf-8');
}

/** Liest den Backend-Katalog (hazard -> Kürzel) aus hazard_symbols.py. */
function backendHazardCatalog(): Record<string, string> {
	const src = read(HAZARD_SYMBOLS_PY);
	const block = src.match(/HAZARD_SMS_SYMBOLS[^=]*=\s*\{([\s\S]*?)\}/);
	assert.ok(block, 'HAZARD_SMS_SYMBOLS nicht in hazard_symbols.py gefunden');
	const catalog: Record<string, string> = {};
	for (const m of block![1].matchAll(/"([a-z_]+)"\s*:\s*"([A-Z]+)"/g)) {
		catalog[m[1]] = m[2];
	}
	assert.equal(
		Object.keys(catalog).length, 9,
		`Backend-Katalog muss 9 Gefahrenarten führen, gelesen: ${JSON.stringify(catalog)}`
	);
	return catalog;
}

/** Alle Quelldateien unterhalb frontend/src (ohne __tests__). */
function frontendSources(dir = FRONTEND_SRC, acc: string[] = []): string[] {
	for (const entry of readdirSync(dir)) {
		const full = join(dir, entry);
		if (statSync(full).isDirectory()) {
			if (entry === '__tests__' || entry === 'node_modules') continue;
			frontendSources(full, acc);
		} else if (/\.(svelte|ts|js)$/.test(entry)) {
			acc.push(full);
		}
	}
	return acc;
}

describe('AC-9: Legende beim Schalter „Amtliche Warnungen"', () => {
	test('Die Legende existiert als eigene Bedienstelle im geteilten Snippet', () => {
		const src = read(WEATHER_METRICS_TAB);
		assert.ok(
			src.includes(LEGEND_TESTID),
			`WeatherMetricsTab muss die Kürzel-Legende rendern (testid "${LEGEND_TESTID}"), ` +
				'im geteilten officialAlertsToggle-Snippet (Sichtbarkeit kontextabhängig, s.u.).'
		);
	});

	test('Die Legende erklärt den `!`-Marker', () => {
		const src = read(WEATHER_METRICS_TAB);
		const idx = src.indexOf(LEGEND_TESTID);
		assert.ok(idx >= 0, `Legende (testid "${LEGEND_TESTID}") fehlt komplett.`);
		const block = src.slice(idx, idx + 3000);
		assert.ok(
			block.includes('!'),
			'Die Legende muss den `!`-Marker als Kennzeichen des Warn-Blocks erklären.'
		);
	});

	test('Die Legende ordnet L/M/H den Warnfarben gelb/orange/rot zu', () => {
		const src = read(WEATHER_METRICS_TAB);
		const idx = src.indexOf(LEGEND_TESTID);
		assert.ok(idx >= 0, `Legende (testid "${LEGEND_TESTID}") fehlt komplett.`);
		const block = src.slice(idx, idx + 3000);
		for (const needle of ['gelb', 'orange', 'rot', 'L', 'M', 'H']) {
			assert.ok(
				block.includes(needle),
				`Die L/M/H-Zuordnung der Legende muss "${needle}" nennen.`
			);
		}
	});

	test('Die Legende wird aus Daten gerendert, nicht als starrer Text', () => {
		const src = read(WEATHER_METRICS_TAB);
		const idx = src.indexOf(LEGEND_TESTID);
		assert.ok(idx >= 0, `Legende (testid "${LEGEND_TESTID}") fehlt komplett.`);
		const block = src.slice(idx, idx + 3000);
		assert.ok(
			block.includes('{#each'),
			'Die 9 Kürzel müssen über die Backend-Katalog-Daten iteriert werden ' +
				'({#each …}), nicht als 9 handgeschriebene Zeilen — sonst entsteht ' +
				'genau die zweite Liste, die AC-9 verbietet.'
		);
	});
});

// FB01 (Adversary Scheibe B, HIGH): Die Legende beschreibt ausschliesslich die
// TRIP-Kurzform. Die Vergleichs-SMS (`render_compare_sms`) zeigt amtliche
// Warnungen gar nicht, die Vergleichs-Telegram-Nachricht zeigt sie ungefiltert
// in Langform ohne `!`, Kürzel und Stufe. Im Vergleich-Kontext waere die
// Legende also eine Falschaussage — sie muss dort verschwinden, der Schalter
// selbst bleibt (Non-Regression).
//
// Nachweis per ECHTEM Svelte-5-Compiler-AST (Muster:
// compare_hourly_layout_controls_structure.test.ts), nicht per Datei-Grep: es
// wird geprueft, unter WELCHEN {#if}-Bedingungen ein Testid im Template haengt.

/** Bedingungen (Quelltext) aller {#if}-Bloecke oberhalb des Elements mit `testid`. */
function ifConditionsAbove(ast: any, source: string, testid: string): string[] | null {
	let result: string[] | null = null;
	function visit(node: unknown, conditions: string[]): void {
		if (node === null || typeof node !== 'object' || result) return;
		if (Array.isArray(node)) {
			node.forEach((c) => visit(c, conditions));
			return;
		}
		const n = node as Record<string, any>;
		let next = conditions;
		if (n.type === 'IfBlock' && n.test) {
			next = [...conditions, source.slice(n.test.start, n.test.end)];
		}
		if (n.type === 'RegularElement' || n.type === 'Component') {
			for (const attr of n.attributes ?? []) {
				if (attr.type !== 'Attribute') continue;
				if (attr.name !== 'data-testid' && attr.name !== 'testid') continue;
				const raw = Array.isArray(attr.value)
					? attr.value.map((v: any) => v.raw ?? '{expr}').join('')
					: (attr.value?.raw ?? '{expr}');
				if (raw === testid) {
					result = next;
					return;
				}
			}
		}
		for (const key of Object.keys(n)) {
			if (key === 'parent' || result) continue;
			// Der Alternate-Zweig eines IfBlocks steht NICHT unter dessen Bedingung.
			visit(n[key], key === 'alternate' ? conditions : next);
		}
	}
	visit(ast.fragment, []);
	return result;
}

describe('FB01: Die Legende erscheint nur im Trip-Kontext', () => {
	const source = read(WEATHER_METRICS_TAB);
	const ast = parse(source, { modern: true });

	test('Die Legende haengt an einer Bedingung ueber `context`', () => {
		const conditions = ifConditionsAbove(ast, source, LEGEND_TESTID);
		assert.ok(conditions, `Legende (testid "${LEGEND_TESTID}") im Template nicht gefunden.`);
		const guard = conditions!.find((c) => /\bcontext\b/.test(c));
		assert.ok(
			guard,
			'Die Legende steht unter keiner context-Bedingung — sie wuerde damit auch im ' +
				'Vergleich gerendert, wo sie die tatsaechlich versendeten Nachrichten ' +
				`falsch beschreibt. Gefundene Bedingungen: ${JSON.stringify(conditions)}`
		);
		assert.ok(
			/'vergleich'|"vergleich"|'route'|"route"/.test(guard!),
			`Die context-Bedingung muss den Vergleich-Kontext ausschliessen, ist aber: ${guard}`
		);
	});

	test('Die 9 Kuerzel und der `!`-Hinweis liegen vollstaendig hinter dieser Bedingung', () => {
		// Kein zweiter, ungeschuetzter Legenden-Block: der `!`-Hinweistext und die
		// Kuerzel-Schleife duerfen nur EINMAL vorkommen — innerhalb der Legende.
		const marker = 'beginnt der Warn-Block mit';
		assert.equal(
			source.split(marker).length - 1, 1,
			'Der `!`-Marker-Hinweis kommt mehrfach vor — mindestens eine Kopie liegt ' +
				'ausserhalb des kontextabhaengigen Legenden-Blocks.'
		);
		const legendIdx = source.indexOf(LEGEND_TESTID);
		const markerIdx = source.indexOf(marker);
		assert.ok(
			markerIdx > legendIdx && markerIdx - legendIdx < 3000,
			'Der `!`-Marker-Hinweis steht nicht innerhalb des Legenden-Blocks.'
		);
		assert.equal(
			source.split('h.sms_symbol').length - 1, 1,
			'Die Kuerzel-Schleife kommt mehrfach vor — Legende ggf. dupliziert.'
		);
	});

	test('Der Schalter „Amtliche Warnungen" bleibt in BEIDEN Kontexten (Non-Regression)', () => {
		const conditions = ifConditionsAbove(ast, source, 'report-show-official-alerts');
		assert.ok(conditions, 'Der Schalter (testid "report-show-official-alerts") fehlt komplett.');
		const contextGuard = conditions!.find((c) => /\bcontext\b/.test(c));
		assert.equal(
			contextGuard, undefined,
			'Der Schalter selbst darf NICHT kontextabhaengig ausgeblendet werden — er ist ' +
				`im Vergleich die einzige Heimat von official_alerts_enabled. Bedingung: ${contextGuard}`
		);
		// Und die Vergleich-Aufrufstelle rendert das geteilte Snippet weiterhin.
		const vergleichIdx = source.indexOf('weather-metrics-tab-vergleich');
		const renderIdx = source.indexOf('{@render officialAlertsToggle(', vergleichIdx);
		assert.ok(
			renderIdx > vergleichIdx && renderIdx - vergleichIdx < 3000,
			'Der Vergleich-Zweig rendert das geteilte officialAlertsToggle-Snippet nicht mehr.'
		);
	});
});

describe('AC-9: Kürzel kommen aus dem Backend, nicht aus einer zweiten Liste', () => {
	test('Der Backend-Katalog wird ans Frontend ausgeliefert', () => {
		// Der Transportweg ist bewusst offen (bestehender Katalog-Endpunkt
		// erweitern ODER neuer read-only Endpunkt) — geprüft wird nur, DASS eine
		// Auslieferungs-Schicht den Katalog liest.
		const layers = ['src/app', 'src/api', 'api', 'internal'];
		const hits: string[] = [];
		for (const layer of layers) {
			const dir = join(REPO_ROOT, ...layer.split('/'));
			let files: string[] = [];
			try {
				files = collect(dir);
			} catch {
				continue;
			}
			for (const f of files) {
				const src = read(f);
				if (src.includes('hazard_symbols') || src.includes('HAZARD_SMS_SYMBOLS')) {
					hits.push(f);
				}
			}
		}
		assert.ok(
			hits.length > 0,
			'Keine API-/Auslieferungs-Schicht liest hazard_symbols.py — der Katalog ' +
				'erreicht das Frontend gar nicht, die Legende könnte ihn also nur ' +
				'hartkodiert anzeigen (genau das verbietet AC-9).'
		);
	});

	test('Kein Frontend-Quelltext führt eine eigene Hazard-Kürzel-Liste', () => {
		const catalog = backendHazardCatalog();
		const hazards = Object.keys(catalog);
		const offenders: string[] = [];
		for (const file of frontendSources()) {
			const src = read(file);
			const known = hazards.filter((h) => src.includes(`'${h}'`) || src.includes(`"${h}"`));
			if (known.length < 3) continue; // keine Katalog-artige Aufzählung
			const withSymbol = known.filter((h) => {
				const s = catalog[h];
				return src.includes(`'${s}'`) || src.includes(`"${s}"`);
			});
			if (withSymbol.length >= 3) offenders.push(`${file} (${withSymbol.join(', ')})`);
		}
		assert.deepEqual(
			offenders, [],
			'Diese Frontend-Dateien führen eine zweite, hartkodierte Zuordnung ' +
				`Gefahrenart -> Kürzel:\n${offenders.join('\n')}\n` +
				'Die Kürzel müssen aus dem Backend-Katalog stammen (AC-9).'
		);
	});

	test('Jede SMS-schwellenwertfähige Metrik zeigt ihr SMS-Kürzel', () => {
		const src = read(WEATHER_METRICS_TAB);
		assert.ok(
			src.includes('sms_symbol') || src.includes('smsSymbol'),
			'Die 7 schwellenwertfähigen Metriken müssen ihr SMS-Kürzel aus dem ' +
				'Backend-Metrik-Katalog anzeigen (Feld `sms_symbol` je Metrik, ' +
				`Spec Abschnitt 5a): ${SMS_THRESHOLD_METRIC_IDS.join(', ')}.`
		);
	});
});

/** Rekursive Dateiliste für Backend-Verzeichnisse (.py/.go). */
function collect(dir: string, acc: string[] = []): string[] {
	for (const entry of readdirSync(dir)) {
		if (entry === '__pycache__' || entry === 'node_modules') continue;
		const full = join(dir, entry);
		if (statSync(full).isDirectory()) collect(full, acc);
		else if (/\.(py|go)$/.test(entry)) acc.push(full);
	}
	return acc;
}
