// Issue #2654 (i18n F5) — feste Literal-Anker fuer JEDEN Katalogwert des Pakets
// (wertebereiche.*): Schluessel -> de | en, Platzhalter als <name> eingesetzt.
// Die deutschen Literale sind gegen den Wortlaut in origin/main (Quelltexte VOR der
// Umstellung, Commit a0effc47e) abgeglichen: WeatherMetricsTab.svelte,
// weather-metrics-tab/{DayWindowCard,SavePresetDialog,WeatherV2Grundauswahl,
// WeatherV2PresetBar,WeatherV2Reihenfolge}.svelte, trip-detail/metricsEditor.ts
// (CATEGORY_LABELS), corridor-editor/compareMetricCatalogLoader.ts (Gewitter-Stufen
// aus `ordinalLabels`, grossgeschrieben) und dem Register (Auswertungen
// Minimum/Maximum/Mittel/Summe, src/app/metric_catalog.py). Saetze mit
// hervorgehobenem Element (<code>, <strong>) stehen mit Platzhalter an dessen Stelle.
// NICHT aus dem Katalog nachziehen: eine Abweichung ist ein Befund.
// Verwendet in wertebereiche_sprache.test.ts (Wertvergleich + statischer Gegencheck).

export const F5_ANKER: [schluessel: string, de: string, en: string][] = [
	// Reiter: Laden, Fehler, Speichern-Leiste (WeatherMetricsTab)
	['wertebereiche.tab.laedt', 'Lade Metriken…', 'Loading metrics…'],
	['wertebereiche.tab.wiederholen', 'Wiederholen', 'Retry'],
	['wertebereiche.tab.ladefehler', 'Fehler beim Laden der Metriken', 'Could not load metrics'],
	['wertebereiche.tab.ungespeichert', 'Ungespeicherte Änderungen', 'Unsaved changes'],
	['wertebereiche.tab.verwerfen', 'Verwerfen', 'Discard'],
	['wertebereiche.tab.gespeichert', 'Gespeichert', 'Saved'],
	['wertebereiche.tab.speichern', 'Speichern', 'Save'],
	['wertebereiche.tab.speichert', 'Speichern…', 'Saving…'],
	['wertebereiche.tab.speichern_fehlgeschlagen', 'Speichern fehlgeschlagen', 'Saving failed'],
	// 01 Profil / Presets (WeatherMetricsTab, WeatherV2PresetBar)
	['wertebereiche.profil.titel', '01 — Profil', '01 — Profile'],
	['wertebereiche.preset.eigene', 'Eigene', 'Custom'],
	['wertebereiche.preset.geaendert', 'Geändert —', 'Changed —'],
	['wertebereiche.preset.als_profil_speichern', 'als eigenes Profil speichern', 'save as custom profile'],
	['wertebereiche.preset.anwenden', 'Preset anwenden', 'Apply preset'],
	['wertebereiche.preset.ueberschreiben_hinweis', 'Du hast ungespeicherte Änderungen. Das Preset überschreibt die aktuelle Auswahl.', 'You have unsaved changes. The preset overwrites the current selection.'],
	['wertebereiche.preset.abbrechen', 'Abbrechen', 'Cancel'],
	['wertebereiche.preset.ueberschreiben', 'Überschreiben', 'Overwrite'],
	// Preset speichern (SavePresetDialog)
	['wertebereiche.preset_dialog.eyebrow', 'EIGENES PRESET', 'CUSTOM PRESET'],
	['wertebereiche.preset_dialog.titel', 'Auswahl als Preset speichern', 'Save selection as preset'],
	['wertebereiche.preset_dialog.schliessen', 'Schließen', 'Close'],
	['wertebereiche.preset_dialog.name', 'NAME', 'NAME'],
	['wertebereiche.preset_dialog.name_platzhalter', 'Mein Wandern-Preset', 'My hiking preset'],
	['wertebereiche.preset_dialog.beschreibung', 'BESCHREIBUNG · OPTIONAL', 'DESCRIPTION · OPTIONAL'],
	['wertebereiche.preset_dialog.beschreibung_platzhalter', 'Optimiert für Tages-Trips', 'Optimised for day trips'],
	['wertebereiche.preset_dialog.wird_gespeichert', 'WIRD GESPEICHERT', 'WILL BE SAVED'],
	['wertebereiche.preset_dialog.zusammenfassung', '<aktiv> Metriken aktiv · <roh> Rohwert · <indikator> Indikator', 'Active metrics: <aktiv> · raw: <roh> · indicator: <indikator>'],
	['wertebereiche.preset_dialog.spalten', '<spalten> Spalten · <detail> Detail · <skala> als Einfach', 'Columns: <spalten> · detail: <detail> · simple: <skala>'],
	['wertebereiche.preset_dialog.zeithorizonte', 'ZEITHORIZONTE', 'TIME HORIZONS'],
	['wertebereiche.preset_dialog.keine_metrik', 'Keine Metrik aktiv', 'No metric active'],
	['wertebereiche.preset_dialog.standard', 'Als Standard für neue Trips', 'Default for new trips'],
	['wertebereiche.preset_dialog.speichern', 'Preset speichern', 'Save preset'],
	['wertebereiche.preset_dialog.name_vergeben', 'Ein Profil mit diesem Namen existiert bereits.', 'A profile with this name already exists.'],
	// 02 Grundauswahl (WeatherMetricsTab, WeatherV2Grundauswahl, CATEGORY_LABELS)
	['wertebereiche.grundauswahl.titel', '02 — Grundauswahl', '02 — Basic selection'],
	['wertebereiche.grundauswahl.frage', 'Welche Metriken ins Briefing?', 'Which metrics go into the briefing?'],
	['wertebereiche.grundauswahl.aktiv', '<anzahl> aktiv', '<anzahl> active'],
	['wertebereiche.grundauswahl.hinweis', 'Aktivierte Metriken erscheinen in Abschnitt 3, wo du Reihenfolge und Darstellung festlegst.', 'Activated metrics appear in section 3, where you set their order and display.'],
	['wertebereiche.kategorie.temperature', 'Temperatur', 'Temperature'],
	['wertebereiche.kategorie.wind', 'Wind', 'Wind'],
	['wertebereiche.kategorie.precipitation', 'Niederschlag', 'Precipitation'],
	['wertebereiche.kategorie.atmosphere', 'Atmosphäre', 'Atmosphere'],
	['wertebereiche.kategorie.winter', 'Winter / Schnee', 'Winter / snow'],
	// Reihenfolge (WeatherV2Reihenfolge, LayoutTab-Zaehlwort)
	['wertebereiche.reihenfolge.titel', 'Reihenfolge', 'Order'],
	['wertebereiche.reihenfolge.anzahl.one', '· <count> Metriken', '· <count> metric'],
	['wertebereiche.reihenfolge.anzahl.other', '· <count> Metriken', '· <count> metrics'],
	['wertebereiche.reihenfolge.richtung', 'links → rechts in der Email-Tabelle', 'left → right in the email table'],
	['wertebereiche.reihenfolge.aria', 'Metriken, Reihenfolge', 'Metrics, order'],
	['wertebereiche.reihenfolge.subjekt', 'Metriken', 'metrics'],
	['wertebereiche.reihenfolge.mail_titel', 'Kurzform in der Mail-Stundentabelle', 'Short form in the email hourly table'],
	['wertebereiche.reihenfolge.mail', 'Mail', 'Email'],
	['wertebereiche.reihenfolge.kurzform_titel', 'Kürzel in SMS, Premium-SMS und Telegram', 'Codes in SMS, Premium SMS and Telegram'],
	['wertebereiche.reihenfolge.kurzform', 'Kurzform', 'Compact'],
	['wertebereiche.reihenfolge.roh', 'Roh', 'Raw'],
	['wertebereiche.reihenfolge.einfach', 'Einfach', 'Simple'],
	['wertebereiche.reihenfolge.entfernen_titel', 'Aus Briefing entfernen', 'Remove from briefing'],
	['wertebereiche.reihenfolge.aus', 'Aus', 'Off'],
	['wertebereiche.reihenfolge.aus_im_kanal', 'Aus in diesem Kanal', 'Off in this channel'],
	['wertebereiche.reihenfolge.aufnehmen_titel', 'Wieder ins Briefing aufnehmen', 'Add back to briefing'],
	['wertebereiche.reihenfolge.ein', 'Ein', 'On'],
	['wertebereiche.reihenfolge.legende', 'So heißen diese Größen in SMS und Telegram-Kurzform:', 'These are the codes for these values in SMS and Telegram compact style:'],
	// Tagesfenster (DayWindowCard)
	['wertebereiche.tagesfenster.titel', 'Tagesfenster', 'Day window'],
	['wertebereiche.tagesfenster.untertitel', 'Zeitraum für Stundentabelle, Vergleichswerte, SMS/Kurzzusammenfassung', 'Time range for the hourly table, comparison values and SMS/short summary'],
	['wertebereiche.tagesfenster.von', 'Von', 'From'],
	['wertebereiche.tagesfenster.bis', 'Bis', 'To'],
	['wertebereiche.tagesfenster.ueber_mitternacht', 'Geht über Mitternacht — endet am Folgetag.', 'Crosses midnight — ends the next day.'],
	// 04 Schwellwerte (WeatherMetricsTab)
	['wertebereiche.schwelle.titel', '04 — Schwellwerte', '04 — Thresholds'],
	['wertebereiche.schwelle.hinweis', 'Gelten für SMS-Token, Telegram-Kurzform und den E-Mail-Ausblick/Trend-Block', 'Apply to SMS tokens, Telegram compact style and the email outlook/trend block'],
	['wertebereiche.schwelle.wind', 'Wind (km/h)', 'Wind (km/h)'],
	['wertebereiche.schwelle.boeen', 'Böen (km/h)', 'Gusts (km/h)'],
	['wertebereiche.schwelle.niederschlag', 'Niederschlag (mm)', 'Precipitation (mm)'],
	['wertebereiche.schwelle.regenwahrscheinlichkeit', 'Regenwahrsch. (%)', 'Rain prob. (%)'],
	['wertebereiche.schwelle.gewitter', 'Gewitter', 'Thunderstorm'],
	['wertebereiche.schwelle.schneehoehe', 'Schneehöhe (cm)', 'Snow depth (cm)'],
	['wertebereiche.schwelle.schneefallgrenze', 'Schneefallgrenze (m)', 'Snow line (m)'],
	['wertebereiche.schwelle.stufe.sensibel', 'Sensibel', 'Sensitive'],
	['wertebereiche.schwelle.stufe.standard', 'Standard', 'Standard'],
	['wertebereiche.schwelle.stufe.robust', 'Robust', 'Robust'],
	['wertebereiche.schwelle.nicht_ladbar', 'Schwellen nicht ladbar', 'Thresholds could not be loaded'],
	['wertebereiche.schwelle.laedt', 'Lädt…', 'Loading…'],
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
	['wertebereiche.ausblick.titel', '3-Tages-Vorschau', '3-day preview'],
	// Amtliche Warnungen (Snippet officialAlertsToggle, beide Kontexte)
	['wertebereiche.warnungen.checkbox', 'Amtliche Warnungen im Bericht', 'Official warnings in the report'],
	['wertebereiche.warnungen.text', 'Amtliche Wetterwarnungen (z. B. Unwetterwarnung) im E-Mail-Briefing anzeigen.', 'Show official weather warnings (e.g. severe weather warning) in the email briefing.'],
	['wertebereiche.warnungen.legende_block', 'In SMS und Telegram-Kurzform beginnt der Warn-Block mit <zeichen> — alles dahinter ist eine amtliche Warnung, nicht die eigene Vorhersage.', 'In SMS and Telegram compact style the warning block starts with <zeichen> — everything after it is an official warning, not our own forecast.'],
	['wertebereiche.warnungen.legende_stufe', 'Die Warnstufe steht nach dem Doppelpunkt: <l> = gelb, <m> = orange, <h> = rot (z. B. <beispiel> = rote Gewitterwarnung).', 'The warning level follows the colon: <l> = yellow, <m> = orange, <h> = red (e.g. <beispiel> = red thunderstorm warning).'],
	// Ortsvergleich (WeatherMetricsTab context="vergleich")
	['wertebereiche.vergleich.titel', 'Wetter-Metriken', 'Weather metrics'],
	['wertebereiche.vergleich.hinweis', 'Nur angewählte Metriken erscheinen in der Vergleichs-Mail.', 'Only selected metrics appear in the comparison email.'],
	['wertebereiche.vergleich.warn_hinweis', 'Amtliche Warnungen stehen unabhängig von dieser Reihenfolge immer an erster Stelle und sind deshalb nicht Teil der sortierbaren Liste.', 'Official warnings always come first regardless of this order and are therefore not part of the sortable list.']
];
