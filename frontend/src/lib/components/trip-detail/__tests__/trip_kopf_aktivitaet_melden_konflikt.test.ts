// TDD RED — Issue #1433, AC-10 (§4 Punkt 3): ein 412 beim Aendern von Name (Kopf)
// oder Aktivitaet fuehrt zur Konfliktanzeige „Nochmal speichern" am gemeinsamen
// Controller — kein stilles Scheitern. Die Fremdaenderung bleibt erhalten.
//
// Spec: docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md — §4 Punkt 3, AC-10;
//       Test Plan `trip_kopf_aktivitaet_melden_konflikt` (hier ueber die WIRKUNG
//       gemessen: Controller-Zustand, Retry, Server-Stand — nicht ueber die Signatur).
//
// Issue #2284 S2 (docs/specs/modules/feat_2284_s2_trip_kopf.md, AC-8, AC-9, AC-17):
// Name, Region (NEU) und Aktivitaet laufen ueber EINE Speicherfunktion des Kopfs,
// `TripHeader.onSaveField(field, value, schliessen)` (Schnittstelle: Kopfkommentar
// `kopfReiter` in tripMehrreiterPruefstand.ts). Vorher: `makeNameSaveHandler` und
// `TripTabs.handleActivityChange` — jede alte Zusicherung steht unten weiter
// (Inventar: docs/artifacts/feat-2284-s2-trip-kopf/ac17-zusicherungs-inventar.md).
// Neu bewacht: Konflikt-Schluessel `kopf-name`/`kopf-region`/`kopf-profil` (ein Eintrag
// je Feld, ein Retry schreibt alle), `schliessen()` erst nach Erfolg, und der Kern-
// Anteil von AC-8 (500 ⇒ wirft mit `error`, Feld bleibt offen, Server unveraendert).
//
// RED vor S2: `TripHeader.onSaveField` existiert nicht ⇒ „Messaufbau: … nicht herleitbar".
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/__tests__/trip_kopf_aktivitaet_melden_konflikt.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import * as P from './tripMehrreiterPruefstand.ts';

let server: FakeTripServer;
const FREMDE_METRIKEN = [{ metric_id: 'cape', enabled: true, aggregations: ['max'] }];

beforeEach(async () => {
	clearEtagRegistry();
	server = createFakeTripServer({ merge: true });
	server.install();
	server.seed(P.TRIP_ID, P.vollerTrip());
	await api.get(P.TRIP_PFAD);
	// ein anderer Tab / der Python-Core hat den Trip inzwischen geaendert
	server.foreignWrite(P.TRIP_ID, { display_config: { metrics: FREMDE_METRIKEN } });
});
afterEach(() => server.restore());

const puts = () => server.calls.filter((c) => c.method === 'PUT');
const stand = () => server.stand(P.TRIP_ID);

describe('AC-10: Kopf (Name) — 412 zeigt „Nochmal speichern"', () => {
	test('412 beim Umbenennen: Controller steht auf `conflict`, Name und Fremdaenderung auf dem Server unveraendert', async () => {
		const a = P.neuerAufbau();
		assert.equal(a.ctl.state, 'idle');
		const k = await P.kopfReiter(a);
		await k.umbenennen('Neuer Name');

		assert.equal(puts().at(-1)!.status, 412, 'Vorbedingung: der Server lehnt den veralteten Stand ab');
		assert.equal(a.ctl.state, 'conflict', 'AC-10: die Oberflaeche muss „Nochmal speichern" zeigen (heute: Kopf meldet nichts an den Controller)');
		assert.notEqual(stand().name, 'Neuer Name');
		assert.deepEqual((stand().display_config as Record<string, unknown>).metrics, FREMDE_METRIKEN, 'die Fremdaenderung bleibt erhalten');
		assert.equal(a.updates.length, 0, 'bei 412 wird `trip` nicht durch die lokale Fassung ersetzt');
	});

	test('„Nochmal speichern" wiederholt die Namensaenderung gegen den frischen Stand; Fremdaenderung bleibt', async () => {
		const a = P.neuerAufbau();
		const k = await P.kopfReiter(a);
		await k.umbenennen('Neuer Name');
		assert.equal(a.ctl.state, 'conflict', 'Vorbedingung');

		await a.ctl.retryConflict();

		assert.equal(stand().name, 'Neuer Name', 'der Retry muss die Eingabe des Nutzers speichern — sonst ist der Knopf eine Attrappe');
		assert.deepEqual((stand().display_config as Record<string, unknown>).metrics, FREMDE_METRIKEN);
		assert.equal(a.ctl.state, 'idle');
	});
});

describe('AC-10: Aktivitaet — 412 zeigt „Nochmal speichern"', () => {
	test('412 beim Aendern der Aktivitaet: Controller `conflict`, nichts geschrieben', async () => {
		const a = P.neuerAufbau();
		const t = await P.aktivitaetReiter(a);
		await t.aendern('skitour');

		assert.equal(puts().at(-1)!.status, 412);
		assert.equal(a.ctl.state, 'conflict', 'AC-10: Konfliktanzeige statt stillem Scheitern (heute: kein try/catch, Controller unbeteiligt)');
		assert.notEqual(stand().activity, 'skitour');
		assert.deepEqual((stand().display_config as Record<string, unknown>).metrics, FREMDE_METRIKEN);
		assert.equal(a.updates.length, 0);
	});

	for (const [feld, wert] of [['name', 'Neuer Name'], ['region', 'Alpen Nord'], ['profile', 'skitour']] as const) {
		test(`onSaveField wirft bei 412 nicht (${feld}) — kein unbehandelter Promise-Fehler im Klick-Handler`, async () => {
			const a = P.neuerAufbau();
			const k = await P.kopfReiter(a);
			await assert.doesNotReject(k.speichereFeld(feld, wert), '412 muss am Controller gemeldet, nicht als Ausnahme durchgereicht werden');
			assert.equal(a.ctl.state, 'conflict');
			assert.equal(k.geschlossen[feld], 0, 'bei 412 bleibt das Feld offen (kein schliessen())');
		});
	}

	test('„Nochmal speichern" wiederholt die Aktivitaetsaenderung; Fremdaenderung bleibt', async () => {
		const a = P.neuerAufbau();
		const t = await P.aktivitaetReiter(a);
		await t.aendern('skitour');
		assert.equal(a.ctl.state, 'conflict', 'Vorbedingung');

		await a.ctl.retryConflict();

		assert.equal(stand().activity, 'skitour');
		assert.deepEqual((stand().display_config as Record<string, unknown>).metrics, FREMDE_METRIKEN);
		assert.equal(a.ctl.state, 'idle');
	});
});

describe('Kopf und Reiter teilen EINE Konfliktanzeige', () => {
	test('Kopf-412 und Alarme-412 landen in derselben Anzeige; ein Retry schreibt beide', async () => {
		const a = P.neuerAufbau();
		const k = await P.kopfReiter(a);
		await k.umbenennen('Neuer Name');
		const alarme = await P.alarmeReiter(a);
		alarme.empfindlichkeitAendern('wind', 'sensibel');
		await P.fertig(a.ctl);
		assert.equal(a.ctl.state, 'conflict');

		await a.ctl.retryConflict();

		assert.equal(stand().name, 'Neuer Name');
		assert.equal(((stand().display_config as Record<string, unknown>).metric_alert_levels as Record<string, unknown>).wind, 'sensibel');
		assert.deepEqual((stand().display_config as Record<string, unknown>).metrics, FREMDE_METRIKEN);
	});
});

// ─── Issue #2284 S2 ──────────────────────────────────────────────────────────

/** Die Konflikt-Schluessel der offenen Eintraege am Controller (Dedup-Schluessel, ein
 *  Eintrag je Schreiber). Wird nur ZUSAETZLICH zur Wirkung (Retry schreibt alle)
 *  gelesen: die Wirkung allein liesse falsche, aber verschiedene Namen durch. */
function konfliktSchluessel(ctl: unknown): unknown[] {
	const liste = (ctl as { _lastFailed?: Array<{ fn: { konfliktSchluessel?: string } }> | null })._lastFailed ?? [];
	return liste.map((e) => e.fn.konfliktSchluessel);
}

describe('#2284 S2 AC-9: Region (neues Eigenfeld) — 412 zeigt „Nochmal speichern"', () => {
	test('412 bei der Region: Controller `conflict`, Feld offen, Region und Fremdaenderung auf dem Server unveraendert', async () => {
		const a = P.neuerAufbau();
		const k = await P.kopfReiter(a);
		await k.regionAendern('Alpen Nord');

		assert.equal(puts().at(-1)!.status, 412, 'Vorbedingung: 412');
		assert.deepEqual(puts().at(-1)!.anfrage, { region: 'Alpen Nord' }, 'nur das Eigenfeld wird gesendet');
		assert.equal(a.ctl.state, 'conflict');
		assert.equal(stand().region, 'Korsika');
		assert.deepEqual((stand().display_config as Record<string, unknown>).metrics, FREMDE_METRIKEN);
		assert.equal(k.geschlossen.region, 0, 'Feld bleibt offen, solange der Konflikt steht');
		assert.equal(a.updates.length, 0);
	});

	test('„Nochmal speichern" schreibt die Region, schliesst das Feld und ersetzt den Seitenstand', async () => {
		const a = P.neuerAufbau();
		const k = await P.kopfReiter(a);
		await k.regionAendern('Alpen Nord');
		assert.equal(a.ctl.state, 'conflict', 'Vorbedingung');

		await a.ctl.retryConflict();

		assert.equal(stand().region, 'Alpen Nord');
		assert.deepEqual((stand().display_config as Record<string, unknown>).metrics, FREMDE_METRIKEN);
		assert.equal(a.ctl.state, 'idle');
		assert.equal(k.geschlossen.region, 1, 'erst der erfolgreiche Retry schliesst das Feld');
		assert.equal(a.updates.length, 1, 'der Retry ersetzt den Seitenstand (kein imWiederholen-Guard beim Trip, Entscheidung 10)');
		assert.equal(a.updates[0].region, 'Alpen Nord');
	});

	test('Name: erst der erfolgreiche Retry schliesst das Feld und meldet den neuen Stand nach oben', async () => {
		const a = P.neuerAufbau();
		const k = await P.kopfReiter(a);
		await k.umbenennen('Neuer Name');
		assert.equal(k.geschlossen.name, 0);
		await a.ctl.retryConflict();
		assert.equal(k.geschlossen.name, 1);
		assert.equal(a.updates.length, 1);
		assert.equal(a.updates[0].name, 'Neuer Name');
	});
});

describe('#2284 S2 AC-9: ein Eintrag je Kopf-Feld (kopf-name / kopf-region / kopf-profil)', () => {
	test('Name UND Region im Konflikt: ein Retry schreibt beide (kein gemeinsamer Eintrag)', async () => {
		const a = P.neuerAufbau();
		const k = await P.kopfReiter(a);
		await k.umbenennen('Neuer Name');
		await k.regionAendern('Alpen Nord');
		assert.equal(a.ctl.state, 'conflict', 'Vorbedingung');

		await a.ctl.retryConflict();

		assert.equal(stand().name, 'Neuer Name', 'teilen Name und Region einen Schluessel, verdraengt die Region den Namen');
		assert.equal(stand().region, 'Alpen Nord');
		assert.equal(k.geschlossen.name, 1);
		assert.equal(k.geschlossen.region, 1);
	});

	test('Name UND Aktivitaet im Konflikt: ein Retry schreibt beide', async () => {
		const a = P.neuerAufbau();
		const k = await P.kopfReiter(a);
		await k.umbenennen('Neuer Name');
		await k.aktivitaetAendern('skitour');
		await a.ctl.retryConflict();
		assert.equal(stand().name, 'Neuer Name');
		assert.equal(stand().activity, 'skitour');
	});

	test('die Eintraege tragen genau die Schluessel kopf-name, kopf-region, kopf-profil', async () => {
		const a = P.neuerAufbau();
		const k = await P.kopfReiter(a);
		await k.umbenennen('Neuer Name');
		await k.regionAendern('Alpen Nord');
		await k.aktivitaetAendern('skitour');
		assert.deepEqual(konfliktSchluessel(a.ctl), ['kopf-name', 'kopf-region', 'kopf-profil']);
	});

	test('zweimal dasselbe Feld im Konflikt: EIN Eintrag, der neueste Wert gewinnt', async () => {
		const a = P.neuerAufbau();
		const k = await P.kopfReiter(a);
		await k.regionAendern('Erst');
		await k.regionAendern('Dann');
		assert.deepEqual(konfliktSchluessel(a.ctl), ['kopf-region']);
		await a.ctl.retryConflict();
		assert.equal(stand().region, 'Dann');
	});
});

describe('#2284 S2 AC-8 (Kern-Anteil): Serverfehler 500 — onSaveField wirft, Feld bleibt offen', () => {
	/** Der naechste PUT auf den Trip antwortet 500 mit `{"error":"Serverfehler"}`
	 *  (der Ersatz-Server kennt keinen Fehlerfall; `server.restore()` setzt fetch zurueck). */
	function naechsterPutScheitert(): void {
		const weiter = globalThis.fetch;
		let einmal = true;
		globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
			if (einmal && (init?.method ?? 'GET').toUpperCase() === 'PUT') {
				einmal = false;
				return new Response(JSON.stringify({ error: 'Serverfehler' }), {
					status: 500,
					headers: { 'Content-Type': 'application/json' }
				});
			}
			return weiter(input, init);
		}) as typeof globalThis.fetch;
	}

	for (const [feld, wert] of [['name', 'Neuer Name'], ['region', 'Alpen Nord'], ['profile', 'skitour']] as const) {
		test(`${feld}: Ablehnung mit error „Serverfehler", kein schliessen(), kein Konflikt, Server unveraendert`, async () => {
			const a = P.neuerAufbau();
			const k = await P.kopfReiter(a);
			const vorher = stand();
			naechsterPutScheitert();
			await assert.rejects(k.speichereFeld(feld, wert), (e: unknown) => {
				assert.equal((e as { error?: string }).error, 'Serverfehler', 'die Meldung des Servers erreicht den Baustein');
				return true;
			});
			assert.equal(k.geschlossen[feld], 0, 'Eingabe bleibt offen');
			assert.notEqual(a.ctl.state, 'conflict', 'ein 500 ist kein Konflikt');
			assert.equal(a.updates.length, 0);
			assert.deepEqual(stand(), vorher, 'der serverseitige Wert ist unveraendert');
		});
	}
});
