// TDD — Issue #2131 Adversary-Finding F001: der Schreibweg selbst muss die
// Sperre kennen (Spec docs/specs/modules/pwa_offline_ansicht_letzter_stand.md,
// Abschnitt H; AC-10). Bisher war das ausschliesslich ueber E2E-Klicks auf
// deaktivierte native <button>/<select>-Elemente abgedeckt — der Browser
// unterdrueckt dort das Ereignis schon selbst, auch bei `{ force: true }`.
// Kein Test rief `request()` bislang UNTER AKTIVER SPERRE auf. Diese Datei
// prueft `api.ts` direkt, unabhaengig von jedem DOM-Zustand.
//
// `window` existiert unter node:test nicht (kein DOM). Fuer diesen Nachweis
// wird deshalb VOR dem Laden von `api.ts` ein minimaler `EventTarget` als
// `globalThis.window` bereitgestellt — genug, damit der modul-globale
// `addEventListener('gz-schreibsperre', ...)` (api.ts:56-60) beim Laden
// tatsaechlich registriert. `api.ts` wird deshalb dynamisch NACH diesem Setup
// geladen — ein statischer Import wuerde (ESM-Hoisting) vor jedem Testcode
// ausgefuehrt und faende `window` noch undefiniert.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/__tests__/apiSchreibsperre.test.ts

import { test, describe, before } from 'node:test';
import assert from 'node:assert/strict';

const windowStandIn = new EventTarget();
(globalThis as { window?: unknown }).window = windowStandIn;

let api: (typeof import('../api.ts'))['api'];

before(async () => {
	({ api } = await import('../api.ts'));
});

function schreibsperreSetzen(gesperrt: boolean): void {
	windowStandIn.dispatchEvent(new CustomEvent('gz-schreibsperre', { detail: { gesperrt } }));
}

/** Ersetzt `globalThis.fetch` durch einen Zaehler, der jeden Aufruf als Fehler wertet. */
function fetchDarfNichtLaufen(): { aufrufe: number; restore: () => void } {
	const echtesFetch = globalThis.fetch;
	const zustand = { aufrufe: 0 };
	(globalThis as { fetch: unknown }).fetch = async () => {
		zustand.aufrufe += 1;
		throw new Error('fetch() haette unter aktiver Sperre nie aufgerufen werden duerfen');
	};
	return {
		get aufrufe() {
			return zustand.aufrufe;
		},
		restore: () => {
			(globalThis as { fetch: unknown }).fetch = echtesFetch;
		}
	};
}

describe('#2131 F001: aktive Sperre weist Schreibvorgaenge im Trichter selbst ab', () => {
	test('put_wirdAbgewiesenOhneFetchAufzurufen', async () => {
		schreibsperreSetzen(true);
		const zaehler = fetchDarfNichtLaufen();
		try {
			await assert.rejects(
				() => api.put('/api/trips/gr20', { name: 'X' }),
				/Ohne Verbindung lässt sich nichts speichern/
			);
		} finally {
			zaehler.restore();
			schreibsperreSetzen(false);
		}
		assert.equal(zaehler.aufrufe, 0, 'fetch() wurde trotz aktiver Sperre aufgerufen');
	});

	test('post_patch_delete_werdenEbenfallsAbgewiesenOhneFetchAufzurufen', async () => {
		schreibsperreSetzen(true);
		const zaehler = fetchDarfNichtLaufen();
		try {
			await assert.rejects(() => api.post('/api/trips', { name: 'X' }));
			await assert.rejects(() => api.patch('/api/trips/gr20', { name: 'X' }));
			await assert.rejects(() => api.del('/api/trips/gr20'));
		} finally {
			zaehler.restore();
			schreibsperreSetzen(false);
		}
		assert.equal(
			zaehler.aufrufe,
			0,
			'mindestens einer der drei schreibenden Aufrufe hat fetch() trotz aktiver Sperre erreicht'
		);
	});

	// Positivkontrolle: die Sperre betrifft laut Spec (Abschnitt H) ausschliesslich
	// SCHREIBENDE Methoden. Ohne diese Gegenprobe koennte `schreibenVerboten()`
	// auch bedingungslos `true` liefern und die beiden Tests oben blieben gruen,
	// ohne dass sie die eigentliche Zusicherung (nur Schreiben ist gesperrt) pruefen.
	test('get_bleibtUnterAktiverSperreErreichbar', async () => {
		schreibsperreSetzen(true);
		const echtesFetch = globalThis.fetch;
		(globalThis as { fetch: unknown }).fetch = async () =>
			new Response(JSON.stringify({ id: 'gr20' }), {
				status: 200,
				headers: { 'Content-Type': 'application/json' }
			});
		try {
			const ergebnis = await api.get('/api/trips/gr20');
			assert.deepEqual(ergebnis, { id: 'gr20' });
		} finally {
			(globalThis as { fetch: unknown }).fetch = echtesFetch;
			schreibsperreSetzen(false);
		}
	});

	test('nachEntsperren_gehtEinSchreibvorgangWiederDurch', async () => {
		schreibsperreSetzen(true);
		schreibsperreSetzen(false);
		const echtesFetch = globalThis.fetch;
		(globalThis as { fetch: unknown }).fetch = async () =>
			new Response(JSON.stringify({ id: 'gr20' }), {
				status: 200,
				headers: { 'Content-Type': 'application/json' }
			});
		try {
			const ergebnis = await api.put('/api/trips/gr20', { name: 'X' });
			assert.deepEqual(ergebnis, { id: 'gr20' });
		} finally {
			(globalThis as { fetch: unknown }).fetch = echtesFetch;
		}
	});
});
