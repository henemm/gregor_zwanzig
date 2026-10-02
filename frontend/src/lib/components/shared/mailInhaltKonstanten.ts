// Issue #2277 S5 — Konstanten der Karte "E-Mail-Inhalt" (MailInhaltCard.svelte).
// Ehemals in edit/reportConfigWrite.ts (Issue #619/#693/#723), dort entfernt.

/** Default-Auswahl der Tages-Summe-Kennzahlen: Regen/Wind/Sicht/Gewitter aktiv, Temperatur aus. */
export const DEFAULT_DAILY_SUMMARY_METRICS: readonly string[] = [
	'precipitation',
	'wind',
	'visibility',
	'thunder',
] as const;

/** Beschreibungen für Inhalts-Bausteine (Issue #693 + #723). Rückwärtskompatibel — entfernte Einträge bleiben. */
export const CONTENT_MODULE_DESCRIPTIONS: Record<string, { label: string; description: string }> = {
	show_stage_stats: {
		label: 'Etappen-Kennzahlen',
		description: 'Distanz, Auf-/Abstieg und maximale Höhe der Etappe als Zahlenraster.',
	},
	show_quick_take_tags: {
		label: 'Quick-Take-Chips',
		description: 'Farbige Schlagwort-Pillen oben, z. B. „Trocken", „Windig".',
	},
	show_metrics_summary: {
		label: 'Metriken-Überblick',
		description: 'Ersetzt Quick-Take-Chips und Tages-Summe durch eine farbige Pille je aktiver Metrik.',
	},
	show_outlook: {
		label: 'Ausblick',
		description: 'Großwetterlage-Kopf, nächste Etappen und Vorhersage-Sicherheit am Mail-Ende.',
	},
	show_stability: {
		label: 'Großwetterlage',
		description: 'Einordnung der Wetterstabilität, z. B. „stabile Hochdrucklage".',
	},
	show_highlights: {
		label: 'Zusammenfassung',
		description: 'Kurzer Fließtext mit den wichtigsten Wetter-Highlights des Tages.',
	},
	show_yesterday_comparison: {
		label: 'Vortag-Vergleich',
		description: 'Vergleich des heutigen Wetters mit dem Vortag als Kurzzeile im Briefing.',
	},
};
