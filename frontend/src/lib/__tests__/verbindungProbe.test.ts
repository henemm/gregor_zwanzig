// TDD RED — Issue #2361 AC-8: Probe-Abruf gegen die Sperr-Sackgasse.
// Spec: docs/specs/modules/fix_2361_abruf_zeitlimit.md (Implementation Details 8).
//
// Das Zeitlimit kann eine erreichbare, aber langsame Verbindung als „offline"
// melden. Entsperrt wird bisher nur durch einen spaeter GELUNGENEN Abruf — den
// eine gesperrte Oberflaeche nicht mehr ausloest. Der Verbindungs-Store schickt
// deshalb, solange er offline ist UND die Seite sichtbar ist, alle 15 s einen
// `GET /api/health` ueber `api.ts`; gelingt er, meldet `api.ts`
// `gz-abruf-gelungen` und der Store entsperrt sich.
//
// Zielschnittstelle in `stores/verbindung.svelte.ts` (neu, von diesen Tests
// festgelegt):
//   * `PROBE_INTERVALL_MS` — 15 000 ms
//   * `setzeProbeIntervall(ms)` — verkuerzt das Intervall fuer Tests
//   * Start/Stopp der Probe aus den Ereignis-Handlern (`gz-abruf-fehlgeschlagen`,
//     `offline`, `gz-abruf-gelungen`, `visibilitychange` am `document`) — NICHT
//     aus einem `$effect`: ein Store ausserhalb einer Komponente hat keinen
//     Effekt-Besitzer, und unter diesem Testaufbau laeuft kein `$effect`.
//
// Der Store nutzt Svelte-Runen. Er wird mit dem echten Compiler uebersetzt
// (`layout-ssr-hooks.mjs`: TypeScript strippen, dann `compileModule`) — kein
// Runen-Attrappen-Shim.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/__tests__/verbindungProbe.test.ts

import { test, describe, before, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../..');
register(
	pathToFileURL(join(FRONTEND, 'src/routes/__tests__/layout-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

// DOM-Stand-ins: `window` fuer die Abruf-Ereignisse, `document` fuer die
// Sichtbarkeit. Beides VOR dem Laden der Module.
const windowStandIn = new EventTarget();
(globalThis as { window?: unknown }).window = windowStandIn;
const documentStandIn = Object.assign(new EventTarget(), { visibilityState: 'visible' as 'visible' | 'hidden' });
(globalThis as { document?: unknown }).document = documentStandIn;

type Store = { offline: boolean; starte: () => void };
type Modul = {
	verbindung: Store;
	PROBE_INTERVALL_MS?: number;
	setzeProbeIntervall?: (ms: number) => void;
};

let modul: Modul;
const INTERVALL = 20;
const FRIST = { timeout: 1500 };
const warte = (ms: number) => new Promise((r) => setTimeout(r, ms));

before(async () => {
	modul = (await import('../stores/verbindung.svelte.ts')) as unknown as Modul;
	modul.verbindung.starte();
});

/** Vertrag pruefen und das Intervall verkuerzen — je Test, damit jeder einzeln rot wird. */
function kurzesIntervall(): void {
	assert.equal(
		typeof modul.setzeProbeIntervall,
		'function',
		'verbindung.svelte.ts muss `setzeProbeIntervall(ms)` exportieren (Test-Setter)'
	);
	modul.setzeProbeIntervall!(INTERVALL);
}

/** fetch-Ersatz: `/api/health` antwortet mit `status` (oder Netzfehler bei null). */
function installiereFetch(status: number | null): { health: () => number; restore: () => void } {
	const echtesFetch = globalThis.fetch;
	const pfade: string[] = [];
	(globalThis as { fetch: unknown }).fetch = async (input: unknown) => {
		pfade.push(String(input));
		if (status === null) throw new TypeError('Failed to fetch');
		return new Response(JSON.stringify({ status: 'ok' }), {
			status,
			headers: { 'Content-Type': 'application/json' }
		});
	};
	return {
		health: () => pfade.filter((p) => p === '/api/health').length,
		restore: () => {
			(globalThis as { fetch: unknown }).fetch = echtesFetch;
		}
	};
}

const gehOffline = () => windowStandIn.dispatchEvent(new CustomEvent('gz-abruf-fehlgeschlagen'));
const gehOnline = () => windowStandIn.dispatchEvent(new CustomEvent('gz-abruf-gelungen'));
function sichtbarkeit(stand: 'visible' | 'hidden'): void {
	documentStandIn.visibilityState = stand;
	documentStandIn.dispatchEvent(new Event('visibilitychange'));
}

let netz: ReturnType<typeof installiereFetch> | null = null;
afterEach(async () => {
	// Probe ueber die Sichtbarkeit beenden — ein Weg, der vom Online-Pfad
	// unabhaengig ist: ist gerade der Stopp bei `gz-abruf-gelungen` kaputt,
	// endet der Test rot statt im Haenger (Fix-Loop 2, F-R2-3).
	sichtbarkeit('hidden');
	gehOnline();
	sichtbarkeit('visible');
	await warte(INTERVALL * 2);
	netz?.restore();
	netz = null;
});

describe('#2361 AC-8: Probe-Intervall', () => {
	test('das Probe-Intervall betraegt 15 Sekunden', () => {
		assert.equal(modul.PROBE_INTERVALL_MS, 15_000, 'verbindung.svelte.ts muss `PROBE_INTERVALL_MS = 15_000` exportieren');
	});
});

describe('#2361 AC-8: Probe entsperrt die App von selbst', () => {
	test('offline + sichtbar ⇒ GET /api/health; Antwort 200 ⇒ online, Probe stoppt', FRIST, async () => {
		kurzesIntervall();
		netz = installiereFetch(200);
		gehOffline();
		assert.equal(modul.verbindung.offline, true, 'Messaufbau: Store ist offline');
		await warte(INTERVALL * 4);
		assert.ok(netz.health() >= 1, 'im Offline-Zustand muss ein Probe-Abruf auf /api/health rausgehen');
		assert.equal(modul.verbindung.offline, false, 'eine gelungene Probe muss die App entsperren');
		const nachEntsperren = netz.health();
		await warte(INTERVALL * 4);
		assert.equal(netz.health(), nachEntsperren, 'nach dem Entsperren darf keine Probe mehr laufen');
	});

	test('scheitert die Probe, bleibt die App gesperrt und probt im Takt weiter (kein Aufschaukeln)', FRIST, async () => {
		kurzesIntervall();
		netz = installiereFetch(null);
		gehOffline();
		await warte(INTERVALL * 6 + INTERVALL / 2);
		assert.equal(modul.verbindung.offline, true, 'eine gescheiterte Probe entsperrt nicht');
		assert.ok(netz.health() >= 2, `die Probe muss nach einem Fehlschlag weiterlaufen (gesehen: ${netz.health()})`);
		assert.ok(netz.health() <= 7, `gescheiterte Proben duerfen keine zusaetzlichen Intervalle starten (gesehen: ${netz.health()})`);
	});
});

describe('#2361 AC-8: keine Probe ohne Anlass', () => {
	test('online ⇒ kein /api/health-Abruf', FRIST, async () => {
		kurzesIntervall();
		netz = installiereFetch(200);
		gehOnline();
		await warte(INTERVALL * 5);
		assert.equal(netz.health(), 0, 'im Online-Zustand laeuft kein Hintergrund-Abruf');
	});

	test('offline, aber Seite unsichtbar ⇒ kein Probe-Abruf', FRIST, async () => {
		kurzesIntervall();
		netz = installiereFetch(200);
		sichtbarkeit('hidden');
		gehOffline();
		await warte(INTERVALL * 5);
		assert.equal(netz.health(), 0, 'bei unsichtbarer Seite darf keine Probe laufen');
		assert.equal(modul.verbindung.offline, true);
	});

	test('wird die Seite wieder sichtbar, setzt die Probe ein und entsperrt', FRIST, async () => {
		kurzesIntervall();
		netz = installiereFetch(200);
		sichtbarkeit('hidden');
		gehOffline();
		await warte(INTERVALL * 3);
		assert.equal(netz.health(), 0, 'Messaufbau: unsichtbar ⇒ keine Probe');
		sichtbarkeit('visible');
		await warte(INTERVALL * 4);
		assert.ok(netz.health() >= 1, 'nach Rueckkehr der Sichtbarkeit muss die Probe einsetzen');
		assert.equal(modul.verbindung.offline, false);
	});

	test('wird die Seite unsichtbar, endet eine laufende Probe', FRIST, async () => {
		kurzesIntervall();
		netz = installiereFetch(null);
		gehOffline();
		await warte(INTERVALL * 3);
		assert.ok(netz.health() >= 1, 'Messaufbau: offline + sichtbar ⇒ Probe laeuft');
		sichtbarkeit('hidden');
		await warte(INTERVALL);
		const beimVerstecken = netz.health();
		await warte(INTERVALL * 4);
		assert.equal(netz.health(), beimVerstecken, 'bei unsichtbarer Seite muss das Intervall beendet sein');
	});
});

describe('#2361 Fix-Loop 1 (F003): hoechstens EIN Probe-Abruf gleichzeitig', () => {
	test('haengt die Probe laenger als mehrere Intervalle, geht keine zweite raus', FRIST, async () => {
		kurzesIntervall();
		// Eigener fetch-Ersatz: /api/health haengt, bis der Test ihn freigibt —
		// sonst liefe der 25-s-Zeitlimit-Timer der Probe in spaetere Tests hinein.
		const echtesFetch = globalThis.fetch;
		let health = 0;
		let freigeben: (() => void) | null = null;
		(globalThis as { fetch: unknown }).fetch = (input: unknown) => {
			if (String(input) === '/api/health') health += 1;
			return new Promise<Response>((resolve) => {
				freigeben = () =>
					resolve(
						new Response(JSON.stringify({ status: 'ok' }), {
							status: 200,
							headers: { 'Content-Type': 'application/json' }
						})
					);
			});
		};
		try {
			gehOffline();
			await warte(INTERVALL * 6 + INTERVALL / 2);
			assert.equal(health, 1, `waehrend eine Probe haengt, darf keine weitere starten (gesehen: ${health})`);
			freigeben!();
			await warte(INTERVALL);
			assert.equal(modul.verbindung.offline, false, 'die freigegebene Probe entsperrt');
		} finally {
			(globalThis as { fetch: unknown }).fetch = echtesFetch;
		}
	});
});

describe('#2361 Fix-Loop 2 (F-R2-1): Geraetemeldung „offline" startet die Probe', () => {
	test('window-Ereignis offline ⇒ nach dem Intervall GET /api/health; Antwort 200 ⇒ online', FRIST, async () => {
		kurzesIntervall();
		netz = installiereFetch(200);
		windowStandIn.dispatchEvent(new Event('offline'));
		assert.equal(modul.verbindung.offline, true, 'Messaufbau: Geraetemeldung offline ⇒ Store offline');
		await warte(INTERVALL * 4);
		assert.ok(netz.health() >= 1, 'nach der Geraetemeldung offline muss die Probe anlaufen');
		assert.equal(modul.verbindung.offline, false, 'die gelungene Probe entsperrt');
	});
});
