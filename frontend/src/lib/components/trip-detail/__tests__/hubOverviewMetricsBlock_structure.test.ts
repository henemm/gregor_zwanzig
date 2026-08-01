// TDD RED — Feature #1435 Etappe E3a: neuer fünfter Block "Wetter-Metriken"
// in `HubOverview.svelte` (Übersichts-Reiter einer Tour).
// Spec: docs/specs/modules/feat_1435_e3a_uebersicht_wetter_block.md
// Belegt: AC-4 (Frontend-Teil), AC-5 (Frontend-Teil), AC-9, AC-10,
// AC-12 (struktureller Teil).
//
// Svelte-Compiler-AST-Prüfung (kein rohes String-Grep) — Vorbild:
// shared/__tests__/alarme_tab_shared_labels.test.ts.
//
// RED heute: `HubOverview.svelte` hat den neuen Block noch nicht — die
// gesuchten Testids/Zweige/Aufrufe existieren schlicht nicht im Baum.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/trip-detail/__tests__/hubOverviewMetricsBlock_structure.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

const here = dirname(fileURLToPath(import.meta.url));
const HUB_OVERVIEW = join(here, '..', 'HubOverview.svelte');
const COMPARE_TABS = join(here, '..', '..', 'compare', 'CompareTabs.svelte');
const SHARED_MODULE = join(here, '..', '..', 'shared', 'trip-metrics', 'tripActiveMetricNames.ts');

function readSrc(path: string): string {
	return readFileSync(path, 'utf-8');
}

function parseSvelte(path: string): { ast: any; src: string } {
	const src = readSrc(path);
	return { ast: parse(src, { modern: true }), src };
}

/** Alle Nodes eines Typs im Baum, tiefensuchend (überspringt `parent`). */
function findAll(node: unknown, type: string): any[] {
	const found: any[] = [];
	function visit(n: unknown): void {
		if (n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) {
			n.forEach(visit);
			return;
		}
		const rec = n as Record<string, any>;
		if (rec.type === type) found.push(rec);
		for (const key of Object.keys(rec)) {
			if (key === 'parent') continue;
			visit(rec[key]);
		}
	}
	visit(node);
	return found;
}

/** Quelltext-Ausdruck eines Attribut-Werts (funktioniert für `{expr}` und Text-Literale). */
function attrExprSource(attr: any, src: string): string {
	const v = attr.value;
	if (Array.isArray(v)) {
		return v
			.map((item: any) =>
				item.type === 'ExpressionTag' ? src.slice(item.expression.start, item.expression.end) : (item.data ?? '')
			)
			.join('');
	}
	if (v && v.type === 'ExpressionTag') {
		return src.slice(v.expression.start, v.expression.end);
	}
	return '';
}

/** Alle data-testid-Werte innerhalb eines Teilbaums. */
function testIdsIn(node: unknown): string[] {
	return findAll(node, 'Attribute')
		.filter((a) => a.name === 'data-testid')
		.map((a) => (Array.isArray(a.value) ? a.value.map((t: any) => t.data ?? '').join('') : ''));
}

/** Findet den ERSTEN IfBlock im Baum, dessen Test-Ausdruck-Quelltext matcht. */
function findIfBlockByTest(node: unknown, src: string, regex: RegExp): any | undefined {
	return findAll(node, 'IfBlock').find((ib) => regex.test(src.slice(ib.test.start, ib.test.end)));
}

/** Die vollständige if/else-if/.../else-Kette ab einem IfBlock, je Glied
 *  { testSrc: string|null, consequent }. `testSrc === null` markiert den
 *  abschließenden `{:else}`-Zweig ohne eigene Bedingung. */
function ifElseChain(rootIfBlock: any, src: string): { testSrc: string | null; consequent: any }[] {
	const chain: { testSrc: string | null; consequent: any }[] = [];
	let current = rootIfBlock;
	while (current) {
		chain.push({ testSrc: src.slice(current.test.start, current.test.end), consequent: current.consequent });
		const alt = current.alternate;
		if (alt && alt.nodes.length === 1 && alt.nodes[0].type === 'IfBlock' && alt.nodes[0].elseif) {
			current = alt.nodes[0];
		} else if (alt) {
			chain.push({ testSrc: null, consequent: alt });
			current = null;
		} else {
			current = null;
		}
	}
	return chain;
}

/** CSS-Klassenlisten aus `class="..."`-Attributen innerhalb eines Teilbaums. */
function classTokensIn(node: unknown): Set<string> {
	const tokens = new Set<string>();
	for (const attr of findAll(node, 'Attribute')) {
		if (attr.name !== 'class') continue;
		const value = Array.isArray(attr.value) ? attr.value.map((t: any) => t.data ?? '').join('') : '';
		for (const token of value.split(/\s+/).filter(Boolean)) tokens.add(token);
	}
	return tokens;
}

/** Alle `@media`-Atrule-Knoten im <style>-CSS-Baum, tiefensuchend. */
function mediaAtrules(cssAst: unknown): any[] {
	return findAll(cssAst, 'Atrule').filter((a) => a.name === 'media');
}

/** Prüft innerhalb eines @media-Knotens, ob eine CSS-Regel existiert, deren
 *  Selektor mindestens eine der übergebenen Klassen trifft UND eine
 *  `display: none`-Deklaration enthält (an beliebiger Position im Block —
 *  nicht nur als erste Deklaration). Liefert die betroffenen Selektor-Texte
 *  (für Fehlermeldungen); leeres Array = kein Treffer. */
function mediaDisplayNoneHits(atrule: any, src: string, classTokens: Set<string>): string[] {
	const hits: string[] = [];
	for (const rule of findAll(atrule.block, 'Rule')) {
		const selectorSrc = src.slice(rule.prelude.start, rule.prelude.end);
		const touchesBlock = [...classTokens].some((cls) =>
			new RegExp(`\\.${cls.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`).test(selectorSrc)
		);
		if (!touchesBlock) continue;
		const hidesDisplay = findAll(rule.block, 'Declaration').some(
			(d: any) =>
				typeof d.property === 'string' &&
				d.property.trim().toLowerCase() === 'display' &&
				typeof d.value === 'string' &&
				d.value.trim().toLowerCase() === 'none'
		);
		if (hidesDisplay) hits.push(selectorSrc);
	}
	return hits;
}

describe('AC-4 (Frontend-Teil): Katalog-Fehler ist der erste, eigene Zweig vor den drei Zuständen', () => {
	test('Ein IfBlock mit `!metricsCatalog` als erster Bedingung existiert', () => {
		const { ast, src } = parseSvelte(HUB_OVERVIEW);
		const ifBlock = findIfBlockByTest(ast.fragment, src, /!\s*metricsCatalog\b/);
		assert.ok(
			ifBlock,
			'Kein IfBlock mit der Bedingung `!metricsCatalog` gefunden — der neue Wetter-Metriken-Block fehlt (AC-4).'
		);
	});

	test('Die vier Zweige (Katalog-Fehler, Altbestand, Leerauswahl, Auswahl) existieren in dieser Reihenfolge mit eigenen Testids', () => {
		const { ast, src } = parseSvelte(HUB_OVERVIEW);
		const ifBlock = findIfBlockByTest(ast.fragment, src, /!\s*metricsCatalog\b/);
		assert.ok(ifBlock, 'Voraussetzung (`!metricsCatalog`-Zweig) fehlt — Block noch nicht vorhanden.');
		const chain = ifElseChain(ifBlock, src);
		assert.equal(chain.length, 4, `Erwartet vier sich ausschließende Zweige, gefunden ${chain.length}.`);

		assert.ok(chain[0].testSrc && /!\s*metricsCatalog\b/.test(chain[0].testSrc));
		assert.ok(
			testIdsIn(chain[0].consequent).includes('hub-metrics-catalog-error'),
			'Der Katalog-Fehler-Zweig trägt nicht das Testid `hub-metrics-catalog-error`.'
		);

		assert.ok(chain[1].testSrc && /altbestand/.test(chain[1].testSrc), 'zweiter Zweig prüft nicht auf `altbestand`');
		assert.ok(
			testIdsIn(chain[1].consequent).includes('hub-metrics-altbestand'),
			'Der Altbestand-Zweig trägt nicht das Testid `hub-metrics-altbestand`.'
		);

		assert.ok(chain[2].testSrc && /empty/.test(chain[2].testSrc), 'dritter Zweig prüft nicht auf `empty`');
		assert.ok(
			testIdsIn(chain[2].consequent).includes('hub-metrics-empty'),
			'Der Leerauswahl-Zweig trägt nicht das Testid `hub-metrics-empty`.'
		);

		assert.equal(chain[3].testSrc, null, 'der vierte Zweig sollte der abschließende `{:else}` ohne eigene Bedingung sein');
		assert.ok(
			testIdsIn(chain[3].consequent).includes('hub-metrics-selected'),
			'Der Auswahl-Zweig (else) trägt nicht das Testid `hub-metrics-selected`.'
		);
	});

	// Fix-Loop 1, F002: der Zähler für unbekannte Kennungen (AC-11) war bis hier
	// unabgesichert — entfernt man das komplette `{#if (metricsState?.unknownCount
	// ?? 0) > 0}…{/if}` aus dem Auswahl-Zweig, blieb der Test oben trotzdem grün
	// (er prüft nur das Testid `hub-metrics-selected`, nicht dessen Inhalt).
	test('Der Auswahl-Zweig (hub-metrics-selected) enthält einen von `unknownCount` abhängigen Ausgabe-Ausdruck (AC-11)', () => {
		const { ast, src } = parseSvelte(HUB_OVERVIEW);
		const ifBlock = findIfBlockByTest(ast.fragment, src, /!\s*metricsCatalog\b/);
		assert.ok(ifBlock, 'Voraussetzung (`!metricsCatalog`-Zweig) fehlt — Block noch nicht vorhanden.');
		const chain = ifElseChain(ifBlock, src);
		const selectedBranch = chain[chain.length - 1];
		assert.equal(
			selectedBranch.testSrc,
			null,
			'Der letzte Zweig sollte der abschließende `{:else}` (Auswahl-Zweig) sein.'
		);
		const exprTags = findAll(selectedBranch.consequent, 'ExpressionTag');
		const nestedIfBlocks = findAll(selectedBranch.consequent, 'IfBlock');
		const dependsOnUnknownCount =
			exprTags.some((e: any) => /unknownCount/.test(src.slice(e.expression.start, e.expression.end))) ||
			nestedIfBlocks.some((ib: any) => /unknownCount/.test(src.slice(ib.test.start, ib.test.end)));
		assert.ok(
			dependsOnUnknownCount,
			'Im Auswahl-Zweig (hub-metrics-selected) fehlt ein von `unknownCount` abhängiger Ausgabe-Ausdruck — ' +
				'eine unbekannte Kennung dürfte dann still verschwinden, statt gesondert ausgewiesen zu werden ' +
				'(AC-11, Fix-Loop 1 F002).'
		);
	});
});

describe('AC-5 (Frontend-Teil): metricsCatalog wird ausschließlich als Prop gelesen', () => {
	// AC-5: kein eigener api.get('/api/metrics')-Aufruf, kein $effect, das den
	// Katalog nachlädt — sonst entsteht wieder ein Ladefenster wie in #1320 (F001).
	test('`metricsCatalog` ist Teil der destrukturierten Props', () => {
		const { ast, src } = parseSvelte(HUB_OVERVIEW);
		const body = ast.instance?.content?.body ?? [];
		const propsDecl = body
			.flatMap((stmt: any) => (stmt.type === 'VariableDeclaration' ? stmt.declarations : []))
			.find((d: any) => d.init?.type === 'CallExpression' && d.init.callee?.name === '$props');
		assert.ok(propsDecl, '`let { ... } = $props()` nicht gefunden');
		const propNames =
			propsDecl.id?.type === 'ObjectPattern'
				? propsDecl.id.properties.map((p: any) => p.key?.name).filter(Boolean)
				: [];
		assert.ok(
			propNames.includes('metricsCatalog'),
			`HubOverview.svelte destrukturiert \`metricsCatalog\` nicht aus den Props (gefunden: ${propNames.join(', ')}).`
		);
	});

	test('Kein eigener Fetch von /api/metrics im Instance-Script', () => {
		const { ast, src } = parseSvelte(HUB_OVERVIEW);
		const calls = findAll(ast.instance, 'CallExpression');
		const fetchesMetrics = calls.some((c) => src.slice(c.start, c.end).includes('/api/metrics'));
		assert.equal(
			fetchesMetrics,
			false,
			'HubOverview.svelte enthält einen eigenen Aufruf gegen /api/metrics — der Katalog muss ' +
				'ausschließlich aus der Server-Naht (+page.server.ts) als Prop kommen (AC-5, Fehlerklasse #1320).'
		);
	});

	test('Kein $effect, das metricsCatalog neu zuweist (kein Nachlade-Pfad)', () => {
		const { ast, src } = parseSvelte(HUB_OVERVIEW);
		const calls = findAll(ast.instance, 'CallExpression').filter((c) => c.callee?.name === '$effect');
		const reloadsCatalog = calls.some((c) => /metricsCatalog\s*=/.test(src.slice(c.start, c.end)));
		assert.equal(
			reloadsCatalog,
			false,
			'Ein $effect-Block weist metricsCatalog neu zu — das wäre ein eigener Nachlade-Pfad, den AC-5 verbietet.'
		);
	});
});

describe('Fix-Loop 1, F001: die drei festen Wortlaute sind an den richtigen Zweig gebunden', () => {
	// Bis hier prüfte kein Test den ANGEZEIGTEN TEXT, nur Bedingung + Testid je
	// Zweig. Vertauscht man die Sätze zwischen Altbestand- und Leerauswahl-Zweig
	// (Testids bleiben korrekt), blieben alle bisherigen Tests grün — der Nutzer
	// bekäme die falsche Erklärung. Diese Tests ordnen Text und Zweig einander zu,
	// statt nur "kommt irgendwo in der Datei vor" zu prüfen.
	function plainText(node: unknown, src: string): string {
		// Eigene Traversierung statt findAll(..., 'Text'): Attribut-Werte
		// (data-testid, class) sind ebenfalls als Text-Knoten kodiert und
		// dürfen den sichtbaren Textinhalt nicht verfälschen.
		const texts: string[] = [];
		function visit(n: unknown): void {
			if (n === null || typeof n !== 'object') return;
			if (Array.isArray(n)) {
				n.forEach(visit);
				return;
			}
			const rec = n as Record<string, any>;
			if (rec.type === 'Attribute') return;
			if (rec.type === 'Text') {
				texts.push(rec.data ?? src.slice(rec.start, rec.end));
				return;
			}
			for (const key of Object.keys(rec)) {
				if (key === 'parent') continue;
				visit(rec[key]);
			}
		}
		visit(node);
		return texts.join('').replace(/\s+/g, ' ').trim();
	}

	function selectedChain(): { chain: { testSrc: string | null; consequent: any }[]; src: string } {
		const { ast, src } = parseSvelte(HUB_OVERVIEW);
		const ifBlock = findIfBlockByTest(ast.fragment, src, /!\s*metricsCatalog\b/);
		assert.ok(ifBlock, 'Voraussetzung (`!metricsCatalog`-Zweig) fehlt — Block noch nicht vorhanden.');
		return { chain: ifElseChain(ifBlock, src), src };
	}

	test('Katalog-Fehler-Zweig (hub-metrics-catalog-error) zeigt exakt "Wetter-Metriken konnten nicht geladen werden."', () => {
		const { chain, src } = selectedChain();
		assert.ok(testIdsIn(chain[0].consequent).includes('hub-metrics-catalog-error'));
		assert.equal(plainText(chain[0].consequent, src), 'Wetter-Metriken konnten nicht geladen werden.');
	});

	test('Altbestand-Zweig (hub-metrics-altbestand) zeigt exakt "Noch nicht eingestellt — es gilt der Standardsatz."', () => {
		const { chain, src } = selectedChain();
		assert.ok(testIdsIn(chain[1].consequent).includes('hub-metrics-altbestand'));
		assert.equal(plainText(chain[1].consequent, src), 'Noch nicht eingestellt — es gilt der Standardsatz.');
	});

	test('Leerauswahl-Zweig (hub-metrics-empty) zeigt exakt "Keine Wettergrößen ausgewählt — das Briefing enthält keine Wettertabelle."', () => {
		const { chain, src } = selectedChain();
		assert.ok(testIdsIn(chain[2].consequent).includes('hub-metrics-empty'));
		assert.equal(
			plainText(chain[2].consequent, src),
			'Keine Wettergrößen ausgewählt — das Briefing enthält keine Wettertabelle.'
		);
	});
});

describe('AC-9: Namensauflösung liegt unter shared/, kein Compare-Pendant entsteht', () => {
	test('tripActiveMetricNames.ts liegt unter shared/trip-metrics/ UND CompareTabs bindet es nicht neu ein', () => {
		assert.ok(
			existsSync(SHARED_MODULE),
			'shared/trip-metrics/tripActiveMetricNames.ts existiert nicht — die Namensauflösung muss ' +
				'laut Teilungs-Invariante (CLAUDE.md) unter shared/ liegen, nicht unter trip-detail/ (AC-9).'
		);
		// Erst NACH Existenz des Bausteins ist diese Ratsche aussagekräftig:
		// CompareTabs.svelte darf ihn im uebersicht-Zweig nicht importieren
		// (kein stillschweigendes Compare-Pendant, Anti-Pattern-Referenz #1170).
		const compareSrc = readSrc(COMPARE_TABS);
		const compareAst = parse(compareSrc, { modern: true });
		const imports = (compareAst.instance?.content?.body ?? []).filter(
			(stmt: any) => stmt.type === 'ImportDeclaration' && /tripActiveMetricNames/.test(stmt.source?.value ?? '')
		);
		assert.equal(
			imports.length,
			0,
			'CompareTabs.svelte importiert tripActiveMetricNames — das wäre ein stillschweigendes ' +
				'Compare-Pendant, das diese Etappe ausdrücklich NICHT liefert (AC-9, Known Limitations).'
		);
	});
});

describe('AC-10: Sprung-Link nutzt denselben Mechanismus wie die bestehenden vier Karten', () => {
	test('Genau ein Aufruf von makeJumpHandler(\'weather\') im Template', () => {
		const { ast, src } = parseSvelte(HUB_OVERVIEW);
		const onclickAttrs = findAll(ast.fragment, 'Attribute').filter((a) => a.name === 'onclick');
		const weatherJumps = onclickAttrs.filter((a) => /makeJumpHandler\(\s*['"]weather['"]\s*\)/.test(attrExprSource(a, src)));
		assert.equal(
			weatherJumps.length,
			1,
			'Kein (oder mehr als ein) onclick={makeJumpHandler(\'weather\')} im Template gefunden — der ' +
				'neue Block muss über denselben Sprung-Mechanismus wie die bestehenden vier Karten in den ' +
				'Reiter „Wetter-Metriken" springen (AC-10).'
		);
	});
});

describe('AC-12 (struktureller Teil): keine viewport-abhängige display-Regel blendet den Block-Inhalt aus', () => {
	// doc-compliance-test: der sichtbare Teil von AC-12 (Screenshot 390x844) wird
	// erst in der Staging-Verifikation erbracht (s. Spec, Test Plan) — hier nur
	// der strukturelle Nachweis, dass die Fehlerklasse #1446 (`display:none` auf
	// einem Container blendet auch den Rumpf aus) nicht erneut entsteht.
	test('Der Auswahl-Absatz (hub-metrics-selected) existiert, und kein @media-Block versteckt seinen Container', () => {
		const { ast, src } = parseSvelte(HUB_OVERVIEW);
		const testidAttrs = findAll(ast.fragment, 'Attribute').filter((a) => a.name === 'data-testid');
		const selectedNode = testidAttrs.find(
			(a) => Array.isArray(a.value) && a.value.map((t: any) => t.data ?? '').join('') === 'hub-metrics-selected'
		);
		assert.ok(selectedNode, 'Testid `hub-metrics-selected` nicht im Template gefunden — der Block fehlt noch.');

		// Die Container-Klassen des neuen Blocks: alle vier sich ausschließenden
		// Zweige (Katalog-Fehler/Altbestand/Leerauswahl/Auswahl) teilen sich
		// u.a. `.hub-metrics-text` — jede dort verwendete Klasse zählt als
		// "Container des neuen Blocks" im Sinn von AC-12.
		const ifBlock = findIfBlockByTest(ast.fragment, src, /!\s*metricsCatalog\b/);
		assert.ok(ifBlock, 'Voraussetzung (`!metricsCatalog`-Zweig) fehlt — Block noch nicht vorhanden.');
		const chain = ifElseChain(ifBlock, src);
		const classTokens = new Set<string>();
		for (const branch of chain) for (const t of classTokensIn(branch.consequent)) classTokens.add(t);
		assert.ok(
			classTokens.size > 0,
			'Keine CSS-Klassen im Wetter-Metriken-Block gefunden — die Prüfung kann keinen Container zuordnen.'
		);

		// Fix-Loop 4, F006: das bisherige Text-Muster
		// `/@media[^{]*\{[\s\S]*?\n\}/g` verlangt die schließende Klammer am
		// Zeilenanfang und fand bei Tab-Einrückung NIE einen Block — der Test
		// bestand dann immer, unabhängig vom tatsächlichen CSS (die
		// #1446-Fehlerklasse also im Prüfwerkzeug selbst). Der
		// Svelte-Compiler liefert für den <style>-Abschnitt einen
		// strukturierten Baum (`ast.css`, Atrule/Rule/Declaration) — darüber
		// ist die Prüfung einrückungsunabhängig.
		assert.ok(
			ast.css && ast.css.children && ast.css.children.length > 0,
			'Kein <style>-Abschnitt (oder leer) in HubOverview.svelte gefunden — AC-12-Strukturprüfung kann nicht laufen.'
		);
		const atrules = mediaAtrules(ast.css);
		assert.ok(
			atrules.length > 0,
			'Kein @media-Block in HubOverview.svelte gefunden — AC-12-Strukturprüfung kann nicht laufen.'
		);

		const hits = atrules.flatMap((a) => mediaDisplayNoneHits(a, src, classTokens));
		assert.deepEqual(
			hits,
			[],
			'Ein @media-Block in HubOverview.svelte setzt display:none auf einem Container des neuen Blocks ' +
				`(Selektor(en): ${hits.join(', ')}) — das ist exakt die #1446-Fehlerklasse ` +
				'(eine DOM-Abfrage meldet „sichtbar", der Nutzer sieht am Handy nichts).'
		);
	});
});
