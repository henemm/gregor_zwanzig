// TDD — Issue #1256 Scheibe 7 Fix-Loop 1 (F002, Adversary CRITICAL).
//
// Spec: docs/specs/modules/issue_1256_compare_ui_rewire.md § Scheibe 7.
// Reproduktion des urspruenglichen Bugs: zwei unsynchronisierte Hub-PUT-Pfade
// (Versand-Aenderung + Aktivieren/Pausieren-Klick) im selben Versand-Tab
// konnten parallel laufen und einander mit einer veralteten `currentPreset`-
// Baseline still ueberschreiben (siehe
// scratchpad/probe_race.mjs des Adversary-Fix-Loops).
//
// `createPutQueue()` (compareHubWizardBridge.ts) serialisiert ALLE
// Hub-PUT-Pfade auf eine gemeinsame Kette. Reine Funktionstests, kein Mock,
// kein DOM/Browser — lauffaehig unter node --experimental-strip-types.

import { describe, test } from 'node:test';
import assert from 'node:assert/strict';
import type { ComparePreset } from '../../../types.ts';
import {
	createPutQueue,
	hydrateVersandFieldsFromPreset,
	flushPendingVersandSave,
	buildToggleActivePutPayload
} from '../compareHubWizardBridge.ts';

function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cmp-42',
		name: 'Skigebiete Tirol',
		location_ids: ['loc-1', 'loc-2', 'loc-3'],
		schedule: 'daily',
		weekday: 0,
		profil: 'wintersport',
		hour_from: 6,
		hour_to: 9,
		empfaenger: ['urlauber@example.com'],
		forecast_hours: 48,
		letzter_versand: undefined,
		top_ort_letzter_versand: null,
		created_at: '2026-01-01T00:00:00Z',
		corridors: [],
		send_telegram: true,
		send_sms: false,
		morning_enabled: true,
		morning_time: '06:30:00',
		evening_enabled: true,
		evening_time: '19:15:00',
		end_date: '2026-08-01',
		display_config: {},
		...overrides
	};
}

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

describe('F002-Integration: Versand-Flush + nachfolgender Toggle-Payload-Bau', () => {
	test('Toggle-PUT nach Versand-PUT sieht den aktualisierten currentPreset-Stand — kein stiller Datenverlust', async () => {
		const queue = createPutQueue();
		// Server-Zustand mit gesetztem End-Datum.
		let serverPreset: ComparePreset = makePreset({ end_date: '2026-08-01' });
		// Simulierter PUT-Responder (kein Mock-Framework): merged den Body wie
		// das echte Backend und liefert das gespeicherte Preset zurueck.
		async function simulatedPut(body: ComparePreset): Promise<ComparePreset> {
			serverPreset = { ...serverPreset, ...body };
			return serverPreset;
		}

		let currentPreset = serverPreset;

		// 1) Nutzer klickt "Bis auf Weiteres" im Laufzeit-Control -> wizardState.endDate = null.
		const before = hydrateVersandFieldsFromPreset(currentPreset);
		const currentVersand = { ...before, endDate: null };

		// 2) handleVersandCommit() — Payload-Bau MUSS innerhalb des enqueueten
		// fn passieren (erst dort currentPreset lesen), analog CompareTabs.svelte.
		currentPreset = await queue.enqueue(async () => {
			const payload = flushPendingVersandSave(currentPreset, currentVersand, before);
			assert.ok(payload, 'End-Datum-Aenderung muss einen PUT-Payload liefern');
			return simulatedPut(payload.body);
		});

		// 3) Direkt danach klickt der Nutzer "Pausieren" — Payload-Bau ebenfalls
		// innerhalb des enqueueten fn, sieht dadurch den bereits aktualisierten
		// currentPreset aus Schritt 2 (nicht mehr den Stand vor dem Versand-PUT).
		currentPreset = await queue.enqueue(async () => {
			const { body } = buildToggleActivePutPayload(currentPreset, 'manual', 'daily');
			return simulatedPut(body);
		});

		assert.strictEqual(
			currentPreset.end_date,
			'',
			'End-Datum-Loeschung ("Bis auf Weiteres") ueberlebt den nachfolgenden Toggle-PUT'
		);
		assert.strictEqual(serverPreset.end_date, '', 'Server-Zustand darf die Versand-Aenderung nicht verlieren');
	});
});

describe('F003-Regression: Rollback-Baseline muss bei Queue-AUSFUEHRUNG erfasst werden, nicht beim Funktionsaufruf', () => {
	test('Edit A erfolgreich, Edit B (waehrend A noch offen) schlaegt fehl — Rollback von B darf Edit A nicht verlieren', async () => {
		const queue = createPutQueue();
		let serverPreset: ComparePreset = makePreset({ morning_time: '06:00:00', send_sms: false });

		// Deterministische Steuerung statt Zeit-basiertem Race (kein setTimeout-
		// Timing-Flake): A haengt bewusst in einem Gate fest, bis der Test B
		// bereits enqueued hat — reproduziert damit exakt den vom Adversary
		// beschriebenen Ablauf (probe_rollback_stale.mjs): zwei GANZ NORMALE,
		// aufeinanderfolgende Versand-Edits, beide angestossen BEVOR Edit A
		// abgeschlossen ist.
		// Definite-Assignment (`!`): beide werden synchron im Promise-Executor
		// zugewiesen, bevor sie verwendet werden — TS kann das ueber die
		// Executor-Callback-Grenze hinweg nicht selbst ableiten.
		let resolveAStarted!: () => void;
		const aStarted = new Promise<void>((r) => {
			resolveAStarted = r;
		});
		let releaseA!: () => void;
		const aGate = new Promise<void>((r) => {
			releaseA = r;
		});

		async function simulatedPutA(body: ComparePreset): Promise<ComparePreset> {
			resolveAStarted();
			await aGate;
			serverPreset = { ...serverPreset, ...body };
			return { ...serverPreset };
		}
		async function simulatedPutB(): Promise<ComparePreset> {
			throw new Error('Netzwerkfehler (simuliert)');
		}

		let currentPreset = serverPreset;
		// wizardState-Simulation: EIN gemeinsames Objekt, wie im echten Component-Code.
		let lastPersistedVersandSnapshot = hydrateVersandFieldsFromPreset(currentPreset);
		let wiz = { ...lastPersistedVersandSnapshot };

		// Nachbau der GEFIXTEN handleVersandCommit-Struktur aus CompareTabs.svelte:
		// current/before werden ERST innerhalb der enqueueten Closure gelesen.
		async function commit(putFn: (body: ComparePreset) => Promise<ComparePreset>): Promise<void> {
			const updated = await queue.enqueue(async () => {
				const current = { ...lastPersistedVersandSnapshot, ...wiz };
				const before = lastPersistedVersandSnapshot;
				const payload = flushPendingVersandSave(currentPreset, current, lastPersistedVersandSnapshot);
				if (!payload) return null;
				try {
					const result = await putFn(payload.body);
					lastPersistedVersandSnapshot = current;
					return result;
				} catch {
					wiz = { ...wiz, ...before };
					return null;
				}
			});
			if (updated) currentPreset = updated;
		}

		// Edit A: Morgen-Uhrzeit aendern.
		wiz.morningTime = '07:30';
		const editA = commit(simulatedPutA);

		// Warten, bis Edit A ihren Snapshot bereits gezogen und den Request
		// gestartet hat (haengt bewusst in aGate fest).
		await aStarted;

		// Edit B: SOFORT danach SMS togglen, WAEHREND Edit A noch offen ist —
		// B wird durch die Queue erst NACH A ausgefuehrt und schlaegt dann fehl.
		wiz.sendSms = true;
		const editB = commit(simulatedPutB);

		releaseA();
		await Promise.all([editA, editB]);

		assert.strictEqual(
			serverPreset.morning_time,
			'07:30:00',
			'Edit A muss trotz spaeter fehlschlagendem Edit B auf dem Server persistiert bleiben'
		);
		assert.strictEqual(
			wiz.morningTime,
			'07:30',
			'F003-Regression: Rollback von Edit B darf Edit A NICHT aus der UI-Anzeige entfernen'
		);
		assert.strictEqual(wiz.sendSms, false, 'Edit B selbst wird korrekt auf den (Edit-A-)Stand zurueckgerollt');
	});
});
