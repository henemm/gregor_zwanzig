// TDD RED — Issue #3305 (Teil B von #3041, Epic #3122): Karte „Was steht wo“ im Anlege-Modus.
// Spec docs/specs/modules/feat_3305_tabelle_trip_anlegen.md, Test Plan Nr. 1 (AC-2, AC-4), Nr. 2 (AC-5), Nr. 6 (AC-10).
//
// FESTGELEGTE SCHNITTSTELLE (der Implementierer folgt diesen Namen):
//   WasStehtWoKarte Props (neu): `createMode: boolean`, `entwurf: () => Trip` (Anlege-Entwurf für die Vorschau),
//     `start?: KarteAnlegeStand` (Stand nach Neuaufbau der Ansicht), `onAnlegeStand: (s: KarteAnlegeStand) => void`.
//   KarteAnlegeStand (exportiert aus shared/wetter-tab/wasStehtWoSpeicherung.ts):
//     { placements: Placements; felder: Felder; felderStart: Felder }
//       placements  = vollständiger lokaler Tabellenstand (Haken, Formate, Reihenfolge, outlook_reports)
//       felder      = aktuelle Schalter unter der Tabelle
//       felderStart = Schalter beim Start der Karte (aus der ersten Vorschau-Antwort bzw. `start`); der Anlege-POST
//                     wendet nur `felderNutzlast('route', felder, felderStart)` an.
//   Im Anlege-Modus: Laden per POST /api/briefings/placements/vorschau?kind=route (kein GET, kein PUT);
//     jede Bedienung (Haken, Format, Reihenfolge, Schalter) meldet `onAnlegeStand` — auch bei `stored=false`;
//     `grundauswahlGeaendert` wirkt auch bei `stored=false` und meldet den neuen Stand;
//     `placementsZumMitspeichern()` liefert den lokalen Stand ohne `stored`-Bedingung;
//     eine Vorschau-Antwort ersetzt nur die Ansicht, nie den lokalen Stand (Haken, Formate, Reihenfolge bleiben).
//
// Messweise: Prüfstand (shared/__tests__/svelteInstanzPruefstand.ts) wertet das ECHTE Instanz-Skript der Karte mit
// gesäten Props aus. `api` ist ein Client im Speicher (Antworten einzeln freigebbar, kein Netz), `fetch` für das
// Profil ebenso; die Uhr über node:test mock.timers. Gemessen wird die Verhaltensfolge: Aufrufe (Methode, Pfad,
// Rumpf) und gemeldeter Stand.
// Hinweis Prüfstand: `$derived` wird einmal beim Aufbau ausgewertet; deshalb ist die Vorschau-Antwort als
// Startwert von `antwort` gesät (wie nach dem ersten Laden) und je Test höchstens ein Schalter bedient.
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/was_steht_wo_karte_anlegen_3305.test.ts

import { test, describe, beforeEach, afterEach, mock } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { umgebungFuer, werte, ohneTypen, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
const KARTE = path.resolve(HERE, '..', 'wetter-tab', 'WasStehtWoKarte.svelte');
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any
type Aufruf = { methode: 'GET' | 'PUT' | 'POST'; pfad: string; rumpf?: J; erledigen: (w?: unknown) => void };
const VORSCHAU = '/api/briefings/placements/vorschau?kind=route';

function client() {
	const aufrufe: Aufruf[] = [];
	const neu = (methode: Aufruf['methode'], pfad: string, rumpf?: unknown) =>
		new Promise<J>((erledigen) => aufrufe.push({ methode, pfad, rumpf: rumpf === undefined ? undefined : JSON.parse(JSON.stringify(rumpf)), erledigen }));
	return {
		aufrufe,
		get: (pfad: string) => neu('GET', pfad),
		put: (pfad: string, rumpf: unknown) => neu('PUT', pfad, rumpf),
		post: (pfad: string, rumpf: unknown) => neu('POST', pfad, rumpf),
		patch: (pfad: string, rumpf: unknown) => neu('PUT', pfad, rumpf),
		del: (pfad: string) => neu('PUT', pfad)
	};
}
const ruhe = () => new Promise((r) => setImmediate(r));

const z = (state: string, extra: J = {}) => ({ state, format: null, reason: null, example: null, ampel: null, mark: null, ...extra });
/** Vorschau-Antwort (Form wie GET /api/briefings/{id}/placements, `stored: false`, #3304). */
function vorschau(ids: string[] = ['temperature_night', 'gust', 'wind'], placementsRows?: J[]): J {
	const zeile = (metric_id: string, position: number) => ({
		metric_id, name: metric_id, position, parent: null,
		cells: { email: z('on', { format: 'simplified' }), telegram: z('on', { format: 'raw' }), sms: z('on'), outlook: z('on', { format: 'raw' }) }
	});
	return {
		kind: 'route', lang: 'de', stored: false,
		placements: { version: 1, rows: placementsRows ?? ids.map((metric_id) => ({ metric_id })) },
		location_count: null,
		columns: ['email', 'telegram', 'sms', 'outlook'].map((stelle) => ({ stelle, subtitle: 'x', block_off: false, rests: null })),
		fixed_rows: [],
		rows: ids.map(zeile),
		sms_example: { text: 'E: W30', length: 6, max_length: 160 },
		outlook_reports: ['evening'],
		blocks: { show_stage_stats: true, show_yesterday_comparison: true, show_night_block: true, email_format: 'full', telegram_style: 'rich', outlook: { morning: false, evening: true } },
		legend: { metrics: [], fixed: [] },
		example_version: 1
	};
}

let entwurf: J;
let profilAbrufe: string[];
const echtFetch = globalThis.fetch;
beforeEach(() => {
	mock.timers.enable({ apis: ['setTimeout'] });
	entwurf = {
		name: 'Neu-3305',
		stages: [{ id: 's1', name: 'A', date: '2026-12-01', waypoints: [] }],
		display_config: { channels: { email: true }, metrics: ['temperature_night', 'gust', 'wind'].map((metric_id) => ({ metric_id, enabled: true })) },
		report_config: { email_format: 'full' }
	};
	profilAbrufe = [];
	globalThis.fetch = (async (url: string, init?: RequestInit) => {
		profilAbrufe.push(`${init?.method ?? 'GET'} ${url}`);
		return { ok: true, json: async () => ({ telegram_chat_id: '1' }) } as Response;
	}) as typeof fetch;
});
afterEach(() => {
	mock.timers.reset();
	globalThis.fetch = echtFetch;
});

/** Karte im Anlege-Modus, gemountet und mit der ersten Vorschau-Antwort geladen. */
async function geladen() {
	const c = client();
	const staende: J[] = [];
	const mounts: Array<() => unknown> = [];
	const { u, ast, quelle } = await umgebungFuer(KARTE, {
		context: 'route',
		id: '',
		saveController: undefined,
		enqueueHubWrite: undefined,
		onUebernahme: undefined,
		createMode: true,
		entwurf: () => entwurf,
		start: undefined,
		onAnlegeStand: (s: J) => staende.push(JSON.parse(JSON.stringify(s))),
		api: c,
		untrack: (fn: () => unknown) => fn(),
		onMount: (fn: () => unknown) => void mounts.push(fn),
		antwort: vorschau(),
		lokal: null
	});
	// Top-Level-Aufrufe `onMount(...)` des Instanz-Skripts gegen die Umgebung auswerten (der Prüfstand führt
	// nur Deklarationen aus); die Rückrufe sammelt die gesäte `onMount`, ausgeführt werden sie hier.
	for (const stmt of (ast.instance?.content?.body as Knoten[]) ?? []) {
		const e = stmt.type === 'ExpressionStatement' ? (stmt.expression as Knoten) : null;
		if (e?.type === 'CallExpression' && e.callee?.type === 'Identifier' && e.callee.name === 'onMount') werte(ohneTypen(quelle, e), u);
	}
	assert.ok(mounts.length >= 1, 'Messaufbau: Karte registriert kein onMount');
	for (const m of mounts) m();
	await ruhe();
	const ersteLadung = c.aufrufe.filter((x) => x.pfad.startsWith('/api/briefings'));
	assert.deepEqual(
		ersteLadung.map((x) => `${x.methode} ${x.pfad}`),
		[`POST ${VORSCHAU}`],
		'Anlegen: die Karte lädt genau einmal über die Vorschau (kein GET ohne Kennung)'
	);
	assert.equal(ersteLadung[0].rumpf?.name, 'Neu-3305', 'Vorschau-Rumpf ist der Entwurf');
	assert.deepEqual(ersteLadung[0].rumpf?.display_config?.metrics, entwurf.display_config.metrics);
	ersteLadung[0].erledigen(vorschau());
	await ruhe();
	return { u, c, staende, letzter: () => staende.at(-1) };
}
const zeile = (stand: J, metrik: string) => stand?.placements?.rows?.find((r: J) => r.metric_id === metrik);
const ids = (pl: J) => pl?.rows?.map((r: J) => r.metric_id);
const schreibend = (c: ReturnType<typeof client>) => c.aufrufe.filter((x) => x.methode !== 'POST' || x.pfad !== VORSCHAU);

describe('#3305 Test 1 (AC-2, AC-4): Anlege-Modus meldet den Stand auch bei stored=false, kein PUT', () => {
	test('Haken: onAnlegeStand meldet die Änderung in placements; kein Schreibaufruf', async () => {
		const k = await geladen();
		k.u.haken({ metrik: 'gust', stelle: 'telegram', an: false });
		assert.ok(k.letzter(), 'kein Stand gemeldet — der Haken ginge beim Anlegen verloren');
		assert.equal(zeile(k.letzter(), 'gust')?.places?.telegram, false);
		assert.deepEqual(schreibend(k.c).map((x) => `${x.methode} ${x.pfad}`), [], 'Anlegen: kein PUT/GET');
	});

	test('Format und Reihenfolge: gemeldeter Stand trägt beides', async () => {
		const k = await geladen();
		k.u.format({ metrik: 'gust', stelle: 'email', format: 'raw' });
		k.u.reihenfolge(['wind', 'gust', 'temperature_night']);
		assert.equal(zeile(k.letzter(), 'gust')?.formats?.email, 'raw');
		assert.deepEqual(ids(k.letzter()?.placements), ['wind', 'gust', 'temperature_night']);
		assert.deepEqual(schreibend(k.c), []);
	});

	test('Schalter (Nacht-Block): gemeldet mit felder und felderStart, kein Teilfeld-PUT', async () => {
		const k = await geladen();
		k.u.feld('show_night_block', false);
		assert.equal(k.letzter()?.felder?.show_night_block, false);
		assert.equal(k.letzter()?.felderStart?.show_night_block, true, 'Start der Karte aus der Vorschau-Antwort');
		assert.equal(k.letzter()?.felderStart?.email_format, 'full');
		mock.timers.tick(5000);
		await ruhe();
		assert.deepEqual(schreibend(k.c), [], 'kein PUT /api/trips/{id} beim Anlegen');
		assert.deepEqual(profilAbrufe.filter((x) => !x.startsWith('GET ')), [], 'kein Schreibaufruf über fetch');
	});

	test('placementsZumMitspeichern: lokaler Stand ohne stored-Bedingung', async () => {
		const k = await geladen();
		k.u.haken({ metrik: 'wind', stelle: 'sms', an: false });
		const mit = k.u.placementsZumMitspeichern();
		assert.ok(mit, 'stored=false darf den Stand beim Anlegen nicht unterdrücken');
		assert.equal(mit.rows.find((r: J) => r.metric_id === 'wind')?.places?.sms, false);
	});
});

describe('#3305 Test 6 (AC-10): Kartenbedienung ohne Metrikänderung lädt keine Vorschau nach', () => {
	test('Haken, Format, Reihenfolge, Ausblick; Zeitgeber läuft ab: weiterhin genau ein Vorschau-Aufruf', async () => {
		const k = await geladen();
		k.u.haken({ metrik: 'gust', stelle: 'telegram', an: false });
		k.u.format({ metrik: 'gust', stelle: 'email', format: 'raw' });
		k.u.reihenfolge(['wind', 'gust', 'temperature_night']);
		k.u.ausblick('morning', true);
		mock.timers.tick(10_000);
		await ruhe();
		assert.equal(k.c.aufrufe.length, 1, `nur die erste Vorschau erwartet, gefunden: ${k.c.aufrufe.map((x) => `${x.methode} ${x.pfad}`).join(', ')}`);
	});
});

describe('#3305 Test 2 (AC-5): Metrik hinzu/weg — Zeilen ergänzt/entfernt, Einstellungen bleiben', () => {
	test('Haken/Format/Reihenfolge bleiben nach grundauswahlGeaendert und nach der folgenden Vorschau-Antwort', async () => {
		const k = await geladen();
		k.u.haken({ metrik: 'gust', stelle: 'telegram', an: false });
		k.u.format({ metrik: 'gust', stelle: 'email', format: 'raw' });
		k.u.reihenfolge(['wind', 'gust', 'temperature_night']);
		// Metrikwechsel im Schritt Wetter: temperature_night weg, rain neu.
		entwurf = { ...entwurf, display_config: { ...entwurf.display_config, metrics: ['gust', 'wind', 'rain'].map((metric_id) => ({ metric_id, enabled: true })) } };
		k.u.grundauswahlGeaendert(['temperature_night', 'gust', 'wind'], ['gust', 'wind', 'rain']);
		const nach = k.letzter();
		assert.deepEqual(ids(nach?.placements), ['wind', 'gust', 'rain'], 'entfernte Zeile entfällt, neue steht hinten');
		assert.equal(zeile(nach, 'gust')?.places?.telegram, false, 'Haken nach Metrikwechsel verloren');
		assert.equal(zeile(nach, 'gust')?.formats?.email, 'raw', 'Format nach Metrikwechsel verloren');

		// Nachladen der Vorschau (entprellt über die Karte, sonst über den Reiter/Erneut-Laden).
		mock.timers.tick(2000);
		await ruhe();
		if (k.c.aufrufe.length === 1) {
			void k.u.laden();
			await ruhe();
		}
		const neu = k.c.aufrufe.at(-1)!;
		assert.equal(`${neu.methode} ${neu.pfad}`, `POST ${VORSCHAU}`);
		assert.deepEqual(ids(neu.rumpf?.display_config?.placements), ['wind', 'gust', 'rain'], 'Vorschau trägt den lokalen Stand');
		// Server-Ansicht ohne die Nutzer-Einstellungen: ersetzt nur die Ansicht, nie den lokalen Stand.
		neu.erledigen(vorschau(['gust', 'wind', 'rain']));
		await ruhe();
		const mit = k.u.placementsZumMitspeichern();
		assert.deepEqual(ids(mit), ['wind', 'gust', 'rain'], 'Vorschau-Antwort hat die Reihenfolge überschrieben');
		assert.equal(mit?.rows.find((r: J) => r.metric_id === 'gust')?.places?.telegram, false, 'Vorschau-Antwort hat den Haken überschrieben');
		assert.equal(mit?.rows.find((r: J) => r.metric_id === 'gust')?.formats?.email, 'raw', 'Vorschau-Antwort hat das Format überschrieben');
	});
});
