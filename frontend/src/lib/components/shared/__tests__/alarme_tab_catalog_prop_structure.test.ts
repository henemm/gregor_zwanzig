// TDD RED — Feature #1435 Etappe E1a-2, Strukturnachweise (AC-5, AC-7, AC-8).
// Spec: docs/specs/modules/feat_1435_e1a2_alarme_reiter_register.md
//
// Warum AST statt DOM: dieses Repo hat kein vitest/jsdom (package.json
// "test": node --test). Statt eines verbotenen Dateiinhalt-Greps parst dieser
// Test die Komponenten mit dem ECHTEN Svelte-5-Compiler und inspiziert den
// AST. Vorbild: shared/__tests__/weather_metrics_tab_compare_catalog_fetch.test.ts
//
// Alle Pfade werden relativ zu DIESER Datei aufgeloest (Pfadregel #1409) —
// ein fester Hauptrepo-Pfad wuerde aus dem Worktree die unveraenderte
// Hauptrepo-Kopie pruefen und falsches Gruen melden.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/alarme_tab_catalog_prop_structure.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

const here = dirname(fileURLToPath(import.meta.url));
const ALARME_TAB = join(here, '..', 'AlarmeTab.svelte');
const OLD_MAPPING = join(here, '..', 'alarme-tab', 'compareMetricMapping.ts');
// Alle Flaechen, die den Alarme-Reiter im Vergleichs-Kontext einbetten.
const COMPARE_MOUNTS = [
	join(here, '..', '..', 'compare', 'CompareTabs.svelte'),
	join(here, '..', '..', 'compare-new', 'CompareNewEditor.svelte')
];

function parseFile(path: string): any {
	return parse(readFileSync(path, 'utf-8'), { modern: true });
}

/** Alle Identifier-Namen eines AST-Subtrees. */
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

/** Der `$derived(...)`-Initialisierer einer benannten Instanz-Variable. */
function derivedInit(ast: any, name: string): any {
	const decl = (ast.instance?.content?.body ?? [])
		.filter((n: any) => n.type === 'VariableDeclaration')
		.flatMap((n: any) => n.declarations)
		.find((d: any) => d.id?.type === 'Identifier' && d.id.name === name);
	assert.ok(decl, `Keine Variable \`${name}\` im Instance-Script gefunden.`);
	assert.equal(decl.init?.type, 'CallExpression');
	assert.equal(decl.init.callee?.name, '$derived');
	return decl.init.arguments[0];
}

/** Namen der tatsaechlich destrukturierten `$props()`-Felder. */
function propNames(ast: any): string[] {
	const decl = (ast.instance?.content?.body ?? [])
		.filter((n: any) => n.type === 'VariableDeclaration')
		.flatMap((n: any) => n.declarations)
		.find((d: any) => d.id?.type === 'ObjectPattern');
	assert.ok(decl, 'Kein `let { ... } = $props()` gefunden.');
	return decl.id.properties.map((p: any) => p.key?.name).filter(Boolean);
}

/** Alle Komponenten-Instanzen eines Namens im Template. */
function componentInstances(ast: any, name: string): any[] {
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
	visit(ast.fragment);
	return found;
}

/** Statischer Attributwert (`context="vergleich"`) — sonst null. */
function staticAttr(instance: any, attr: string): string | null {
	const a = (instance.attributes ?? []).find(
		(x: any) => x.type === 'Attribute' && x.name === attr
	);
	if (!a) return null;
	if (Array.isArray(a.value)) {
		return a.value.map((v: any) => v.data ?? v.raw ?? '').join('');
	}
	return typeof a.value === 'string' ? a.value : null;
}

function hasAttr(instance: any, attr: string): boolean {
	return (instance.attributes ?? []).some((x: any) => x.type === 'Attribute' && x.name === attr);
}

describe('#1435 E1a-2 AC-8: die handgepflegte Zuordnungs-Liste ist weg', () => {
	test('`alarme-tab/compareMetricMapping.ts` existiert nicht mehr', () => {
		assert.equal(
			existsSync(OLD_MAPPING),
			false,
			`Die alte Frontend-Liste liegt noch unter ${OLD_MAPPING} — solange sie da ist, ` +
				'kann die Zuordnung Wetter-Groesse → Alarm-Zeile weiter am Register vorbei ' +
				'gepflegt werden (Ratsche gegen Nachwachsen, #1435 AC-8).'
		);
	});

	test('`AlarmeTab.svelte` importiert nichts mehr aus dieser Datei', () => {
		const ast = parseFile(ALARME_TAB);
		const sources: string[] = (ast.instance?.content?.body ?? [])
			.filter((n: any) => n.type === 'ImportDeclaration')
			.map((n: any) => String(n.source.value));
		const treffer = sources.filter((s) => s.includes('compareMetricMapping'));
		assert.deepEqual(
			treffer,
			[],
			`AlarmeTab.svelte importiert weiterhin aus der geloeschten Liste: ${treffer.join(', ')}`
		);
	});
});

describe('#1435 E1a-2 AC-5: der Katalog kommt als Prop herein, nicht als Modul-Getter', () => {
	test('AlarmeTab nimmt eine `catalog`-Prop entgegen', () => {
		const props = propNames(parseFile(ALARME_TAB));
		assert.ok(
			props.includes('catalog'),
			'AlarmeTab.svelte destrukturiert keine `catalog`-Prop — ohne Uebergabewert ' +
				`bliebe nur der nicht-reaktive Modul-Getter (AC-5). Ist: ${props.join(', ')}`
		);
	});

	test('Der Vergleichs-Zweig rechnet mit der Prop, nicht mit dem Modul-Getter', () => {
		const cond = derivedInit(parseFile(ALARME_TAB), 'effectiveActiveMetrics');
		assert.equal(cond.type, 'ConditionalExpression');
		const namen = identifiers(cond.consequent);

		assert.ok(
			namen.has('deriveActiveAlertMetricsFromCatalog'),
			'Der Vergleichs-Zweig ruft die register-gestuetzte Ableitung nicht auf (AC-1/AC-5).'
		);
		assert.ok(
			namen.has('catalog'),
			'Der Vergleichs-Zweig liest den Katalog nicht aus der Prop `catalog` (AC-5).'
		);
		assert.equal(
			namen.has('registeredCompareMetricCatalog'),
			false,
			'Der Vergleichs-Zweig schlaegt den Katalog ueber den Modul-Getter nach — der ist ' +
				'nicht reaktiv, ein spaeteres Laden wuerde die Tabelle nicht aktualisieren ' +
				'(AC-5, Fehlerklasse #1320).'
		);
		assert.equal(
			namen.has('deriveActiveAlertMetrics'),
			false,
			'Der Vergleichs-Zweig nutzt weiterhin die alte Ableitung aus der geloeschten Liste.'
		);
	});

	test('Jede Vergleichs-Einbettung reicht den geladenen Katalog durch', () => {
		for (const mount of COMPARE_MOUNTS) {
			const ast = parseFile(mount);
			const instanzen = componentInstances(ast, 'AlarmeTab').filter(
				(i) => staticAttr(i, 'context') === 'vergleich'
			);
			assert.ok(
				instanzen.length >= 1,
				`Keine <AlarmeTab context="vergleich"> in ${mount} gefunden.`
			);
			for (const inst of instanzen) {
				assert.ok(
					hasAttr(inst, 'catalog'),
					`<AlarmeTab context="vergleich"> in ${mount} bekommt kein \`catalog\`-Attribut — ` +
						'die Empfindlichkeits-Tabelle bliebe dort leer, obwohl Metriken aktiv sind ' +
						'(AC-5, Fehlerklasse #1320).'
				);
			}
		}
	});

	test('Regressionsschutz: der Reiter wird erst nach dem Hydrieren gemountet', () => {
		// `alarmeHydrated` wird erst NACH dem Aufloesen von
		// `loadCompareSelectionEntries()` wahr — dadurch ist der Katalog beim
		// ersten Rendern bereits da (Spec Implementation Details Punkt 3).
		//
		// Fix-Loop 1 (Adversary F001): geprueft wird JEDE Einbettung, nicht nur
		// COMPARE_MOUNTS[0]. Die Anlege-Seite mountete den Reiter ungeschuetzt
		// hinter `{:else if activeTab === 'alarme'}` — wer ihn erreicht, bevor
		// der Fetch aufgeloest ist, sieht faelschlich "keine Metriken" (AC-5
		// sagt "zu keinem Zeitpunkt … auch nicht kurzzeitig", Fehlerklasse #1320).
		for (const mount of COMPARE_MOUNTS) {
			const ast = parseFile(mount);
			// Jede AlarmeTab-Instanz einzeln erfassen: EINE geschuetzte Einbettung
			// darf eine zweite, ungeschuetzte in derselben Datei nicht decken.
			const ungated: number[] = [];
			let seen = 0;
			function visit(node: unknown, inHydrateGate: boolean): void {
				if (node === null || typeof node !== 'object') return;
				if (Array.isArray(node)) {
					node.forEach((c) => visit(c, inHydrateGate));
					return;
				}
				const n = node as Record<string, any>;
				let next = inHydrateGate;
				if (n.type === 'IfBlock') next = inHydrateGate || identifiers(n.test).has('alarmeHydrated');
				if (n.type === 'Component' && n.name === 'AlarmeTab') {
					seen += 1;
					if (!next) ungated.push(seen);
				}
				for (const key of Object.keys(n)) {
					if (key === 'parent') continue;
					visit(n[key], next);
				}
			}
			visit(ast.fragment, false);

			assert.ok(seen >= 1, `Keine <AlarmeTab> in ${mount} gefunden.`);
			assert.deepEqual(
				ungated,
				[],
				`In ${mount} liegen ${ungated.length} von ${seen} <AlarmeTab>-Einbettungen NICHT ` +
					'hinter `{#if alarmeHydrated}` — dort kann der Reiter vor dem Laden des ' +
					'Katalogs rendern und zeigt faelschlich "keine Metriken" (AC-5, #1320).'
			);
		}
	});
});

describe('#1435 E1a-2 AC-7: der Touren-Zweig bleibt unberuehrt', () => {
	test('`context="route"` liest ausschliesslich die `activeMetrics`-Prop', () => {
		const cond = derivedInit(parseFile(ALARME_TAB), 'effectiveActiveMetrics');
		const namen = identifiers(cond.alternate);

		assert.ok(
			namen.has('activeMetrics'),
			'Der Touren-Zweig liest nicht mehr die `activeMetrics`-Prop (AC-7).'
		);
		for (const verboten of [
			'catalog',
			'deriveActiveAlertMetricsFromCatalog',
			'registeredCompareMetricCatalog',
			'wiz'
		]) {
			assert.equal(
				namen.has(verboten),
				false,
				`Der Touren-Zweig zieht \`${verboten}\` heran — fuer Touren darf sich inhaltlich ` +
					'nichts aendern (AC-7, geteilter Baustein, Anti-Pattern #1170).'
			);
		}
	});

	test('Die Trip-Einbettung bleibt unveraendert (kein Katalog, keine neuen Attribute)', () => {
		const ast = parseFile(join(here, '..', '..', 'trip-detail', 'AlarmeScheduleTab.svelte'));
		const instanzen = componentInstances(ast, 'AlarmeTab');
		assert.ok(instanzen.length >= 1, 'Keine <AlarmeTab> in AlarmeScheduleTab.svelte gefunden.');
		for (const inst of instanzen) {
			assert.equal(staticAttr(inst, 'context'), 'route');
			assert.equal(
				hasAttr(inst, 'catalog'),
				false,
				'Die Trip-Einbettung reicht einen Katalog durch — der Touren-Zweig braucht ' +
					'keinen und darf sich durch diese Etappe nicht bewegen (AC-7).'
			);
			assert.deepEqual(
				(inst.attributes ?? []).map((a: any) => a.name).sort(),
				[
					'activeMetrics',
					'context',
					'existingChannelThresholds',
					'existingChannels',
					'metricLevels',
					'onTripUpdate',
					'saveController',
					'trip'
				],
				// Issue #1461 S3b-2a: legitime Erweiterung um
				// `existingChannelThresholds` (Kanal-Schwelle, route-Speicherweg) --
				// diese Zusicherung bewacht weiterhin, dass KEIN Katalog-Attribut
				// (#1435-Scope) den Touren-Zweig erreicht.
				'Die Attribut-Liste der Trip-Einbettung hat sich unerwartet geaendert (AC-7).'
			);
		}
	});
});
