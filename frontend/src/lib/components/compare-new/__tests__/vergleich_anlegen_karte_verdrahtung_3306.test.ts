// TDD RED — Issue #3306 (Teil C von #3041, Epic #3122), Spec docs/specs/modules/feat_3306_tabelle_orte_anlegen.md,
// Test Plan Nr. 4 (AC-1, AC-2, AC-3, AC-4). Pendant zu trip-new/__tests__/trip_anlegen_karte_verdrahtung_3305.test.ts.
//
// Gemessen dort, wo es WIRKT: die ECHTEN Instanz-Skripte von CompareNewEditor.svelte, WetterTabInhalt.svelte und
// WasStehtWoKarte.svelte (svelteInstanzPruefstand.ts), verbunden über die ECHTEN Attribut-Ausdrücke ihrer
// Einbettungen (`<WetterTab …>` im Editor, Desktop = 0, Mobil = 1; `<WasStehtWoKarte …>` im Reiter), ausgewertet in
// der Umgebung des jeweiligen Eltern-Skripts. Der POST läuft über den echten `speichereNeuenVergleich` ->
// `legeVergleichAn` -> `baueVergleichAnlegeRumpf` und wird am gesäten `api.post` mitgeschnitten; jeder PUT
// (Editor oder Karte) würde ebenfalls mitgeschnitten. Vorlagen/Katalog live aus dem Python-Core; die Vorschau der
// Karte beantwortet ein Client im Speicher (kein Netz).
//   V1  Sichtbarkeit: an beiden WetterTab-Stellen steht die Karte im Anlegen (Rückkanal `onAnlegeKarte` gesetzt).
//   V2  Kartenbedienung (Haken, Format, Reihenfolge, Ausblick) -> Editor (`karteStand`) -> genau ein POST trägt
//       display_config.placements; kein PUT.
//   V3  Schalter der Karte (Stundenverlauf, Telegram-Kurzstil) -> POST hourly_enabled / display_config.telegram_style.
//   V4  Neuaufbau (Wechsel Desktop <-> Mobil, Schritt vor und zurück): die neue Karte startet aus dem Editor-Stand.
//   V5  Vorschau-Entwurf `wetterAbo` trägt die gewählten Orte, hourly_enabled und telegram_style des Feldsatzes.
//   V6  Karte nie bedient: POST ohne placements (AC-5, Gegenprobe).
//
//   cd frontend && npm test -- src/lib/components/compare-new/__tests__/vergleich_anlegen_karte_verdrahtung_3306.test.ts

import { test, describe, before, after, beforeEach, afterEach, mock } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { umgebungFuer, findeKomponenten, attributAusdruck, ohneTypen, werte, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import { live, REPO } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';
import { toCompareSelectionEntries } from '../../shared/weather-metrics-tab/compareMetricSelection.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const EDITOR = join(HIER, '..', 'CompareNewEditor.svelte');
const WETTER_TAB = join(HIER, '..', '..', 'organisms', 'wetter-tab', 'WetterTabInhalt.svelte');
const KARTE = join(HIER, '..', '..', 'organisms', 'wetter-tab', 'WasStehtWoKarte.svelte');
register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any

const PY_KATALOG = [
	'import sys, json',
	"sys.path.insert(0, 'src'); sys.path.insert(0, '.')",
	'from output.renderers.compare_metric_catalog import get_compare_metric_catalog',
	"print(json.dumps({'metrics': get_compare_metric_catalog(lang='de')}, ensure_ascii=False))"
].join('\n');
const KATALOG_ANTWORT = JSON.parse(execFileSync('uv', ['run', 'python3', '-c', PY_KATALOG], { cwd: REPO, encoding: 'utf-8' }).trim());
const KATALOG = toCompareSelectionEntries(KATALOG_ANTWORT);
const ORTE = ['ort-a', 'ort-b'];

const LIVE_API = {
	get: async (pfad: string) => {
		const d = live();
		if (pfad === '/api/metrics') return d.metrics;
		if (pfad === '/api/templates') return d.templates;
		if (pfad === '/api/metric-presets') return [];
		throw new Error(`unerwartet: ${pfad}`);
	}
};
const ruhe = () => new Promise((r) => setImmediate(r));
const z = (state: string, extra: J = {}) => ({ state, format: null, reason: null, example: null, ampel: null, mark: null, ...extra });
function vorschau(ids: string[]): J {
	return {
		kind: 'vergleich', lang: 'de', stored: false,
		placements: { version: 1, rows: ids.map((metric_id) => ({ metric_id })), outlook_reports: ['evening'] },
		location_count: ORTE.length,
		columns: ['email', 'telegram', 'sms', 'outlook'].map((stelle) => ({ stelle, subtitle: 'x', block_off: false, rests: null })),
		fixed_rows: [],
		rows: ids.map((metric_id, position) => ({ metric_id, name: metric_id, position, parent: null, cells: { email: z('on', { format: 'simplified' }), telegram: z('on'), sms: z('on'), outlook: z('on') } })),
		sms_example: { text: 'A: W30', length: 6, max_length: 160 },
		outlook_reports: ['evening'],
		blocks: { hourly: true, telegram_style: 'rich' },
		legend: { metrics: [], fixed: [] },
		example_version: 1
	};
}

/** Netzgrenze: GET /api/compare/metrics (Katalog-Lader des Editors) echt aus dem Kern, sonst 404. */
let vorherFetch: typeof globalThis.fetch;
before(() => {
	vorherFetch = globalThis.fetch;
});
after(() => {
	globalThis.fetch = vorherFetch;
});
beforeEach(() => {
	mock.timers.enable({ apis: ['setTimeout'] });
	globalThis.fetch = (async (input: unknown) => {
		const pfad = new URL(String(input), 'http://gz.invalid').pathname;
		if (pfad === '/api/compare/metrics') return new Response(JSON.stringify(KATALOG_ANTWORT), { status: 200, headers: { 'Content-Type': 'application/json' } });
		return new Response('{}', { status: 404 });
	}) as typeof fetch;
});
afterEach(() => mock.timers.reset());

/** Wert eines Attributs an einer echten Einbettung, ausgewertet in der Umgebung des Eltern-Skripts. */
function attr(einbettung: Knoten, quelle: string, name: string, u: Knoten): unknown {
	if (attributAusdruck(einbettung, quelle, name) === null) return undefined;
	const a = (einbettung.attributes as Knoten[]).find((x) => x.type === 'Attribute' && x.name === name)!;
	// Text-Attribut (`context="vergleich"`): der wörtliche Wert.
	if (Array.isArray(a.value) && a.value.every((t: Knoten) => t.type === 'Text')) return a.value.map((t: Knoten) => t.data).join('');
	return a.value?.type === 'ExpressionTag' ? werte(ohneTypen(quelle, a.value.expression), u) : werte(name, u);
}
const dekl = (ast: Knoten, name: string) =>
	(ast.instance.content.body as Knoten[]).filter((s) => s.type === 'VariableDeclaration').flatMap((s) => s.declarations as Knoten[]).find((d) => d.id?.name === name);

async function editor() {
	const gesendet: Array<{ methode: string; url: string; payload: J }> = [];
	const mitschnitt = (methode: string) => async (url: string, payload: J) => (gesendet.push({ methode, url, payload: JSON.parse(JSON.stringify(payload)) }), { id: 'neu-1' });
	const { ast, quelle, u } = await umgebungFuer(EDITOR, {
		untrack: (fn: () => unknown) => fn(),
		stateOverride: { name: 'Vergleich-3306', pickedIds: ORTE },
		vorlage: null,
		locations: ORTE.map((id) => ({ id, name: id, lat: 47, lon: 11 })),
		alarmeCatalog: KATALOG, // Stand nach onMount (hydrateAlarmeTab)
		api: { post: mitschnitt('POST'), put: mitschnitt('PUT'), patch: mitschnitt('PATCH') }
	});
	assert.equal(typeof u.speichereNeuenVergleich, 'function', 'Messaufbau: speichereNeuenVergleich nicht herleitbar');
	const wetterAboDekl = dekl(ast, 'wetterAbo');
	assert.ok(wetterAboDekl, 'Messaufbau: wetterAbo fehlt im Editor');
	/** `wetterAbo` ist `$derived` — Svelte leitet ihn bei jeder Änderung neu ab; hier der ECHTE Ausdruck neu ausgewertet. */
	const neuAbleiten = () => {
		u.wetterAbo = werte(ohneTypen(quelle, wetterAboDekl!.init), u);
	};
	const speichern = async () => {
		gesendet.length = 0;
		await u.speichereNeuenVergleich();
		const posts = gesendet.filter((g) => g.methode === 'POST');
		assert.equal(gesendet.filter((g) => g.methode !== 'POST').length, 0, `Schreibaufruf außer dem POST: ${JSON.stringify(gesendet.map((g) => g.methode + ' ' + g.url))}`);
		assert.equal(posts.length, 1, 'nicht genau ein POST');
		assert.equal(posts[0].url, '/api/compare/presets');
		return posts[0].payload;
	};
	return { ast, quelle, u, gesendet, neuAbleiten, speichern };
}
type Ed = Awaited<ReturnType<typeof editor>>;

/** Reiter Wetter, gemountet wie die `i`-te `<WetterTab>`-Einbettung im Editor (0 = Desktop, 1 = Mobil). */
async function reiter(ed: Ed, i: number) {
	ed.neuAbleiten();
	const e = findeKomponenten(ed.ast, 'WetterTab')[i];
	assert.ok(e, 'Messaufbau: WetterTab-Einbettung fehlt');
	const props: Knoten = { trip: undefined, saveController: undefined, enqueueHubWrite: undefined, onTripUpdate: undefined, onCompareUpdate: undefined };
	for (const n of ['context', 'preset', 'createMode', 'onAnlegeStand', 'karteStart', 'onAnlegeKarte']) props[n] = attr(e, ed.quelle, n, ed.u);
	assert.equal(props.context, 'vergleich', 'Messaufbau: Einbettung nicht im Kontext vergleich');
	const wt = await umgebungFuer(WETTER_TAB, { ...props, api: LIVE_API });
	await wt.u.laden();
	assert.equal(wt.u.phase, 'bereit', 'Messaufbau: Reiter Wetter hat nicht geladen');
	// Erster Stand-Bericht an den Editor (handleWetterAnlegeStand lädt den Katalog asynchron).
	for (let n = 0; n < 5; n++) await ruhe();
	return wt;
}
type Wt = Awaited<ReturnType<typeof reiter>>;

/** Karte, gemountet wie die `<WasStehtWoKarte>`-Einbettung im Reiter, erste Vorschau beantwortet. */
async function karte(wt: Wt) {
	const e = findeKomponenten(wt.ast, 'WasStehtWoKarte')[0];
	const props: Knoten = { saveController: undefined, enqueueHubWrite: undefined, onUebernahme: undefined };
	for (const n of ['context', 'id', 'createMode', 'entwurf', 'start', 'onAnlegeStand']) props[n] = attr(e, wt.quelle, n, wt.u);
	const aufrufe: Array<{ pfad: string; rumpf: J; erledigen: (w: unknown) => void }> = [];
	const puts: string[] = [];
	const api = {
		post: (pfad: string, rumpf: unknown) => new Promise((erledigen) => aufrufe.push({ pfad, rumpf: JSON.parse(JSON.stringify(rumpf)), erledigen })),
		put: async (pfad: string) => (puts.push(pfad), {}),
		get: async (pfad: string) => {
			throw new Error(`GET im Anlegen: ${pfad}`);
		}
	};
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
	assert.equal(aufrufe[0].pfad, '/api/briefings/placements/vorschau?kind=vergleich');
	aufrufe[0].erledigen(vorschau(ids));
	await ruhe();
	/** Schalter wie in der Ansicht; `aktFelder` ist `$derived(felder ?? …)` und wird hier wie in Svelte nachgeführt. */
	const schalter = (name: string, wert: unknown) => {
		k.u.feld(name, wert);
		k.u.aktFelder = k.u.felder;
	};
	return { u: k.u, ids, aufrufe, puts, schalter };
}
const zeile = (pl: J, m: string) => pl?.rows?.find((r: J) => r.metric_id === m);

/** Bedingung des `{#if}` um die Karte, ausgewertet in der Umgebung des Reiters. */
async function karteSichtbar(saat: Knoten): Promise<boolean> {
	const { ast, quelle, u } = await umgebungFuer(WETTER_TAB, { trip: undefined, onAnlegeKarte: undefined, ...saat });
	let bedingung: Knoten | null = null;
	const lauf = (n: unknown, b: Knoten | null): void => {
		if (!n || typeof n !== 'object') return;
		if (Array.isArray(n)) return n.forEach((x) => lauf(x, b));
		const k = n as Knoten;
		if (k.type === 'Component' && k.name === 'WasStehtWoKarte') bedingung = b;
		for (const key of Object.keys(k)) if (key !== 'parent' && key !== 'loc') lauf(k[key], k.type === 'IfBlock' && key === 'consequent' ? k.test : b);
	};
	lauf(ast.fragment, null);
	assert.ok(bedingung, 'Messaufbau: keine Bedingung um die Karte');
	return Boolean(werte(quelle.slice((bedingung as Knoten).start, (bedingung as Knoten).end), u));
}

describe('#3306 V1 (AC-1): die Karte steht beim Ortsvergleich-Anlegen an beiden Stellen (Desktop, Mobil)', () => {
	for (const [i, name] of [[0, 'Desktop'], [1, 'Mobil']] as const) {
		test(`${name}: Einbettung reicht Rückkanal und Startstand durch, die Karte ist sichtbar`, async () => {
			const ed = await editor();
			ed.neuAbleiten();
			const e = findeKomponenten(ed.ast, 'WetterTab')[i];
			assert.ok(e, 'Messaufbau: WetterTab-Einbettung fehlt');
			const props: Knoten = {};
			for (const n of ['context', 'preset', 'createMode', 'onAnlegeKarte']) props[n] = attr(e, ed.quelle, n, ed.u);
			assert.equal(typeof props.onAnlegeKarte, 'function', `${name}: onAnlegeKarte fehlt — ohne Rückkanal keine Karte (ihr Stand käme nicht in den POST)`);
			assert.notEqual(attributAusdruck(e, ed.quelle, 'karteStart'), null, `${name}: karteStart fehlt — Stand ginge beim Neuaufbau verloren`);
			assert.equal(await karteSichtbar(props), true, `${name}: Karte im Anlegen nicht sichtbar`);
		});
	}
});

describe('#3306 V2 (AC-2, AC-4): Kartenbedienung -> Editor -> genau der Anlege-POST trägt die Tabelle', () => {
	test('Haken, Format, Reihenfolge und Ausblick in der Karte stehen im POST display_config.placements; kein PUT', async () => {
		const ed = await editor();
		const k = await karte(await reiter(ed, 0));
		const [m0, m1] = k.ids;
		k.u.haken({ metrik: m0, stelle: 'telegram', an: false });
		k.u.format({ metrik: m1, stelle: 'email', format: 'raw' });
		k.u.reihenfolge([...k.ids].reverse());
		k.u.ausblick('morning', true);
		assert.ok(ed.u.karteStand, 'Kartenmeldung kam nicht beim Editor an (onAnlegeKarte -> karteStand)');
		const p = await ed.speichern();
		const pl = p.display_config?.placements;
		assert.equal(zeile(pl, m0)?.places?.telegram, false, 'bediente Karte, aber POST ohne ihren Haken');
		assert.equal(zeile(pl, m1)?.formats?.email, 'raw', 'Format der Karte fehlt im POST');
		assert.deepEqual(pl?.rows.map((r: J) => r.metric_id), [...k.ids].reverse(), 'Reihenfolge der Karte fehlt im POST');
		assert.deepEqual([...(pl?.outlook_reports ?? [])].sort(), ['evening', 'morning'], 'Ausblick (outlook_reports) fehlt im POST');
		assert.deepEqual(k.puts, [], 'die Karte hat im Anlegen einen PUT abgesetzt');
	});
});

describe('#3306 V3 (AC-3): Schalter der Karte -> POST', () => {
	test('Stundenverlauf aus und Telegram-Kurzstil: hourly_enabled=false, display_config.telegram_style=kurzform; keine Altschlüssel', async () => {
		const ed = await editor();
		const k = await karte(await reiter(ed, 0));
		k.schalter('hourly_enabled', false);
		k.schalter('telegram_style', 'kurzform');
		const p = await ed.speichern();
		assert.equal(p.hourly_enabled, false, 'Stundenverlauf der Karte fehlt im POST');
		assert.equal(p.display_config?.telegram_style, 'kurzform', 'Telegram-Kurzstil der Karte fehlt im POST');
		for (const a of ['channel_layouts', 'outlook_metrics', 'outlook_metric_formats', 'channel_active_metrics', 'hourly_metrics', 'hourly_metric_formats']) {
			assert.equal(a in p, false, a);
			assert.equal(a in (p.display_config ?? {}), false, `display_config.${a}`);
		}
		assert.deepEqual(k.puts, []);
	});
});

describe('#3306 V4 (AC-1): Neuaufbau (Desktop <-> Mobil, Schritt vor und zurück) behält den Kartenstand', () => {
	for (const [von, nach, name] of [[0, 1, 'Desktop -> Mobil'], [1, 0, 'Mobil -> Desktop'], [0, 0, 'Schritt Zustellung und zurück']] as const) {
		test(name, async () => {
			const ed = await editor();
			const k1 = await karte(await reiter(ed, von));
			const m = k1.ids[0];
			k1.u.haken({ metrik: m, stelle: 'telegram', an: false });
			k1.u.reihenfolge([...k1.ids].reverse());
			k1.schalter('hourly_enabled', false);
			const k2 = await karte(await reiter(ed, nach));
			const mit = k2.u.placementsZumMitspeichern();
			assert.equal(zeile(mit, m)?.places?.telegram, false, 'neu aufgebaute Karte hat den Haken verloren');
			assert.deepEqual(mit?.rows.map((r: J) => r.metric_id), [...k1.ids].reverse(), 'neu aufgebaute Karte hat die Reihenfolge verloren');
			// Ein Schalter nach dem Neuaufbau verliert weder Tabelle noch den früheren Schalter.
			k2.schalter('telegram_style', 'kurzform');
			const p = await ed.speichern();
			assert.equal(zeile(p.display_config?.placements, m)?.places?.telegram, false);
			assert.equal(p.hourly_enabled, false, 'Schalter vor dem Neuaufbau verloren');
			assert.equal(p.display_config?.telegram_style, 'kurzform');
		});
	}
});

describe('#3306 V5 (AC-1, AC-7): Vorschau-Entwurf trägt die gewählten Orte und die Schalter des Feldsatzes', () => {
	test('erste Vorschau der Karte: location_ids = gewählte Orte, hourly_enabled und display_config.telegram_style aus dem Feldsatz', async () => {
		const ed = await editor();
		ed.u.wiz.hourlyEnabled = false; // Altblock im Schritt Zustellung (bis #3307)
		ed.u.wiz.telegramStyle = 'kurzform';
		const k = await karte(await reiter(ed, 0));
		const rumpf = k.aufrufe[0].rumpf;
		assert.deepEqual(rumpf.location_ids, ORTE, 'Vorschau ohne die gewählten Orte — keine Beispielwerte');
		assert.equal(rumpf.hourly_enabled, false, 'Vorschau-Entwurf ohne hourly_enabled des Feldsatzes');
		assert.equal(rumpf.display_config?.telegram_style, 'kurzform', 'Vorschau-Entwurf ohne telegram_style des Feldsatzes');
		assert.ok(rumpf.display_config?.ampel, 'Vorschau-Entwurf verliert die Ampel');
	});

	test('Standard-Feldsatz: hourly_enabled=true, telegram_style=rich im Entwurf', async () => {
		const ed = await editor();
		const k = await karte(await reiter(ed, 1));
		const rumpf = k.aufrufe[0].rumpf;
		assert.deepEqual(rumpf.location_ids, ORTE);
		assert.equal(rumpf.hourly_enabled, true);
		assert.equal(rumpf.display_config?.telegram_style, 'rich');
	});
});

describe('#3306 V6 (AC-5): Karte nie bedient — POST wie heute', () => {
	test('Schritt Wetter geöffnet, Karte geladen, nichts geändert: POST ohne placements, kein PUT', async () => {
		const ed = await editor();
		const k = await karte(await reiter(ed, 0));
		const p = await ed.speichern();
		assert.equal('placements' in (p.display_config ?? {}), false);
		assert.equal(p.hourly_enabled, true, 'hourly_enabled nur aus dem Feldsatz');
		assert.equal('telegram_style' in (p.display_config ?? {}), false);
		assert.deepEqual(k.puts, []);
	});
});
