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
