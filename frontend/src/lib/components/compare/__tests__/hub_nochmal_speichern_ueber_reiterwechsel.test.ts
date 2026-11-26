// TDD RED — Issue #1433, AC-20 (Paritaet Ortsvergleich): der Ortsvergleich-Hub
// (`hubSaveCtl`, routes/compare/[id]/+page.svelte:70) teilt Controller-Klasse,
// Registry und `api.ts` mit der Trip-Seite — und damit denselben Fehler: nach
// einem 412 springt die Anzeige beim Speichern in einem ANDEREN Reiter von
// `conflict` auf `idle` („Nochmal speichern" verschwindet), und der Retry kennt nur
// den letzten gescheiterten Speichervorgang. Dieselbe Zusicherung wie auf der
// Trip-Seite: Anzeige bleibt ueber den Reiterwechsel, nichts Fremdes wird
// ueberschrieben, nach „Nochmal speichern" stehen BEIDE Aenderungen auf dem Server.
//
// Spec: docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md — §4 Punkt 6, AC-20.
//
// Messaufbau: wie `compareReiterAufbauPruefstand.ts` (echte `erstelle…Speicherung`,
// echte Hydration, echter SaveStatus MIT Kennung `vergleich`, echte Hub-Queue,
// echtes `api`, Go-treuer Ersatz-Server) — aber ZWEI Reiter (Alarme, Wertebereiche; bis #3389 Versand) teilen
// EINEN Controller, EINE Queue und EINE Basis, wie im Hub (CompareTabs).
//
// Erwartet gruen bleibend (Regressionswaechter, AC-21): Teilfeld-Nutzlasten des
// Ortsvergleichs aus #2375 — der Name der Fremdaenderung wird nie zurueckgeschrieben.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/compare/__tests__/hub_nochmal_speichern_ueber_reiterwechsel.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import * as registry from '../../../etagRegistry.ts';
import { clearEtagRegistry, getKnownEtag } from '../../../etagRegistry.ts';
import type { ComparePreset } from '../../../types.ts';
import { createPutQueue } from '../compareHubPersistenz.ts';
import { hydrateAlarmFieldsFromPreset } from '../compareHubHydration.ts';
import { erstelleAlarmeVergleichSpeicherung } from '../../shared/alarmeVergleichSpeicherung.ts';
import { erstelleWertebereicheVergleichSpeicherung } from '../../shared/wetter-tab/wertebereicheVergleichSpeicherung.ts';
import {
	hydrierterWs,
	wertebereicheBedienung
} from '../../shared/wetter-tab/__tests__/wertebereicheVergleichPruefstand.ts';
import { createController } from '../../shared/__tests__/versandVergleichPruefstand.ts';
import {
	createGoMergeServer,
	vollerVergleich,
	type GoMergeServer
} from '../../shared/__tests__/goMergeServerPruefstand.ts';

const ID = 'cp-1433-paritaet';
const PFAD = `/api/compare/presets/${ID}`;

let server: GoMergeServer;

beforeEach(async () => {
	clearEtagRegistry();
	server = createGoMergeServer({ [ID]: vollerVergleich(ID) });
	server.install();
	await api.get(PFAD); // beide Reiter haben den Vergleich mit diesem Stand geladen
});
afterEach(() => server.restore());

/** Zwei Reiter des Hubs, EIN Controller (`hubSaveCtl`), EINE Queue, EINE Basis. */
function hub() {
	let basis = vollerVergleich(ID) as unknown as ComparePreset;
	const ctl = createController(ID);
	const queue = createPutQueue();
	const gemeinsam = {
		client: api,
		preset: () => basis,
		enqueueHubWrite: <T>(fn: () => Promise<T>) => queue.enqueue(fn),
		onCompareUpdate: (p: ComparePreset) => {
			basis = p;
		},
		saveController: ctl
	};
	const alarmeZustand: Record<string, unknown> = {};
	hydrateAlarmFieldsFromPreset(alarmeZustand, basis, []);
	const alarme = erstelleAlarmeVergleichSpeicherung({ ...gemeinsam, zustand: alarmeZustand });
	// #3389: Reiter B ist der Wertebereiche-Speicherer (der Versand-Speicherer war tot).
	const wertebereicheZustand = hydrierterWs(basis);
	const wertebereiche = erstelleWertebereicheVergleichSpeicherung({ ...gemeinsam, zustand: wertebereicheZustand });
	return {
		ctl,
		alarmeAendern() {
			alarmeZustand.radarAlertEnabled = !(alarmeZustand.radarAlertEnabled as boolean);
			alarme.aenderungMelden();
		},
		wertebereicheAendern() {
			wertebereicheBedienung(wertebereicheZustand).patch('wind_max_kmh', { max: 55 });
			wertebereiche.aenderungMelden();
		}
	};
}

/** Höchstwert des Wind-Korridors im Server-Stand. */
const windMax = (stand: Record<string, unknown>) =>
	((stand.corridors as Array<{ metric: string; range: [number | null, number | null] }>) ?? []).find(
		(c) => c.metric === 'wind_max_kmh'
	)?.range?.[1];

const putEintraege = () => server.mitschnitt.filter((e) => e.method === 'PUT');

describe('AC-20: Hub — Anzeige bleibt ueber den Reiterwechsel, Retry schreibt beide Reiter', () => {
	test('A (Alarme) 412, Wechsel, B (Wertebereiche) speichert: Anzeige bleibt, B bekommt 412 mit If-Match, Fremdaenderung unveraendert', async () => {
		server.fremdSchreiben(ID, { name: 'Fremd von A' });
		const h = hub();
		const stand0 = JSON.stringify(server.stand(ID));
		const alt = getKnownEtag(ID);

		h.alarmeAendern();
		await h.ctl.flush();
		assert.equal(putEintraege()[0].status, 412, 'Vorbedingung: Alarme-Reiter scheitert am Fremdschreiber');
		assert.equal(h.ctl.state, 'conflict', 'Vorbedingung: Konfliktanzeige');

		// Reiterwechsel, Wertebereiche-Reiter speichert
		h.wertebereicheAendern();
		await h.ctl.flush();

		assert.equal(h.ctl.state, 'conflict', 'AC-20: „Nochmal speichern" bleibt nach dem Speichern im anderen Reiter sichtbar');
		const b = putEintraege().at(-1)!;
		assert.equal(b.ifMatch, alt, 'der Wertebereiche-PUT bei offenem Konflikt traegt das ALTE If-Match (kein unbedingtes Schreiben)');
		assert.equal(b.status, 412);
		assert.equal(JSON.stringify(server.stand(ID)), stand0, 'der Server ist unveraendert — weder A noch B haben geschrieben');
		assert.equal(server.stand(ID).name, 'Fremd von A');
	});

	test('„Nochmal speichern": Fremdaenderung, Alarme-Aenderung (A) UND Wertebereiche-Aenderung (B) stehen danach auf dem Server', async () => {
		server.fremdSchreiben(ID, { name: 'Fremd von A' });
		const h = hub();
		h.alarmeAendern();
		await h.ctl.flush();
		h.wertebereicheAendern();
		await h.ctl.flush();
		assert.equal(h.ctl.state, 'conflict', 'Vorbedingung');

		const vorRetry = putEintraege().length;
		await h.ctl.retryConflict();

		const retryPuts = putEintraege().slice(vorRetry);
		assert.ok(retryPuts.length >= 2, `beide Reiter muessen erneut gesendet werden, gesehen: ${retryPuts.length}`);
		for (const p of retryPuts) assert.equal(p.status, 200);
		const s = server.stand(ID);
		assert.equal(s.name, 'Fremd von A', 'Fremdaenderung bleibt');
		assert.equal(s.radar_alert_enabled, true, 'Alarme-Aenderung aus Reiter A steht auf dem Server');
		assert.equal(windMax(s), 55, 'Wertebereiche-Aenderung aus Reiter B steht auf dem Server');
		assert.equal(h.ctl.state, 'idle', 'die Konfliktanzeige verschwindet');
		const f = (registry as unknown as { istKonflikt?: (i: string) => boolean }).istKonflikt;
		assert.equal(typeof f, 'function', 'etagRegistry.ts muss `istKonflikt(id)` exportieren');
		assert.equal(f!(ID), false, 'die Konflikt-Markierung ist geloescht');
	});

	test('Gegenprobe: ohne Fremdschreiber speichern beide Reiter normal und die Anzeige endet in „Gespeichert"', async () => {
		const h = hub();
		h.alarmeAendern();
		await h.ctl.flush();
		h.wertebereicheAendern();
		await h.ctl.flush();

		assert.equal(h.ctl.state, 'idle');
		assert.ok(putEintraege().every((p) => p.status === 200));
		assert.equal(server.stand(ID).radar_alert_enabled, true);
		assert.equal(windMax(server.stand(ID)), 55);
	});
});
