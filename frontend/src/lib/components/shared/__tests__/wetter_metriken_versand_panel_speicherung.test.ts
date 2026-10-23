// TDD RED — Issue #1743, Speicher-Slot im Panel „Wetter-Metriken + Versand"
// (Spec docs/specs/modules/feat_1743_reiter_aufraeumen.md, Abschnitt 5,
// AC-10, AC-11, AC-13, AC-14, AC-15).
//
// Wetter-Metriken und Versand stehen kuenftig in EINEM Reiter und teilen sich den
// EINEN Speicher-Controller der Seite. Heute verdraengt der zweite geplante
// Speichervorgang den ersten lautlos — die erste Aenderung kommt nie beim Server an.
//
// Gemessen wird dort, wo die Zusicherung wirkt: die ECHTEN Bausteine des Panels
// schreiben ueber das echte `api` an einen Ersatz-Server, der wie Go zusammenfuehrt;
// gelesen werden die aufgezeichneten PUT-Koerper und der Server-Stand.
//   - context `route` (Trip-Hub): `WeatherMetricsTab.svelte` und
//     `BriefingScheduleTab.svelte` (echte Instanz-Skripte, Pruefstand
//     `tripMehrreiterPruefstand.ts`), Ersatz-Server `fakeTripServer.ts` (merge).
//   - context `vergleich` (Ortsvergleich-Hub): die echten Speicherwege
//     `erstelleWetterMetrikenVergleichSpeicherung` und
//     `erstelleVersandVergleichSpeicherung` an EINEM Controller, EINER Hub-Queue und
//     EINER Basis (`currentPreset`) — wie `CompareTabs.svelte` sie verdrahtet;
//     Ersatz-Server `goMergeServerPruefstand.ts`.
// Die Panel-Huelle `WetterMetrikenVersandPanel.svelte` selbst haelt keine
// Speicherlogik (sie reicht nur durch); ihre Struktur pruefen die AC-8-Tests.
//
// Kein Fixture setzt die erwarteten Werte: die Aenderungen laufen durch die
// Bedien-Handler der Bausteine, den PUT-Koerper schreibt das Produkt.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/shared/__tests__/wetter_metriken_versand_panel_speicherung.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import type { SaveStatus } from '../../../stores/saveStatusStore.svelte.ts';
import type { ComparePreset } from '../../../types.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import * as P from '../../trip-detail/__tests__/tripMehrreiterPruefstand.ts';
import { createGoMergeServer, vollerVergleich, type GoMergeServer } from './goMergeServerPruefstand.ts';
import { createController, versandBedienung } from './versandVergleichPruefstand.ts';
import { createPutQueue } from '../../compare/compareHubPersistenz.ts';
import {
	erstelleVersandVergleichSpeicherung,
	hydrateVersandFieldsFromPreset
} from '../versandVergleichSpeicherung.ts';
import { erstelleWetterMetrikenVergleichSpeicherung } from '../weather-metrics-tab/weatherMetricsCompareSave.ts';
import {
	hydrierterWs as hydrierterWetterWs,
	wetterMetrikenBedienung
} from '../weather-metrics-tab/__tests__/wetterMetrikenVergleichPruefstand.ts';

/** Fehlerinjektion ueber dem Ersatz-Server (Muster compare_retry_fehlerpfade_kein_verlust). */
let fehler: ((method: string, path: string, body: string) => boolean) | null = null;
function fehlerSchicht(): void {
	const darunter = globalThis.fetch;
	(globalThis as { fetch: unknown }).fetch = async (input: unknown, init?: RequestInit) => {
		if (fehler?.((init?.method ?? 'GET').toUpperCase(), String(input), String(init?.body ?? ''))) {
			return new Response(JSON.stringify({ error: 'boom', detail: 'Serverfehler' }), {
				status: 500,
				headers: { 'Content-Type': 'application/json' }
			});
		}
		return darunter(input as never, init);
	};
}

/** Controller der laufenden Testfalls — ein vorzeitig rot abgebrochener Fall darf keinen
 *  geplanten Speichervorgang hinterlassen, der spaeter in den Ersatz-Server des NAECHSTEN
 *  Falls schreibt (falsches Gruen dort). */
const offeneController: SaveStatus[] = [];
async function aufraeumen(): Promise<void> {
	fehler = null;
	for (const ctl of offeneController.splice(0)) await leeren(ctl);
}

const tick = (ms = 5): Promise<void> => new Promise((r) => setTimeout(r, ms));

/** Alles abarbeiten, was der Controller plant oder gerade sendet — auch mehrere
 *  Schreiber nacheinander (`fertig()` wartet nur auf den letzten). */
async function leeren(ctl: SaveStatus): Promise<void> {
	for (let i = 0; i < 20; i++) {
		await ctl.flush();
		const laufend = ctl.laufendeSpeicherung;
		if (laufend) await laufend;
		await tick();
		if (!ctl.hasPending && !ctl.laufendeSpeicherung) return;
	}
}

/** Nur den gerade laufenden Vorgang abschliessen lassen, nichts Geplantes vorziehen. */
async function laufendenAbschliessen(ctl: SaveStatus): Promise<void> {
	await tick();
	const laufend = ctl.laufendeSpeicherung;
	if (laufend) await laufend;
	await tick(20);
}

// ─────────────────────────────── context = route (Trip-Hub) ───────────────────────────────

const VERSANDZEIT = '08:00:00';

describe('context route (Trip-Hub): Wetter-Metriken und Versand an einem Controller', () => {
	let server: FakeTripServer;

	beforeEach(async () => {
		clearEtagRegistry();
		fehler = null;
		server = createFakeTripServer({ merge: true });
		server.install();
		server.seed(P.TRIP_ID, P.vollerTrip());
		fehlerSchicht();
		await api.get(P.TRIP_PFAD);
	});
	afterEach(async () => {
		await aufraeumen();
		server.restore();
	});

	const puts = () => server.calls.filter((c) => c.method === 'PUT');
	const stand = () => server.stand(P.TRIP_ID);
	const dcStand = () => stand().display_config as Record<string, unknown>;
	const rcStand = () => stand().report_config as Record<string, unknown>;

	async function panel(a = P.neuerAufbau()) {
		offeneController.push(a.ctl);
		const wm = await P.wetterMetrikenReiter(a);
		const versand = await P.versandReiter(a);
		return {
			a,
			wm,
			versand,
			/** Metrik-Katalog-Geste (Telegram-Kurzform) ⇒ `scheduleAutoSave` */
			metrikAendern() {
				wm.inst.u.telegramKurzform = true;
				wm.metrikenSpeichern();
			},
			versandzeitAendern() {
				versand.aendern({ morning_time: VERSANDZEIT });
			}
		};
	}

	/** Re-Hydration: beide Bausteine frisch aus dem Server-Stand (Neuladen der Seite). */
	async function neuGeladen() {
		const b = P.neuerAufbau(stand());
		return { wm: await P.wetterMetrikenReiter(b), versand: await P.versandReiter(b) };
	}

	function beideImBackend(): void {
		assert.ok(
			puts().some((p) => /\/weather-config$/.test(p.path) && (p.anfrage as Record<string, unknown>)?.telegram_kurzform === true),
			`kein PUT traegt die Wetter-Metrik-Aenderung (PUTs: ${JSON.stringify(puts().map((p) => p.path))})`
		);
		assert.ok(
			puts().some((p) => ((p.anfrage as Record<string, unknown>)?.report_config as Record<string, unknown>)?.morning_time === VERSANDZEIT),
			'kein PUT traegt die Versandzeit'
		);
		assert.equal(dcStand().telegram_kurzform, true, 'Wetter-Metrik-Aenderung fehlt auf dem Server');
		assert.equal(rcStand().morning_time, VERSANDZEIT, 'Versandzeit fehlt auf dem Server');
	}

	test('Vorbedingung (Gegenprobe): jede Aenderung allein kommt an', async () => {
		const p = await panel();
		p.metrikAendern();
		await leeren(p.a.ctl);
		p.versandzeitAendern();
		await leeren(p.a.ctl);
		beideImBackend();
		assert.equal(p.a.ctl.state, 'idle');
	});

	test('AC-10: Wetter-Metrik, binnen 700 ms Versandzeit ⇒ beide im Backend, nach Re-Hydration beide sichtbar', async () => {
		const p = await panel();
		p.metrikAendern();
		p.versandzeitAendern();
		await leeren(p.a.ctl);
		beideImBackend();
		assert.equal(p.a.ctl.state, 'idle');
		const neu = await neuGeladen();
		assert.equal(neu.wm.inst.u.telegramKurzform, true, 'UI nach Re-Hydration: Wetter-Metrik fehlt');
		assert.equal((neu.versand.inst.u.reportConfig as Record<string, unknown>).morning_time, VERSANDZEIT);
	});

	test('AC-11: Versandzeit, binnen 700 ms Wetter-Metrik ⇒ beide im Backend, nach Re-Hydration beide sichtbar', async () => {
		const p = await panel();
		p.versandzeitAendern();
		p.metrikAendern();
		await leeren(p.a.ctl);
		beideImBackend();
		assert.equal(p.a.ctl.state, 'idle');
		const neu = await neuGeladen();
		assert.equal(neu.wm.inst.u.telegramKurzform, true);
		assert.equal((neu.versand.inst.u.reportConfig as Record<string, unknown>).morning_time, VERSANDZEIT, 'UI nach Re-Hydration: Versandzeit fehlt');
	});

	test('AC-13: ungespeicherte Versandzeit ueberlebt Wetter-PUT + Re-Hydration und wird danach gespeichert', async () => {
		const p = await panel();
		p.metrikAendern();
		p.versandzeitAendern();
		await laufendenAbschliessen(p.a.ctl);
		assert.equal(dcStand().telegram_kurzform, true, 'der Wetter-PUT muss abgeschlossen sein, waehrend die Versandzeit noch aussteht');
		// Re-Hydration: die Seite reicht die Server-Antwort als neuen `trip` an beide Bausteine.
		const antwort = p.a.updates.at(-1);
		assert.ok(antwort, 'Messaufbau: der Wetter-Weg meldet seine Server-Antwort nach oben (onTripUpdate)');
		p.wm.inst.u.trip = antwort;
		p.versand.inst.u.trip = antwort;
		assert.equal((p.versand.inst.u.reportConfig as Record<string, unknown>).morning_time, VERSANDZEIT, 'Re-Hydration hat die Versand-Eingabe ueberschrieben');
		await leeren(p.a.ctl);
		assert.equal(rcStand().morning_time, VERSANDZEIT, 'die Versandzeit wurde nach der Re-Hydration nicht mehr gespeichert');
		assert.equal(dcStand().telegram_kurzform, true);
	});

	test('AC-13 (umgekehrt): ungespeicherte Wetter-Metrik ueberlebt Versand-PUT + Re-Hydration und wird danach gespeichert', async () => {
		const p = await panel();
		p.versandzeitAendern();
		p.metrikAendern();
		await laufendenAbschliessen(p.a.ctl);
		assert.equal(rcStand().morning_time, VERSANDZEIT, 'der Versand-PUT muss abgeschlossen sein, waehrend die Wetter-Metrik noch aussteht');
		const antwort = p.a.updates.at(-1);
		assert.ok(antwort, 'Messaufbau: der Versand-Weg meldet seine Server-Antwort nach oben (onTripUpdate)');
		p.wm.inst.u.trip = antwort;
		p.versand.inst.u.trip = antwort;
		assert.equal(p.wm.inst.u.telegramKurzform, true, 'Re-Hydration hat die Wetter-Eingabe ueberschrieben');
		await leeren(p.a.ctl);
		assert.equal(dcStand().telegram_kurzform, true, 'die Wetter-Metrik wurde nach der Re-Hydration nicht mehr gespeichert');
	});

	test('AC-14: WeatherMetricsTab allein — Auto-Save und nur-report_config-Save binnen 700 ms ⇒ beide im Backend', async () => {
		const a = P.neuerAufbau();
		offeneController.push(a.ctl);
		const wm = await P.wetterMetrikenReiter(a);
		wm.inst.u.telegramKurzform = true;
		wm.metrikenSpeichern();
		wm.reportConfigSpeichern({ day_window_start_hour: 6 });
		await leeren(a.ctl);
		assert.ok(
			puts().some((p) => /\/weather-config$/.test(p.path)),
			'der Auto-Save-Weg (/weather-config) wurde vom report_config-Weg verdraengt'
		);
		assert.equal(dcStand().telegram_kurzform, true, 'Telegram-Kurzform (Auto-Save-Weg) fehlt auf dem Server');
		assert.equal(rcStand().day_window_start_hour, 6, 'Tagesfenster (report_config-Weg) fehlt auf dem Server');
		assert.equal(a.ctl.state, 'idle');
	});

	test('AC-15: erster Schreiber scheitert (500), zweiter klappt ⇒ Anzeige „Fehler", nicht „Gespeichert"', async () => {
		const p = await panel();
		let wetterPutVersucht = false;
		fehler = (m, path) => m === 'PUT' && /\/weather-config$/.test(path) && (wetterPutVersucht = true);
		p.metrikAendern();
		p.versandzeitAendern();
		await leeren(p.a.ctl);
		fehler = null;
		assert.equal(wetterPutVersucht, true, 'der Wetter-Schreiber wurde nie gesendet (vom Versand verdraengt)');
		assert.equal(rcStand().morning_time, VERSANDZEIT, 'Messaufbau: der zweite Schreiber war erfolgreich');
		assert.equal(p.a.ctl.state, 'error', 'der Fehlschlag des Wetter-Schreibers wurde vom Versand-Erfolg ueberdeckt');
		assert.equal(p.a.ctl.savedAt, null);
	});

	test('AC-15: beide Schreiber erfolgreich ⇒ „Gespeichert"', async () => {
		const p = await panel();
		p.metrikAendern();
		p.versandzeitAendern();
		await leeren(p.a.ctl);
		beideImBackend();
		assert.equal(p.a.ctl.state, 'idle');
		assert.ok(p.a.ctl.savedAt instanceof Date);
	});

	// Adversary F001 (Gegenstueck zum Vergleich): Zuruecksetzen binnen 700 ms darf den
	// ausstehenden Slot des ANDEREN Besitzers nicht mitnehmen; Endstand = zurueckgesetzter Wert.
	test('F001 Versand: aendern und binnen 700 ms zuruecksetzen ⇒ Wetter-Slot gesendet, Versandzeit unveraendert', async () => {
		const p = await panel();
		p.metrikAendern();
		p.versandzeitAendern();
		p.versand.aendern({ morning_time: '07:00:00' });
		await leeren(p.a.ctl);
		assert.equal(dcStand().telegram_kurzform, true, 'der Wetter-Slot des anderen Besitzers kam nicht an');
		assert.equal(rcStand().morning_time, '07:00:00', 'die zurueckgenommene Versandzeit steht auf dem Server');
		assert.equal(p.a.ctl.hasPending, false);
		assert.equal(p.a.ctl.state, 'idle');
	});

	test('F001 Wetter: aendern und binnen 700 ms zuruecksetzen ⇒ Versand-Slot gesendet, Metrik unveraendert', async () => {
		const p = await panel();
		p.versandzeitAendern();
		p.metrikAendern();
		p.wm.inst.u.telegramKurzform = false;
		p.wm.metrikenSpeichern();
		await leeren(p.a.ctl);
		assert.equal(rcStand().morning_time, VERSANDZEIT, 'der Versand-Slot des anderen Besitzers kam nicht an');
		assert.equal(dcStand().telegram_kurzform, false, 'die zurueckgenommene Metrik steht auf dem Server');
		assert.equal(p.a.ctl.hasPending, false);
		assert.equal(p.a.ctl.state, 'idle');
	});
});

// ─────────────────────────── context = vergleich (Ortsvergleich-Hub) ───────────────────────────

const ID = 'cp-1743-panel';
const NEUE_METRIK = 'gust_max_kmh';

describe('context vergleich (Ortsvergleich-Hub): Wetter-Metriken und Versand an einem Controller', () => {
	let server: GoMergeServer;
	let wetterPutGesehen = false;

	beforeEach(async () => {
		clearEtagRegistry();
		fehler = null;
		wetterPutGesehen = false;
		server = createGoMergeServer({ [ID]: vollerVergleich(ID) });
		server.install();
		fehlerSchicht();
		await api.get(`/api/compare/presets/${ID}`);
	});
	afterEach(async () => {
		await aufraeumen();
		server.restore();
	});

	const puts = () => server.mitschnitt.filter((e) => e.method === 'PUT');
	const aktiveMetriken = (body: unknown): string[] =>
		(((body as Record<string, unknown>)?.display_config as Record<string, unknown>)?.active_metrics as string[]) ?? [];

	/** EIN wizardState, EIN Controller, EINE Queue, EINE Basis — wie CompareTabs. */
	function panel() {
		let basis = vollerVergleich(ID) as unknown as ComparePreset;
		const zustand: Record<string, unknown> = {
			...(hydrateVersandFieldsFromPreset(basis) as unknown as Record<string, unknown>),
			...hydrierterWetterWs(basis)
		};
		const ctl = createController(ID);
		offeneController.push(ctl);
		const queue = createPutQueue();
		const gemeinsam = {
			client: api,
			zustand,
			preset: () => basis,
			enqueueHubWrite: <T>(fn: () => Promise<T>) => queue.enqueue(fn),
			onCompareUpdate: (p: ComparePreset) => {
				basis = p;
			},
			saveController: ctl
		};
		const wetter = erstelleWetterMetrikenVergleichSpeicherung(gemeinsam as never);
		const versand = erstelleVersandVergleichSpeicherung(gemeinsam as never);
		const wb = wetterMetrikenBedienung(zustand);
		const vb = versandBedienung(zustand);
		return {
			zustand,
			ctl,
			basis: () => basis,
			metrikAendern() {
				wb.toggleMetric(NEUE_METRIK);
				wetter.aenderungMelden();
			},
			versandzeitAendern() {
				vb.setMorgenZeit('07:15');
				versand.aenderungMelden();
			},
			/** dieselbe Metrik-Geste noch einmal ⇒ Stand wieder gleich der Basis */
			metrikZuruecksetzen() {
				wb.toggleMetric(NEUE_METRIK);
				wetter.aenderungMelden();
			},
			/** Versandzeit zurueck auf den Ausgangswert der Basis (06:30) */
			versandzeitZuruecksetzen() {
				vb.setMorgenZeit('06:30');
				versand.aenderungMelden();
			}
		};
	}

	function beideImBackend(): void {
		assert.ok(
			puts().some((p) => p.status === 200 && aktiveMetriken(p.anfrage).includes(NEUE_METRIK)),
			`kein PUT traegt die Wetter-Metrik-Aenderung (Koerper: ${JSON.stringify(puts().map((p) => p.anfrage))})`
		);
		assert.ok(
			puts().some((p) => p.status === 200 && String((p.anfrage as Record<string, unknown>)?.morning_time ?? '').startsWith('07:15')),
			'kein PUT traegt die Versandzeit'
		);
		const s = server.stand(ID);
		assert.ok(aktiveMetriken(s).includes(NEUE_METRIK), 'Wetter-Metrik-Aenderung fehlt auf dem Server');
		assert.ok(String(s.morning_time).startsWith('07:15'), 'Versandzeit fehlt auf dem Server');
	}

	/** Re-Hydration aus dem Server-Stand, wie die Hydrations-Effekte des Hubs. */
	function neuGeladen() {
		const s = server.stand(ID) as unknown as ComparePreset;
		return { versand: hydrateVersandFieldsFromPreset(s), wetter: hydrierterWetterWs(s) };
	}

	test('Vorbedingung (Gegenprobe): jede Aenderung allein kommt an', async () => {
		const p = panel();
		p.metrikAendern();
		await leeren(p.ctl);
		p.versandzeitAendern();
		await leeren(p.ctl);
		beideImBackend();
		assert.equal(p.ctl.state, 'idle');
	});

	test('AC-10: Wetter-Metrik, binnen 700 ms Versandzeit ⇒ beide im Backend, nach Re-Hydration beide sichtbar', async () => {
		const p = panel();
		p.metrikAendern();
		p.versandzeitAendern();
		await leeren(p.ctl);
		beideImBackend();
		assert.equal(p.ctl.state, 'idle');
		const neu = neuGeladen();
		assert.ok((neu.wetter.activeMetricKeys as string[]).includes(NEUE_METRIK), 'UI nach Re-Hydration: Wetter-Metrik fehlt');
		assert.equal(neu.versand.morningTime, '07:15');
	});

	test('AC-11: Versandzeit, binnen 700 ms Wetter-Metrik ⇒ beide im Backend, nach Re-Hydration beide sichtbar', async () => {
		const p = panel();
		p.versandzeitAendern();
		p.metrikAendern();
		await leeren(p.ctl);
		beideImBackend();
		assert.equal(p.ctl.state, 'idle');
		const neu = neuGeladen();
		assert.ok((neu.wetter.activeMetricKeys as string[]).includes(NEUE_METRIK));
		assert.equal(neu.versand.morningTime, '07:15', 'UI nach Re-Hydration: Versandzeit fehlt');
	});

	test('AC-13: ungespeicherte Versandzeit ueberlebt Wetter-PUT (neue Basis) und wird danach gespeichert', async () => {
		const p = panel();
		p.metrikAendern();
		p.versandzeitAendern();
		await laufendenAbschliessen(p.ctl);
		assert.ok(
			aktiveMetriken(server.stand(ID)).includes(NEUE_METRIK),
			'der Wetter-PUT muss abgeschlossen sein, waehrend die Versandzeit noch aussteht'
		);
		assert.ok(aktiveMetriken(p.basis()).includes(NEUE_METRIK), 'Messaufbau: die Server-Antwort ist neue Basis');
		assert.equal(p.zustand.morningTime, '07:15', 'die neue Basis hat die Versand-Eingabe ueberschrieben');
		await leeren(p.ctl);
		assert.ok(String(server.stand(ID).morning_time).startsWith('07:15'), 'die Versandzeit wurde danach nicht mehr gespeichert');
	});

	test('AC-13 (umgekehrt): ungespeicherte Wetter-Metrik ueberlebt Versand-PUT (neue Basis) und wird danach gespeichert', async () => {
		const p = panel();
		p.versandzeitAendern();
		p.metrikAendern();
		await laufendenAbschliessen(p.ctl);
		assert.ok(
			String(server.stand(ID).morning_time).startsWith('07:15'),
			'der Versand-PUT muss abgeschlossen sein, waehrend die Wetter-Metrik noch aussteht'
		);
		assert.ok((p.zustand.activeMetricKeys as string[]).includes(NEUE_METRIK), 'die neue Basis hat die Wetter-Eingabe ueberschrieben');
		await leeren(p.ctl);
		assert.ok(aktiveMetriken(server.stand(ID)).includes(NEUE_METRIK), 'die Wetter-Metrik wurde danach nicht mehr gespeichert');
	});

	test('AC-15: erster Schreiber scheitert (500), zweiter klappt ⇒ Anzeige „Fehler", nicht „Gespeichert"', async () => {
		const p = panel();
		// der PUT des Wetter-Schreibers (traegt active_metrics) scheitert
		fehler = (m, _p, body) => m === 'PUT' && body.includes('active_metrics') && (wetterPutGesehen = true);
		p.metrikAendern();
		p.versandzeitAendern();
		await leeren(p.ctl);
		fehler = null;
		assert.equal(wetterPutGesehen, true, 'der Wetter-Schreiber wurde nie gesendet (vom Versand verdraengt)');
		assert.ok(String(server.stand(ID).morning_time).startsWith('07:15'), 'Messaufbau: der zweite Schreiber war erfolgreich');
		assert.equal(p.ctl.state, 'error', 'der Fehlschlag des Wetter-Schreibers wurde vom Versand-Erfolg ueberdeckt');
		assert.equal(p.ctl.savedAt, null);
	});

	// Adversary F001: der Besitzer beim Verwerfen wirkt am AUFRUFER. Ohne Besitzer
	// (`cancel()`) laesst der Controller den eigenen Slot stehen — er gilt weiter als
	// ausstehend (`hasPending`), obwohl der Nutzer seine Aenderung zurueckgenommen hat.
	test('F001 Versand: aendern und binnen 700 ms zuruecksetzen ⇒ eigener Slot verworfen, Wetter-Slot trotzdem gesendet', async () => {
		const p = panel();
		p.metrikAendern(); // Besitzer „wetter-metriken" steht aus
		p.versandzeitAendern(); // Besitzer „versand" — sendet den Wetter-Slot zuerst
		p.versandzeitZuruecksetzen();
		assert.equal(p.ctl.hasPending, false, 'der zurueckgenommene Versand-Slot steht noch aus (cancel ohne Besitzer?)');
		await leeren(p.ctl);
		assert.ok(aktiveMetriken(server.stand(ID)).includes(NEUE_METRIK), 'der Wetter-Slot des anderen Besitzers kam nicht an');
		assert.ok(String(server.stand(ID).morning_time).startsWith('06:30'), 'die zurueckgenommene Versandzeit wurde gespeichert');
		assert.ok(
			!puts().some((x) => String((x.anfrage as Record<string, unknown>)?.morning_time ?? '').startsWith('07:15')),
			'ein PUT traegt die zurueckgenommene Versandzeit'
		);
		assert.equal(p.ctl.state, 'idle');
	});

	test('F001 Wetter: aendern und binnen 700 ms zuruecksetzen ⇒ eigener Slot verworfen, Versand-Slot trotzdem gesendet', async () => {
		const p = panel();
		p.versandzeitAendern(); // Besitzer „versand" steht aus
		p.metrikAendern(); // Besitzer „wetter-metriken" — sendet den Versand-Slot zuerst
		p.metrikZuruecksetzen();
		assert.equal(p.ctl.hasPending, false, 'der zurueckgenommene Wetter-Slot steht noch aus (cancel ohne Besitzer?)');
		await leeren(p.ctl);
		assert.ok(String(server.stand(ID).morning_time).startsWith('07:15'), 'der Versand-Slot des anderen Besitzers kam nicht an');
		assert.ok(!aktiveMetriken(server.stand(ID)).includes(NEUE_METRIK), 'die zurueckgenommene Metrik wurde gespeichert');
		assert.ok(
			!puts().some((x) => aktiveMetriken(x.anfrage).includes(NEUE_METRIK)),
			'ein PUT traegt die zurueckgenommene Metrik'
		);
		assert.equal(p.ctl.state, 'idle');
	});

	test('F001 ohne fremden Slot: aendern und zuruecksetzen ⇒ nichts aussteht, kein PUT, Anzeige idle', async () => {
		const p = panel();
		p.versandzeitAendern();
		p.versandzeitZuruecksetzen();
		assert.equal(p.ctl.hasPending, false, 'Versand: zurueckgenommener Slot steht noch aus');
		p.metrikAendern();
		p.metrikZuruecksetzen();
		assert.equal(p.ctl.hasPending, false, 'Wetter: zurueckgenommener Slot steht noch aus');
		assert.equal(p.ctl.state, 'idle');
		await tick(800);
		assert.equal(puts().length, 0, 'nach dem Zuruecksetzen wurde trotzdem gespeichert');
		assert.equal(p.ctl.savedAt, null, 'ein folgenloser Speichervorgang meldet „Gespeichert"');
	});
});
