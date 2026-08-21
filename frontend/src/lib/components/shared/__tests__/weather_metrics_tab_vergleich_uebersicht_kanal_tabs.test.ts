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

/**
 * Fix-Loop Adversary-Fund F001 (HIGH): `findAttr` belegt nur die ANWESENHEIT
 * eines Attributs. Die Mutation `hasLabelColumn={false}` -> `{true}` lief
 * dadurch durch alle Frontend-Tests gruen — die Kappungs-Aussage haette dann
 * "N Spalten (Label + Metriken)" behauptet, obwohl es keine Label-Spalte gibt.
 *
 * Liefert den TATSAECHLICHEN Wert eines boolean-Attributs:
 *   - `undefined`          Attribut fehlt
 *   - `true` / `false`     `{true}` / `{false}` (Literal)
 *   - `true`               Kurzform `<C hasLabelColumn />` (Svelte-Semantik:
 *                          ein Attribut ohne Wert ist `true`)
 *   - String               alles andere (Identifier, Aufruf, Text) — der Text
 *                          landet in der Fehlermeldung, damit ein spaeterer
 *                          Umbau nicht still als "kein false" durchrutscht.
 */
function boolAttrValue(node: any, name: string): true | false | string | undefined {
	const attr = findAttr(node, name);
	if (attr === undefined) return undefined;
	const value = attr.value;
	if (value === true) return true;
	if (value?.type === 'ExpressionTag') {
		const expr = value.expression;
		if (expr?.type === 'Literal') {
			if (expr.value === true) return true;
			if (expr.value === false) return false;
			return `Literal(${expr.raw})`;
		}
		return `Ausdruck(${expr?.type})`;
	}
	if (Array.isArray(value)) {
		return `Text("${value.map((t: any) => t.raw ?? t.data ?? '').join('')}")`;
	}
	return `unbekannt(${value?.type})`;
}

/** Name des Identifiers, der als `name={IDENT}` uebergeben wird (sonst eine
 *  beschreibende Zeichenkette bzw. `undefined`, wenn das Attribut fehlt). */
function identAttrValue(node: any, name: string): string | undefined {
	const attr = findAttr(node, name);
	if (attr === undefined) return undefined;
	const expr = attr.value?.type === 'ExpressionTag' ? attr.value.expression : undefined;
	if (expr?.type === 'Identifier') return expr.name;
	if (expr?.type === 'Literal') return `Literal(${expr.raw})`;
	return `Ausdruck(${expr?.type ?? attr.value?.type ?? 'Text'})`;
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
			// Label-Spalte mitzaehlen (Gegenprobe M6). Geprueft wird der WERT,
			// nicht die Anwesenheit (Fix-Loop F001).
			assert.equal(
				boolAttrValue(layoutTabs[0], 'hasLabelColumn'),
				false,
				'AC-S8-13 FAIL: der Uebersichts-LayoutTab uebergibt `hasLabelColumn` nicht als ' +
					'`{false}` — die Uebersicht zaehlt Metriken als ZEILEN; jeder andere Wert laesst ' +
					'den Kappungs-Hinweis "N Spalten (Label + Metriken)" behaupten (ltCapNoteText, ' +
					'ltChannels.ts:147), obwohl es dort keine Label-Spalte gibt.'
			);
			// Fix B: die SMS-Zeichengrenze des VERGLEICHSPFADS (153), nicht die
			// Trip-Konstante (160) — Gegenprobe M7. Auch hier der WERT: ein
			// Tausch auf SMS_TRIP_CHAR_LIMIT haette die Anwesenheitspruefung
			// unveraendert bestanden und den Widerspruch Badge/Hinweis (160 vs.
			// 153) wieder eingefuehrt, den Fix B gerade beseitigt hat.
			assert.equal(
				identAttrValue(layoutTabs[0], 'smsCharLimit'),
				'SMS_COMPARE_CHAR_LIMIT',
				'AC-S8-12 FAIL: der Uebersichts-LayoutTab speist `smsCharLimit` nicht aus ' +
					'SMS_COMPARE_CHAR_LIMIT (153, channel_layout.py:45-54) — Badge, Ueberlauf-Chip ' +
					'und Kappungs-Hinweis nennten dann den Trip-Wert 160.'
			);
		}
	);

	// Fix-Loop Adversary-Fund F001 (HIGH): der Trip-Aufruf uebergibt seit
	// Scheibe 8 ebenfalls `hasLabelColumn={false}` — vorher war das der aus
	// `context` abgeleitete Default (route -> false). Die Ableitung ist mit
	// dieser Scheibe entfallen; ohne Waechter waere ein stiller Wechsel auf
	// `{true}` eine Regression im Trip-Editor, die kein Test bemerkt.
	test(
		'auch der Trip-Aufruf (route-Zweig) zaehlt Metriken als ZEILEN: hasLabelColumn={false}',
		{ skip: !exists(SHARED_FILE) },
		() => {
			const code = readFileSync(SHARED_FILE, 'utf-8');
			const markupStart = code.indexOf("{#if context === 'vergleich'}");
			const routeStart = code.indexOf('\n{:else}', markupStart);
			assert.ok(
				markupStart > 0 && routeStart > markupStart,
				'Markup-Verzweigung nicht gefunden — Test ist blind geworden.'
			);
			const ast = parse(code, { modern: true });
			const layoutTabs = findComponentsNamed(ast.fragment, 'LayoutTab').filter(
				(n) => n.start >= routeStart
			);
			assert.equal(
				layoutTabs.length,
				1,
				`Erwartet genau EINEN LayoutTab-Aufruf im route-Zweig, gefunden ${layoutTabs.length} — ` +
					'Test ist blind geworden oder die Struktur hat sich geaendert.'
			);
			if (layoutTabs.length !== 1) return;
			assert.equal(
				boolAttrValue(layoutTabs[0], 'hasLabelColumn'),
				false,
				'REGRESSION: der Trip-LayoutTab uebergibt `hasLabelColumn` nicht mehr als `{false}`. ' +
					'Die Trip-Kappung zaehlt reine Metriken (Fresh-Eyes-Fund #1232-3b, ' +
					'WeatherMetricsTab.svelte:1422-1427); jeder andere Wert verschiebt die Kapplinie ' +
					'gegen den Ueberlauf-Chip.'
			);
		}
	);
});

// ⚠️ AC-S8-14 (b) TEILWEISE ABGELOEST durch #1848 A3 (PO-Freigabe 2026-08-21).
//
// Die Zusicherung lautete: "Ausblick UND Stundenverlauf uebergeben WEDER
// offColumns NOCH onRestore — Scheibe 8 gibt ausdruecklich nur der
// Uebersichtstabelle eine Kanal-Ebene; hier entstuende eine Aus-Gruppe ohne
// Kanal-Reiter, also ohne Bedeutung."
//
// Fuer den AUSBLICK trifft die Begruendung seit A3 nicht mehr zu: er hat jetzt
// eine Grundauswahl-Bindung (ADR-0050 Regeln 1/2, loest ADR-0053 Punkt 1 ab),
// und seine Kaestchenliste — der bisherige Rueckweg fuer eine abgewaehlte
// Groesse — ist ersatzlos entfallen (Block A, Issue #2029). Ohne "Aus"-Gruppe
// gaebe es dort GAR KEINEN Rueckweg mehr (ADR-0050 Regel 4). Dieselbe
// Ablösung betrifft AC-13 aus fix_1719_s3, s.
// compare_outlook_metric_selection_structure.test.ts.
//
// Der STUNDENVERLAUF bleibt unveraendert: er hat weiterhin seine eigene
// Kaestchenliste und damit einen funktionierenden Rueckweg — dort waere eine
// zweite Aus-Gruppe genau die bedeutungslose Doppelung, die S8 ausschloss.
describe('AC-S8-14 (b): der Stundenverlauf bleibt ohne Kanal-Ebene', () => {
	for (const [label, file] of [
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

	test('der Ausblick uebergibt offColumns UND onRestore (#1848 A3, umgedreht)', () => {
		const ast = parse(readFileSync(OUTLOOK_FILE, 'utf-8'), { modern: true });
		const rows = findComponentsNamed(ast.fragment, 'WeatherV2Reihenfolge');
		assert.equal(
			rows.length,
			1,
			`Erwartet genau einen WeatherV2Reihenfolge-Aufruf im Ausblick, gefunden ${rows.length}.`
		);
		if (rows.length !== 1) return;
		assert.ok(
			findAttr(rows[0], 'offColumns') && findAttr(rows[0], 'onRestore'),
			'#1848 A3 FAIL: der Ausblick uebergibt kein `offColumns`/`onRestore` mehr. Ohne die ' +
				'abgeschaffte Kaestchenliste (Block A, #2029) gaebe es keinen Weg, eine abgewaehlte ' +
				'Groesse zurueckzuholen (ADR-0050 Regel 4).'
		);
	});
});
