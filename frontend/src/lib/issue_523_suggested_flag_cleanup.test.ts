// Issue #523 — RED-Tests: suggested/waypoint.ai-Flag entfernen (C8 aus #506)
//
// Source-Inspection-Tests: prüfen dass die Felder/Funktionen NICHT mehr im Code stehen.
// Diese Tests scheitern aktuell (RED), weil der Code noch existiert.
// Nach der Implementierung (GREEN) müssen sie bestehen.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/issue_523_suggested_flag_cleanup.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const ROOT = fileURLToPath(new URL('../../..', import.meta.url)); // -> worktree root

function read(relPath: string): string {
	return readFileSync(join(ROOT, relPath), 'utf-8');
}

// AC-5: internal/model/trip.go hat kein Suggested/SuggestionReason mehr
test('AC-5: model/trip.go hat kein Suggested-Feld mehr', () => {
	const src = read('internal/model/trip.go');
	assert.ok(
		!src.includes('Suggested'),
		'internal/model/trip.go darf kein Suggested-Feld mehr enthalten'
	);
});

test('AC-5: model/trip.go hat kein SuggestionReason-Feld mehr', () => {
	const src = read('internal/model/trip.go');
	assert.ok(
		!src.includes('SuggestionReason'),
		'internal/model/trip.go darf kein SuggestionReason-Feld mehr enthalten'
	);
});

// AC-4: frontend/src/lib/types.ts hat kein suggested?/suggestion_reason? mehr
test('AC-4: types.ts hat kein suggested?-Feld mehr', () => {
	const src = read('frontend/src/lib/types.ts');
	assert.ok(
		!src.includes('suggested?'),
		'frontend/src/lib/types.ts darf kein suggested?-Feld mehr im Waypoint-Interface haben'
	);
});

test('AC-4: types.ts hat kein suggestion_reason?-Feld mehr', () => {
	const src = read('frontend/src/lib/types.ts');
	assert.ok(
		!src.includes('suggestion_reason?'),
		'frontend/src/lib/types.ts darf kein suggestion_reason?-Feld mehr haben'
	);
});

// AC-6: waypointEditor.ts hat kein stripSuggested mehr
test('AC-6: waypointEditor.ts hat keine stripSuggested-Funktion mehr', () => {
	const src = read('frontend/src/lib/utils/waypointEditor.ts');
	assert.ok(
		!src.includes('stripSuggested'),
		'frontend/src/lib/utils/waypointEditor.ts darf keine stripSuggested-Funktion mehr enthalten'
	);
});

// AC-7: WaypointPin.svelte hat kein suggested-Prop und keinen dashed-Branch mehr
test('AC-7: WaypointPin.svelte hat kein suggested-Prop mehr', () => {
	const src = read('frontend/src/lib/components/trip-detail/waypoints/WaypointPin.svelte');
	assert.ok(
		!src.includes('suggested'),
		'WaypointPin.svelte darf kein suggested-Prop mehr haben'
	);
});

test('AC-7: WaypointPin.svelte hat keinen stroke-dasharray-Branch mehr', () => {
	const src = read('frontend/src/lib/components/trip-detail/waypoints/WaypointPin.svelte');
	assert.ok(
		!src.includes('stroke-dasharray'),
		'WaypointPin.svelte darf keinen gestrichelten SVG-Branch mehr haben'
	);
});

// WaypointCard: keine deprecated onConfirm/onReject mehr
test('WaypointCard.svelte hat keine deprecated onConfirm-Prop mehr', () => {
	const src = read('frontend/src/lib/components/trip-detail/waypoints/WaypointCard.svelte');
	assert.ok(
		!src.includes('onConfirm'),
		'WaypointCard.svelte darf keine deprecated onConfirm-Prop mehr haben'
	);
});

test('WaypointCard.svelte hat keine deprecated onReject-Prop mehr', () => {
	const src = read('frontend/src/lib/components/trip-detail/waypoints/WaypointCard.svelte');
	assert.ok(
		!src.includes('onReject'),
		'WaypointCard.svelte darf keine deprecated onReject-Prop mehr haben'
	);
});

// Aufrufstellen: kein stripSuggested-Aufruf in den 3 Edit-Komponenten
test('TripEditView.svelte ruft kein stripSuggested mehr auf', () => {
	const src = read('frontend/src/lib/components/edit/TripEditView.svelte');
	assert.ok(
		!src.includes('stripSuggested'),
		'TripEditView.svelte darf stripSuggested nicht mehr aufrufen'
	);
});

test('WaypointsPanel.svelte ruft kein stripSuggested mehr auf', () => {
	const src = read('frontend/src/lib/components/trip-detail/WaypointsPanel.svelte');
	assert.ok(
		!src.includes('stripSuggested'),
		'WaypointsPanel.svelte darf stripSuggested nicht mehr aufrufen'
	);
});

test('EditStagesPanelNew.svelte ruft kein stripSuggested mehr auf', () => {
	const src = read('frontend/src/lib/components/edit/EditStagesPanelNew.svelte');
	assert.ok(
		!src.includes('stripSuggested'),
		'EditStagesPanelNew.svelte darf stripSuggested nicht mehr aufrufen'
	);
});

// Legacy-Handler-Block: nicht mehr in trip.go
test('handler/trip.go hat keine Legacy-suggested-Normalisierung mehr', () => {
	const src = read('internal/handler/trip.go');
	assert.ok(
		!src.includes('wp.Suggested'),
		'internal/handler/trip.go darf keinen Legacy-Block mit wp.Suggested mehr haben'
	);
});
