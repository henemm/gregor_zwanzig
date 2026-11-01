// Fix-Loop 1 — Issue #2682 (Epic #2345), Adversary F001/F002/F003/F004(B02):
// die VERDRAHTUNG der geteilten Hub-Übersicht als Verhalten.
// Spec: docs/specs/modules/feat_2682_hub_uebersicht_geteilt.md — AC-6, AC-7, AC-12, Entscheidung 3
//
// Was hier gemessen wird (nicht, ob ein Bezeichner im Quelltext steht):
//   F001  HubUebersicht (Trip UND Ortsvergleich) loest GENAU EINEN Abruf von
//         /api/briefings/{id}/briefing-history?kind=… aus — mit der richtigen Art und
//         Kennung. „Zuletzt raus" (Trip) zeigt das Datum aus DERSELBEN Antwort, die
//         eingebettete Versand-Historie deren Eintraege.
//   F002  Trip: /api/next-briefings wird GENAU EINMAL abgerufen; die Trip-Hauptflaeche
//         (trip-detail/HubOverview in TripTabs) bekommt den Wert und zeigt die
//         Slot-Zeit samt Zonenkuerzel („Briefings laufen").
//   F003  Ortsvergleich: nach dem ECHTEN Pause-Weg von CompareTabs (handleToggleActive,
//         PUT gegen einen Ersatz-Server) zeigt die Status-Kennzahl „Pausiert".
//   B02   Scheitert der geteilte Abruf, zeigt die Versand-Historie ihren Fehlertext.
//
// Messaufbau und warum so:
//   - Ein echter Client-Mount ist hier strukturell nicht moeglich: im Projekt gibt es
//     kein DOM (kein jsdom/happy-dom), und der SSR-Render fuehrt kein `$effect` aus —
//     ein Abruf waere dort nie beobachtbar. Deshalb laeuft das ECHTE Instanz-Skript der
//     Komponenten ueber den Pruefstand (`umgebungFuer`), die beiden Lader sind die
//     ECHTEN, fuer die Svelte-CLIENT-Laufzeit uebersetzten Runen-Module
//     (clientRunenHook.mjs) unter `effect_root` + `flush` — echte Effekte, echte
//     Abhaengigkeits-Verfolgung. Die Saat ersetzt die Lader-Bindung nur durch eine
//     Huelle, die den ECHTEN Lader in einer Effekt-Wurzel startet (die Komponente
//     waere das im Browser selbst); `quelle` und `holen` kommen unveraendert aus dem
//     Quelltext der Komponente.
//   - Das Netz ist ein Fetch-Ersatz am Ausgang (`globalThis.fetch`): `$lib/api.js` ist
//     das ECHTE Modul, jeder Abruf landet mit seiner URL im Protokoll. Antworten in der
//     Form der Go-Handler (internal/handler/briefing_history.go, next_briefings).
//   - `$derived` wertet der Pruefstand einmal beim Aufbau aus (Stand „laedt"); nach dem
//     Laden wird die ECHTE Herleitung aus dem Quelltext (`neuAuswerten`) erneut
//     ausgewertet — sonst liefe die Zusicherung gegen den veralteten Wert.
//   - Die Weitergabe an Kind-Komponenten (BriefingHistory, HubOverview, HubUebersicht in
//     CompareTabs) wird ueber die ECHTEN Attribut-Ausdruecke der Einbettung ausgewertet;
//     fehlt ein Attribut, kommt `undefined` an — wie beim Mount.
//
// Pfadregel #1409: alles relativ zu DIESER Datei.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/shared/hub-uebersicht/__tests__/hub_uebersicht_verdrahtung_laufzeit.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parse } from 'svelte/compiler';
import { umgebungFuer, effekteVon, findeKomponenten, werte, ohneTypen, type Knoten } from '../../__tests__/svelteInstanzPruefstand.ts';

process.env.TZ = 'Europe/Berlin';

const HIER = dirname(fileURLToPath(import.meta.url));
// __tests__ -> hub-uebersicht -> shared -> components -> lib -> src -> frontend
const FRONTEND = resolve(HIER, '..', '..', '..', '..', '..', '..');
const SHARED = resolve(HIER, '..', '..');
const COMPONENTS = resolve(SHARED, '..');
const HU = join(HIER, '..', 'HubUebersicht.svelte');
const BH = join(SHARED, 'BriefingHistory.svelte');
const TRIP_TABS = join(COMPONENTS, 'trip-detail', 'TripTabs.svelte');
const HUB_OVERVIEW = join(COMPONENTS, 'trip-detail', 'HubOverview.svelte');
const COMPARE_TABS = join(COMPONENTS, 'compare', 'CompareTabs.svelte');
const basis = pathToFileURL(FRONTEND + '/').href;

// Reihenfolge bewusst (zuletzt registriert = zuerst gefragt): der SSR-Hook loest endungslose
// Importe auf und uebersetzt `.svelte` fuer den Server-Render; der clientRunenHook danach
// uebersetzt `*.svelte.ts` (die Lader) fuer die CLIENT-Laufzeit.
register(pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, basis);
register(pathToFileURL(join(SHARED, 'versand-tab', '__tests__', 'clientRunenHook.mjs')).href, pathToFileURL(HIER + '/').href);

// Interne Client-Laufzeit (ohne Typdeklaration) — Spezifizierer als Wert.
const CLIENT_LAUFZEIT: string = 'svelte/internal/client';
const $ = (await import(CLIENT_LAUFZEIT)) as Record<string, any>;
const { render } = await import('svelte/server');
const { erstelleBriefingHistoryLader } = await import(pathToFileURL(join(SHARED, 'briefingHistoryLader.svelte.ts')).href);
const { erstelleNaechstesBriefingLader } = await import(
	pathToFileURL(join(SHARED, 'versand-tab', 'naechstesBriefingLader.svelte.ts')).href
);
const { briefingHistoryUrl } = await import(pathToFileURL(join(SHARED, 'briefingHistory.ts')).href);
const { formatLastSent } = await import(pathToFileURL(join(COMPONENTS, 'compare', 'subscriptionHelpers.ts')).href);
const BriefingHistory = (await import(pathToFileURL(BH).href)).default;

// ── Netz: Fetch-Ersatz am Ausgang, Antworten wie die Go-Handler ──────────────

type Eintrag = { sent_at: string; kind: string; channels: string[]; on_demand: boolean };
const PLANMAESSIG_28: Eintrag = { sent_at: '2026-10-28T05:00:00Z', kind: 'morning', channels: ['email'], on_demand: false };
const ABEND_29: Eintrag = { sent_at: '2026-10-29T16:00:00Z', kind: 'evening', channels: ['email', 'telegram'], on_demand: false };
const VON_HAND_30: Eintrag = { sent_at: '2026-10-30T10:00:00Z', kind: 'morning', channels: ['sms'], on_demand: true };
const LOG = [PLANMAESSIG_28, ABEND_29, VON_HAND_30];
const NB = { at: '2026-11-02T07:00:00+01:00', local_date: '2026-11-02', local_time: '07:00', tz: 'Europe/Berlin', tz_abbr: 'CET', slot: 'morning' };

const echtesFetch = globalThis.fetch;
afterEach(() => {
	globalThis.fetch = echtesFetch;
});

/** Ersatz-Server: `historie` je „kind:id"; `/api/next-briefings` beantwortet jede Kennung mit NB. */
function netz(historie: Record<string, Eintrag[] | 'fehler'>) {
	const urls: string[] = [];
	const antwort = (status: number, body: unknown) =>
		new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
	globalThis.fetch = (async (eingabe: unknown) => {
		const url = String(eingabe);
		urls.push(url);
		const bh = /^\/api\/briefings\/([^/]+)\/briefing-history\?kind=(route|vergleich)$/.exec(url);
		if (bh) {
			const log = historie[`${bh[2]}:${decodeURIComponent(bh[1])}`];
			return log === 'fehler' ? antwort(502, { error: 'bad gateway' }) : antwort(200, log ?? []);
		}
		const nb = /^\/api\/next-briefings\?(trip_id|preset_id)=(.+)$/.exec(url);
		if (nb) {
			const id = decodeURIComponent(nb[2]);
			return antwort(200, nb[1] === 'trip_id' ? { trips: { [id]: NB }, compare: {} } : { trips: {}, compare: { [id]: NB } });
		}
		return antwort(404, { error: 'not found' });
	}) as typeof fetch;
	return {
		urls,
		historienAbrufe: () => urls.filter((u) => u.includes('/briefing-history')),
		naechsteAbrufe: () => urls.filter((u) => u.startsWith('/api/next-briefings'))
	};
}

/** Mikrotasks + Effekt-Warteschlange abarbeiten (Fetch-Ersatz → api.get → Lader). */
async function setzen() {
	$.flush();
	for (let i = 0; i < 10; i++) await new Promise((r) => setTimeout(r, 0));
	$.flush();
}

// ── Pruefstand-Helfer ────────────────────────────────────────────────────────

const wurzeln: Array<() => void> = [];
afterEach(() => {
	while (wurzeln.length) wurzeln.pop()?.();
});

/** Startet den ECHTEN Lader in einer Effekt-Wurzel (im Browser: die Komponente). */
function inWurzel(echt: (...a: any[]) => any) {
	return (...args: any[]) => {
		let lader: any;
		wurzeln.push($.effect_root(() => { lader = echt(...args); }));
		return lader;
	};
}

const LADER_SAAT = {
	erstelleBriefingHistoryLader: inWurzel(erstelleBriefingHistoryLader),
	erstelleNaechstesBriefingLader: inWurzel(erstelleNaechstesBriefingLader)
};

/** Die ECHTE Herleitung `name` (Initialisierer aus dem Quelltext) erneut gegen `u` auswerten. */
function neuAuswerten(ast: Knoten, quelle: string, u: Knoten, name: string): unknown {
	for (const stmt of (ast.instance?.content?.body as Knoten[]) ?? []) {
		if (stmt.type !== 'VariableDeclaration') continue;
		for (const d of stmt.declarations as Knoten[]) {
			if (d.id?.type === 'Identifier' && d.id.name === name && d.init) {
				u[name] = werte(ohneTypen(quelle, d.init), u);
				return u[name];
			}
		}
	}
	throw new Error(`Deklaration „${name}" nicht gefunden`);
}

/** Props an einer Einbettung, wie der Mount sie uebergibt: fehlt das Attribut ⇒ undefined. */
function propsDerEinbettung(einbettung: Knoten, quelle: string, u: Knoten, namen: string[]): Knoten {
	const props: Knoten = {};
	for (const name of namen) {
		const a = ((einbettung.attributes ?? []) as Knoten[]).find((x) => x.type === 'Attribute' && x.name === name);
		if (!a) {
			props[name] = undefined;
			continue;
		}
		const v = Array.isArray(a.value) && a.value.length === 1 ? a.value[0] : a.value;
		if (v === true) props[name] = true;
		else if (v?.type === 'Text') props[name] = v.data;
		else if (v?.type === 'ExpressionTag') props[name] = werte(ohneTypen(quelle, v.expression), u);
		else throw new Error(`Attribut ${name}: unerwartete Wertform ${JSON.stringify(v?.type)}`);
	}
	return props;
}

const HU_LEER = { context: undefined, trip: undefined, preset: undefined, status: undefined, orte: undefined, saveController: undefined, onJump: undefined, children: undefined };

async function hubUebersicht(props: Knoten) {
	const umg = await umgebungFuer(HU, { ...HU_LEER, ...props, ...LADER_SAAT }, { jsAlsTs: true });
	// Pruefstand schluckt scheiternde Deklarationen — ohne Lader waere jede Zusicherung leer.
	for (const n of ['historie', 'naechstesBriefing', 'briefingId', 'modell']) {
		assert.ok(umg.u[n] != null, `Messaufbau: HubUebersicht-Herleitung „${n}" fehlt in der Umgebung`);
	}
	return umg;
}

/** Die eingebettete BriefingHistory mit den Props, die HubUebersicht ihr wirklich reicht. */
async function eingebetteteHistorie(hu: { ast: Knoten; quelle: string; u: Knoten }) {
	const einbettungen = findeKomponenten(hu.ast, 'BriefingHistory');
	assert.equal(einbettungen.length, 1, 'HubUebersicht bettet genau eine Versand-Historie ein');
	const props = propsDerEinbettung(einbettungen[0], hu.quelle, hu.u, ['id', 'kind', 'entries', 'lader']);
	const bh = await umgebungFuer(BH, { ...props });
	// Ihren eigenen Abruf-Effekt ausfuehren — wie beim Mount.
	for (const effekt of effekteVon(bh.ast, bh.quelle, bh.u)) effekt();
	await setzen();
	return props;
}

function zeilen(html: string): string[] {
	return [...html.matchAll(/data-testid="briefing-history-entry"[\s\S]*?<time datetime="([^"]+)"/g)].map((m) => m[1]);
}

function kennzahl(modell: any, id: string): any {
	const k = modell?.kennzahlen?.find((x: any) => x.id === id);
	assert.ok(k, `Kennzahl „${id}" fehlt`);
	return k;
}

// ── Fixtures ────────────────────────────────────────────────────────────────

const TRIP = {
	id: 't-2682',
	name: 'Testtrip',
	stages: [{ id: 's1', name: 'E1', date: '2099-07-01', waypoints: [] }],
	report_config: { enabled: true, morning_enabled: true, evening_enabled: false, morning_time: '07:00:00', evening_time: '18:00:00' },
	display_config: {}
};

const PRESET = {
	id: 'cp-2682',
	name: 'Vergleich',
	location_ids: ['l1', 'l2'],
	schedule: 'daily',
	previous_schedule: 'daily',
	profil: 'wandern',
	hour_from: 6,
	hour_to: 18,
	empfaenger: [],
	forecast_hours: 48,
	created_at: '2026-10-01T00:00:00Z',
	morning_enabled: true,
	morning_time: '07:00:00',
	display_config: {}
};

// ── F001: EIN Abruf der Versand-Historie, Kennzahl und Liste aus derselben Antwort ──

describe('F001 / AC-12: HubUebersicht ruft die Versand-Historie genau einmal ab', () => {
	for (const art of [
		{ context: 'route', id: TRIP.id, props: { trip: TRIP } },
		{ context: 'vergleich', id: PRESET.id, props: { preset: PRESET, orte: [] } }
	] as const) {
		test(`${art.context}: genau EIN Aufruf ${briefingHistoryUrl(art.id, art.context)} (Kennzahl + eingebettete Liste)`, async () => {
			const n = netz({ [`${art.context}:${art.id}`]: LOG });
			const hu = await hubUebersicht({ context: art.context, ...art.props });
			await setzen();
			const props = await eingebetteteHistorie(hu);
			assert.deepEqual(n.historienAbrufe(), [briefingHistoryUrl(art.id, art.context)], 'Abrufe: ' + JSON.stringify(n.historienAbrufe()));
			// Die Liste rendert die Eintraege DERSELBEN Antwort (neueste zuerst).
			const html = render(BriefingHistory, { props }).body;
			assert.deepEqual(zeilen(html), [...LOG].reverse().map((e) => e.sent_at), 'Historien-Liste zeigt nicht die geladenen Eintraege');
		});
	}

	test('route: „Zuletzt raus" zeigt den neuesten PLANMAESSIGEN Eintrag derselben Antwort', async () => {
		netz({ [`route:${TRIP.id}`]: LOG });
		const hu = await hubUebersicht({ context: 'route', trip: TRIP });
		await setzen();
		const modell = neuAuswerten(hu.ast, hu.quelle, hu.u, 'modell');
		const k = kennzahl(modell, 'zuletzt-raus');
		assert.notEqual(k.lang, '—', '„Zuletzt raus" bleibt „—" — der geladene Stand kommt im Modell nicht an');
		assert.equal(k.lang, formatLastSent(ABEND_29.sent_at));
		assert.equal(k.kurz, formatLastSent(ABEND_29.sent_at));
	});

	test('B02: Abruf scheitert ⇒ Versand-Historie zeigt ihren Fehlertext (Lader-Zustand „fehler")', async () => {
		const n = netz({ [`route:${TRIP.id}`]: 'fehler' });
		const hu = await hubUebersicht({ context: 'route', trip: TRIP });
		await setzen();
		const props = await eingebetteteHistorie(hu);
		assert.equal(n.historienAbrufe().length, 1, 'kein zweiter Abruf nach dem Fehler');
		const html = render(BriefingHistory, { props }).body;
		assert.match(html, /Versand-Historie konnte nicht geladen werden\./, 'Fehlertext fehlt');
		assert.doesNotMatch(html, /Lade Versand-Historie/, 'bleibt im Ladezustand haengen');
	});
});

// ── F002: „Naechster Versand" einmal laden, an die Trip-Hauptflaeche reichen ──

describe('F002 / AC-12: Trip — /api/next-briefings genau einmal, HubOverview zeigt das Zonenkuerzel', () => {
	test('TripTabs → HubUebersicht (children-Snippet) → HubOverview: ein Abruf, „07:00 (CET)"', async () => {
		const n = netz({});
		const hu = await hubUebersicht({ context: 'route', trip: TRIP });
		await setzen();

		// 1) Was HubUebersicht an `children` reicht: der echte Argument-Ausdruck des {@render}.
		const renders: Knoten[] = [];
		(function lauf(k: unknown): void {
			if (k === null || typeof k !== 'object') return;
			if (Array.isArray(k)) return k.forEach(lauf);
			const x = k as Knoten;
			const ruf = x.type === 'RenderTag' ? (x.expression?.type === 'ChainExpression' ? x.expression.expression : x.expression) : null;
			if (ruf?.callee?.name === 'children') renders.push(ruf);
			for (const key of Object.keys(x)) if (key !== 'parent' && key !== 'loc') lauf(x[key]);
		})(hu.ast.fragment);
		assert.equal(renders.length, 1, 'HubUebersicht rendert das children-Snippet genau einmal');
		const ausdruck = renders[0];
		assert.equal(ausdruck.arguments.length, 1, 'children bekommt genau ein Argument');
		const snippetWert = werte(ohneTypen(hu.quelle, ausdruck.arguments[0]), hu.u);

		// 2) TripTabs: das Snippet-Argument geht als `nextBriefing` an HubOverview.
		const ttQuelle = readFileSync(TRIP_TABS, 'utf-8');
		const ttAst: Knoten = parse(ttQuelle, { modern: true });
		const [huEinbettung] = findeKomponenten(ttAst, 'HubUebersicht');
		assert.ok(huEinbettung, 'TripTabs bettet HubUebersicht ein');
		const snippet = (huEinbettung.fragment?.nodes as Knoten[]).find((x) => x.type === 'SnippetBlock' && x.expression?.name === 'children');
		assert.ok(snippet, 'HubUebersicht in TripTabs traegt ein children-Snippet');
		const param = snippet.parameters?.[0]?.name as string;
		const [hoEinbettung] = findeKomponenten({ fragment: snippet.body }, 'HubOverview');
		assert.ok(hoEinbettung, 'HubOverview sitzt im children-Snippet');
		const hoProps = propsDerEinbettung(hoEinbettung, ttQuelle, { [param]: snippetWert }, ['nextBriefing']);

		// 3) HubOverview mit dem gereichten Wert: kein eigener Abruf, Zeit mit Zonenkuerzel.
		const ho = await umgebungFuer(
			HUB_OVERVIEW,
			{ trip: TRIP, onJump: undefined, metricsCatalog: null, ...hoProps, ...LADER_SAAT },
			{ jsAlsTs: true }
		);
		assert.ok(ho.u.naechstesBriefing, 'Messaufbau: HubOverview-Lader fehlt in der Umgebung');
		await setzen();
		assert.deepEqual(n.naechsteAbrufe(), [`/api/next-briefings?trip_id=${TRIP.id}`], 'Abrufe: ' + JSON.stringify(n.naechsteAbrufe()));
		neuAuswerten(ho.ast, ho.quelle, ho.u, 'briefing');
		const morgen = neuAuswerten(ho.ast, ho.quelle, ho.u, 'morgenZeit');
		assert.equal(morgen, '07:00 (CET)', 'HubOverview zeigt die Slot-Zeit ohne Zonenkuerzel — der Wert kam nicht an');
	});
});

// ── F003: lokales Pausieren erreicht die Status-Kennzahl ─────────────────────

describe('F003 / AC-3: CompareTabs reicht den lokalen Status an HubUebersicht', () => {
	test('echter Pause-Weg (handleToggleActive, PUT) ⇒ Status-Kennzahl „Pausiert", obwohl das Preset noch „daily" traegt', async () => {
		netz({});
		const stand: Knoten = { ...PRESET };
		const puts: Array<{ url: string; body: unknown }> = [];
		// Ersatz-Server des Schreibwegs (Merge wie der Go-Store, vgl. compare_hub_pausieren_kette.test.ts).
		const server = {
			put: async (url: string, body: unknown) => {
				puts.push({ url, body });
				Object.assign(stand, body);
				return { ...stand };
			},
			get: async () => ({ ...stand })
		};
		const ctl: Knoten = { setSaving() {}, setSaved() {}, setError() {}, flush: async () => {}, imWiederholen: false };
		const ct = await umgebungFuer(COMPARE_TABS, {
			preset: { ...PRESET },
			locations: [],
			saveController: ctl,
			api: server,
			extractMessage: (e: any) => String(e?.message ?? e),
			onScheduleChange: () => {}
		});
		ct.u.currentPreset = { ...PRESET };
		const einbettungen = findeKomponenten(ct.ast, 'HubUebersicht');
		assert.equal(einbettungen.length, 1, 'CompareTabs bettet HubUebersicht genau einmal ein');
		const statusText = async () => {
			const props = propsDerEinbettung(einbettungen[0], ct.quelle, ct.u, ['context', 'preset', 'status']);
			const hu = await hubUebersicht(props);
			return kennzahl(neuAuswerten(hu.ast, hu.quelle, hu.u, 'modell'), 'status').lang;
		};
		assert.equal(await statusText(), 'Läuft automatisch', 'Messaufbau: vor dem Pausieren aktiv');

		await ct.u.handleToggleActive();
		assert.deepEqual(puts.map((p) => p.url), [`/api/compare/presets/${PRESET.id}`], 'Messaufbau: der Pause-Weg hat geschrieben');
		assert.equal(ct.u.localSchedule, 'manual');
		neuAuswerten(ct.ast, ct.quelle, ct.u, 'status');
		assert.equal(await statusText(), 'Pausiert', 'lokales Pausieren kommt in der Übersicht nicht an');
	});
});
