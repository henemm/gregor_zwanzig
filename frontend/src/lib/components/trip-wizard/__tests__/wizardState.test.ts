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

// --- Sub-Spec #163 §3.1: addStage-Patch (suggested:true zentral) -----------
// AC#16 — Waypoints ohne suggested-Flag erhalten suggested:true; explizite
// Werte (true / false) bleiben erhalten.

test('addStage AC#16a: Waypoints ohne suggested-Flag → nach addStage suggested:true', () => {
	const s = new WizardState();
	s.addStage({
		id: 'st-a',
		name: 'Etappe A',
		date: '2026-06-01',
		waypoints: [
			{ id: 'w1', name: 'Gipfel', lat: 0, lon: 0, elevation_m: 2000 },
			{ id: 'w2', name: 'Hütte', lat: 0, lon: 0, elevation_m: 1500 }
		]
	});
	const stage = s.stages[0];
	assert.equal(stage.waypoints.length, 2);
	assert.equal(stage.waypoints[0].suggested, true, 'wp1 ohne Flag → true');
	assert.equal(stage.waypoints[1].suggested, true, 'wp2 ohne Flag → true');
});

test('addStage AC#16b: Waypoints mit suggested:true (explizit) → bleibt true', () => {
	const s = new WizardState();
	s.addStage({
		id: 'st-b',
		name: 'Etappe B',
		date: '2026-06-01',
		waypoints: [
			{ id: 'w1', name: 'Gipfel', lat: 0, lon: 0, elevation_m: 2000, suggested: true }
		]
	});
	assert.equal(s.stages[0].waypoints[0].suggested, true);
});

test('addStage AC#16c: Waypoints mit suggested:false (explizit) → bleibt false', () => {
	const s = new WizardState();
	s.addStage({
		id: 'st-c',
		name: 'Etappe C',
		date: '2026-06-01',
		waypoints: [
			{ id: 'w1', name: 'Gipfel', lat: 0, lon: 0, elevation_m: 2000, suggested: false }
		]
	});
	assert.equal(
		s.stages[0].waypoints[0].suggested,
		false,
		'explizit false darf nicht zu true werden'
	);
});

// --- Sub-Spec #163 §3.2: confirmWaypoint(stageId, waypointId) --------------
// AC#14 — Entfernt suggested-Flag (Property weg, nicht nur false).

test('confirmWaypoint AC#14a: entfernt suggested-Property aus angegebenem Wegpunkt', () => {
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
	// Pre-Condition: addStage-Patch hat beide auf suggested:true gesetzt
	assert.equal(s.stages[0].waypoints[0].suggested, true);
	assert.equal(s.stages[0].waypoints[1].suggested, true);

	s.confirmWaypoint('st-1', 'w1');

	const wp1 = s.stages[0].waypoints[0];
	const wp2 = s.stages[0].waypoints[1];
	assert.equal(
		Object.prototype.hasOwnProperty.call(wp1, 'suggested'),
		false,
		'suggested-Property muss vollstaendig entfernt sein, nicht nur false'
	);
	assert.equal(wp2.suggested, true, 'wp2 bleibt unangetastet');
});

test('confirmWaypoint AC#14b: falsche stageId → kein Crash, State unveraendert', () => {
	const s = new WizardState();
	s.addStage({
		id: 'st-1',
		name: 'Etappe 1',
		date: '2026-06-01',
		waypoints: [{ id: 'w1', name: 'X', lat: 0, lon: 0, elevation_m: 100 }]
	});
	const before = JSON.stringify(s.stages);
	s.confirmWaypoint('st-DOES-NOT-EXIST', 'w1');
	assert.equal(JSON.stringify(s.stages), before, 'State unveraendert bei falscher stageId');
});

test('confirmWaypoint AC#14c: falsche waypointId → kein Crash, suggested bleibt', () => {
	const s = new WizardState();
	s.addStage({
		id: 'st-1',
		name: 'Etappe 1',
		date: '2026-06-01',
		waypoints: [{ id: 'w1', name: 'X', lat: 0, lon: 0, elevation_m: 100 }]
	});
	s.confirmWaypoint('st-1', 'wp-DOES-NOT-EXIST');
	assert.equal(
		s.stages[0].waypoints[0].suggested,
		true,
		'wp1 bleibt suggested:true bei falscher waypointId'
	);
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

test('toTripPayload #164 AC#18: alert_thresholds-Block geschrieben wenn min. 1 Feld nicht null', () => {
	const s = makeStateWithDefaults();
	s.briefings.thresholds.gust_kmh = 80;
	s.briefings.thresholds.precip_mm = 15;
	s.briefings.thresholds.thunder_level = 'HIGH';
	s.briefings.thresholds.snow_line_m = 1800;
	const rc = s.toTripPayload().report_config as Record<string, unknown> | undefined;
	assert.ok(rc, 'report_config muss vorhanden sein');
	const at = rc.alert_thresholds as Record<string, unknown> | undefined;
	assert.ok(at, 'alert_thresholds-Block muss vorhanden sein');
	assert.equal(at.gust_kmh, 80);
	assert.equal(at.precip_mm, 15);
	assert.equal(at.thunder_level, 'HIGH');
	assert.equal(at.snow_line_m, 1800);
});

test('toTripPayload #164 AC#18b: alert_thresholds enthaelt alle 4 Felder auch wenn nur 1 gesetzt', () => {
	const s = makeStateWithDefaults();
	s.briefings.thresholds.gust_kmh = 70;
	// andere bleiben null
	const rc = s.toTripPayload().report_config as Record<string, unknown> | undefined;
	assert.ok(rc, 'report_config muss vorhanden sein');
	const at = rc.alert_thresholds as Record<string, unknown> | undefined;
	assert.ok(at, 'alert_thresholds-Block muss vorhanden sein');
	assert.equal(at.gust_kmh, 70);
	assert.equal(at.precip_mm, null);
	assert.equal(at.thunder_level, null);
	assert.equal(at.snow_line_m, null);
});

test('toTripPayload #164 AC#19: KEIN alert_thresholds-Block wenn alle 4 thresholds null', () => {
	const s = makeStateWithDefaults();
	// Defaults: alle null
	assert.equal(s.briefings.thresholds.gust_kmh, null);
	assert.equal(s.briefings.thresholds.precip_mm, null);
	assert.equal(s.briefings.thresholds.thunder_level, null);
	assert.equal(s.briefings.thresholds.snow_line_m, null);
	const rc = s.toTripPayload().report_config as Record<string, unknown> | undefined;
	assert.ok(rc, 'report_config muss vorhanden sein');
	assert.equal(
		Object.prototype.hasOwnProperty.call(rc, 'alert_thresholds'),
		false,
		'alert_thresholds darf NICHT geschrieben werden wenn alle null'
	);
});

test('toTripPayload #164 AC#20: KEINE alten change_threshold_*-Felder im report_config', () => {
	const s = makeStateWithDefaults();
	s.briefings.thresholds.gust_kmh = 50;
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
