// Struktur-Waechter um den Ausblick-Block (CompareOutlookLayoutControls.svelte).
//
// HERKUNFT: Issue #1406 Scheibe A (Epic #1372 S4b Scheibe 2, Dach #1374),
// fortgeschrieben in #1848 A2.
//
// 🔴 STAND #1848 A3 (Block A, Issue #2029): die Kaestchenliste des Ausblicks
// ist ABGESCHAFFT. Damit entfallen die Zusicherungen dieser Datei, die ihre
// Existenz und ihr Innenleben bewachten (AC-1 `{#each groupCompareCatalog(
// catalog)}`, AC-2/AC-3/AC-4 „ein Kaestchen je Groesse, geschluesselt ueber
// group.metric_id", AC-8 „die Ausblick-Zeile traegt ein eigenes Testid-
// Praefix") — sie pruefen ein Verhalten, das die Spec ersatzlos gestrichen
// hat, und stehen im direkten Widerspruch zu
// `outlook_erbt_grundauswahl_structure.test.ts` (AC-1/AC-2/AC-12), das ihre
// ABWESENHEIT zusichert. Nach der Kern-Testregel (CLAUDE.md: „sofort fixen
// ODER loeschen, wenn er veraltetes Verhalten prueft") sind sie entfernt,
// nicht auskommentiert.
//
// WAS BLEIBT — beides ist von Block A unberuehrt:
//   1. der Reihenfolge-/„Aus"-Block (WeatherV2Reihenfolge), jetzt MIT
//      offColumns/onRestore (AC-13-Abloesung, s. u.);
//   2. die `testidPrefix`-Zusicherungen an AggregationMetricRow.svelte — die
//      Komponente wird von der Vergleichs-UEBERSICHT weiterhin gemountet, und
//      ihr Praefix-Vertrag (#1411/#1406, Adversary F001) gilt unveraendert.
//
// Spec: docs/specs/modules/feat_1848_a3_ausblick_erbt_grundauswahl.md
//       docs/specs/modules/feat_1406a_ausblick_geteiltes_element.md (Herkunft)
//
// Grund fuer AST statt DOM: dieses Repo hat kein vitest/jsdom (package.json
// "test": node --test). Der Test parst die betroffenen Komponenten mit dem
// ECHTEN Svelte-5-Compiler und inspiziert den Template-/Instance-Script-AST
// statt eines verbotenen Dateiinhalt-Vergleichs.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/compare_outlook_metric_selection_structure.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

const here = dirname(fileURLToPath(import.meta.url));
const OUTLOOK_COMPONENT = join(here, '..', 'CompareOutlookLayoutControls.svelte');
const AGGREGATION_ROW_COMPONENT = join(
	here, '..', 'weather-metrics-tab', 'AggregationMetricRow.svelte'
);
const OVERVIEW_COMPONENT = join(here, '..', 'WeatherMetricsTab.svelte');

function parseComponent(path: string): any {
	const src = readFileSync(path, 'utf-8');
	return parse(src, { modern: true });
}

// ─── generische AST-Helfer (Vorbild: compare_hourly_layout_controls_structure.test.ts) ───

/** Sammelt alle `Component`-Knoten mit gegebenem Namen im Subtree (Usage-Stelle,
 *  NICHT die Zieldatei — Svelte inlined fremde Komponenten nicht in den AST). */
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

function findAttr(node: any, name: string): any {
	return (node?.attributes ?? []).find(
		(a: any) => a.type === 'Attribute' && a.name === name
	);
}

/** Sammelt JEDES `Attribute`-Attribut mit gegebenem Namen irgendwo im Subtree,
 *  unabhaengig vom Element/Zweig, in dem es steht — Gegenprobe zu `findAttr`
 *  (nur EIN Element) fuer den vollstaendigen Testid-Nachweis (AC-8 F001,
 *  Adversary-Befund: das `<td>` (Zeile 62) wurde beim ersten Umbau uebersehen,
 *  weil der Test nur benannte Elemente einzeln pruefte statt JEDES
 *  `data-testid` im Template). */
function findAllAttributesNamed(subtree: unknown, name: string): any[] {
	const found: any[] = [];
	function visit(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visit);
			return;
		}
		const n = node as Record<string, any>;
		if (n.type === 'Attribute' && n.name === name) found.push(n);
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(subtree);
	return found;
}

/** Laeuft ueber ALLE Ausdruecke eines Attributs (ExpressionTag, Template-
 *  Literal-Interpolation, Svelte-native `"prefix-{expr}"`-Mischform) und ruft
 *  `visit` je Ausdrucks-Wurzel auf. Gemeinsame Grundlage der Ausdrucks-Helfer
 *  unten — die Notation bleibt damit ueberall gleich egal. */
function forEachAttributeExpression(attr: any, visit: (expr: unknown) => void): void {
	if (!attr) return;
	const value = attr.value;
	if (Array.isArray(value)) {
		for (const part of value) {
			if (part?.type === 'ExpressionTag') visit(part.expression);
		}
	} else if (value?.type === 'ExpressionTag') {
		visit(value.expression);
	}
}

/** Prueft rekursiv, ob IRGENDWO im Ausdrucks-Subtree eines Attributs (egal ob
 *  `{expr}`-ExpressionTag, Template-Literal-Interpolation oder Svelte-native
 *  `"prefix-{expr}"`-Mischform) ein `Identifier` mit `identifierName`
 *  vorkommt. Formunabhaengig — die Spec nennt die genaue Notation bewusst
 *  Implementierungsdetail. */
function attributeReferencesIdentifier(attr: any, identifierName: string): boolean {
	if (!attr) return false;
	let hit = false;
	function visitExpr(node: unknown): void {
		if (hit || node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visitExpr);
			return;
		}
		const n = node as Record<string, any>;
		if (n.type === 'Identifier' && n.name === identifierName) {
			hit = true;
			return;
		}
		for (const key of Object.keys(n)) {
			if (key === 'parent' || key === 'loc') continue;
			visitExpr(n[key]);
		}
	}
	forEachAttributeExpression(attr, visitExpr);
	return hit;
}

/** Instance-Script-AST einer Komponente (Vorbild: officialAlertLegend.test.ts
 *  F003, `ast.instance.content.body`). */
function instanceBody(ast: any): any[] {
	return (ast?.instance?.content?.body as any[]) ?? [];
}

// ═══════════════════════════════════════════════════════════════════════════
// AC-5 (primaryColumns/onRemove/onDndReorder: REGRESSIONSSCHUTZ, bleibt GRUEN)
// + AC-13-Abloesung (#1848 A3): offColumns/onRestore MUESSEN jetzt gesetzt
// sein — umgedreht gegenueber dem urspruenglichen #1719-S3-Waechter.
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-5 [primaryColumns/onRemove/onDndReorder REGRESSIONSSCHUTZ] + AC-1/AC-7 [#1848 A3, offColumns/onRestore]: Reihenfolge-/„Aus"-Block (WeatherV2Reihenfolge)', () => {
	test('WeatherV2Reihenfolge wird weiterhin mit primaryColumns/onRemove/onDndReorder aufgerufen, UND jetzt zusaetzlich mit offColumns/onRestore (#1848 A3)', () => {
		// Der primaryColumns/onRemove/onDndReorder-Teil prueft KEIN neues
		// Verhalten: er ist seit #1361 Befund 2/#1368 (`8fc4d210`, live
		// 2026-07-27) gruen und muss es bleiben — der Umbau des Auswahl-Blocks
		// darf den Reihenfolge-Block nicht beschaedigen.
		const ast = parseComponent(OUTLOOK_COMPONENT);
		const rows = findComponentsNamed(ast.fragment, 'WeatherV2Reihenfolge');
		assert.equal(
			rows.length,
			1,
			`REGRESSION: erwartet genau einen WeatherV2Reihenfolge-Aufruf in CompareOutlookLayoutControls.svelte, ` +
				`gefunden ${rows.length}.`
		);
		const row = rows[0];
		const primaryColumnsAttr = findAttr(row, 'primaryColumns');
		const onRemoveAttr = findAttr(row, 'onRemove');
		const onDndReorderAttr = findAttr(row, 'onDndReorder');
		assert.ok(
			primaryColumnsAttr && attributeReferencesIdentifier(primaryColumnsAttr, 'materializedOutlookKeys'),
			'REGRESSION: `primaryColumns` des WeatherV2Reihenfolge-Aufrufs referenziert nicht mehr ' +
				'`materializedOutlookKeys` — der Umbau des Auswahl-Blocks hat den Reihenfolge-Block beruehrt ' +
				'(Nicht-Umfang-Verstoss, AC-5).'
		);
		assert.ok(
			onRemoveAttr && attributeReferencesIdentifier(onRemoveAttr, 'onOutlookRemove'),
			'REGRESSION: `onRemove` des WeatherV2Reihenfolge-Aufrufs wurde veraendert (AC-5 Nicht-Umfang-Verstoss).'
		);
		assert.ok(
			onDndReorderAttr && attributeReferencesIdentifier(onDndReorderAttr, 'handleOutlookDndReorder'),
			'REGRESSION: `onDndReorder` des WeatherV2Reihenfolge-Aufrufs wurde veraendert (AC-5 Nicht-Umfang-Verstoss).'
		);
		// 🔴 AC-13-ABLOESUNG (#1848 A3, PO-Entscheid 2026-08-21): die Begruendung
		// von #1719 S3 -- der Ausblick habe "bereits einen funktionierenden
		// Rueckweg (Checkbox darueber)" -- entfaellt mit A3 Block A: die
		// Kaestchenliste selbst wird abgeschafft (s.
		// outlook_erbt_grundauswahl_structure.test.ts, AC-1/AC-2). Ohne sie
		// gibt es KEIN Kaestchen mehr, ueber das man etwas zurueckholen
		// koennte -- die Aus-Gruppe von WeatherV2Reihenfolge UEBERNIMMT diese
		// Rolle jetzt, exakt wie im Trip-Kanal-Reiter (ADR-0050 Regel 4 gilt ab
		// A3 auch fuer den Ausblick, loest ADR-0053 Punkt 1 ab). Die
		// Zusicherung ist deshalb UMGEDREHT, nicht geloescht: `offColumns`/
		// `onRestore` MUESSEN jetzt gesetzt sein.
		// SPEC: docs/specs/modules/feat_1848_a3_ausblick_erbt_grundauswahl.md
		//   AC-1/AC-7, Mutations-Gegenprobe M-2.
		const offColumnsAttr = findAttr(row, 'offColumns');
		assert.ok(
			offColumnsAttr,
			'AC-1/AC-7 FAIL (#1848 A3): der Ausblick-Aufruf von WeatherV2Reihenfolge ' +
				'uebergibt kein `offColumns` mehr — ohne die abgeschaffte Kaestchenliste ' +
				'(AC-1) waere eine abgewaehlte Groesse nicht mehr zurueckholbar (ADR-0050 ' +
				'Regel 4, loest AC-13 aus fix_1719_s3 ab).'
		);
		const onRestoreAttr = findAttr(row, 'onRestore');
		assert.ok(
			onRestoreAttr,
			'AC-1/AC-7 FAIL (#1848 A3): der Ausblick-Aufruf von WeatherV2Reihenfolge ' +
				'uebergibt kein `onRestore` mehr — dieselbe Naht wie offColumns oben.'
		);
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// AC-8: unterscheidbare data-testid zwischen Uebersicht und Ausblick
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-8: AggregationMetricRow traegt durchgaengig einen testidPrefix (kein doppeltes data-testid)', () => {
	test('der Ausblick mountet AggregationMetricRow nicht (mehr) — sonst braucht er wieder eine eigene testidPrefix-Prop', () => {
		// #1848 A2 hatte den Mehrfach-Auswertungs-Zweig entfernt, A3 die ganze
		// Kaestchenliste. Die Kollisionsgefahr entsteht damit gar nicht erst —
		// diese Zusicherung haelt genau das fest.
		const ast = parseComponent(OUTLOOK_COMPONENT);
		const rows = findComponentsNamed(ast.fragment, 'AggregationMetricRow');
		assert.equal(
			rows.length,
			0,
			'AC-8 FAIL: der Ausblick mountet wieder AggregationMetricRow — dann braucht er auch ' +
				'wieder eine eigene `testidPrefix`-Prop, sonst kollidiert das Testid mit dem der ' +
				'Uebersicht (`aggregation-metric-row-temperature` doppelt im DOM).'
		);
	});

	test('AggregationMetricRow.svelte destrukturiert testidPrefix als optionale Prop', () => {
		const ast = parseComponent(AGGREGATION_ROW_COMPONENT);
		const propsDecl = instanceBody(ast).find(
			(stmt) =>
				stmt.type === 'VariableDeclaration' &&
				stmt.declarations?.[0]?.id?.type === 'ObjectPattern'
		);
		assert.ok(propsDecl, 'AggregationMetricRow.svelte: keine `let { ... } = $props()`-Destrukturierung gefunden.');
		if (!propsDecl) return;
		const properties = propsDecl.declarations[0].id.properties ?? [];
		const hasTestidPrefix = properties.some(
			(p: any) => p.key?.type === 'Identifier' && p.key.name === 'testidPrefix'
		);
		assert.ok(
			hasTestidPrefix,
			'AC-8 FAIL: AggregationMetricRow.svelte destrukturiert `testidPrefix` nicht mehr aus ' +
				'den Props — ein zweiter Mounter kann der Komponente keinen abweichenden Testid-Praefix mitgeben.'
		);
	});

	test('AggregationMetricRow.svelte: JEDES data-testid im Template referenziert testidPrefix (mit Default-Fallback) — keine Einzel-Element-Lueckenpruefung', () => {
		// Adversary-Befund F001 (BROKEN, Gegenpruefung nach Green): der erste
		// Test hier pruefte nur die NAMENTLICH bekannten Elemente `<tr>` und
		// `<label class="multi-option">` — das `<td data-testid="aggregation-
		// choices-{metricId}">` (Zeile 62) rutschte unbemerkt durch. Dieser Test
		// erfasst deshalb JEDES `data-testid`-Attribut im gesamten Template
		// (unabhaengig von Tag/Modus) und verlangt ausnahmslos einen
		// `testidPrefix`-Bezug — faengt damit auch ein kuenftig hinzugefuegtes
		// Element automatisch.
		const ast = parseComponent(AGGREGATION_ROW_COMPONENT);
		const allTestidAttrs = findAllAttributesNamed(ast.fragment, 'data-testid');
		assert.ok(
			allTestidAttrs.length > 0,
			'AggregationMetricRow.svelte: keine `data-testid`-Attribute im Template gefunden (Test-Setup kaputt?).'
		);

		const missing = allTestidAttrs.filter((attr) => !attributeReferencesIdentifier(attr, 'testidPrefix'));
		assert.equal(
			missing.length,
			0,
			`AC-8 FAIL: ${missing.length} von ${allTestidAttrs.length} \`data-testid\`-Attributen in ` +
				'AggregationMetricRow.svelte referenzieren `testidPrefix` NICHT (u. a. das `<td data-testid=' +
				'"aggregation-choices-{metricId}">`, Zeile 62, F001) — ohne durchgaengigen Praefix-Bezug ' +
				'kollidiert mindestens ein Testid zwischen zwei Mountpunkten auf derselben Editor-Seite.'
		);
	});

	test('[REGRESSIONSSCHUTZ, bereits GRUEN] der Uebersichts-Aufruf (WeatherMetricsTab.svelte) uebergibt weiterhin KEINE testidPrefix-Prop — Default bleibt bitidentisch', () => {
		// Kein neues Verhalten: der bestehende #1411-Aufrufer darf durch den
		// optionalen Parameter nicht veraendert werden (Spec Implementation
		// Details 2, "Ohne Angabe (Default): ... die Uebersicht ... aendert
		// sich dadurch NICHT"). Muss vor UND nach der Implementierung gruen sein.
		const ast = parseComponent(OVERVIEW_COMPONENT);
		const rows = findComponentsNamed(ast.fragment, 'AggregationMetricRow');
		assert.ok(rows.length >= 1, 'WeatherMetricsTab.svelte ruft AggregationMetricRow nicht mehr auf (unerwartet).');
		const anyWithPrefix = rows.some((row) => findAttr(row, 'testidPrefix'));
		assert.ok(
			!anyWithPrefix,
			'REGRESSION: der Uebersichts-Aufruf von AggregationMetricRow in WeatherMetricsTab.svelte ' +
				'uebergibt jetzt eine testidPrefix-Prop — das aendert seine Default-Testids und bricht ' +
				'damit bestehende #1411-Vertraege.'
		);
	});
});
