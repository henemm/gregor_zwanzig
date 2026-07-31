// TDD RED — Issue #1395 Scheibe S4: refreshTripEtag() existiert noch nicht.
// Spec: docs/specs/modules/issue_1395_s4_conflict_retry.md — AC-5.
//
// `refreshTripEtag(tripId)` ist ein dünner Wrapper um `api.get(/api/trips/{id})`,
// dessen einziger Zweck der bereits bestehende ETag-Seiteneffekt in
// `etagRegistry.ts` ist (S3, `setKnownEtagIfUnchanged`). Der zurückgegebene
// Trip-Datensatz wird NICHT ausgewertet — die Funktion liefert `Promise<void>`.
// Diese Tests belegen genau diese zwei Eigenschaften gegen den echten
// S2-Server-Vertrag-Nachbau (fakeTripServer.ts), kein Mock der eigenen Annahme.

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { refreshTripEtag } from '../api.ts';
import { clearEtagRegistry, getKnownEtag } from '../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from './fakeTripServer.ts';

let server: FakeTripServer;

beforeEach(() => {
	clearEtagRegistry();
	server = createFakeTripServer({});
	server.install();
});

afterEach(() => server.restore());

describe('AC-5 (Teil 1): refreshTripEtag() gibt den Trip-Datensatz nicht weiter', () => {
	test('test_refreshTripEtag_returnsVoid_responseBodyNotExposed', async () => {
		const result = await refreshTripEtag('gr20');

		assert.equal(
			result,
			undefined,
			'refreshTripEtag() darf den geladenen Trip-Datensatz nicht zurückgeben — sonst entsteht die Versuchung, ' +
				'ihn irgendwo (z.B. trip = updated) zuzuweisen und damit andere Tabs zu gefährden'
		);
	});
});

describe('AC-5 (Teil 2): refreshTripEtag() aktualisiert die Registry über den bestehenden GET-Seiteneffekt', () => {
	test('test_refreshTripEtag_updatesRegistryViaExistingGetSideEffect', async () => {
		assert.equal(getKnownEtag('gr20'), undefined, 'Vorbedingung: kein bekannter Stand vor dem Refresh');

		await refreshTripEtag('gr20');

		assert.equal(
			getKnownEtag('gr20'),
			server.etagOf('gr20'),
			'nach refreshTripEtag() muss die Registry den aktuellen serverseitigen Stand kennen — ' +
				'ganz ohne eigene Änderung an etagRegistry.ts, nur über den bestehenden GET-Seiteneffekt'
		);
	});
});

describe('Grundlage für die Retry-Fehlerbehandlung: ein echter Netzwerkfehler wird nicht verschluckt', () => {
	test('test_refreshTripEtag_propagatesNetworkFailure', async () => {
		const realFetch = globalThis.fetch;
		(globalThis as { fetch: unknown }).fetch = () => Promise.reject(new Error('Netz ausgefallen'));

		let thrown: unknown;
		try {
			await refreshTripEtag('gr20');
			assert.fail('refreshTripEtag() hätte den Fetch-Fehler weiterreichen müssen');
		} catch (e) {
			thrown = e;
		} finally {
			(globalThis as { fetch: unknown }).fetch = realFetch;
		}

		assert.equal((thrown as Error).message, 'Netz ausgefallen');
	});
});
