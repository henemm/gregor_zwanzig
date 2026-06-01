// TDD RED — Issue #506 Rest-Scope: Tote Props + @deprecated-Annotation + Navigation-Doku
//
// Spec: docs/specs/modules/issue_506_restscope.md
//
// Source-Inspection-Tests: prüfen, dass die NEUEN Muster im Code vorhanden
// und die ALTEN Muster entfernt sind. Vor der Implementierung SCHEITERN sie (RED).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-detail/waypoints/issue_506_restscope.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const ROOT = fileURLToPath(new URL('../../../../..', import.meta.url)); // -> frontend root

function readFrontend(relPath: string): string {
	return readFileSync(join(ROOT, 'src', relPath), 'utf-8');
}

function readProject(relPath: string): string {
	const projectRoot = join(ROOT, '..');
	return readFileSync(join(projectRoot, relPath), 'utf-8');
}

function projectFileExists(relPath: string): boolean {
	const projectRoot = join(ROOT, '..');
	return existsSync(join(projectRoot, relPath));
}

// ---------------------------------------------------------------------------
// AC-1: WaypointCard enthält KEIN onConfirm/onReject in der Props-Interface
// ---------------------------------------------------------------------------

test('AC-1a: WaypointCard.svelte enthält KEIN onConfirm in der Props-Interface', () => {
	const src = readFrontend(
		'lib/components/trip-detail/waypoints/WaypointCard.svelte'
	);
	assert.ok(
		!src.includes('onConfirm'),
		'WaypointCard.svelte darf kein onConfirm mehr enthalten — tote @deprecated-Prop entfernen'
	);
});

test('AC-1b: WaypointCard.svelte enthält KEIN onReject in der Props-Interface', () => {
	const src = readFrontend(
		'lib/components/trip-detail/waypoints/WaypointCard.svelte'
	);
	assert.ok(
		!src.includes('onReject'),
		'WaypointCard.svelte darf kein onReject mehr enthalten — tote @deprecated-Prop entfernen'
	);
});

// ---------------------------------------------------------------------------
// AC-2: EditStagesPanelNew enthält KEIN noop, übergibt kein onConfirm/onReject
// ---------------------------------------------------------------------------

test('AC-2a: EditStagesPanelNew.svelte enthält KEIN noop', () => {
	const src = readFrontend('lib/components/edit/EditStagesPanelNew.svelte');
	assert.ok(
		!src.includes('noop'),
		'EditStagesPanelNew.svelte darf kein noop() mehr enthalten — Glue-Code für tote Props entfernen'
	);
});

test('AC-2b: EditStagesPanelNew.svelte übergibt KEIN onConfirm an WaypointCard', () => {
	const src = readFrontend('lib/components/edit/EditStagesPanelNew.svelte');
	assert.ok(
		!src.includes('onConfirm={'),
		'EditStagesPanelNew.svelte darf onConfirm nicht an WaypointCard übergeben'
	);
});

test('AC-2c: EditStagesPanelNew.svelte übergibt KEIN onReject an WaypointCard', () => {
	const src = readFrontend('lib/components/edit/EditStagesPanelNew.svelte');
	assert.ok(
		!src.includes('onReject={'),
		'EditStagesPanelNew.svelte darf onReject nicht an WaypointCard übergeben'
	);
});

// ---------------------------------------------------------------------------
// AC-3: types.ts — suggested? ist mit @deprecated kommentiert UND existiert noch
// ---------------------------------------------------------------------------

test('AC-3a: types.ts Waypoint.suggested? hat @deprecated-Kommentar', () => {
	const src = readFrontend('lib/types.ts');
	// Kommentar muss direkt vor oder auf derselben Zeile wie suggested? stehen
	const hasDeprecatedSuggested =
		/@deprecated[^\n]*\n\s*suggested\?/.test(src) ||
		/\/\*\*[^*]*@deprecated[^*]*\*\/\s*\n\s*suggested\?/.test(src) ||
		/suggested\?[^\n]*@deprecated/.test(src);
	assert.ok(
		hasDeprecatedSuggested,
		'types.ts: Waypoint.suggested? muss mit /** @deprecated */ annotiert sein'
	);
});

test('AC-3b: types.ts Waypoint.suggested? existiert weiterhin (nicht entfernt)', () => {
	const src = readFrontend('lib/types.ts');
	assert.ok(
		src.includes('suggested?'),
		'types.ts: Waypoint.suggested? muss weiterhin vorhanden sein (wird von stripSuggested() benötigt)'
	);
});

// ---------------------------------------------------------------------------
// AC-4: docs/architecture/navigation.md existiert und enthält Pflicht-Inhalte
// ---------------------------------------------------------------------------

test('AC-4a: docs/architecture/navigation.md existiert', () => {
	assert.ok(
		projectFileExists('docs/architecture/navigation.md'),
		'docs/architecture/navigation.md muss existieren — kanonisches Navigationsmodell dokumentieren'
	);
});

test('AC-4b: navigation.md enthält ?tab= als kanonische URL-Konvention', () => {
	const src = readProject('docs/architecture/navigation.md');
	assert.ok(
		src.includes('?tab=') || src.includes('tab='),
		'navigation.md muss ?tab= als kanonische URL-Konvention beschreiben'
	);
});

test('AC-4c: navigation.md enthält valide Tab-Werte für Trip-Detail', () => {
	const src = readProject('docs/architecture/navigation.md');
	// Mindestens 4 der 6 Tab-Werte müssen erwähnt sein
	const tabValues = ['overview', 'stages', 'weather', 'briefings', 'alerts', 'preview'];
	const found = tabValues.filter(v => src.includes(v));
	assert.ok(
		found.length >= 4,
		`navigation.md muss valide Tab-Werte enthalten. Gefunden: ${found.join(', ')} (min. 4 von 6 nötig)`
	);
});

test('AC-4d: navigation.md enthält goto-Muster mit replaceState', () => {
	const src = readProject('docs/architecture/navigation.md');
	assert.ok(
		src.includes('replaceState') || src.includes('goto'),
		'navigation.md muss das goto-Muster mit replaceState dokumentieren'
	);
});

test('AC-4e: navigation.md enthält 301-Redirect-Konvention', () => {
	const src = readProject('docs/architecture/navigation.md');
	assert.ok(
		src.includes('301') || src.includes('redirect'),
		'navigation.md muss die 301-Redirect-Konvention für veraltete Routen beschreiben'
	);
});
