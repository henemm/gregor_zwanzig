// #1401 Scheibe B, Teil 1 — AC-2 (zweiter Teil): der Vergleichs-Kontext laedt
// das Metrik-Register (`/api/metrics`) zusaetzlich, OHNE dass die Stunden-
// verlauf-Steuerung dadurch an diesen Ladevorgang gekoppelt wird.
// Spec: docs/specs/modules/fix_1401b_register_stundenverlauf_alarme.md AC-2/AC-7
//
// Struktur-/AST-Test mit dem echten Svelte-Compiler (dieses Repo hat kein
// vitest/jsdom), Vorbild: compare_hourly_layout_controls_structure.test.ts.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/weather_metrics_tab_compare_catalog_fetch.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

const here = dirname(fileURLToPath(import.meta.url));
const COMPONENT = join(here, '..', 'WeatherMetricsTab.svelte');

function parseComponent(): any {
	return parse(readFileSync(COMPONENT, 'utf-8'), { modern: true });
}

/** Alle `$effect(...)`-Aufrufe im Instance-Script. */
function effectCalls(ast: any): any[] {
	const found: any[] = [];
	function visit(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visit);
			return;
		}
		const n = node as Record<string, any>;
		if (n.type === 'CallExpression' && n.callee?.type === 'Identifier' && n.callee.name === '$effect') {
			found.push(n);
		}
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(ast.instance?.content?.body ?? []);
	return found;
}

/** Sammelt alle String-Literale eines Subtrees. */
function stringLiterals(subtree: unknown): string[] {
	const found: string[] = [];
	function visit(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visit);
			return;
		}
		const n = node as Record<string, any>;
		if (n.type === 'Literal' && typeof n.value === 'string') found.push(n.value);
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(subtree);
	return found;
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

/**
 * Sucht den Template-IfBlock, dessen Bedingung `sections.includes('<name>')`
 * enthaelt, und liefert ihn mitsamt der Kette seiner IfBlock-Vorfahren.
 */
function findSectionBlockWithAncestors(fragment: unknown, sectionName: string): {
	block: any;
	ancestorTests: any[];
} | null {
	let hit: { block: any; ancestorTests: any[] } | null = null;
	function visit(node: unknown, ancestors: any[]): void {
		if (hit) return;
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach((c) => visit(c, ancestors));
			return;
		}
		const n = node as Record<string, any>;
		let nextAncestors = ancestors;
		if (n.type === 'IfBlock') {
			if (stringLiterals(n.test).includes(sectionName)) {
				hit = { block: n, ancestorTests: ancestors };
				return;
			}
			nextAncestors = [...ancestors, n.test];
		}
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key], nextAncestors);
		}
	}
	visit(fragment, []);
	return hit;
}

describe('#1401b AC-2: der Vergleich laedt das Metrik-Register fuer die Beschriftungen', () => {
	test('Ein $effect laedt im Vergleichs-Kontext `/api/metrics`', () => {
		const ast = parseComponent();
		const matching = effectCalls(ast).filter((eff) => {
			const literals = stringLiterals(eff);
			return literals.includes('/api/metrics') && literals.includes('vergleich');
		});
		assert.ok(
			matching.length >= 1,
			'Kein $effect-Block laedt im Vergleichs-Kontext `/api/metrics` — ohne diesen ' +
				'Abruf bleibt das Register im Vergleich leer und der Stundenverlauf zeigt ' +
				'weiter seine eigenen Namen (#1401b AC-2).'
		);
	});

	test('Der Abruf ist fail-soft (`.catch`) und kippt `catalogLoaded` nicht', () => {
		const ast = parseComponent();
		const eff = effectCalls(ast).find((e) => {
			const literals = stringLiterals(e);
			return literals.includes('/api/metrics') && literals.includes('vergleich');
		});
		assert.ok(eff, 'Vergleichs-Effect mit /api/metrics nicht gefunden.');
		const names = identifiers(eff);
		assert.ok(names.has('catch'), 'Der Abruf hat kein `.catch(...)` — ein Fehlschlag wuerde durchschlagen.');
		assert.equal(
			names.has('catalogLoaded'),
			false,
			'Der Vergleichs-Abruf fasst `catalogLoaded` an — dieses Flag steuert den ' +
				'route-eigenen Speicher-Gate (weatherSaveGate) und darf im Vergleich nicht kippen.'
		);
	});

	// Issue #3276 (Spec-AC-38): die Stundenverlauf-Steuerung des Ortsvergleichs ist ersatzlos
	// entfernt (Einstellung nur noch in „Was steht wo"). Die beiden Tests „haengt an keinem
	// Katalog-Gate" und „bekommt das Register als catalog-Attribut" pruefen eine Flaeche, die es
	// nicht mehr gibt — ersetzt durch die Zusicherung, dass sie nicht zurueckkehrt.
	test('#3276: es gibt keinen `sections.includes("stundenverlauf")`-Block mehr', () => {
		const ast = parseComponent();
		assert.equal(findSectionBlockWithAncestors(ast.fragment, 'stundenverlauf'), null);
	});

	test('Gegenprobe: der Ausblick-Block IST bewusst an compareCatalogLoaded gekoppelt', () => {
		// Beweist, dass der Gate-Nachweis oben ueberhaupt anschlagen kann — der
		// Nachbarblock traegt genau diese Kopplung (bewusst, s. Kommentar dort).
		const ast = parseComponent();
		const outlook = findSectionBlockWithAncestors(ast.fragment, 'ausblick');
		assert.ok(outlook, 'Kein `{#if sections.includes("ausblick")}`-Block gefunden.');
		assert.ok(identifiers(outlook!.block.test).has('compareCatalogLoaded'));
	});
});
