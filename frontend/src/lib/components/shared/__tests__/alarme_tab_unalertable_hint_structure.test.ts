// TDD RED — Feature #1435 Etappe E1b (AC-4, AC-6, AC-7, AC-8, AC-9):
// der Alarme-Reiter kennt DREI sich gegenseitig ausschliessende Zustaende
// statt zwei — echter Leerzustand, „nur nicht alarmfaehige Groessen gewaehlt",
// Tabelle (+ Fussnote).
// Spec: docs/specs/modules/feat_1435_e1b_alarm_erklaersatz.md
//
// Warum AST statt DOM: dieses Repo hat kein vitest/jsdom (package.json
// "test": node --test). Statt eines verbotenen Dateiinhalt-Greps parst dieser
// Test AlarmeTab.svelte mit dem ECHTEN Svelte-5-Compiler, wertet die
// Bedingungen der Zweige mit konkreten Werten aus und baut daraus den Text,
// den der Nutzer saehe. Vorbild: alarme_tab_catalog_prop_structure.test.ts
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/alarme_tab_unalertable_hint_structure.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

import { toCompareSelectionEntries } from '../weather-metrics-tab/compareMetricSelection.ts';
import type { CompareSelectionEntry } from '../weather-metrics-tab/compareMetricSelection.ts';
import type { CompareMetricCatalogEntry } from '../../../types.ts';

const here = dirname(fileURLToPath(import.meta.url));
const ALARME_TAB = join(here, '..', 'AlarmeTab.svelte');
// Alle Flaechen, die den Alarme-Reiter im Vergleichs-Kontext einbetten, mit der
// Zahl der dortigen Einbettungen (Adversary-Befund F001 aus E1a-2: die zweite
// Einbettung in CompareNewEditor wurde uebersehen).
const COMPARE_MOUNTS: Array<[string, string, number]> = [
	['Vergleichs-Hub', join(here, '..', '..', 'compare', 'CompareTabs.svelte'), 1],
	['/compare/new (Desktop + mobil)', join(here, '..', '..', 'compare-new', 'CompareNewEditor.svelte'), 2]
];

const SRC = readFileSync(ALARME_TAB, 'utf-8');
const AST: any = parse(SRC, { modern: true });

// ── AST-Werkzeug ───────────────────────────────────────────────────────────
function find(node: unknown, pred: (n: any) => boolean, out: any[] = []): any[] {
	if (node === null || typeof node !== 'object') return out;
	if (Array.isArray(node)) {
		node.forEach((n) => find(n, pred, out));
		return out;
	}
	const n = node as Record<string, any>;
	if (pred(n)) out.push(n);
	for (const key of Object.keys(n)) {
		if (key === 'parent') continue;
		find(n[key], pred, out);
	}
	return out;
}

function identifiers(subtree: unknown): Set<string> {
	return new Set(find(subtree, (n) => n.type === 'Identifier' && typeof n.name === 'string').map((n) => n.name));
}

function staticAttr(node: any, attr: string): string | null {
	const a = (node.attributes ?? []).find((x: any) => x.type === 'Attribute' && x.name === attr);
	if (!a) return null;
	if (Array.isArray(a.value)) return a.value.map((v: any) => v.data ?? v.raw ?? '').join('');
	return typeof a.value === 'string' ? a.value : null;
}

/** Der `$derived(...)`-Initialisierer einer benannten Instanz-Variable. */
function derivedInit(name: string): any {
	const decl = (AST.instance?.content?.body ?? [])
		.filter((n: any) => n.type === 'VariableDeclaration')
		.flatMap((n: any) => n.declarations)
		.find((d: any) => d.id?.type === 'Identifier' && d.id.name === name);
	assert.ok(
		decl,
		`Keine Variable \`${name}\` im Instance-Script von AlarmeTab.svelte — ohne sie kann ` +
			'der Reiter die gewaehlten, aber nicht alarmfaehigen Groessen nicht benennen (#1435 E1b).'
	);
	assert.equal(decl.init?.type, 'CallExpression');
	assert.equal(decl.init.callee?.name, '$derived');
	return decl.init.arguments[0];
}

// ── Mini-Renderer: was saehe der Nutzer bei DIESEN Werten? ─────────────────
type Scope = Record<string, unknown>;
type Screen = { testids: string[]; components: string[]; text: string };

function evalExpr(code: string, scope: Scope): unknown {
	const keys = Object.keys(scope);
	try {
		return new Function(...keys, `return (${code});`)(...keys.map((k) => scope[k]));
	} catch (err) {
		return assert.fail(
			`Der Ausdruck \`${code}\` aus AlarmeTab.svelte ist mit den bekannten Groessen ` +
				`(${keys.join(', ')}) nicht auswertbar: ${String(err)}`
		);
	}
}

/** `{#if}` / `{:else if}` / `{:else}` als flache Liste (Bedingung `null` = else). */
function ifChain(block: any): Array<{ test: string | null; fragment: any }> {
	const branches: Array<{ test: string | null; fragment: any }> = [];
	let cur: any = block;
	while (cur) {
		branches.push({ test: SRC.slice(cur.test.start, cur.test.end), fragment: cur.consequent });
		const alt = cur.alternate;
		if (!alt) break;
		const inhalt = (alt.nodes ?? []).filter((n: any) => n.type !== 'Text' || n.data.trim() !== '');
		if (inhalt.length === 1 && inhalt[0].type === 'IfBlock') cur = inhalt[0];
		else {
			branches.push({ test: null, fragment: alt });
			break;
		}
	}
	return branches;
}

function collect(fragment: any, scope: Scope, acc: Screen): Screen {
	for (const node of fragment?.nodes ?? []) {
		if (node.type === 'Text') acc.text += node.data;
		else if (node.type === 'ExpressionTag')
			acc.text += String(evalExpr(SRC.slice(node.expression.start, node.expression.end), scope));
		else if (node.type === 'IfBlock') {
			const inner = renderChain(ifChain(node), scope);
			acc.testids.push(...inner.testids);
			acc.components.push(...inner.components);
			acc.text += inner.text;
		} else if (node.type === 'Component') {
			acc.components.push(node.name);
			collect(node.fragment, scope, acc);
		} else {
			const testid = staticAttr(node, 'data-testid');
			if (testid) acc.testids.push(testid);
			collect(node.fragment, scope, acc);
		}
	}
	return acc;
}

function renderChain(chain: Array<{ test: string | null; fragment: any }>, scope: Scope): Screen {
	const leer: Screen = { testids: [], components: [], text: '' };
	for (const b of chain) {
		if (b.test === null || Boolean(evalExpr(b.test, scope))) return collect(b.fragment, scope, leer);
	}
	return leer;
}

/** Die Zweig-Kette des Abschnitts `metric-levels`. */
function metricLevelsChain(): Array<{ test: string | null; fragment: any }> {
	const abschnitt = find(
		AST.fragment,
		(n) => n.type === 'IfBlock' && SRC.slice(n.test.start, n.test.end).includes("'metric-levels'")
	)[0];
	assert.ok(abschnitt, 'Kein Abschnitt `metric-levels` in AlarmeTab.svelte gefunden.');
	const inner = find(abschnitt.consequent, (n) => n.type === 'IfBlock')[0];
	assert.ok(inner, 'Der Abschnitt `metric-levels` hat keine Zweig-Kette.');
	return ifChain(inner);
}

/** Was der Alarme-Reiter bei dieser Auswahl zeigt. */
function screen(opts: { context?: string; metrics?: string[]; unalertable?: string[] } = {}): Screen {
	return renderChain(metricLevelsChain(), {
		context: opts.context ?? 'vergleich',
		effectiveActiveMetrics: opts.metrics ?? [],
		unalertableSelectedMetricNames: opts.unalertable ?? [],
		effectiveMetricLevels: {},
		handleMetricLevelChange: () => {}
	});
}

function elementByTestid(id: string): any {
	return find(AST.fragment, (n) => staticAttr(n, 'data-testid') === id)[0] ?? null;
}

// ── Fixture fuer die Zahlen-Haelfte von AC-4/AC-9 ──────────────────────────
// Ausschnitt der ECHTEN Antwort von GET /api/compare/metrics (Stand
// 2026-07-31), Reihenfolge unveraendert.
const RESPONSE: { metrics: CompareMetricCatalogEntry[] } = {
	metrics: [
		{key: 'wind_max_kmh', unit: 'km/h', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, metric_id: 'wind', aggregation: 'max', label: 'Wind', aggregation_label: 'Maximum', alertMetric: 'wind_change', alarmCapable: true},
		{key: 'cloud_avg_pct', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, metric_id: 'cloud_total', aggregation: 'avg', label: 'Bewölkung', aggregation_label: 'Mittel', alertMetric: null, alarmCapable: false},
		{key: 'uv_index_max', unit: '', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 12, step: 1, metric_id: 'uv_index', aggregation: 'max', label: 'UV-Index', aggregation_label: 'Maximum', alertMetric: null, alarmCapable: false},
		{key: 'humidity_avg_pct', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, metric_id: 'humidity', aggregation: 'avg', label: 'Luftfeuchtigkeit', aggregation_label: 'Mittel', alertMetric: null, alarmCapable: false}
	]
};
// Erwartete Schreibweise nach PO-Nachbesserung 2: alle drei `label` kommen im
// Register genau einmal vor, also KEIN Klammerzusatz (Expected Behavior B).
const NUR_UNALERTABLE = ['Bewölkung', 'UV-Index', 'Luftfeuchtigkeit'];

type Fn = (keys: string[], catalog: CompareSelectionEntry[]) => unknown[];
async function loadDerivations(): Promise<{ alarmfaehig: Fn; ohneAlarm: Fn }> {
	const mod = (await import('../alarme-tab/activeAlertMetricsFromCatalog.ts')) as Record<string, unknown>;
	const ohneAlarm = mod.deriveUnalertableSelectedMetricNames;
	if (typeof ohneAlarm !== 'function') {
		assert.fail(
			'`deriveUnalertableSelectedMetricNames` fehlt in alarme-tab/' +
				'activeAlertMetricsFromCatalog.ts — ohne sie kann der Reiter nicht zwischen ' +
				'„nichts gewaehlt" und „nur nicht alarmfaehige Groessen gewaehlt" unterscheiden (#1435 E1b).'
		);
	}
	return {
		alarmfaehig: mod.deriveActiveAlertMetricsFromCatalog as Fn,
		ohneAlarm: ohneAlarm as Fn
	};
}

describe('#1435 E1b AC-6: der Leerzustand nennt den richtigen Reiter', () => {
	test('Der echte Leerzustand fuehrt zum Reiter „Wetter-Metriken" — in Tour wie Vergleich', () => {
		const vergleich = screen();
		assert.deepEqual(vergleich.testids, ['alarme-no-metrics']);
		assert.ok(
			vergleich.text.includes('Wetter-Metriken'),
			'Der Leerzustand schickt den Nutzer nicht in den Reiter, in dem die Groessen ' +
				`tatsaechlich gewaehlt werden. Angezeigt wird: „${vergleich.text.trim()}" (AC-6).`
		);
		assert.equal(
			vergleich.text.includes('Wertebereiche'),
			false,
			'Der Leerzustand nennt weiterhin den Reiter „Wertebereiche" — dort gibt es keine ' +
				'Metrik-Auswahl, der Nutzer sucht vergeblich (AC-6).'
		);
		assert.equal(
			screen({ context: 'route' }).text.trim(),
			vergleich.text.trim(),
			'Tour und Vergleich zeigen unterschiedliche Leerzustands-Texte — die Reiter heissen ' +
				'in beiden Kontexten gleich, der Satz muss identisch sein (AC-6).'
		);
	});
});

describe('#1435 E1b AC-4: die Leerzustand-Meldung nur im echten Leerzustand', () => {
	test('Ohne jede Auswahl: nur die Meldung, keine Tabelle, kein Erklaersatz', () => {
		const s = screen();
		assert.deepEqual(s.testids, ['alarme-no-metrics']);
		assert.equal(s.components.includes('AlertMetricLevelTable'), false);
		const nurOhneAlarm = screen({ unalertable: NUR_UNALERTABLE });
		assert.equal(
			nurOhneAlarm.testids.includes('alarme-no-metrics'),
			false,
			'Der Nutzer HAT Groessen gewaehlt (nur eben keine alarmfaehige) — die Oberflaeche ' +
				'behauptet trotzdem „nichts gewaehlt". Genau das ist die still verschwundene ' +
				'Groesse in Reinform (AC-4/AC-9).'
		);
	});

	test('Bewusst leere Auswahl: beide Ableitungen liefern nichts', async () => {
		const { alarmfaehig, ohneAlarm } = await loadDerivations();
		const katalog = toCompareSelectionEntries(RESPONSE);
		assert.deepEqual(alarmfaehig([], katalog), []);
		assert.deepEqual(ohneAlarm([], katalog), []);
	});
});

describe('#1435 E1b AC-9: nur nicht alarmfaehige Groessen gewaehlt', () => {
	test('Eigener Satz statt Leerzustand, keine Tabelle', () => {
		const s = screen({ unalertable: NUR_UNALERTABLE });
		assert.deepEqual(
			s.testids,
			['alarme-only-unalertable-hint'],
			'Erwartet wird genau der Zweig `alarme-only-unalertable-hint` (Zustand 2 der Spec).'
		);
		assert.equal(s.components.includes('AlertMetricLevelTable'), false);
		assert.ok(
			s.text.includes('Keine der gewählten Größen kann einen Alarm auslösen'),
			`Zustand 2 zeigt nicht den dafuer freigegebenen Satzanfang. Angezeigt: „${s.text.trim()}"`
		);
		for (const name of NUR_UNALERTABLE) {
			assert.ok(s.text.includes(name), `Der Satz nennt „${name}" nicht (AC-9).`);
		}
		assert.ok(s.text.includes('Sie erscheinen weiterhin im Briefing'));
	});

	test('Dieselbe Auswahl in Zahlen: keine Alarmzeile, aber drei Namen aus dem Register', async () => {
		const { alarmfaehig, ohneAlarm } = await loadDerivations();
		const aktiv = ['cloud_avg_pct', 'uv_index_max', 'humidity_avg_pct'];
		const katalog = toCompareSelectionEntries(RESPONSE);
		assert.deepEqual(alarmfaehig(aktiv, katalog), []);
		assert.deepEqual(ohneAlarm(aktiv, katalog), NUR_UNALERTABLE);
	});

	test('Zustand 2 und Zustand 3 sind zwei verschiedene Saetze, nie beide zugleich', () => {
		const nurOhneAlarm = screen({ unalertable: NUR_UNALERTABLE });
		const gemischt = screen({ metrics: ['wind_change'], unalertable: NUR_UNALERTABLE });
		assert.deepEqual(gemischt.testids, ['alarme-unalertable-metrics-hint']);
		assert.ok(gemischt.components.includes('AlertMetricLevelTable'));
		assert.ok(
			gemischt.text.includes('Für diese Größen gibt es keinen Alarm'),
			`Zustand 3 zeigt nicht die Fussnote unter der Tabelle. Angezeigt: „${gemischt.text.trim()}"`
		);
		assert.equal(nurOhneAlarm.testids.includes('alarme-unalertable-metrics-hint'), false);
		assert.equal(gemischt.testids.includes('alarme-only-unalertable-hint'), false);
		assert.deepEqual(
			screen({ metrics: ['wind_change'] }).testids,
			[],
			'Ohne nicht alarmfaehige Groesse bleibt jeder Erklaersatz aus (AC-3).'
		);
	});
});

describe('#1435 E1b AC-7: der Tour-Kontext bleibt bei zwei Zustaenden', () => {
	test('Die neue Ableitung liefert im Tour-Kontext strukturell immer eine leere Liste', () => {
		const cond = derivedInit('unalertableSelectedMetricNames');
		assert.equal(cond.type, 'ConditionalExpression');
		assert.ok(identifiers(cond.test).has('context'));
		const imVergleich = identifiers(cond.consequent);
		assert.ok(imVergleich.has('deriveUnalertableSelectedMetricNames'));
		assert.ok(
			imVergleich.has('catalog'),
			'Der Erklaersatz liest den Katalog nicht aus der `catalog`-Prop (Fehlerklasse #1320).'
		);
		assert.equal(cond.alternate.type, 'ArrayExpression');
		assert.deepEqual(
			cond.alternate.elements,
			[],
			'Der Tour-Zweig liefert nicht die leere Liste — dort gibt es keine Metrik-Auswahl, ' +
				'jeder daraus gebildete Satz waere sachlich falsch (AC-7).'
		);
	});

	test('Im Tour-Kontext rendert nie einer der beiden Erklaersaetze', () => {
		for (const id of ['alarme-only-unalertable-hint', 'alarme-unalertable-metrics-hint']) {
			assert.ok(
				elementByTestid(id),
				`Der Zweig „${id}" fehlt im Template — solange es ihn nicht gibt, ist AC-7 nicht ` +
					'nachweisbar (es gaebe nichts, was im Tour-Kontext ausbleiben koennte).'
			);
		}
		for (const metrics of [[], ['wind_change']]) {
			const s = screen({ context: 'route', metrics });
			for (const id of ['alarme-only-unalertable-hint', 'alarme-unalertable-metrics-hint']) {
				assert.equal(s.testids.includes(id), false, `Tour-Kontext zeigt „${id}" (AC-7).`);
			}
		}
	});

	test('Die Absicherung des Fussnoten-Satzes haelt auch bei nicht-leerer Namensliste', () => {
		// Adversary-Befund F001 (E1b): der Test oben beweist den Tour-Kontext nur
		// MITTELBAR — ueber den $derived, der fuer context="route" strukturell []
		// liefert. Faellt diese Eigenschaft (die Spec nennt als Known Limitation
		// genau den Nachfolger, der den Katalog doch in den Tour-Container reicht),
		// haelt allein die Template-Absicherung `context === 'vergleich' && …`.
		// Hier wird sie direkt geprueft: Namensliste absichtlich nicht leer.
		const s = screen({ context: 'route', metrics: ['wind_change'], unalertable: NUR_UNALERTABLE });
		assert.ok(
			s.components.includes('AlertMetricLevelTable'),
			'Vorbedingung: dieser Fall muss im dritten Zweig landen (Tabelle sichtbar) — nur ' +
				'dort steht der Fussnoten-Satz ueberhaupt zur Debatte.'
		);
		assert.equal(
			s.testids.includes('alarme-unalertable-metrics-hint'),
			false,
			'Der Fussnoten-Satz haengt allein daran, dass der $derived im Tour-Kontext leer ' +
				'bleibt — die zweite Absicherung im Template (`context === \'vergleich\'`) fehlt ' +
				'oder wirkt nicht. Reicht eine spaetere Etappe den Katalog in den Tour-Container, ' +
				'erschiene dort ein Satz ueber eine Auswahl, die es bei Touren nicht gibt ' +
				'(AC-7, Fehlerklasse F001).'
		);
		assert.equal(s.text.includes('Für diese Größen gibt es keinen Alarm'), false);
	});
});

describe('#1435 E1b AC-8: alle drei Vergleichs-Flaechen zeigen denselben Satz', () => {
	test('Jede Einbettung reicht denselben Katalog durch, aus dem der Satz liest', () => {
		let gesamt = 0;
		for (const [flaeche, datei, erwartet] of COMPARE_MOUNTS) {
			const quelle = readFileSync(datei, 'utf-8');
			const baum: any = parse(quelle, { modern: true });
			const instanzen = find(baum.fragment, (n) => n.type === 'Component' && n.name === 'AlarmeTab').filter(
				(i) => staticAttr(i, 'context') === 'vergleich'
			);
			assert.equal(
				instanzen.length,
				erwartet,
				`${flaeche}: erwartet ${erwartet} <AlarmeTab context="vergleich">, gefunden ` +
					`${instanzen.length} — eine still uebersprungene Einbettung zeigte den Satz nicht (AC-8, F001).`
			);
			for (const inst of instanzen) {
				const attr = (inst.attributes ?? []).find((a: any) => a.name === 'catalog');
				assert.ok(attr, `${flaeche}: <AlarmeTab context="vergleich"> ohne \`catalog\` (AC-8).`);
				assert.equal(quelle.slice(attr.start, attr.end), 'catalog={alarmeCatalog}');
			}
			gesamt += instanzen.length;
		}
		assert.equal(gesamt, 3);
		assert.ok(
			identifiers(derivedInit('unalertableSelectedMetricNames')).has('catalog'),
			'Der Satz haengt nicht an der durchgereichten `catalog`-Prop — dann kann er an einer ' +
				'der drei Flaechen fehlen oder anderes zeigen (AC-8, Fehlerklasse #1320).'
		);
	});

	test('Beide Erklaersaetze lesen dieselbe Ableitung — kein zweiter Datenpfad', () => {
		for (const id of ['alarme-only-unalertable-hint', 'alarme-unalertable-metrics-hint']) {
			const el = elementByTestid(id);
			assert.ok(el, `Der Zweig „${id}" fehlt im Template (#1435 E1b).`);
			const namen = identifiers(el.fragment);
			assert.ok(
				namen.has('unalertableSelectedMetricNames'),
				`„${id}" bildet seine Namen nicht aus der EINEN Ableitung (AC-8).`
			);
			assert.equal(
				namen.has('deriveUnalertableSelectedMetricNames'),
				false,
				`„${id}" rechnet im Template selbst — ein zweiter Datenpfad neben dem $derived (AC-8).`
			);
		}
	});
});
