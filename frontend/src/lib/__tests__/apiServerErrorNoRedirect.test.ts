// TDD — Issue #2353 AC-7: eine 503-Antwort der Auth-Middleware (Lesefehler der
// Gästeliste) darf NICHT wie ein 401 behandelt werden. `api.ts` leitet heute
// bei 401 hart auf `/login?expired=1` um (api.ts:118-131) — dieses Verhalten
// existiert schon und bleibt unverändert; dieser Test belegt nur, dass 503
// NICHT denselben Pfad nimmt, sondern über den generischen Fehlerpfad läuft
// (angereichertes Fehlerobjekt mit `status: 503`, kein Redirect).
//
// Muster von apiSchreibsperre.test.ts: `window` existiert unter node:test
// nicht. Hier braucht der Nachweis zusätzlich ein beschreibbares
// `window.location.href` (fürs Redirect-Ziel) UND `dispatchEvent`/
// `addEventListener` (api.ts registriert beim Laden einen
// `gz-schreibsperre`-Listener und meldet nach jedem Abruf ein
// `gz-abruf-gelungen`/`-fehlgeschlagen`-Ereignis). Ein minimaler
// `EventTarget`-Nachfahre mit eigenem `location`-Feld deckt beides ab, ohne
// ein DOM zu simulieren. `api.ts` wird deshalb dynamisch NACH diesem Setup
// geladen (ESM-Hoisting würde einen statischen Import vor dem Setup laufen
// lassen und fände `window` noch undefiniert).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/__tests__/apiServerErrorNoRedirect.test.ts

import { test, describe, before } from 'node:test';
import assert from 'node:assert/strict';

class WindowStandIn extends EventTarget {
	location = { pathname: '/trips/gr20', search: '', href: '' };
}

const windowStandIn = new WindowStandIn();
(globalThis as { window?: unknown }).window = windowStandIn;

let api: (typeof import('../api.ts'))['api'];

before(async () => {
	({ api } = await import('../api.ts'));
});

/** Ersetzt `globalThis.fetch` durch einen echten `Response`-Wert mit dem gegebenen Status. */
function fetchLiefert(status: number, body: unknown): () => void {
	const echtesFetch = globalThis.fetch;
	(globalThis as { fetch: unknown }).fetch = async () =>
		new Response(JSON.stringify(body), {
			status,
			headers: { 'content-type': 'application/json' }
		});
	return () => {
		(globalThis as { fetch: unknown }).fetch = echtesFetch;
	};
}

describe('#2353 AC-7: 503 (Lookup-Fehler) leitet NICHT auf /login um', () => {
	test('service_unavailable_wirftFehlerMitStatus503OhneRedirect', async () => {
		windowStandIn.location.href = '';
		const restore = fetchLiefert(503, { error: 'service_unavailable' });
		try {
			await assert.rejects(
				() => api.get('/api/trips'),
				(err: unknown) => {
					assert.equal((err as { status?: number }).status, 503);
					return true;
				}
			);
		} finally {
			restore();
		}
		assert.equal(
			windowStandIn.location.href,
			'',
			'503 darf keinen Redirect auf /login ausloesen, href wurde veraendert: ' +
				windowStandIn.location.href
		);
	});

	// Gegenprobe: belegt, dass der Stand-in einen Redirect ueberhaupt messen
	// kann — sonst bestuende der Test oben auch dann, wenn api.ts NIE
	// umleitet.
	test('unauthorized_leitetWeiterhinAufLoginUm', async () => {
		windowStandIn.location.href = '';
		const restore = fetchLiefert(401, { error: 'unauthorized' });
		try {
			await assert.rejects(
				() => api.get('/api/trips'),
				(err: unknown) => {
					assert.equal((err as { status?: number }).status, 401);
					return true;
				}
			);
		} finally {
			restore();
		}
		assert.ok(
			windowStandIn.location.href.startsWith('/login?expired=1'),
			`401 muss weiterhin auf /login umleiten, bekommen ${windowStandIn.location.href}`
		);
	});
});
