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
// Mechanik gibt es nicht mehr. Beide Regressionen liefen deshalb an der echten
// Orchestrierung samt echtem Speicher-Controller; seit #3389 (toter
// Versand-Speicherer entfernt) am lebenden Alarme-Speicherer. Die
// Fehlerbehandlung liegt dort, wo sie im Produktivpfad liegt: die SaveFn
// wirft weiter, der Controller fängt.
//
// Spec: docs/specs/modules/rework_2276_s5_versand.md — AC-1, AC-3;
//       docs/specs/modules/rework_3389_tote_exporte.md
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
import { createGoMergeServer } from '../../shared/__tests__/goMergeServerPruefstand.ts';
import type { ComparePreset } from '../../../types.ts';
import type { PutClient } from '../../shared/tripSpeicherung.ts';
import { createPutQueue, buildToggleActivePutPayload } from '../compareHubPersistenz.ts';
import { hydrateAlarmFieldsFromPreset } from '../compareHubHydration.ts';
import { erstelleAlarmeVergleichSpeicherung } from '../../shared/alarmeVergleichSpeicherung.ts';
import { createController, makePreset } from '../../shared/__tests__/versandVergleichPruefstand.ts';

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

// #3389: F002/F003 laufen seit dem Wegfall des toten Versand-Speicherers am lebenden
// Alarme-Speicherer (dieselben Zusicherungen: Basis-Rückmeldung vor dem Toggle-PUT,
// diff-basierter Rollback mit Baseline bei Queue-Ausführung).
describe('F002-Integration: Alarme-Speicherung + nachfolgender Toggle-Active-PUT', () => {
	test('Toggle-PUT nach Alarme-PUT sieht den aktualisierten currentPreset-Stand — kein stiller Datenverlust', async () => {
		let currentPreset: ComparePreset = makePreset(PRESET_ID);
		const zustand: Record<string, unknown> = {};
		hydrateAlarmFieldsFromPreset(zustand, currentPreset, []);
		const ctl = createController(PRESET_ID);
		const queue = createPutQueue();
		// Seit #2375 sendet der Toggle nur { schedule, previous_schedule } — das
		// Ueberleben der Alarme-Aenderung entscheidet der Server-Abgleich, also
		// laeuft der Test gegen den Ersatz-Server, der wie der Go-Handler zusammenfuehrt
		// (der fakeTripServer ersetzt den gespeicherten Rumpf komplett).
		const goServer = createGoMergeServer({ [PRESET_ID]: currentPreset as unknown as Record<string, unknown> });
		goServer.install();
		try {
			const alarme = erstelleAlarmeVergleichSpeicherung({
				client: api,
				zustand,
				preset: () => currentPreset,
				enqueueHubWrite: (fn) => queue.enqueue(fn),
				onCompareUpdate: (p: ComparePreset) => {
					currentPreset = p;
				},
				saveController: ctl
			});

			// 1) Nutzer schaltet den Radar-Alarm an.
			assert.strictEqual(zustand.radarAlertEnabled, false, 'Vorbedingung: Radar-Alarm aus');
			zustand.radarAlertEnabled = true;
			alarme.aenderungMelden();
			await ctl.flush();
			assert.strictEqual(goServer.putRuempfe().length, 1, 'Vorbedingung: der Alarme-PUT ist raus');

			// 2) Direkt danach klickt der Nutzer „Pausieren" — der Payload-Bau passiert
			// innerhalb des enqueueten fn.
			currentPreset = await queue.enqueue(async () => {
				const { url, body } = buildToggleActivePutPayload(currentPreset, 'manual', 'daily');
				return api.put<ComparePreset>(url, body);
			});

			assert.deepStrictEqual(goServer.putRuempfe()[1], { schedule: 'manual', previous_schedule: 'daily' });
			assert.strictEqual(
				currentPreset.radar_alert_enabled,
				true,
				'die Radar-Alarm-Aenderung ueberlebt den nachfolgenden Toggle-PUT'
			);
			const stand = goServer.stand(PRESET_ID);
			assert.strictEqual(stand.radar_alert_enabled, true, 'Server-Zustand darf die Alarme-Aenderung nicht verlieren');
			assert.strictEqual(stand.schedule, 'manual');
		} finally {
			goServer.restore();
		}
	});
});

describe('F003-Regression: die Rollback-Baseline wird bei Queue-AUSFUEHRUNG erfasst, nicht beim Planen', () => {
	test('Edit A erfolgreich, Edit B (waehrend A noch offen) schlaegt fehl — der Rollback von B darf Edit A nicht verlieren', async () => {
		let currentPreset: ComparePreset = makePreset(PRESET_ID, { radar_alert_enabled: false });
		const zustand: Record<string, unknown> = {};
		hydrateAlarmFieldsFromPreset(zustand, currentPreset, []);
		const ausgangOfficialWarnings = zustand.officialWarningsEnabled;
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

		const alarme = erstelleAlarmeVergleichSpeicherung({
			client,
			zustand,
			preset: () => currentPreset,
			enqueueHubWrite: (fn) => queue.enqueue(fn),
			onCompareUpdate: (p: ComparePreset) => {
				currentPreset = p;
			},
			saveController: ctl
		});

		// Edit A: Radar-Alarm an.
		zustand.radarAlertEnabled = true;
		alarme.aenderungMelden();
		const lauf = ctl.flush();
		await gestartet;

		// Edit B: SOFORT danach amtliche Warnungen umschalten, WAEHREND Edit A noch offen ist.
		zustand.officialWarningsEnabled = !(ausgangOfficialWarnings as boolean);
		alarme.aenderungMelden();

		torOeffnen();
		await lauf.catch(() => {
			/* der Fehlschlag von Edit B ist Teil des Szenarios */
		});

		assert.strictEqual(ctl.state, 'error', 'der gescheiterte Edit B muss am Controller sichtbar werden');
		ctl.cancel(); // etwaigen Rest-Eintrag im Speicher-Platz räumen

		assert.strictEqual(
			(server.storedBody(PRESET_ID) as Record<string, unknown>).radar_alert_enabled,
			true,
			'Edit A muss trotz spaeter fehlschlagendem Edit B auf dem Server persistiert bleiben'
		);
		assert.strictEqual(
			zustand.radarAlertEnabled,
			true,
			'F003-Regression: der Rollback von Edit B darf Edit A NICHT aus der Anzeige entfernen'
		);
		assert.strictEqual(
			zustand.officialWarningsEnabled,
			ausgangOfficialWarnings,
			'Edit B selbst wird auf den (Edit-A-)Stand zurueckgerollt'
		);
	});
});
