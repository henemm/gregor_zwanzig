// compareNewLogic.ts — Reine Progressive-Lock-Engine für den Ortsvergleich-
// Anlege-Flow (/compare/new). Epic #1301 Scheibe F2a.
// Spec: docs/specs/modules/feat_1301_f2a_compare_new_trip_pattern.md
//
// Struktureller Spiegel von `trip-new/tripNewLogic.ts` (#622): DOM-frei, keine
// Svelte-Runes, keine Seiteneffekte — unit-testbar mit node:test.
//
// Freischalt-Kette exakt nach der Tab-Struktur-Tabelle der Spec:
//   Name → Orte≥2 → Wetter-Metriken → Wertebereiche → Layout → Alarme → Versand
// Die *Visited-Flags werden von CompareNewEditor.svelte beim Tab-Wechsel gesetzt
// und NICHT zurückgesetzt (einmal besucht bleibt besucht, wie im Trip-Vorbild).

export type CompareNewTabId =
	'vergleich' | 'orte' | 'metriken' | 'idealwerte' | 'layout' | 'alarme' | 'versand';

export interface CompareNewProgress {
	name: string;
	pickedCount: number;
	metrikenVisited: boolean;
	idealsVisited: boolean;
	layoutVisited: boolean;
	alarmeVisited: boolean;
	versandVisited: boolean;
}

/** Welche Tabs sind anklickbar (sequenzielle Freischaltung, Spec-Tabelle)? */
export function unlockedTabs(p: CompareNewProgress): Set<CompareNewTabId> {
	const s = new Set<CompareNewTabId>(['vergleich']);
	if (p.name.trim()) s.add('orte');
	if (p.name.trim() && p.pickedCount >= 2) s.add('metriken');
	if (p.name.trim() && p.pickedCount >= 2 && p.metrikenVisited) s.add('idealwerte');
	if (p.name.trim() && p.pickedCount >= 2 && p.metrikenVisited && p.idealsVisited) s.add('layout');
	if (p.name.trim() && p.pickedCount >= 2 && p.metrikenVisited && p.idealsVisited && p.layoutVisited)
		s.add('alarme');
	if (
		p.name.trim() &&
		p.pickedCount >= 2 &&
		p.metrikenVisited &&
		p.idealsVisited &&
		p.layoutVisited &&
		p.alarmeVisited
	)
		s.add('versand');
	return s;
}

/** Welche Tabs gelten als erledigt (✓-Kennzeichen + Fortschrittszähler)? */
export function doneTabs(p: CompareNewProgress): Set<CompareNewTabId> {
	const s = new Set<CompareNewTabId>();
	if (p.name.trim()) s.add('vergleich');
	if (p.pickedCount >= 2) s.add('orte');
	if (p.metrikenVisited) s.add('metriken');
	if (p.idealsVisited) s.add('idealwerte');
	if (p.layoutVisited) s.add('layout');
	if (p.alarmeVisited) s.add('alarme');
	if (p.versandVisited) s.add('versand');
	return s;
}

/** Fortschrittszähler = Anzahl erledigter Tabs, gedeckelt bei 7. */
export function progressCount(done: Set<CompareNewTabId>): number {
	return Math.min(done.size, 7);
}

/** „Briefing aktivieren" erst nach Besuch des Versand-Tabs. */
export function canActivate(done: Set<CompareNewTabId>): boolean {
	return done.has('versand');
}
