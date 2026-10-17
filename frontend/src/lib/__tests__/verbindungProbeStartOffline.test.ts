// Issue #2361 Fix-Loop 1 (F004): meldet das Geraet schon beim Start „keine
// Verbindung" (`navigator.onLine === false`), ist der Store von Anfang an
// offline — und die Probe muss dann OHNE weiteres Ereignis anlaufen, sonst
// bleibt die App gesperrt, bis zufaellig ein anderer Abruf gelingt.
//
// Eigene Datei, weil der Store ein Singleton ist, das sich nur einmal startet
// (`#gestartet`); node --test faehrt jede Datei in einem eigenen Prozess.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/__tests__/verbindungProbeStartOffline.test.ts

import { test } from 'node:test';
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

// DOM-Stand-ins VOR dem Laden: Geraet meldet „offline", Seite sichtbar.
(globalThis as { window?: unknown }).window = new EventTarget();
const documentStandIn = Object.assign(new EventTarget(), {
	visibilityState: 'visible' as 'visible' | 'hidden'
});
(globalThis as { document?: unknown }).document = documentStandIn;
Object.defineProperty(globalThis, 'navigator', { value: { onLine: false }, configurable: true });

const warte = (ms: number) => new Promise((r) => setTimeout(r, ms));

// Laden VOR der Test-Frist: das Uebersetzen der .svelte.ts-Datei dauert unter
// Volllast der Gesamt-Suite laenger als 1,5 s. Der Import startet nichts —
// die Probe laeuft erst mit `starte()`.
const modul = (await import('../stores/verbindung.svelte.ts')) as unknown as {
	verbindung: { offline: boolean; starte: () => void };
	setzeProbeIntervall: (ms: number) => void;
};

test('Start mit navigator.onLine === false ⇒ Probe laeuft ohne weiteres Ereignis an und entsperrt', { timeout: 1500 }, async () => {
	let health = 0;
	(globalThis as { fetch: unknown }).fetch = async (input: unknown) => {
		if (String(input) === '/api/health') health += 1;
		return new Response(JSON.stringify({ status: 'ok' }), {
			status: 200,
			headers: { 'Content-Type': 'application/json' }
		});
	};
	modul.setzeProbeIntervall(20);
	modul.verbindung.starte();
	try {
		assert.equal(modul.verbindung.offline, true, 'Messaufbau: Geraetemeldung offline ⇒ Store offline');
		await warte(100);
		assert.ok(health >= 1, 'ohne weiteres Ereignis muss die Probe anlaufen');
		assert.equal(modul.verbindung.offline, false, 'die gelungene Probe entsperrt');
		const nachEntsperren = health;
		await warte(100);
		assert.equal(health, nachEntsperren, 'nach dem Entsperren darf keine Probe mehr laufen');
	} finally {
		// Probe ueber die Sichtbarkeit beenden (unabhaengig vom Online-Pfad),
		// damit ein noch laufendes Intervall den Prozess nicht offen haelt.
		documentStandIn.visibilityState = 'hidden';
		documentStandIn.dispatchEvent(new Event('visibilitychange'));
	}
});
