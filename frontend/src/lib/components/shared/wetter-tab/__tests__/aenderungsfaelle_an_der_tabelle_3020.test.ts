// Issue #3020 R1 (G35): die vier Änderungsfälle aus tests/fixtures/einstellung_auslieferung/aenderungsfaelle.json als
// Gesten der Karte „Was steht wo“ an den Goldens A und C — der ganze Weg Antwort, Geste, gespeicherte Tabelle,
// ausgelieferte Liste. Vor #3357 prüfte das die Alt-Fläche gegen eingefrorene channel_layouts-Stände.
//
// Antwort und Listen aus Python (placementsOrakel.ts: GET …/placements und `resolve_channel_lists`), die Geste an den
// ECHTEN Funktionen im Instanz-Skript von WasStehtWoKarte.svelte, gespeichert über den echten Tabellen-Speicherer
// (PUT-Rumpf). Die Reihenfolge gilt seit ADR-0124 für alle Stellen: fall2 und fall4 prüfen eine gemeinsame Folge.
// Zwei Nutzer: Golden A gehört A, Golden C gehört B.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/aenderungsfaelle_an_der_tabelle_3020.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { umgebungFuer, type Knoten } from '../../__tests__/svelteInstanzPruefstand.ts';
import { fixture } from './wetterTabDaten.ts';
import { placementsOrakel, type J, type OrakelFall, type OrakelStand } from './placementsOrakel.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const KARTE = join(HIER, '..', '..', '..', 'organisms', 'wetter-tab', 'WasStehtWoKarte.svelte');
const FAELLE = fixture('einstellung_auslieferung/aenderungsfaelle.json');
const STELLEN = ['email', 'telegram', 'sms', 'outlook'] as const;
type Stelle = (typeof STELLEN)[number];
type Paar = [string, string | null];

const abo = (golden: string): OrakelFall => ({ id: `fall-${golden.replace('_', '-')}`, nutzer: golden === 'golden_a' ? 'aenderung-a' : 'aenderung-b', kind: 'route', abo: fixture(`einstellung_auslieferung/${golden}.json`) });
const [STAND_A, STAND_C] = placementsOrakel([abo('golden_a'), abo('golden_c')]);

/** Die Karte im Hub auf einer Antwort; `gespeichert()` führt den geplanten PUT aus und liefert seinen Rumpf. */
async function karte(antwort: J) {
	const puts: { pfad: string; rumpf: J }[] = [];
	let geplant: (() => Promise<void>) | null = null;
	const { u } = await umgebungFuer(KARTE, {
		context: 'route',
		id: 'abo-1',
		createMode: false,
		start: undefined,
		entwurf: undefined,
		onAnlegeStand: undefined,
		onUebernahme: undefined,
		enqueueHubWrite: undefined,
		saveController: { schedule: (fn: () => Promise<void>) => void (geplant = fn), cancel: () => {} },
		api: {
			get: async () => structuredClone(antwort),
			put: async (pfad: string, rumpf: J) => {
				puts.push({ pfad, rumpf: structuredClone(rumpf) });
				return {};
			}
		},
		untrack: (fn: () => unknown) => fn(),
		onMount: () => {}
	});
	u.uebernehmen(structuredClone(antwort));
	assert.equal(u.phase, 'bereit', 'Messaufbau: die Karte ist geladen');
	return {
		u: u as Knoten,
		sofort: () => structuredClone(u.antwort) as J,
		async gespeichert(): Promise<J> {
			assert.ok(geplant, 'die Geste plant kein Speichern');
			await geplant();
			assert.equal(puts.length, 1, 'genau ein PUT');
			assert.match(puts[0].pfad, /\/api\/briefings\/abo-1\/placements/);
			return puts[0].rumpf;
		}
	};
}

/** Was die Karte an einer Stelle zeigt: Haken an (oder „keine eigene Spalte“, gehört zur Ausgabe), mit Form. */
const anzeige = (antwort: J, s: Stelle): Paar[] =>
	antwort.rows.filter((r: J) => r.cells[s].state === 'on' || r.cells[s].reason === 'keine_eigene_spalte').map((r: J) => [r.metric_id, r.cells[s].format]);
const zustaende = (antwort: J) => antwort.rows.map((r: J) => [r.metric_id, Object.fromEntries(STELLEN.map((s) => [s, [r.cells[s].state, r.cells[s].format]]))]);
const zeilen = (antwort: J): string[] => antwort.rows.map((r: J) => r.metric_id);
const ids = (liste: Paar[]) => liste.map(([m]) => m);
const istTeilfolge = (teil: Paar[], ganz: Paar[]) => {
	let i = 0;
	for (const p of ganz) if (i < teil.length && JSON.stringify(teil[i]) === JSON.stringify(p)) i++;
	return i === teil.length;
};

/** Anzeige = ausgelieferte Liste an jeder Stelle: jede Briefing-Liste ist eine Teilfolge der Anzeige (Größen nur
 *  eines Briefings), zusammen sind sie genau die Anzeige. */
function anzeigeGleichAusgabe(s: OrakelStand): void {
	for (const stelle of STELLEN) {
		const listen = (['morning', 'evening'] as const).map((rt) => s.listen[rt][stelle]);
		// Der Ausblick entfällt ganz in einem Briefing ohne Ausblick (outlook_reports). Eine Größe nur im anderen
		// Briefing (Bericht-Flags, cloud_low in Golden C) zeigt die Karte dort trotzdem angehakt: #3364, hier ausgenommen.
		const mitAusblick = new Set((s.antwort.outlook_reports as string[]).flatMap((rt) => STELLEN.flatMap((x) => ids(s.listen[rt][x]))));
		const soll = anzeige(s.antwort, stelle).filter(([m]) => stelle !== 'outlook' || mitAusblick.has(m));
		for (const l of listen) assert.ok(istTeilfolge(l, soll), `${stelle}: ausgelieferte Liste ${ids(l)} steht nicht so in der Karte ${ids(soll)}`);
		assert.deepEqual([...new Set(listen.flatMap(ids))].sort(), ids(soll).sort(), `${stelle}: Karte zeigt eine andere Menge als die Ausgabe`);
	}
}

/** Speichert die Tabelle am Abo, lädt neu, prüft Sofortanzeige und Anzeige = Ausgabe. */
async function nachSpeichern(vorher: OrakelStand, golden: string, k: Awaited<ReturnType<typeof karte>>): Promise<OrakelStand> {
	const sofort = k.sofort();
	const placements = await k.gespeichert();
	const f = abo(golden);
	const [nachher] = placementsOrakel([{ ...f, abo: { ...f.abo, display_config: { ...f.abo.display_config, placements } } }]);
	if (vorher === STAND_A || vorher === STAND_C) assert.equal(vorher.antwort.stored, false, 'Messaufbau: Golden ohne Tabelle');
	assert.equal(nachher.antwort.stored, true, 'die Tabelle gilt als gespeichert');
	assert.deepEqual(zustaende(nachher.antwort), zustaende(sofort), 'Anzeige nach dem Neuladen = Anzeige nach der Geste');
	anzeigeGleichAusgabe(nachher);
	return nachher;
}
const mitFolge = (liste: Paar[], folge: string[]): Paar[] => [...liste].sort((a, b) => folge.indexOf(a[0]) - folge.indexOf(b[0]));
const vertauscht = (folge: string[], a: string, b: string) => folge.map((m) => (m === a ? b : m === b ? a : m));

describe('#3020 G35: Änderungsfälle als Gesten der Karte', () => {
	test('fall1_metrik_abwaehlen: nur diese Stelle verliert die Metrik, Anzeige und ausgelieferte Liste gleich', async () => {
		const { metric_id, channel } = FAELLE.fall1_metrik_abwaehlen;
		assert.equal(channel, 'email');
		anzeigeGleichAusgabe(STAND_A);
		const k = await karte(STAND_A.antwort);
		k.u.haken({ metrik: metric_id, stelle: channel, an: false });
		const n = await nachSpeichern(STAND_A, 'golden_a', k);
		for (const rt of ['morning', 'evening']) {
			assert.deepEqual(n.listen[rt].email, STAND_A.listen[rt].email.filter(([m]) => m !== metric_id), rt);
			assert.notDeepEqual(n.listen[rt].email, STAND_A.listen[rt].email, 'Messaufbau: die Metrik stand in der E-Mail');
			for (const s of ['telegram', 'sms'] as const) assert.deepEqual(n.listen[rt][s], STAND_A.listen[rt][s], `${rt}/${s} unverändert`);
			// Der Ausblick setzt die E-Mail voraus (ADR-0124 Nr. 4): dort entfällt höchstens dieselbe Metrik.
			assert.deepEqual(n.listen[rt].outlook, STAND_A.listen[rt].outlook.filter(([m]) => m !== metric_id), `${rt}/outlook`);
		}
	});

	test('fall2_reihenfolge_tauschen: alle Stellen in der neuen Folge, Anzeige und ausgelieferte Liste gleich', async () => {
		const { metric_a, metric_b } = FAELLE.fall2_reihenfolge_tauschen;
		const folge = vertauscht(zeilen(STAND_A.antwort), metric_a, metric_b);
		const k = await karte(STAND_A.antwort);
		k.u.reihenfolge(folge);
		const n = await nachSpeichern(STAND_A, 'golden_a', k);
		assert.deepEqual(zeilen(n.antwort), folge);
		for (const rt of ['morning', 'evening'])
			for (const s of STELLEN) assert.deepEqual(n.listen[rt][s], mitFolge(STAND_A.listen[rt][s], folge), `${rt}/${s}: gleiche Auswahl und Form, neue Folge`);
		assert.notDeepEqual(ids(n.listen.evening.email), ids(STAND_A.listen.evening.email), 'Messaufbau: der Tausch ist in der E-Mail sichtbar');
	});

	test('fall3_roh_einfach_umschalten: nur diese Stelle wechselt die Form, Anzeige und ausgelieferte Liste gleich', async () => {
		const { metric_id, channel, from_friendly, to_friendly } = FAELLE.fall3_roh_einfach_umschalten;
		const form = (f: boolean) => (f ? 'simplified' : 'raw');
		const zelle = (s: OrakelStand) => s.antwort.rows.find((r: J) => r.metric_id === metric_id).cells[channel].format;
		// Das „Roh“ der Alt-Fläche stand im wirkungslosen channel_layouts (#3237): die Geste geht erst nach Roh (Ausgang
		// des Falls), dann auf der gespeicherten Tabelle nach Einfach.
		assert.equal(zelle(STAND_A), form(to_friendly), 'Messaufbau: ohne Tabelle gilt die Katalog-Form');
		let vorher = STAND_A;
		for (const ziel of [form(from_friendly), form(to_friendly)]) {
			const k = await karte(vorher.antwort);
			k.u.format({ metrik: metric_id, stelle: channel, format: ziel });
			const n = await nachSpeichern(vorher, 'golden_a', k);
			assert.equal(zelle(n), ziel);
			for (const rt of ['morning', 'evening'])
				for (const s of STELLEN)
					assert.deepEqual(
						n.listen[rt][s],
						vorher.listen[rt][s].map(([m, f]) => (s === channel && m === metric_id ? [m, ziel] : [m, f])),
						`${ziel} ${rt}/${s}`
					);
			assert.notDeepEqual(n.listen.evening.email, vorher.listen.evening.email, 'Messaufbau: die Form ist in der E-Mail-Liste sichtbar');
			vorher = n;
		}
	});

	test('fall4_sms_erstbearbeitung: E-Mail und Telegram bleiben, Anzeige und ausgelieferte Liste gleich', async () => {
		const { deselect_metric_id, metric_a, metric_b, channel } = FAELLE.fall4_sms_erstbearbeitung;
		assert.equal(channel, 'sms');
		anzeigeGleichAusgabe(STAND_C);
		const folge = vertauscht(zeilen(STAND_C.antwort), metric_a, metric_b);
		const k = await karte(STAND_C.antwort);
		k.u.haken({ metrik: deselect_metric_id, stelle: 'sms', an: false });
		k.u.reihenfolge(folge);
		const n = await nachSpeichern(STAND_C, 'golden_c', k);
		for (const rt of ['morning', 'evening']) {
			assert.deepEqual(n.listen[rt].sms, mitFolge(STAND_C.listen[rt].sms.filter(([m]) => m !== deselect_metric_id), folge), `${rt}/sms`);
			for (const s of ['email', 'telegram', 'outlook'] as const) assert.deepEqual(n.listen[rt][s], mitFolge(STAND_C.listen[rt][s], folge), `${rt}/${s}: Auswahl und Form bleiben`);
		}
		assert.ok(ids(STAND_C.listen.evening.sms).includes(deselect_metric_id), 'Messaufbau: die Metrik stand in der SMS');
	});
});
