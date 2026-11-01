// TDD RED — Issue #2682 (Epic #2345): EIN Laden der Versand-Historie fuer
// Kennzahl „Zuletzt raus" UND Historien-Liste.
// Spec: docs/specs/modules/feat_2682_hub_uebersicht_geteilt.md
//   Entscheidung 3 (on_demand !== true, ein Laden), AC-6, AC-7, AC-12
//
// Pruefling: shared/briefingHistoryLader.svelte.ts — Runen-Modul. Testart wie
// versand-tab/__tests__/naechstes_briefing_lader_laufzeit.test.ts: das Modul
// wird mit dem echten Svelte-Compiler fuer die CLIENT-Laufzeit uebersetzt
// (clientRunenHook.mjs) und unter `effect_root` + `flush` ausgefuehrt — echte
// Abhaengigkeits-Verfolgung, kein DOM. Der Abrufer ist ein Fake-SERVER am
// Netz-Ausgang: er beantwortet den Pfad mit der JSON-Form von
// internal/handler/briefing_history.go (sent_at, kind, channels, on_demand —
// on_demand ist dort KEIN omitempty, kommt also immer als bool) und zaehlt
// die Aufrufe. Kein Mock-Theater: geprueft wird das beobachtbare Ergebnis.
//
// ── VERTRAG (hier festgelegt, Phase 6 baut danach) ──────────────────────────
//   export interface BriefingHistoryLader {
//     readonly zustand: 'laedt' | 'geladen' | 'fehler';   // ohne id: 'laedt' (nie geladen)
//     readonly eintraege: BriefingHistoryEntry[];         // chronologisch wie vom Server
//     readonly neuesterPlanmaessiger: BriefingHistoryEntry | null;
//        // = neuesterPlanmaessigerEintrag(eintraege) aus hub-uebersicht/hubUebersichtModell.ts
//   }
//   export function erstelleBriefingHistoryLader(
//     quelle: () => { kind: 'route' | 'vergleich'; id?: string },
//     holen: (pfad: string) => Promise<unknown>
//   ): BriefingHistoryLader;
//   Pfad: briefingHistoryUrl(id, kind) aus shared/briefingHistory.ts.
//
// Das Modul wird JE TEST dynamisch geladen (`ladeLader()`), damit in RED jeder
// Fall mit eigener Meldung scheitert.
//
// Pfadregel #1409: alles relativ zu DIESER Datei.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/shared/__tests__/briefing_history_lader.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { existsSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SHARED = path.join(HERE, '..');
const COMPONENTS = path.join(SHARED, '..');
// __tests__ -> shared -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
const LADER = path.join(SHARED, 'briefingHistoryLader.svelte.ts');
// Reihenfolge bewusst: Node-Hooks laufen zuletzt-registriert-zuerst. Der SSR-Hook loest
// endungslose relative Importe auf (der Lader zieht ueber hubUebersichtModell.ts
// compare/subscriptionHelpers.ts -> '../../utils/cockpitHelpers568' herein); der danach
// registrierte clientRunenHook uebersetzt `*.svelte.ts` trotzdem fuer die CLIENT-Laufzeit.
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(
	pathToFileURL(path.join(SHARED, 'versand-tab', '__tests__', 'clientRunenHook.mjs')).href,
	pathToFileURL(HERE + '/').href
);

// Interne Client-Laufzeit (ohne Typdeklaration) — Spezifizierer als Wert.
const CLIENT_LAUFZEIT: string = 'svelte/internal/client';
const $ = (await import(CLIENT_LAUFZEIT)) as Record<string, any>;
const { briefingHistoryUrl } = await import(pathToFileURL(path.join(SHARED, 'briefingHistory.ts')).href);
// Messaufbau-Beleg: die Hook-Kette loest die Abhaengigkeiten des Modells heute schon auf
// (sonst schluege der Lader-Test in Phase 6 mit ERR_MODULE_NOT_FOUND statt an einer Zusicherung fehl).
await import(pathToFileURL(path.join(COMPONENTS, 'compare', 'subscriptionHelpers.ts')).href);

async function ladeLader(): Promise<(q: () => unknown, h: (p: string) => Promise<unknown>) => any> {
	assert.ok(
		existsSync(LADER),
		'shared/briefingHistoryLader.svelte.ts fehlt (RED) — Spec „Affected Files": erstelleBriefingHistoryLader'
	);
	const mod = await import(pathToFileURL(LADER).href);
	assert.equal(typeof mod.erstelleBriefingHistoryLader, 'function', 'erstelleBriefingHistoryLader fehlt');
	return mod.erstelleBriefingHistoryLader;
}

/** Mikrotasks + Effekt-Warteschlange abarbeiten. */
async function setzen() {
	$.flush();
	for (let i = 0; i < 5; i++) await new Promise((r) => setTimeout(r, 0));
	$.flush();
}

// ── Fake-Server: Antwortform wie internal/handler/briefing_history.go ────────

type Eintrag = { sent_at: string; kind: string; channels: string[]; on_demand: boolean };
const PLANMAESSIG_28: Eintrag = { sent_at: '2026-10-28T05:00:00Z', kind: 'morning', channels: ['email', 'telegram'], on_demand: false };
const ABEND_29: Eintrag = { sent_at: '2026-10-29T16:00:00Z', kind: 'evening', channels: ['email'], on_demand: false };
const VON_HAND_30: Eintrag = { sent_at: '2026-10-30T10:00:00Z', kind: 'morning', channels: ['sms'], on_demand: true };

/** Server je Briefing-Kennung (ein Nutzer-Log, gefiltert wie der Go-Handler nach kind+id). */
function fakeServer(logs: Record<string, Eintrag[] | Error | Promise<unknown>>) {
	const pfade: string[] = [];
	const holen = async (pfad: string) => {
		pfade.push(pfad);
		const m = /^\/api\/briefings\/([^/]+)\/briefing-history\?kind=(route|vergleich)$/.exec(pfad);
		if (!m) throw new Error(`404 ${pfad}`);
		const antwort = logs[`${m[2]}:${decodeURIComponent(m[1])}`];
		if (antwort instanceof Error) throw antwort;
		if (antwort instanceof Promise) return antwort;
		return antwort ?? []; // Go: unbekannte/fremde id ⇒ 200 []
	};
	return { pfade, holen };
}

async function starte(start: { kind: string; id?: string }, holen: (p: string) => Promise<unknown>) {
	const erstelle = await ladeLader();
	const signale = { kind: $.state(start.kind), id: $.state(start.id), fremd: $.state(0) };
	let lader: any;
	const stopp = $.effect_root(() => {
		lader = erstelle(() => ({ kind: $.get(signale.kind), id: $.get(signale.id) }), holen);
	});
	return { signale, get lader() { return lader; }, stopp };
}

// ── AC-12: ein Laden, Liste und Kennzahl aus derselben Antwort ──────────────

describe('AC-12: genau EIN Abruf, Liste und neuester planmaessiger Eintrag aus derselben Antwort', () => {
	test('route: ein Aufruf an briefingHistoryUrl, Liste vollstaendig, neuester planmaessiger = 29.10.', async () => {
		const s = fakeServer({ 'route:t-1': [PLANMAESSIG_28, ABEND_29, VON_HAND_30] });
		const l = await starte({ kind: 'route', id: 't-1' }, s.holen);
		await setzen();
		// beide Lesestellen mehrfach abfragen — darf keinen weiteren Abruf ausloesen
		const liste = l.lader.eintraege;
		const neuester = l.lader.neuesterPlanmaessiger;
		void l.lader.eintraege;
		void l.lader.neuesterPlanmaessiger;
		await setzen();
		assert.deepEqual(s.pfade, [briefingHistoryUrl('t-1', 'route')], `erwartet genau EIN Abruf: ${JSON.stringify(s.pfade)}`);
		assert.equal(l.lader.zustand, 'geladen');
		assert.deepEqual(liste.map((e: Eintrag) => e.sent_at), [PLANMAESSIG_28, ABEND_29, VON_HAND_30].map((e) => e.sent_at));
		assert.equal(neuester?.sent_at, ABEND_29.sent_at, 'on_demand-Eintrag (30.10.) darf nicht „Zuletzt raus" sein');
		l.stopp();
	});

	test('vergleich: Pfad mit kind=vergleich, ebenfalls ein Aufruf', async () => {
		const s = fakeServer({ 'vergleich:cp-1': [PLANMAESSIG_28] });
		const l = await starte({ kind: 'vergleich', id: 'cp-1' }, s.holen);
		await setzen();
		assert.deepEqual(s.pfade, [briefingHistoryUrl('cp-1', 'vergleich')]);
		assert.equal(l.lader.neuesterPlanmaessiger?.sent_at, PLANMAESSIG_28.sent_at);
		l.stopp();
	});

	test('fremdes Signal aendert sich ⇒ KEIN zweiter Abruf', async () => {
		const s = fakeServer({ 'route:t-1': [PLANMAESSIG_28] });
		const l = await starte({ kind: 'route', id: 't-1' }, s.holen);
		await setzen();
		$.set(l.signale.fremd, 1);
		await setzen();
		assert.equal(s.pfade.length, 1);
		l.stopp();
	});
});

// ── Filter on_demand !== true ───────────────────────────────────────────────

describe('Entscheidung 3: „Zuletzt raus" ignoriert Eintraege von Hand', () => {
	test('nur Eintraege von Hand ⇒ neuesterPlanmaessiger = null, Liste traegt sie trotzdem', async () => {
		const s = fakeServer({ 'route:t-1': [VON_HAND_30] });
		const l = await starte({ kind: 'route', id: 't-1' }, s.holen);
		await setzen();
		assert.equal(l.lader.neuesterPlanmaessiger, null);
		assert.equal(l.lader.eintraege.length, 1, 'die Historien-Liste zeigt auch Eintraege von Hand');
		l.stopp();
	});
});

// ── AC-7: Zustaende ─────────────────────────────────────────────────────────

describe('AC-7: Lade-, Leer- und Fehlerzustand', () => {
	test('vor der Antwort ⇒ zustand „laedt", keine Eintraege', async () => {
		let aufloesen: (v: unknown) => void = () => {};
		const s = fakeServer({ 'route:t-1': new Promise((r) => (aufloesen = r)) });
		const l = await starte({ kind: 'route', id: 't-1' }, s.holen);
		await setzen();
		assert.equal(l.lader.zustand, 'laedt');
		assert.deepEqual(l.lader.eintraege, []);
		assert.equal(l.lader.neuesterPlanmaessiger, null);
		aufloesen([PLANMAESSIG_28]);
		await setzen();
		assert.equal(l.lader.zustand, 'geladen');
		l.stopp();
	});

	test('leere Antwort (Go: 200 []) ⇒ geladen, leer', async () => {
		const s = fakeServer({});
		const l = await starte({ kind: 'route', id: 't-neu' }, s.holen);
		await setzen();
		assert.equal(l.lader.zustand, 'geladen');
		assert.deepEqual(l.lader.eintraege, []);
		assert.equal(l.lader.neuesterPlanmaessiger, null);
		l.stopp();
	});

	test('Abruf scheitert ⇒ zustand „fehler", kein Absturz', async () => {
		const s = fakeServer({ 'route:t-1': new Error('502') });
		const l = await starte({ kind: 'route', id: 't-1' }, s.holen);
		await setzen();
		assert.equal(l.lader.zustand, 'fehler');
		assert.equal(l.lader.neuesterPlanmaessiger, null);
		l.stopp();
	});

	test('ohne id (Anlege-Seite) ⇒ kein Abruf', async () => {
		const s = fakeServer({});
		const l = await starte({ kind: 'route', id: undefined }, s.holen);
		await setzen();
		assert.equal(s.pfade.length, 0);
		assert.equal(l.lader.zustand, 'laedt');
		l.stopp();
	});
});

// ── Stale-Guard ─────────────────────────────────────────────────────────────

describe('Stale-Guard: eine spaete Antwort fuer eine alte Kennung wird verworfen', () => {
	test('id wechselt t-1 → t-2, danach trifft die Antwort fuer t-1 ein ⇒ Anzeige bleibt bei t-2', async () => {
		let t1Aufloesen: (v: unknown) => void = () => {};
		const s = fakeServer({
			'route:t-1': new Promise((r) => (t1Aufloesen = r)),
			'route:t-2': [ABEND_29]
		});
		const l = await starte({ kind: 'route', id: 't-1' }, s.holen);
		await setzen();
		$.set(l.signale.id, 't-2');
		await setzen();
		assert.equal(l.lader.neuesterPlanmaessiger?.sent_at, ABEND_29.sent_at, 'Messaufbau: t-2 geladen');
		t1Aufloesen([PLANMAESSIG_28, VON_HAND_30]);
		await setzen();
		assert.equal(l.lader.neuesterPlanmaessiger?.sent_at, ABEND_29.sent_at, 'veraltete Antwort (t-1) hat t-2 ueberschrieben');
		assert.equal(l.lader.eintraege.length, 1);
		l.stopp();
	});

	test('id faellt weg, danach trifft die alte Antwort ein ⇒ wird nicht uebernommen', async () => {
		let aufloesen: (v: unknown) => void = () => {};
		const s = fakeServer({ 'route:t-1': new Promise((r) => (aufloesen = r)) });
		const l = await starte({ kind: 'route', id: 't-1' }, s.holen);
		await setzen();
		$.set(l.signale.id, undefined);
		await setzen();
		aufloesen([PLANMAESSIG_28]);
		await setzen();
		assert.deepEqual(l.lader.eintraege, []);
		assert.equal(l.lader.neuesterPlanmaessiger, null);
		l.stopp();
	});
});
