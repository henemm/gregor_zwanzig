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

export const F5_ANKER: [schluessel: string, de: string, en: string][] = [
	// Reiter: Laden, Fehler, Speichern-Leiste (WeatherMetricsTab)
	['wertebereiche.tab.laedt', 'Lade Metriken…', 'Loading metrics…'],
	['wertebereiche.tab.speichert', 'Speichern…', 'Saving…'],
	// 01 Profil / Presets (WeatherMetricsTab, WeatherV2PresetBar)
	['wertebereiche.preset.eigene', 'Eigene', 'Custom'],
	['wertebereiche.preset.geaendert', 'Geändert —', 'Changed —'],
	['wertebereiche.preset.als_profil_speichern', 'als eigenes Profil speichern', 'save as custom profile'],
	// Preset speichern (SavePresetDialog): seit #2794 S3a Teil-PR 3 (AC-42) ueber den Katalog
	// `wetter.dialog.*` (Anker dort: s3a2794_teil3_wetter_katalog); die Schluessel
	// `wertebereiche.preset_dialog.*` sind mit Zeithorizonten und Zusammenfassung entfallen.
	// 02 Grundauswahl (WeatherMetricsTab, WeatherV2Grundauswahl, CATEGORY_LABELS)
	['wertebereiche.grundauswahl.frage', 'Welche Metriken ins Briefing?', 'Which metrics go into the briefing?'],
	['wertebereiche.grundauswahl.aktiv', '<anzahl> aktiv', '<anzahl> active'],
	['wertebereiche.grundauswahl.hinweis', 'Aktivierte Metriken erscheinen in Abschnitt 3, wo du Reihenfolge und Darstellung festlegst.', 'Activated metrics appear in section 3, where you set their order and display.'],
	// #3047 N2 (Hinweis bewusst leere Grundauswahl) und N3 (Kennzeichnung nur ein Bericht, bis #3065).
	['wertebereiche.grundauswahl.leer_titel', 'Keine Metrik ausgewählt.', 'No metric selected.'],
	['wertebereiche.grundauswahl.leer_text', 'Die Listen bleiben leer, Stundenverlauf und Ausblick entfallen in der E-Mail.', 'The lists stay empty; the hourly view and the outlook are left out of the email.'],
	['wertebereiche.grundauswahl.nur_morgens', 'nur morgens', 'morning only'],
	['wertebereiche.grundauswahl.nur_abends', 'nur abends', 'evening only'],
	['wertebereiche.kategorie.temperature', 'Temperatur', 'Temperature'],
	['wertebereiche.kategorie.wind', 'Wind', 'Wind'],
	['wertebereiche.kategorie.precipitation', 'Niederschlag', 'Precipitation'],
	['wertebereiche.kategorie.atmosphere', 'Atmosphäre', 'Atmosphere'],
	['wertebereiche.kategorie.winter', 'Winter / Schnee', 'Winter / snow'],
	// Reihenfolge (WeatherV2Reihenfolge, LayoutTab-Zaehlwort)
	['wertebereiche.reihenfolge.roh', 'Roh', 'Raw'],
	['wertebereiche.reihenfolge.einfach', 'Einfach', 'Simple'],
	['wertebereiche.reihenfolge.aus', 'Aus', 'Off'],
	// #2792 S1c-3 (AC-22): Sperr-Hinweis im SMS-Schwellwert-Block (der Hinweis oben im
	// Reiter Wertebereiche entfiel mit dem Korridor-Editor, #2794 Teil-PR 4a)
	// 04 Schwellwerte (WeatherMetricsTab)
	// #3155 (Spec feat_3155 Nr. 7): der Block heisst mit dem einen Namen.
	['wertebereiche.schwelle.stufe.sensibel', 'Sensibel', 'Sensitive'],
	['wertebereiche.schwelle.stufe.standard', 'Standard', 'Standard'],
	['wertebereiche.schwelle.stufe.robust', 'Robust', 'Robust'],
	// Gewitter-Stufen (ordinalLabels aus /api/compare/metrics, Stufe als Kennung)
	['wertebereiche.gewitter_stufe.kein', 'Kein', 'None'],
	['wertebereiche.gewitter_stufe.leicht', 'Leicht', 'Light'],
	['wertebereiche.gewitter_stufe.mittel', 'Mittel', 'Moderate'],
	['wertebereiche.gewitter_stufe.hoch', 'Hoch', 'High'],
	// Auswertungen (Kennung aggregation, Annahme A1)
	['wertebereiche.auswertung.min', 'Minimum', 'Minimum'],
	['wertebereiche.auswertung.max', 'Maximum', 'Maximum'],
	['wertebereiche.auswertung.avg', 'Mittel', 'Average'],
	['wertebereiche.auswertung.sum', 'Summe', 'Total'],
	// 3-Tages-Vorschau (Titel an OutlookLayoutControls)
	// Amtliche Warnungen (Snippet officialAlertsToggle, beide Kontexte)
	// Ortsvergleich (WeatherMetricsTab context="vergleich")
	// Nacht-Stundentabelle (#1721, nur Trip)
	// #2764 (F13): Rueckfall der Mehrfach-Symbol-Zeilen ohne Register-Eintrag; de = Bestand, en = label_en des Registers
	['wertebereiche.symbolzeile.temperature', 'Temperatur', 'Temperature'],
	['wertebereiche.symbolzeile.temperature_night', 'Tiefsttemperatur Nacht', 'Night low'], // #2955: Mockup-Name
	['wertebereiche.symbolzeile.wind_chill', 'Gefühlte Temperatur', 'Feels-like temperature'],
	['wertebereiche.symbolzeile.temperature_day_low', 'Tages-Tiefsttemperatur (Gehzeit)', 'Daytime low (walking hours)'],
	['wertebereiche.symbolzeile.temperature_day_high', 'Tages-Höchsttemperatur (Gehzeit)', 'Daytime high (walking hours)'],
	['wertebereiche.symbolzeile.wind_chill_day_low', 'Gefühlte Tages-Tiefsttemperatur (Gehzeit)', 'Feels-like daytime low (walking hours)'],
	['wertebereiche.symbolzeile.wind_chill_day_high', 'Gefühlte Tages-Höchsttemperatur (Gehzeit)', 'Feels-like daytime high (walking hours)'],
	['wertebereiche.symbolzeile.wind_chill_night', 'Gefühlte Tiefsttemperatur Nacht', 'Feels-like night low'] // #2955: Mockup-Name
];
