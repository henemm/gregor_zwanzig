// Smoke-Tests fuer WizardState (Epic #136 Master-Spec §3.1, §1.4).
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-wizard/__tests__/wizardState.test.ts
//
// Hinweis: Svelte-5-Runen `$state` und `$derived` werden vom Svelte-Compiler
// transformiert. Im Plain-Node-Kontext definieren wir sie als
// Identity-Funktionen — fuer Unit-Tests ohne Reaktivitaet ausreichend, weil
// wir nur Initial-Werte und imperative Mutations pruefen.

// --- Globals fuer Svelte-5-Runen einrichten BEFORE Modul-Import ----------
type RuneFn = (v: unknown) => unknown;
const g = globalThis as unknown as Record<string, RuneFn>;
if (typeof g.$state !== 'function') g.$state = (v: unknown) => v;
if (typeof g.$derived !== 'function') g.$derived = (v: unknown) => v;

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { isPauseStage } from '../wizardHelpers.ts';
import { WizardState, defaultBriefingConfig } from '../wizardState.svelte.ts';

test('WizardState: Initial-State entspricht Spec-Defaults', () => {
	const s = new WizardState();
	assert.equal(s.currentStep, 1);
	assert.equal(s.activity, null);
	assert.equal(s.briefings.channels.email, true);
	assert.equal(s.briefings.channels.signal, false);
	assert.equal(s.briefings.channels.telegram, false);
	assert.equal(s.briefings.channels.sms, false);
	assert.equal(s.briefings.reports.morning.enabled, true);
	assert.equal(s.briefings.reports.evening.enabled, true);
	assert.equal(s.briefings.reports.morning.time, '06:00');
	assert.equal(s.briefings.reports.evening.time, '18:00');
	assert.equal(s.saveStatus, 'idle');
	assert.equal(s.saveError, null);
});

test('WizardState: nextStep() schreitet 1 → 2 voran', () => {
	const s = new WizardState();
	s.nextStep();
	assert.equal(s.currentStep, 2);
});

test('WizardState: nextStep() bleibt bei 4 (kein Wrap)', () => {
	const s = new WizardState();
	s.currentStep = 4;
	s.nextStep();
	assert.equal(s.currentStep, 4);
});

test('WizardState: prevStep() bleibt bei 1 (kein Underflow)', () => {
	const s = new WizardState();
	assert.equal(s.currentStep, 1);
	s.prevStep();
	assert.equal(s.currentStep, 1);
});

test('WizardState: prevStep() schreitet 4 → 3 zurueck', () => {
	const s = new WizardState();
	s.currentStep = 4;
	s.prevStep();
	assert.equal(s.currentStep, 3);
});

test('WizardState: toTripPayload mit activity=skitour → aggregation.profile=wintersport', () => {
	const s = new WizardState();
	s.activity = 'skitour';
	s.name = 'Test-Tour';
	const trip = s.toTripPayload();
	assert.equal(trip.activity, 'skitour');
	assert.ok(trip.aggregation, 'aggregation muss gesetzt sein');
	assert.equal((trip.aggregation as { profile: string }).profile, 'wintersport');
});

test('WizardState: addPauseStage() fuegt Stage mit leeren Wegpunkten hinzu', () => {
	const s = new WizardState();
	const before = s.stages.length;
	s.addPauseStage();
	assert.equal(s.stages.length, before + 1);
	const last = s.stages.at(-1)!;
	assert.deepEqual(last.waypoints, []);
	assert.equal(isPauseStage(last), true);
});

test('WizardState: defaultBriefingConfig ist nicht geteilt (Klone unabhaengig)', () => {
	const a = new WizardState();
	const b = new WizardState();
	a.briefings.channels.signal = true;
	assert.equal(b.briefings.channels.signal, false, 'jede Instanz haelt eigene briefings');
	// defaultBriefingConfig selbst ist auch unangetastet:
	assert.equal(defaultBriefingConfig.channels.signal, false);
});

// --- canAdvanceStep1 (Sub-Spec #161 §6, AC#15) -----------------------------
//
// Pflichtfelder fuer Step 1: activity, name, startDate.
// Optional: shortcode (faellt nicht in die Bedingung).
// Hinweis: Damit die Tests in Plain-Node mit Identity-Mocks funktionieren,
// muss die Implementierung getter-basiert sein (oder eine pure Helper-
// Funktion verwenden) — beides ist Svelte-5-reaktivitaets-kompatibel.

test('canAdvanceStep1: initial false (alle Pflichtfelder leer)', () => {
	const s = new WizardState();
	assert.equal(s.canAdvanceStep1, false);
});

test('canAdvanceStep1: nur activity gesetzt → false (name+startDate fehlen)', () => {
	const s = new WizardState();
	s.activity = 'trekking';
	assert.equal(s.canAdvanceStep1, false);
});

test('canAdvanceStep1: activity+name gesetzt → false (startDate fehlt)', () => {
	const s = new WizardState();
	s.activity = 'skitour';
	s.name = 'Stubai';
	assert.equal(s.canAdvanceStep1, false);
});

test('canAdvanceStep1: alle 3 Pflichtfelder gesetzt → true', () => {
	const s = new WizardState();
	s.activity = 'trekking';
	s.name = 'GR20';
	s.startDate = '2026-06-01';
	assert.equal(s.canAdvanceStep1, true);
});

test('canAdvanceStep1: name nur Whitespace → false (trim-Logik)', () => {
	const s = new WizardState();
	s.activity = 'trekking';
	s.name = '   ';
	s.startDate = '2026-06-01';
	assert.equal(s.canAdvanceStep1, false);
});

test('canAdvanceStep1: leerer startDate-String → false (HTML5-Date-Input nach Loeschen)', () => {
	const s = new WizardState();
	s.activity = 'trekking';
	s.name = 'GR20';
	s.startDate = '';
	assert.equal(s.canAdvanceStep1, false);
});

test('canAdvanceStep1: nach Loeschen eines Pflichtfelds → false', () => {
	const s = new WizardState();
	s.activity = 'mtb';
	s.name = 'Tour';
	s.startDate = '2026-07-15';
	assert.equal(s.canAdvanceStep1, true, 'Pre-Condition: alle Pflichtfelder gesetzt');

	s.activity = null;
	assert.equal(s.canAdvanceStep1, false, 'Loeschen activity → canAdvanceStep1 false');
});

test('canAdvanceStep1: shortcode ist optional, beeinflusst Bedingung nicht', () => {
	const s = new WizardState();
	s.activity = 'klettersteig';
	s.name = 'KS-Test';
	s.startDate = '2026-08-01';
	// kein shortcode gesetzt
	assert.equal(s.canAdvanceStep1, true, 'shortcode leer → canAdvanceStep1 true');

	s.shortcode = 'KS-25';
	assert.equal(s.canAdvanceStep1, true, 'shortcode gesetzt → canAdvanceStep1 weiterhin true');
});

// --- canAdvanceStep2 (Sub-Spec #162 §3) -----------------------------------
//
// Step 2 darf weitergeschaltet werden, sobald mindestens eine Etappe existiert.
// Pausentage zaehlen aktuell nicht eigenstaendig — die Acceptance-Kriterien
// verlangen mindestens eine "echte" Etappe; Implementierung: stages.length > 0.

test('canAdvanceStep2: initial false (keine Etappen)', () => {
	const s = new WizardState();
	assert.equal(s.canAdvanceStep2, false);
});

test('canAdvanceStep2: nach addStage true', () => {
	const s = new WizardState();
	s.addStage({ id: 'a', name: 'Etappe 1', date: '2026-06-01', waypoints: [] });
	assert.equal(s.canAdvanceStep2, true);
});

test('canAdvanceStep2: nach deleteStage zurueck auf false', () => {
	const s = new WizardState();
	s.addStage({ id: 'a', name: 'Etappe 1', date: '2026-06-01', waypoints: [] });
	assert.equal(s.canAdvanceStep2, true);
	s.deleteStage('a');
	assert.equal(s.canAdvanceStep2, false);
});

// --- canAdvanceCurrent (Sub-Spec #162 §3, §9) ------------------------------

test('canAdvanceCurrent: Step 1 spiegelt canAdvanceStep1', () => {
	const s = new WizardState();
	assert.equal(s.canAdvanceCurrent, false, 'initial Step 1 nicht erfuellt');
	s.activity = 'trekking';
	s.name = 'GR20';
	s.startDate = '2026-06-01';
	assert.equal(s.canAdvanceCurrent, true, 'Step 1 erfuellt');
});

test('canAdvanceCurrent: Step 2 spiegelt canAdvanceStep2', () => {
	const s = new WizardState();
	s.currentStep = 2;
	assert.equal(s.canAdvanceCurrent, false, 'Step 2 ohne Etappen → false');
	s.addStage({ id: 'a', name: 'Etappe 1', date: '2026-06-01', waypoints: [] });
	assert.equal(s.canAdvanceCurrent, true, 'Step 2 mit Etappe → true');
});

test('canAdvanceCurrent: Step 3 ist immer true', () => {
	const s = new WizardState();
	s.currentStep = 3;
	assert.equal(s.canAdvanceCurrent, true);
});

test('canAdvanceCurrent: Step 4 ist immer true', () => {
	const s = new WizardState();
	s.currentStep = 4;
	assert.equal(s.canAdvanceCurrent, true);
});

// --- addPauseStageAt (Sub-Spec #162 §7) ------------------------------------

test('addPauseStageAt: fuegt Pause an Position afterIndex+1 ein', () => {
	const s = new WizardState();
	s.startDate = '2026-06-01';
	s.addStage({ id: 'a', name: 'A', date: '2026-06-01', waypoints: [{ id: 'w1', name: 'W', lat: 0, lon: 0, elevation_m: 0 }] });
	s.addStage({ id: 'b', name: 'B', date: '2026-06-02', waypoints: [{ id: 'w2', name: 'W', lat: 0, lon: 0, elevation_m: 0 }] });
	s.addPauseStageAt(0); // Pause nach Stage 0
	assert.equal(s.stages.length, 3);
	assert.equal(s.stages[0].id, 'a');
	assert.equal(isPauseStage(s.stages[1]), true, 'Pause an Position 1');
	assert.equal(s.stages[2].id, 'b');
});

test('addPauseStageAt: ruft recomputeStageDates auf', () => {
	const s = new WizardState();
	s.startDate = '2026-06-01';
	s.addStage({ id: 'a', name: 'A', date: '2026-06-01', waypoints: [{ id: 'w1', name: 'W', lat: 0, lon: 0, elevation_m: 0 }] });
	s.addStage({ id: 'b', name: 'B', date: '2026-06-02', waypoints: [{ id: 'w2', name: 'W', lat: 0, lon: 0, elevation_m: 0 }] });
	s.addPauseStageAt(0);
	// Nach Insert: Stage 0 = '2026-06-01', Pause = '2026-06-02', Stage 'b' = '2026-06-03'
	assert.equal(s.stages[0].date, '2026-06-01');
	assert.equal(s.stages[1].date, '2026-06-02');
	assert.equal(s.stages[2].date, '2026-06-03');
});

// --- deleteStage (Sub-Spec #162 §5) ----------------------------------------

test('deleteStage: entfernt Stage per ID', () => {
	const s = new WizardState();
	s.startDate = '2026-06-01';
	s.addStage({ id: 'a', name: 'A', date: '2026-06-01', waypoints: [] });
	s.addStage({ id: 'b', name: 'B', date: '2026-06-02', waypoints: [] });
	s.addStage({ id: 'c', name: 'C', date: '2026-06-03', waypoints: [] });
	s.deleteStage('b');
	assert.equal(s.stages.length, 2);
	assert.deepEqual(
		s.stages.map((x) => x.id),
		['a', 'c']
	);
});

test('deleteStage: ruft recomputeStageDates auf', () => {
	const s = new WizardState();
	s.startDate = '2026-06-01';
	s.addStage({ id: 'a', name: 'A', date: '2026-06-01', waypoints: [] });
	s.addStage({ id: 'b', name: 'B', date: '2026-06-02', waypoints: [] });
	s.addStage({ id: 'c', name: 'C', date: '2026-06-03', waypoints: [] });
	s.deleteStage('a');
	// Nach Delete: 'b' rueckt auf Index 0 → '2026-06-01', 'c' auf Index 1 → '2026-06-02'
	assert.equal(s.stages[0].date, '2026-06-01');
	assert.equal(s.stages[1].date, '2026-06-02');
});

// --- recomputeStageDates (Sub-Spec #162 §8) --------------------------------

test('recomputeStageDates: setzt date=startDate+index', () => {
	const s = new WizardState();
	s.startDate = '2026-06-01';
	s.addStage({ id: 'a', name: 'A', date: '', waypoints: [] });
	s.addStage({ id: 'b', name: 'B', date: '', waypoints: [] });
	s.recomputeStageDates();
	assert.equal(s.stages[0].date, '2026-06-01');
	assert.equal(s.stages[1].date, '2026-06-02');
});

test('recomputeStageDates: schuetzt dateOverridden=true', () => {
	const s = new WizardState();
	s.startDate = '2026-06-01';
	s.addStage({ id: 'a', name: 'A', date: '2026-07-15', waypoints: [], dateOverridden: true });
	s.addStage({ id: 'b', name: 'B', date: '', waypoints: [] });
	s.recomputeStageDates();
	assert.equal(s.stages[0].date, '2026-07-15', 'overridden bleibt');
	assert.equal(s.stages[1].date, '2026-06-02');
});

test('recomputeStageDates: no-op wenn startDate null', () => {
	const s = new WizardState();
	s.startDate = null;
	s.addStage({ id: 'a', name: 'A', date: '2026-06-01', waypoints: [] });
	s.recomputeStageDates();
	assert.equal(s.stages[0].date, '2026-06-01', 'date unveraendert');
});

// --- reorderStages: ruft recomputeStageDates auf ---------------------------

test('reorderStages: re-dated Etappen lueckenlos', () => {
	const s = new WizardState();
	s.startDate = '2026-06-01';
	s.addStage({ id: 'a', name: 'A', date: '2026-06-01', waypoints: [] });
	s.addStage({ id: 'b', name: 'B', date: '2026-06-02', waypoints: [] });
	s.addStage({ id: 'c', name: 'C', date: '2026-06-03', waypoints: [] });
	s.reorderStages(2, 0); // C an den Anfang
	assert.equal(s.stages[0].id, 'c');
	assert.equal(s.stages[0].date, '2026-06-01', 'C bekommt Tag 1');
	assert.equal(s.stages[1].date, '2026-06-02');
	assert.equal(s.stages[2].date, '2026-06-03');
});

// --- toTripPayload: dateOverridden wird gestrippt --------------------------

test('toTripPayload: strippt dateOverridden aus jeder Stage', () => {
	const s = new WizardState();
	s.activity = 'trekking';
	s.name = 'GR20';
	s.startDate = '2026-06-01';
	s.addStage({ id: 'a', name: 'A', date: '2026-06-01', waypoints: [], dateOverridden: true });
	s.addStage({ id: 'b', name: 'B', date: '2026-06-02', waypoints: [], dateOverridden: false });
	const trip = s.toTripPayload();
	for (const stage of trip.stages) {
		assert.equal(
			Object.prototype.hasOwnProperty.call(stage, 'dateOverridden'),
			false,
			`stage ${stage.id} darf kein dateOverridden mehr enthalten`
		);
	}
});
