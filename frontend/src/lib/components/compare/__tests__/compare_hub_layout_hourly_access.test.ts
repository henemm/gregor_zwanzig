// TDD RED — Issue #1299/#1291/#1287 (Scheibe C2 von Epic #1301): Der Hub-
// Layout-Tab (CompareTabs.svelte) muss die Stundenverlauf-Metriken-Checkboxen
// und den "Stundenverlauf ein/aus"-Schalter selbst rendern — die bisherige
// Steuerung lebt nur in `CompareInhaltSection.svelte`, die vom weggeleiteten
// `CompareEditor` (Route ist reiner Redirect-Platzhalter seit Slice S3) und
// damit vom erreichbaren Hub aus nicht mehr benutzbar ist.
//
// Spec: docs/specs/modules/compare_hub_hourly_metrics.md § AC-1, AC-4
//
// --- Warum AST statt DOM-Mount (bewusste Entscheidung, kein Dateiinhalt-Grep) ---
// Dieses Repo hat KEIN vitest / jsdom / @testing-library/svelte (package.json:
// "test": "node --experimental-strip-types --test"). Ein echter DOM-Mount ist
// hier strukturell nicht moeglich; ein SSR-Render via svelte/server scheitert
// an der ungeloesten $lib-/shadcn-Import-Kette (bits-ui) — dafuer waere Vite
// noetig. Statt eines Text-Greps ueber den gesamten Dateiinhalt (laut CLAUDE.md
// als Verhaltensnachweis verboten) parst dieser Test die Komponente mit dem
// ECHTEN Svelte-5-Compiler und inspiziert den Template-AST.
//
// Isolation auf das Layout-Tab-Panel-Fragment: der Test findet zunaechst das
// `IfBlock`-AST-Knoten mit dem Test-Ausdruck `activeTab === 'layout'` (der
// gesamte Tab-Panel-Bereich, der nur bei aktivem Layout-Tab gerendert wird)
// und sammelt Testids NUR aus dessen `consequent`-Fragment. Damit prueft der
// Test wirklich nur das Layout-Panel, nicht versehentlich ein Testid aus
// einem anderen Tab (z. B. Wetter-Metriken oder Alarme). Isolierung war in
// der Praxis unkompliziert (der Compare-Compiler liefert ein klar
// identifizierbares BinaryExpression-Testfeld je Top-Level-Tab-IfBlock) — ein
// Fallback auf den Gesamtdatei-AST war nicht noetig.
//
// --- Nachbesserung (Epic #1301 Scheibe C2, B3-Anti-Pattern-Haertung) ---
// Der urspruengliche AC-1-Test suchte 9 fixe literale
// `compare-layout-hourly-metric-<key>`-Testids im Panel-AST. Das erzwang in
// der Komponente genau die Hand-Unrollung, die B3 (Epic #1301) an anderer
// Stelle bereits als Anti-Pattern bekaempft: eine 10. Metrik in
// `ALL_HOURLY_METRICS` haette den Test weiterhin gruen gelassen, ohne dass im
// UI je eine Checkbox dafuer erscheint — der Katalog und das Gerenderte
// koennen stumm auseinanderlaufen. Der Test prueft jetzt STRUKTURELL, dass im
// Layout-Panel eine `{#each ALL_HOURLY_METRICS as metric}`-Schleife (Ausdruck
// referenziert exakt den Identifier `ALL_HOURLY_METRICS`, kein Zwischen-Array)
// eine `ChannelToggle`-Checkbox mit einem `testid`-Template-Literal erzeugt,
// das mit dem Praefix `compare-layout-hourly-metric-` beginnt und `metric.key`
// interpoliert. Damit folgt „fuer JEDEN Katalog-Eintrag existiert eine
// Checkbox" aus der Schleifen-Konstruktion selbst (eine Schleife ueber N
// Eintraege erzeugt IMMER N Checkboxen), statt aus einer Zaehlung fixer
// Literale, die bei einer Katalog-Erweiterung nicht mitwaechst. Ein
// Vakuum-Schutz (`ALL_HOURLY_METRICS.length >= 1`) verhindert, dass ein leerer
// Katalog den Test trivial bestehen liesse.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_hub_layout_hourly_access.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

import { ALL_HOURLY_METRICS } from '../compareHourlyMetricDefs.ts';

const here = dirname(fileURLToPath(import.meta.url));
const COMPONENT = join(here, '..', 'CompareTabs.svelte');

/** Findet im Template-AST das IfBlock-Fragment fuer `activeTab === '<tabValue>'`
 * (Top-Level-Tab-Panel-Verzweigung) und liefert dessen `consequent`-Fragment.
 * Liefert `null`, wenn kein passendes IfBlock gefunden wird (Isolations-Fallback
 * s. Kopfkommentar). */
function findTabPanelFragment(ast: unknown, tabValue: string): unknown {
	let found: unknown = null;
	function visit(node: unknown): void {
		if (found !== null) return;
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visit);
			return;
		}
		const n = node as Record<string, any>;
		if (
			n.type === 'IfBlock' &&
			n.test?.type === 'BinaryExpression' &&
			n.test.operator === '===' &&
			n.test.left?.type === 'Identifier' &&
			n.test.left.name === 'activeTab' &&
			n.test.right?.value === tabValue
		) {
			found = n.consequent;
			return;
		}
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(ast);
	return found;
}

/** Sammelt alle im Template-AST-Subtree vergebenen Testids (data-testid an
 *  Elementen, testid-Prop an Svelte-Komponenten wie ChannelToggle). */
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

/** Sammelt alle Text-Node-Inhalte im Subtree (fuer Label-Abwesenheits-Check
 *  AC-4 — strukturell ueber Text-AST-Knoten, kein Dateiinhalt-Grep). */
function renderedTexts(subtree: unknown): string[] {
	const found: string[] = [];
	function visit(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visit);
			return;
		}
		const n = node as Record<string, any>;
		if (n.type === 'Text' && typeof n.data === 'string' && n.data.trim().length > 0) {
			found.push(n.data.trim());
		}
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(subtree);
	return found;
}

/** Findet im Subtree jeden `EachBlock`, dessen Iterations-Ausdruck EXAKT der
 *  Identifier `identifierName` ist (kein Zwischen-Array, keine Methodenkette
 *  wie `.filter()` — die Checkbox-Menge muss 1:1 aus dem Katalog kommen). */
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

/** Findet im Subtree jede Svelte-Komponenten-Instanz mit dem gegebenen Namen
 *  (z. B. `ChannelToggle`). */
function findComponents(subtree: unknown, componentName: string): any[] {
	const found: any[] = [];
	function visit(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visit);
			return;
		}
		const n = node as Record<string, any>;
		if (n.type === 'Component' && n.name === componentName) {
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

/** Prueft, ob eine Komponente ein `testid`-Attribut traegt, dessen Wert ein
 *  Template-Literal ist, das mit `prefix` beginnt und eine `metric.key`-
 *  MemberExpression interpoliert (AST-Beweis fuer
 *  `` `compare-layout-hourly-metric-${metric.key}` `` statt eines fixen
 *  Literal-Strings). */
function hasKeyedTestidTemplate(component: any, prefix: string, memberObjectName: string, memberPropertyName: string): boolean {
	for (const attr of component.attributes ?? []) {
		if (attr.type !== 'Attribute' || attr.name !== 'testid') continue;
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
		if (startsWithPrefix && hasMemberExpr) return true;
	}
	return false;
}

function parseComponent(): unknown {
	return parse(readFileSync(COMPONENT, 'utf-8'), { modern: true });
}

describe('C2 AC-1: Hub-Layout-Tab rendert Stundenverlauf-Checkboxen + Toggle', () => {
	test('ALL_HOURLY_METRICS liefert mindestens einen Katalog-Eintrag (Vakuum-Schutz)', () => {
		// GIVEN: der Katalog der waehlbaren Stundenverlauf-Metriken
		// WHEN: er importiert wird
		// THEN: mindestens 1 Eintrag — ohne diese Bedingung wuerde eine leere Liste
		// den strukturellen Schleifen-Beweis unten trivial (aber sinnlos) bestehen
		// lassen. Bewusst KEINE exakte Zahl mehr (frueher `=== 9`): die Testids
		// werden jetzt nicht mehr einzeln gezaehlt, sondern folgen strukturell aus
		// der Schleife (s. Kopfkommentar "Nachbesserung").
		assert.ok(ALL_HOURLY_METRICS.length >= 1);
	});

	// Epic #1301 Scheibe F2a: Die Stundenverlauf-Steuerung (Schleife ueber
	// ALL_HOURLY_METRICS + enabled-Toggle) wurde aus dem Hub-Inline-Markup in die
	// GETEILTE Komponente shared/CompareHourlyLayoutControls.svelte extrahiert
	// (Hub + Anlege-Seite /compare/new teilen sie). Der Hub mountet sie jetzt nur
	// noch — der strukturelle Anti-Hand-Kopie-Beweis (`{#each ALL_HOURLY_METRICS}`
	// + `compare-layout-hourly-metric-${metric.key}` + enabled-Toggle) liegt jetzt
	// im Struktur-Test der Komponente
	// (shared/__tests__/compare_hourly_layout_controls_structure.test.ts). Hier
	// bleibt die aequivalente Zusicherung: das Hub-Layout-Panel mountet die
	// geteilte Komponente (und rollt die Metrik-Liste NICHT selbst hand-kopiert
	// aus — das faengt der Negativ-Guard ALL_HOURLY_METRICS.length unten ab).
	test('AC-1: Layout-Tab-Panel mountet die geteilte CompareHourlyLayoutControls-Komponente', () => {
		// GIVEN: das Hub-Layout-Tab-Panel-Fragment (activeTab === 'layout')
		// WHEN: die Komponente geparst wird (Template-AST = das Renderbare)
		// THEN: im Panel existiert genau eine <CompareHourlyLayoutControls>-Instanz
		// (die extrahierte Stundenverlauf-Steuerung). Die Schleife/Testids selbst
		// werden im Struktur-Test der Komponente geprueft.
		const ast = parseComponent();
		const panel = findTabPanelFragment((ast as any).fragment, 'layout');
		assert.ok(panel, 'Layout-Tab-Panel-IfBlock (activeTab === "layout") nicht gefunden');

		const mounts = findComponents(panel, 'CompareHourlyLayoutControls');
		assert.ok(
			mounts.length >= 1,
			'CompareTabs.svelte Layout-Panel mountet die geteilte Komponente ' +
				'<CompareHourlyLayoutControls> nicht — Spec F2a AC-7 verlangt die geteilte ' +
				'Stundenverlauf-Steuerung (Extraktion aus dem frueheren Inline-Markup).'
		);

		// Anti-Hand-Kopie-Regression: das Panel darf die Metrik-Liste NICHT wieder
		// selbst inline ausrollen (die Schleife lebt jetzt ausschliesslich in der
		// Komponente). Kein `{#each ALL_HOURLY_METRICS ...}`-Block mehr im Hub-Panel.
		const strayLoops = findEachBlocksOverIdentifier(panel, 'ALL_HOURLY_METRICS');
		assert.equal(
			strayLoops.length,
			0,
			'CompareTabs.svelte Layout-Panel rollt ALL_HOURLY_METRICS wieder inline aus, ' +
				'statt die geteilte Komponente zu nutzen (Doppel-Quelle/Anti-Hand-Kopie).'
		);
	});
});

describe('C2 AC-4: Hub-Layout-Tab OHNE Top-N-Attrappe und OHNE Bucket-Zuordnung (Negativ-Guard)', () => {
	test('AC-4: kein Testid verweist auf "topn" (Anzahl Orte mit stuendlichem Detail)', () => {
		// GIVEN: das Hub-Layout-Tab-Panel-Fragment
		// WHEN: die Komponente geparst wird
		// THEN: kein Testid enthaelt (case-insensitiv) "topn" — die Top-N-Attrappe
		// (#1287) darf im erreichbaren Hub nicht existieren.
		// Erwartet GRUEN bereits heute (Regressionsanker, kein RED-Ziel dieser Datei).
		const ast = parseComponent();
		const panel = findTabPanelFragment((ast as any).fragment, 'layout');
		assert.ok(panel, 'Layout-Tab-Panel-IfBlock (activeTab === "layout") nicht gefunden');
		const ids = renderedTestids(panel);
		const topnIds = ids.filter((id) => id.toLowerCase().includes('topn'));
		assert.deepEqual(
			topnIds,
			[],
			`CompareTabs.svelte Layout-Panel rendert Top-N-Testids, obwohl AC-4 deren Abwesenheit verlangt: ${topnIds.join(', ')}`
		);
	});

	test('AC-4: kein Text/Label "Anzahl Orte mit stündlichem Detail" im Panel', () => {
		// GIVEN: das Hub-Layout-Tab-Panel-Fragment
		// WHEN: die Komponente geparst wird
		// THEN: kein Text-Knoten traegt das alte Top-N-Label.
		// Erwartet GRUEN bereits heute.
		const ast = parseComponent();
		const panel = findTabPanelFragment((ast as any).fragment, 'layout');
		assert.ok(panel, 'Layout-Tab-Panel-IfBlock (activeTab === "layout") nicht gefunden');
		const texts = renderedTexts(panel);
		assert.ok(
			!texts.some((t) => t.includes('Anzahl Orte mit stündlichem Detail')),
			`CompareTabs.svelte Layout-Panel enthaelt weiterhin das Top-N-Label. Texte: ${texts.join(' | ')}`
		);
	});

	test('AC-4: keine "Spalte/Detail"-Bucket-Zuordnung (channel_layouts-Editor) im Panel', () => {
		// GIVEN: das Hub-Layout-Tab-Panel-Fragment
		// WHEN: die Komponente geparst wird
		// THEN: kein Testid verweist auf eine Bucket-/Spalten-Zuordnung
		// ("bucket", "channel-layout"). Erwartet GRUEN bereits heute.
		const ast = parseComponent();
		const panel = findTabPanelFragment((ast as any).fragment, 'layout');
		assert.ok(panel, 'Layout-Tab-Panel-IfBlock (activeTab === "layout") nicht gefunden');
		const ids = renderedTestids(panel);
		const bucketIds = ids.filter(
			(id) => id.toLowerCase().includes('bucket') || id.toLowerCase().includes('channel-layout')
		);
		assert.deepEqual(
			bucketIds,
			[],
			`CompareTabs.svelte Layout-Panel rendert Bucket-/Spalten-Zuordnungs-Testids, obwohl AC-4 deren Abwesenheit verlangt: ${bucketIds.join(', ')}`
		);
	});
});
