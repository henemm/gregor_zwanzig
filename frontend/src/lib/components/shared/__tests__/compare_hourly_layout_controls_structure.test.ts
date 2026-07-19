// TDD RED — Epic #1301 Scheibe F2a: geteilte Stundenverlauf-Steuerung.
//
// Die neue Anlege-Seite (`/compare/new`) und der Hub teilen sich EINE extrahierte
// Komponente `shared/CompareHourlyLayoutControls.svelte` (Layout-Tab = NUR
// Stundenverlauf-Toggle + Metrik-Auswahl). Spec:
//   docs/specs/modules/feat_1301_f2a_compare_new_trip_pattern.md
//   § "Neue Dateien" / § "Design-Entscheidung" / AC-7
//
// Struktur-/AST-Test (Anti-Hand-Kopie), Vorbild-Muster:
//   compare/__tests__/compare_hub_layout_hourly_access.test.ts (C2-Kern)
// Grund für AST statt DOM: dieses Repo hat kein vitest/jsdom (package.json
// "test": node --test). Statt eines verbotenen Dateiinhalt-Greps parst der Test
// die Komponente mit dem ECHTEN Svelte-5-Compiler und inspiziert den Template-AST.
//
// RED heute: die Datei `shared/CompareHourlyLayoutControls.svelte` existiert noch
// nicht → readFileSync/parse schlägt fehl. Nach der Extraktion muss die Schleife
// `{#each ALL_HOURLY_METRICS as metric}` mit `metric.key`-Testids + Enabled-Toggle
// strukturell nachweisbar sein.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/compare_hourly_layout_controls_structure.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

import { ALL_HOURLY_METRICS } from '../../compare/compareHourlyMetricDefs.ts';

const here = dirname(fileURLToPath(import.meta.url));
const COMPONENT = join(here, '..', 'CompareHourlyLayoutControls.svelte');

/** Sammelt alle im Template-AST-Subtree vergebenen Testids (data-testid an
 *  Elementen, testid-Prop an Svelte-Komponenten). Template-Literale werden als
 *  Roh-String mit `{expr}`-Platzhaltern serialisiert (Präfix-Vergleich). */
function renderedTestids(subtree: unknown): string[] {
	const found: string[] = [];
	function visit(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visit);
			return;
		}
		const n = node as Record<string, any>;
		if (n.type === 'RegularElement' || n.type === 'Component') {
			for (const attr of n.attributes ?? []) {
				if (attr.type !== 'Attribute') continue;
				if (attr.name !== 'data-testid' && attr.name !== 'testid') continue;
				const raw = Array.isArray(attr.value)
					? attr.value.map((v: any) => v.raw ?? '{expr}').join('')
					: (attr.value?.raw ?? '{expr}');
				found.push(raw);
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

/** Findet jeden `EachBlock`, dessen Iterations-Ausdruck EXAKT der Identifier
 *  `identifierName` ist (kein Zwischen-Array/Filter — 1:1-Bezug zum Katalog). */
function findEachBlocksOverIdentifier(subtree: unknown, identifierName: string): any[] {
	const found: any[] = [];
	function visit(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visit);
			return;
		}
		const n = node as Record<string, any>;
		if (
			n.type === 'EachBlock' &&
			n.expression?.type === 'Identifier' &&
			n.expression.name === identifierName
		) {
			found.push(n);
		}
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(subtree);
	return found;
}

/** Prüft, ob im Subtree IRGENDEIN Element/Komponente ein `testid`/`data-testid`
 *  als Template-Literal trägt, das mit `prefix` beginnt und `metric.key`
 *  interpoliert (AST-Beweis für `` `compare-layout-hourly-metric-${metric.key}` ``). */
function hasKeyedTestidTemplate(
	subtree: unknown,
	prefix: string,
	memberObjectName: string,
	memberPropertyName: string
): boolean {
	let hit = false;
	function visit(node: unknown): void {
		if (hit) return;
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visit);
			return;
		}
		const n = node as Record<string, any>;
		if (n.type === 'RegularElement' || n.type === 'Component') {
			for (const attr of n.attributes ?? []) {
				if (attr.type !== 'Attribute') continue;
				if (attr.name !== 'testid' && attr.name !== 'data-testid') continue;
				const value = attr.value;
				const expr = Array.isArray(value) ? value[0]?.expression : value?.expression;
				if (!expr || expr.type !== 'TemplateLiteral') continue;
				const startsWithPrefix = expr.quasis?.[0]?.value?.raw === prefix;
				const hasMemberExpr = (expr.expressions ?? []).some(
					(e: any) =>
						e.type === 'MemberExpression' &&
						e.object?.type === 'Identifier' &&
						e.object.name === memberObjectName &&
						e.property?.type === 'Identifier' &&
						e.property.name === memberPropertyName &&
						!e.computed
				);
				if (startsWithPrefix && hasMemberExpr) {
					hit = true;
					return;
				}
			}
		}
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(subtree);
	return hit;
}

function parseComponent(): any {
	// RED: Datei fehlt heute → readFileSync wirft ENOENT.
	const src = readFileSync(COMPONENT, 'utf-8');
	return parse(src, { modern: true });
}

describe('F2a AC-7: CompareHourlyLayoutControls extrahiert den Stundenverlauf geteilt', () => {
	test('Katalog ALL_HOURLY_METRICS hat mindestens 1 Eintrag (Vakuum-Schutz)', () => {
		assert.ok(ALL_HOURLY_METRICS.length >= 1);
	});

	test('Komponente iteriert `{#each ALL_HOURLY_METRICS as metric}` (Anti-Hand-Kopie)', () => {
		// GIVEN: die neu extrahierte geteilte Komponente
		// WHEN: sie mit dem echten Svelte-Compiler geparst wird
		// THEN: es existiert eine Schleife über EXAKT den Katalog-Identifier —
		// keine hart kopierte Metrik-Liste, die still von Hub/Anlege divergieren kann.
		const ast = parseComponent();
		const eachBlocks = findEachBlocksOverIdentifier(ast.fragment, 'ALL_HOURLY_METRICS');
		assert.ok(
			eachBlocks.length >= 1,
			'CompareHourlyLayoutControls.svelte enthält keinen `{#each ALL_HOURLY_METRICS as ...}`-Block ' +
				'(Spec F2a AC-7 / Anti-Hand-Kopie).'
		);
	});

	test('Je Katalog-Eintrag eine Metrik-Checkbox mit `compare-layout-hourly-metric-${metric.key}`-Testid', () => {
		// GIVEN: der Schleifenkörper über ALL_HOURLY_METRICS
		// WHEN: geparst
		// THEN: darin trägt ein Element/eine Komponente ein testid-Template-Literal
		// mit Präfix `compare-layout-hourly-metric-` + interpoliertem `metric.key`.
		const ast = parseComponent();
		const eachBlocks = findEachBlocksOverIdentifier(ast.fragment, 'ALL_HOURLY_METRICS');
		const matchFound = eachBlocks.some((block) =>
			hasKeyedTestidTemplate(block.body, 'compare-layout-hourly-metric-', 'metric', 'key')
		);
		assert.ok(
			matchFound,
			'CompareHourlyLayoutControls.svelte: keine Metrik-Checkbox mit `testid` ' +
				'`compare-layout-hourly-metric-${metric.key}` im ALL_HOURLY_METRICS-Schleifenkörper.'
		);
	});

	test('Komponente rendert den "Stundenverlauf ein/aus"-Schalter (compare-layout-hourly-enabled-toggle)', () => {
		// GIVEN: die Komponente
		// WHEN: geparst
		// THEN: das Enabled-Toggle-Testid existiert im AST.
		const ast = parseComponent();
		const ids = renderedTestids(ast.fragment);
		assert.ok(
			ids.includes('compare-layout-hourly-enabled-toggle'),
			`CompareHourlyLayoutControls.svelte rendert "compare-layout-hourly-enabled-toggle" nicht. ` +
				`Gefundene Testids: ${ids.join(', ')}`
		);
	});
});
