// TDD RED — Issue #1406 Scheibe A (Epic #1372 S4b Scheibe 2, Dach #1374).
//
// Der Ausblick-Auswahl-Block (`CompareOutlookLayoutControls.svelte:96-114`)
// zeigt heute noch das alte, ungruppierte Vor-#1411-Muster (26 flache Zeilen,
// „Temperatur" doppelt). Diese Datei weist strukturell nach, dass der Block
// stattdessen ueber `groupCompareCatalog(catalog)` iteriert und je Gruppe
// entweder eine einfache Checkbox-Zeile (eine Auswertung) oder
// `AggregationMetricRow mode="multiple"` (mehrere Auswertungen) rendert —
// exakt das Muster, das die Vergleichs-Uebersicht seit #1411 bereits zeigt
// (`WeatherMetricsTab.svelte:918-948`).
//
// Spec: docs/specs/modules/feat_1406a_ausblick_geteiltes_element.md
//   § Implementation Details 1+2, AC-1..AC-5, AC-8, Test-Plan
// Kontext: docs/context/feat-1406a-ausblick-geteiltes-element.md
//
// Grund fuer AST statt DOM: dieses Repo hat kein vitest/jsdom (package.json
// "test": node --test). Der Test parst die betroffenen Komponenten mit dem
// ECHTEN Svelte-5-Compiler und inspiziert den Template-/Instance-Script-AST
// statt eines verbotenen Dateiinhalt-Vergleichs. Vorbild:
// compare_hourly_layout_controls_structure.test.ts, officialAlertLegend.test.ts
// (Instance-Script-AST-Zugriff `ast.instance.content.body`).
//
// AC-5 (Reihenfolge-/„Aus"-Block, WeatherV2Reihenfolge) ist laut Spec
// NICHT-UMFANG dieser Lieferung — der zugehoerige Test ist deshalb
// ausdruecklich als REGRESSIONSSCHUTZ gekennzeichnet und muss HEUTE BEREITS
// GRUEN sein (bleibt es auch nach der Implementierung).
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

/** Findet jeden `EachBlock`, dessen Iterations-Ausdruck EXAKT ein Aufruf
 *  `calleeName(argName)` ist — Beweis, dass ueber die Gruppierungsfunktion
 *  iteriert wird, nicht ueber eine hart kopierte/rohe Liste. */
function findEachBlocksOverCall(subtree: unknown, calleeName: string, argName: string): any[] {
	const found: any[] = [];
	function visit(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visit);
			return;
		}
		const n = node as Record<string, any>;
		if (n.type === 'EachBlock' && n.expression?.type === 'CallExpression') {
			const callee = n.expression.callee;
			const args = n.expression.arguments ?? [];
			if (
				callee?.type === 'Identifier' &&
				callee.name === calleeName &&
				args.length >= 1 &&
				args[0]?.type === 'Identifier' &&
				args[0].name === argName
			) {
				found.push(n);
			}
		}
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(subtree);
	return found;
}

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

/** Sammelt alle `RegularElement`-Knoten mit gegebenem Tag-Namen im Subtree.
 *  Component-Aufrufe (fremde Dateien) werden NICHT betreten — deren Innenleben
 *  gehoert nicht zu diesem AST (kein False-Positive durch AggregationMetricRow-
 *  interne Checkboxen). */
function findElementsNamed(subtree: unknown, name: string): any[] {
	const found: any[] = [];
	function visit(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visit);
			return;
		}
		const n = node as Record<string, any>;
		if (n.type === 'RegularElement' && n.name === name) found.push(n);
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

/** Static-Text-Attribut, z. B. `mode="multiple"` (Svelte serialisiert das als
 *  `[{type:'Text', data:'multiple'}]`, KEIN Template-Literal). */
function attrIsStaticText(attr: any, expected: string): boolean {
	if (!attr) return false;
	const value = attr.value;
	if (Array.isArray(value)) {
		return value.length === 1 && value[0]?.type === 'Text' && value[0].data === expected;
	}
	return false;
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

/** Prueft rekursiv, ob IRGENDWO im Ausdrucks-Subtree eines Attributs der
 *  KONKRETE Member-Pfad `objectName.propertyName` steht (nicht-berechneter
 *  Zugriff, also `group.metric_id`, nicht `group[x]`).
 *
 *  Warum eigener Helfer (Adversary-Befund F-ADV3, #1848 A2, HIGH): der
 *  allgemeine `attributeReferencesIdentifier(attr, 'group')` ist an dieser
 *  Stelle BLIND — `group.options[0].key` referenziert `group` genauso gut wie
 *  `group.metric_id`. Belegt durch Mutation: `makeOutlookMetricHandler(
 *  group.options[0].key)` liess alle 12 Tests dieser Datei gruen, obwohl die
 *  Fehlermeldung woertlich die Kennung zusicherte. Genau der Rueckfall auf den
 *  alten Katalog-Schluessel bricht aber AC-1/AC-8 in Produktion. */
function attributeReferencesMemberPath(attr: any, objectName: string, propertyName: string): boolean {
	let hit = false;
	function visitExpr(node: unknown): void {
		if (hit || node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visitExpr);
			return;
		}
		const n = node as Record<string, any>;
		if (isMemberPath(n, objectName, propertyName)) {
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

/** `objectName.propertyName` als AST-Knoten — nicht berechnet, damit
 *  `group['metric_id']`-Umwege nicht stillschweigend als Treffer zaehlen. */
function isMemberPath(node: any, objectName: string, propertyName: string): boolean {
	return (
		node?.type === 'MemberExpression' &&
		node.computed !== true &&
		node.object?.type === 'Identifier' &&
		node.object.name === objectName &&
		node.property?.type === 'Identifier' &&
		node.property.name === propertyName
	);
}

/** Schaerfste Form fuer Handler-Attribute: irgendwo im Attribut steht ein
 *  Aufruf `calleeName(objectName.propertyName, ...)` — das ERSTE Argument ist
 *  exakt der Member-Pfad. Damit ist nicht nur belegt, dass die Kennung im
 *  Ausdruck vorkommt, sondern dass sie genau die Stelle besetzt, an der der
 *  Schluessel uebergeben wird. */
function attributeCallsWithMemberArgument(
	attr: any,
	calleeName: string,
	objectName: string,
	propertyName: string
): boolean {
	let hit = false;
	function visitExpr(node: unknown): void {
		if (hit || node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visitExpr);
			return;
		}
		const n = node as Record<string, any>;
		if (
			n.type === 'CallExpression' &&
			n.callee?.type === 'Identifier' &&
			n.callee.name === calleeName &&
			isMemberPath((n.arguments ?? [])[0], objectName, propertyName)
		) {
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

/** Prueft, ob ein Attributwert (welcher Notation auch immer) mit einem
 *  statischen Text-Praefix beginnt UND den Member-Pfad
 *  `objectName.propertyName` einsetzt — Beweis fuer
 *  `compare-layout-outlook-metric-${group.metric_id}`-artige Testids,
 *  unabhaengig von Template-Literal- vs. Svelte-Mischform-Notation. */
function attributeHasPrefixAndMemberPath(
	attr: any,
	prefix: string,
	objectName: string,
	propertyName: string
): boolean {
	if (!attr) return false;
	const value = attr.value;
	if (Array.isArray(value)) {
		const startsWithPrefix = value[0]?.type === 'Text' && value[0].data === prefix;
		return startsWithPrefix && attributeReferencesMemberPath(attr, objectName, propertyName);
	}
	if (value?.type === 'ExpressionTag' && value.expression?.type === 'TemplateLiteral') {
		const startsWithPrefix = value.expression.quasis?.[0]?.value?.raw === prefix;
		return startsWithPrefix && attributeReferencesMemberPath(attr, objectName, propertyName);
	}
	return false;
}

/** Instance-Script-AST einer Komponente (Vorbild: officialAlertLegend.test.ts
 *  F003, `ast.instance.content.body`). */
function instanceBody(ast: any): any[] {
	return (ast?.instance?.content?.body as any[]) ?? [];
}

// ═══════════════════════════════════════════════════════════════════════════
// AC-1: Auswahl-Block iteriert `groupCompareCatalog(catalog)` (24 statt 26 Zeilen)
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-1: Ausblick-Auswahl-Block gruppiert ueber groupCompareCatalog(catalog)', () => {
	test('CompareOutlookLayoutControls.svelte enthaelt `{#each groupCompareCatalog(catalog) as group}`', () => {
		const ast = parseComponent(OUTLOOK_COMPONENT);
		const eachBlocks = findEachBlocksOverCall(ast.fragment, 'groupCompareCatalog', 'catalog');
		assert.ok(
			eachBlocks.length >= 1,
			'AC-1 FAIL (RED): CompareOutlookLayoutControls.svelte iteriert noch nicht ueber ' +
				'`groupCompareCatalog(catalog)` — der Auswahl-Block zeigt noch die alte flache ' +
				'`{#each catalog as entry}`-Liste (26 statt 24 Zeilen, „Temperatur" doppelt).'
		);
	});

	test('Anti-Hand-Kopie: der Instance-Script importiert groupCompareCatalog statt eine eigene Gruppierung zu bauen', () => {
		const ast = parseComponent(OUTLOOK_COMPONENT);
		const imports = instanceBody(ast).filter((stmt) => stmt.type === 'ImportDeclaration');
		const hit = imports.some(
			(imp) =>
				String(imp.source?.value ?? '').includes('compareAggregationGrouping') &&
				(imp.specifiers ?? []).some(
					(s: any) => s.imported?.name === 'groupCompareCatalog' || s.local?.name === 'groupCompareCatalog'
				)
		);
		assert.ok(
			hit,
			'AC-1 FAIL (RED): kein Import von `groupCompareCatalog` aus `compareAggregationGrouping.ts` ' +
				'im Instance-Script gefunden — Gefahr eines zweiten, eigenen Gruppierungs-Codes statt ' +
				'Wiederverwendung des #1411-Bausteins.'
		);
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// AC-3: Einzel-Options-Gruppen (22 von 24) bleiben die einfache Checkbox-Zeile
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-3: Einzel-Options-Gruppen rendern weiterhin nur eine einfache Checkbox, kein AggregationMetricRow', () => {
	test('im Gruppierungs-Block existiert eine Checkbox-Zeile mit Testid-Praefix `compare-layout-outlook-metric-`, geschluesselt ueber `group.metric_id`', () => {
		const ast = parseComponent(OUTLOOK_COMPONENT);
		const eachBlocks = findEachBlocksOverCall(ast.fragment, 'groupCompareCatalog', 'catalog');
		assert.ok(
			eachBlocks.length >= 1,
			'AC-3 FAIL (RED): ohne den groupCompareCatalog-Block (AC-1) gibt es keine Gruppen, an denen ' +
				'sich der Einzel-Options-Zweig pruefen liesse.'
		);
		if (eachBlocks.length === 0) return;

		const checkboxTestids: any[] = [];
		for (const block of eachBlocks) {
			for (const el of findElementsNamed(block.body, 'label').concat(findElementsNamed(block.body, 'input'))) {
				const testidAttr = findAttr(el, 'data-testid') ?? findAttr(el, 'testid');
				if (testidAttr) checkboxTestids.push(testidAttr);
			}
		}
		const matchFound = checkboxTestids.some((attr) =>
			attributeHasPrefixAndMemberPath(attr, 'compare-layout-outlook-metric-', 'group', 'metric_id')
		);
		assert.ok(
			matchFound,
			'AC-3 FAIL (RED): keine Checkbox-/Label-Zeile mit `compare-layout-outlook-metric-`-Testid, ' +
				'die den Zeilen-Schluessel aus `group.metric_id` (der Kennung) bildet, im ' +
				'Gruppierungs-Block gefunden. Ein blosser `group`-Bezug genuegt NICHT — ' +
				'`group.options[0].key` wuerde das alte Katalog-Vokabular ins Testid schreiben ' +
				'(#1848 A2, Adversary F-ADV3).'
		);
	});

	test('die Einzel-Checkbox bleibt am unveraenderten Handler `isOutlookMetricActive` haengen — mit der Kennung als Schluessel', () => {
		const ast = parseComponent(OUTLOOK_COMPONENT);
		const eachBlocks = findEachBlocksOverCall(ast.fragment, 'groupCompareCatalog', 'catalog');
		assert.ok(eachBlocks.length >= 1, 'AC-3 FAIL (RED): kein groupCompareCatalog-Block (s. AC-1).');
		if (eachBlocks.length === 0) return;

		const inputs = eachBlocks.flatMap((block) => findElementsNamed(block.body, 'input'));
		const checkedUsesHandler = inputs.some((input) => {
			const checkedAttr = findAttr(input, 'checked');
			return (
				checkedAttr &&
				attributeCallsWithMemberArgument(checkedAttr, 'isOutlookMetricActive', 'group', 'metric_id')
			);
		});
		assert.ok(
			checkedUsesHandler,
			'AC-3/AC-4 FAIL (RED): keine Checkbox im Gruppierungs-Block, deren `checked`-Attribut ' +
				'`isOutlookMetricActive(group.metric_id)` aufruft (unveraenderter Handler, Zeilen 47-57) — ' +
				'der Haken muss ueber die KENNUNG gelesen werden, nicht ueber ' +
				'`group.options[0].key` (#1848 A2, Adversary F-ADV3).'
		);
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// AC-2 / AC-4 — UMGESTELLT in Issue #1848 Scheibe A2
//
// Vorher stand hier: "Mehrfach-Options-Gruppen (Temperatur, gefuehlte
// Temperatur) rendern je Auswertung ein eigenes Kaestchen ueber
// AggregationMetricRow mode='multiple'". Genau dieses Verhalten hat A2
// abgeschafft (Spec AC-8, PO-Entscheid 2026-08-20): der Ausblick speichert die
// KENNUNG, eine Halbauswahl laesst sich gar nicht mehr ablegen, und seit
// #1848 A1 stehen Tief und Hoch ohnehin in EINER Spannen-Zelle der Mail. Zwei
// Kaestchen wuerden etwas anderes versprechen, als herauskommt.
//
// Die Zusicherung ist deshalb UMGEDREHT statt geloescht: es darf keinen
// Mehrfach-Zweig mehr geben, und jede Gruppe -- auch die mit mehreren
// Auswertungen -- haengt an genau EINEM Kaestchen, das die Kennung schaltet.
// Dieselbe Nachweistiefe wie vorher (AST der echten Komponente), nur mit dem
// heutigen Sollzustand.
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-2 [#1848 A2]: kein Mehrfach-Auswertungs-Zweig mehr — ein Kaestchen je Groesse', () => {
	test('im Gruppierungs-Block gibt es keinen AggregationMetricRow-Aufruf mehr', () => {
		const ast = parseComponent(OUTLOOK_COMPONENT);
		const eachBlocks = findEachBlocksOverCall(ast.fragment, 'groupCompareCatalog', 'catalog');
		assert.ok(
			eachBlocks.length >= 1,
			'AC-2 FAIL: ohne den groupCompareCatalog-Block (AC-1) gibt es keine Gruppe zu pruefen.'
		);

		const rows = eachBlocks.flatMap((block) => findComponentsNamed(block.body, 'AggregationMetricRow'));
		assert.equal(
			rows.length,
			0,
			`AC-2 FAIL (#1848 A2): es haengen noch ${rows.length} AggregationMetricRow-Aufrufe im ` +
				'Ausblick-Gruppierungs-Block. Temperatur und gefuehlte Temperatur bekaemen damit ' +
				'weiterhin je Auswertung ein eigenes Kaestchen — eine Auswahl, die das Backend seit ' +
				'A2 gar nicht mehr speichern kann.'
		);
	});

	test('genau EIN Kaestchen je Gruppe, und es schaltet die Kennung (`group.metric_id`)', () => {
		const ast = parseComponent(OUTLOOK_COMPONENT);
		const eachBlocks = findEachBlocksOverCall(ast.fragment, 'groupCompareCatalog', 'catalog');
		assert.ok(eachBlocks.length >= 1, 'AC-2 FAIL: kein groupCompareCatalog-Block (s. AC-1).');

		const inputs = eachBlocks.flatMap((block) => findElementsNamed(block.body, 'input'));
		assert.equal(
			inputs.length,
			1,
			`AC-2 FAIL (#1848 A2): der Gruppierungs-Block enthaelt ${inputs.length} Eingabefelder — ` +
				'erwartet genau eines (ein Kaestchen je Groesse, ohne Sonderzweig).'
		);

		const onchange = findAttr(inputs[0], 'onchange');
		assert.ok(
			onchange && attributeReferencesIdentifier(onchange, 'makeOutlookMetricHandler'),
			'AC-2/AC-4 FAIL: das Kaestchen ruft beim Umschalten nicht `makeOutlookMetricHandler` auf.'
		);
		assert.ok(
			onchange &&
				attributeCallsWithMemberArgument(onchange, 'makeOutlookMetricHandler', 'group', 'metric_id'),
			'AC-2 FAIL (#1848 A2): der Umschalt-Handler bekommt als ersten Parameter nicht ' +
				'`group.metric_id`. Erwartet ist exakt `makeOutlookMetricHandler(group.metric_id)` — die ' +
				'KENNUNG. Ein anderer Pfad unter `group` (namentlich `group.options[0].key`, der ' +
				'Katalog-Schluessel einer einzelnen Auswertung) schreibt beim Speichern wieder das alte ' +
				'Vokabular und bricht AC-1/AC-8 in Produktion.'
		);
	});
});

describe('AC-4 [#1848 A2]: Anzeige und Umschalten lesen weiterhin aus DERSELBEN Quelle', () => {
	test('jedes Kaestchen haengt mit `checked` an isOutlookMetricActive — keine zweite Quelle daneben', () => {
		// Die Kette Anzeige/Umschalten aus EINER Materialisierung (#1366 F001)
		// ist unveraendert tragend -- nur der Schluessel ist jetzt die Kennung.
		// AC-3 zeigt, dass es die Bindung GIBT; hier wird geprueft, dass KEIN
		// Kaestchen daneben eine andere Quelle benutzt.
		const ast = parseComponent(OUTLOOK_COMPONENT);
		const eachBlocks = findEachBlocksOverCall(ast.fragment, 'groupCompareCatalog', 'catalog');
		assert.ok(eachBlocks.length >= 1, 'AC-4 FAIL: kein groupCompareCatalog-Block (s. AC-1).');

		const inputs = eachBlocks.flatMap((block) => findElementsNamed(block.body, 'input'));
		assert.ok(inputs.length >= 1, 'AC-4 FAIL: kein Kaestchen im Gruppierungs-Block.');
		for (const input of inputs) {
			const checkedAttr = findAttr(input, 'checked');
			assert.ok(
				checkedAttr &&
					attributeCallsWithMemberArgument(checkedAttr, 'isOutlookMetricActive', 'group', 'metric_id'),
				'AC-4 FAIL: ein Kaestchen im Gruppierungs-Block liest seinen Haken nicht aus ' +
					'`isOutlookMetricActive(group.metric_id)` — entweder haengt die Anzeige an einer anderen ' +
					'Funktion oder an einem anderen Schluessel als das Umschalten (z. B. ' +
					'`group.options[0].key`). Beides laesst Anzeige und Umschalten auf verschiedene ' +
					'Quellen laufen (Fehlerklasse #1366 F001).'
			);
		}
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// AC-5 (REGRESSIONSSCHUTZ — bereits heute GRUEN, muss es bleiben)
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-5 [REGRESSIONSSCHUTZ, bereits GRUEN]: Reihenfolge-/„Aus"-Block (WeatherV2Reihenfolge) bleibt unberuehrt', () => {
	test('WeatherV2Reihenfolge wird weiterhin mit primaryColumns/onRemove/onDndReorder aufgerufen — Nicht-Umfang laut Spec', () => {
		// Dieser Test prueft KEIN neues Verhalten dieser Lieferung. Er ist HEUTE
		// bereits gruen (Issue #1361 Befund 2/#1368, `8fc4d210`, live 2026-07-27)
		// und MUSS es nach der Implementierung von #1406 Scheibe A bleiben — die
		// Spec grenzt die Zeilen 116-136 explizit als Nicht-Umfang ab.
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
		// Issue #1719 S3 (Adversary-Fund F001, BROKEN): "Aus ist ein Zustand"
		// gilt NUR fuer den Trip-Kanal-Reiter (WeatherMetricsTab.svelte, route-
		// Kontext) — diese Einbettung arbeitet auf einem flachen Array ohne
		// Kanal-Ebene und hat bereits einen funktionierenden Rueckweg (Checkbox
		// darueber). `offColumns`/`onRestore` sind OPTIONALE Props ohne
		// Vorgabewert — die Naht ist die PROP-ANWESENHEIT (Spec Abschnitt 1),
		// nicht ein `context`-String. Werden sie hier durchgereicht, entsteht
		// eine ungewollte Aus-Gruppe im Ortsvergleich (AC-13-Verstoss).
		assert.equal(
			findAttr(row, 'offColumns'),
			undefined,
			'AC-13 FAIL: der Ausblick-Aufruf von WeatherV2Reihenfolge uebergibt jetzt `offColumns` — ' +
				'das erzeugt eine Aus-Gruppe im Ortsvergleich, wo ADR-0050 Regel 4 nicht gilt.'
		);
		assert.equal(
			findAttr(row, 'onRestore'),
			undefined,
			'AC-13 FAIL: der Ausblick-Aufruf von WeatherV2Reihenfolge uebergibt jetzt `onRestore` — ' +
				'siehe offColumns-Befund oben, dieselbe Naht.'
		);
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// AC-8: unterscheidbare data-testid zwischen Uebersicht und Ausblick
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-8: Ausblick uebergibt einen testidPrefix ungleich dem Uebersichts-Default (kein doppeltes data-testid)', () => {
	test('die Ausblick-Zeile traegt ein eigenes Testid-Praefix, das nicht mit dem der Uebersicht kollidiert', () => {
		// #1848 A2 umgestellt: frueher lief diese Zusicherung ueber die
		// `testidPrefix`-Prop des Ausblick-Aufrufs von AggregationMetricRow.
		// Den Aufruf gibt es nicht mehr (s. AC-2) — die Kollisionsgefahr, die
		// hier bewacht wird, entsteht damit gar nicht erst. Der Sache nach
		// geprueft wird weiterhin dasselbe: die Ausblick-Zeilen tragen ein
		// EIGENES Praefix, nicht das der Uebersicht.
		const ast = parseComponent(OUTLOOK_COMPONENT);
		const eachBlocks = findEachBlocksOverCall(ast.fragment, 'groupCompareCatalog', 'catalog');
		assert.ok(eachBlocks.length >= 1, 'AC-8 FAIL: kein groupCompareCatalog-Block (s. AC-1).');

		const rows = eachBlocks.flatMap((block) => findComponentsNamed(block.body, 'AggregationMetricRow'));
		assert.equal(
			rows.length,
			0,
			'AC-8 FAIL: der Ausblick mountet wieder AggregationMetricRow — dann braucht er auch ' +
				'wieder eine eigene `testidPrefix`-Prop, sonst kollidiert das Testid mit dem der ' +
				'Uebersicht (`aggregation-metric-row-temperature` doppelt im DOM).'
		);

		const testids: any[] = [];
		for (const block of eachBlocks) {
			for (const el of findElementsNamed(block.body, 'label').concat(findElementsNamed(block.body, 'input'))) {
				const attr = findAttr(el, 'data-testid') ?? findAttr(el, 'testid');
				if (attr) testids.push(attr);
			}
		}
		assert.ok(
			testids.some((attr) =>
				attributeHasPrefixAndMemberPath(attr, 'compare-layout-outlook-metric-', 'group', 'metric_id')
			),
			'AC-8 FAIL: keine Ausblick-Zeile mit dem eigenen Praefix ' +
				'`compare-layout-outlook-metric-` UND dem Schluessel `group.metric_id` gefunden — ohne ' +
				'eigenes Praefix waeren Ausblick- und Uebersichts-Zeile im DOM nicht auseinanderzuhalten, ' +
				'und mit einem anderen `group`-Pfad (`group.options[0].key`) traege die Zeile das alte ' +
				'Katalog-Vokabular statt der Kennung.'
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
			'AC-8 FAIL (RED): AggregationMetricRow.svelte destrukturiert `testidPrefix` noch nicht aus ' +
				'den Props — der Ausblick kann der Komponente keinen abweichenden Testid-Praefix mitgeben.'
		);
	});

	test('AggregationMetricRow.svelte: JEDES data-testid im Template referenziert testidPrefix (mit Default-Fallback) — keine Einzel-Element-Lueckenpruefung', () => {
		// Adversary-Befund F001 (BROKEN, Gegenpruefung nach Green): der erste
		// Test hier pruefte nur die NAMENTLICH bekannten Elemente `<tr>` und
		// `<label class="multi-option">` — das `<td data-testid="aggregation-
		// choices-{metricId}">` (Zeile 62) rutschte unbemerkt durch. Uebersicht
		// und Ausblick zeigen auf derselben Seite beide eine Mehrfach-Gruppe
		// fuer `temperature` ⇒ ohne Praefix zweimal `data-testid="aggregation-
		// choices-temperature"` im DOM. Dieser Test erfasst deshalb JEDES
		// `data-testid`-Attribut im gesamten Template (unabhaengig von Tag/Modus)
		// und verlangt ausnahmslos einen `testidPrefix`-Bezug — faengt damit
		// auch ein kuenftig hinzugefuegtes Element automatisch.
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
				'kollidiert mindestens ein Testid zwischen Uebersicht und Ausblick auf derselben Editor-Seite.'
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
