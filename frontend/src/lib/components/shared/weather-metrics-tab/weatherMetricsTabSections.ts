// Issue #1311, Scheibe C1 von Epic #1301 — geteilter Wetter-Metriken-Tab
// (Trip UND Ortsvergleich). Pure-Function-Kern fuer WeatherMetricsTab.svelte:
// welche Abschnitte je Kontext sichtbar sind (Vorbild: alarme-tab/alarmeTabSections.ts).
//
// Spec: docs/specs/modules/compare_weather_metrics_tab.md
//   (Implementation Details Abschnitt 1, AC-1, AC-6, AC-8)
//
// D2-Fix-Loop 2 (Scheibe D2 von #1301, Staging-Befund BROKEN, AC-6): neuer
// Abschnitt 'official_alerts' — anders als die uebrigen ROUTE_ONLY_SECTIONS
// fuer BEIDE Kontexte sichtbar. Grund: der Amtliche-Warnungen-Toggle im
// geteilten Alarm-Tab entfaellt (D2 Punkt 1-5); fuer bestehende Vergleiche
// (Hub `/compare/{id}/edit` -> 307 auf den Hub, CompareInhaltSection nur im
// Anlege-Wizard erreichbar) ist der Hub-Tab "Wetter-Metriken" die einzige
// erreichbare Inhalt-Heimat fuer `official_alerts_enabled`.
// Spec: docs/specs/modules/d2_1301_official_alerts_single_control.md § Punkt 6, AC-6

export type WeatherMetricsContext = 'route' | 'vergleich';

const ROUTE_ONLY_SECTIONS = ['reihenfolge', 'sms_schwellen', 'report_config'] as const;

export function weatherMetricsTabSections(context: WeatherMetricsContext): string[] {
	const sections: string[] = ['grundauswahl'];
	if (context === 'route') sections.push(...ROUTE_ONLY_SECTIONS);
	sections.push('official_alerts');
	return sections;
}
