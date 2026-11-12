// Issue #2961 (FE2b) — ein echtes 401 der Go-API raeumt die offline
// vorgehaltenen Ansichten (gz-daten-*), die Programmdateien bleiben. Ein
// Netzfehler (offline) und ein 503 raeumen nichts.
//
// Spec: docs/specs/modules/security_haertung_2026_11_frontend.md (AC-11)
//
// Aufbau wie apiServerErrorNoRedirect.test.ts: `window` ist ein minimaler
// EventTarget-Stand-in mit beschreibbarer Adresse; der Gerätespeicher ist der
// In-Memory-Doppel aus pwa/__tests__, der wirklich speichert und loescht.
// Die echte `api` laeuft; ersetzt ist nur das Netz am Ausgang (`fetch`).
//
//   cd frontend && npm test -- src/lib/__tests__/api_401_raeumt_inhaltsspeicher.test.ts

import { test, describe, before, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { GeraetespeicherDoppel } from '../pwa/__tests__/geraetespeicherDoppel.ts';

class WindowStandIn extends EventTarget {
	location = { pathname: '/trips/gr20', search: '', href: '' };
}

const windowStandIn = new WindowStandIn();
(globalThis as { window?: unknown }).window = windowStandIn;

let api: (typeof import('../api.ts'))['api'];
let speicher: GeraetespeicherDoppel;
const PROGRAMM = 'gz-1700000000';

before(async () => {
	({ api } = await import('../api.ts'));
});

beforeEach(async () => {
	speicher = new GeraetespeicherDoppel();
	(globalThis as { caches?: unknown }).caches = speicher;
	await (await speicher.open(PROGRAMM)).put('/_app/start.js', new Response('js'));
	await (await speicher.open('gz-daten-mandant-a')).put('/trips/gr20', new Response('<html>'));
	windowStandIn.location.href = '';
});

function netzLiefert(antwort: () => Promise<Response>): () => void {
	const echtesFetch = globalThis.fetch;
	(globalThis as { fetch: unknown }).fetch = antwort;
	return () => {
		(globalThis as { fetch: unknown }).fetch = echtesFetch;
	};
}

async function rufeAuf(): Promise<void> {
	await assert.rejects(() => api.get('/api/trips'));
}

describe('AC-11: Inhaltsspeicher bei beendeter Sitzung', () => {
	test('401: gz-daten-* ist geraeumt, das Programm bleibt, die Umleitung laeuft', async () => {
		const zurueck = netzLiefert(async () => new Response('{"error":"unauthorized"}', { status: 401 }));
		try {
			await rufeAuf();
		} finally {
			zurueck();
		}
		assert.deepEqual(await speicher.keys(), [PROGRAMM]);
		assert.ok(windowStandIn.location.href.startsWith('/login?expired=1'));
	});

	test('Netzfehler (offline): nichts wird geraeumt', async () => {
		const zurueck = netzLiefert(async () => {
			throw new TypeError('Failed to fetch');
		});
		try {
			await rufeAuf();
		} finally {
			zurueck();
		}
		assert.deepEqual((await speicher.keys()).sort(), ['gz-daten-mandant-a', PROGRAMM].sort());
		assert.equal(windowStandIn.location.href, '');
	});

	test('503 (Server gestoert): nichts wird geraeumt', async () => {
		const zurueck = netzLiefert(async () => new Response('{"error":"service_unavailable"}', { status: 503 }));
		try {
			await rufeAuf();
		} finally {
			zurueck();
		}
		assert.deepEqual((await speicher.keys()).sort(), ['gz-daten-mandant-a', PROGRAMM].sort());
	});
});
