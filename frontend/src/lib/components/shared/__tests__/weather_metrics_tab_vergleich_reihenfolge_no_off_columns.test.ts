// Issue #1719 Scheibe S3 — Adversary-Fund F001 (BROKEN, verifiziert nach GREEN,
// 2026-08-11): "Aus ist ein Zustand" (ADR-0050 Regel 4) gilt ausschliesslich
// fuer den Trip-Kanal-Reiter (WeatherMetricsTab.svelte, route-Kontext). Die
// DRITTE `WeatherV2Reihenfolge`-Einbettung — die Vergleichs-Uebersicht
// (`{#if context === 'vergleich'} ... {/if}`-Zweig derselben Datei,
// `WeatherMetricsTab.svelte:1178`) — arbeitet auf einem flachen Array ohne
// Kanal-Ebene und hat bereits einen funktionierenden Rueckweg (Checkbox
// darueber). `offColumns`/`onRestore` sind OPTIONALE Props ohne Vorgabewert
// (Spec Abschnitt 1) — die Naht ist die PROP-ANWESENHEIT, nicht ein
// `context`-String. Werden sie hier durchgereicht, entsteht eine ungewollte
// Aus-Gruppe im Ortsvergleich (AC-13-Verstoss).
//
// Die beiden anderen Vergleichs-Einbettungen (CompareOutlookLayoutControls,
// CompareHourlyLayoutControls) haben denselben Waechter in
// compare_outlook_metric_selection_structure.test.ts bzw.
// compare_hourly_layout_controls_structure.test.ts — drei Einbettungen, drei
// Waechter (Adversary-Vorgabe).
//
// Grund fuer AST statt DOM: dieses Repo hat kein vitest/jsdom (package.json
// "test": node --test). Der Test parst WeatherMetricsTab.svelte mit dem
// ECHTEN Svelte-5-Compiler. Die Positions-Eingrenzung auf den vergleich-Zweig
// uebernimmt das Muster aus weatherMetricsTabSharing.test.ts (String-Position
// der Markup-Verzweigung, AST-Knoten per `start`-Offset zugeordnet) — die
// Datei hat ZWEI WeatherV2Reihenfolge-Aufrufe (vergleich + route), ohne
// Eingrenzung waere ein Treffer im route-Zweig (der offColumns zu Recht
// traegt) ein falscher Alarm.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/weather_metrics_tab_vergleich_reihenfolge_no_off_columns.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

const here = dirname(fileURLToPath(import.meta.url));
const SHARED_FILE = join(here, '..', 'WeatherMetricsTab.svelte');

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

function sharedExists(): boolean {
	try {
		readFileSync(SHARED_FILE, 'utf-8');
		return true;
	} catch {
		return false;
	}
}

describe('AC-13 (Issue #1719 S3, Adversary-Fund F001): Vergleichs-Uebersicht bekommt WEDER offColumns NOCH onRestore', () => {
	test(
		'WeatherV2Reihenfolge im vergleich-Zweig von WeatherMetricsTab.svelte traegt keine der beiden Props',
		{ skip: !sharedExists() },
		() => {
			const code = readFileSync(SHARED_FILE, 'utf-8');
			const markupStart = code.indexOf("{#if context === 'vergleich'}");
			const routeStart = code.indexOf('\n{:else}', markupStart);
			assert.ok(markupStart > 0 && routeStart > markupStart, 'Markup-Verzweigung nicht gefunden — Test ist blind geworden.');

			const ast = parse(code, { modern: true });
			const alleReihenfolgeAufrufe = findComponentsNamed(ast.fragment, 'WeatherV2Reihenfolge');
			const vergleichsAufrufe = alleReihenfolgeAufrufe.filter(
				(n) => n.start >= markupStart && n.start < routeStart
			);
			assert.equal(
				vergleichsAufrufe.length,
				1,
				`Erwartet genau einen WeatherV2Reihenfolge-Aufruf im vergleich-Zweig, gefunden ${vergleichsAufrufe.length} ` +
					`(insgesamt ${alleReihenfolgeAufrufe.length} in der Datei) — Test ist blind geworden oder die Struktur hat sich geaendert.`
			);
			if (vergleichsAufrufe.length !== 1) return;

			const row = vergleichsAufrufe[0];
			assert.equal(
				findAttr(row, 'offColumns'),
				undefined,
				'AC-13 FAIL: die Vergleichs-Uebersicht uebergibt jetzt `offColumns` an WeatherV2Reihenfolge — ' +
					'das erzeugt eine Aus-Gruppe im Ortsvergleich, wo ADR-0050 Regel 4 nicht gilt.'
			);
			assert.equal(
				findAttr(row, 'onRestore'),
				undefined,
				'AC-13 FAIL: die Vergleichs-Uebersicht uebergibt jetzt `onRestore` an WeatherV2Reihenfolge — ' +
					'siehe offColumns-Befund oben, dieselbe Naht.'
			);
		}
	);
});
