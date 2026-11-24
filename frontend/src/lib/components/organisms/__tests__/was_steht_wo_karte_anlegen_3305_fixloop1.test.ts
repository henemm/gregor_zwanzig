// Fix-Loop 1 — Issue #3305 (Spec docs/specs/modules/feat_3305_tabelle_trip_anlegen.md, AC-5, AC-6, AC-7).
// Adversary-Protokoll docs/artifacts/feat-3305-tabelle-trip-anlegen/adversary-dialog.md:
//   F007/F001: Metrikwechsel, BEVOR die erste Vorschau-Antwort da ist (antwort == null, auch nach Neuaufbau mit
//              `start`), ging für den lokalen Stand verloren; eine ältere Antwort füllte `lokal` mit den alten
//              Metriken, und keine spätere Antwort ersetzte ihn. Der Anlege-POST trug dann die alte Zeilenliste.
//   M8/M13:    eine NIE bediente Karte darf auch nach einem Metrikwechsel nichts melden (AC-7: POST ohne rows).
//
// Messweise wie was_steht_wo_karte_anlegen_3305.test.ts: Prüfstand wertet das ECHTE Instanz-Skript der Karte
// aus, Vorschau-Client im Speicher mit einzeln freigebbaren Antworten, Uhr über node:test mock.timers.
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/was_steht_wo_karte_anlegen_3305_fixloop1.test.ts

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
type Aufruf = { methode: string; pfad: string; rumpf?: J; erledigen: (w?: unknown) => void; scheitern: (e: unknown) => void };

function client() {
	const aufrufe: Aufruf[] = [];
	const neu = (methode: string, pfad: string, rumpf?: unknown) =>
		new Promise<J>((erledigen, scheitern) => aufrufe.push({ methode, pfad, rumpf: rumpf === undefined ? undefined : JSON.parse(JSON.stringify(rumpf)), erledigen, scheitern }));
	return { aufrufe, get: (p: string) => neu('GET', p), put: (p: string, r: unknown) => neu('PUT', p, r), post: (p: string, r: unknown) => neu('POST', p, r) };
}
const ruhe = () => new Promise((r) => setImmediate(r));
const z = (state: string, extra: J = {}) => ({ state, format: null, reason: null, example: null, ampel: null, mark: null, ...extra });
const FELDER = { show_stage_stats: true, show_yesterday_comparison: true, show_night_block: true, email_format: 'full', telegram_style: 'rich', hourly_enabled: true };
/** Vorschau-Antwort (#3304): Server baut die Zeilen aus den Metriken des Entwurfs. */
function vorschau(ids: string[]): J {
	return {
		kind: 'route', lang: 'de', stored: false,
		placements: { version: 1, rows: ids.map((metric_id) => ({ metric_id })) },
		location_count: null,
		columns: ['email', 'telegram', 'sms', 'outlook'].map((stelle) => ({ stelle, subtitle: 'x', block_off: false, rests: null })),
		fixed_rows: [],
		rows: ids.map((metric_id, position) => ({ metric_id, name: metric_id, position, parent: null, cells: { email: z('on', { format: 'simplified' }), telegram: z('on', { format: 'raw' }), sms: z('on'), outlook: z('on') } })),
		sms_example: { text: 'E: W30', length: 6, max_length: 160 },
		outlook_reports: ['evening'],
		blocks: { show_stage_stats: true, show_yesterday_comparison: true, show_night_block: true, email_format: 'full', telegram_style: 'rich' },
		legend: { metrics: [], fixed: [] },
		example_version: 1
	};
}
const ALT = ['temperature_night', 'gust', 'wind'];
const NEU = ['gust', 'wind', 'rain'];
const metriken = (ids: string[]) => ids.map((metric_id) => ({ metric_id, enabled: true }));
const ids = (pl: J) => pl?.rows?.map((r: J) => r.metric_id);

let entwurf: J;
beforeEach(() => {
	mock.timers.enable({ apis: ['setTimeout'] });
	entwurf = { name: 'Neu-3305', stages: [], display_config: { channels: { email: true }, metrics: metriken(ALT) } };
	globalThis.fetch = (async () => ({ ok: true, json: async () => ({}) }) as Response) as typeof fetch;
});
afterEach(() => mock.timers.reset());

/** Karte im Anlege-Modus montiert, die erste Vorschau ist unterwegs (NICHT beantwortet). */
async function montiert(saat: J = {}) {
	const c = client();
	const staende: J[] = [];
	const mounts: Array<() => unknown> = [];
	const { u, ast, quelle } = await umgebungFuer(KARTE, {
		context: 'route', id: '', saveController: undefined, enqueueHubWrite: undefined, onUebernahme: undefined,
		createMode: true,
		entwurf: () => entwurf,
		start: undefined,
		onAnlegeStand: (s: J) => staende.push(JSON.parse(JSON.stringify(s))),
		api: c,
		untrack: (fn: () => unknown) => fn(),
		onMount: (fn: () => unknown) => void mounts.push(fn),
		...saat
	});
	for (const stmt of (ast.instance?.content?.body as Knoten[]) ?? []) {
		const e = stmt.type === 'ExpressionStatement' ? (stmt.expression as Knoten) : null;
		if (e?.type === 'CallExpression' && e.callee?.name === 'onMount') werte(ohneTypen(quelle, e), u);
	}
	for (const m of mounts) m();
	await ruhe();
	assert.equal(c.aufrufe.length, 1, 'Messaufbau: erste Vorschau läuft');
	return { u, c, staende };
}
/** Metrikwechsel im Schritt Wetter, wie WetterTabInhalt.aendern ihn an die Karte gibt. */
async function metrikWechsel(k: Awaited<ReturnType<typeof montiert>>) {
	entwurf = { ...entwurf, display_config: { ...entwurf.display_config, metrics: metriken(NEU) } };
	k.u.grundauswahlGeaendert(ALT, NEU);
	k.u.vorschauNachMetrik();
	mock.timers.tick(2000);
	await ruhe();
}

describe('#3305 F007: Metrikwechsel vor der ersten Vorschau-Antwort verfälscht den Stand nicht', () => {
	test('ohne Startstand: ältere Antwort (alte Metriken) wird verworfen, der Stand trägt die neue Auswahl', async () => {
		const k = await montiert();
		await metrikWechsel(k);
		assert.equal(k.c.aufrufe.length, 2, 'Messaufbau: Nachladen nach dem Metrikwechsel');
		assert.deepEqual(k.c.aufrufe[1].rumpf?.display_config?.metrics, metriken(NEU));
		k.c.aufrufe[0].erledigen(vorschau(ALT)); // ältere Antwort kommt zuerst
		await ruhe();
		k.c.aufrufe[1].erledigen(vorschau(NEU));
		await ruhe();
		assert.deepEqual(ids(k.u.placementsZumMitspeichern()), NEU, 'POST trüge die Zeilen der alten Metriken');
	});

	test('ältere Antwort NACH der neueren: bleibt verworfen', async () => {
		const k = await montiert();
		await metrikWechsel(k);
		k.c.aufrufe[1].erledigen(vorschau(NEU));
		await ruhe();
		k.c.aufrufe[0].erledigen(vorschau(ALT));
		await ruhe();
		assert.deepEqual(ids(k.u.placementsZumMitspeichern()), NEU);
	});

	test('nach Neuaufbau mit Startstand: Haken bleibt, entfernte Zeile entfällt, neue kommt hinzu, Stand wird gemeldet', async () => {
		const start = {
			placements: { version: 1, rows: [{ metric_id: 'wind' }, { metric_id: 'gust', places: { telegram: false } }, { metric_id: 'temperature_night' }] },
			felder: { ...FELDER }, felderStart: { ...FELDER }
		};
		const k = await montiert({ start });
		await metrikWechsel(k);
		const gemeldet = k.staende.at(-1);
		assert.deepEqual(ids(gemeldet?.placements), ['wind', 'gust', 'rain'], 'Metrikwechsel vor der ersten Antwort nicht im gemeldeten Stand');
		k.c.aufrufe[0].erledigen(vorschau(ALT));
		await ruhe();
		k.c.aufrufe[1].erledigen(vorschau(NEU));
		await ruhe();
		const mit = k.u.placementsZumMitspeichern();
		assert.deepEqual(ids(mit), ['wind', 'gust', 'rain']);
		assert.equal(mit.rows.find((r: J) => r.metric_id === 'gust')?.places?.telegram, false, 'Haken aus dem Startstand verloren');
	});
});

describe('#3305 M8/M13 (AC-7): eine nie bediente Karte meldet auch nach einem Metrikwechsel nichts', () => {
	test('geladen, nicht bedient, Metrik weg/hinzu: kein gemeldeter Stand (POST bleibt ohne rows)', async () => {
		const k = await montiert({ antwort: vorschau(ALT) });
		k.c.aufrufe[0].erledigen(vorschau(ALT));
		await ruhe();
		await metrikWechsel(k);
		assert.deepEqual(k.staende, [], 'unbediente Karte hat einen Stand gemeldet');
		// Gegenprobe: nach einer Bedienung meldet sie.
		k.u.haken({ metrik: 'gust', stelle: 'telegram', an: false });
		assert.equal(k.staende.length, 1);
	});
});

describe('#3305 Fix-Loop 1: gescheitertes Nachladen der Vorschau lässt die Karte nicht endlos laden', () => {
	test('noch keine Antwort (erste verworfen), entprelltes Nachladen scheitert: sichtbarer Fehlerzustand', async () => {
		const k = await montiert();
		await metrikWechsel(k);
		k.c.aufrufe[0].erledigen(vorschau(ALT)); // verworfen (alte Metriken)
		await ruhe();
		k.c.aufrufe[1].scheitern(Object.assign(new Error('netz'), { status: 502 }));
		await ruhe();
		assert.equal(k.u.phase, 'fehler', 'Karte bliebe endlos im Ladezustand');
	});

	test('Antwort schon da, Nachladen scheitert: alte Ansicht bleibt stehen', async () => {
		const k = await montiert();
		k.c.aufrufe[0].erledigen(vorschau(ALT));
		await ruhe();
		assert.equal(k.u.phase, 'bereit', 'Messaufbau');
		await metrikWechsel(k);
		k.c.aufrufe[1].scheitern(new Error('netz'));
		await ruhe();
		assert.equal(k.u.phase, 'bereit');
		assert.ok(k.u.antwort, 'Ansicht verloren');
	});
});

describe('#3305 Fix-Loop 2 (F-A3b): Start der Schalter bleibt der Start der Karte', () => {
	test('spätere Vorschau mit anderen Schalterwerten (Zustellung: Kompakt) verschiebt felderStart nicht', async () => {
		const k = await montiert({ antwort: vorschau(ALT) });
		k.c.aufrufe[0].erledigen(vorschau(ALT));
		await ruhe();
		k.u.feld('show_night_block', false);
		await metrikWechsel(k);
		k.c.aufrufe[1].erledigen({ ...vorschau(NEU), blocks: { ...vorschau(NEU).blocks, email_format: 'compact' } });
		await ruhe();
		k.u.haken({ metrik: 'gust', stelle: 'telegram', an: false });
		const s = k.staende.at(-1);
		assert.equal(s?.felderStart?.email_format, 'full', 'felderStart folgt der späteren Vorschau');
		// Folge im POST: die Karte hat das Mail-Format nicht bedient, also darf sie es nicht überschreiben.
		assert.equal(s?.felder?.email_format, s?.felderStart?.email_format, 'POST überschriebe das Mail-Format der Zustellung');
	});
});

describe('#3305 Fix-Loop 3 (F-B1, AC-5): Metrik entfernt, keine neue Vorschau — Ansicht und Klick bringen die Zeile nicht zurück', () => {
	test('Ansicht ohne die Zeile; ein Haken danach meldet einen Stand ohne die entfernte Metrik', async () => {
		const k = await montiert({ antwort: vorschau(ALT) });
		k.c.aufrufe[0].erledigen(vorschau(ALT));
		await ruhe();
		k.u.haken({ metrik: 'gust', stelle: 'telegram', an: false }); // bedient
		entwurf = { ...entwurf, display_config: { ...entwurf.display_config, metrics: metriken(NEU) } };
		k.u.grundauswahlGeaendert(ALT, NEU); // kein Nachladen (bzw. es scheitert): keine neue Antwort
		assert.equal(k.u.anzeige().includes('temperature_night'), false, 'Ansicht zeigt die Zeile der entfernten Metrik');
		k.u.haken({ metrik: 'wind', stelle: 'sms', an: false });
		const pl = k.staende.at(-1)?.placements;
		assert.equal(ids(pl).includes('temperature_night'), false, 'Klick hat die entfernte Metrik in den Stand zurückgebracht');
		assert.equal(pl.rows.find((r: J) => r.metric_id === 'gust')?.places?.telegram, false);
		assert.equal(pl.rows.find((r: J) => r.metric_id === 'wind')?.places?.sms, false);
	});
});
