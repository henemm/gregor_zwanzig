// Issue #1911 AC-3 (Verdrahtung) / AC-7 (Ladezustand): die Gewitter-
// Schwellenzeile in WeatherMetricsTab.svelte muss (a) ihre `levels` ueber
// `deriveThunderThresholdLevels(...)` beziehen statt ueber das alte
// Array-Literal, und (b) darf keinen kaputten/leeren Zustand rendern,
// solange `compareCatalog` noch nicht geladen ist (`compareCatalogLoaded
// === false`) oder das Laden fehlschlug (`compareCatalogError` gesetzt).
//
// Struktur-/AST-Test mit dem echten Svelte-Compiler (dieses Repo hat kein
// vitest/jsdom, kein Runtime-Rendering-Harness fuer Svelte-5-Runen in
// node:test) -- Vorbild: shared/__tests__/weather_metrics_tab_compare_catalog_fetch.test.ts,
// das denselben Ancestor-IfBlock-Nachweis fuer ganze Sections liefert. Diese
// Datei uebertraegt das Muster von "Section" auf eine einzelne
// <ThresholdMetricRow metricId="thunder" .../>-Komponente.
//
// Spec: docs/specs/modules/thunder_threshold_katalog.md AC-3, AC-7.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/weather-metrics-tab/__tests__/thunderThresholdCatalogGuard.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

const here = dirname(fileURLToPath(import.meta.url));
const COMPONENT = join(here, '..', '..', 'WeatherMetricsTab.svelte');

function parseComponent(): any {
	return parse(readFileSync(COMPONENT, 'utf-8'), { modern: true });
}

/** Alle Identifier-Namen eines Subtrees. */
function identifiers(subtree: unknown): Set<string> {
	const found = new Set<string>();
	function visit(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visit);
			return;
		}
		const n = node as Record<string, any>;
		if (n.type === 'Identifier' && typeof n.name === 'string') found.add(n.name);
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(subtree);
	return found;
}

/** Der (Ausdrucks-)Wert eines Attributs: String bei Text-Attributen (z.B.
 *  `metricId="thunder"`), Ausdrucks-AST-Knoten bei `{...}`-Attributen (z.B.
 *  `levels={...}`). */
function attrValue(node: any, name: string): unknown {
	const attr = (node.attributes ?? []).find(
		(a: any) => a.type === 'Attribute' && a.name === name
	);
	if (!attr) return undefined;
	if (Array.isArray(attr.value)) {
		return attr.value.map((v: any) => v.data ?? '').join('');
	}
	if (attr.value?.type === 'ExpressionTag') {
		return attr.value.expression;
	}
	return attr.value;
}

/**
 * Findet die `<ThresholdMetricRow metricId="thunder" .../>`-Komponente
 * mitsamt der Kette ihrer IfBlock-Vorfahren (Test-Ausdruck jedes
 * umschliessenden `{#if ...}`) -- Vorbild:
 * weather_metrics_tab_compare_catalog_fetch.test.ts::findSectionBlockWithAncestors,
 * hier auf eine einzelne Komponente statt einen benannten Section-Block
 * uebertragen. Liefert zusaetzlich den NAECHSTEN (innersten) umschliessenden
 * IfBlock als `innermostIf` -- das ist der Block, dessen `{:else}`-Zweig
 * (falls vorhanden) den in AC-7 geforderten Platzhalter-/Fehlerzustand
 * tragen muesste.
 */
function findThunderThresholdRow(fragment: unknown): {
	component: any;
	ancestorIfBlocks: any[];
} | null {
	let hit: { component: any; ancestorIfBlocks: any[] } | null = null;
	function visit(node: unknown, ifAncestors: any[]): void {
		if (hit) return;
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach((c) => visit(c, ifAncestors));
			return;
		}
		const n = node as Record<string, any>;
		if (n.type === 'Component' && n.name === 'ThresholdMetricRow' && attrValue(n, 'metricId') === 'thunder') {
			hit = { component: n, ancestorIfBlocks: ifAncestors };
			return;
		}
		let nextAncestors = ifAncestors;
		if (n.type === 'IfBlock') {
			nextAncestors = [...ifAncestors, n];
		}
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key], nextAncestors);
		}
	}
	visit(fragment, []);
	return hit;
}

/**
 * Sucht im Subtree nach einem `<catalog>.find((e) => e.<field> === '<literalValue>')`-
 * Aufruf (Adversary-Finding F001: der bisherige Test prueft nur, DASS `levels` ein
 * Funktionsaufruf ist, nicht WELCHER Katalog-Schluessel als Argument hineingeht --
 * ein Katalog-Eintrag ohne `ordinalLabels`, z.B. `wind_max_kmh`, liefert eine leere
 * Schwellenliste, ohne dass ein bestehender Test rot wird). Liefert den gefundenen
 * `find(...)`-CallExpression-Knoten oder `null`.
 */
function findCatalogLookupComparingTo(node: unknown, literalValue: string): any {
	let found: any = null;
	function visit(n: unknown): void {
		if (found || n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) {
			n.forEach(visit);
			return;
		}
		const rec = n as Record<string, any>;
		if (
			rec.type === 'CallExpression' &&
			rec.callee?.type === 'MemberExpression' &&
			rec.callee.property?.name === 'find'
		) {
			const arrowArg = (rec.arguments ?? [])[0];
			const body = arrowArg?.body;
			const comparesToLiteral =
				body?.type === 'BinaryExpression' &&
				(body.operator === '===' || body.operator === '==') &&
				((body.left?.type === 'Literal' && body.left.value === literalValue) ||
					(body.right?.type === 'Literal' && body.right.value === literalValue));
			if (comparesToLiteral) {
				found = rec;
				return;
			}
		}
		for (const key of Object.keys(rec)) {
			if (key === 'parent') continue;
			visit(rec[key]);
		}
	}
	visit(node);
	return found;
}

describe('#1911 AC-3 (Verdrahtung): die Gewitter-Zeile bezieht `levels` aus deriveThunderThresholdLevels(...)', () => {
	test('`levels`-Attribut ist ein Aufruf von deriveThunderThresholdLevels, kein Array-Literal', () => {
		const ast = parseComponent();
		const hit = findThunderThresholdRow(ast.fragment);
		assert.ok(
			hit,
			'Keine <ThresholdMetricRow metricId="thunder" .../> im Template gefunden -- ' +
				'Struktur zu weit veraendert, um den Block zu finden.'
		);

		const levelsExpr = attrValue(hit!.component, 'levels') as { type?: string; callee?: { name?: string } } | undefined;
		assert.equal(
			levelsExpr?.type,
			'CallExpression',
			'AC-3 FAIL: `levels` an der Gewitter-Zeile ist (noch) kein Funktionsaufruf ' +
				`(gefundener Ausdruckstyp: ${levelsExpr?.type ?? 'Array-Literal/undefined'}) -- ` +
				'vermutlich noch das alte hart codierte Level-Array.'
		);
		assert.equal(
			levelsExpr?.callee?.name,
			'deriveThunderThresholdLevels',
			`AC-3 FAIL: \`levels\` ruft nicht `+
				`\`deriveThunderThresholdLevels\` auf, sondern \`${levelsExpr?.callee?.name}\`.`
		);
	});

	test('das Argument von deriveThunderThresholdLevels stammt aus dem Katalog-Eintrag "thunder_level_max" (Adversary F001)', () => {
		const ast = parseComponent();
		const hit = findThunderThresholdRow(ast.fragment);
		assert.ok(hit, 'Keine <ThresholdMetricRow metricId="thunder" .../> im Template gefunden.');

		const levelsExpr = attrValue(hit!.component, 'levels') as { type?: string; arguments?: unknown } | undefined;
		assert.equal(
			levelsExpr?.type,
			'CallExpression',
			'Vorbedingung (s. vorheriger Test) nicht erfuellt -- `levels` ist kein Funktionsaufruf.'
		);

		const lookupCall = findCatalogLookupComparingTo(levelsExpr!.arguments, 'thunder_level_max');
		assert.ok(
			lookupCall,
			'AC-3 FAIL: das Argument von `deriveThunderThresholdLevels(...)` enthaelt keinen ' +
				'`....find((e) => e.metric === \'thunder_level_max\')`-Aufruf -- die Ableitung liest ' +
				'moeglicherweise den falschen Katalog-Eintrag (z.B. einen Range-Eintrag ohne ' +
				'`ordinalLabels`), was still eine leere Schwellenliste liefert.'
		);
	});
});

describe('#1911 AC-7: definierter Lade-/Fehlerzustand statt kaputter/leerer Optionsliste', () => {
	test('die Gewitter-Zeile ist an compareCatalogLoaded/compareCatalogError gekoppelt (kein ungeschuetztes Rendern vor dem Laden)', () => {
		const ast = parseComponent();
		const hit = findThunderThresholdRow(ast.fragment);
		assert.ok(hit, 'Keine <ThresholdMetricRow metricId="thunder" .../> im Template gefunden.');

		const guardBlock = hit!.ancestorIfBlocks.find(
			(block) => identifiers(block.test).has('compareCatalogLoaded') || identifiers(block.test).has('compareCatalogError')
		);
		assert.ok(
			guardBlock,
			'AC-7 FAIL: kein umschliessender `{#if compareCatalogLoaded/compareCatalogError ...}`-Block ' +
				'um die Gewitter-Schwellenzeile gefunden -- die Zeile kann rendern, bevor der Katalog ' +
				'geladen ist bzw. obwohl das Laden fehlschlug (leere/kaputte Optionsliste statt eines ' +
				'definierten Zustands).'
		);
	});

	test('der Guard-Block hat einen {:else}-Zweig -- ein definierter Platzhalter-/Fehlerzustand existiert', () => {
		const ast = parseComponent();
		const hit = findThunderThresholdRow(ast.fragment);
		assert.ok(hit, 'Keine <ThresholdMetricRow metricId="thunder" .../> im Template gefunden.');

		const guardBlock = hit!.ancestorIfBlocks.find(
			(block) => identifiers(block.test).has('compareCatalogLoaded') || identifiers(block.test).has('compareCatalogError')
		);
		assert.ok(guardBlock, 'Vorbedingung (s. vorheriger Test) nicht erfuellt -- kein Guard-Block gefunden.');
		assert.ok(
			guardBlock.alternate,
			'AC-7 FAIL: der Guard-Block um die Gewitter-Schwellenzeile hat keinen `{:else}`-Zweig -- ' +
				'ohne geladenen Katalog gibt es keinen definierten Platzhalter-/Fehlerzustand, nur ein ' +
				'stilles Nichts-Rendern (das Template zeigt dann weder die Zeile noch einen Hinweis).'
		);
	});
});

/**
 * Minimaler boolescher Auswerter fuer den Guard-Test-Ausdruck (Adversary-Finding
 * F002: der bisherige Test prueft nur, DASS ein `{#if}`-Block mit `{:else}`-Zweig
 * existiert -- nicht die RICHTUNG der Bedingung. Eine Invertierung zu
 * `{#if !compareCatalogLoaded || compareCatalogError}` behaelt Struktur und
 * Zweige exakt bei, vertauscht aber, WELCHER Zweig bei geladenem/fehlerfreiem
 * Katalog gerendert wird -- rein strukturelle Tests bleiben dafuer blind).
 * Unterstuetzt nur die hier vorkommenden Knotentypen bewusst eng, damit ein
 * unbekannter Ausdruckstyp den Test klar scheitern laesst statt still `false`
 * zurueckzugeben.
 */
function evalGuardTest(node: any, env: Record<string, unknown>): boolean {
	switch (node?.type) {
		case 'Identifier':
			return Boolean(env[node.name]);
		case 'UnaryExpression':
			if (node.operator === '!') return !evalGuardTest(node.argument, env);
			throw new Error(`evalGuardTest: unsupported unary operator "${node.operator}"`);
		case 'LogicalExpression':
			if (node.operator === '&&') return evalGuardTest(node.left, env) && evalGuardTest(node.right, env);
			if (node.operator === '||') return evalGuardTest(node.left, env) || evalGuardTest(node.right, env);
			throw new Error(`evalGuardTest: unsupported logical operator "${node.operator}"`);
		case 'Literal':
			return Boolean(node.value);
		default:
			throw new Error(`evalGuardTest: unsupported node type "${node?.type}" -- Guard-Test-Ausdruck zu weit veraendert, um ihn auszuwerten.`);
	}
}

/** Sucht in einem Fragment-Subtree (z.B. `IfBlock.consequent`/`.alternate`) nach
 *  der `<ThresholdMetricRow metricId="thunder" .../>`-Komponente. */
function fragmentContainsThunderRow(fragment: unknown): boolean {
	return findThunderThresholdRow(fragment) !== null;
}

/** Sucht in einem Fragment-Subtree nach dem Platzhalter-`<tr>` der Gewitter-Zeile. */
function fragmentContainsPlaceholder(fragment: unknown): boolean {
	let found = false;
	function visit(node: unknown): void {
		if (found || node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visit);
			return;
		}
		const n = node as Record<string, any>;
		if (n.type === 'RegularElement') {
			const attrs = n.attributes ?? [];
			const testIdAttr = attrs.find((a: any) => a.type === 'Attribute' && a.name === 'data-testid');
			const val = Array.isArray(testIdAttr?.value) ? testIdAttr.value.map((v: any) => v.data ?? '').join('') : undefined;
			if (val === 'threshold-metric-row-thunder-placeholder') {
				found = true;
				return;
			}
		}
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(fragment);
	return found;
}

describe('#1911 AC-7 Richtung (Adversary F002): der Guard-Test waehlt den echten Zweig genau dann, wenn der Katalog bereit ist', () => {
	function findGuardBlock() {
		const ast = parseComponent();
		const hit = findThunderThresholdRow(ast.fragment);
		assert.ok(hit, 'Keine <ThresholdMetricRow metricId="thunder" .../> im Template gefunden.');
		const guardBlock = hit!.ancestorIfBlocks.find(
			(block) => identifiers(block.test).has('compareCatalogLoaded') || identifiers(block.test).has('compareCatalogError')
		);
		assert.ok(guardBlock, 'Kein Guard-Block gefunden.');
		return guardBlock;
	}

	test('Guard-Test ist wahr bei geladenem, fehlerfreiem Katalog und falsch waehrend des Ladens bzw. bei Fehler', () => {
		const guardBlock = findGuardBlock();

		const ready = evalGuardTest(guardBlock.test, { compareCatalogLoaded: true, compareCatalogError: undefined });
		assert.equal(
			ready,
			true,
			'AC-7 FAIL: bei compareCatalogLoaded=true und compareCatalogError=undefined (Katalog bereit) ' +
				'muss der Guard-Test wahr sein -- sonst rendert der Platzhalter, obwohl der Katalog fertig ' +
				'geladen ist (invertierte Bedingung).'
		);

		const stillLoading = evalGuardTest(guardBlock.test, { compareCatalogLoaded: false, compareCatalogError: undefined });
		assert.equal(
			stillLoading,
			false,
			'AC-7 FAIL: bei compareCatalogLoaded=false (noch am Laden) darf der Guard-Test nicht wahr sein -- ' +
				'sonst rendert die echte Zeile mit ungeladenem Katalog statt des "Lädt…"-Platzhalters.'
		);

		const errored = evalGuardTest(guardBlock.test, { compareCatalogLoaded: true, compareCatalogError: 'Netzwerkfehler' });
		assert.equal(
			errored,
			false,
			'AC-7 FAIL: bei gesetztem compareCatalogError darf der Guard-Test nicht wahr sein -- sonst ' +
				'rendert die echte Zeile trotz Ladefehler statt der Fehlermeldung.'
		);
	});

	test('die echte Zeile steht im Wahr-Zweig (consequent), der Platzhalter im {:else}-Zweig -- nicht umgekehrt', () => {
		const guardBlock = findGuardBlock();

		const consequentHasRow = fragmentContainsThunderRow(guardBlock.consequent);
		const alternateHasRow = fragmentContainsThunderRow(guardBlock.alternate);
		assert.ok(
			consequentHasRow && !alternateHasRow,
			'AC-7 FAIL: die <ThresholdMetricRow metricId="thunder" .../> steht nicht (ausschliesslich) im ' +
				`Wahr-Zweig des Guard-Blocks (consequent: ${consequentHasRow}, alternate: ${alternateHasRow}).`
		);

		const consequentHasPlaceholder = fragmentContainsPlaceholder(guardBlock.consequent);
		const alternateHasPlaceholder = fragmentContainsPlaceholder(guardBlock.alternate);
		assert.ok(
			alternateHasPlaceholder && !consequentHasPlaceholder,
			'AC-7 FAIL: der Platzhalter steht nicht (ausschliesslich) im {:else}-Zweig des Guard-Blocks ' +
				`(consequent: ${consequentHasPlaceholder}, alternate: ${alternateHasPlaceholder}).`
		);
	});
});
