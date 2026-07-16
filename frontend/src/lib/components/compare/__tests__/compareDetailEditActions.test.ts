// TDD RED — Issue #1261 Teil (a): Compare-Detailseite (Desktop) — „Bearbeiten"
// im ⋮-Kebab auffindbar machen.
//
// Spec: docs/specs/modules/issue_1261_compare_edit_autosave.md
//   § Implementation Details (a), § Acceptance Criteria AC-2/AC-3/AC-4
//
// Der Desktop-Detail-⋮-Kebab (`routes/compare/[id]/+page.svelte:179`) nutzt
// heute `compareLifecycleActions(status)`, die bewusst KEIN `edit` enthält
// (Mobile-Sheet-Vorgabe #1256 Scheibe 8 AC-23). #1261 verlangt einen neuen,
// eng begrenzten Helper `compareDetailActions(status)` NUR für den
// Desktop-Detail-Call-Site — `compareLifecycleActions()` selbst bleibt
// unangetastet (Regressionsnachweis unten).
//
// `compareDetailActions` existiert in `subscriptionHelpers.ts` noch NICHT →
// der Import wirft einen Modul-Resolve-Fehler und alle Tests scheitern (RED).
//
// Reine Verhaltenstests (echter Funktionsaufruf, KEIN Mock, KEINE
// Datei-Inhalt-Prüfung).
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compareDetailEditActions.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

// Direkter Funktionsaufruf — kein Mock, kein DOM.
const { compareDetailActions, compareLifecycleActions } = await import('../subscriptionHelpers.ts');

describe('AC-2: compareDetailActions("active") enthält "Bearbeiten"', () => {
	test('Eintrag {id:"edit", label:"Bearbeiten"} ist enthalten', () => {
		const actions = compareDetailActions('active');
		const edit = actions.find((a: { id: string }) => a.id === 'edit');
		assert.ok(edit, 'kein "edit"-Eintrag in compareDetailActions("active") gefunden');
		assert.equal(edit?.label, 'Bearbeiten');
	});
});

describe('AC-2: compareDetailActions("paused") enthält ebenfalls "Bearbeiten"', () => {
	test('Eintrag {id:"edit", label:"Bearbeiten"} ist enthalten', () => {
		const actions = compareDetailActions('paused');
		const edit = actions.find((a: { id: string }) => a.id === 'edit');
		assert.ok(edit, 'kein "edit"-Eintrag in compareDetailActions("paused") gefunden');
		assert.equal(edit?.label, 'Bearbeiten');
	});
});

describe('AC-4: compareDetailActions("draft") enthält KEIN "Bearbeiten" (Draft hat Setup-Pfad)', () => {
	test('kein "edit"-Eintrag für Draft', () => {
		const actions = compareDetailActions('draft');
		const edit = actions.find((a: { id: string }) => a.id === 'edit');
		assert.equal(edit, undefined, 'Draft darf keinen "edit"-Eintrag bekommen — Setup-Pfad deckt das ab');
	});
});

describe('Regression (#1256 Scheibe 8 AC-23): compareLifecycleActions("active") bleibt ohne "edit"', () => {
	test('Mobile-Sheet-Aktionsliste enthält weiterhin keinen "edit"-Eintrag', () => {
		const actions = compareLifecycleActions('active');
		const edit = actions.find((a: { id: string }) => a.id === 'edit');
		assert.equal(
			edit,
			undefined,
			'compareLifecycleActions() darf durch #1261 NICHT um "edit" erweitert werden — das würde ' +
				'das Mobile-Bottom-Sheet regressieren (MCompareActionSheet.svelte nutzt dieselbe Funktion)'
		);
	});
});
