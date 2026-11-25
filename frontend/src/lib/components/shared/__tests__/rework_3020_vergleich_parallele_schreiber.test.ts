// Rework #3020 R1 (Adversary F001): zwei parallele Schreiber im Ortsvergleich-Hub.
// Ersatz fuer den Vergleichs-Block des mit #3357 geloeschten
// wetter_metriken_versand_panel_speicherung.test.ts. Der pruefte zwei Schreiber an EINEM Controller,
// EINER Hub-Schlange (`createPutQueue`, compareHubPersistenz.ts) und EINER Basis -- damals ueber die
// Fabriken aus versandVergleichSpeicherung.ts/weatherMetricsCompareSave.ts, die heute keinen
// Produktionsaufrufer mehr haben. Heute verdrahtet CompareTabs.svelte dieselbe Lage mit den lebenden
// Speicherern: Reiter Wetter (`SPEICHERER.vergleich`, WetterTab) und Reiter Zustellung
// (`erstelleZustellungSpeicherung`, ZustellungTab), beide mit `saveController`, `enqueueHubWrite`
// (hubPutQueue) und Uebernahme der Serverantwort.
//
// Zusicherung: aendert der Nutzer im Entprell-Fenster beide Reiter, kommen BEIDE Aenderungen beim
// Server an (kein Schreiber verdraengt oder ueberschreibt den anderen, kein 412 durch einen
// veralteten Stempel), unabhaengig von der Reihenfolge; der Controller endet `idle`.
//
// Pruefstand ohne Mock: echtes `api` (If-Match), Go-Merge-Pruefserver (412 bei veraltetem ETag),
// echte Hub-Schlange, echter SaveStatus (Muster f003_vergleich_speicherer_hub_schlange.test.ts).
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/rework_3020_vergleich_parallele_schreiber.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import type { ComparePreset } from '../../../types.ts';
import { createPutQueue } from '../../compare/compareHubPersistenz.ts';
import { createController } from './versandVergleichPruefstand.ts';
import { createGoMergeServer, vollerVergleich, type GoMergeServer } from './goMergeServerPruefstand.ts';
import { aufgeloestVon, live } from '../wetter-tab/__tests__/wetterTabDaten.ts';
import { vorlagenAusTemplates } from '../wetter-tab/ampelModell.ts';
import { mitAlarmAb, standAusAbo, type AboSicht, type WetterStand } from '../wetter-tab/wetterZustand.ts';
import { SPEICHERER } from '../wetter-tab/wetterTabSpeicherung.ts';
import { standAusPreset, type ZustellungStand } from '../zustellung-tab/zustellungModell.ts';
import { erstelleZustellungSpeicherung } from '../zustellung-tab/zustellungSpeicherung.ts';

const ID = 'cp-3020-parallel';
const PFAD = `/api/compare/presets/${ID}`;

function abo(): Record<string, unknown> {
	const v = vollerVergleich(ID);
	const dc = v.display_config as Record<string, unknown>;
	dc.active_metrics = [
		{ metric_id: 'temperature', aggregation: 'max' },
		{ metric_id: 'wind', aggregation: 'max' },
		{ metric_id: 'gust', aggregation: 'max' }
	];
	dc.ampel = { template: 'allgemein' };
	return v;
}

let server: GoMergeServer;
const vorlagen = vorlagenAusTemplates(live().templates);

/** Netz-Laufzeit ueber dem Ersatz-Server: jeder PUT ist 20 ms unterwegs, bevor der Server ihn sieht.
 *  Erst damit koennen sich zwei Schreiber ueberholen (gleicher Stempel ⇒ 412), wenn die Hub-Schlange
 *  sie nicht nacheinander schickt. `gleichzeitig` = hoechste Zahl gleichzeitig offener PUTs. */
let offen = 0;
let gleichzeitig = 0;
function netzLaufzeit(): void {
	const darunter = globalThis.fetch;
	(globalThis as { fetch: unknown }).fetch = async (input: unknown, init?: RequestInit) => {
		if ((init?.method ?? 'GET').toUpperCase() !== 'PUT') return darunter(input as never, init);
		offen += 1;
		gleichzeitig = Math.max(gleichzeitig, offen);
		try {
			await new Promise((r) => setTimeout(r, 20));
			return await darunter(input as never, init);
		} finally {
			offen -= 1;
		}
	};
}

beforeEach(async () => {
	clearEtagRegistry();
	offen = 0;
	gleichzeitig = 0;
	server = createGoMergeServer({ [ID]: abo() });
	server.install();
	netzLaufzeit();
	await api.get(PFAD);
});
afterEach(() => server.restore());

const puts = () => server.mitschnitt.filter((e) => e.method === 'PUT');

/** EIN Controller, EINE Hub-Schlange, EINE Seiten-Basis -- wie CompareTabs.svelte. */
function hub() {
	let seite = abo() as AboSicht;
	const ctl = createController(ID);
	const queue = createPutQueue();
	// #2988 (#3379): Ampel und Vorlagen-ID kommen fertig vom Server (Aufloesung); wie WetterTabInhalt
	// hydriert der Reiter aus Abo + Aufloesung (echtes Python ueber aufgeloestVon, Muster f003).
	let wetterStand: WetterStand = standAusAbo('vergleich', seite, aufgeloestVon(seite));
	const wetter = SPEICHERER.vergleich({
		client: api,
		stand: () => wetterStand,
		vorlagen: () => vorlagen,
		abo: () => seite,
		saveController: ctl,
		enqueueHubWrite: (fn) => queue.enqueue(fn),
		uebernehmen: (a) => {
			seite = a as AboSicht;
		},
		neuGeladen: () => {}
	});
	const zustellBasis: ZustellungStand = standAusPreset(seite as unknown as ComparePreset);
	const zustellung = erstelleZustellungSpeicherung({
		context: 'vergleich',
		id: ID,
		client: api,
		saveController: ctl,
		basis: zustellBasis,
		enqueueHubWrite: (fn) => queue.enqueue(fn),
		onAntwort: (a) => {
			seite = a as AboSicht;
		}
	});
	return {
		ctl,
		queue,
		wetterAendern() {
			wetterStand = mitAlarmAb(wetterStand, 'gust', 'red');
			wetter.melden();
		},
		zustellungAendern() {
			zustellung.aenderungMelden({ ...zustellBasis, morgenZeit: '07:15' });
		}
	};
}

function beideAufDemServer(): void {
	assert.deepEqual(puts().map((p) => p.status), [200, 200], `erwartet zwei angenommene PUTs: ${JSON.stringify(puts().map((p) => p.status))}`);
	const s = server.stand(ID);
	const ampel = (s.display_config as Record<string, unknown>).ampel as { metrics?: Record<string, { alarm_ab?: string }> };
	assert.equal(ampel.metrics?.gust?.alarm_ab, 'red', 'die Aenderung des Reiters Wetter fehlt auf dem Server');
	assert.ok(String(s.morning_time).startsWith('07:15'), 'die Aenderung des Reiters Zustellung fehlt auf dem Server');
	assert.equal(gleichzeitig, 1, 'zwei PUTs waren gleichzeitig unterwegs (Hub-Schlange umgangen)');
}

describe('Rework #3020 F001: Wetter und Zustellung schreiben im Vergleichs-Hub parallel, keiner verdraengt den anderen', () => {
	test('Vorbedingung (Gegenprobe): jede Aenderung allein kommt an', async () => {
		const h = hub();
		h.wetterAendern();
		await h.ctl.flush();
		h.zustellungAendern();
		await h.ctl.flush();
		beideAufDemServer();
		assert.equal(h.ctl.state, 'idle');
	});

	test('Wetter, binnen der Entprellung Zustellung: beide Aenderungen auf dem Server, kein 412', async () => {
		const h = hub();
		h.wetterAendern();
		h.zustellungAendern();
		await h.ctl.flush();
		await h.ctl.flush();
		beideAufDemServer();
		assert.equal(h.ctl.state, 'idle');
	});

	// Der Controller reiht die beiden eigenen Vorgaenge schon nacheinander; die Hub-Schlange ordnet sie
	// zusaetzlich hinter fremde Hub-Schreiber (z. B. Orte-Reiter, Pausieren), die nicht ueber den
	// Controller laufen. Ohne Schlange gingen beide PUTs am laufenden Schreiber vorbei.
	test('ein fremder Hub-Schreiber laeuft: beide PUTs warten in der Hub-Schlange, danach beide auf dem Server', async () => {
		const h = hub();
		let freigeben!: () => void;
		const blocker = h.queue.enqueue(() => new Promise<void>((res) => (freigeben = res)));
		h.wetterAendern();
		h.zustellungAendern();
		const fertig = h.ctl.flush();
		await new Promise((r) => setTimeout(r, 60));
		assert.equal(puts().length, 0, 'ein Schreiber schreibt am laufenden Hub-Schreiber vorbei (keine Hub-Schlange)');
		freigeben();
		await blocker;
		await fertig;
		await h.ctl.flush();
		beideAufDemServer();
		assert.equal(h.ctl.state, 'idle');
	});

	test('Zustellung, binnen der Entprellung Wetter: beide Aenderungen auf dem Server, kein 412', async () => {
		const h = hub();
		h.zustellungAendern();
		h.wetterAendern();
		await h.ctl.flush();
		await h.ctl.flush();
		beideAufDemServer();
		assert.equal(h.ctl.state, 'idle');
	});
});
