// Issue #1261 (b) — Compare-Editor Autospeichern: kombiniert das bestehende
// #1234-Gesten-Gate (weatherSaveGate, context-agnostisch) mit dem
// Dirty-Zustand des Compare-Editors.
// Spec: docs/specs/modules/issue_1261_compare_edit_autosave.md
//   § Implementation Details (b).3, § Acceptance Criteria AC-5/AC-7
//
// Reine Entscheidungsfunktion — kein DOM, kein Svelte-State, unit-testbar
// ohne Mocks (compareAutosaveGate.test.ts). weatherSaveGate() wird
// wiederverwendet statt neu implementiert (keine Compare-eigene Gabelung).

import { weatherSaveGate } from '../trip-detail/weatherSaveGate.ts';

export interface CompareAutoSaveInput {
	/** true wenn sich der Editor-Zustand gegenüber dem Snapshot geändert hat. */
	dirty: boolean;
	/** Ausschließlich aus echten DOM-Ereignissen gesetzt — nie in einem $effect. */
	userTouched: boolean;
	/** Im Compare-Editor faktisch immer true (synchrone SSR-Hydration). */
	catalogLoaded: boolean;
}

export function computeCompareAutoSaveAction(input: CompareAutoSaveInput): 'save' | 'skip' {
	if (!input.dirty) return 'skip';
	return weatherSaveGate({ catalogLoaded: input.catalogLoaded, userTouched: input.userTouched });
}
