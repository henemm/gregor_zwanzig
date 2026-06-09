// Compare-Editor — reine Progressive-Lock-Engine (Issue #678, Epic #677).
// Spec: docs/specs/modules/issue_678_compare_editor_shell.md
//
// DOM-frei und unit-testbar. Identische Logik wie CE_unlocked/CE_doneSet aus
// claude-code-handoff/current/jsx/screen-compare-editor.jsx, hier als reine
// Funktionen extrahiert (keine Mocks, keine Browser-APIs).

export const TAB_ORDER = ['vergleich', 'orte', 'idealwerte', 'layout', 'versand'] as const;

export type CompareTabId = (typeof TAB_ORDER)[number];

export interface CompareEditorProgress {
	name: string;
	pickedCount: number;
	idealsVisited: boolean;
	layoutVisited: boolean;
	versandVisited?: boolean;
}

/** Welche Tabs sind im Create-Modus anklickbar (sequenzielle Freischaltung)? */
export function unlockedTabs(p: CompareEditorProgress): Set<CompareTabId> {
	const s = new Set<CompareTabId>(['vergleich']);
	if (p.name.trim()) s.add('orte');
	if (p.pickedCount >= 2) s.add('idealwerte');
	if (p.idealsVisited) s.add('layout');
	if (p.layoutVisited) s.add('versand');
	return s;
}

/** Welche Tabs gelten als erledigt (✓-Kennzeichen + Fortschrittszähler)? */
export function doneTabs(p: CompareEditorProgress): Set<CompareTabId> {
	const s = new Set<CompareTabId>();
	if (p.name.trim()) s.add('vergleich');
	if (p.pickedCount >= 2) s.add('orte');
	if (p.idealsVisited) s.add('idealwerte');
	if (p.layoutVisited) s.add('layout');
	if (p.versandVisited) s.add('versand');
	return s;
}
