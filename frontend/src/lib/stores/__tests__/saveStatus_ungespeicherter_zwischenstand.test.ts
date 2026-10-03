// TDD RED — Issue #2215: ein offener, nicht speicherbarer Zwischenstand darf
// nach dem Ablauf eines vorgemerkten Saves nie „Gespeichert" melden.
//
// Spec: docs/specs/modules/fix_2215_unsaved_input_marker.md (AC-1 … AC-8,
// Kerntests 1–8). Neue Methode `setUnsavedInput()` existiert noch NICHT → RED.
//
// Geprüft wird die ANZEIGE (`state`, `savedAt`) NACH Timer-Ablauf bzw. nach
// Auflösung des Requests — dort, wo die Zusicherung wirkt. Echte Methoden der
// echten Klasse (`Object.create(SaveStatus.prototype)`, Begründung im Kopf von
// saveStatus.test.ts), kein Mock des Prüflings.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/stores/__tests__/saveStatus_ungespeicherter_zwischenstand.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { SaveStatus } from '../saveStatusStore.svelte.ts';
import { api } from '../../api.ts';
import { clearEtagRegistry } from '../../etagRegistry.ts';
import { createFakeTripServer } from '../../__tests__/fakeTripServer.ts';

function neu(): SaveStatus {
	const inst = Object.create(SaveStatus.prototype) as SaveStatus;
	const f = inst as unknown as Record<string, unknown>;
	f.state = 'idle';
	f.savedAt = null;
	f.error = null;
	f._timer = null;
	f._pendingFn = null;
	f._inflight = null;
	f._unresolvedError = null;
	return inst;
}

/** Zugriff auf die noch nicht existierende Methode, ohne dass die Datei schon
 *  beim Typcheck stirbt — der Aufruf selbst scheitert in RED mit TypeError. */
function setUnsavedInput(c: SaveStatus): void {
	(c as unknown as { setUnsavedInput: () => void }).setUnsavedInput();
}

const warte = (ms: number) => new Promise((r) => setTimeout(r, ms));

describe('#2215 Kerntest 1 (AC-1, AC-2): vorgemerkter Save läuft, Anzeige bleibt „Nicht gespeichert"', () => {
	test('schedule → setUnsavedInput → Timer läuft ab: fn genau einmal gerufen, state dirty, savedAt unverändert', async () => {
		const c = neu();
		let calls = 0;
		c.schedule(async () => {
			calls++;
		}, 20);
		setUnsavedInput(c);
		assert.equal(c.state, 'dirty');
		await warte(80);
		assert.equal(calls, 1, 'der zuletzt gültige Stand muss trotzdem geschrieben werden (kein stilles Verwerfen)');
		assert.equal(c.state, 'dirty', 'die Anzeige darf nach dem PUT nicht „Gespeichert" sagen, solange der Zwischenstand offen ist');
		assert.equal(c.savedAt, null, 'kein frischer „Gespeichert HH:MM"-Zeitstempel');
	});
});

describe('#2215 Kerntest 2 (AC-3): Request im Netz', () => {
	test('doSave läuft, setUnsavedInput kommt dazwischen, Request endet: state dirty, kein savedAt', async () => {
		const c = neu();
		let lose!: () => void;
		const offen = new Promise<void>((r) => (lose = r));
		const lauf = c.doSave(async () => {
			await offen;
		});
		setUnsavedInput(c);
		lose();
		await lauf;
		assert.equal(c.state, 'dirty');
		assert.equal(c.savedAt, null);
	});
});

describe('#2215 Kerntest 3 (AC-4): flush()-Weg', () => {
	test('schedule → setUnsavedInput → flush: state bleibt dirty', async () => {
		const c = neu();
		let calls = 0;
		c.schedule(async () => {
			calls++;
		}, 10_000);
		setUnsavedInput(c);
		await c.flush();
		assert.equal(calls, 1);
		assert.equal(c.state, 'dirty');
		assert.equal(c.savedAt, null);
	});
});

describe('#2215 Kerntest 4+5 (AC-5): Zwischenstand-Merkmal wird wieder gelöscht', () => {
	test('neue gültige Eingabe (schedule) überholt den Zwischenstand: danach idle + savedAt', async () => {
		const c = neu();
		setUnsavedInput(c);
		c.schedule(async () => undefined, 10);
		await warte(60);
		assert.equal(c.state, 'idle');
		assert.notEqual(c.savedAt, null);
	});

	test('cancel() löscht das Merkmal: nachfolgendes doSave → idle', async () => {
		const c = neu();
		c.schedule(async () => undefined, 10_000);
		setUnsavedInput(c);
		c.cancel();
		await c.doSave(async () => undefined);
		assert.equal(c.state, 'idle');
		assert.notEqual(c.savedAt, null);
	});

	test('markPristine() löscht das Merkmal: nachfolgendes doSave → idle', async () => {
		const c = neu();
		setUnsavedInput(c);
		c.markPristine();
		assert.equal(c.state, 'idle');
		await c.doSave(async () => undefined);
		assert.equal(c.state, 'idle');
		assert.notEqual(c.savedAt, null);
	});
});

describe('#2215 Kerntest 6 (AC-6): Altverhalten von setDirty()/defer() bleibt', () => {
	test('schedule → setDirty → Timer läuft ab: Anzeige „Gespeichert" (idle)', async () => {
		const c = neu();
		c.schedule(async () => undefined, 10);
		c.setDirty();
		await warte(60);
		assert.equal(c.state, 'idle', 'EditStagesPanelNew-Bedeutung: vorgemerkter Save meldet danach „Gespeichert"');
		assert.notEqual(c.savedAt, null);
	});

	test('defer + flush → idle', async () => {
		const c = neu();
		c.defer(async () => undefined);
		assert.equal(c.state, 'dirty');
		await c.flush();
		assert.equal(c.state, 'idle');
	});
});

describe('#2215 Kerntest 7 (AC-7): Konflikt ist sticky', () => {
	test('setUnsavedInput bei Konflikt ändert nichts; nach retryConflict + Erfolg → idle (Merkmal wurde nie gesetzt)', async () => {
		// retryConflict() macht einen echten GET — Ersatz-Server wie in saveStatusConflictRetry.test.ts.
		clearEtagRegistry();
		const server = createFakeTripServer({ latencyMs: 0 });
		server.install();
		try {
			await runKerntest7(server);
		} finally {
			server.restore();
		}
	});
});

async function runKerntest7(server: ReturnType<typeof createFakeTripServer>): Promise<void> {
	{
		const c = neu();
		const f = c as unknown as Record<string, unknown>;
		f._tripId = 'gr20';
		f._resourceKind = 'trip';
		f._lastFailed = null;
		// Echter 412: jemand schreibt vorbei an der Registry.
		await api.get('/api/trips/gr20');
		await server.handler('/api/trips/gr20', {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ name: 'fremd' })
		});
		await c.doSave(() => api.put('/api/trips/gr20', { name: 'lokal' }).then(() => undefined));
		assert.equal(c.state, 'conflict', 'Vorbedingung');
		setUnsavedInput(c);
		assert.equal(c.state, 'conflict');
		await c.retryConflict();
		assert.equal(c.state, 'idle', 'ein bei Konflikt ignoriertes setUnsavedInput darf kein Merkmal hinterlassen');
	}
}

describe('#2215 Kerntest 8 (AC-8): Fehler bei offenem Zwischenstand', () => {
	test('gescheiterter PUT → error; späterer Erfolg bei offenem Zwischenstand → dirty; PUT-Erfolg löscht _unresolvedError', async () => {
		const c = neu();
		setUnsavedInput(c);
		await c.doSave(async () => {
			throw new Error('boom');
		});
		assert.equal(c.state, 'error');
		await c.doSave(async () => undefined);
		assert.equal(c.state, 'dirty', 'weiter offener Zwischenstand: nicht „Gespeichert"');
		assert.equal(c.savedAt, null);
		c.markPristine();
		assert.equal(c.state, 'idle', 'der echte Erfolg hat den offenen Fehlschlag gelöscht → kein error mehr');
	});
});
