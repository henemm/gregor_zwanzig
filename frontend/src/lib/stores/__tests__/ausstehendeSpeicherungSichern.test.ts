// TDD RED — Issue #2316 Scheibe A (AC-9/AC-10): gemeinsamer Speicher-Wächter
// für die Detailseiten /trips/[id] und /compare/[id].
//
// Spec: docs/specs/modules/pwa_update_erkennung.md
//   § Implementation Details „compare/[id]/+page.svelte + trips/[id]/+page.svelte (Scheibe A)"
//   § Acceptance Criteria AC-9, AC-10
//
// Zielschnittstelle (existiert noch NICHT → RED per ERR_MODULE_NOT_FOUND):
//
//   sichereAusstehendeSpeicherung(
//     navigation: { willUnload: boolean; to: { url: URL } | null; cancel(): void },
//     ctl: SaveStatus,
//     goto: (href: string) => unknown
//   ): void | Promise<void>
//
// Sie ersetzt 1:1 die heutige Logik aus routes/trips/[id]/+page.svelte:42-59
// (beforeNavigate-Rumpf). Die Svelte-Verdrahtung (`beforeNavigate` aus
// `$app/navigation`) bleibt eine dünne Hülle in den Seiten bzw. einem eigenen
// Modul — dieses Modul hier darf NICHTS aus `$app/*` importieren und keine
// Runen enthalten, sonst ist es unter node:test nicht ladbar.
//
// `navigation.cancel` ist SvelteKits Navigations-Abbruch (Argument von
// `beforeNavigate`), NICHT `SaveStatus.cancel()`. Letzteres würde den
// ausstehenden Speichervorgang verwerfen — dass `saveFn` tatsächlich läuft,
// belegt, dass der Controller ihn nicht verworfen hat.
//
// Kein Mock-Theater: `ctl` ist eine ECHTE SaveStatus-Instanz (echte
// Prototype-Methoden `schedule`/`flush`/`doSave`), `saveFn` ist die echte
// Speicher-Funktion des Aufrufers (hier: zeichnet ihr `init` auf).
//
// Warum `Object.create(SaveStatus.prototype)` statt `new SaveStatus()`:
// die Klassenfelder sind Svelte-5-Runen (`$state(...)`) und werfen außerhalb
// des Svelte-Compilers `ReferenceError: $state is not defined`. Ausführliche
// Begründung + Präzedenzfall: `./saveStatus.test.ts` Zeilen 18-48.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/stores/__tests__/ausstehendeSpeicherungSichern.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { SaveStatus } from '../saveStatusStore.svelte.ts';
import { sichereAusstehendeSpeicherung } from '../ausstehendeSpeicherungSichern.ts';

/** Echte SaveStatus-Instanz ohne Konstruktor (Muster aus saveStatus.test.ts). */
function createTestInstance(): SaveStatus {
	const inst = Object.create(SaveStatus.prototype) as SaveStatus;
	const fields = inst as unknown as Record<string, unknown>;
	fields.state = 'idle';
	fields.savedAt = null;
	fields.error = null;
	fields._timer = null;
	fields._pendingFn = null;
	fields._inflight = null;
	fields._lastFailed = null;
	fields._unresolvedError = null;
	return inst;
}

/** Navigations-Argument wie von SvelteKits `beforeNavigate`, zeichnet `cancel()` auf. */
function createNavigation(willUnload: boolean, href: string | null) {
	const rec = { cancelCalls: 0 };
	const navigation = {
		willUnload,
		to: href ? { url: new URL(href) } : null,
		cancel: () => {
			rec.cancelCalls++;
		}
	};
	return { navigation, rec };
}

/** Aufgezeichnete `goto`-Aufrufe. */
function createGoto() {
	const calls: string[] = [];
	return { goto: (h: string) => void calls.push(h), calls };
}

const tick = () => new Promise<void>((r) => setImmediate(r));

describe('Issue #2316 Scheibe A: gemeinsamer Speicher-Wächter vor dem Verlassen der Detailseite', () => {
	test('(a) ausstehende Änderung + Neuladen (willUnload): speichert SOFORT mit keepalive, OHNE Verlassen-Rückfrage', async () => {
		const ctl = createTestInstance();
		const inits: Array<RequestInit | undefined> = [];
		ctl.schedule(async (init) => {
			inits.push(init);
		});
		assert.equal(ctl.hasPending, true, 'Vorbedingung: Änderung wartet im 700-ms-Fenster');

		const { navigation, rec } = createNavigation(true, null);
		const { goto, calls } = createGoto();

		sichereAusstehendeSpeicherung(navigation, ctl, goto);

		// Synchron geprüft, BEVOR irgendetwas abgewartet wird: der Request muss
		// noch im Tick des Entladens abgesetzt sein, sonst überlebt er das
		// Dokument nicht (#1376).
		assert.equal(inits.length, 1, 'die ausstehende Speicherung muss noch im selben Tick abgesetzt werden');
		assert.equal(inits[0]?.keepalive, true, 'beim Entladen muss keepalive:true durchgereicht werden');
		assert.equal(
			rec.cancelCalls,
			0,
			'beim Neuladen darf die Navigation NICHT abgebrochen werden — sonst erscheint die Verlassen-Rückfrage (AC-9)'
		);

		await tick();
		assert.equal(ctl.hasPending, false, 'nach dem Sichern steht nichts mehr aus');
		assert.equal(calls.length, 0, 'beim Entladen wird nicht selbst weiternavigiert');
	});

	test('(b) ausstehende Änderung + Seitenwechsel innerhalb der App: Navigation anhalten, speichern, DANACH zum Ziel', async () => {
		const ctl = createTestInstance();
		const inits: Array<RequestInit | undefined> = [];
		let release!: () => void;
		const onTheWire = new Promise<void>((r) => {
			release = r;
		});
		ctl.schedule(async (init) => {
			inits.push(init);
			await onTheWire;
		});

		const target = 'http://localhost:4173/trips?tab=aktiv';
		const { navigation, rec } = createNavigation(false, target);
		const { goto, calls } = createGoto();

		sichereAusstehendeSpeicherung(navigation, ctl, goto);

		assert.equal(rec.cancelCalls, 1, 'die Navigation muss angehalten werden, solange gespeichert wird');
		assert.equal(inits.length, 1, 'die ausstehende Speicherung muss sofort ausgelöst werden (nicht erst nach 700 ms)');
		assert.notEqual(inits[0]?.keepalive, true, 'innerhalb der App ist kein keepalive nötig — das Dokument bleibt');

		await tick();
		assert.equal(calls.length, 0, 'solange der Request läuft, darf noch nicht weiternavigiert werden');

		release();
		await tick();
		await tick();
		assert.deepEqual(calls, [target], 'nach abgeschlossener Speicherung muss genau zum ursprünglichen Ziel navigiert werden');
		assert.equal(ctl.hasPending, false);
	});

	test('(c1) nichts ausstehend + Seitenwechsel: weder anhalten noch speichern noch umleiten', async () => {
		const ctl = createTestInstance();
		const { navigation, rec } = createNavigation(false, 'http://localhost:4173/compare');
		const { goto, calls } = createGoto();

		sichereAusstehendeSpeicherung(navigation, ctl, goto);
		await tick();

		assert.equal(rec.cancelCalls, 0, 'ohne ausstehende Änderung darf die Navigation nicht angehalten werden');
		assert.equal(calls.length, 0, 'ohne ausstehende Änderung keine eigene Umleitung');
		assert.equal(ctl.state, 'idle', 'ohne ausstehende Änderung kein Speichervorgang (Zustand bleibt idle)');
		assert.equal(ctl.savedAt, null, 'kein Speichervorgang heißt auch kein neuer Gespeichert-Zeitstempel');
	});

	test('(c2) nichts ausstehend + Neuladen: kein Speichervorgang, keine Rückfrage', async () => {
		const ctl = createTestInstance();
		const { navigation, rec } = createNavigation(true, null);
		const { goto, calls } = createGoto();

		sichereAusstehendeSpeicherung(navigation, ctl, goto);
		await tick();

		assert.equal(rec.cancelCalls, 0);
		assert.equal(calls.length, 0);
		assert.equal(ctl.state, 'idle');
		assert.equal(ctl.savedAt, null);
	});
});
