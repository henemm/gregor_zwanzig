// Fix-Loop 2 — Issue #3196 (Workflow feat-3196-trip-tempo-etappen), Adversary F002/F003/F006/F007.
// Spec: docs/specs/modules/feat_3196_trip_tempo_etappen.md — AC-1, AC-4, AC-7
//
// Gemessen dort, wo es WIRKT (nicht ob ein Bezeichner im Quelltext steht):
//   F002 (AC-1)  Der ECHTE Trip-Hub (TripTabs) im Reiter Etappen, serverseitig gerendert: ein
//                Bestandstrip mit gespeichertem tempo Rad/20 (bzw. nur activity fahrrad_20) zeigt
//                in der Karte Rad gewaehlt und 20 km/h. Der Reiter Etappen wird ueber den
//                F8-Hook als Startzustand gesetzt (setzt sonst erst `$effect`).
//   F003a (AC-4) Das ECHTE Instanz-Skript von TempoKarteInhalt (svelteInstanzPruefstand): Wahl
//                von Rad, MTB, Ski meldet das Grundtempo des Vorschlagswerts (20/12/3).
//   F007         Zahlenfeld: Werte ausserhalb 0.5..60 werden nicht gemeldet.
//   F003b/c (AC-7) Das ECHTE Instanz-Skript von TripNewEditor: die Karte meldet die Wahl ueber
//                ihren Markup-Rueckruf, der Anlege-POST /api/trips traegt sie als `tempo`
//                (echter buildCreateTripPayload), und der stubTrip traegt sie ebenfalls.
//   F006 (AC-7)  Das ECHTE Effekt-Skript von WeatherMetricsTab: die Fortbewegung des (stub)Trips
//                waehlt die Vorlage vor (fuss→alpen-trekking, rad/mtb→radtour, ski→skitouren),
//                auch in der Kette Editor-stubTrip → Effekt.
//
//   cd frontend && npm test -- src/lib/components/trip-detail/__tests__/tempo_verdrahtung_3196_fixloop2.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const T = await import('./f9Pruefstand.ts');
const { render } = await import('svelte/server');
const P = await import('../../shared/__tests__/svelteInstanzPruefstand.ts');
const { umgebungFuer, effekteVon, findeKomponenten, attributAusdruck, werte, ohneTypen } = P;
type Knoten = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const { STANDARD_TEMPO, wechsleFortbewegung } = await import('../../../utils/naismith.ts');

const TRIP_TABS = path.join(T.TD, 'TripTabs.svelte');
const TEMPO_INHALT = path.join(T.KOMP, 'organisms', 'tempo-karte', 'TempoKarteInhalt.svelte');
const EDITOR = path.join(T.KOMP, 'trip-new', 'TripNewEditor.svelte');
const WMT = path.join(T.KOMP, 'shared', 'WeatherMetricsTab.svelte');

const variante = async (datei: string, ersetzungen: [string, string][]) =>
	(await import(`${pathToFileURL(datei).href}?f8variante=${Buffer.from(JSON.stringify(ersetzungen)).toString('base64url')}`)).default;

function tagMit(h: string, testid: string): string {
	const m = new RegExp(`<[^>]*data-testid="${testid}"[^>]*>`).exec(h);
	assert.ok(m, `[data-testid=${testid}] fehlt`);
	return m[0];
}

// ── F002 (AC-1): Trip → Karte im Reiter Etappen ─────────────────────────────

describe('F002 (AC-1): der Reiter Etappen zeigt das Tempo des geladenen Trips', () => {
	const etappenReiter = () =>
		variante(TRIP_TABS, [["let activeTab = $state<string>('uebersicht');", "let activeTab = $state<string>('etappen');"]]);
	const karte = async (trip: Record<string, unknown>) => {
		const Tabs = await etappenReiter();
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		const h = render(Tabs as any, { props: { initialTab: 'etappen', trip, metricsCatalog: T.KATALOG } }).body.replace(/<!--[\s\S]*?-->/g, '');
		tagMit(h, 'trip-detail-panel-etappen');
		tagMit(h, 'tempo-karte');
		const gedrueckt = ['fuss', 'rad', 'mtb', 'ski'].filter((f) => /aria-pressed="true"/.test(tagMit(h, `tempo-fortbewegung-${f}`)));
		const wert = /value="([^"]*)"/.exec(tagMit(h, 'tempo-grundtempo'))?.[1];
		return { gedrueckt, wert };
	};

	test('gespeichertes tempo Rad/20 ⇒ Rad gewaehlt, 20 km/h', async () => {
		const k = await karte(T.tripLaufend({ activity: 'trekking', tempo: { fortbewegung: 'rad', grundtempo_kmh: 20 } }));
		assert.deepEqual(k.gedrueckt, ['rad']);
		assert.equal(k.wert, '20');
	});

	test('nur activity fahrrad_20 (ohne tempo) ⇒ Rad gewaehlt, 20 km/h', async () => {
		const trip = T.tripLaufend({ activity: 'fahrrad_20' });
		delete (trip as Record<string, unknown>).tempo;
		const k = await karte(trip);
		assert.deepEqual(k.gedrueckt, ['rad']);
		assert.equal(k.wert, '20');
	});
});

// ── F003a (AC-4) und F007: Instanz-Skript der Karte ──────────────────────────

async function karteInstanz(tempo: unknown) {
	const gemeldet: unknown[] = [];
	const { u } = await umgebungFuer(TEMPO_INHALT, { tempo, onchange: (t: unknown) => gemeldet.push(t) });
	assert.equal(typeof u.waehle, 'function', 'Messaufbau: waehle nicht herleitbar');
	assert.equal(typeof u.grundtempo, 'function', 'Messaufbau: grundtempo nicht herleitbar');
	return { u, gemeldet };
}

describe('F003a (AC-4): Wahl der Fortbewegung setzt das Grundtempo auf den Vorschlagswert', () => {
	test('zu Fuss 4 → Rad 20 → MTB 12 → Ski 3 (jeweils mit dem zuvor gemeldeten Stand)', async () => {
		let tempo: Knoten = { fortbewegung: 'fuss', grundtempo_kmh: 4 };
		for (const [f, kmh] of [['rad', 20], ['mtb', 12], ['ski', 3]] as const) {
			const { u, gemeldet } = await karteInstanz(tempo);
			u.waehle(f);
			assert.equal(gemeldet.length, 1, `Wahl ${f} meldet nichts`);
			assert.deepEqual(gemeldet[0], { fortbewegung: f, grundtempo_kmh: kmh }, `Wahl ${f}`);
			tempo = gemeldet[0] as Knoten;
		}
	});

	test('erneute Wahl derselben Fortbewegung meldet nichts (Grundtempo bleibt)', async () => {
		const { u, gemeldet } = await karteInstanz({ fortbewegung: 'rad', grundtempo_kmh: 17 });
		u.waehle('rad');
		assert.equal(gemeldet.length, 0);
	});
});

describe('F007: Zahlenfeld meldet nur Werte in 0.5..60 km/h', () => {
	const eingabe = (value: string) => ({ currentTarget: { value } });
	for (const [roh, gemeldetErwartet] of [
		['61', false], ['60.5', false], ['0.4', false], ['0', false], ['-2', false], ['abc', false],
		['60', true], ['0.5', true], ['5', true]
	] as const) {
		test(`Eingabe ${roh} ⇒ ${gemeldetErwartet ? 'gemeldet' : 'verworfen'}`, async () => {
			const { u, gemeldet } = await karteInstanz({ fortbewegung: 'fuss', grundtempo_kmh: 4 });
			u.grundtempo(eingabe(roh));
			if (!gemeldetErwartet) assert.equal(gemeldet.length, 0, `${roh} wurde gemeldet: ${JSON.stringify(gemeldet)}`);
			else assert.deepEqual(gemeldet, [{ fortbewegung: 'fuss', grundtempo_kmh: Number(roh) }]);
		});
	}
});

// ── F003b/c (AC-7): Anlegen — Karte → POST und stubTrip ──────────────────────

async function editor() {
	const gesendet: Array<{ url: string; payload: Knoten }> = [];
	const { ast, quelle, u } = await umgebungFuer(EDITOR, {
		stateOverride: undefined,
		untrack: (fn: () => unknown) => fn(),
		api: {
			post: async (url: string, payload: Knoten) => {
				gesendet.push({ url, payload });
				return { id: 'neu-1' };
			}
		}
	});
	assert.equal(typeof u.buildAndSave, 'function', 'Messaufbau: buildAndSave nicht herleitbar');
	const karten = findeKomponenten(ast, 'TempoKarte');
	assert.ok(karten.length >= 1, 'Messaufbau: keine TempoKarte im Editor');
	const stub = (ast.instance.content.body as Knoten[])
		.filter((s) => s.type === 'VariableDeclaration')
		.flatMap((s) => s.declarations as Knoten[])
		.find((d) => d.id?.name === 'stubTrip');
	assert.ok(stub, 'Messaufbau: stubTrip fehlt im Editor');
	const stubNeu = () => werte(ohneTypen(quelle, stub.init), u) as Knoten;
	return { ast, quelle, u, gesendet, karten, stubNeu };
}

type Ed = Awaited<ReturnType<typeof editor>>;

/** Markup-Rueckruf `onchange` der TempoKarte Nr. `nr` im Editor (ECHTER Ausdruck, gegen die Editor-Umgebung). */
function editorRueckruf(ed: Ed, nr: number): (t: unknown) => void {
	const ausdruck = attributAusdruck(ed.karten[nr], ed.quelle, 'onchange');
	assert.ok(ausdruck, `Messaufbau: TempoKarte Nr. ${nr} ohne onchange`);
	return werte(ausdruck, ed.u) as (t: unknown) => void;
}

/** Die Karte meldet eine Wahl: ECHTER Rueckruf der Karte → ECHTER Markup-Rueckruf des Editors. */
async function waehleImEditor(ed: Ed, karteNr: number, f: string): Promise<void> {
	const tempoAusdruck = attributAusdruck(ed.karten[karteNr], ed.quelle, 'tempo');
	assert.ok(tempoAusdruck, 'Messaufbau: TempoKarte ohne tempo');
	const { u } = await umgebungFuer(TEMPO_INHALT, { tempo: werte(tempoAusdruck, ed.u), onchange: editorRueckruf(ed, karteNr) });
	u.waehle(f);
}

async function speichern(ed: Ed): Promise<Knoten> {
	ed.u.ready = true;
	const id = await ed.u.buildAndSave();
	assert.equal(id, 'neu-1', `buildAndSave scheiterte: ${ed.u.saveError}`);
	assert.equal(ed.gesendet.length, 1);
	assert.equal(ed.gesendet[0].url, '/api/trips');
	return ed.gesendet[0].payload;
}

describe('F003b/c (AC-7): die gewaehlte Fortbewegung reist im Anlege-POST', () => {
	test('ohne Wahl: POST traegt tempo zu Fuss 4 km/h', async () => {
		const ed = await editor();
		const p = await speichern(ed);
		assert.deepEqual(p.tempo, STANDARD_TEMPO);
	});

	test('jede Karte im Editor (Desktop und Handy): Wahl Rad ⇒ POST traegt tempo Rad 20, stubTrip ebenso', async () => {
		const probe = await editor();
		for (let nr = 0; nr < probe.karten.length; nr++) {
			const ed = await editor();
			await waehleImEditor(ed, nr, 'rad');
			assert.deepEqual(ed.stubNeu().tempo, { fortbewegung: 'rad', grundtempo_kmh: 20 }, `Karte ${nr}: stubTrip ohne gewaehltes tempo`);
			const p = await speichern(ed);
			assert.deepEqual(p.tempo, { fortbewegung: 'rad', grundtempo_kmh: 20 }, `Karte ${nr}: POST ohne gewaehltes tempo`);
		}
	});

	test('Wahl Ski, danach Grundtempo 2.5 ⇒ POST traegt Ski 2.5', async () => {
		const ed = await editor();
		await waehleImEditor(ed, 0, 'ski');
		const { u } = await umgebungFuer(TEMPO_INHALT, { tempo: ed.u.selectedTempo, onchange: editorRueckruf(ed, 0) });
		u.grundtempo({ currentTarget: { value: '2.5' } });
		const p = await speichern(ed);
		assert.deepEqual(p.tempo, { fortbewegung: 'ski', grundtempo_kmh: 2.5 });
	});
});

// ── F006 (AC-7): Fortbewegung → Vorlage (Effekt in WeatherMetricsTab) ────────

async function vorlageFuer(trip: Knoten): Promise<string[]> {
	const gewaehlt: string[] = [];
	const { ast, quelle, u } = await umgebungFuer(WMT, {
		createMode: true,
		trip,
		isDirty: false,
		templates: [{ id: 'alpen-trekking' }, { id: 'radtour' }, { id: 'skitouren' }, { id: 'allgemein' }],
		applyPreset: (id: string) => gewaehlt.push(id)
	});
	const effekte = effekteVon(ast, quelle, u, 'FORTBEWEGUNG_TO_TEMPLATE');
	assert.equal(effekte.length, 1, 'Messaufbau: Vorlagen-Effekt nicht gefunden');
	effekte[0]();
	return gewaehlt;
}

describe('F006 (AC-7): Vorlagen-Vorbelegung richtet sich nach der Fortbewegung', () => {
	for (const [f, vorlage] of [['fuss', 'alpen-trekking'], ['rad', 'radtour'], ['mtb', 'radtour'], ['ski', 'skitouren']] as const) {
		test(`${f} ⇒ ${vorlage}`, async () => {
			const tempo = wechsleFortbewegung(STANDARD_TEMPO, f);
			assert.deepEqual(await vorlageFuer({ tempo }), [vorlage]);
		});
	}

	test('Kette Anlegen: Wahl MTB in der Karte ⇒ stubTrip ⇒ Vorlage radtour', async () => {
		const ed = await editor();
		await waehleImEditor(ed, 0, 'mtb');
		assert.deepEqual(await vorlageFuer(ed.stubNeu()), ['radtour']);
	});
});
