// Issue #1311, Scheibe C1 von Epic #1301 — geteilter Wetter-Metriken-Tab
// (Trip UND Ortsvergleich). Pure-Function-Kern fuer WeatherMetricsTab.svelte:
// welche Abschnitte je Kontext sichtbar sind (Vorbild: alarme-tab/alarmeTabSections.ts).
//
// Spec: docs/specs/modules/compare_weather_metrics_tab.md
//   (Implementation Details Abschnitt 1, AC-1, AC-6, AC-8)

export type WeatherMetricsContext = 'route' | 'vergleich';

const ROUTE_ONLY_SECTIONS = ['reihenfolge', 'sms_schwellen', 'report_config'] as const;

export function weatherMetricsTabSections(context: WeatherMetricsContext): string[] {
	const sections: string[] = ['grundauswahl'];
	if (context === 'route') sections.push(...ROUTE_ONLY_SECTIONS);
	return sections;
}
