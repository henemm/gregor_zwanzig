// Issue #1258 Scheibe S2 — geteilter Alarme-Organism (ungewired).
// Pure-Function-Kern fuer AlarmeTab.svelte: feste Abschnittsreihenfolge
// (AC-9), Korridor-Zusammenfassungs-Label (AC-10) und Sprung-Link-Ziel je
// Kontext.
//
// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md
//   (AC-9, AC-10, Abschnitt 4 a-h)

export type AlarmeContext = 'route' | 'vergleich';

// Abschnitte a-f + h, ohne 'radar' (g) — das kommt nur bei vergleich dazu.
const BASE_SECTIONS = [
	'korridor-summary',
	'official-warnings',
	'metric-levels',
	'channels',
	'cooldown',
	'quiet-hours'
] as const;

export function alarmeTabSections(context: AlarmeContext): string[] {
	const sections: string[] = [...BASE_SECTIONS];
	if (context === 'vergleich') sections.push('radar');
	sections.push('sample');
	return sections;
}

export function notifySummaryLabel(notifyCount: number): string | null {
	if (notifyCount === 0) return null;
	return `${notifyCount} × Warnen aktiv`;
}

export function wertebereicheTabId(context: AlarmeContext): string {
	return context === 'vergleich' ? 'idealwerte' : 'alerts';
}
