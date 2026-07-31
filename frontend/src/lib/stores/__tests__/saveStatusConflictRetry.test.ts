// TDD RED — Issue #1395 Scheibe S4: "Nochmal speichern" bei ETag-Konflikt.
// Spec: docs/specs/modules/issue_1395_s4_conflict_retry.md
//   § Implementation Details, § Acceptance Criteria AC-1..AC-6
// Kontext: docs/context/fix-1395-s4-nochmal-speichern.md
//
// `SaveState` bekommt einen neuen Wert `'conflict'`, `SaveStatus` einen
// optionalen `tripId`-Konstruktorparameter, ein `_lastFailed`-Feld und eine
// Methode `retryConflict()` — nichts davon existiert bisher auf
// `SaveStatus.prototype`. Diese Tests treiben den GREEN-Vertrag.
//
// Warum `Object.create(SaveStatus.prototype)` statt `new SaveStatus(...)`:
// s. Kommentarblock in `saveStatus.test.ts` (Svelte-5-Runen-Feldinitializer
// werfen außerhalb des Compiler-Kontexts sofort `$state is not defined`).
// Reine Verhaltenstests auf der echten Klasse, kein Mock.
//
// Für `retryConflict()`-Tests mit echtem Netz-Ablauf (Refresh-Reihenfolge,
// Re-Konflikt) läuft `frontend/src/lib/api.ts` gegen denselben
// Ersatz-Server (`fakeTripServer.ts`) wie die S3-Tests — kein Mock im
// verbotenen Sinn, sondern ein Nachbau des S2-Server-Vertrags.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/stores/__tests__/saveStatusConflictRetry.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { SaveStatus } from '../saveStatusStore.svelte.ts';
import { api } from '../../api.ts';
import { clearEtagRegistry } from '../../etagRegistry.ts';
import { createFakeTripServer, PRECONDITION_FAILED_DETAIL, type FakeTripServer } from '../../__tests__/fakeTripServer.ts';
import type { ApiError } from '../../types.ts';

let server: FakeTripServer;

function boot(latencyMs: number | ((method: string, path: string) => number) = 0) {
	if (server) server.restore();
	server = createFakeTripServer({ latencyMs });
	server.install();
}

beforeEach(() => {
	clearEtagRegistry();
	boot(0);
});

afterEach(() => server.restore());

/** Instanz OHNE Konstruktor-Aufruf — s. Begründung im Modulkommentar. */
function createTestInstance(tripId?: string): SaveStatus {
	const inst = Object.create(SaveStatus.prototype) as SaveStatus;
	const internals = inst as unknown as Record<string, unknown>;
	internals.state = 'idle';
	internals.savedAt = null;
	internals.error = null;
	internals._timer = null;
	internals._pendingFn = null;
	internals._inflight = null;
	// Issue #1395 S4: neue Konstruktor-Felder, die `new SaveStatus(tripId)`
	// setzen würde.
	internals._tripId = tripId;
	internals._lastFailed = null;
	return inst;
}

const putCalls = () => server.calls.filter((c) => c.method === 'PUT');
const getCalls = () => server.calls.filter((c) => c.method === 'GET');

describe('AC-1 (Vorbedingung): ein 412 mit bekannter tripId wird als Konflikt erkannt, nicht als generischer Fehler', () => {
	test('test_doSave_412WithTripId_entersConflictState_remembersFailedSave', async () => {
		const c = createTestInstance('gr20');
		let calls = 0;
		const failing = async () => {
			calls++;
			const err: ApiError = { error: 'precondition_failed', detail: PRECONDITION_FAILED_DETAIL, status: 412 };
			throw err;
		};

		await c.doSave(failing);

		assert.equal(
			c.state,
			'conflict',
			'ein 412 mit bekannter tripId muss einen eigenen Konflikt-Zustand setzen, nicht den generischen Fehlerzustand'
		);
		assert.equal(c.error, PRECONDITION_FAILED_DETAIL, 'die deutsche Servermeldung muss weiterhin über extractMessage() erscheinen');
		assert.equal(calls, 1, 'Vorbedingung: der Speichervorgang ist genau einmal gescheitert');
	});
});

describe('AC-1: "Nochmal speichern" frischt den ETag zuerst auf und wiederholt danach denselben Speichervorgang', () => {
	test('test_retryConflict_refreshesEtagThenResendsOriginalSaveFn_inOrder', async () => {
		// GIVEN: die Tour ist geladen, dann schreibt jemand anderes vorbei an der
		// Registry (server-seitig neuer Stand, unser Client weiß es noch nicht).
		await api.get('/api/trips/gr20');
		await server.handler('/api/trips/gr20', {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ name: 'fremd' })
		});

		const c = createTestInstance('gr20');
		await c.doSave(() => api.put('/api/trips/gr20', { name: 'lokal' }).then(() => undefined));
		assert.equal(c.state, 'conflict', 'Vorbedingung: der erste Versuch muss mit einem echten 412 scheitern');

		// WHEN: der Nutzer "Nochmal speichern" klickt.
		await c.retryConflict();

		// THEN: es gab einen zweiten GET (den Refresh) UND einen zweiten PUT (den
		// Retry) — in dieser Reihenfolge, belegt über echte Zeitstempel.
		// Der Ersatz-Server protokolliert JEDE Anfrage — auch den oben von Hand
		// abgesetzten fremden Schreibvorgang (puts[0]). Die eigenen Vorgänge
		// dieses Tests sind daher puts[1] (abgelehnt) und puts[2] (Retry).
		const gets = getCalls();
		const puts = putCalls();
		assert.equal(gets.length, 2, 'der Refresh muss einen zusätzlichen GET auslösen (initiales Laden + Refresh)');
		assert.equal(puts.length, 3, 'der Retry muss einen zusätzlichen PUT auslösen (fremd + gescheiterter Versuch + Retry)');
		assert.ok(
			gets[1].startedAt >= puts[1].finishedAt,
			'der Refresh-GET darf erst NACH dem gescheiterten PUT starten'
		);
		assert.ok(
			puts[2].startedAt >= gets[1].finishedAt,
			'der wiederholte PUT darf erst NACH dem Refresh-GET starten — sonst trägt er weiterhin den veralteten Stand'
		);
		assert.notEqual(
			puts[2].ifMatch,
			puts[1].ifMatch,
			'der wiederholte PUT muss den frisch aufgefrischten Stand mitführen, nicht den ursprünglich abgelehnten'
		);
		assert.equal(puts[2].status, 200, 'mit dem frischen Stand muss der wiederholte Speichervorgang gelingen');
	});
});

describe('AC-2: gelingt der Retry, zeigt der Anzeiger wieder "Gespeichert"', () => {
	test('test_retryConflict_successfulRetry_transitionsToIdleWithSavedAt', async () => {
		await api.get('/api/trips/gr20');
		await server.handler('/api/trips/gr20', {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ name: 'fremd' })
		});

		const c = createTestInstance('gr20');
		await c.doSave(() => api.put('/api/trips/gr20', { name: 'lokal' }).then(() => undefined));
		assert.equal(c.state, 'conflict');

		await c.retryConflict();

		assert.equal(c.state, 'idle', 'nach erfolgreichem Retry muss der Anzeiger "Gespeichert" zeigen');
		assert.ok(c.savedAt instanceof Date, 'ein erfolgreicher Retry muss savedAt setzen wie jeder andere Speichervorgang');
	});
});

describe('AC-3: ein weiterer fremder Schreibvorgang zwischen Refresh und Retry darf nicht still überschrieben werden', () => {
	test('test_retryConflict_freshConflictDuringRetry_returnsToConflictState_notSaved', async () => {
		// Verzögerter GET, damit ein fremder Schreibvorgang zwischen "Refresh
		// angekommen" und "Refresh beantwortet" stattfinden kann — derselbe
		// F001-Mechanismus wie in apiTripEtagConflict.test.ts.
		boot((method) => (method === 'GET' ? 60 : 0));

		await api.get('/api/trips/gr20');
		await server.handler('/api/trips/gr20', {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ name: 'fremd 1' })
		});

		const c = createTestInstance('gr20');
		await c.doSave(() => api.put('/api/trips/gr20', { name: 'lokal' }).then(() => undefined));
		assert.equal(c.state, 'conflict', 'Vorbedingung: erster Versuch scheitert');

		// WHEN: der Retry angestoßen wird — der Refresh-GET ist unterwegs
		// (60ms), währenddessen schreibt ein Dritter erneut.
		const retryPromise = c.retryConflict();
		assert.ok(
			getCalls().some((g) => Number.isNaN(g.finishedAt)),
			'Vorbedingung: der Refresh-GET muss bereits beim Server angekommen, aber noch nicht beantwortet sein'
		);
		await server.handler('/api/trips/gr20', {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ name: 'fremd 2' })
		});
		await retryPromise;

		// THEN: der Retry trägt den (durch die verspätete Antwort) bereits
		// wieder veralteten Stand und scheitert erneut — kein stilles
		// Überschreiben von "fremd 2".
		assert.equal(
			c.state,
			'conflict',
			'AC-3: ein zwischenzeitlicher weiterer fremder Schreibvorgang darf den Retry nicht fälschlich als erfolgreich melden'
		);
		assert.equal(
			(server.storedBody('gr20') as { name?: string })?.name,
			'fremd 2',
			'die zwischenzeitliche fremde Änderung darf nicht überschrieben worden sein'
		);
	});
});

describe('AC-4: generische Fehler (kein 412) bekommen keinen Konflikt-Zustand', () => {
	test('test_doSave_genericErrorStatus_setsErrorState_notConflict', async () => {
		const c = createTestInstance('gr20');
		const failing = async () => {
			const err: ApiError = { error: 'validation_failed', status: 400 };
			throw err;
		};

		await c.doSave(failing);

		assert.equal(c.state, 'error', 'ein 400/500 muss weiterhin den generischen Fehlerzustand setzen');
	});
});

describe('Wiedereintritts-Schutz: ein zweiter Klick während eines laufenden Retries darf nichts doppelt auslösen', () => {
	test('test_retryConflict_noOpWhenStateIsNotConflict', async () => {
		const c = createTestInstance('gr20');
		assert.equal(c.state, 'idle');

		await c.retryConflict();

		assert.equal(c.state, 'idle', 'außerhalb des Konflikt-Zustands darf retryConflict() nichts verändern');
		assert.equal(server.calls.length, 0, 'ohne aktiven Konflikt darf retryConflict() keine Netzanfrage auslösen');
	});
});

describe('Refresh selbst schlägt fehl: kein automatischer zweiter Versuch (Known Limitation)', () => {
	test('test_retryConflict_refreshFailure_fallsBackToErrorState_doesNotRetrySave', async () => {
		await api.get('/api/trips/gr20');
		await server.handler('/api/trips/gr20', {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ name: 'fremd' })
		});

		const c = createTestInstance('gr20');
		await c.doSave(() => api.put('/api/trips/gr20', { name: 'lokal' }).then(() => undefined));
		assert.equal(c.state, 'conflict');

		// WHEN: der Refresh selbst am Netz scheitert (echter Fetch-Fehler).
		const realFetch = globalThis.fetch;
		(globalThis as { fetch: unknown }).fetch = () => Promise.reject(new Error('Netz ausgefallen'));
		try {
			await c.retryConflict();
		} finally {
			(globalThis as { fetch: unknown }).fetch = realFetch;
		}

		assert.equal(c.state, 'error', 'ein gescheiterter Refresh muss in den generischen Fehlerzustand fallen');
		assert.equal(
			putCalls().length,
			2,
			'nach gescheitertem Refresh darf KEIN erneuter Speicherversuch beim Server ankommen ' +
				'(protokolliert bleiben nur der fremde Schreibvorgang und der eine abgelehnte Versuch)'
		);
	});
});

describe('AC-6: eine SaveStatus-Instanz ohne tripId verhält sich exakt wie vor dieser Scheibe', () => {
	test('test_createSaveStatus_withoutTripId_412FallsBackToPlainErrorState', async () => {
		const c = createTestInstance(undefined);
		const failing = async () => {
			const err: ApiError = { error: 'precondition_failed', detail: PRECONDITION_FAILED_DETAIL, status: 412 };
			throw err;
		};

		await c.doSave(failing);

		assert.equal(
			c.state,
			'error',
			'ohne bekannte tripId (z.B. heutiger Ortsvergleich-Editor vor S6) darf auch ein 412 nur den generischen Fehlerzustand setzen'
		);
	});

	test('test_retryConflict_withoutTripId_isNoOp', async () => {
		const c = createTestInstance(undefined);
		// Erzwungener Grenzfall: state manuell auf 'conflict' gesetzt (kann ohne
		// tripId über doSave() gar nicht entstehen, s. Test oben) — retryConflict()
		// muss trotzdem defensiv nichts tun.
		(c as unknown as { state: string }).state = 'conflict';

		await c.retryConflict();

		assert.equal(c.state, 'conflict', 'ohne tripId darf retryConflict() den Zustand nicht verändern');
		assert.equal(server.calls.length, 0, 'ohne tripId darf retryConflict() keine Netzanfrage auslösen');
	});
});
