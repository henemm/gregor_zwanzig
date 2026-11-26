// Issue #2654 (i18n F5) — feste Literal-Anker fuer JEDEN Katalogwert des Pakets
// (wertebereiche.*): Schluessel -> de | en, Platzhalter als <name> eingesetzt.
// Die deutschen Literale sind gegen den Wortlaut in origin/main (Quelltexte VOR der
// Umstellung, Commit a0effc47e) abgeglichen: WeatherMetricsTab.svelte,
// weather-metrics-tab/{SavePresetDialog,WeatherV2Grundauswahl,
// WeatherV2PresetBar,WeatherV2Reihenfolge}.svelte, trip-detail/metricsEditor.ts
// (CATEGORY_LABELS), wetter-tab/compareMetricCatalogLoader.ts (Gewitter-Stufen
// aus `ordinalLabels`, grossgeschrieben) und dem Register (Auswertungen
// Minimum/Maximum/Mittel/Summe, src/app/metric_catalog.py). Saetze mit
// hervorgehobenem Element (<code>, <strong>) stehen mit Platzhalter an dessen Stelle.
// NICHT aus dem Katalog nachziehen: eine Abweichung ist ein Befund.
// Verwendet in wertebereiche_sprache.test.ts (Wertvergleich + statischer Gegencheck).
// #3383 S1: die Schluessel der geloeschten Waisen (wertebereiche.preset.*, .grundauswahl.*,
// .reihenfolge.aus, .schwelle.stufe.*, .symbolzeile.*; 22) sind mit ihnen aus dem Katalog entfallen.

export const F5_ANKER: [schluessel: string, de: string, en: string][] = [
	// Reiter: Laden, Fehler, Speichern-Leiste (WeatherMetricsTab)
	['wertebereiche.tab.laedt', 'Lade Metriken…', 'Loading metrics…'],
	['wertebereiche.tab.speichert', 'Speichern…', 'Saving…'],
	// Preset speichern (SavePresetDialog): seit #2794 S3a Teil-PR 3 (AC-42) ueber den Katalog
	// `wetter.dialog.*` (Anker dort: s3a2794_teil3_wetter_katalog); die Schluessel
	// `wertebereiche.preset_dialog.*` sind mit Zeithorizonten und Zusammenfassung entfallen.
	// Kategorien (CATEGORY_LABELS)
	['wertebereiche.kategorie.temperature', 'Temperatur', 'Temperature'],
	['wertebereiche.kategorie.wind', 'Wind', 'Wind'],
	['wertebereiche.kategorie.precipitation', 'Niederschlag', 'Precipitation'],
	['wertebereiche.kategorie.atmosphere', 'Atmosphäre', 'Atmosphere'],
	['wertebereiche.kategorie.winter', 'Winter / Schnee', 'Winter / snow'],
	// Reihenfolge (WeatherV2Reihenfolge, LayoutTab-Zaehlwort)
	['wertebereiche.reihenfolge.roh', 'Roh', 'Raw'],
	['wertebereiche.reihenfolge.einfach', 'Einfach', 'Simple'],
	// Gewitter-Stufen (ordinalLabels aus /api/compare/metrics, Stufe als Kennung)
	['wertebereiche.gewitter_stufe.kein', 'Kein', 'None'],
	['wertebereiche.gewitter_stufe.leicht', 'Leicht', 'Light'],
	['wertebereiche.gewitter_stufe.mittel', 'Mittel', 'Moderate'],
	['wertebereiche.gewitter_stufe.hoch', 'Hoch', 'High'],
	// Auswertungen (Kennung aggregation, Annahme A1)
	['wertebereiche.auswertung.min', 'Minimum', 'Minimum'],
	['wertebereiche.auswertung.max', 'Maximum', 'Maximum'],
	['wertebereiche.auswertung.avg', 'Mittel', 'Average'],
	['wertebereiche.auswertung.sum', 'Summe', 'Total']
];
