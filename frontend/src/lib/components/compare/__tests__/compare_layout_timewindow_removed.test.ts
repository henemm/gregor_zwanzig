// TDD RED — Issue #1268 (AC-1/AC-2): Der Ortsvergleich-Editor rendert im
// Layout-Tab keine Zeitfenster-Eingabefelder, keinen Horizont-Select und keine
// zugehoerigen Info-Kacheln mehr.
//
// Spec: docs/specs/modules/issue_1268_compare_timewindow_removal.md § AC-1/AC-2
//
// --- Warum AST statt DOM-Mount (bewusste Entscheidung, kein Dateiinhalt-Grep) ---
// Dieses Repo hat KEIN vitest / jsdom / @testing-library/svelte (package.json:
// "test": "node --experimental-strip-types --test"). Ein echter DOM-Mount ist
// hier strukturell nicht moeglich; ein SSR-Render via svelte/server scheitert an
// der ungeloesten $lib-/shadcn-Import-Kette (bits-ui) — dafuer waere Vite noetig.
//
// Statt eines Text-Greps (`assert src.includes('...')` — laut CLAUDE.md als
// Verhaltensnachweis verboten, weil er in Kommentaren/Strings falsch anschlaegt
// und Templating uebersieht) parst dieser Test die Komponente mit dem ECHTEN
// Svelte-5-Compiler und inspiziert den Template-AST: welche Elemente traegt das
// Fragment und mit welchem `data-testid`/`testid`?
//
// Das ist ein struktureller Beweis ueber das Renderbare, kein String-Vergleich:
// Ein Testid, das im Template-AST als Attribut nicht existiert, KANN von dieser
// Komponente nicht gerendert werden. Auskommentierter Code taucht im AST nicht
// auf (kein False-Green), ein anders formatiertes Attribut sehr wohl (kein
// False-Red). Ergaenzend deckt Playwright gegen Staging das echte DOM ab.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_layout_timewindow_removed.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

const here = dirname(fileURLToPath(import.meta.url));
const COMPONENT = join(here, '..', 'CompareInhaltSection.svelte');

/** Sammelt alle im Template-AST vergebenen Testids (data-testid an Elementen,
 *  testid-Prop an Svelte-Komponenten wie ChannelToggle/Select). */
function renderedTestids(file: string): string[] {
	const ast = parse(readFileSync(file, 'utf-8'), { modern: true }) as any;
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

	visit(ast.fragment);
	return found;
}

// Die Testids, die laut Spec verschwinden muessen.
const REMOVED_TESTIDS = [
	'compare-step5-time-window-start',
	'compare-step5-time-window-end',
	'compare-step5-forecast-hours',
	'compare-step5-timewindow-tile',
	'compare-step5-horizon-tile'
];

// AC-7-Regressionsanker: diese Felder MUESSEN erhalten bleiben.
const KEPT_TESTIDS = [
	'compare-step5-topn',
	'compare-step5-hourly-metrics',
	'compare-step5-official-alerts-toggle',
	'compare-step5-hourly-enabled-toggle',
	'compare-step5-schedule-tile'
];

describe('#1268 AC-1/AC-2: Zeitfenster-/Horizont-Felder im Layout-Tab', () => {
	for (const testid of REMOVED_TESTIDS) {
		test(`AC-1/AC-2: CompareInhaltSection rendert "${testid}" nicht mehr`, () => {
			// GIVEN: der Ortsvergleich-Editor-Layout-Tab (CompareInhaltSection)
			// WHEN: die Komponente gerendert wird (Template-AST = das Renderbare)
			// THEN: das verworfene Zeitfenster-/Horizont-Testid existiert nicht
			// RED vor Fix: Feld ist noch im Template → Assertion schlaegt fehl.
			const ids = renderedTestids(COMPONENT);
			assert.ok(
				!ids.includes(testid),
				`CompareInhaltSection.svelte rendert weiterhin "${testid}" — laut Spec #1268 ` +
					`ist das Feld ersatzlos zu entfernen (nicht nur zu verstecken). ` +
					`Gerenderte Testids: ${ids.join(', ')}`
			);
		});
	}

	test('AC-1: keine Zeitfenster-Validierungsmeldung mehr, wenn es kein Zeitfenster gibt', () => {
		// GIVEN: die Zeitfenster-Inputs entfallen samt hasTimeOverlap-Derived
		// WHEN: die Komponente gerendert wird
		// THEN: auch der zugehoerige Fehlertext ist weg (kein verwaister Zweig)
		// RED vor Fix: das Testid existiert noch.
		const ids = renderedTestids(COMPONENT);
		assert.ok(
			!ids.includes('compare-step5-time-overlap-error'),
			'CompareInhaltSection.svelte rendert weiterhin "compare-step5-time-overlap-error" — ' +
				'die Validierung gehoert zu den entfernten Zeitfenster-Inputs (hasTimeOverlap-Derived).'
		);
	});

	for (const testid of KEPT_TESTIDS) {
		test(`AC-7 (Regressionsanker): "${testid}" bleibt erhalten`, () => {
			// GIVEN: Top-N, Stundenverlauf-Metriken, Inhalt-Toggles, Versand-Kachel
			// WHEN: der Layout-Tab nach dem Fix gerendert wird
			// THEN: diese Felder sind unveraendert vorhanden (nichts mitgerissen)
			// Erwartet GRUEN vor UND nach dem Fix — sichert gegen Kollateralschaden.
			const ids = renderedTestids(COMPONENT);
			assert.ok(
				ids.includes(testid),
				`CompareInhaltSection.svelte rendert "${testid}" nicht mehr — AC-7 verlangt, ` +
					`dass dieses Feld beim Entfernen von Zeitfenster/Horizont unangetastet bleibt.`
			);
		});
	}
});
