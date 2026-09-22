// TDD — Hub-PUT-Queue: ALLE Schreibpfade des Ortsvergleich-Hubs laufen
// serialisiert über EINE Kette (`createPutQueue`, compareHubPersistenz.ts).
//
// Ursprung: Issue #1256 Scheibe 7 Fix-Loop 1 (F002/F003, Adversary CRITICAL) —
// zwei unsynchronisierte Hub-PUT-Pfade (Versand-Änderung + Aktivieren/
// Pausieren-Klick) konnten parallel laufen und einander mit einer veralteten
// `currentPreset`-Baseline still überschreiben.
//
// 🔴 REWORK für Issue #2276 Scheibe S5 (Epic #2345), kein Import-Swap: die
// F002-/F003-Blöcke bauten `handleVersandCommit`/`lastPersistedVersand-
// Snapshot` aus CompareTabs.svelte INTERN nach (eigene `commit()`-Hülle mit
// eigenem try/catch). Mit S5 speichert der Versand-Reiter selbst; diese
// Mechanik gibt es nicht mehr. Beide Regressionen sind deshalb auf die echte
// Orchestrierung `erstelleVersandVergleichSpeicherung()` samt echtem
// Speicher-Controller umgestellt — sonst prüfte der Test seine eigene Hülle
// statt des Prüflings. Die Fehlerbehandlung wandert damit dorthin, wo sie im
// Produktivpfad liegt: die SaveFn wirft weiter, der Controller fängt.
//
// Spec: docs/specs/modules/rework_2276_s5_versand.md — AC-1, AC-3
//
// Zielschnittstelle (existiert noch NICHT → RED per ERR_MODULE_NOT_FOUND):
//   shared/versandVergleichSpeicherung.ts → erstelleVersandVergleichSpeicherung
//
// Reine Funktions-/Transporttests gegen `fakeTripServer.ts`, kein Mock, kein
// DOM/Browser — lauffähig unter node --experimental-strip-types.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/compare/__tests__/hub_put_queue.test.ts

import { describe, test, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../types.ts';
import type { PutClient } from '../../shared/tripSpeicherung.ts';
import { createPutQueue, buildToggleActivePutPayload } from '../compareHubPersistenz.ts';
import { erstelleVersandVergleichSpeicherung } from '../../shared/versandVergleichSpeicherung.ts';
import {
	createController,
	hydrierterWiz,
	makePreset
} from '../../shared/__tests__/versandVergleichPruefstand.ts';

const PRESET_ID = 'cmp-42';

describe('createPutQueue: Serialisierung', () => {
	test('zwei ueberlappend enqueuete fns laufen strikt sequenziell (Beweis per Zeitfolge)', async () => {
		const queue = createPutQueue();
		const order: string[] = [];
		let firstResolved = false;

		const p1 = queue.enqueue(async () => {
			order.push('start-1');
			await new Promise((r) => setTimeout(r, 15));
			firstResolved = true;
			order.push('end-1');
		});
		const p2 = queue.enqueue(async () => {
			// Beweis: das zweite fn darf erst NACH dem Resolve des ersten starten,
			// obwohl beide synchron direkt hintereinander enqueued wurden.
			assert.strictEqual(firstResolved, true, 'zweites fn lief bereits vor Resolve des ersten — keine Serialisierung');
			order.push('start-2');
		});

		await Promise.all([p1, p2]);
		assert.deepStrictEqual(order, ['start-1', 'end-1', 'start-2']);
	});

	test('Fehler im ersten fn bricht die Kette nicht ab — zweites fn laeuft trotzdem', async () => {
		const queue = createPutQueue();
		const p1 = queue.enqueue(async () => {
			throw new Error('PUT fehlgeschlagen');
		});
		let secondRan = false;
		const p2 = queue.enqueue(async () => {
			secondRan = true;
			return 'ok';
		});

		await assert.rejects(p1, /PUT fehlgeschlagen/);
		assert.strictEqual(await p2, 'ok');
		assert.strictEqual(secondRan, true);
	});

	test('drei enqueuete fns behalten die Aufrufreihenfolge bei (kein Interleaving)', async () => {
		const queue = createPutQueue();
		const order: number[] = [];
		const delays = [10, 1, 5];
		const tasks = delays.map((ms, i) =>
			queue.enqueue(async () => {
				await new Promise((r) => setTimeout(r, ms));
				order.push(i);
			})
		);
		await Promise.all(tasks);
		assert.deepStrictEqual(order, [0, 1, 2]);
	});
});

let server: FakeTripServer;

beforeEach(() => {
	clearEtagRegistry();
	server = createFakeTripServer();
	server.install();
});

afterEach(() => server.restore());

const puts = () => server.calls.filter((c) => c.method === 'PUT');

describe('F002-Integration: Versand-Speicherung + nachfolgender Toggle-Active-PUT', () => {
	test('Toggle-PUT nach Versand-PUT sieht den aktualisierten currentPreset-Stand — kein stiller Datenverlust', async () => {
		let currentPreset: ComparePreset = makePreset(PRESET_ID);
		const wiz = hydrierterWiz(currentPreset);
		const ctl = createController(PRESET_ID);
		const queue = createPutQueue();
		const versand = erstelleVersandVergleichSpeicherung({
			client: api,
			zustand: wiz,
			preset: () => currentPreset,
			enqueueHubWrite: (fn) => queue.enqueue(fn),
			onCompareUpdate: (p: ComparePreset) => {
				currentPreset = p;
			},
			saveController: ctl
		});

		// 1) Nutzer klickt „Bis auf Weiteres" im Laufzeit-Control → wiz.endDate = null.
		wiz.endDate = null;
		versand.aenderungMelden();
		await ctl.flush();
		assert.strictEqual(puts().length, 1, 'Vorbedingung: der Versand-PUT ist raus');

		// 2) Direkt danach klickt der Nutzer „Pausieren" — der Payload-Bau passiert
		// innerhalb des enqueueten fn und sieht dadurch den bereits über
		// onCompareUpdate aufgefrischten currentPreset aus Schritt 1.
		currentPreset = await queue.enqueue(async () => {
			const { url, body } = buildToggleActivePutPayload(currentPreset, 'manual', 'daily');
			return api.put<ComparePreset>(url, body);
		});

		assert.strictEqual(
			currentPreset.end_date,
			'',
			'End-Datum-Loeschung („Bis auf Weiteres") ueberlebt den nachfolgenden Toggle-PUT'
		);
		const stand = server.storedBody(PRESET_ID) as Record<string, unknown>;
		assert.strictEqual(stand.end_date, '', 'Server-Zustand darf die Versand-Aenderung nicht verlieren');
		assert.strictEqual(stand.schedule, 'manual');
	});
});

describe('F003-Regression: die Rollback-Baseline wird bei Queue-AUSFUEHRUNG erfasst, nicht beim Planen', () => {
	test('Edit A erfolgreich, Edit B (waehrend A noch offen) schlaegt fehl — der Rollback von B darf Edit A nicht verlieren', async () => {
		let currentPreset: ComparePreset = makePreset(PRESET_ID, { morning_time: '06:00:00', send_sms: false });
		const wiz = hydrierterWiz(currentPreset);
		const ctl = createController(PRESET_ID);
		const queue = createPutQueue();

		// Deterministische Steuerung statt zeit-basiertem Race: der erste PUT
		// haengt in einem Tor fest, bis der Test Edit B bereits angestossen hat.
		// Jeder weitere PUT scheitert — das ist Edit B.
		let torOeffnen!: () => void;
		const tor = new Promise<void>((r) => {
			torOeffnen = r;
		});
		let aGestartet!: () => void;
		const gestartet = new Promise<void>((r) => {
			aGestartet = r;
		});
		let nr = 0;
		const client: PutClient = {
			put: async (url: string, body: unknown, init?: RequestInit) => {
				nr += 1;
				if (nr === 1) {
					aGestartet();
					await tor;
					return api.put(url, body as ComparePreset, init);
				}
				throw Object.assign(new Error('Netzwerkfehler (simuliert)'), { status: 500 });
			}
		} as PutClient;

		const versand = erstelleVersandVergleichSpeicherung({
			client,
			zustand: wiz,
			preset: () => currentPreset,
			enqueueHubWrite: (fn) => queue.enqueue(fn),
			onCompareUpdate: (p: ComparePreset) => {
				currentPreset = p;
			},
			saveController: ctl
		});

		// Edit A: Morgen-Uhrzeit aendern.
		wiz.morningTime = '07:30';
		versand.aenderungMelden();
		const lauf = ctl.flush();
		await gestartet;

		// Edit B: SOFORT danach SMS umschalten, WAEHREND Edit A noch offen ist.
		wiz.sendSms = true;
		versand.aenderungMelden();

		torOeffnen();
		await lauf.catch(() => {
			/* der Fehlschlag von Edit B ist Teil des Szenarios */
		});

		assert.strictEqual(ctl.state, 'error', 'der gescheiterte Edit B muss am Controller sichtbar werden');
		ctl.cancel(); // etwaigen Rest-Eintrag im Speicher-Platz räumen

		assert.strictEqual(
			(server.storedBody(PRESET_ID) as Record<string, unknown>).morning_time,
			'07:30:00',
			'Edit A muss trotz spaeter fehlschlagendem Edit B auf dem Server persistiert bleiben'
		);
		assert.strictEqual(
			wiz.morningTime,
			'07:30',
			'F003-Regression: der Rollback von Edit B darf Edit A NICHT aus der Anzeige entfernen'
		);
		assert.strictEqual(wiz.sendSms, false, 'Edit B selbst wird auf den (Edit-A-)Stand zurueckgerollt');
	});
});
