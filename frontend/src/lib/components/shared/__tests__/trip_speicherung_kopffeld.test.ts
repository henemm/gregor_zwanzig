// TDD RED — Issue #2284 Scheibe S2 (Spec v1.1), AC-11: Kopf-Felder (Trip: Name/
// Region/Aktivität, Vergleich: Name/Region/Profil) speichern über den geteilten
// Helper `speichereKopfFeld(fn, ctl)` MIT Chip-Verlauf am Controller des Hubs:
// `saving` während der PUT läuft ⇒ `idle` mit frischem `savedAt` („Gespeichert
// HH:MM") nach Erfolg. 412 ⇒ Eintrag im Konfliktspeicher, Zustand `conflict`
// (sticky, `setSaved` danach ein No-op). Jeder andere Fehler ⇒ Chip zurück auf
// den letzten bekannten Stand (`markPristine`), der Fehler geht an den Aufrufer
// (der Baustein zeigt ihn als `{p}-…-save-error` am Feld).
//
// Spec: docs/specs/modules/feat_2284_s2_trip_kopf.md — AC-11 (Test-Plan:
// `shared/__tests__/trip_speicherung_kopffeld.test.ts`)
//
// Hintergrund (CI-Rot PR #2494): `speichereOderMeldeKonflikt` fasst den Zustand
// bewusst nicht an — der Kopf-Speicherweg rief nie `setSaving`/`setSaved`, der
// Chip blieb in beiden Hubs auf `idle` ohne neuen Zeitstempel.
//
// Echter Controller (`SaveStatus`, Muster `Object.create` wie
// versandVergleichPruefstand.createController), echter `api`-Client gegen den
// fakeTripServer (echte ETag/If-Match-Mechanik ⇒ echter 412). Nur der 500-Fall
// nutzt einen werfenden PutClient (Netzgrenze), weil der Fake keinen 500 kennt.
//
// RED HEUTE: `speichereKopfFeld` ist nicht exportiert. Der Import steckt in
// `helper()`, damit jeder Test einzeln mit eigener Meldung scheitert.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test --test-reporter=spec \
//     src/lib/components/shared/__tests__/trip_speicherung_kopffeld.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import { SaveStatus, type SaveFn } from '../../../stores/saveStatusStore.svelte.ts';
import * as tripSpeicherung from '../tripSpeicherung.ts';
import { baueTripSpeicherung, type PutClient } from '../tripSpeicherung.ts';

const TRIP_ID = 'trip-2284-s2-kopf';
const TRIP_PFAD = `/api/trips/${TRIP_ID}`;

type KopfHelper = (fn: SaveFn, ctl: SaveStatus | null | undefined) => Promise<void>;

function helper(): KopfHelper {
	const h = (tripSpeicherung as Record<string, unknown>).speichereKopfFeld;
	assert.equal(
		typeof h,
		'function',
		'AC-11: tripSpeicherung.ts exportiert keinen geteilten Kopf-Speicherweg `speichereKopfFeld(fn, ctl)`'
	);
	return h as KopfHelper;
}

/** Echte SaveStatus-Instanz ohne Konstruktor (Runen-Feldinitialisierer laufen unter node nicht). */
function controller(): SaveStatus {
	const inst = Object.create(SaveStatus.prototype) as SaveStatus;
	Object.assign(inst as unknown as Record<string, unknown>, {
		state: 'idle',
		savedAt: null,
		error: null,
		_timer: null,
		_pendingFn: null,
		_inflight: null,
		_lastFailed: null,
		_unresolvedError: null,
		_tripId: TRIP_ID,
		_resourceKind: 'trip'
	});
	return inst;
}

/** Client, der den Chip-Zustand im Moment des PUT festhält und dann an `api` weiterreicht. */
function beobachtenderClient(ctl: SaveStatus, zustaende: string[]): PutClient {
	return {
		put: <T>(pfad: string, body: unknown, init?: RequestInit) => {
			zustaende.push(ctl.state);
			return api.put<T>(pfad, body, init);
		}
	};
}

let server: FakeTripServer;

beforeEach(() => {
	clearEtagRegistry();
	server = createFakeTripServer();
	server.install();
});

afterEach(() => server.restore());

describe('#2284 S2 AC-11 — speichereKopfFeld: Chip-Verlauf am Controller des Hubs', () => {
	test('Erfolg: während des PUT „saving", danach „idle" mit frischem savedAt (Gespeichert HH:MM)', async () => {
		const speichere = helper();
		await api.get(TRIP_PFAD); // Seitenstand bekannt (ETag)
		const ctl = controller();
		const zustaende: string[] = [];
		let schlossen = false;
		const fn = baueTripSpeicherung(
			beobachtenderClient(ctl, zustaende),
			TRIP_ID,
			{ region: 'Alpen Nord' },
			() => {
				schlossen = true;
			},
			'kopf-region'
		);
		const vorher = Date.now();

		await speichere(fn, ctl);

		assert.deepEqual(zustaende, ['saving'], 'AC-11: der Chip steht während des PUT nicht auf „saving"');
		assert.equal(ctl.state, 'idle', 'AC-11: nach Erfolg steht der Chip nicht auf idle');
		assert.ok(ctl.savedAt instanceof Date, 'AC-11: kein savedAt ⇒ kein „Gespeichert HH:MM"');
		assert.ok(ctl.savedAt!.getTime() >= vorher, 'AC-11: savedAt ist nicht frisch gestempelt');
		assert.ok(schlossen, 'die Server-Antwort wurde nicht übernommen');
		const put = server.calls.filter((c) => c.method === 'PUT');
		assert.equal(put.length, 1, 'genau ein PUT');
		assert.deepEqual(put[0].anfrage, { region: 'Alpen Nord' }, 'Rumpf nur Eigenfeld');
	});

	test('412: Eintrag im Konfliktspeicher unter dem Kopf-Schlüssel, Zustand conflict, kein „Gespeichert"', async () => {
		const speichere = helper();
		await api.get(TRIP_PFAD);
		// eine andere Sitzung ändert den Trip ⇒ unser If-Match ist veraltet
		await server.handler(TRIP_PFAD, { method: 'PUT', body: JSON.stringify({ name: 'fremd' }) });
		const ctl = controller();
		const fn = baueTripSpeicherung(api, TRIP_ID, { region: 'Konflikt' }, undefined, 'kopf-region');

		await speichere(fn, ctl); // erfüllt, wirft NICHT (Feld bleibt offen ohne Meldung)

		assert.equal(ctl.state, 'conflict', 'AC-11/AC-9: 412 muss „Nochmal speichern" (conflict) zeigen');
		assert.equal(ctl.savedAt, null, 'AC-11: nach 412 darf kein „Gespeichert HH:MM" erscheinen');
		const liste = (ctl as unknown as { _lastFailed: { fn: SaveFn }[] | null })._lastFailed ?? [];
		assert.equal(liste.length, 1, 'AC-9: genau ein Konflikt-Eintrag');
		assert.equal(
			(liste[0].fn as SaveFn & { konfliktSchluessel?: string }).konfliktSchluessel,
			'kopf-region',
			'AC-9: der Eintrag trägt den Kopf-Schlüssel'
		);
	});

	test('anderer Fehler (500): Chip zurück auf den letzten Stand (nicht „saving"), Fehler wird weitergeworfen', async () => {
		const speichere = helper();
		const ctl = controller();
		const fehler = { status: 500, error: 'Serverfehler' };
		const werfend: PutClient = {
			put: () => Promise.reject(fehler)
		};
		const fn = baueTripSpeicherung(werfend, TRIP_ID, { region: 'scheitert' }, undefined, 'kopf-region');

		await assert.rejects(
			() => speichere(fn, ctl),
			(e) => e === fehler,
			'AC-8: der Fehler muss an den Aufrufer (Feld-Fehlermeldung) weitergehen'
		);
		assert.equal(ctl.state, 'idle', 'AC-11: der Chip hängt nach einem Fehler auf „saving" (kein markPristine)');
		assert.equal(ctl.savedAt, null, 'AC-11: nach einem Fehler darf kein „Gespeichert HH:MM" erscheinen');
		assert.equal(
			((ctl as unknown as { _lastFailed: unknown[] | null })._lastFailed ?? []).length,
			0,
			'ein 500 ist kein Konflikt-Eintrag'
		);
	});

	test('ohne Controller: Speichern läuft trotzdem, ein 500 wird weitergeworfen', async () => {
		const speichere = helper();
		await api.get(TRIP_PFAD);
		const fn = baueTripSpeicherung(api, TRIP_ID, { name: 'ohne Chip' }, undefined, 'kopf-name');
		await speichere(fn, null);
		assert.equal(server.calls.filter((c) => c.method === 'PUT').length, 1);

		const fehler = { status: 500 };
		const werfend: PutClient = { put: () => Promise.reject(fehler) };
		await assert.rejects(() => speichere(baueTripSpeicherung(werfend, TRIP_ID, { name: 'x' }), undefined), (e) => e === fehler);
	});
});
