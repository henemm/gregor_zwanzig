// TDD RED — Issue #1743, Speicher-Slot (Spec docs/specs/modules/feat_1743_reiter_aufraeumen.md,
// Abschnitt 5, AC-12 und Kern von AC-15).
//
// Der Controller hat heute EINEN Platz fuer einen geplanten Speichervorgang. Seit
// Wetter-Metriken und Versand in einem Reiter stehen, teilen sich zwei Schreiber
// diesen Platz: der zweite verdraengt den ersten lautlos (Datenverlust). Die
// Schnittstelle (docs/artifacts/feat-1743-reiter-aufraeumen/red-schnittstellen.md):
//   schedule(fn, ms, owner) — fremder Besitzer mit belegtem Platz ⇒ dessen Funktion
//                             wird ZUERST gesendet, dann der neue Platz gesetzt;
//                             gleicher Besitzer ⇒ ersetzt (Entprellung) wie bisher.
//   cancel(owner)           — verwirft nur den Platz dieses Besitzers.
//
// Instanz ohne Konstruktor (Runen-Felder, s. saveStatus.test.ts) ueber den
// bestehenden Helfer `createController`. Es werden bewusst KEINE neuen internen
// Felder vorbelegt — die Umsetzung muss fehlende Felder als leer lesen (wie
// `_lastFailed`), sonst bindet der Test die interne Form.
//
// Fake-Timer nur fuer `setTimeout` (node:test `mock.timers`). Geprueft wird erst
// nach dem Abarbeiten — ob die Umsetzung den fremden Platz synchron oder per
// Microtask anstoesst, entscheidet den Test nicht.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/stores/__tests__/saveStatusStoreBesitzer.test.ts

import { test, describe, beforeEach, afterEach, mock } from 'node:test';
import assert from 'node:assert/strict';

import type { SaveFn, SaveStatus } from '../saveStatusStore.svelte.ts';
import { createController } from '../../components/shared/__tests__/versandVergleichPruefstand.ts';

type Planen = (fn: SaveFn, ms?: number, owner?: string) => void;
type Verwerfen = (owner?: string) => void;

const planen = (ctl: SaveStatus, fn: SaveFn, owner: string): void =>
	(ctl.schedule as unknown as Planen).call(ctl, fn, 700, owner);
const verwerfen = (ctl: SaveStatus, owner: string): void =>
	(ctl.cancel as unknown as Verwerfen).call(ctl, owner);

/** Microtasks abarbeiten (Fake-Timer betreffen nur setTimeout). */
async function microtasks(n = 20): Promise<void> {
	for (let i = 0; i < n; i++) await Promise.resolve();
}

/** Alles abarbeiten: Entprell-Timer vorspulen, laufende Speicherungen abwarten. */
async function abarbeiten(ctl: SaveStatus): Promise<void> {
	for (let i = 0; i < 5; i++) {
		mock.timers.tick(700);
		await microtasks();
		const laufend = ctl.laufendeSpeicherung;
		if (laufend) await laufend;
		await microtasks();
	}
}

/** Speicherfunktion, die ihren Aufruf protokolliert (optional scheiternd, kein 412). */
function schreiber(name: string, log: string[], scheitert = false): SaveFn {
	return async () => {
		log.push(name);
		if (scheitert) throw { status: 500, error: `${name} kaputt` };
	};
}

beforeEach(() => mock.timers.enable({ apis: ['setTimeout'] }));
afterEach(() => mock.timers.reset());

describe('AC-12: zwei Besitzer — kein Schreiber verdraengt den anderen', () => {
	test('schedule(A) dann schedule(B) binnen 700 ms ⇒ A wird gesendet (nicht verworfen), danach B', async () => {
		const ctl = createController('t-1743');
		const log: string[] = [];
		planen(ctl, schreiber('A', log), 'A');
		planen(ctl, schreiber('B', log), 'B');
		await abarbeiten(ctl);
		assert.deepEqual(log, ['A', 'B'], `fremder Platz muss zuerst gesendet werden, gesendet: ${JSON.stringify(log)}`);
		assert.equal(ctl.hasPending, false);
	});

	test('cancel(A) verwirft nur A — ein wartender Platz von B wird weiterhin gesendet', async () => {
		const ctl = createController('t-1743');
		const log: string[] = [];
		planen(ctl, schreiber('B', log), 'B');
		verwerfen(ctl, 'A');
		await abarbeiten(ctl);
		assert.deepEqual(log, ['B'], 'cancel(A) hat den Platz von B verworfen');
	});

	test('cancel(A) mit eigenem wartendem Platz ⇒ A wird nicht gesendet', async () => {
		const ctl = createController('t-1743');
		const log: string[] = [];
		planen(ctl, schreiber('A', log), 'A');
		verwerfen(ctl, 'A');
		await abarbeiten(ctl);
		assert.deepEqual(log, [], 'der eigene Platz muss verworfen werden');
	});

	test('A, dann B (A wird dabei gesendet), dann cancel(A) ⇒ B wird trotzdem gesendet, A genau einmal', async () => {
		const ctl = createController('t-1743');
		const log: string[] = [];
		planen(ctl, schreiber('A', log), 'A');
		planen(ctl, schreiber('B', log), 'B');
		verwerfen(ctl, 'A');
		await abarbeiten(ctl);
		assert.deepEqual(log, ['A', 'B']);
	});

	test('gleicher Besitzer ersetzt weiterhin (Entprellung): nur die zweite Funktion wird gesendet', async () => {
		const ctl = createController('t-1743');
		const log: string[] = [];
		planen(ctl, schreiber('A1', log), 'A');
		planen(ctl, schreiber('A2', log), 'A');
		await abarbeiten(ctl);
		assert.deepEqual(log, ['A2'], 'Entprellung innerhalb eines Besitzers muss erhalten bleiben');
	});
});

describe('AC-15 (Kern am Store): eine Anzeige fuer zwei Schreiber', () => {
	test('A erfolgreich gesendet, B wartet noch ⇒ Anzeige zeigt NICHT „Gespeichert"', async () => {
		const ctl = createController('t-1743');
		const log: string[] = [];
		planen(ctl, schreiber('A', log), 'A');
		planen(ctl, schreiber('B', log), 'B');
		// nur Microtasks — der Entprell-Timer von B ist noch nicht abgelaufen
		await microtasks();
		const laufend = ctl.laufendeSpeicherung;
		if (laufend) await laufend;
		await microtasks();
		assert.deepEqual(log, ['A'], 'Messaufbau: A muss bereits gesendet sein, B noch nicht');
		assert.notEqual(ctl.state, 'idle', '„Gespeichert", obwohl B noch aussteht');
		assert.equal(ctl.hasPending, true, 'B muss weiterhin ausstehen');
		await abarbeiten(ctl);
		assert.equal(ctl.state, 'idle', 'nach beiden Erfolgen: „Gespeichert"');
		assert.ok(ctl.savedAt instanceof Date);
	});

	test('A scheitert (500), B erfolgreich ⇒ Anzeige „Fehler" statt „Gespeichert"', async () => {
		const ctl = createController('t-1743');
		const log: string[] = [];
		planen(ctl, schreiber('A', log, true), 'A');
		planen(ctl, schreiber('B', log), 'B');
		await abarbeiten(ctl);
		assert.deepEqual(log, ['A', 'B'], `beide Schreiber muessen gesendet werden, gesendet: ${JSON.stringify(log)}`);
		assert.equal(ctl.state, 'error', 'der Fehlschlag von A wurde vom Erfolg von B ueberdeckt');
		assert.equal(ctl.savedAt, null, 'kein „Gespeichert HH:MM", solange ein Schreiber gescheitert ist');
	});

	test('A erfolgreich, B scheitert (500) ⇒ Anzeige „Fehler"', async () => {
		const ctl = createController('t-1743');
		const log: string[] = [];
		planen(ctl, schreiber('A', log), 'A');
		planen(ctl, schreiber('B', log, true), 'B');
		await abarbeiten(ctl);
		assert.deepEqual(log, ['A', 'B']);
		assert.equal(ctl.state, 'error');
	});
});
