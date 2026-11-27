// Issue #1258 Scheibe S2 — geteilter Alarme-Organism (ungewired).
// Pure-Function-Kern fuer AlarmeTab.svelte: feste Abschnittsreihenfolge
// (AC-9), Korridor-Zusammenfassungs-Label (AC-10) und Sprung-Link-Ziel je Kontext.
// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md
//   (AC-9, AC-10, Abschnitt 4 a-h)

import { tr } from '../../../i18n/index.ts';

export type AlarmeContext = 'route' | 'vergleich';

// Abschnitte b-f + h. 'radar' (g) kommt nur bei vergleich dazu, direkt
// hinter 'official-warnings' (Epic #1301 D3). Issue #1371: Abschnitt (a)
// 'korridor-summary' ("Korridor-Auslöser") entfaellt ersatzlos — der Reiter
// Wertebereiche setzt keine Warn-Schwellen mehr, die Aussage waere sachlich
// falsch. Die metric-levels-Sektion zeigt die tatsaechliche Alarm-Konfiguration
// bereits vollstaendig.
const BASE_SECTIONS = [
	'official-warnings',
	'metric-levels',
	'channels',
	'cooldown',
	'quiet-hours'
] as const;

export function alarmeTabSections(context: AlarmeContext, ohneZustellung = false): string[] {
	const sections: string[] = BASE_SECTIONS.filter((s) => !ohneZustellung || !ZUSTELLUNGS_ABSCHNITTE.includes(s));
	if (context === 'vergleich') {
		const officialIdx = sections.indexOf('official-warnings');
		sections.splice(officialIdx + 1, 0, 'radar');
	}
	// Issue #3458: Abschnitt 'sample' (Beispiel-Warnung) entfaellt — ersetzt durch den Test-Alarm (#3441).
	return sections;
}

// Epic #1301 D3 AC-2: Ueberschrift ueber der Ausloeser-Gruppe
// (official-warnings + radar), kontextabhaengig. Issue #2656: aktuelle Sprache (tr).
export function triggerGroupHeading(context: AlarmeContext): string {
	return context === 'vergleich' ? tr('alarme.gruppe.amtlich_radar') : tr('alarme.gruppe.amtlich');
}

// Issue #3332 (D1 von #3307, AC-9): im Trip-Anlegen besitzt der Reiter Zustellung Alarm-Kanaele
// (mit Dringlichkeit), Cooldown und Stille Stunden — der Reiter Alarme blendet sie dort aus, damit
// jedes Feld genau eine Bedienstelle hat. Kontext-Unterschied als Daten (Ratsche
// context_herkunft_zweige_eingefroren). #3333 (D2, AC-10): ebenso im Ortsvergleich-Anlegen.
const ZUSTELLUNGS_ABSCHNITTE: readonly string[] = ['channels', 'cooldown', 'quiet-hours'];
export const ZUSTELLUNG_IM_ANLEGEN_AUSGELAGERT: Record<AlarmeContext, boolean> = { route: true, vergleich: true };
