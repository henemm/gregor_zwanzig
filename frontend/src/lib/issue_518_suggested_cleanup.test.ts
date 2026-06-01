// TDD RED — Issue #518: KI/Bestätigen-Verwerfen im Trip-Wizard entfernen
//
// Spec: docs/specs/modules/issue_518_wizard_suggested_cleanup.md
//
// Source-Inspection-Tests: prüfen, dass die alten "suggested"-Muster
// NICHT mehr im Code vorhanden sind. Vor dem Fix SCHEITERN sie (RED),
// weil die Muster noch existieren. Nach dem Fix BESTEHEN sie (GREEN).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/issue_518_suggested_cleanup.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const ROOT = fileURLToPath(new URL('../../..', import.meta.url)); // -> worktree root
const WIZARD = join(ROOT, 'frontend/src/lib/components/trip-wizard');

function read(relPath: string): string {
	return readFileSync(join(WIZARD, relPath), 'utf-8');
}

// ---------------------------------------------------------------------------
// AC-4: wizardState.svelte.ts — suggested-Logik entfernt
// ---------------------------------------------------------------------------

test('AC-4a: wizardState.addStage setzt kein suggested:true mehr (Muster gelöscht)', () => {
	const src = read('wizardState.svelte.ts');
	// Das Muster "suggested: true" taucht in addStage auf um Wegpunkte zu markieren.
	// Nach dem Cleanup darf es dort nicht mehr stehen.
	assert.equal(
		src.includes('suggested: true'),
		false,
		'wizardState.svelte.ts darf "suggested: true" nicht mehr enthalten (addStage-Patch entfernt)'
	);
});

test('AC-4b: wizardState hat keine confirmWaypoint-Methode mehr', () => {
	const src = read('wizardState.svelte.ts');
	assert.equal(
		src.includes('confirmWaypoint'),
		false,
		'wizardState.svelte.ts darf keine confirmWaypoint-Methode mehr enthalten'
	);
});

test('AC-4c: wizardState hat keine stripSuggested-Funktion mehr', () => {
	const src = read('wizardState.svelte.ts');
	assert.equal(
		src.includes('stripSuggested'),
		false,
		'wizardState.svelte.ts darf keine stripSuggested-Funktion mehr enthalten'
	);
});

test('AC-5 (Regression): wizardState hat noch rejectWaypoint', () => {
	const src = read('wizardState.svelte.ts');
	assert.equal(
		src.includes('rejectWaypoint'),
		true,
		'wizardState.svelte.ts muss rejectWaypoint noch enthalten (Löschen-Funktion bleibt)'
	);
});

// ---------------------------------------------------------------------------
// AC-1: TripWizardShell.svelte — Step-Hint-Text bereinigt
// ---------------------------------------------------------------------------

test('AC-1: TripWizardShell stepHints[2] enthält kein "gestrichelt"-Text mehr', () => {
	const src = read('TripWizardShell.svelte');
	assert.equal(
		src.includes('gestrichelt'),
		false,
		'TripWizardShell.svelte darf "gestrichelt" nicht mehr enthalten'
	);
});

test('AC-1b: TripWizardShell stepHints[2] enthält kein "bestätigen oder verwerfen"-Text mehr', () => {
	const src = read('TripWizardShell.svelte');
	// Suche case-insensitive nach dem Hinweis-Text
	assert.equal(
		src.toLowerCase().includes('bestätigen oder verwerfen'),
		false,
		'TripWizardShell.svelte darf "bestätigen oder verwerfen" nicht mehr enthalten'
	);
});

// ---------------------------------------------------------------------------
// AC-2/3: WaypointRow.svelte — uniform, kein Confirm-Button
// ---------------------------------------------------------------------------

test('AC-2: WaypointRow.svelte hat keine isSuggested-Logik mehr', () => {
	const src = read('steps/WaypointRow.svelte');
	assert.equal(
		src.includes('isSuggested'),
		false,
		'WaypointRow.svelte darf keine isSuggested-Ableitung mehr haben'
	);
});

test('AC-2b: WaypointRow.svelte hat keine onConfirm-Prop mehr', () => {
	const src = read('steps/WaypointRow.svelte');
	assert.equal(
		src.includes('onConfirm'),
		false,
		'WaypointRow.svelte darf kein onConfirm-Prop mehr haben'
	);
});

test('AC-3: WaypointRow.svelte hat keinen Bestätigen-Button mehr', () => {
	const src = read('steps/WaypointRow.svelte');
	assert.equal(
		src.includes('trip-wizard-step3-confirm-'),
		false,
		'data-testid="trip-wizard-step3-confirm-{index}" darf nicht mehr existieren'
	);
});

test('AC-3 (Regression): WaypointRow.svelte hat noch den Löschen-Button', () => {
	const src = read('steps/WaypointRow.svelte');
	assert.equal(
		src.includes('trip-wizard-step3-reject-'),
		true,
		'data-testid="trip-wizard-step3-reject-{index}" muss noch vorhanden sein'
	);
});

test('AC-3 (Regression): WaypointRow.svelte hat noch data-testid für Row', () => {
	const src = read('steps/WaypointRow.svelte');
	assert.equal(
		src.includes('trip-wizard-step3-waypoint-row-'),
		true,
		'data-testid="trip-wizard-step3-waypoint-row-{index}" muss noch vorhanden sein'
	);
});

// ---------------------------------------------------------------------------
// Step2Stages.svelte — Vorschläge-Pill entfernt
// ---------------------------------------------------------------------------

test('Step2Stages: suggestedCount-Funktion entfernt', () => {
	const src = read('steps/Step2Stages.svelte');
	assert.equal(
		src.includes('suggestedCount'),
		false,
		'Step2Stages.svelte darf keine suggestedCount-Funktion mehr haben'
	);
});

test('Step2Stages: Vorschläge-Pill entfernt', () => {
	const src = read('steps/Step2Stages.svelte');
	assert.equal(
		src.includes('Vorschläge'),
		false,
		'Step2Stages.svelte darf keine "Vorschläge"-Pill mehr haben'
	);
});

// ---------------------------------------------------------------------------
// Step3Waypoints.svelte — Confirm-Handler entfernt
// ---------------------------------------------------------------------------

test('Step3Waypoints: makeConfirmHandler entfernt', () => {
	const src = read('steps/Step3Waypoints.svelte');
	assert.equal(
		src.includes('makeConfirmHandler'),
		false,
		'Step3Waypoints.svelte darf keinen makeConfirmHandler mehr haben'
	);
});

test('Step3Waypoints: kein confirmWaypoint-Aufruf mehr', () => {
	const src = read('steps/Step3Waypoints.svelte');
	assert.equal(
		src.includes('confirmWaypoint'),
		false,
		'Step3Waypoints.svelte darf keinen confirmWaypoint-Aufruf mehr haben'
	);
});

// ---------------------------------------------------------------------------
// ProfileChart.svelte — uniform Pin-Stil
// ---------------------------------------------------------------------------

test('ProfileChart: kein suggested-Branch mehr', () => {
	const src = read('steps/ProfileChart.svelte');
	assert.equal(
		src.includes('wp.suggested'),
		false,
		'ProfileChart.svelte darf kein "wp.suggested"-Branch mehr haben'
	);
});
