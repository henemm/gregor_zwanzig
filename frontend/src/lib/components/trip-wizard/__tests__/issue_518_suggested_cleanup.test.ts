// TDD RED — Issue #518: KI/Bestätigen-Verwerfen im Trip-Wizard entfernen.
//
// Spec: docs/specs/modules/issue_518_wizard_suggested_cleanup.md
//
// Diese Tests beschreiben das NEUE erwartete Verhalten (nach Cleanup).
// Sie MÜSSEN rot sein, solange der alte Code noch existiert.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-wizard/__tests__/issue_518_suggested_cleanup.test.ts

// --- Globals für Svelte-5-Runen BEFORE Modul-Import ----------
type RuneFn = (v: unknown) => unknown;
const g = globalThis as unknown as Record<string, RuneFn>;
if (typeof g.$state !== 'function') g.$state = (v: unknown) => v;
if (typeof g.$derived !== 'function') g.$derived = (v: unknown) => v;
if (typeof g.$effect !== 'function') g.$effect = (_fn: unknown) => {};

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { WizardState } from '../wizardState.svelte.ts';

// --- Hilfsdaten ----------------------------------------------------------------

function makeStageWithWaypoints() {
	return {
		id: 'st-1',
		name: 'Etappe 1',
		date: '2026-06-01',
		waypoints: [
			{ id: 'w1', name: 'Gipfel', lat: 45.0, lon: 6.5, elevation_m: 2400 },
			{ id: 'w2', name: 'Hütte', lat: 45.1, lon: 6.6, elevation_m: 1800 }
		]
	};
}

// --- AC-4a: addStage setzt KEIN suggested:true mehr ----------------------------
// ERWARTET: nach addStage haben Wegpunkte kein suggested-Flag.
// AKTUELL (vor Fix): addStage markiert Wegpunkte automatisch mit suggested:true → FAIL.

test('AC-4a: addStage setzt kein suggested:true auf Wegpunkten', () => {
	const s = new WizardState();
	s.addStage(makeStageWithWaypoints());

	for (const wp of s.stages[0].waypoints) {
		assert.equal(
			Object.prototype.hasOwnProperty.call(wp, 'suggested'),
			false,
			`Wegpunkt "${wp.name}" darf kein suggested-Property haben`
		);
	}
});

// --- AC-4b: confirmWaypoint existiert nicht mehr auf WizardState ---------------
// ERWARTET: Die Methode ist gelöscht.
// AKTUELL (vor Fix): confirmWaypoint existiert als Methode → FAIL.

test('AC-4b: WizardState hat keine confirmWaypoint-Methode mehr', () => {
	const s = new WizardState();
	assert.equal(
		typeof (s as unknown as Record<string, unknown>)['confirmWaypoint'],
		'undefined',
		'confirmWaypoint soll nach dem Cleanup nicht mehr existieren'
	);
});

// --- AC-4c: Explizit gesetztes suggested-Flag aus externem Import bleibt beim Save erhalten ---
// (Regression: toTripPayload darf Wegpunkt-Daten nicht mehr verändern, weil stripSuggested weg ist.)
// ERWARTET: toTripPayload lässt suggested-Flag unverändert durch (wird nicht gestrippt).
// AKTUELL (vor Fix): toTripPayload ruft stripSuggested auf → suggested-Flag wird ENTFERNT → FAIL.

test('AC-4c: toTripPayload entfernt suggested-Flag nicht mehr (kein stripSuggested)', () => {
	const s = new WizardState();
	s.name = 'Test-Trip';
	// Direkt in stages schreiben (umgeht addStage-Logik), um suggested:true zu simulieren
	// (z.B. von einem Backend-Import, der das Feld noch mitschickt).
	s.stages = [
		{
			id: 'st-1',
			name: 'Etappe 1',
			date: '2026-06-01',
			waypoints: [
				{ id: 'w1', name: 'Gipfel', lat: 45.0, lon: 6.5, elevation_m: 2400, suggested: true }
			]
		}
	];
	const payload = s.toTripPayload();
	// Nach dem Fix: suggested bleibt erhalten (kein stripSuggested).
	assert.equal(
		payload.stages[0].waypoints[0].suggested,
		true,
		'toTripPayload darf suggested nicht mehr entfernen (stripSuggested ist gelöscht)'
	);
});

// --- AC-5a: rejectWaypoint existiert noch und löscht den Wegpunkt --------------
// ERWARTET: bleibt erhalten und funktioniert (Regression).
// AKTUELL: funktioniert bereits → GRÜN (Regression-Schutz).

test('AC-5a: rejectWaypoint löscht Wegpunkt aus stage.waypoints (bleibt erhalten)', () => {
	const s = new WizardState();
	s.addStage(makeStageWithWaypoints());
	assert.equal(s.stages[0].waypoints.length, 2);

	s.rejectWaypoint('st-1', 'w1');

	assert.equal(s.stages[0].waypoints.length, 1, 'Wegpunkt soll nach rejectWaypoint entfernt sein');
	assert.equal(s.stages[0].waypoints[0].id, 'w2', 'verbleibender Wegpunkt ist w2');
});

// --- AC-5b: rejectWaypoint bei falscher stageId → kein Crash -------------------

test('AC-5b: rejectWaypoint mit falscher stageId → kein Crash, State unverändert', () => {
	const s = new WizardState();
	s.addStage(makeStageWithWaypoints());
	const before = JSON.stringify(s.stages);

	s.rejectWaypoint('st-UNBEKANNT', 'w1');

	assert.equal(JSON.stringify(s.stages), before, 'State soll unverändert sein');
});
