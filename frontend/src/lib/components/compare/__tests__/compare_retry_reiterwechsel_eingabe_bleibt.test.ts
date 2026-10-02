// Fix-Loop 3, Issue #1433 — F201 (Compare-Paritaet) und F207 (Compare 'wiederholt' nur bei frischem Stand).
//
// F201 (Compare): der Hub haelt `wizardState` ueber Reiterwechsel hinweg; verloren geht die
// Eingabe, wenn ein ERSTMALS geoeffneter Nachbar-Reiter (Versand teilt Abkuehlzeit/Ruhezeit
// mit Alarme) `wizardState` aus dem veralteten Hub-`currentPreset` hydriert. Invariante:
// Seitenstand = Server ⊕ ausstehende Eigenfeld-Nutzlasten — der Hub schreibt sein
// `currentPreset` beim 412 lokal fort (ohne die Seiten-Prop zu aendern: deren Wechsel
// ruehrt Hydrations-Flags und den offenen Reiter an).
// Gemessen am ECHTEN CompareTabs-Skript (`umgebungFuer` + `effekteVon`: die echte
// Registrierung am Controller und der echte Versand-Hydrationseffekt), echtem Controller,
// echtem Alarme-Speicherweg und dem Go-Merge-Server.
//
// F207: die Seite uebernimmt bei 'wiederholt' den frisch geholten Stand nur, wenn seit
// Beginn des GET nichts Neues ansteht/gespeichert wurde und der Registry-Stempel passt.
// Der GET-Stand wird BEI ANKUNFT berechnet (veraltet), die Antwort kommt verzoegert.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/compare/__tests__/compare_retry_reiterwechsel_eingabe_bleibt.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { api } from '../../../api.ts';
import { clearEtagRegistry, getKnownEtag, istKonflikt } from '../../../etagRegistry.ts';
import { erstelleVersandVergleichSpeicherung } from '../../shared/versandVergleichSpeicherung.ts';
import type { ComparePreset } from '../../../types.ts';
import { createPutQueue } from '../compareHubPersistenz.ts';
import { hydrateAlarmFieldsFromPreset } from '../compareHubHydration.ts';
import { erstelleAlarmeVergleichSpeicherung } from '../../shared/alarmeVergleichSpeicherung.ts';
import { createController } from '../../shared/__tests__/versandVergleichPruefstand.ts';
import { umgebungFuer, effekteVon, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import {
	createGoMergeServer,
	vollerVergleich,
	type GoMergeServer
} from '../../shared/__tests__/goMergeServerPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const SEITE = join(FRONTEND, 'src/routes/compare/[id]/+page.svelte');
const HUB = join(HIER, '..', 'CompareTabs.svelte');
register(
	pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const ID = 'cp-1433-fl3';
const PFAD = `/api/compare/presets/${ID}`;
let server: GoMergeServer;
const warte = (ms: number) => new Promise((r) => setTimeout(r, ms));

beforeEach(async () => {
	clearEtagRegistry();
	server = createGoMergeServer({ [ID]: vollerVergleich(ID) });
	server.install();
	await api.get(PFAD);
});
afterEach(() => {
	server.restore();
	delete (globalThis as { window?: unknown }).window;
});

const fertig = async (ctl: ReturnType<typeof createController>) => {
	await ctl.flush();
	const l = ctl.laufendeSpeicherung;
	if (l) await l;
};

/** Der echte Hub (CompareTabs-Skript) mit seiner echten Registrierung am Controller. */
async function hub(ctl: ReturnType<typeof createController>) {
	const wizardState: Knoten = {};
	const { u, ast, quelle } = await umgebungFuer(HUB, {
		preset: vollerVergleich(ID),
		locations: [],
		saveController: ctl,
		wizardState
	});
	for (const e of effekteVon(ast, quelle, u, 'registriereAbgelehnt')) e();
	return { u, ast, quelle, wizardState };
}

/** Ein (neu gemounteter) Alarme-Reiter auf dem gemeinsamen `wizardState` des Hubs. */
function alarmeReiter(h: Awaited<ReturnType<typeof hub>>, ctl: ReturnType<typeof createController>) {
	const queue = createPutQueue();
	return erstelleAlarmeVergleichSpeicherung({
		client: api,
		zustand: h.wizardState,
		preset: () => h.u.currentPreset as ComparePreset,
		enqueueHubWrite: <T>(fn: () => Promise<T>) => queue.enqueue(fn),
		onCompareUpdate: (p: ComparePreset) => {
			h.u.currentPreset = p;
		},
		saveController: ctl
	});
}

/** Versand zum ERSTEN Mal oeffnen: der echte Hydrationseffekt liest den Hub-Stand. */
function versandErstmalsOeffnen(h: Awaited<ReturnType<typeof hub>>): void {
	h.u.activeTab = 'versand';
	const effekte = effekteVon(h.ast, h.quelle, h.u, 'hydrateVersandFieldsFromPreset');
	assert.equal(effekte.length, 1, 'Messaufbau: genau ein Versand-Hydrationseffekt');
	effekte[0]();
}

describe('F201 (Compare): Reiterwechsel nach einem Konflikt verliert die Eingabe nicht', () => {
	test('Alarme 412 (Abkuehlzeit), Versand erstmals oeffnen, zurueck: Reiter zeigt die Eingabe; zweite Aenderung + Nochmal speichern ⇒ BEIDE auf dem Server', async () => {
		server.fremdSchreiben(ID, { name: 'Fremder Name' });
		const ctl = createController(ID);
		const h = await hub(ctl);
		hydrateAlarmFieldsFromPreset(h.wizardState, h.u.currentPreset as ComparePreset, []);

		const erster = alarmeReiter(h, ctl); // Baseline = Stand nach der Hydration
		h.wizardState.alertCooldownMinutes = 77;
		erster.aenderungMelden();
		await fertig(ctl);
		assert.equal(ctl.state, 'conflict', 'Vorbedingung: 412');

		versandErstmalsOeffnen(h);
		const zurueck = alarmeReiter(h, ctl); // Rueckkehr in Alarme: neuer Reiter, gleicher wizardState
		assert.equal(h.wizardState.alertCooldownMinutes, 77, 'der Hub-Stand traegt die ungesicherte Eingabe, Versand ueberschreibt sie nicht');

		h.wizardState.alertQuietFrom = '21:00';
		zurueck.aenderungMelden();
		await fertig(ctl);
		assert.equal(ctl.state, 'conflict', 'Vorbedingung: weiter Konflikt');

		await ctl.retryConflict();
		const s = server.stand(ID);
		assert.equal(ctl.state, 'idle');
		assert.equal(s.name, 'Fremder Name', 'die Fremdaenderung bleibt');
		assert.equal(s.alert_cooldown_minutes, 77, 'die ERSTE Eingabe ging nicht verloren');
		assert.equal(s.alert_quiet_from, '21:00', 'die zweite steht auch auf dem Server');
	});

	test('ohne zweite Aenderung: Nochmal speichern schreibt genau das, was der Reiter zeigt (keine zwei Wahrheiten)', async () => {
		server.fremdSchreiben(ID, { name: 'Fremder Name' });
		const ctl = createController(ID);
		const h = await hub(ctl);
		hydrateAlarmFieldsFromPreset(h.wizardState, h.u.currentPreset as ComparePreset, []);
		const erster = alarmeReiter(h, ctl); // Baseline = Stand nach der Hydration
		h.wizardState.alertCooldownMinutes = 77;
		erster.aenderungMelden();
		await fertig(ctl);

		versandErstmalsOeffnen(h);
		alarmeReiter(h, ctl);
		const angezeigt = h.wizardState.alertCooldownMinutes;

		await ctl.retryConflict();
		assert.equal(ctl.state, 'idle');
		assert.equal(server.stand(ID).alert_cooldown_minutes, angezeigt, 'Server == Anzeige');
		assert.equal(angezeigt, 77);
	});
});

/** Echte Seiten-Instanz (+page.svelte des Vergleichs) mit gesaetem Controller. */
async function seite(ctl: ReturnType<typeof createController>): Promise<Knoten> {
	(globalThis as { window?: unknown }).window = {
		location: { href: `http://x/compare/${ID}?tab=alarme` },
		dispatchEvent: () => true,
		addEventListener: () => {}
	};
	const { u } = await umgebungFuer(SEITE, {
		data: { preset: vollerVergleich(ID), etag: server.etagOf(ID) },
		browser: true,
		hubSaveCtl: ctl
	});
	return u;
}

/** Lese-Antworten werden BEI ANKUNFT berechnet und dann verzoegert ausgeliefert. */
function verzoegereLesen(ms: number): () => void {
	const basis = globalThis.fetch;
	(globalThis as { fetch: unknown }).fetch = async (input: unknown, init?: RequestInit) => {
		const res = await basis(input as never, init);
		if ((init?.method ?? 'GET').toUpperCase() === 'GET') await warte(ms);
		return res;
	};
	return () => {
		(globalThis as { fetch: unknown }).fetch = basis;
	};
}

describe("F207 (Compare): 'wiederholt' uebernimmt den frisch geholten Stand nur, wenn er noch frisch ist", () => {
	test('Nutzer speichert im Latenzfenster des GET ⇒ KEIN Neuaufbau mit dem veralteten Stand (Stempel passt nicht mehr)', async () => {
		const ctl = createController(ID);
		const u = await seite(ctl);
		const zurueck = verzoegereLesen(150);
		ctl.onAdopt!({}, 'wiederholt');
		await warte(30);
		await api.put(PFAD, { alert_cooldown_minutes: 99 }); // 200, neuer Stempel
		await warte(300);
		zurueck();
		assert.equal(server.stand(ID).alert_cooldown_minutes, 99, 'Vorbedingung: die Eingabe steht auf dem Server');
		assert.equal(u.uebernommeneFassung, 0, 'kein Neuaufbau mit dem GET-Stand von vor der Eingabe');
	});

	test('ausstehende Eingabe (hasPending, Zustand trotzdem idle) waehrend des GET ⇒ kein Neuaufbau', async () => {
		const ctl = createController(ID);
		const u = await seite(ctl);
		const zurueck = verzoegereLesen(60);
		ctl.onAdopt!({}, 'wiederholt');
		await warte(10);
		ctl.defer(async () => {}); // Nutzer tippt: ausstehender Speichervorgang
		ctl.setSaved(); // ein gleichzeitig fertig werdender Speichervorgang setzt den Zustand auf 'idle' — die Eingabe steht trotzdem aus
		await warte(150);
		zurueck();
		assert.equal(ctl.hasPending, true, 'Vorbedingung');
		assert.equal(u.uebernommeneFassung, 0);
	});

	test("Controller nicht mehr 'idle' (Eingabe ohne Speichervorgang: dirty) waehrend des GET ⇒ kein Neuaufbau", async () => {
		const ctl = createController(ID);
		const u = await seite(ctl);
		const zurueck = verzoegereLesen(60);
		ctl.onAdopt!({}, 'wiederholt');
		await warte(10);
		ctl.setDirty();
		await warte(150);
		zurueck();
		assert.equal(u.uebernommeneFassung, 0);
	});

	test('Gegenprobe: ohne Stoerung wird frisch uebernommen und der Hub neu aufgebaut', async () => {
		const ctl = createController(ID);
		const u = await seite(ctl);
		server.fremdSchreiben(ID, { name: 'Server-Stand' });
		ctl.onAdopt!({}, 'wiederholt');
		await warte(80);
		assert.equal((u.currentPreset as ComparePreset).name, 'Server-Stand');
		assert.equal(u.uebernommeneFassung, 1);
	});
});

/** PUTs scheitern mit 500 (Server-Fehler), bis die zurueckgegebene Funktion gerufen wird. */
function putsScheitern(): () => void {
	const basis = globalThis.fetch;
	(globalThis as { fetch: unknown }).fetch = async (input: unknown, init?: RequestInit) =>
		(init?.method ?? 'GET').toUpperCase() === 'PUT'
			? new Response(JSON.stringify({ error: 'boom', detail: 'Serverfehler' }), {
					status: 500,
					headers: { 'Content-Type': 'application/json' }
				})
			: basis(input as never, init);
	return () => {
		(globalThis as { fetch: unknown }).fetch = basis;
	};
}

describe('F205: `imWiederholen` gilt nur WAEHREND der Wiederholung', () => {
	test('nach erfolgreichem Retry ist das Flag zurueck; ein Folge-Fehler setzt die Anzeige wie vorher zurueck (Rollback)', async () => {
		server.fremdSchreiben(ID, { name: 'Fremder Name' });
		const ctl = createController(ID);
		const h = await hub(ctl);
		hydrateAlarmFieldsFromPreset(h.wizardState, h.u.currentPreset as ComparePreset, []);
		const reiter = alarmeReiter(h, ctl);
		h.wizardState.alertCooldownMinutes = 77;
		reiter.aenderungMelden();
		await fertig(ctl);
		await ctl.retryConflict();
		assert.equal(ctl.state, 'idle');
		assert.equal(ctl.imWiederholen, false, 'das Flag ist nach dem Retry zurueckgesetzt');

		const ende = putsScheitern();
		h.wizardState.alertQuietFrom = '21:00';
		reiter.aenderungMelden();
		await fertig(ctl);
		ende();
		assert.equal(ctl.state, 'error', 'Folge-Fehler (500) ist ein normaler Fehler');
		assert.equal(h.wizardState.alertQuietFrom, '22:00', 'Rollback der Anzeige wie vor dem Retry (Flag haengt nicht)');
	});

	test('auch nach einem GESCHEITERTEN Retry ist das Flag zurueckgesetzt', async () => {
		server.fremdSchreiben(ID, { name: 'Fremder Name' });
		const ctl = createController(ID);
		const h = await hub(ctl);
		hydrateAlarmFieldsFromPreset(h.wizardState, h.u.currentPreset as ComparePreset, []);
		const reiter = alarmeReiter(h, ctl);
		h.wizardState.alertCooldownMinutes = 77;
		reiter.aenderungMelden();
		await fertig(ctl);

		const ende = putsScheitern();
		await ctl.retryConflict();
		ende();
		assert.equal(ctl.state, 'conflict');
		assert.equal(ctl.imWiederholen, false);
	});
});

describe('F301a (Fix-Loop 4, Compare): ein GESCHEITERTER Retry laesst keinen Save aus einem erstmals geoeffneten Reiter mit Hub-Altstand durch', () => {
	test('PX2: Fremd send_telegram=false, Retry 500, Versand erstmals oeffnen und speichern => 412, Server bleibt false; erneuter Retry => alles auf dem Server', async () => {
		server.fremdSchreiben(ID, { send_telegram: false, name: 'Fremder Name' });
		const ctl = createController(ID);
		const h = await hub(ctl);
		hydrateAlarmFieldsFromPreset(h.wizardState, h.u.currentPreset as ComparePreset, []);
		const al = alarmeReiter(h, ctl);
		h.wizardState.alertCooldownMinutes = 77;
		al.aenderungMelden();
		await fertig(ctl);
		assert.equal(ctl.state, 'conflict', 'Vorbedingung: 412');

		const ende = putsScheitern();
		await ctl.retryConflict();
		ende();
		assert.equal(ctl.state, 'conflict');
		assert.equal(istKonflikt(ID), true, 'die Markierung bleibt nach dem gescheiterten Retry');

		versandErstmalsOeffnen(h);
		const queue = createPutQueue();
		const vs = erstelleVersandVergleichSpeicherung({
			client: api,
			zustand: h.wizardState,
			preset: () => h.u.currentPreset as ComparePreset,
			enqueueHubWrite: <T>(fn: () => Promise<T>) => queue.enqueue(fn),
			onCompareUpdate: (p: ComparePreset) => {
				h.u.currentPreset = p;
			},
			saveController: ctl
		});
		h.wizardState.eveningEnabled = true;
		vs.aenderungMelden();
		await fertig(ctl);
		assert.equal(server.stand(ID).send_telegram, false, 'Fremdaenderung bleibt (kein Hub-Altstand darueber)');
		assert.equal(ctl.state, 'conflict', 'Konflikt-Anzeige bleibt');

		await ctl.retryConflict();
		assert.equal(ctl.state, 'idle');
		assert.equal(server.stand(ID).name, 'Fremder Name', 'Fremdaenderung ausserhalb der Versand-Gruppe steht nach dem Retry weiter');
		assert.equal(server.stand(ID).alert_cooldown_minutes, 77);
		assert.equal(server.stand(ID).evening_enabled, true);
	});
});

describe('F204: ein Lese-GET im Flug waehrend eines 412 uebernimmt seinen Stempel nicht (bumpVersion in markiereKonflikt)', () => {
	test('GET startet vor dem 412 und antwortet danach => die Registry behaelt den Stempel des abgelehnten Schreibens', async () => {
		const e0 = getKnownEtag(ID);
		server.fremdSchreiben(ID, { name: 'Fremder Name' });
		const bremse = verzoegereLesen(120);
		const lesen = api.get(PFAD); // Antwort traegt den NEUEN Stempel, trifft aber erst nach dem 412 ein
		const ctl = createController(ID);
		const h = await hub(ctl);
		hydrateAlarmFieldsFromPreset(h.wizardState, h.u.currentPreset as ComparePreset, []);
		const al = alarmeReiter(h, ctl);
		h.wizardState.alertCooldownMinutes = 77;
		al.aenderungMelden();
		await fertig(ctl);
		assert.equal(ctl.state, 'conflict', 'Vorbedingung: der 412 kam, waehrend der GET noch unterwegs war');
		await lesen;
		bremse();
		assert.equal(getKnownEtag(ID), e0, 'der verspaetete GET darf den Konflikt-Stempel nicht ueberschreiben');
	});
});
