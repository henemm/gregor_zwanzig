// Issue #1703 Scheibe 8 — UMGEDREHTE Invariante (AC-S8-14, Gegenprobe M9).
//
// Vorgaenger-Fassung dieser Datei (#1719 S3, Adversary-Fund F001):
// `weather_metrics_tab_vergleich_reihenfolge_no_off_columns.test.ts` sicherte,
// dass die Vergleichs-UEBERSICHT WEDER `offColumns` NOCH `onRestore` an
// `WeatherV2Reihenfolge` durchreicht — damals richtig: die Uebersicht arbeitete
// auf einem flachen Array ohne Kanal-Ebene und hatte ihren Rueckweg ueber die
// Grundauswahl-Checkbox darueber.
//
// Mit Scheibe 8 bekommt genau diese Einbettung Kanal-Reiter (E-Mail/Telegram/
// SMS) und damit eine echte Kanal-Ebene: eine im SMS-Reiter abgewaehlte Metrik
// MUSS dort sichtbar und wieder einschaltbar bleiben (ADR-0050 Regel 4, "Aus
// ist ein Zustand"). Die alte Zusicherung waere ab jetzt die FALSCHE.
//
// Die Naht bleibt dieselbe wie in S3: die PROP-ANWESENHEIT, nicht ein
// `context`-String (`offColumns`/`onRestore` sind optionale Props OHNE
// Vorgabewert, WeatherV2Reihenfolge.svelte:43-44). Deshalb prueft diese Datei
// beide Richtungen an EINER Stelle:
//   1. die Uebersicht (vergleich-Zweig von WeatherMetricsTab.svelte) TRAEGT beide,
//   2. Ausblick und Stundenverlauf tragen sie WEITERHIN NICHT (AC-S8-14).
//
// Punkt 2 wird zusaetzlich von den beiden unveraenderten Geschwister-Waechtern
// `compare_outlook_metric_selection_structure.test.ts` und
// `compare_hourly_layout_controls_structure.test.ts` bewacht. Die Doppelung ist
// Absicht (Gegenprobe M9): wer diese Datei ersatzlos loescht, statt sie
// umzuschreiben, wuerde sonst die Abgrenzungs-Zusicherung mit ihr verlieren.
//
// Grund fuer AST statt DOM: dieses Repo hat kein vitest/jsdom (package.json
// "test": node --test). Der Test parst die Komponenten mit dem ECHTEN
// Svelte-5-Compiler. Die Positions-Eingrenzung auf den vergleich-Zweig
// uebernimmt das Muster aus weatherMetricsTabSharing.test.ts (String-Position
// der Markup-Verzweigung, AST-Knoten per `start`-Offset zugeordnet) — die
// Datei hat ZWEI WeatherV2Reihenfolge-Aufrufe (vergleich + route), ohne
// Eingrenzung waere ein Treffer im route-Zweig ein falscher Beleg.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/weather_metrics_tab_vergleich_uebersicht_kanal_tabs.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

const here = dirname(fileURLToPath(import.meta.url));
const SHARED_FILE = join(here, '..', 'WeatherMetricsTab.svelte');
const OUTLOOK_FILE = join(here, '..', 'CompareOutlookLayoutControls.svelte');
const HOURLY_FILE = join(here, '..', 'CompareHourlyLayoutControls.svelte');

function findAttr(node: any, name: string): any {
	return (node?.attributes ?? []).find((a: any) => a.type === 'Attribute' && a.name === name);
}

function findComponentsNamed(subtree: unknown, name: string): any[] {
	const found: any[] = [];
	function visit(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visit);
			return;
		}
		const n = node as Record<string, any>;
		if (n.type === 'Component' && n.name === name) found.push(n);
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(subtree);
	return found;
}

function exists(path: string): boolean {
	try {
		readFileSync(path, 'utf-8');
		return true;
	} catch {
		return false;
	}
}

/** Der EINE WeatherV2Reihenfolge-Aufruf im vergleich-Zweig (Uebersicht). */
function uebersichtsAufruf(): any {
	const code = readFileSync(SHARED_FILE, 'utf-8');
	const markupStart = code.indexOf("{#if context === 'vergleich'}");
	const routeStart = code.indexOf('\n{:else}', markupStart);
	assert.ok(
		markupStart > 0 && routeStart > markupStart,
		'Markup-Verzweigung nicht gefunden — Test ist blind geworden.'
	);

	const ast = parse(code, { modern: true });
	const alle = findComponentsNamed(ast.fragment, 'WeatherV2Reihenfolge');
	const imVergleich = alle.filter((n) => n.start >= markupStart && n.start < routeStart);
	assert.equal(
		imVergleich.length,
		1,
		`Erwartet genau einen WeatherV2Reihenfolge-Aufruf im vergleich-Zweig, gefunden ${imVergleich.length} ` +
			`(insgesamt ${alle.length} in der Datei) — Test ist blind geworden oder die Struktur hat sich geaendert.`
	);
	return imVergleich[0];
}

describe('AC-S8-14 (a): die Vergleichs-UEBERSICHT traegt jetzt offColumns UND onRestore', () => {
	test(
		'der WeatherV2Reihenfolge-Aufruf im vergleich-Zweig uebergibt beide Props',
		{ skip: !exists(SHARED_FILE) },
		() => {
			const row = uebersichtsAufruf();
			assert.notEqual(
				findAttr(row, 'offColumns'),
				undefined,
				'AC-S8-14 FAIL: die Vergleichs-Uebersicht uebergibt KEIN `offColumns` mehr an ' +
					'WeatherV2Reihenfolge — eine im Kanal-Reiter abgewaehlte Metrik verschwindet dann ' +
					'spurlos aus der Liste statt in die Aus-Gruppe zu wandern (ADR-0050 Regel 4).'
			);
			assert.notEqual(
				findAttr(row, 'onRestore'),
				undefined,
				'AC-S8-14 FAIL: die Vergleichs-Uebersicht uebergibt KEIN `onRestore` mehr — ohne ' +
					'Rueckweg ist die Aus-Gruppe eine Sackgasse (AC-S8-5).'
			);
		}
	);

	test(
		'die Uebersicht haengt im geteilten LayoutTab-Organism (Kanal-Reiter), nicht mehr nackt in der Card',
		{ skip: !exists(SHARED_FILE) },
		() => {
			const code = readFileSync(SHARED_FILE, 'utf-8');
			const markupStart = code.indexOf("{#if context === 'vergleich'}");
			const routeStart = code.indexOf('\n{:else}', markupStart);
			const ast = parse(code, { modern: true });
			const layoutTabs = findComponentsNamed(ast.fragment, 'LayoutTab').filter(
				(n) => n.start >= markupStart && n.start < routeStart
			);
			assert.equal(
				layoutTabs.length,
				1,
				`AC-S8-12/AC-S8-13 FAIL: erwartet genau EINEN LayoutTab-Aufruf im vergleich-Zweig, ` +
					`gefunden ${layoutTabs.length} — ohne ihn gibt es keine Kanal-Reiter und keine ` +
					`Kappungs-Aussage fuer die Uebersicht.`
			);
			if (layoutTabs.length !== 1) return;

			// Fix A: Metriken sind ZEILEN — die Kappungs-Zaehlung darf keine
			// Label-Spalte mitzaehlen (Gegenprobe M6).
			const hasLabelColumn = findAttr(layoutTabs[0], 'hasLabelColumn');
			assert.notEqual(
				hasLabelColumn,
				undefined,
				'AC-S8-13 FAIL: der Uebersichts-LayoutTab uebergibt `hasLabelColumn` nicht explizit — ' +
					'ein kontextabgeleiteter Default wuerde hier "N Spalten (Label + Metriken)" behaupten.'
			);
			// Fix B: die SMS-Zeichengrenze des VERGLEICHSPFADS (153), nicht die
			// Trip-Konstante (160) — Gegenprobe M7.
			assert.notEqual(
				findAttr(layoutTabs[0], 'smsCharLimit'),
				undefined,
				'AC-S8-12 FAIL: der Uebersichts-LayoutTab uebergibt `smsCharLimit` nicht — Badge und ' +
					'Kappungs-Hinweis fielen still auf den Trip-Wert 160 zurueck.'
			);
		}
	);
});

describe('AC-S8-14 (b): Ausblick und Stundenverlauf bleiben ohne Kanal-Ebene', () => {
	for (const [label, file] of [
		['Ausblick (CompareOutlookLayoutControls)', OUTLOOK_FILE],
		['Stundenverlauf (CompareHourlyLayoutControls)', HOURLY_FILE]
	] as [string, string][]) {
		test(
			`${label} uebergibt WEDER offColumns NOCH onRestore`,
			{ skip: !exists(file) },
			() => {
				const ast = parse(readFileSync(file, 'utf-8'), { modern: true });
				const rows = findComponentsNamed(ast.fragment, 'WeatherV2Reihenfolge');
				assert.equal(
					rows.length,
					1,
					`Erwartet genau einen WeatherV2Reihenfolge-Aufruf in ${label}, gefunden ${rows.length} — ` +
						'Test ist blind geworden oder die Struktur hat sich geaendert.'
				);
				if (rows.length !== 1) return;
				assert.equal(
					findAttr(rows[0], 'offColumns'),
					undefined,
					`AC-S8-14 FAIL: ${label} uebergibt jetzt \`offColumns\` — Scheibe 8 gibt AUSDRUECKLICH ` +
						'nur der Uebersichtstabelle eine Kanal-Ebene; hier entstuende eine Aus-Gruppe ohne ' +
						'Kanal-Reiter, also ohne Bedeutung.'
				);
				assert.equal(
					findAttr(rows[0], 'onRestore'),
					undefined,
					`AC-S8-14 FAIL: ${label} uebergibt jetzt \`onRestore\` — siehe offColumns-Befund oben, ` +
						'dieselbe Naht.'
				);
			}
		);
	}
});
