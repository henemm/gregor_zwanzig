// TDD — Issue #2276 Scheibe S6f (Epic #2345), Adversary-Finding F001 (Fix-Loop 1).
//
// Finding: `hub_put_queue.test.ts` bewacht nur die Choreografie der Queue
// SELBST (per handgebauten Closures) — nie den ECHTEN Funktionskoerper von
// `persistPickedIds` in `CompareTabs.svelte`. Eine Mutation, die den
// Payload-Bau `buildHubPutPayload(currentPreset, { pickedIds: newIds })` aus
// dem `hubPutQueue.enqueue(async () => {…})`-Closure VOR den enqueue-Aufruf
// zieht, faellt daher bei keinem bestehenden Test auf — obwohl genau das der
// Bug ist, den Fix-Loop 1 (F002) beheben sollte: ein zweiter, schnell
// aufeinanderfolgender Aufruf wuerde dann mit der VERALTETEN
// `currentPreset`-Baseline arbeiten statt mit der frisch aus der ersten
// PUT-Antwort aufgefrischten.
//
// Dieser Test fuehrt den ECHTEN Instanz-Code von `CompareTabs.svelte` aus
// (`svelteInstanzPruefstand.ts`, Vorbild: `compare_versand_wertprops.test.ts`)
// — Importe (`buildHubPutPayload`, `buildToggleActivePutPayload`,
// `createPutQueue` aus `compareHubPersistenz.ts`) sind ECHT, nur `api` wird
// gesaet (Mitschnitt statt Netz). Kein Mock des Pruefteils selbst.
//
// Spec: docs/specs/modules/rework_2276_s6f_bridge_umzug.md — AC-5
//
// Pfadregel #1409: alles relativ zu DIESER Datei aufgeloest.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/compare/__tests__/hub_orte_schreibweg_liest_baseline_erst_in_der_schlange.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { umgebungFuer, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const HUB = join(HIER, '..', 'CompareTabs.svelte');

type PutCall = { url: string; body: Record<string, unknown> };

function basisPreset(): Record<string, unknown> {
	return {
		id: 'p1',
		name: 'Start',
		location_ids: ['a'],
		display_config: {},
		schedule: 'daily',
		previous_schedule: 'daily'
	};
}

/** Ein Aufzeichnungs-`saveController` — nur die drei Methoden, die
 *  `persistPickedIds`/`handleToggleActive` tatsaechlich aufrufen. */
function saveControllerAufzeichner(): Knoten {
	return {
		setSaving: () => {},
		setSaved: () => {},
		setError: () => {},
		flush: async () => {}
	};
}

/** Baut eine gesteuerte `api.put`-Attrappe: der ERSTE Aufruf haengt an einem
 *  manuell aufgeloesten Promise, jeder weitere Aufruf liefert sofort einen
 *  Wert. Jeder Aufruf (Start UND das Resolve des ersten) wird in `events`
 *  vermerkt — das belegt die Aufrufreihenfolge, nicht nur das Endergebnis. */
function gesteuerteApi() {
	const putCalls: PutCall[] = [];
	const events: string[] = [];
	let resolveFirst!: (value: unknown) => void;
	const api = {
		put: async (url: string, body: unknown) => {
			const nr = putCalls.push({ url, body: body as Record<string, unknown> });
			events.push(`put${nr}-gestartet`);
			if (nr === 1) {
				return await new Promise((resolve) => {
					resolveFirst = resolve;
				});
			}
			return { ...(body as Record<string, unknown>) };
		}
	};
	return {
		api,
		putCalls,
		events,
		loeseErstenAuf(wert: unknown) {
			events.push('erster-put-aufgeloest');
			resolveFirst(wert);
		}
	};
}

/** Ein paar Mikrotask-Runden abwarten, ohne echte Timer — genug, damit ein
 *  `await`-Zwischenschritt (z. B. `saveController.flush()`) durchlaeuft,
 *  bevor der Test den Zwischenstand prueft. */
async function mikrotasksAbwarten(runden = 10): Promise<void> {
	for (let i = 0; i < runden; i++) await Promise.resolve();
}

describe('#2276 S6f F001: der Orte-Schreibweg liest die Baseline erst BEIM Ausfuehren in der Schlange', () => {
	test('zwei sofort aufeinanderfolgende persistPickedIds-Aufrufe: der zweite PUT-Body traegt die Antwort des ERSTEN PUT, beide laufen seriell', async () => {
		const preset = basisPreset();
		const saveController = saveControllerAufzeichner();
		const { api, putCalls, events, loeseErstenAuf } = gesteuerteApi();

		const { u } = await umgebungFuer(HUB, {
			preset,
			locations: [],
			saveController,
			api
		});

		assert.strictEqual(
			typeof u.persistPickedIds,
			'function',
			'Messaufbau kaputt: `persistPickedIds` ist keine Funktion — umgebungFuer() hat die ' +
				`Deklaration nicht hergeleitet. Herleitbar waren: ${JSON.stringify(Object.keys(u).sort())}.`
		);
		assert.ok(
			u.hubPutQueue && typeof (u.hubPutQueue as Knoten).enqueue === 'function',
			'Messaufbau kaputt: `hubPutQueue` ist kein Objekt mit `enqueue()` — ohne die echte Queue ' +
				'misst dieser Test keine Serialisierung.'
		);

		// Zwei Aufrufe OHNE dazwischen zu warten — genau das Szenario aus F001.
		const p1 = (u.persistPickedIds as (ids: string[]) => Promise<void>)(['a', 'b']);
		const p2 = (u.persistPickedIds as (ids: string[]) => Promise<void>)(['a', 'b', 'c']);

		// Vorbedingung fuer die Serialisierungs-Aussage: nach beliebig vielen
		// Mikrotask-Runden ist der zweite PUT noch NICHT losgelaufen, solange der
		// erste noch offen ist — sonst wuerde „seriell" nichts pruefen.
		await mikrotasksAbwarten();
		assert.strictEqual(
			putCalls.length,
			1,
			`Messaufbau/Regression: es sind bereits ${putCalls.length} PUTs gestartet, bevor der erste ` +
				'aufgeloest wurde — dann liefen die beiden Aufrufe nicht seriell durch dieselbe Schlange.'
		);
		assert.strictEqual(
			putCalls[0].body.name,
			'Start',
			'Messaufbau kaputt: der erste PUT-Body traegt nicht den Ausgangs-Namen.'
		);

		// Der erste PUT loest auf — mit einem erkennbar AUFGEFRISCHTEN Preset.
		loeseErstenAuf({ ...preset, name: 'Aufgefrischt', location_ids: ['a', 'b'] });

		await p1;
		await p2;

		assert.strictEqual(
			putCalls.length,
			2,
			`Erwartet genau zwei PUT-Aufrufe, gesehen wurden ${putCalls.length}.`
		);
		assert.deepStrictEqual(
			events,
			['put1-gestartet', 'erster-put-aufgeloest', 'put2-gestartet'],
			`F001 FAIL: die Aufrufreihenfolge (${events.join(', ')}) belegt keine Serialisierung — der ` +
				'zweite PUT muss erst NACH dem Aufloesen des ersten starten.'
		);
		assert.strictEqual(
			putCalls[1].body.name,
			'Aufgefrischt',
			`F001 FAIL: der zweite PUT-Body traegt \`name\` = ${JSON.stringify(putCalls[1].body.name)} ` +
				"statt der aufgefrischten Antwort des ersten PUT ('Aufgefrischt'). Das ist genau die " +
				'Mutation, die den Payload-Bau aus dem `enqueue()`-Closure herauszieht: dann liest ' +
				'`persistPickedIds` `currentPreset` bereits beim Aufruf statt bei der tatsaechlichen ' +
				'Ausfuehrung in der Schlange.'
		);
		assert.deepStrictEqual(
			putCalls[1].body.location_ids,
			['a', 'b', 'c'],
			'F001 FAIL: der zweite PUT-Body traegt nicht die zweite Orte-Auswahl.'
		);
	});

	test('persistPickedIds gefolgt von handleToggleActive: der Toggle-PUT-Body traegt ebenfalls die aufgefrischte Baseline', async () => {
		const preset = basisPreset();
		const saveController = saveControllerAufzeichner();
		const { api, putCalls, events, loeseErstenAuf } = gesteuerteApi();

		const { u } = await umgebungFuer(HUB, {
			preset,
			locations: [],
			saveController,
			api,
			onScheduleChange: undefined
		});

		assert.strictEqual(
			typeof u.handleToggleActive,
			'function',
			'Messaufbau kaputt: `handleToggleActive` ist keine Funktion — umgebungFuer() hat die ' +
				`Deklaration nicht hergeleitet. Herleitbar waren: ${JSON.stringify(Object.keys(u).sort())}.`
		);

		const p1 = (u.persistPickedIds as (ids: string[]) => Promise<void>)(['a', 'b']);
		const p2 = (u.handleToggleActive as () => Promise<boolean>)();

		await mikrotasksAbwarten();
		assert.strictEqual(
			putCalls.length,
			1,
			`Messaufbau/Regression: es sind bereits ${putCalls.length} PUTs gestartet, bevor der erste ` +
				'aufgeloest wurde.'
		);

		loeseErstenAuf({ ...preset, name: 'Aufgefrischt', location_ids: ['a', 'b'] });

		await p1;
		const toggleErfolgreich = await p2;

		assert.strictEqual(toggleErfolgreich, true, 'handleToggleActive muss erfolgreich zurueckmelden.');
		assert.strictEqual(putCalls.length, 2, `Erwartet zwei PUT-Aufrufe, gesehen ${putCalls.length}.`);
		assert.deepStrictEqual(
			events,
			['put1-gestartet', 'erster-put-aufgeloest', 'put2-gestartet'],
			`Serialisierung ueber zwei VERSCHIEDENE Schreibpfade (Orte + Toggle-Active) verletzt: ${events.join(', ')}.`
		);
		assert.strictEqual(
			putCalls[1].body.name,
			'Aufgefrischt',
			`Toggle-PUT-Body traegt \`name\` = ${JSON.stringify(putCalls[1].body.name)} statt der ` +
				"aufgefrischten Antwort des vorangegangenen Orte-PUT ('Aufgefrischt') — dieselbe " +
				'Baseline-Lehre wie F001, hier fuer den Toggle-Active-Schreibweg.'
		);
		assert.strictEqual(putCalls[1].body.schedule, 'manual', 'Toggle-PUT-Body muss `schedule: manual` tragen.');
		assert.strictEqual(
			putCalls[1].body.previous_schedule,
			'daily',
			'Toggle-PUT-Body muss `previous_schedule` unveraendert mitfuehren.'
		);
	});
});
