// Fix-Loop 1 — Issue #3305 (Spec docs/specs/modules/feat_3305_tabelle_trip_anlegen.md, AC-1, AC-2, AC-10).
// Adversary-Protokoll docs/artifacts/feat-3305-tabelle-trip-anlegen/adversary-dialog.md: die Einzelteile waren
// geprüft, der Weg Karte -> Editor -> POST nicht (überlebende Mutationen M4, M5, M6, M10).
//
// Gemessen dort, wo es WIRKT: die ECHTEN Instanz-Skripte von TripNewEditor.svelte, WetterTabInhalt.svelte und
// WasStehtWoKarte.svelte (svelteInstanzPruefstand.ts), verbunden über die ECHTEN Attribut-Ausdrücke ihrer
// Einbettungen (`<WetterTab …>` im Editor, `<WasStehtWoKarte …>` im Reiter), ausgewertet in der Umgebung des
// jeweiligen Eltern-Skripts (Muster f002_trip_anlegen_ampel_im_post.test.ts). Der POST läuft über den echten
// `buildAndSave` -> `buildCreateTripPayload` und wird am gesäten `api.post` mitgeschnitten. Vorlagen/Katalog
// live aus dem Python-Core; die Vorschau der Karte beantwortet ein Client im Speicher (kein Netz).
//   M4  Kartenmeldung -> karteStand -> POST trägt display_config.placements
//   M5  Neuaufbau (Wechsel Desktop <-> Mobil): die neue Karte startet aus dem Stand des Editors
//   M6  Metrikwechsel im Reiter Wetter lädt die Vorschau genau einmal nach, nach dem Melden an den Editor;
//       reine Nicht-Metrik-Änderungen laden nichts
//   M10 Die Karte steht im Anlegen nur mit Rückkanal (Orte-Anlegen ohne onAnlegeKarte: keine Karte, #3306)
//   Fix-Loop 2 (adversary-dialog-runde2.md): F-A1 Metrik im Reiter entfernt -> Zeile weg im Kartenstand UND im POST;
//   F-A2 Vorschau-Rumpf über die echte Einbettung trägt die aktuelle Metrikauswahl; F-A3 eine Kartenmeldung
//   baut den Reiter nicht neu auf (wetterNeuaufbau bleibt).
//
//   cd frontend && npm test -- src/lib/components/trip-new/__tests__/trip_anlegen_karte_verdrahtung_3305.test.ts

import { test, describe, beforeEach, afterEach, mock } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { umgebungFuer, findeKomponenten, attributAusdruck, ohneTypen, werte, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import { aufloesungPost, live } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const EDITOR = join(HIER, '..', 'TripNewEditor.svelte');
const WETTER_TAB = join(HIER, '..', '..', 'organisms', 'wetter-tab', 'WetterTabInhalt.svelte');
const KARTE = join(HIER, '..', '..', 'organisms', 'wetter-tab', 'WasStehtWoKarte.svelte');
register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any

const LIVE_API = {
	get: async (pfad: string) => {
		const d = live();
		if (pfad === '/api/metrics') return d.metrics;
		if (pfad === '/api/templates') return d.templates;
		if (pfad === '/api/metric-presets') return [];
		throw new Error(`unerwartet: ${pfad}`);
	},
	post: aufloesungPost()
};
const ruhe = () => new Promise((r) => setImmediate(r));
const z = (state: string, extra: J = {}) => ({ state, format: null, reason: null, example: null, ampel: null, mark: null, ...extra });
function vorschau(ids: string[]): J {
	return {
		kind: 'route', lang: 'de', stored: false,
		placements: { version: 1, rows: ids.map((metric_id) => ({ metric_id })) },
		location_count: null,
		columns: ['email', 'telegram', 'sms', 'outlook'].map((stelle) => ({ stelle, subtitle: 'x', block_off: false, rests: null })),
		fixed_rows: [],
		rows: ids.map((metric_id, position) => ({ metric_id, name: metric_id, position, parent: null, cells: { email: z('on', { format: 'simplified' }), telegram: z('on'), sms: z('on'), outlook: z('on') } })),
		sms_example: { text: 'E: W30', length: 6, max_length: 160 },
		outlook_reports: ['evening'],
		blocks: { show_stage_stats: true, show_yesterday_comparison: true, show_night_block: true, email_format: 'full', telegram_style: 'rich' },
		legend: { metrics: [], fixed: [] },
		example_version: 1
	};
}

beforeEach(() => {
	mock.timers.enable({ apis: ['setTimeout'] });
	globalThis.fetch = (async () => ({ ok: true, json: async () => ({}) }) as Response) as typeof fetch;
});
afterEach(() => mock.timers.reset());

/** Wert eines Attributs an einer echten Einbettung, ausgewertet in der Umgebung des Eltern-Skripts. */
function attr(einbettung: Knoten, quelle: string, name: string, u: Knoten): unknown {
	if (attributAusdruck(einbettung, quelle, name) === null) return undefined;
	const a = (einbettung.attributes as Knoten[]).find((x) => x.type === 'Attribute' && x.name === name)!;
	// Typ-Annotationen im Ausdruck (z. B. `as unknown as Trip`) per AST ausgeblendet.
	return a.value?.type === 'ExpressionTag' ? werte(ohneTypen(quelle, a.value.expression), u) : werte(name, u);
}
const dekl = (ast: Knoten, name: string) =>
	(ast.instance.content.body as Knoten[]).filter((s) => s.type === 'VariableDeclaration').flatMap((s) => s.declarations as Knoten[]).find((d) => d.id?.name === name);

async function editor() {
	const gesendet: Array<{ url: string; payload: J }> = [];
	const { ast, quelle, u } = await umgebungFuer(EDITOR, {
		stateOverride: undefined,
		untrack: (fn: () => unknown) => fn(),
		api: { post: async (url: string, payload: J) => (gesendet.push({ url, payload }), { id: 'neu-1' }) }
	});
	const neuAbleiten = () => {
		u.stubTrip = werte(ohneTypen(quelle, dekl(ast, 'stubTrip')!.init), u);
		u.wetterAnlegeTrip = werte(ohneTypen(quelle, dekl(ast, 'wetterAnlegeTrip')!.init), u);
	};
	const speichern = async () => {
		u.ready = true; // hängt am GPX-Upload, für den Speicherweg ohne Belang
		gesendet.length = 0;
		u.savedTripId = null;
		assert.equal(await u.buildAndSave(), 'neu-1', `buildAndSave scheiterte: ${u.saveError}`);
		assert.equal(gesendet.length, 1);
		return gesendet[0].payload;
	};
	return { ast, quelle, u, neuAbleiten, speichern };
}
type Ed = Awaited<ReturnType<typeof editor>>;

/** Reiter Wetter, gemountet wie die `i`-te `<WetterTab>`-Einbettung im Editor (0 = Desktop, 1 = Mobil). */
async function reiter(ed: Ed, i: number) {
	ed.neuAbleiten();
	const e = findeKomponenten(ed.ast, 'WetterTab')[i];
	assert.ok(e, 'Messaufbau: WetterTab-Einbettung fehlt');
	const props: Knoten = { context: 'route', preset: undefined, saveController: undefined, enqueueHubWrite: undefined, onTripUpdate: undefined, onCompareUpdate: undefined };
	for (const n of ['trip', 'createMode', 'onAnlegeStand', 'karteStart', 'onAnlegeKarte']) props[n] = attr(e, ed.quelle, n, ed.u);
	const wt = await umgebungFuer(WETTER_TAB, { ...props, api: LIVE_API });
	await wt.u.laden();
	assert.equal(wt.u.phase, 'bereit', 'Messaufbau: Reiter Wetter hat nicht geladen');
	return wt;
}
type Wt = Awaited<ReturnType<typeof reiter>>;

/** Karte, gemountet wie die `<WasStehtWoKarte>`-Einbettung im Reiter, erste Vorschau beantwortet. */
async function karte(wt: Wt) {
	const e = findeKomponenten(wt.ast, 'WasStehtWoKarte')[0];
	const props: Knoten = { saveController: undefined, enqueueHubWrite: undefined, onUebernahme: undefined };
	for (const n of ['context', 'id', 'createMode', 'entwurf', 'start', 'onAnlegeStand']) props[n] = attr(e, wt.quelle, n, wt.u);
	const aufrufe: Array<{ pfad: string; rumpf: J; erledigen: (w: unknown) => void }> = [];
	const api = { post: (pfad: string, rumpf: unknown) => new Promise((erledigen) => aufrufe.push({ pfad, rumpf: JSON.parse(JSON.stringify(rumpf)), erledigen })) };
	const ids = (wt.u.stand.auswahl as string[]).slice();
	const mounts: Array<() => unknown> = [];
	const k = await umgebungFuer(KARTE, { ...props, api, untrack: (fn: () => unknown) => fn(), onMount: (fn: () => unknown) => void mounts.push(fn), antwort: vorschau(ids) });
	for (const stmt of k.ast.instance.content.body as Knoten[]) {
		const x = stmt.type === 'ExpressionStatement' ? (stmt.expression as Knoten) : null;
		if (x?.type === 'CallExpression' && x.callee?.name === 'onMount') werte(ohneTypen(k.quelle, x), k.u);
	}
	for (const m of mounts) m();
	await ruhe();
	assert.equal(aufrufe.length, 1, 'Messaufbau: die Karte lädt im Anlegen über die Vorschau');
	aufrufe[0].erledigen(vorschau(ids));
	await ruhe();
	return { u: k.u, ids, aufrufe };
}
const zeile = (pl: J, m: string) => pl?.rows?.find((r: J) => r.metric_id === m);

describe('#3305 M4 (AC-2): Kartenbedienung -> Editor -> genau der Anlege-POST trägt die Tabelle', () => {
	test('Haken in der Karte steht im POST display_config.placements', async () => {
		const ed = await editor();
		const k = await karte(await reiter(ed, 0));
		const m = k.ids[0];
		k.u.haken({ metrik: m, stelle: 'telegram', an: false });
		const p = await ed.speichern();
		assert.equal(zeile(p.display_config?.placements, m)?.places?.telegram, false, 'bediente Karte, aber POST ohne ihren Stand');
	});

	test('Karte nie bedient: POST ohne placements (AC-7, Gegenprobe)', async () => {
		const ed = await editor();
		await karte(await reiter(ed, 0));
		const p = await ed.speichern();
		assert.equal('placements' in (p.display_config ?? {}), false);
	});
});

describe('#3305 M5 (AC-1): Neuaufbau beim Wechsel Desktop <-> Mobil behält den Kartenstand', () => {
	for (const [von, nach, name] of [[0, 1, 'Desktop -> Mobil'], [1, 0, 'Mobil -> Desktop']] as const) {
		test(name, async () => {
			const ed = await editor();
			const k1 = await karte(await reiter(ed, von));
			const m = k1.ids[0];
			k1.u.haken({ metrik: m, stelle: 'telegram', an: false });
			k1.u.reihenfolge([...k1.ids].reverse());
			const k2 = await karte(await reiter(ed, nach));
			const mit = k2.u.placementsZumMitspeichern();
			assert.equal(zeile(mit, m)?.places?.telegram, false, 'neu aufgebaute Karte hat den Haken verloren');
			assert.deepEqual(mit?.rows.map((r: J) => r.metric_id), [...k1.ids].reverse(), 'neu aufgebaute Karte hat die Reihenfolge verloren');
			// Ein Schalter nach dem Neuaufbau verliert den Tabellenstand nicht.
			k2.u.feld('show_night_block', false);
			const p = await ed.speichern();
			assert.equal(zeile(p.display_config?.placements, m)?.places?.telegram, false);
			assert.equal(p.display_config?.show_night_block, false);
		});
	}
});

describe('#3305 M6 (AC-10): Metrikwechsel lädt die Vorschau der Karte nach — nach dem Melden an den Editor', () => {
	test('Metrik entfernt: genau ein Nachladen, Editor kennt die neue Auswahl schon; Nicht-Metrik-Änderung lädt nichts', async () => {
		const ed = await editor();
		const wt = await reiter(ed, 0);
		const weg = (wt.u.stand.auswahl as string[])[0];
		const nachladen: string[][] = [];
		wt.u.karte = {
			grundauswahlGeaendert: () => {},
			placementsZumMitspeichern: () => undefined,
			nachFremdemSpeichern: () => {},
			vorschauNachMetrik: () => nachladen.push((ed.u.weatherMetrics as J[]).filter((x) => x.enabled).map((x) => x.metric_id))
		};
		wt.u.entfernen(weg);
		assert.equal(nachladen.length, 1, 'Metrikwechsel ohne Nachladen der Vorschau');
		assert.equal(nachladen[0].includes(weg), false, 'Nachladen vor dem Melden: der Entwurf trüge noch die alte Auswahl');
		wt.u.aendern({ ...wt.u.stand, warnungenAn: !wt.u.stand.warnungenAn });
		wt.u.aendern({ ...wt.u.stand, tagesfenster: { start: 7, end: 20 } });
		assert.equal(nachladen.length, 1, 'Änderung ohne Metrikwechsel hat die Vorschau nachgeladen');
	});
});

describe('#3305 M10: die Karte steht im Anlegen nur mit Rückkanal', () => {
	/** Bedingung des `{#if}` um die Karte, ausgewertet in der Umgebung des Reiters. */
	async function sichtbar(saat: Knoten): Promise<boolean> {
		const { ast, quelle, u } = await umgebungFuer(WETTER_TAB, { preset: undefined, onAnlegeKarte: undefined, ...saat });
		let test: Knoten | null = null;
		const lauf = (n: unknown, bedingung: Knoten | null): void => {
			if (!n || typeof n !== 'object') return;
			if (Array.isArray(n)) return n.forEach((x) => lauf(x, bedingung));
			const k = n as Knoten;
			if (k.type === 'Component' && k.name === 'WasStehtWoKarte') test = bedingung;
			for (const key of Object.keys(k)) if (key !== 'parent' && key !== 'loc') lauf(k[key], k.type === 'IfBlock' && key === 'consequent' ? k.test : bedingung);
		};
		lauf(ast.fragment, null);
		assert.ok(test, 'Messaufbau: keine Bedingung um die Karte');
		return Boolean(werte(quelle.slice((test as Knoten).start, (test as Knoten).end), u));
	}
	test('Orte-Anlegen ohne onAnlegeKarte: keine Karte (ihr Stand käme nicht in den POST)', async () => {
		assert.equal(await sichtbar({ context: 'vergleich', createMode: true, preset: { id: '__new__' } }), false);
	});
	test('Trip-Anlegen mit Rückkanal: Karte', async () => {
		assert.equal(await sichtbar({ context: 'route', createMode: true, trip: { id: '__new__' }, onAnlegeKarte: () => {} }), true);
	});
	test('Hub (gespeicherter Trip): Karte', async () => {
		assert.equal(await sichtbar({ context: 'route', createMode: false, trip: { id: 't1' } }), true);
	});
});

describe('#3305 Fix-Loop 2 (AC-5, AC-10): Metrikwechsel im Reiter -> Karte -> Vorschau und POST, über die echten Einbettungen', () => {
	test('F-A1/F-A2: Metrik entfernen — Zeile entfällt im Kartenstand und im POST, Haken bleibt; Vorschau-Rumpf trägt die neue Auswahl', async () => {
		const ed = await editor();
		const wt = await reiter(ed, 0);
		const k = await karte(wt);
		wt.u.karte = k.u; // bind:this={karte}
		const [weg, bleibt] = k.ids;
		k.u.haken({ metrik: bleibt, stelle: 'telegram', an: false });
		wt.u.entfernen(weg);
		// Svelte reicht den neu abgeleiteten Entwurf als Prop `trip` an den Reiter weiter.
		ed.neuAbleiten();
		wt.u.trip = ed.u.wetterAnlegeTrip;
		assert.equal(zeile(ed.u.karteStand?.placements, weg), undefined, 'Kartenstand trägt noch die Zeile der entfernten Metrik');
		mock.timers.tick(2000);
		await ruhe();
		assert.equal(k.aufrufe.length, 2, 'Metrikwechsel: genau ein Nachladen der Vorschau');
		const rumpf = k.aufrufe[1].rumpf;
		const aktiv = ((rumpf?.display_config?.metrics ?? []) as J[]).filter((m) => m.enabled).map((m) => m.metric_id);
		assert.ok(aktiv.length > 0, 'Vorschau-Rumpf ohne Metrikauswahl');
		assert.equal(aktiv.includes(weg), false, 'Vorschau-Rumpf trägt noch die entfernte Metrik');
		assert.ok(aktiv.includes(bleibt));
		assert.equal(zeile(rumpf?.display_config?.placements, weg), undefined);
		const p = await ed.speichern();
		assert.equal(zeile(p.display_config?.placements, weg), undefined, 'POST trägt die Zeile der entfernten Metrik');
		assert.equal(zeile(p.display_config?.placements, bleibt)?.places?.telegram, false, 'Haken nach Metrikwechsel verloren');
	});

	test('F-A3: eine Kartenmeldung baut den Reiter Wetter nicht neu auf', async () => {
		const ed = await editor();
		const k = await karte(await reiter(ed, 0));
		const vorher = ed.u.wetterNeuaufbau;
		k.u.haken({ metrik: k.ids[0], stelle: 'telegram', an: false });
		k.u.feld('show_night_block', false);
		assert.ok(ed.u.karteStand, 'Messaufbau: Meldung kam nicht an');
		assert.equal(ed.u.wetterNeuaufbau, vorher, 'Kartenmeldung löst einen Neuaufbau aus (Karte würde je Klick neu montiert)');
	});
});
