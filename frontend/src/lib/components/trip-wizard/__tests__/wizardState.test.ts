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
