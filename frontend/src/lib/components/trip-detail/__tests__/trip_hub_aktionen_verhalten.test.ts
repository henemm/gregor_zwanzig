// Fix-Loop 1/2 — Issue #2278, F001/F003/F006/F008/F017/F020 am Trip-Hub als echtes VERHALTEN: der ECHTE
// Instanz-Code von routes/trips/[id]/+page.svelte (Pruefstand `tripSeite`) laeuft gegen den Ersatz-Server,
// gemessen werden die Requests. Ergaenzt die Bindungs-Tests (aktionsmodell_seiten_bindung.test.ts) um die Wirkung.
// Gewartet wird auf BEDINGUNGEN (Request angekommen, Handler fertig), nie auf feste Zeiten (F020).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/__tests__/trip_hub_aktionen_verhalten.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import * as P from './tripMehrreiterPruefstand.ts';

let server: FakeTripServer;
beforeEach(async () => {
	clearEtagRegistry();
	server = createFakeTripServer({ merge: true });
	server.install();
	server.seed(P.TRIP_ID, P.vollerTrip());
	await api.get(P.TRIP_PFAD);
});
afterEach(() => server.restore());

const nach = (m: string, teil: string) => server.calls.filter((c) => c.method === m && c.path.includes(teil));

/** Wartet (max. 5 s) auf eine Bedingung; scheitert LAUT mit Beschreibung statt still durchzulaufen. */
async function bis(bedingung: () => boolean, was: string): Promise<void> {
	const ende = Date.now() + 5000;
	while (!bedingung()) {
		if (Date.now() > ende) assert.fail(`Zeitueberschreitung beim Warten auf: ${was}`);
		await new Promise((r) => setTimeout(r, 5));
	}
}
/** Alle bisher gestarteten Anfragen sind beantwortet und der Hub arbeitet nicht mehr. */
const ruhig = (u: Record<string, any>) => () =>
	u.isLoading !== true && server.calls.every((c) => !Number.isNaN(c.finishedAt));
/**
 * Abwesenheitspruefung (F024): erst auf RUHE warten (alle Anfragen beantwortet), dann einen Zeitpuffer
 * lassen, in dem auch verzoegert angestossene Handler (setTimeout) ihren Request absetzen wuerden.
 * Erst danach darf „es wurde nichts gesendet/geloescht" behauptet werden.
 */
const tick = async (u?: Record<string, any>) => {
	for (let i = 0; i < 10; i++) await Promise.resolve();
	await new Promise((r) => setTimeout(r, 120));
	await bis(() => (u ? ruhig(u)() : server.calls.every((c) => !Number.isNaN(c.finishedAt))), 'Ruhe nach der Aktion');
};

async function seite() {
	const a = P.neuerAufbau();
	const s = await P.tripSeite(a, server);
	server.calls.length = 0;
	const u = s.inst.u as Record<string, any>;
	u.sendTimer = undefined; // `let sendTimer;` ohne Initialisierer legt die Umgebung nicht an
	const gotos: string[] = [];
	u.goto = (pfad: string) => void gotos.push(pfad); // $app/navigation ist unter node nicht ladbar
	return { a, u, gotos, aktion: (id: string) => u.handleHubAction(id) };
}

describe('F006: Pausieren/Fortsetzen schreiben den richtigen Zielzustand', () => {
	test('"pause" -> PATCH /state {paused:true}; "resume" -> {paused:false}', async () => {
		const { aktion, a, u } = await seite();
		aktion('pause');
		await bis(() => nach('PATCH', '/state').length === 1 && ruhig(u)(), 'PATCH nach "pause"');
		aktion('resume');
		await bis(() => nach('PATCH', '/state').length === 2 && ruhig(u)(), 'PATCH nach "resume"');
		a.ctl.cancel();
		assert.deepEqual(
			nach('PATCH', '/state').map((c) => c.anfrage),
			[{ paused: true }, { paused: false }]
		);
	});
});

describe('F008: Loeschen und Archivieren fragen erst zurueck', () => {
	test('"delete" oeffnet nur den Dialog; erst die Bestaetigung loescht (DELETE auf den Trip)', async () => {
		const { aktion, u, gotos } = await seite();
		aktion('delete');
		await tick(u);
		assert.equal(u.deleteDialogOpen, true);
		assert.equal(nach('DELETE', P.TRIP_PFAD).length, 0, 'DELETE ohne Rueckfrage');
		assert.deepEqual(gotos, []);
		await u.handleDeleteConfirm();
		assert.equal(nach('DELETE', P.TRIP_PFAD).length, 1);
		assert.equal(u.deleteDialogOpen, false);
		assert.deepEqual(gotos, ['/trips'], 'nach dem Loeschen landet der Nutzer in der Trip-Liste');
	});

	test('"archive" oeffnet nur den Dialog; erst die Bestaetigung schreibt {archived:true}', async () => {
		const { aktion, u, a } = await seite();
		aktion('archive');
		await tick(u);
		assert.equal(u.archiveDialogOpen, true);
		assert.equal(nach('PATCH', '/state').length, 0, 'Archivieren ohne Rueckfrage');
		u.handleArchiveConfirm();
		await bis(() => nach('PATCH', '/state').length === 1 && ruhig(u)(), 'PATCH nach Archiv-Bestaetigung');
		a.ctl.cancel();
		assert.deepEqual(nach('PATCH', '/state').map((c) => c.anfrage), [{ archived: true }]);
	});
});

describe('F001/F017: Senden erst nach Bestaetigung, mit der gewaehlten Berichtsart', () => {
	test('Aktion "send" im Hub-Dispatch loest keinen Versand aus', async () => {
		const { aktion, u } = await seite();
		aktion('send');
		await tick(u);
		assert.equal(nach('POST', '/send').length, 0);
	});

	test('handleSendConfirm("evening") -> genau ein POST /send?report_type=evening, Erfolg wird gemeldet', async () => {
		const { u } = await seite();
		u.sendDialogOpen = true;
		await u.handleSendConfirm('evening');
		clearTimeout(u.sendTimer);
		const posts = nach('POST', '/send');
		assert.equal(posts.length, 1);
		assert.match(posts[0].path, /report_type=evening/);
		assert.equal(u.sendStatus, 'ok');
		assert.equal(u.sendDialogOpen, false);
	});

	test('handleSendConfirm() ohne Wahl sendet den Morgen-Bericht', async () => {
		const { u } = await seite();
		await u.handleSendConfirm();
		clearTimeout(u.sendTimer);
		const posts = nach('POST', '/send');
		assert.equal(posts.length, 1);
		assert.match(posts[0].path, /report_type=morning/);
	});
});
