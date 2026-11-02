// TDD RED — Issue #2213: bauliche Aenderungen im Etappen-Tab (Etappe hinzufuegen/
// loeschen, Pausentag, Klick ins Hoehenprofil, Wegpunkt umbenennen/loeschen) aendern
// im Auto-Save-Modus nur den Bildschirmstand. Es wird weder gespeichert noch
// vorgemerkt — weder Seiten- noch Reiterwechsel retten die Aenderung: stiller Verlust.
//
// Spec: docs/specs/modules/etappen_bauliche_aenderung_speichern.md (AC-1 … AC-10).
//
// Gemessen am ECHTEN Instanz-Skript (`tripMehrreiterPruefstand.ts`), echtem `api`,
// echtem SaveStatus und dem Ersatz-Server im Merge-Modus — gelesen wird der SERVER-STAND.
//
// 🔴 Gewartet wird in Echtzeit, OHNE `flush()`: der Befund ist gerade, dass ein
// vorgemerkter Vorgang erst beim Flush feuert. Ein Flush im Test rettete ihn und
// ergaebe falsches Gruen. Nur AC-5 flusht — dort ist das Vormerken die Zusicherung.
//
// Pruefstand-Eigenheit: `$derived` wird beim Aufbau EINMAL ausgewertet, nicht
// nachgefuehrt. `cascadeFollowers` wird deshalb so gesetzt, wie Svelte es nach der
// jeweiligen Handlung herleitet; `activeStage` ist die beim Aufbau aktive Etappe T1.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/__tests__/etappen_bauliche_aenderung_speichert.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import * as P from './tripMehrreiterPruefstand.ts';
import { locale } from '../../../i18n/index.ts';
import { isPauseStage } from '../../shared/wizardHelpers.ts';

type Wp = { id: string; name: string };
type St = { id: string; name: string; date: string; waypoints: Wp[] };

function tripMitDreiEtappen(): Record<string, unknown> {
	const t = P.vollerTrip();
	const wp = (id: string, lat: number, ele: number) => ({ id, name: id, lat, lon: 9.0, elevation_m: ele });
	t.stages = [
		{ id: 'T1', name: 'Etappe 1', date: '2026-10-10', waypoints: [wp('G1a', 42.1, 100), wp('G1b', 42.14, 500)] },
		{ id: 'T2', name: 'Etappe 2', date: '2026-10-11', waypoints: [wp('G2a', 42.2, 200), wp('G2b', 42.24, 600)] },
		{ id: 'T3', name: 'Etappe 3', date: '2026-10-12', waypoints: [wp('G3a', 42.3, 300), wp('G3b', 42.34, 700)] }
	];
	return t;
}

let server: FakeTripServer;
const originalPrompt = (globalThis as { prompt?: unknown }).prompt;

beforeEach(async () => {
	clearEtagRegistry();
	server = createFakeTripServer({ merge: true });
	server.install();
	server.seed(P.TRIP_ID, tripMitDreiEtappen());
	await api.get(P.TRIP_PFAD);
});
afterEach(() => {
	server.restore();
	(globalThis as { prompt?: unknown }).prompt = originalPrompt;
});

const puts = () => server.calls.filter((c) => c.method === 'PUT');
const serverEtappen = () => server.stand(P.TRIP_ID).stages as St[];
const ids = (stages: unknown) => (stages as St[]).map((s) => s.id);
const warte = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Echtzeit-Ruhe ueber den 700-ms-Entprell-Takt hinaus, OHNE Flush; danach
 *  laufende PUTs zu Ende kommen lassen. */
async function ruhe(ms = 1000): Promise<void> {
	await warte(ms);
	const ende = Date.now() + 2000;
	while (server.calls.some((c) => Number.isNaN(c.finishedAt)) && Date.now() < ende) await warte(10);
}

async function aufbau(trip = tripMitDreiEtappen()) {
	const a = P.neuerAufbau(trip);
	const e = await P.etappenReiter(a);
	return { a, e, u: e.inst.u };
}

type U = Awaited<ReturnType<typeof aufbau>>['u'];
const rufe = (u: U, name: string, ...args: unknown[]) => (u[name] as (...a: unknown[]) => unknown)(...args);

/** Etappe ueber den Loesch-Dialog loeschen (wie Klick auf × und „Loeschen"). */
function loesche(u: U, stageId: string): void {
	u.pendingRemoveStageId = stageId;
	rufe(u, 'confirmRemoveStage');
}

/** Rueckfrage zur Datumsverschiebung oeffnen: Datum von `stageId` aendern. */
function rueckfrageOeffnen(u: U, stageId: string, datum: string, folger: string[]): void {
	rufe(u, 'handleDateChange', stageId, datum);
	const c = u.cascade as { done: boolean; stageId: string } | null;
	assert.ok(c && !c.done && c.stageId === stageId, 'Messaufbau: Rueckfrage zur Datumsverschiebung steht');
	u.cascadeFollowers = folger; // $derived, wie Svelte es herleitet
}

/** Genau EIN PUT, und zwar sofort (vor Ablauf des 700-ms-Entprell-Takts). */
async function genauEinSofortigerPut(hinweis: string): Promise<void> {
	await warte(200);
	assert.ok(puts().length >= 1, `${hinweis}: nach 200 ms muss der Speichervorgang laufen — heute 0 PUT (nur Bildschirmstand)`);
	await ruhe();
	assert.equal(puts().length, 1, `${hinweis}: genau EIN Speichervorgang`);
	assert.equal(puts()[0].status, 200, `${hinweis}: PUT erfolgreich`);
}

describe('AC-1/AC-2: Etappe hinzufuegen, Pausentag, Etappe loeschen ⇒ sofort gespeichert', () => {
	test('AC-1: „+ Etappe" (Strip) ⇒ ein PUT, neue Etappe steht auf dem Server', async () => {
		const { a, u } = await aufbau();
		rufe(u, 'handleAddStage');
		await genauEinSofortigerPut('Etappe hinzufuegen');
		assert.equal(serverEtappen().length, 4);
		assert.equal(serverEtappen()[3].name, 'Neue Etappe');
		assert.equal(a.ctl.hasPending, false, 'nichts bleibt vorgemerkt');
	});

	test('AC-1: Pausentag in der Strip-Luecke ⇒ ein PUT, Pausentag an Position 2', async () => {
		const { u } = await aufbau();
		rufe(u, 'handlePauseInsert', 0);
		await genauEinSofortigerPut('Pausentag einfuegen');
		const s = serverEtappen();
		assert.equal(s.length, 4);
		assert.equal(s[1].name, 'Pausentag');
		assert.deepEqual([s[0].id, s[2].id, s[3].id], ['T1', 'T2', 'T3']);
	});

	test('AC-1/AC-2: Etappe ueber den Loesch-Dialog loeschen ⇒ ein PUT ohne die Etappe', async () => {
		const { a, u } = await aufbau();
		loesche(u, 'T2');
		await genauEinSofortigerPut('Etappe loeschen');
		assert.deepEqual(ids(serverEtappen()), ['T1', 'T3'], 'die geloeschte Etappe kehrt nach dem Neuladen nicht zurueck');
		assert.equal(a.ctl.hasPending, false);
	});

	test('AC-2: mobil „+ Etappe" → Pausentag ⇒ ein PUT, Pausentag am Ende', async () => {
		const { u } = await aufbau();
		rufe(u, 'handleMobileAddPause');
		await genauEinSofortigerPut('mobil Pausentag');
		const s = serverEtappen();
		assert.equal(s.length, 4);
		assert.equal(s[3].name, 'Pausentag');
	});
});

// Issue #2658 (i18n F9, Adversary F001): die Vorschlagsnamen sind gespeicherte DATEN — auch
// unter englischer Oberflaeche bleibt die Nutzlast sprachunabhaengig („Pausentag" erkennt
// isPauseStage() am Namen). Gemessen am Server-Stand nach dem echten Handler.
describe('i18n F9: Vorschlagsnamen in der Nutzlast unter locale=en unveraendert', () => {
	afterEach(() => locale.set('de'));
	const pausen = [
		['handlePauseInsert (Strip-Luecke)', (u: U) => rufe(u, 'handlePauseInsert', 0), 1],
		['handleMobileAddPause (mobil)', (u: U) => rufe(u, 'handleMobileAddPause'), 3]
	] as const;
	for (const [name, ausloesen, pos] of pausen) {
		test(`${name}: name === 'Pausentag', isPauseStage true`, async () => {
			const { u } = await aufbau();
			locale.set('en');
			ausloesen(u);
			await genauEinSofortigerPut(name);
			const s = serverEtappen()[pos];
			assert.equal(s.name, 'Pausentag');
			assert.equal(isPauseStage(s as never), true);
		});
	}
	test('handleAddStage / handleProfileAdd: „Neue Etappe" / „Neuer Punkt" unveraendert', async () => {
		const { u } = await aufbau();
		locale.set('en');
		rufe(u, 'handleAddStage');
		rufe(u, 'handleProfileAdd', 0.5);
		await ruhe();
		const s = serverEtappen();
		assert.equal(s[3].name, 'Neue Etappe');
		assert.equal(s.find((x) => x.id === 'T1')!.waypoints[1].name, 'Neuer Punkt');
	});
});

describe('AC-3: Hoehenprofil und Wegpunkte ⇒ sofort gespeichert', () => {
	test('AC-3: Klick ins Hoehenprofil ⇒ ein PUT, neuer Wegpunkt in T1', async () => {
		const { u } = await aufbau();
		rufe(u, 'handleProfileAdd', 0.5);
		await genauEinSofortigerPut('Profil-Klick');
		const t1 = serverEtappen().find((s) => s.id === 'T1')!;
		assert.equal(t1.waypoints.length, 3);
		assert.equal(t1.waypoints[1].name, 'Neuer Punkt');
	});

	test('AC-3: Wegpunkt umbenennen ⇒ ein PUT mit neuem Namen (nicht entprellt)', async () => {
		(globalThis as { prompt?: unknown }).prompt = () => 'Gipfelkreuz';
		const { u } = await aufbau();
		(rufe(u, 'makeRenameHandler', 'T1', 'G1b') as () => void)();
		await genauEinSofortigerPut('Wegpunkt umbenennen');
		const t1 = serverEtappen().find((s) => s.id === 'T1')!;
		assert.deepEqual(t1.waypoints.map((w) => w.name), ['G1a', 'Gipfelkreuz']);
	});

	test('AC-3: Wegpunkt loeschen ⇒ ein PUT ohne den Wegpunkt', async () => {
		const { u } = await aufbau();
		(rufe(u, 'makeDeleteHandler', 'T1', 'G1a') as () => void)();
		await genauEinSofortigerPut('Wegpunkt loeschen');
		const t1 = serverEtappen().find((s) => s.id === 'T1')!;
		assert.deepEqual(t1.waypoints.map((w) => w.id), ['G1b']);
	});
});

describe('AC-4: Knopf-Modus und Neuanlage speichern NICHT automatisch (Waechter)', () => {
	for (const [art, ohne] of [
		['Knopf-Modus (kein saveController)', { saveController: undefined }],
		['Neuanlage (weder saveController noch tripId)', { saveController: undefined, tripId: undefined }]
	] as const) {
		test(`AC-4: ${art} ⇒ 0 PUT bei Hinzufuegen, Loeschen, Pausentag, Profil-Klick`, async () => {
			const { u } = await aufbau();
			Object.assign(u, ohne);
			rufe(u, 'handleAddStage');
			rufe(u, 'handlePauseInsert', 0);
			rufe(u, 'handleMobileAddPause');
			rufe(u, 'handleProfileAdd', 0.5);
			loesche(u, 'T2');
			await ruhe();
			assert.equal(puts().length, 0, 'gespeichert wird nur ueber den Knopf bzw. die Anlage-Schaltflaeche');
			assert.equal((u.stages as St[]).length, 5, 'Messaufbau: die Handlungen haben gewirkt');
		});
	}
});

describe('AC-5: offene Rueckfrage ⇒ nur vormerken, nichts geht verloren (Waechter)', () => {
	test('AC-5: Etappe hinzufuegen bei offener Rueckfrage ⇒ 0 PUT, vorgemerkt; Flush schreibt den neuen Stand', async () => {
		const { a, u } = await aufbau();
		rueckfrageOeffnen(u, 'T1', '2026-10-15', ['T2', 'T3']);
		rufe(u, 'handleAddStage');
		await ruhe();
		assert.equal(puts().length, 0, 'nichts an der Rueckfrage vorbei schreiben');
		assert.equal(a.ctl.hasPending, true, 'die Aenderung ist vorgemerkt');
		await P.fertig(a.ctl); // Seiten-/Reiterwechsel
		assert.equal(puts().length, 1);
		assert.equal(serverEtappen().length, 4, 'die neue Etappe geht beim Verlassen nicht verloren');
		assert.equal(serverEtappen()[0].date, '2026-10-15', 'die Datumsaenderung auch nicht');
	});

	test('AC-5: Folge-Etappe loeschen bei weiter offener Rueckfrage ⇒ 0 PUT; „Nur diese Etappe" schreibt den Stand ohne sie', async () => {
		const { a, u } = await aufbau();
		rueckfrageOeffnen(u, 'T1', '2026-10-15', ['T2', 'T3']);
		u.cascadeFollowers = ['T3']; // nach dem Loeschen von T2 hergeleitet
		loesche(u, 'T2');
		await ruhe();
		assert.equal(puts().length, 0);
		assert.equal(a.ctl.hasPending, true);
		rufe(u, 'dismissCascade');
		await ruhe(100);
		assert.equal(puts().length, 1, 'die Antwort schreibt genau einmal');
		assert.deepEqual(ids(serverEtappen()), ['T1', 'T3']);
	});
});

describe('AC-6/AC-7: Rueckfrage wird durch Loeschen gegenstandslos ⇒ genau EIN PUT', () => {
	test('AC-6: ausloesende Etappe loeschen ⇒ Rueckfrage weg, genau ein PUT ohne sie, nichts vorgemerkt', async () => {
		const { a, u } = await aufbau();
		rueckfrageOeffnen(u, 'T1', '2026-10-15', ['T2', 'T3']);
		loesche(u, 'T1');
		await ruhe();
		assert.equal(u.cascade, null, 'die Rueckfrage ist verschwunden');
		assert.equal(puts().length, 1, 'genau EIN Speichervorgang — heute 0 (nur vorgemerkt, ohne Zeitgeber)');
		assert.deepEqual(ids(serverEtappen()), ['T2', 'T3'], 'die geloeschte Etappe erscheint nach dem Neuladen nicht wieder');
		assert.equal(a.ctl.hasPending, false, 'nichts bleibt vorgemerkt');
	});

	test('AC-7: letzte Folge-Etappe loeschen ⇒ genau EIN PUT (kein doppelter), Stand ohne sie', async () => {
		const { a, u } = await aufbau();
		rueckfrageOeffnen(u, 'T1', '2026-10-15', ['T2', 'T3']);
		u.cascadeFollowers = ['T3'];
		loesche(u, 'T2');
		u.cascadeFollowers = []; // nach dem Loeschen von T3 hergeleitet ⇒ Rueckfrage gegenstandslos
		loesche(u, 'T3');
		await ruhe();
		assert.equal(puts().length, 1, 'genau EIN Speichervorgang (Doppel-PUT-Schutz)');
		assert.deepEqual(ids(serverEtappen()), ['T1']);
		assert.equal(serverEtappen()[0].date, '2026-10-15');
		assert.equal(a.ctl.hasPending, false);
	});
});

describe('AC-8: entprellte Datumsaenderung + Loeschen ⇒ gespeichert ohne Seitenwechsel', () => {
	test('AC-8: Datum der letzten Etappe aendern, sofort andere Etappe loeschen ⇒ PUT mit Datum, ohne die Etappe, kein verwaister Vormerkzustand', async () => {
		const { a, u } = await aufbau();
		rufe(u, 'handleDateChange', 'T3', '2026-10-20'); // letzte Etappe ⇒ keine Rueckfrage, entprellt
		assert.equal(u.cascade, null, 'Messaufbau: keine Rueckfrage');
		assert.equal(a.ctl.hasPending, true, 'Messaufbau: das Speichern der Datumsaenderung steht aus');
		loesche(u, 'T1');
		await ruhe(1200);
		assert.equal(puts().length, 1, 'ohne Seitenwechsel gespeichert — heute 0 (zeitgeberlos vorgemerkt)');
		assert.deepEqual(ids(serverEtappen()), ['T2', 'T3']);
		assert.equal(serverEtappen()[1].date, '2026-10-20', 'das geaenderte Datum bleibt erhalten');
		assert.equal(a.ctl.hasPending, false, 'kein verwaister, zeitgeberloser Vormerkzustand');
	});
});

describe('AC-9: waehrend die Kaskade angewendet wird, aendern Profil und Wegpunkte nichts', () => {
	test('AC-9: cascadeBusy ⇒ Profil-Klick, Wegpunkt umbenennen/loeschen lassen `stages` unveraendert, 0 PUT', async () => {
		(globalThis as { prompt?: unknown }).prompt = () => 'Gipfelkreuz';
		const { u } = await aufbau();
		const vorher = JSON.stringify(u.stages);
		u.cascadeBusy = true;
		rufe(u, 'handleProfileAdd', 0.5);
		(rufe(u, 'makeRenameHandler', 'T1', 'G1b') as () => void)();
		(rufe(u, 'makeDeleteHandler', 'T1', 'G1a') as () => void)();
		await ruhe();
		assert.equal(JSON.stringify(u.stages), vorher, 'die Handlungen aendern waehrend der Kaskade nichts');
		assert.equal(puts().length, 0);
	});
});

describe('AC-10: Umsortieren (#2288) unveraendert (Regressionswaechter fuer den Helfer)', () => {
	test('AC-10: Ablegen ohne Rueckfrage ⇒ sofort genau ein PUT mit neuer Reihenfolge', async () => {
		const { u } = await aufbau();
		const s = u.stages as St[];
		rufe(u, 'handleStagesReorder', [s[1], s[0], s[2]]);
		rufe(u, 'handleReorderEnd');
		await genauEinSofortigerPut('Umsortieren');
		assert.deepEqual(ids(serverEtappen()), ['T2', 'T1', 'T3']);
	});

	test('AC-10: Ablegen bei offener Rueckfrage ⇒ 0 PUT, vorgemerkt', async () => {
		const { a, u } = await aufbau();
		rueckfrageOeffnen(u, 'T1', '2026-10-15', ['T2', 'T3']);
		const s = u.stages as St[];
		rufe(u, 'handleStagesReorder', [s[0], s[2], s[1]]);
		u.cascadeFollowers = ['T3', 'T2'];
		rufe(u, 'handleReorderEnd');
		await ruhe();
		assert.equal(puts().length, 0);
		assert.equal(a.ctl.hasPending, true);
	});
});

describe('F001: nach angewendeter Kaskade (Erfolgs-Streifen, cascade.done) wird sofort geschrieben', () => {
	async function kaskadeAngewendet() {
		const { a, u } = await aufbau();
		rueckfrageOeffnen(u, 'T1', '2026-10-15', ['T2', 'T3']);
		await (u.applyCascade as () => Promise<void>)();
		await ruhe(300);
		const c = u.cascade as { done: boolean } | null;
		assert.ok(c && c.done === true, 'Messaufbau: Kaskade angewendet, Erfolgs-Streifen steht');
		assert.equal(a.ctl.hasPending, false, 'Messaufbau: nichts vorgemerkt');
		return { a, u, vorher: puts().length };
	}

	test('F001: Etappe hinzufuegen nach Kaskade ⇒ genau ein weiterer PUT, nichts vorgemerkt', async () => {
		const { a, u, vorher } = await kaskadeAngewendet();
		rufe(u, 'handleAddStage');
		await ruhe();
		assert.equal(puts().length - vorher, 1, 'genau EIN Speichervorgang fuer die Handlung');
		assert.equal(serverEtappen().length, 4, 'neue Etappe steht auf dem Server');
		assert.equal(a.ctl.hasPending, false, 'nichts bleibt vorgemerkt');
	});

	test('F001: Etappe loeschen nach Kaskade ⇒ genau ein weiterer PUT ohne die Etappe', async () => {
		const { a, u, vorher } = await kaskadeAngewendet();
		loesche(u, 'T3');
		await ruhe();
		assert.equal(puts().length - vorher, 1);
		assert.deepEqual(ids(serverEtappen()), ['T1', 'T2']);
		assert.equal(a.ctl.hasPending, false);
	});
});

describe('F003: saveController vorhanden, aber keine tripId', () => {
	test('F003: 0 PUT bei Hinzufuegen, Pausentag, Profil-Klick, Loeschen', async () => {
		const { u } = await aufbau();
		Object.assign(u, { tripId: undefined });
		rufe(u, 'handleAddStage');
		rufe(u, 'handlePauseInsert', 0);
		rufe(u, 'handleProfileAdd', 0.5);
		loesche(u, 'T2');
		await ruhe();
		assert.equal(puts().length, 0, 'ohne tripId wird nichts automatisch geschrieben');
	});
});
