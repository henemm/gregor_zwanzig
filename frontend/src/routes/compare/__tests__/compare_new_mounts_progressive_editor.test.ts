// TDD RED — Epic #1301 Scheibe F2a: /compare/new mountet den Progressive-Editor.
//
// Die Route `frontend/src/routes/compare/new/+page.svelte` muss den neuen
// Progressive-Tab-Editor `CompareNewEditor` mounten und NICHT mehr den
// Alt-Editor `CompareEditor mode="create"`. Spec:
//   docs/specs/modules/feat_1301_f2a_compare_new_trip_pattern.md
//   § "Geänderte Dateien" / AC-1 / AC-10
//
// Struktur-/AST-Test (kein Dateiinhalt-Grep): parst die Route mit dem echten
// Svelte-5-Compiler und inspiziert die im Template gemounteten Komponenten.
//
// RED heute: die Route rendert `<CompareEditor mode="create" .../>` (kein
// `CompareNewEditor`). Beide Asserts schlagen fehl:
//   (1) CompareNewEditor NICHT gemountet, (2) CompareEditor NOCH gemountet.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/routes/compare/__tests__/compare_new_mounts_progressive_editor.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

const here = dirname(fileURLToPath(import.meta.url));
const ROUTE = join(here, '..', 'new', '+page.svelte');

/** Namen aller im Template-AST gemounteten Svelte-Komponenten-Instanzen. */
function mountedComponentNames(subtree: unknown): string[] {
	const found: string[] = [];
	function visit(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visit);
			return;
		}
		const n = node as Record<string, any>;
		if (n.type === 'Component' && typeof n.name === 'string') {
			found.push(n.name);
		}
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(subtree);
	return found;
}

function parseRoute(): any {
	return parse(readFileSync(ROUTE, 'utf-8'), { modern: true });
}

describe('F2a AC-1/AC-10: /compare/new mountet CompareNewEditor statt CompareEditor', () => {
	test('AC-1: Route mountet <CompareNewEditor>', () => {
		// GIVEN: die Route /compare/new
		// WHEN: der Template-AST inspiziert wird
		// THEN: CompareNewEditor ist gemountet (Progressive-Tab-Editor).
		const ast = parseRoute();
		const names = mountedComponentNames(ast.fragment);
		assert.ok(
			names.includes('CompareNewEditor'),
			`/compare/new mountet "CompareNewEditor" nicht. Gemountete Komponenten: ${names.join(', ')}`
		);
	});

	test('AC-10: Route mountet KEINEN CompareEditor mehr (Alt-Editor bleibt nur im Repo)', () => {
		// GIVEN: die Route /compare/new
		// WHEN: der Template-AST inspiziert wird
		// THEN: der Alt-Editor CompareEditor wird von der Route NICHT mehr gemountet
		// (er bleibt als Rollback-Punkt vorhanden, aber ohne Import von /compare/new).
		const ast = parseRoute();
		const names = mountedComponentNames(ast.fragment);
		assert.ok(
			!names.includes('CompareEditor'),
			`/compare/new mountet weiterhin den Alt-Editor "CompareEditor" — AC-10 verlangt den ` +
				`Wechsel auf CompareNewEditor. Gemountete Komponenten: ${names.join(', ')}`
		);
	});
});
