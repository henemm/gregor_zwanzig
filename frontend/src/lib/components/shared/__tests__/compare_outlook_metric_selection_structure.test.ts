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
	const value = attr.value;
	if (Array.isArray(value)) {
		for (const part of value) {
			if (part?.type === 'ExpressionTag') visitExpr(part.expression);
		}
	} else if (value?.type === 'ExpressionTag') {
		visitExpr(value.expression);
	}
	return hit;
}

/** Prueft, ob ein Attributwert (welcher Notation auch immer) mit einem
 *  statischen Text-Praefix beginnt UND zusaetzlich `identifierName` referenziert
 *  — Beweis fuer `compare-layout-outlook-metric-${group.metric_id}`-artige
 *  Testids, unabhaengig von Template-Literal- vs. Svelte-Mischform-Notation. */
function attributeHasPrefixAndIdentifier(attr: any, prefix: string, identifierName: string): boolean {
	if (!attr) return false;
	const value = attr.value;
	if (Array.isArray(value)) {
		const startsWithPrefix = value[0]?.type === 'Text' && value[0].data === prefix;
		return startsWithPrefix && attributeReferencesIdentifier(attr, identifierName);
	}
	if (value?.type === 'ExpressionTag' && value.expression?.type === 'TemplateLiteral') {
		const startsWithPrefix = value.expression.quasis?.[0]?.value?.raw === prefix;
		return startsWithPrefix && attributeReferencesIdentifier(attr, identifierName);
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
	test('im Gruppierungs-Block existiert eine Checkbox-Zeile mit Testid-Praefix `compare-layout-outlook-metric-`, an `group` gebunden', () => {
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
			attributeHasPrefixAndIdentifier(attr, 'compare-layout-outlook-metric-', 'group')
		);
		assert.ok(
			matchFound,
			'AC-3 FAIL (RED): keine Checkbox-/Label-Zeile mit `compare-layout-outlook-metric-`-Testid, ' +
				'die auf `group` (statt des alten `entry`) verweist, im Gruppierungs-Block gefunden.'
		);
	});

	test('die Einzel-Checkbox bleibt am unveraenderten Handler `isOutlookMetricActive` haengen', () => {
		const ast = parseComponent(OUTLOOK_COMPONENT);
		const eachBlocks = findEachBlocksOverCall(ast.fragment, 'groupCompareCatalog', 'catalog');
		assert.ok(eachBlocks.length >= 1, 'AC-3 FAIL (RED): kein groupCompareCatalog-Block (s. AC-1).');
		if (eachBlocks.length === 0) return;

		const inputs = eachBlocks.flatMap((block) => findElementsNamed(block.body, 'input'));
		const checkedUsesHandler = inputs.some((input) => {
			const checkedAttr = findAttr(input, 'checked');
			return checkedAttr && attributeReferencesIdentifier(checkedAttr, 'isOutlookMetricActive');
		});
		assert.ok(
			checkedUsesHandler,
			'AC-3/AC-4 FAIL (RED): keine Checkbox im Gruppierungs-Block, deren `checked`-Attribut ' +
				'`isOutlookMetricActive` (unveraenderter Handler, Zeilen 47-57) referenziert.'
		);
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// AC-2 / AC-4: Mehrfach-Options-Gruppen ueber AggregationMetricRow mode="multiple"
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-2: Mehrfach-Options-Gruppen (Temperatur, gefuehlte Temperatur) ueber AggregationMetricRow mode="multiple"', () => {
	test('im Gruppierungs-Block wird AggregationMetricRow mit mode="multiple" und options={group.options} aufgerufen', () => {
		const ast = parseComponent(OUTLOOK_COMPONENT);
		const eachBlocks = findEachBlocksOverCall(ast.fragment, 'groupCompareCatalog', 'catalog');
		assert.ok(
			eachBlocks.length >= 1,
			'AC-2 FAIL (RED): ohne den groupCompareCatalog-Block (AC-1) gibt es keine Gruppe, in der ' +
				'AggregationMetricRow mode="multiple" haengen koennte.'
		);
		if (eachBlocks.length === 0) return;

		const rows = eachBlocks.flatMap((block) => findComponentsNamed(block.body, 'AggregationMetricRow'));
		assert.ok(
			rows.length >= 1,
			'AC-2 FAIL (RED): kein `AggregationMetricRow`-Aufruf im Ausblick-Gruppierungs-Block gefunden.'
		);
		if (rows.length === 0) return;

		const withMultipleMode = rows.filter((row) => attrIsStaticText(findAttr(row, 'mode'), 'multiple'));
		assert.ok(
			withMultipleMode.length >= 1,
			'AC-2 FAIL (RED): kein AggregationMetricRow-Aufruf mit `mode="multiple"` im Ausblick.'
		);

		const withOptionsFromGroup = withMultipleMode.some((row) => {
			const optionsAttr = findAttr(row, 'options');
			return optionsAttr && attributeReferencesIdentifier(optionsAttr, 'group');
		});
		assert.ok(
			withOptionsFromGroup,
			'AC-2 FAIL (RED): `options`-Prop des AggregationMetricRow-Aufrufs verweist nicht auf `group` ' +
				'(erwartet `options={group.options}`, die tatsaechlichen Katalog-Optionen der Gruppe).'
		);
	});
});

describe('AC-4: beide Zweige leiten checked/selectedChoiceIds weiterhin aus materializedOutlookKeys ab', () => {
	test('AggregationMetricRow selectedChoiceIds={materializedOutlookKeys} — direkte Bindung, keine neue Zwischenvariable', () => {
		const ast = parseComponent(OUTLOOK_COMPONENT);
		const eachBlocks = findEachBlocksOverCall(ast.fragment, 'groupCompareCatalog', 'catalog');
		assert.ok(eachBlocks.length >= 1, 'AC-4 FAIL (RED): kein groupCompareCatalog-Block (s. AC-1).');
		if (eachBlocks.length === 0) return;

		const rows = eachBlocks.flatMap((block) => findComponentsNamed(block.body, 'AggregationMetricRow'));
		const wired = rows.some((row) => {
			const attr = findAttr(row, 'selectedChoiceIds');
			return attr && attributeReferencesIdentifier(attr, 'materializedOutlookKeys');
		});
		assert.ok(
			wired,
			'AC-4 FAIL (RED): kein AggregationMetricRow-Aufruf mit `selectedChoiceIds`, das ' +
				'`materializedOutlookKeys` referenziert — die Mehrfach-Auswertung wuerde aus einer ' +
				'anderen/neuen Quelle als die bisherige Checkbox-Liste lesen (Datenverlust-Risiko AC-4).'
		);
	});

	// Die Einzel-Zweig-Haelfte von AC-4 (checked aus isOutlookMetricActive, das
	// intern materializedOutlookKeys.includes(...) nutzt, Zeilen 47-51,
	// UNVERAENDERT) ist bereits durch den AC-3-Test oben bewiesen — kein
	// zweiter Nachweis derselben Kette noetig.
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
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// AC-8: unterscheidbare data-testid zwischen Uebersicht und Ausblick
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-8: Ausblick uebergibt einen testidPrefix ungleich dem Uebersichts-Default (kein doppeltes data-testid)', () => {
	test('der Ausblick-Aufruf von AggregationMetricRow traegt eine testidPrefix-Prop', () => {
		const ast = parseComponent(OUTLOOK_COMPONENT);
		const eachBlocks = findEachBlocksOverCall(ast.fragment, 'groupCompareCatalog', 'catalog');
		assert.ok(eachBlocks.length >= 1, 'AC-8 FAIL (RED): kein groupCompareCatalog-Block (s. AC-1).');
		if (eachBlocks.length === 0) return;

		const rows = eachBlocks.flatMap((block) => findComponentsNamed(block.body, 'AggregationMetricRow'));
		const withPrefix = rows.some((row) => findAttr(row, 'testidPrefix'));
		assert.ok(
			withPrefix,
			'AC-8 FAIL (RED): kein AggregationMetricRow-Aufruf im Ausblick uebergibt eine ' +
				'`testidPrefix`-Prop — ohne sie kollidiert das Testid mit dem der Uebersicht ' +
				'(`aggregation-metric-row-temperature` doppelt im DOM).'
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
