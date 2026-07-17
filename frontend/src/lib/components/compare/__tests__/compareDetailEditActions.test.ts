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

// UMKEHRUNG des #1261-AC-2-Verhaltens durch Epic #1273 Slice S3 (Spec AC-5):
// Der separate "Bearbeiten"-Einstieg im Desktop-Detail-Kebab ist überflüssig
// geworden, seit S2 Name/Region/Aktivitätsprofil INLINE auf dem Hub selbst
// editierbar macht — der Hub *ist* jetzt die Bearbeiten-Fläche, ein
// "Bearbeiten"-Eintrag im eigenen Kebab wäre zirkulär. compareDetailActions()
// wird daher zum reinen Alias auf compareLifecycleActions() (ohne edit).
describe('AC-5 (S3): compareDetailActions("active") enthält KEIN "Bearbeiten" mehr', () => {
	test('kein "edit"-Eintrag (Umkehrung #1261-AC-2)', () => {
		const actions = compareDetailActions('active');
		const edit = actions.find((a: { id: string }) => a.id === 'edit');
		assert.equal(
			edit,
			undefined,
			'compareDetailActions("active") darf keinen "edit"-Eintrag mehr liefern — der Hub ist die Bearbeiten-Fläche'
		);
	});
});

describe('AC-5 (S3): compareDetailActions("paused") enthält ebenfalls KEIN "Bearbeiten" mehr', () => {
	test('kein "edit"-Eintrag (Umkehrung #1261-AC-2)', () => {
		const actions = compareDetailActions('paused');
		const edit = actions.find((a: { id: string }) => a.id === 'edit');
		assert.equal(
			edit,
			undefined,
			'compareDetailActions("paused") darf keinen "edit"-Eintrag mehr liefern — der Hub ist die Bearbeiten-Fläche'
		);
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
