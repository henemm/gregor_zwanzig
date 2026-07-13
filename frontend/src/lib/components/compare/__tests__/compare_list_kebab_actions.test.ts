// TDD RED — Issue #1256 Scheibe 1: Listen-Kebab ohne "Archivieren" (AC-1).
//
// Spec: docs/specs/modules/issue_1256_compare_ui_rewire.md (AC-1, AC-2)
// Soll: molecules.jsx:1018-1027 — compareActions('active'|'paused') liefert
// im Listen-Kontext genau 5 Einträge (Pausieren/Aktivieren, Briefing jetzt
// senden, Vorschau öffnen, Bearbeiten, Löschen) — OHNE "Archivieren".
// Archivieren wandert exklusiv in die künftige Hub-Header-Lifecycle-Liste
// (Scheibe 3, compareLifecycleActions()) — nicht Teil dieser Scheibe.
//
// RED-Erwartung: subscriptionHelpers.ts::compareActions() liefert im Ist
// (vor Scheibe 1) noch 6 Einträge inkl. `archive` (siehe
// bug_626_compare_menu_actions.test.ts / issue_488_compare_tile_atoms.test.ts
// / issue_627_send_action.test.ts, die aktuell 6 erzwingen) → alle Tests
// hier schlagen fehl, bis `archive` aus dem active/paused-Zweig entfernt ist.
//
// AC-2 (compareActions('draft') bleibt bei 2 Einträgen, unverändert) wird
// bereits vollständig durch bug_626_compare_menu_actions.test.ts abgedeckt
// (Regressionsnachweis) — hier bewusst nicht dupliziert.
//
// Bekannte Nebenwirkung (siehe Entwickler-Bericht): CompareKebab.svelte
// speist sowohl die Liste als auch den Hub-Header ausschließlich aus dieser
// einen Funktion (kein `variant`/Kontext-Parameter in dieser Scheibe) — die
// Reduktion auf 5 Einträge nimmt daher vorübergehend auch dem Hub-Header
// "Archivieren", bis Scheibe 3 eine eigene `compareLifecycleActions()` samt
// injizierbarer Aktionsliste einführt. Das ist ein gestaffelter,
// spezifikationskonformer Zwischenzustand (kein Scope dieser Tests).
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_list_kebab_actions.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

const { compareActions } = await import('../subscriptionHelpers.ts');

describe('Issue #1256 AC-1: compareActions("active") — Listen-Kebab ohne Archivieren', () => {
	test('liefert genau 5 Einträge', () => {
		const actions = compareActions('active');
		assert.equal(
			actions.length,
			5,
			`compareActions("active") muss genau 5 Aktionen liefern (Pausieren, Senden, Vorschau, Bearbeiten, Löschen), hat aber ${actions.length}`
		);
	});

	test('enthält KEIN Item mit id="archive"', () => {
		const actions = compareActions('active');
		const ids = actions.map((a: { id: string }) => a.id);
		assert.ok(
			!ids.includes('archive'),
			'compareActions("active") darf "archive" nicht mehr enthalten (AC-1 — wandert in Hub-Lifecycle-Kebab, Scheibe 3)'
		);
	});

	test('enthält weiterhin pause, send, preview, edit, delete (in dieser Reihenfolge)', () => {
		const actions = compareActions('active');
		const ids = actions.map((a: { id: string }) => a.id);
		assert.deepEqual(
			ids,
			['pause', 'send', 'preview', 'edit', 'delete'],
			`compareActions("active") muss exakt [pause, send, preview, edit, delete] liefern, hat aber [${ids.join(', ')}]`
		);
	});

	test('delete-Item hat weiterhin danger=true', () => {
		const actions = compareActions('active');
		const del = actions.find((a: { id: string }) => a.id === 'delete');
		assert.ok(del, 'compareActions("active") muss ein "delete"-Item enthalten');
		assert.equal(del!.danger, true, 'delete-Item muss danger=true haben');
	});
});

describe('Issue #1256 AC-1: compareActions("paused") — Listen-Kebab ohne Archivieren', () => {
	test('liefert genau 5 Einträge', () => {
		const actions = compareActions('paused');
		assert.equal(
			actions.length,
			5,
			`compareActions("paused") muss genau 5 Aktionen liefern, hat aber ${actions.length}`
		);
	});

	test('enthält KEIN Item mit id="archive"', () => {
		const actions = compareActions('paused');
		const ids = actions.map((a: { id: string }) => a.id);
		assert.ok(
			!ids.includes('archive'),
			'compareActions("paused") darf "archive" nicht mehr enthalten (AC-1)'
		);
	});

	test('pause-Item hat weiterhin Label "Aktivieren" bei Status paused (Regression #626)', () => {
		const actions = compareActions('paused');
		const pause = actions.find((a: { id: string }) => a.id === 'pause');
		assert.ok(pause, 'compareActions("paused") muss ein "pause"-Item enthalten');
		assert.equal(pause!.label, 'Aktivieren');
	});
});
