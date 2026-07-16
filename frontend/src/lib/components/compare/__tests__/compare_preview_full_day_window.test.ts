// TDD RED — Issue #1268 (AC-11): Der Vorschau-Call schickt das feste
// Ganztags-Fenster [0, 23], nicht [preset.hour_from, preset.hour_to].
//
// Spec: docs/specs/modules/issue_1268_compare_timewindow_removal.md § AC-11
//
// Befund: CompareTabs.svelte schickte `time_window: [preset.hour_from,
// preset.hour_to]` an /api/_validator/compare-email-preview. Bei einem nach
// #1268 neu angelegten Vergleich sind beide Werte 0 → [0, 0] → die Vorschau
// wertet ein Null-Fenster aus und liefe leer. Die Vorschau muss zeigen, was
// tatsaechlich verschickt wird (Dispatch nutzt fest (0, 23)).
//
// --- Warum AST (bewusste Entscheidung, kein Dateiinhalt-Grep) ---
// Der Aufruf sitzt in einem $effect einer Svelte-5-Komponente; das Repo hat
// kein vitest/jsdom (s. compare_layout_timewindow_removed.test.ts). Statt eines
// Text-Greps parst dieser Test die Komponente mit dem ECHTEN Svelte-Compiler und
// inspiziert den Instance-Script-AST: welches Argument traegt der Preview-Call
// unter dem Schluessel `time_window`? Auskommentierter Code taucht im AST nicht
// auf (kein False-Green), andere Formatierung sehr wohl (kein False-Red).
// Das echte Verhalten deckt zusaetzlich die Staging-Validierung ab.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

const here = dirname(fileURLToPath(import.meta.url));
const COMPONENT = join(here, '..', 'CompareTabs.svelte');

const PREVIEW_ENDPOINT = '/api/_validator/compare-email-preview';

/** Findet das Body-Objekt des Preview-Calls und liefert die `time_window`-Property. */
function previewTimeWindowNode(file: string): Record<string, any> | null {
	const ast = parse(readFileSync(file, 'utf-8'), { modern: true }) as any;
	let found: Record<string, any> | null = null;

	function visit(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visit);
			return;
		}
		const n = node as Record<string, any>;
		// api.post(PREVIEW_ENDPOINT, { ... }) — irgendein Call mit dem Endpoint
		// als String-Literal und einem Objekt-Argument.
		if (n.type === 'CallExpression' && Array.isArray(n.arguments)) {
			const hasEndpoint = n.arguments.some(
				(a: any) => a?.type === 'Literal' && a.value === PREVIEW_ENDPOINT
			);
			if (hasEndpoint) {
				const body = n.arguments.find((a: any) => a?.type === 'ObjectExpression');
				const prop = body?.properties?.find(
					(p: any) => p?.type === 'Property' && p.key?.name === 'time_window'
				);
				if (prop) found = prop.value;
			}
		}
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}

	visit(ast.instance);
	return found;
}

/** Rendert einen AST-Ausdruck grob als Text — nur fuer Fehlermeldungen. */
function describeNode(n: Record<string, any> | null): string {
	if (!n) return '(nicht gefunden)';
	if (n.type === 'ArrayExpression') {
		return `[${n.elements.map((e: any) => describeNode(e)).join(', ')}]`;
	}
	if (n.type === 'Literal') return String(n.value);
	if (n.type === 'MemberExpression') {
		return `${describeNode(n.object)}.${n.property?.name ?? '?'}`;
	}
	if (n.type === 'Identifier') return n.name;
	return n.type;
}

describe('#1268 AC-11: Vorschau-Call nutzt das feste Ganztags-Fenster', () => {
	test('time_window ist das Literal [0, 23], nicht aus hour_from/hour_to gebaut', () => {
		// GIVEN: der Vorschau-Tab im Vergleichs-Hub
		// WHEN: die Vorschau geladen wird
		// THEN: der Call schickt [0, 23] — denselben Zeitraum wie der echte Versand
		// RED vor Fix: [preset.hour_from, preset.hour_to] → bei neuen Presets [0, 0].
		const node = previewTimeWindowNode(COMPONENT);

		assert.ok(node, `Preview-Call mit time_window in CompareTabs.svelte nicht gefunden`);
		assert.equal(
			node!.type,
			'ArrayExpression',
			`time_window muss ein Literal-Array sein, ist: ${describeNode(node)}`
		);

		const values = node!.elements.map((e: any) => (e?.type === 'Literal' ? e.value : describeNode(e)));
		assert.deepEqual(
			values,
			[0, 23],
			`RED: Vorschau schickt time_window=${describeNode(node)} statt [0, 23]. Bei einem nach ` +
				`#1268 neu angelegten Vergleich sind hour_from/hour_to = 0 → die Vorschau liefe leer ` +
				`(Spec #1268 AC-11).`
		);
	});

	test('der Preview-Call liest weder preset.hour_from noch preset.hour_to', () => {
		// Regressionsanker: auch keine indirekte Wiedereinfuehrung ueber Variablen.
		const node = previewTimeWindowNode(COMPONENT);
		const rendered = describeNode(node);
		for (const forbidden of ['hour_from', 'hour_to']) {
			assert.ok(
				!rendered.includes(forbidden),
				`time_window bezieht weiterhin "${forbidden}" ein: ${rendered}`
			);
		}
	});
});
