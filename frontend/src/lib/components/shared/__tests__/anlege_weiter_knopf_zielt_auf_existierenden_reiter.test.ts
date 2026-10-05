// Feature #2287 (Adversary F002): jeder Weiter-Knopf der Anlege-Kette (`/compare/new`,
// `/trips/new`) schaltet auf einen Reiter, den es in TAB_DEFS der Seite gibt —
// insbesondere `compare-editor-continue-wertebereiche` auf `wertebereiche`. Vor diesem
// Test blieb die Mutation des Ziels auf `'idealwerte'` gruen.
//
// Messweise (Verhalten, kein Dateiinhalt-Check): das ECHTE Instanz-Skript des Editors
// wird ueber `svelteInstanzPruefstand.ts` ausgewertet. Fuer jeden Weiter-Knopf wird der
// onclick-Ausdruck aus dem Markup (AST) gegen diese Umgebung ausgewertet und AUSGEFUEHRT;
// gemessen wird der danach aktive Reiter (`activeTab`). Vergleich: echte Freischaltung
// (`tailUnlocked`, alle Besuchs-Flags gesetzt) — ein Ziel ausserhalb von TAB_DEFS ist dort
// gesperrt und laesst den Reiter stehen. Trip: `switchTab` kennt kein Schloss — dort
// faellt ein unbekanntes Ziel als aktiver Reiter ausserhalb von TAB_DEFS auf.
//
// Ausfuehren:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/anlege_weiter_knopf_zielt_auf_existierenden_reiter.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { umgebungFuer, werte, type Knoten } from './svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const VERGLEICH_NEU = join(HIER, '..', '..', 'compare-new', 'CompareNewEditor.svelte');
const TRIP_NEU = join(HIER, '..', '..', 'trip-new', 'TripNewEditor.svelte');
register(
	pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

/** Alle Markup-Knoten (Elemente + Komponenten) mit onclick-Attribut. */
function klickKnoten(ast: Knoten): Knoten[] {
	const treffer: Knoten[] = [];
	(function lauf(n: unknown): void {
		if (n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) return n.forEach(lauf);
		const k = n as Knoten;
		if (Array.isArray(k.attributes) && k.attributes.some((a: Knoten) => a.type === 'Attribute' && a.name === 'onclick')) {
			treffer.push(k);
		}
		for (const key of Object.keys(k)) if (key !== 'parent' && key !== 'loc') lauf(k[key]);
	})(ast.fragment);
	return treffer;
}

function attrText(k: Knoten, quelle: string, name: string): string | null {
	const a = (k.attributes as Knoten[]).find((x) => x.type === 'Attribute' && x.name === name);
	if (!a) return null;
	const v = a.value;
	if (v?.type === 'ExpressionTag') return quelle.slice(v.expression.start, v.expression.end);
	if (Array.isArray(v)) return v.map((t: Knoten) => (t.type === 'Text' ? t.data : '')).join('');
	return null;
}

const tabIds = (u: Knoten): string[] => (u.TAB_DEFS as Array<{ id: string }>).map((t) => t.id);

// ── Ortsvergleich-Anlegen ───────────────────────────────────────────────────────

async function vergleichEditor() {
	const wiz = { name: 'X', region: '', profile: 'wandern', pickedIds: ['a', 'b', 'c'] };
	return umgebungFuer(
		VERGLEICH_NEU,
		{
			untrack: (f: () => unknown) => f(),
			getContext: () => wiz,
			stateOverride: {
				activeTab: 'vergleich',
				metrikenVisited: true,
				idealsVisited: true,
				alarmeVisited: true,
				versandVisited: true
			}
		},
		{ jsAlsTs: true }
	);
}

describe('F002 Ortsvergleich-Anlegen: jeder Weiter-Knopf schaltet auf den Reiter seiner testid', () => {
	test('Vorbedingung: echte Freischaltung gibt alle TAB_DEFS-Reiter frei', async () => {
		const { u } = await vergleichEditor();
		assert.deepEqual(tabIds(u), ['vergleich', 'orte', 'wetter-metriken', 'wertebereiche', 'alarme', 'versand']);
		for (const id of tabIds(u)) assert.ok((u.unlocked as Set<string>).has(id), `'${id}' nicht freigeschaltet`);
	});

	test('compare-editor-continue-<id>: Klick → activeTab === <id> ∈ TAB_DEFS (insb. wertebereiche)', async () => {
		const { u, ast, quelle } = await vergleichEditor();
		const knoepfe = klickKnoten(ast)
			.map((k) => ({ testid: attrText(k, quelle, 'data-testid'), onclick: attrText(k, quelle, 'onclick') }))
			.filter((k) => k.testid?.startsWith('compare-editor-continue-'));
		const ziele = knoepfe.map((k) => k.testid!.slice('compare-editor-continue-'.length));
		assert.deepEqual(ziele, ['orte', 'wetter-metriken', 'wertebereiche', 'alarme', 'versand'], 'Weiter-Knoepfe');
		for (const { testid, onclick } of knoepfe) {
			const ziel = testid!.slice('compare-editor-continue-'.length);
			assert.ok(tabIds(u).includes(ziel), `testid ${testid} nennt keinen Reiter aus TAB_DEFS`);
			u.activeTab = 'vergleich';
			(werte(onclick!, u) as () => void)();
			assert.equal(u.activeTab, ziel, `${testid} schaltet nicht auf '${ziel}' (Ziel veraltet/gesperrt?)`);
		}
	});
});

// ── Trip-Anlegen ────────────────────────────────────────────────────────────────

async function tripEditor() {
	return umgebungFuer(
		TRIP_NEU,
		{
			untrack: (f: () => unknown) => f(),
			stateOverride: { activeTab: 'route', name: 'GR20', startDate: '2026-07-01' }
		},
		{ jsAlsTs: true }
	);
}

describe('F002 Trip-Anlegen: jeder Weiter-Knopf/-Handler zielt auf einen Reiter aus TAB_DEFS', () => {
	test('onclick-Ausdruecke mit Weiter-Handler (make…Continue…Handler): Ziel ∈ TAB_DEFS und = Literal', async () => {
		const { u, ast, quelle } = await tripEditor();
		const ausdruecke = klickKnoten(ast)
			.map((k) => attrText(k, quelle, 'onclick')!)
			.filter((x) => /make\w*Continue\w*Handler\(/.test(x));
		assert.ok(ausdruecke.length >= 6, `Messaufbau: nur ${ausdruecke.length} Weiter-Knoepfe gefunden`);
		for (const x of ausdruecke) {
			u.activeTab = 'route';
			(werte(x, u) as () => void)();
			assert.ok(tabIds(u).includes(u.activeTab), `${x} schaltet auf '${u.activeTab}' — kein Reiter aus TAB_DEFS`);
			const literal = /\(\s*'([a-z-]+)'\s*\)/.exec(x)?.[1];
			if (literal) assert.equal(u.activeTab, literal, x);
			else assert.notEqual(u.activeTab, 'route', `${x} schaltet nicht weiter`);
		}
	});

	test('parameterlose Weiter-Fabriken (auch ausserhalb von onclick): Ziel ∈ TAB_DEFS', async () => {
		const { u } = await tripEditor();
		const fabriken = Object.keys(u).filter((n) => /^make\w*Continue\w*Handler$/.test(n) && (u[n] as () => unknown).length === 0);
		assert.ok(fabriken.includes('makeMobileWegpunkteContinueHandler'), `Fabriken: ${fabriken.join(',')}`);
		for (const f of fabriken) {
			u.activeTab = 'route';
			(u[f] as () => () => void)()();
			assert.ok(tabIds(u).includes(u.activeTab), `${f} schaltet auf '${u.activeTab}' — kein Reiter aus TAB_DEFS`);
			assert.notEqual(u.activeTab, 'route', `${f} schaltet nicht weiter`);
		}
	});
});
