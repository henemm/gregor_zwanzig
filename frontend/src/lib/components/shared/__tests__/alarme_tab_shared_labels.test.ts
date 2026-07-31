// TDD RED — #1401 Scheibe B, Teil 2: die Alarme-Tabelle (`AlertMetricLevelTable
// .svelte`) vergibt Metrik-Namen heute ueber eine LOKALE Konstante
// `METRIC_LABELS`, die von der eigentlich zustaendigen, breiter genutzten
// SSoT-Kandidatin `alertMetricLabels.ts::ALERT_METRIC_LABELS` divergiert
// (z.B. "Temperatursturz" vs. "Temperaturänderung"). Da die Komponente von
// `alerts-tab/AlertsTab.svelte` (Trip) UND `shared/AlarmeTab.svelte`
// (context="route"|"vergleich") gemeinsam eingebunden wird, wirkt jede
// Divergenz in BEIDEN Kontexten gleichzeitig — die Behebung ist der Wegfall
// der lokalen Zweitquelle zugunsten von `ALERT_METRIC_LABELS`.
// Spec: docs/specs/modules/fix_1401b_register_stundenverlauf_alarme.md AC-5/AC-6
//
// Struktur-/AST-Test (kein Dateiinhalt-Grep als Verhaltensnachweis), Vorbild:
//   shared/__tests__/compare_hourly_layout_controls_structure.test.ts
//   shared/__tests__/officialAlertLegend.test.ts (F003, $effect-Block-Analyse)
//
// RED heute: `AlertMetricLevelTable.svelte` deklariert noch eine eigene
// `METRIC_LABELS`-Konstante und importiert `ALERT_METRIC_LABELS` nicht.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/alarme_tab_shared_labels.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

const here = dirname(fileURLToPath(import.meta.url));
const TABLE_COMPONENT = join(here, '..', '..', 'alerts-tab', 'AlertMetricLevelTable.svelte');
const ALARME_TAB = join(here, '..', 'AlarmeTab.svelte');

function parseTableComponent(): any {
	const src = readFileSync(TABLE_COMPONENT, 'utf-8');
	return parse(src, { modern: true });
}

function instanceBody(ast: any): any[] {
	return ast.instance?.content?.body ?? [];
}

describe('#1401b AC-5/AC-6: AlertMetricLevelTable liest Labels aus dem geteilten Register statt aus eigener Liste', () => {
	test('Keine lokale `METRIC_LABELS`-Konstante mehr im Instance-Script', () => {
		const ast = parseTableComponent();
		const body = instanceBody(ast);
		const localMetricLabels = body
			.flatMap((stmt: any) => (stmt.type === 'VariableDeclaration' ? stmt.declarations : []))
			.find((decl: any) => decl.id?.type === 'Identifier' && decl.id.name === 'METRIC_LABELS');
		assert.equal(
			localMetricLabels,
			undefined,
			'AlertMetricLevelTable.svelte deklariert weiterhin eine eigene `METRIC_LABELS`-Konstante ' +
				'— das ist genau die Zweitquelle, die gegenüber alertMetricLabels.ts divergieren kann ' +
				'(#1401b AC-5). Sie muss entfallen; das Label kommt aus `ALERT_METRIC_LABELS`.'
		);
	});

	test('Instance-Script importiert `ALERT_METRIC_LABELS` aus dem geteilten Util-Modul', () => {
		const ast = parseTableComponent();
		const body = instanceBody(ast);
		const importsAlertMetricLabels = body.some(
			(stmt: any) =>
				stmt.type === 'ImportDeclaration' &&
				/alertMetricLabels/.test(stmt.source?.value ?? '') &&
				(stmt.specifiers ?? []).some(
					(spec: any) => spec.imported?.name === 'ALERT_METRIC_LABELS'
				)
		);
		assert.ok(
			importsAlertMetricLabels,
			'AlertMetricLevelTable.svelte importiert `ALERT_METRIC_LABELS` nicht aus ' +
				'`$lib/utils/alertMetricLabels` — ohne diesen Import kann die Komponente nicht aus dem ' +
				'geteilten Register lesen (#1401b AC-5/AC-6, betrifft Trip UND Vergleich gleichzeitig, ' +
				'da AlertMetricLevelTable von beiden Kontexten eingebunden wird).'
		);
	});
});

// AC-6, zweiter Teil (nachgezogen in Adversary-Runde 1): der Nachweis oben
// zeigt nur, dass die Tabelle SELBST nicht zwischen den Kontexten unterscheiden
// kann. Er sagt nichts darueber, ob der Aufrufer sie zweimal einbindet — genau
// das waere der Verstoss gegen die Trip/Compare-Teilungs-Invariante
// (Anti-Pattern-Referenz #1170: Compare-Pendant "analog Trip" nachgebaut statt
// geteilt). Hier wird deshalb der Aufrufer geprueft.

function parseAlarmeTab(): any {
	return parse(readFileSync(ALARME_TAB, 'utf-8'), { modern: true });
}

/** Alle Vorkommen einer Komponente im Template, je mit der Kette der
 *  IfBlock-Bedingungen, unter denen sie steht. */
function componentUsages(
	fragment: unknown,
	componentName: string
): { node: any; ancestorTests: any[] }[] {
	const found: { node: any; ancestorTests: any[] }[] = [];
	function visit(node: unknown, ancestors: any[]): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach((c) => visit(c, ancestors));
			return;
		}
		const n = node as Record<string, any>;
		if (n.type === 'Component' && n.name === componentName) {
			found.push({ node: n, ancestorTests: ancestors });
		}
		const nextAncestors = n.type === 'IfBlock' ? [...ancestors, n.test] : ancestors;
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key], nextAncestors);
		}
	}
	visit(fragment, []);
	return found;
}

function identifierNames(subtree: unknown): Set<string> {
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

describe('#1401b AC-6: AlarmeTab bindet die Alarm-Tabelle EINMAL fuer beide Kontexte ein', () => {
	test('Genau eine Einbindung von AlertMetricLevelTable im Template', () => {
		const usages = componentUsages(parseAlarmeTab().fragment, 'AlertMetricLevelTable');
		assert.equal(
			usages.length,
			1,
			`AlarmeTab.svelte bindet AlertMetricLevelTable ${usages.length}-mal ein. Mehr als eine ` +
				'Einbindung heisst: Trip und Vergleich koennten unterschiedliche Beschriftungen ' +
				'zeigen (#1401b AC-6, Teilungs-Invariante).'
		);
	});

	test('Genau ein Import der Komponente (kein zweites Compare-Pendant)', () => {
		const body = instanceBody(parseAlarmeTab());
		const imports = body.filter(
			(stmt: any) =>
				stmt.type === 'ImportDeclaration' && /AlertMetricLevelTable/.test(stmt.source?.value ?? '')
		);
		assert.equal(imports.length, 1);
		const localNames = imports.flatMap((i: any) =>
			(i.specifiers ?? []).map((s: any) => s.local?.name)
		);
		assert.deepEqual(localNames, ['AlertMetricLevelTable']);
	});

	test('Die Einbindung steht in KEINEM context-abhaengigen Zweig', () => {
		const usages = componentUsages(parseAlarmeTab().fragment, 'AlertMetricLevelTable');
		assert.equal(usages.length, 1);
		const gateIdentifiers = new Set(
			usages[0].ancestorTests.flatMap((t) => [...identifierNames(t)])
		);
		assert.equal(
			gateIdentifiers.has('context'),
			false,
			'Die Alarm-Tabelle steht unter einer `context`-Bedingung — dann gaebe es doch wieder ' +
				'zwei Pfade fuer Trip und Vergleich (#1401b AC-6).'
		);
	});

	test('Beide Kontexte speisen dieselben Bindungspfade (activeMetrics/levels/onLevelChange)', () => {
		const usages = componentUsages(parseAlarmeTab().fragment, 'AlertMetricLevelTable');
		const attrs = (usages[0].node.attributes ?? [])
			.filter((a: any) => a.type === 'Attribute')
			.map((a: any) => a.name)
			.sort();
		assert.deepEqual(attrs, ['activeMetrics', 'levels', 'onLevelChange']);

		// Die Kontext-Unterscheidung passiert ausschliesslich VOR der Komponente,
		// in den abgeleiteten Werten — nicht in einer zweiten Einbindung.
		const body = instanceBody(parseAlarmeTab());
		const derivedNames = body
			.flatMap((stmt: any) => (stmt.type === 'VariableDeclaration' ? stmt.declarations : []))
			.map((d: any) => d.id?.name)
			.filter(Boolean);
		for (const name of ['effectiveActiveMetrics', 'effectiveMetricLevels']) {
			assert.ok(derivedNames.includes(name), `Abgeleiteter Wert \`${name}\` fehlt.`);
		}
	});
});
