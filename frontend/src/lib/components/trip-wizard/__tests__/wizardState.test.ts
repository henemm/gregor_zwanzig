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

test('WizardState: nextStep() schreitet 4 → 5 voran (Issue #430 — 5 Steps)', () => {
	const s = new WizardState();
	s.currentStep = 4;
	s.nextStep();
	assert.equal(s.currentStep, 5);
});

test('WizardState: nextStep() bleibt bei 5 (kein Wrap, Issue #430)', () => {
	const s = new WizardState();
	s.currentStep = 5;
	s.nextStep();
	assert.equal(s.currentStep, 5);
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
	assert.equal(trip.aggregation?.profile, 'wintersport');
});

// --- Issue #224: alte Issue-#222-W2-Threshold-Tests entfernt
// (briefings.thresholds existiert nicht mehr; AlertRules werden direkt
// ueber `wizard.alertRules` geschrieben — siehe Issue #224-Tests am Datei-Ende).

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
	// Issue #300: activity ist KEIN Pflichtfeld mehr — Pflicht sind name + startDate.
	s.name = 'Tour';
	s.startDate = '2026-07-15';
	assert.equal(s.canAdvanceStep1, true, 'Pre-Condition: alle Pflichtfelder gesetzt');

	s.name = '';
	assert.equal(s.canAdvanceStep1, false, 'Loeschen name → canAdvanceStep1 false');
});

test('canAdvanceStep1: Issue #300 — activity ist kein Pflichtfeld mehr (nur name+startDate)', () => {
	const s = new WizardState();
	s.name = 'GR20';
	s.startDate = '2026-06-01';
	assert.equal(s.activity, null, 'Pre-Condition: activity ist null');
	assert.equal(
		s.canAdvanceStep1,
		true,
		'name + startDate reichen — activity nicht erforderlich'
	);
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

// --- Sub-Spec #163 §3.3: rejectWaypoint(stageId, waypointId) ---------------
// AC#15 — Entfernt Wegpunkt vollstaendig aus stage.waypoints.

test('rejectWaypoint AC#15a: entfernt Wegpunkt aus stage.waypoints', () => {
	const s = new WizardState();
	s.addStage({
		id: 'st-1',
		name: 'Etappe 1',
		date: '2026-06-01',
		waypoints: [
			{ id: 'w1', name: 'Gipfel', lat: 0, lon: 0, elevation_m: 2000 },
			{ id: 'w2', name: 'See', lat: 0, lon: 0, elevation_m: 1500 }
		]
	});
	s.rejectWaypoint('st-1', 'w1');
	assert.equal(s.stages[0].waypoints.length, 1, 'genau 1 Wegpunkt uebrig');
	assert.equal(s.stages[0].waypoints[0].id, 'w2', 'wp2 ist der verbleibende');
});

test('rejectWaypoint AC#15b: falsche stageId → State unveraendert', () => {
	const s = new WizardState();
	s.addStage({
		id: 'st-1',
		name: 'Etappe 1',
		date: '2026-06-01',
		waypoints: [{ id: 'w1', name: 'X', lat: 0, lon: 0, elevation_m: 100 }]
	});
	s.rejectWaypoint('UNKNOWN', 'w1');
	assert.equal(s.stages[0].waypoints.length, 1);
});

// --- Sub-Spec #163 §3.4: canAdvanceStep3-Getter (immer true) ---------------
// AC#17 — Liefert immer true; auch ohne Stages, mit allen verworfenen, etc.

test('canAdvanceStep3 AC#17a: neuer State (keine Stages) → true', () => {
	const s = new WizardState();
	assert.equal(s.canAdvanceStep3, true);
});

test('canAdvanceStep3 AC#17b: mit Stages → true', () => {
	const s = new WizardState();
	s.addStage({
		id: 'st-1',
		name: 'Etappe',
		date: '2026-06-01',
		waypoints: [{ id: 'w1', name: 'X', lat: 0, lon: 0, elevation_m: 100 }]
	});
	assert.equal(s.canAdvanceStep3, true);
});

test('canAdvanceStep3 AC#17c: mit allen Waypoints verworfen → true', () => {
	const s = new WizardState();
	s.addStage({
		id: 'st-1',
		name: 'Etappe',
		date: '2026-06-01',
		waypoints: [{ id: 'w1', name: 'X', lat: 0, lon: 0, elevation_m: 100 }]
	});
	s.rejectWaypoint('st-1', 'w1');
	assert.equal(s.stages[0].waypoints.length, 0, 'Pre-Condition: 0 Waypoints');
	assert.equal(s.canAdvanceStep3, true);
});

// --- Sub-Spec #163 §3.5: canAdvanceCurrent case 3 → canAdvanceStep3 --------
// AC#18 — Switch case 3 delegiert auf den Getter (statt literal true).

test('canAdvanceCurrent AC#18: Step 3 delegiert auf canAdvanceStep3', () => {
	const s = new WizardState();
	s.currentStep = 3;
	// Identitaet pruefen: canAdvanceCurrent === canAdvanceStep3
	assert.equal(s.canAdvanceCurrent, s.canAdvanceStep3);
	assert.equal(s.canAdvanceCurrent, true);
});

// --- Sub-Spec #164 §3.1: canAdvanceStep4-Getter (immer true) ---------------
// AC#17 (#164) — Liefert immer true; kein Validierungs-Gate fuer Step 4.

test('canAdvanceStep4 #164 AC#1: neuer State → true', () => {
	const s = new WizardState();
	assert.equal(s.canAdvanceStep4, true);
});

test('canAdvanceStep4 #164 AC#1b: alle Kanaele aus → trotzdem true', () => {
	const s = new WizardState();
	s.briefings.channels.email = false;
	s.briefings.channels.signal = false;
	s.briefings.channels.telegram = false;
	s.briefings.channels.sms = false;
	assert.equal(s.canAdvanceStep4, true);
});

test('canAdvanceStep4 #164 AC#1c: beide Reports aus → trotzdem true', () => {
	const s = new WizardState();
	s.briefings.reports.morning.enabled = false;
	s.briefings.reports.evening.enabled = false;
	assert.equal(s.canAdvanceStep4, true);
});

// --- Sub-Spec #164 §3.2: canAdvanceCurrent case 4 → canAdvanceStep4 --------
// AC#18 (#164) — Switch case 4 delegiert auf den Getter (statt literal true).

test('canAdvanceCurrent #164 AC#2: Step 4 delegiert auf canAdvanceStep4', () => {
	const s = new WizardState();
	s.currentStep = 4;
	// Identitaet pruefen: canAdvanceCurrent === canAdvanceStep4
	assert.equal(s.canAdvanceCurrent, s.canAdvanceStep4);
	assert.equal(s.canAdvanceCurrent, true);
});

// --- Sub-Spec #164 §3.3: toTripPayload() schreibt report_config -----------
// Helper: minimal valide Setup-Funktion fuer die Mapping-Tests.
function makeStateWithDefaults(): WizardState {
	const s = new WizardState();
	s.activity = 'trekking';
	s.name = 'Step4-Test';
	s.startDate = '2026-06-01';
	return s;
}

test('toTripPayload #164 AC#15a: report_config.send_email = briefings.channels.email', () => {
	const s = makeStateWithDefaults();
	s.briefings.channels.email = true;
	const rc = s.toTripPayload().report_config as Record<string, unknown> | undefined;
	assert.ok(rc, 'report_config muss vorhanden sein');
	assert.equal(rc.send_email, true);

	const s2 = makeStateWithDefaults();
	s2.briefings.channels.email = false;
	const rc2 = s2.toTripPayload().report_config as Record<string, unknown> | undefined;
	assert.ok(rc2);
	assert.equal(rc2.send_email, false);
});

test('toTripPayload #164 AC#15b: report_config.send_signal = briefings.channels.signal', () => {
	const s = makeStateWithDefaults();
	s.briefings.channels.signal = true;
	const rc = s.toTripPayload().report_config as Record<string, unknown> | undefined;
	assert.ok(rc, 'report_config muss vorhanden sein');
	assert.equal(rc.send_signal, true);

	const s2 = makeStateWithDefaults();
	s2.briefings.channels.signal = false;
	const rc2 = s2.toTripPayload().report_config as Record<string, unknown> | undefined;
	assert.ok(rc2);
	assert.equal(rc2.send_signal, false);
});

test('toTripPayload #164 AC#15c: report_config.send_telegram = briefings.channels.telegram', () => {
	const s = makeStateWithDefaults();
	s.briefings.channels.telegram = true;
	const rc = s.toTripPayload().report_config as Record<string, unknown> | undefined;
	assert.ok(rc, 'report_config muss vorhanden sein');
	assert.equal(rc.send_telegram, true);

	const s2 = makeStateWithDefaults();
	s2.briefings.channels.telegram = false;
	const rc2 = s2.toTripPayload().report_config as Record<string, unknown> | undefined;
	assert.ok(rc2);
	assert.equal(rc2.send_telegram, false);
});

test('toTripPayload #164 AC#15d: report_config.send_sms = briefings.channels.sms', () => {
	const s = makeStateWithDefaults();
	s.briefings.channels.sms = false;
	const rc = s.toTripPayload().report_config as Record<string, unknown> | undefined;
	assert.ok(rc, 'report_config muss vorhanden sein');
	assert.equal(rc.send_sms, false);
});

test('toTripPayload #164 AC#16a: report_config.morning_time = briefings.reports.morning.time', () => {
	const s = makeStateWithDefaults();
	s.briefings.reports.morning.time = '07:30';
	const rc = s.toTripPayload().report_config as Record<string, unknown> | undefined;
	assert.ok(rc, 'report_config muss vorhanden sein');
	assert.equal(rc.morning_time, '07:30');
});

test('toTripPayload #164 AC#16b: report_config.evening_time = briefings.reports.evening.time', () => {
	const s = makeStateWithDefaults();
	s.briefings.reports.evening.time = '21:15';
	const rc = s.toTripPayload().report_config as Record<string, unknown> | undefined;
	assert.ok(rc, 'report_config muss vorhanden sein');
	assert.equal(rc.evening_time, '21:15');
});

test('toTripPayload #164 AC#17a: report_config.enabled = true wenn beide Reports aktiv', () => {
	const s = makeStateWithDefaults();
	s.briefings.reports.morning.enabled = true;
	s.briefings.reports.evening.enabled = true;
	const rc = s.toTripPayload().report_config as Record<string, unknown> | undefined;
	assert.ok(rc, 'report_config muss vorhanden sein');
	assert.equal(rc.enabled, true);
});

test('toTripPayload #164 AC#17b: report_config.enabled = true wenn nur morning aktiv', () => {
	const s = makeStateWithDefaults();
	s.briefings.reports.morning.enabled = true;
	s.briefings.reports.evening.enabled = false;
	const rc = s.toTripPayload().report_config as Record<string, unknown> | undefined;
	assert.ok(rc, 'report_config muss vorhanden sein');
	assert.equal(rc.enabled, true);
});

test('toTripPayload #164 AC#17c: report_config.enabled = false wenn beide Reports aus', () => {
	const s = makeStateWithDefaults();
	s.briefings.reports.morning.enabled = false;
	s.briefings.reports.evening.enabled = false;
	const rc = s.toTripPayload().report_config as Record<string, unknown> | undefined;
	assert.ok(rc, 'report_config muss vorhanden sein');
	assert.equal(rc.enabled, false);
});

// Issue #224: AC#18/AC#18b/AC#19 entfernt — `briefings.thresholds` und der
// `report_config.alert_thresholds`-Block existieren nicht mehr. Ersatz-Tests
// stehen weiter unten als "Issue #224 AC-4/AC-5/AC-6".

test('toTripPayload #164 AC#20: KEINE alten change_threshold_*-Felder im report_config', () => {
	const s = makeStateWithDefaults();
	const rc = s.toTripPayload().report_config as Record<string, unknown> | undefined;
	assert.ok(rc, 'report_config muss vorhanden sein');
	assert.equal(
		Object.prototype.hasOwnProperty.call(rc, 'change_threshold_temp_c'),
		false,
		'change_threshold_temp_c darf NICHT geschrieben werden'
	);
	assert.equal(
		Object.prototype.hasOwnProperty.call(rc, 'change_threshold_wind_kmh'),
		false,
		'change_threshold_wind_kmh darf NICHT geschrieben werden'
	);
	assert.equal(
		Object.prototype.hasOwnProperty.call(rc, 'change_threshold_precip_mm'),
		false,
		'change_threshold_precip_mm darf NICHT geschrieben werden'
	);
});

// --- Issue #197: WizardState.save() Redirect-Fallback ----------------------
//
// Spec: docs/specs/bugfix/wizard_save_redirect_fallback.md
//
// Diese Tests inspizieren den Quellcode statisch (readFileSync), weil:
//  - Im Plain-Node-Kontext sind die Lazy-Imports `$lib/api` und
//    `$app/navigation` nicht aufloesbar. Mocks sind projektweit verboten.
//  - AC-1/AC-2 sind durch die statische Source-Form 1:1 erfuellt (genau ein
//    goto-Aufruf auf '/trips' innerhalb des try-Blocks bestimmt das
//    Laufzeit-Verhalten).
//  - AC-3 und AC-4 sind explizit Code-Marker- bzw. Spec-Datei-Tests.

import { readFileSync } from 'node:fs';

/** Liefert den Substring der save()-Methode (ohne Body-aeussere Klammern). */
function extractSaveMethod(source: string): string {
	const startMarker = 'async save(): Promise<void>';
	const startIdx = source.indexOf(startMarker);
	assert.ok(startIdx >= 0, "save()-Methoden-Header nicht gefunden in wizardState.svelte.ts");
	// Klammer-Balance ab dem '{' nach dem Header.
	const braceStart = source.indexOf('{', startIdx);
	assert.ok(braceStart >= 0, "save()-Methoden-Body-Start '{' nicht gefunden");
	let depth = 0;
	for (let i = braceStart; i < source.length; i++) {
		const c = source[i];
		if (c === '{') depth++;
		else if (c === '}') {
			depth--;
			if (depth === 0) {
				return source.slice(braceStart, i + 1);
			}
		}
	}
	throw new Error('save()-Methoden-Body nicht geschlossen — Klammer-Balance gebrochen');
}

test("AC-1 #197 → #436: save() navigiert zu '/trips/${created.id}' — Template-Literal-Navigation", () => {
	const sourcePath = new URL('../wizardState.svelte.ts', import.meta.url);
	const source = readFileSync(sourcePath, 'utf-8');
	const saveBody = extractSaveMethod(source);

	// Erwartet: Template-Literal-Navigation zu /trips/${created.id}
	const expectedTemplate = /goto\(\s*`\/trips\/\$\{/;
	assert.ok(
		expectedTemplate.test(saveBody),
		"save() muss 'goto(`/trips/${...}`)' enthalten — Navigation zum neu erstellten Trip (#436)"
	);

	// Erwartet: Fallback-Kondition created?.id ? ... : '/trips'
	const conditionalPattern = /created(\?\.|\.)id\s*\?/;
	assert.ok(
		conditionalPattern.test(saveBody),
		"save() muss eine id-Kondition 'created?.id ?' enthalten — Fallback auf '/trips' (#436)"
	);
});

test('AC-2 #197: goto-Aufruf steht innerhalb des try-Blocks von save()', () => {
	const sourcePath = new URL('../wizardState.svelte.ts', import.meta.url);
	const source = readFileSync(sourcePath, 'utf-8');
	const saveBody = extractSaveMethod(source);

	const tryIdx = saveBody.indexOf('try {');
	const gotoIdx = saveBody.indexOf('goto(');
	const catchIdx = saveBody.search(/catch\s*\(\s*e\s*:/);

	assert.ok(tryIdx >= 0, "save() muss einen 'try {'-Block enthalten");
	assert.ok(gotoIdx >= 0, "save() muss einen 'goto('-Aufruf enthalten");
	assert.ok(catchIdx >= 0, "save() muss einen 'catch (e:'-Block enthalten");

	assert.ok(
		tryIdx < gotoIdx,
		"goto-Aufruf muss NACH 'try {' stehen (innerhalb des try-Blocks)"
	);
	assert.ok(
		gotoIdx < catchIdx,
		"goto-Aufruf muss VOR 'catch (e:' stehen (nicht im catch-Block)"
	);
});

test('AC-4 #197: Master-Spec §1.4 nennt /trips als Fallback (nicht /) mit Verweis auf #197', () => {
	const specPath = new URL(
		'../../../../../../docs/specs/modules/epic_136_trip_wizard.md',
		import.meta.url
	);
	const spec = readFileSync(specPath, 'utf-8');

	// a) Fallback-Klausel zeigt auf /trips (nicht nur auf /).
	assert.ok(
		spec.includes('Fallback auf /trips') || spec.includes('Fallback auf `/trips`'),
		"Master-Spec muss 'Fallback auf /trips' enthalten (#197 — Korrektur auf Trip-Liste statt /)"
	);

	// b) Verweis auf Issue #197 ist im Dokument vorhanden.
	assert.ok(
		spec.includes('#197') || spec.includes('Issue 197') || spec.includes('Issue #197'),
		"Master-Spec muss auf Issue #197 verweisen (Begruendung des Fallback-Targets)"
	);
});

// --- Issue #224: WizardState.alertRules direct state (kein Mapper mehr) -----
//
// Spec: docs/specs/modules/issue_224_wizard_alert_rules_editor.md
// AC-2/AC-4/AC-5/AC-6/AC-7 — der Wizard schreibt AlertRule[]-Objekte direkt
// aus einem Top-Level-State `alertRules: AlertRule[]`, ohne
// `mapBriefingsToAlertRules` und ohne `report_config.alert_thresholds`-Block.

test('Issue #224 AC-2: alertRules ist initial leeres Array', () => {
	const s = new WizardState();
	assert.ok(Array.isArray(s.alertRules), 'alertRules muss ein Array sein');
	assert.equal(s.alertRules.length, 0, 'alertRules initial leer');
});

test('Issue #224 AC-4: toTripPayload schreibt alertRules als Tiefkopie in trip.alert_rules', () => {
	const s = new WizardState();
	s.name = 'Issue 224 AC-4';
	const rule = {
		id: 'r1',
		kind: 'absolute' as const,
		metric: 'temperature_min' as const,
		threshold: -10,
		unit: '°C',
		severity: 'critical' as const,
		enabled: true
	};
	s.alertRules = [rule];
	const trip = s.toTripPayload();
	assert.ok(trip.alert_rules, 'alert_rules muss gesetzt sein');
	assert.equal(trip.alert_rules!.length, 1);
	assert.equal(trip.alert_rules![0].metric, 'temperature_min');
	assert.equal(trip.alert_rules![0].severity, 'critical');
	assert.equal(trip.alert_rules![0].threshold, -10);
	assert.notStrictEqual(
		trip.alert_rules![0],
		rule,
		'Tiefkopie — keine Referenz-Gleichheit zur State-Rule'
	);
});

test('Issue #224 AC-5: toTripPayload ohne alertRules → kein alert_rules im Payload', () => {
	const s = new WizardState();
	s.name = 'Issue 224 AC-5';
	const trip = s.toTripPayload();
	assert.ok(
		trip.alert_rules === undefined || trip.alert_rules.length === 0,
		'leere alertRules → kein alert_rules-Feld im Payload'
	);
});

test('Issue #224 AC-6: toTripPayload schreibt KEINEN report_config.alert_thresholds-Block', () => {
	const s = new WizardState();
	s.name = 'Issue 224 AC-6';
	s.alertRules = [
		{
			id: 'r1',
			kind: 'absolute' as const,
			metric: 'wind_gust' as const,
			threshold: 50,
			unit: 'km/h',
			severity: 'warning' as const,
			enabled: true
		}
	];
	const rc = s.toTripPayload().report_config as Record<string, unknown> | undefined;
	assert.ok(rc, 'report_config muss vorhanden sein');
	assert.equal(
		Object.prototype.hasOwnProperty.call(rc, 'alert_thresholds'),
		false,
		'alert_thresholds-Block ist gestrichen — Wizard schreibt ihn nicht mehr'
	);
});

test('Issue #224 AC-7: BriefingConfig.thresholds existiert nicht mehr (Runtime-Schnitt)', () => {
	const s = new WizardState();
	const briefings = s.briefings as unknown as Record<string, unknown>;
	assert.equal(
		Object.prototype.hasOwnProperty.call(briefings, 'thresholds'),
		false,
		'briefings.thresholds wurde aus BriefingConfig entfernt'
	);
});
