// TDD RED — Issue #1269 (b): falsches „✓ Gespeichert HH:MM" ohne echten
// Speichervorgang.
//
// Spec: docs/specs/modules/issue_1269_save_status_lie.md
//   § Implementation Details Punkt 1 ("Zustandsmaschine strikt einhalten"),
//   § Acceptance Criteria AC-2
// Kontext: docs/context/fix-1269-save-status-lie.md
//   Root-Cause (b): CompareEditor.svelte:240-241 ruft `setSaved()` unbedingt
//   bei dirty→clean, OHNE dass ein PUT stattfand — der einzige PUT-lose
//   `setSaved()`-Aufruf im gesamten Frontend.
//
// Fehlende Zustandsmaschinen-Transition: `SaveStatus` braucht einen Weg, von
// `dirty` zurück nach `idle` zu gehen, OHNE `savedAt` neu zu stempeln — sonst
// täuscht ein dirty→clean-Übergang ohne PUT einen frischen
// "Gespeichert HH:MM"-Zeitstempel vor. Diese Methode existiert noch NICHT
// (`markPristine()`).
//
// ── Warum `Object.create(SaveStatus.prototype)` statt `new SaveStatus()` ──
//
// `SaveStatus`s Instanzfelder (`state = $state(...)`, `error = $state(...)`,
// `savedAt = $state(...)`) sind Svelte-5-Runen, die als Klassenfeld-
// Initializer bei JEDEM `new SaveStatus()` ausgeführt werden — außerhalb
// eines vom Svelte-Compiler transformierten Kontexts wirft das sofort
// `ReferenceError: $state is not defined` (verifiziert:
// `node --import ./test-lib-loader.mjs --experimental-strip-types -e
// "import('./src/lib/stores/saveStatusStore.svelte.ts').then(m => new
// m.SaveStatus())"` → exakt dieser Fehler). Präzedenzfall + ausführliche
// Begründung im Repo:
// `frontend/src/lib/components/shared/__tests__/alarme_delivery_consolidated_save.test.ts`
// (Kommentarblock "Teil (b)").
//
// `Object.create(SaveStatus.prototype)` umgeht NUR den Konstruktor (die
// `$state(...)`-Aufrufe laufen dort, nicht in den Methoden) — die auf dieser
// Instanz aufgerufenen Methoden (`setSaving`/`setSaved`/`setDirty`/
// `doSave`/`markPristine`) sind die ECHTEN Prototype-Methoden aus der
// Produktionsdatei, KEINE Kopie/Reproduktion. Verifiziert: alle diese
// Methoden SCHREIBEN nur auf `state`/`savedAt`/`error` (nie ein lesender
// Zugriff vor dem ersten Schreiben nötig), daher verhalten sich die auf der
// Test-Instanz manuell vorbelegten Plain-Felder identisch zu den
// (unkompilierten) `$state`-Feldern für diesen Zweck. Kein Mock — echter
// Aufruf von Produktionscode.
//
// Reine Verhaltenstests (echter Methodenaufruf auf der echten Klasse, KEIN
// Mock, KEINE Datei-Inhalt-Prüfung).
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/stores/__tests__/saveStatus.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { SaveStatus } from '../saveStatusStore.svelte.ts';
import { weatherSaveGate } from '../../components/trip-detail/weatherSaveGate.ts';
import { reportConfigChangedByUser } from '../../components/shared/reportConfigDirty.ts';

/** Instanz OHNE Konstruktor-Aufruf (keine `$state(...)`-Initialisierung
 *  nötig) — nur die auf `SaveStatus.prototype` echten Methoden werden
 *  benutzt. `state`/`savedAt`/`error` werden manuell als Plain-Felder
 *  vorbelegt, exakt wie es der (aktuell nicht node-test-faehige) Konstruktor
 *  täte. */
function createTestInstance(): SaveStatus {
	const inst = Object.create(SaveStatus.prototype) as SaveStatus;
	(inst as unknown as { state: string }).state = 'idle';
	(inst as unknown as { savedAt: Date | null }).savedAt = null;
	(inst as unknown as { error: string | null }).error = null;
	return inst;
}

describe('Abgrenzung (Regressionsschutz): der legitime Speicherweg doSave() stempelt savedAt weiterhin neu', () => {
	test('AC-2: setSaved() (via doSave-Erfolg) setzt einen neuen savedAt-Zeitstempel', async () => {
		const c = createTestInstance();
		c.setSaved();
		const t0 = c.savedAt;
		assert.ok(t0 instanceof Date, 'setSaved() muss savedAt auf ein Date setzen');

		// Kleine Wartezeit, damit ein neuer Date.now() sich von t0 unterscheidet
		// (echte Zeit, kein Fake-Timer).
		await new Promise((r) => setTimeout(r, 5));

		c.setDirty();
		assert.equal(c.state, 'dirty');

		await c.doSave(async () => {
			/* echter Speichervorgang (hier: no-op-Callback, aber ECHTER doSave()-Pfad) */
		});

		assert.equal(c.state, 'idle', 'nach erfolgreichem doSave() muss der Zustand idle sein');
		assert.ok(c.savedAt instanceof Date, 'nach doSave() muss savedAt weiterhin ein Date sein');
		assert.notEqual(
			c.savedAt?.getTime(),
			t0?.getTime(),
			'ein ECHTER Speichervorgang (doSave) MUSS savedAt neu stempeln — das ist der legitime "Gespeichert HH:MM"-Pfad'
		);
	});
});

describe('AC-2 (RED, Issue #1269 (b)): markPristine() geht dirty→idle OHNE savedAt neu zu stempeln', () => {
	test('dirty→idle via markPristine() lässt den vorhandenen savedAt-Zeitstempel unangetastet', () => {
		const c = createTestInstance();

		// 1. Ein echter Speichervorgang hat vorher stattgefunden — savedAt = t0.
		c.setSaved();
		const t0 = c.savedAt;
		assert.ok(t0 instanceof Date);

		// 2. Der Nutzer ändert etwas (Anzeige wird korrekt "dirty").
		c.setDirty();
		assert.equal(c.state, 'dirty');

		// 3. Der Zustand geht OHNE echten PUT wieder auf "clean" zurück (z.B. weil
		//    eine Mount-Kanonisierung fälschlich dirty gesetzt hatte und die
		//    Baseline-Korrektur das rückgängig macht — s. Spec (a)/(b)-Kopplung).
		//    markPristine() existiert noch NICHT auf SaveStatus.prototype → RED
		//    (TypeError: c.markPristine is not a function).
		c.markPristine();

		assert.equal(
			c.state,
			'idle',
			'markPristine() muss den Zustand auf idle ("gespeichert"-Anzeige) zurücksetzen'
		);
		assert.equal(
			c.savedAt?.getTime(),
			t0?.getTime(),
			'markPristine() darf savedAt NICHT neu stempeln — sonst würde ein dirty→clean-Übergang OHNE ' +
				'PUT einen frischen "Gespeichert HH:MM"-Zeitstempel vortäuschen (Issue #1269 (b))'
		);
	});

	test('markPristine() existiert als Methode auf SaveStatus.prototype (Signatur-Vertrag für GREEN)', () => {
		assert.equal(
			typeof SaveStatus.prototype.markPristine,
			'function',
			'SaveStatus.prototype.markPristine muss als parameterlose Methode existieren'
		);
	});
});

describe('Fix-Loop 1 (Adversary F001, Issue #1269 (c)): Anzeige aus dem Inhalts-Diff, Schreiben aus der Geste', () => {
	// Regressionsschutz für die BriefingScheduleTab.svelte-Verdrahtung (reine
	// Svelte-Komponente, in node:test nicht instanziierbar — s. Kommentarblock
	// oben) — hier als Komposition der ECHTEN, bereits einzeln getesteten
	// Bausteine (reportConfigChangedByUser, weatherSaveGate, SaveStatus),
	// exakt dieselbe Reihenfolge wie in der Komponente verdrahtet: erst der
	// Inhalts-Diff, dann das Gesten-Gate.
	test(
		'echte inhaltliche Änderung + Gate "skip" (keine erfasste Geste) → setDirty() statt setSaved()/doSave() ' +
			'— ehrliche "Nicht gespeichert"-Anzeige, kein stiller Verlust (AC-6/AC-7)',
		() => {
			const c = createTestInstance();
			c.setSaved();
			const t0 = c.savedAt;

			const baseline = { morning_time: '07:00:00', evening_time: '18:00:00', send_email: true };
			// Echte inhaltliche Änderung (keine reine Mount-Kanonisierung).
			const current = { ...baseline, morning_time: '09:00:00' };
			const changed = reportConfigChangedByUser(baseline, current);
			assert.equal(changed, true, 'Vorbedingung: dies muss eine ECHTE Änderung sein');

			// F003/F004-Klasse: die Gesten-Erfassung hat diese Änderung NICHT
			// eingefangen (userTouched blieb false) — Spec: "nicht garantiert
			// lückenlos". Der Schreibzugriff bleibt gegated (kein PUT), aber die
			// Zustandsmaschine muss trotzdem sagen: "Nicht gespeichert".
			const gateDecision = weatherSaveGate({ catalogLoaded: true, userTouched: false });

			if (changed) {
				if (gateDecision === 'save') {
					c.setSaved();
				} else {
					c.setDirty();
				}
			}

			assert.equal(gateDecision, 'skip', 'Vorbedingung: Gate muss hier "skip" liefern (keine Geste erfasst)');

			assert.equal(
				c.state,
				'dirty',
				'AC-7: eine echte Änderung, die das Gesten-Gate verpasst, darf NIE fälschlich "gespeichert" ' +
					'anzeigen — genau das in der Spec unter "Ausdrücklich verworfen" verbotene Muster ' +
					'(Anzeige an userTouched koppeln)'
			);
			assert.equal(
				c.savedAt?.getTime(),
				t0?.getTime(),
				'kein neuer Speichervorgang fand statt — savedAt darf unverändert bleiben'
			);
		}
	);

	test('echte inhaltliche Änderung + Gate "save" (Geste erfasst) → schreibt (doSave-Pfad bleibt unverändert)', async () => {
		const c = createTestInstance();
		const baseline = { morning_time: '07:00:00' };
		const current = { morning_time: '09:00:00' };
		const changed = reportConfigChangedByUser(baseline, current);
		const gateDecision = weatherSaveGate({ catalogLoaded: true, userTouched: true });
		assert.equal(changed, true);
		assert.equal(gateDecision, 'save');

		if (changed && gateDecision === 'save') {
			await c.doSave(async () => {
				/* echter PUT in der Komponente, hier: echter doSave()-Pfad ohne Netzwerk */
			});
		}

		assert.equal(c.state, 'idle');
		assert.ok(c.savedAt instanceof Date, 'ein echter Speichervorgang muss savedAt setzen');
	});
});
