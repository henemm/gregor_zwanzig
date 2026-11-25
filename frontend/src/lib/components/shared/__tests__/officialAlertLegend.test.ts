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

// #2654 (i18n F5): Wortlaut steht im Katalog — die Ratsche liest den Quelltext mit eingesetzten de-Werten.
import { quelleMitKatalog } from '../../../i18n/__tests__/quelleMitKatalog.ts';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { parse } from 'svelte/compiler';

const here = dirname(fileURLToPath(import.meta.url));
const SHARED_DIR = join(here, '..');
// __tests__ -> shared -> components -> lib -> src -> frontend -> repo
const REPO_ROOT = join(here, '..', '..', '..', '..', '..', '..');
const FRONTEND_SRC = join(REPO_ROOT, 'frontend', 'src');
const HAZARD_SYMBOLS_PY = join(REPO_ROOT, 'src', 'output', 'tokens', 'hazard_symbols.py');

const LEGEND_TESTID = 'official-alerts-symbol-legend';

// Die 7 SMS-schwellenwertfähigen Metriken (Spec Abschnitt 5a). Quelle der
// Kürzel ist `SMS_SYMBOL_BY_METRIC` in src/output/renderers/sms_trip.py.
const SMS_THRESHOLD_METRIC_IDS = [
	'precipitation', 'rain_probability', 'wind', 'gust', 'thunder',
	'snow_depth', 'snowfall_limit'
];

function read(path: string): string {
	return quelleMitKatalog(readFileSync(path, 'utf-8'));
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
	// 12 seit #1441 (avalanche_bulletin, Lawinen-Lagebericht).
	assert.equal(
		Object.keys(catalog).length, 12,
		`Backend-Katalog muss 12 Gefahrenarten führen, gelesen: ${JSON.stringify(catalog)}`
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

// #3297/#3020: Faelle gegen WeatherMetricsTab.svelte entfallen (Datei geloescht).

// FB01 (Adversary Scheibe B, HIGH — abgeloest durch Issue #1332, PO-Korrektur
// 2026-07-23): urspruenglich beschrieb die Legende ausschliesslich die
// TRIP-Kurzform, weil die Vergleichs-SMS amtliche Warnungen gar nicht zeigte
// und die Vergleichs-Telegram-Nachricht sie ungefiltert/kuerzelfrei zeigte --
// die Legende waere im Vergleich-Kontext eine Falschaussage gewesen.
// Mit #1332 zeigt sowohl die Vergleichs-SMS (`!`-Kuerzel-Marker, ab orange)
// als auch das Vergleichs-Telegram (ausgeschriebener Warn-Block wie das
// Trip-Telegram) dasselbe Format wie der Trip-Pfad -- die Legende beschreibt
// jetzt beide Kontexte korrekt und steht deshalb OHNE Kontext-Schalter,
// gebunden nur an den geladenen Kuerzel-Katalog (`smsSymbols`).
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

/** Bedingungen (Quelltext) aller {#if}-Bloecke oberhalb des ERSTEN
 *  `{@render <name>(...)}`-Aufrufs im Template. `null`, wenn es keinen gibt.
 *  Issue #1360: ersetzt eine brueckige Zeichen-Abstands-Naeherung. */
function renderTagConditions(ast: any, source: string, snippetName: string): string[] | null {
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
		if (n.type === 'RenderTag') {
			const raw = source.slice(n.start, n.end);
			if (raw.includes(snippetName + '(')) {
				result = next;
				return;
			}
		}
		for (const key of Object.keys(n)) {
			if (key === 'parent' || result) continue;
			visit(n[key], key === 'alternate' ? conditions : next);
		}
	}
	visit(ast.fragment, []);
	return result;
}

// #3297/#3020: FB01/F003 lasen WeatherMetricsTab.svelte (Datei geloescht).

// F003 (Adversary-Fund, Fix-Loop 2 / #1332): die Legende haengt an
// `smsSymbols` (s. FB01 oben), aber `smsSymbols` wurde ausschliesslich in
// load() gesetzt, und load() laeuft nur im route-$effect (context ===
// 'route'). Im Vergleich-Kontext blieb `smsSymbols` deshalb IMMER null —
// die Legende erschien nie, obwohl der {#if}-Guard laengst context-frei war.
// Geprueft wird per Instance-Script-AST, dass es einen eigenen Ladepfad
// (`$effect`, an eine 'vergleich'-Bedingung gekoppelt) gibt.

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
