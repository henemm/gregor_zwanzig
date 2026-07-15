// Compare-Editor — reine Progressive-Lock-Engine (Issue #678, Epic #677).
// Spec: docs/specs/modules/issue_678_compare_editor_shell.md
//
// DOM-frei und unit-testbar. Identische Logik wie CE_unlocked/CE_doneSet aus
// claude-code-handoff/current/jsx/screen-compare-editor.jsx, hier als reine
// Funktionen extrahiert (keine Mocks, keine Browser-APIs).

// Issue #1258 Scheibe S4 (AC-28, E1/E2): "alarme" wird reguläre Station
// zwischen "layout" und "versand" — der bestehende Layout-Tab bleibt zwischen
// Wertebereiche und Alarme (Programm-Spec Abschnitt 7, Konkretisierung).
export const TAB_ORDER = ['vergleich', 'orte', 'idealwerte', 'layout', 'alarme', 'versand'] as const;

export type CompareTabId = (typeof TAB_ORDER)[number];

export interface CompareEditorProgress {
	name: string;
	pickedCount: number;
	idealsVisited: boolean;
	layoutVisited: boolean;
	// Issue #1258 Scheibe S4 (AC-28): neue Station im Progress-Modell.
	alarmeVisited?: boolean;
	versandVisited?: boolean;
	idealsValid?: boolean; // Issue #718: undefined = rückwärtskompatibel (gilt als valid)
}

/** Welche Tabs sind im Create-Modus anklickbar (sequenzielle Freischaltung)? */
export function unlockedTabs(p: CompareEditorProgress): Set<CompareTabId> {
	const s = new Set<CompareTabId>(['vergleich']);
	if (p.name.trim()) s.add('orte');
	if (p.pickedCount >= 2) s.add('idealwerte');
	if (p.idealsVisited) s.add('layout');
	// Issue #1258 Scheibe S4 (AC-28): letzte Freischalt-Kante ersetzt —
	// layoutVisited schaltet "alarme" frei (statt direkt "versand"),
	// "versand" erst nach alarmeVisited.
	if (p.layoutVisited) s.add('alarme');
	if (p.alarmeVisited) s.add('versand');
	return s;
}

/** Welche Tabs gelten als erledigt (✓-Kennzeichen + Fortschrittszähler)? */
export function doneTabs(p: CompareEditorProgress): Set<CompareTabId> {
	const s = new Set<CompareTabId>();
	if (p.name.trim()) s.add('vergleich');
	if (p.pickedCount >= 2) s.add('orte');
	if (p.idealsVisited && p.idealsValid !== false) s.add('idealwerte');
	if (p.layoutVisited) s.add('layout');
	// Issue #1258 Scheibe S4 (AC-28): sechste Station im Fortschrittszähler.
	if (p.alarmeVisited) s.add('alarme');
	if (p.versandVisited) s.add('versand');
	return s;
}
