// TDD RED — Issue #1433 Fix-Loop (CI-Befund PR #2486, E2E Test 9 Orte / Test 11a):
// Orte-Speichern (`persistPickedIds`) und Pausieren/Aktivieren (`handleToggleActive`)
// im Hub schreiben mit Registry-If-Match, aber am Controller vorbei. Nach einem 412
// bleibt das alte If-Match stehen (#1433 §4.1) — ohne Meldung an den Controller gab es
// keinen „Nochmal speichern"-Knopf, jeder weitere Versuch endete wieder mit 412.
//
// Spec: docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md — §4 (2/4/5/6), AC-18,
//       AC-19, AC-20.
//
// Fallen aus dem Auftrag (docs/artifacts/fix-1433-mehrreiter-412-datenverlust/
// fix-loop-ci-e2e-sackgassen.md), hier je als eigene Zusicherung gemessen:
//   1. Orte: bei 412 KEIN Rollback (die Liste, die B sieht, ist die, die der Retry sendet);
//      bei anderen Fehlern bleibt der Rollback.
//   2. Pausieren: der Retry darf keinen veralteten `previous_schedule` festschreiben.
//   3. `setSaving()` in `handleToggleActive` darf einen offenen Konflikt nicht beenden.
//
// Gemessen am ECHTEN Instanz-Skript von `CompareTabs.svelte`, echtem `api`, echter
// Hub-Queue, echtem SaveStatus (Kennung `vergleich`) und dem Go-treuen Ersatz-Server.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/compare/__tests__/compare_orte_status_412_nochmal_speichern.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { extractMessage, type SaveStatus } from '../../../stores/saveStatusStore.svelte.ts';
import { umgebungFuer, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import { createController } from '../../shared/__tests__/versandVergleichPruefstand.ts';
import {
	createGoMergeServer,
	vollerVergleich,
	type GoMergeServer
} from '../../shared/__tests__/goMergeServerPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const HUB = join(HIER, '..', 'CompareTabs.svelte');

register(
	pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const ID = 'cp-1433-orte-status-412';
const PFAD = `/api/compare/presets/${ID}`;

let server: GoMergeServer;

beforeEach(async () => {
	clearEtagRegistry();
	server = createGoMergeServer({ [ID]: vollerVergleich(ID) });
	server.install();
	await api.get(PFAD); // Seitenaufbau: Stempel dieses Standes
});
afterEach(() => server.restore());

async function hub(
	preset: Record<string, unknown> = vollerVergleich(ID)
): Promise<{ u: Knoten; ctl: SaveStatus; schedules: string[] }> {
	const ctl = createController(ID);
	const schedules: string[] = [];
	const { u } = await umgebungFuer(HUB, {
		preset,
		locations: [],
		saveController: ctl,
		// `.svelte`-Importpfade bindet der Pruefstand nicht — der echte Helfer wird gesaet.
		extractMessage,
		onScheduleChange: (s: string) => schedules.push(s)
	});
	assert.equal(typeof u.persistPickedIds, 'function', 'Messaufbau: persistPickedIds nicht herleitbar');
	assert.equal(typeof u.handleToggleActive, 'function', 'Messaufbau: handleToggleActive nicht herleitbar');
	assert.equal(u.api, api, 'Messaufbau: der Hub muss das echte `api` benutzen');
	return { u, ctl, schedules };
}

const puts = () => server.mitschnitt.filter((e) => e.method === 'PUT');
const orteSetzen = (u: Knoten, ids: string[]) => (u.persistPickedIds as (i: string[]) => Promise<void>)(ids);
const toggle = (u: Knoten) => (u.handleToggleActive as () => Promise<boolean>)();

describe('Orte (persistPickedIds): 412 ⇒ „Nochmal speichern", kein Rollback', () => {
	test('412 mit If-Match ⇒ Controller `conflict`, Ortsliste von B bleibt stehen (Falle 1), Server unveraendert', async () => {
		server.fremdSchreiben(ID, { name: 'Name von A' });
		const { u, ctl } = await hub();
		const stand0 = JSON.stringify(server.stand(ID));

		await orteSetzen(u, ['loc-a', 'loc-c']);

		assert.equal(puts().length, 1);
		assert.ok(puts()[0].ifMatch, 'AC-18: If-Match');
		assert.equal(puts()[0].status, 412, 'Vorbedingung');
		assert.equal(ctl.state, 'conflict', '„Nochmal speichern" muss erscheinen — sonst Sackgasse');
		assert.deepEqual(u.currentLocationIds, ['loc-a', 'loc-c'], 'Falle 1: bei 412 KEIN Rollback — B sieht, was der Retry sendet');
		assert.equal(JSON.stringify(server.stand(ID)), stand0);
	});

	test('„Nochmal speichern" ⇒ Name von A UND Ortsliste von B auf dem Server, Nutzlast exakt { location_ids }', async () => {
		server.fremdSchreiben(ID, { name: 'Name von A' });
		const { u, ctl } = await hub();
		await orteSetzen(u, ['loc-a', 'loc-c']);
		assert.equal(ctl.state, 'conflict', 'Vorbedingung');

		await ctl.retryConflict();

		const retry = puts().at(-1)!;
		assert.equal(retry.status, 200);
		assert.deepEqual(retry.anfrage, { location_ids: ['loc-a', 'loc-c'] });
		const s = server.stand(ID);
		assert.equal(s.name, 'Name von A', 'die Fremdaenderung bleibt');
		assert.deepEqual(s.location_ids, ['loc-a', 'loc-c']);
		assert.equal(ctl.state, 'idle');
		assert.deepEqual(u.currentLocationIds, ['loc-a', 'loc-c']);
	});

	test('Gegenprobe: ein anderer Fehler (500) rollt die Ortsliste weiter zurueck und zeigt `error`', async () => {
		const { u, ctl } = await hub();
		const vorher = globalThis.fetch;
		globalThis.fetch = (async () =>
			new Response(JSON.stringify({ error: 'kaputt' }), { status: 500, headers: { 'Content-Type': 'application/json' } })) as typeof fetch;
		try {
			await orteSetzen(u, ['loc-a']);
		} finally {
			globalThis.fetch = vorher;
		}
		assert.deepEqual(u.currentLocationIds, ['loc-a', 'loc-b', 'loc-c'], 'Rollback bei Nicht-412 wie bisher');
		assert.equal(ctl.state, 'error');
	});

	test('F805: offener Orte-Konflikt + naechste Orte-Aenderung scheitert mit 500 ⇒ Anzeige == das, was „Nochmal speichern" sendet', async () => {
		server.fremdSchreiben(ID, { name: 'Name von A' });
		const { u, ctl } = await hub();
		await orteSetzen(u, ['loc-a', 'loc-c']);
		assert.equal(ctl.state, 'conflict', 'Vorbedingung');

		const vorher = globalThis.fetch;
		globalThis.fetch = (async () =>
			new Response(JSON.stringify({ error: 'kaputt' }), { status: 500, headers: { 'Content-Type': 'application/json' } })) as typeof fetch;
		try {
			await orteSetzen(u, ['loc-b']);
		} finally {
			globalThis.fetch = vorher;
		}
		assert.equal(ctl.state, 'conflict', 'der offene Konflikt bleibt');
		const angezeigt = [...(u.currentLocationIds as string[])];

		await ctl.retryConflict();

		const retry = puts().at(-1)!;
		assert.equal(retry.status, 200);
		assert.deepEqual(retry.anfrage, { location_ids: angezeigt }, 'der Retry sendet, was B vorher sah');
		assert.deepEqual(angezeigt, ['loc-a', 'loc-c'], 'Rollback auf die ausstehende Eingabe, nicht auf den letzten Serverstand');
		assert.deepEqual(server.stand(ID).location_ids, angezeigt);
		assert.deepEqual(u.currentLocationIds, angezeigt);
		assert.equal(ctl.state, 'idle');
	});
});

describe('Pausieren/Aktivieren (handleToggleActive): 412 ⇒ „Nochmal speichern"', () => {
	test('412 ⇒ Controller `conflict`, kein Fehlschlag fuer den Kebab (Falle 4), Server unveraendert', async () => {
		server.fremdSchreiben(ID, { name: 'Name von A' });
		const { u, ctl } = await hub();
		const stand0 = JSON.stringify(server.stand(ID));

		const ok = await toggle(u);

		assert.equal(puts().at(-1)!.status, 412, 'Vorbedingung');
		assert.ok(puts().at(-1)!.ifMatch, 'AC-18: If-Match');
		assert.equal(ctl.state, 'conflict', '„Nochmal speichern" muss erscheinen');
		assert.equal(ok, true, 'die Konfliktanzeige uebernimmt — der Kebab darf keinen eigenen Fehlertext zeigen');
		assert.equal(JSON.stringify(server.stand(ID)), stand0);
	});

	test('„Nochmal speichern" ⇒ Name von A bleibt, schedule "manual", Nutzlast nur { schedule, previous_schedule }', async () => {
		server.fremdSchreiben(ID, { name: 'Name von A' });
		const { u, ctl, schedules } = await hub();
		await toggle(u);
		assert.equal(ctl.state, 'conflict', 'Vorbedingung');

		await ctl.retryConflict();

		const retry = puts().at(-1)!;
		assert.equal(retry.status, 200);
		assert.deepEqual(Object.keys(retry.anfrage as object).sort(), ['previous_schedule', 'schedule']);
		const s = server.stand(ID);
		assert.equal(s.name, 'Name von A');
		assert.equal(s.schedule, 'manual');
		assert.equal(s.previous_schedule, 'daily');
		assert.equal(ctl.state, 'idle');
		assert.equal(u.localSchedule, 'manual', 'die Aktivierungs-Karte zeigt nach dem Retry den gespeicherten Status');
		assert.deepEqual(schedules, ['manual'], 'die Kopf-Pille zieht mit (onScheduleChange)');
	});

	test('Falle 2: Fremdgeraet hat den Zeitplan auf "weekly" gesetzt ⇒ der Retry merkt sich "weekly", nicht den veralteten Zeitplan', async () => {
		server.fremdSchreiben(ID, { name: 'Name von A', schedule: 'weekly', previous_schedule: 'weekly' });
		const { u, ctl } = await hub(); // B haelt noch "daily"
		await toggle(u);
		assert.equal(ctl.state, 'conflict', 'Vorbedingung');

		await ctl.retryConflict();

		const s = server.stand(ID);
		assert.equal(s.schedule, 'manual');
		assert.equal(s.previous_schedule, 'weekly', 'ein spaeteres Aktivieren muss den AKTUELLEN Zeitplan wiederherstellen');
		assert.equal(s.name, 'Name von A');
	});

	test('Falle 2: Fremdgeraet hat schon pausiert ⇒ der Retry ueberschreibt dessen `previous_schedule` nicht', async () => {
		server.fremdSchreiben(ID, { schedule: 'manual', previous_schedule: 'weekly' });
		const { u, ctl } = await hub(); // B haelt noch "daily" (aktiv) und pausiert
		await toggle(u);
		assert.equal(ctl.state, 'conflict', 'Vorbedingung');

		await ctl.retryConflict();

		const s = server.stand(ID);
		assert.equal(s.schedule, 'manual');
		assert.equal(s.previous_schedule, 'weekly', 'der gemerkte Zeitplan des Fremdgeraets bleibt');
		assert.equal(ctl.state, 'idle');
	});

	test('F801 Falle 2 (Aktivieren): Fremdgeraet hat mit "weekly" aktiviert ⇒ der Retry behaelt "weekly", nicht den lokal gemerkten "daily"', async () => {
		// Ausgang: pausiert, gemerkter Zeitplan "daily"; B laedt diesen Stand (Stempel + Prop).
		server.fremdSchreiben(ID, { schedule: 'manual', previous_schedule: 'daily' });
		await api.get(PFAD);
		const { u, ctl, schedules } = await hub({ ...vollerVergleich(ID), schedule: 'manual', previous_schedule: 'daily' });
		// Fremdgeraet aktiviert mit "weekly" — NUR `schedule`: der Server-`previous_schedule`
		// bleibt "daily" (sonst waere die Mutation „`aktiv ??` entfernt" aequivalent).
		server.fremdSchreiben(ID, { schedule: 'weekly' });
		assert.equal(server.stand(ID).previous_schedule, 'daily', 'Messaufbau');

		await toggle(u); // B sieht „pausiert" und aktiviert
		assert.equal(puts().at(-1)!.status, 412, 'Vorbedingung');
		assert.equal(ctl.state, 'conflict', 'Vorbedingung');

		await ctl.retryConflict();

		const retry = puts().at(-1)!;
		assert.equal(retry.status, 200);
		assert.deepEqual(Object.keys(retry.anfrage as object).sort(), ['previous_schedule', 'schedule'], 'nur Eigenfelder');
		assert.equal(server.stand(ID).schedule, 'weekly', 'der laufende Zeitplan des Fremdgeraets gewinnt');
		assert.equal(server.stand(ID).name, 'X');
		assert.equal(ctl.state, 'idle');
		assert.equal(u.localSchedule, 'weekly');
		assert.deepEqual(schedules, ['weekly']);
	});

	test('Falle 3: offener Konflikt (Orte) + Pausieren ⇒ Anzeige bleibt `conflict`, EIN Retry schreibt beide', async () => {
		server.fremdSchreiben(ID, { name: 'Name von A' });
		const { u, ctl } = await hub();
		await orteSetzen(u, ['loc-b']);
		assert.equal(ctl.state, 'conflict', 'Vorbedingung');

		await toggle(u);
		assert.equal(ctl.state, 'conflict', 'setSaving()/flush() duerfen den offenen Konflikt nicht beenden (Spec §4.2/§4.5)');
		assert.equal(puts().at(-1)!.ifMatch, puts()[0].ifMatch, 'AC-18: auch das Pausieren traegt das ALTE If-Match');

		await ctl.retryConflict();

		const s = server.stand(ID);
		assert.deepEqual(s.location_ids, ['loc-b']);
		assert.equal(s.schedule, 'manual');
		assert.equal(s.name, 'Name von A');
		assert.equal(ctl.state, 'idle');
	});

	test('Gegenprobe ohne Fremdschreiber: Pausieren speichert sofort, Nutzlast { schedule, previous_schedule }', async () => {
		const { u, ctl } = await hub();
		const ok = await toggle(u);
		assert.equal(ok, true);
		assert.equal(puts().length, 1);
		assert.equal(puts()[0].status, 200);
		assert.deepEqual(puts()[0].anfrage, { schedule: 'manual', previous_schedule: 'daily' });
		assert.equal(ctl.state, 'idle');
	});
});
