// Issue #2657 (i18n F8) — feste Literal-Anker fuer JEDEN Katalogwert des Pakets
// (layout.*): Schluessel -> de | en, Platzhalter als <name> eingesetzt. Die
// deutschen Literale sind gegen den Wortlaut in origin/main (Quelltexte VOR der
// Umstellung, Commit a0effc47e) abgeglichen: LayoutTab/LTCutLine.svelte,
// ltChannels.ts, CorridorEditor/CorridorEditorMobile.svelte, corridorEditorState.ts,
// OutputLayoutEditor/OutlookLayoutControls/MailInhaltCard.svelte,
// mailInhaltKonstanten.ts, routes/gpx-upload/+page.svelte. Satzteile, die im
// Bestand um ein Element herum standen (Hervorhebung, Pfeil, Doppelpunkt),
// stehen ohne dieses Element. Plural: `.one`/`.other` je mit <count>.
// NICHT aus dem Katalog nachziehen: eine Abweichung ist ein Befund.
// Verwendet in layout_korridor_sprache.test.ts (Wertvergleich + statischer Gegencheck).

export const F8_ANKER: [schluessel: string, de: string, en: string][] = [
	// Layout-Reiter (LayoutTab, LTCutLine)
	['layout.tab.eyebrow', 'Kanal · Auswahl & Kappung', 'Channel · selection & cutoff'],
	['layout.kappung.schnittlinie', '✂ ab hier <kanal>-Limit (max <max>)', '✂ <kanal> limit from here (max <max>)'],
	// Kappungs-Hinweis (ltChannels.ts::ltCapNoteText) und Abwahl-Hinweis
	['layout.kappung.zeigt_alles', '<kanal> zeigt alles · keine Begrenzung', '<kanal> shows everything · no limit'],
	['layout.kappung.zeichen', '<kanal>: kein Raster, keine Tabelle — Fließtext, <zeichen> Zeichen', '<kanal>: no grid, no table — plain text, <zeichen> characters'],
	['layout.kappung.anzahl_passt', '<kanal>: <anzahl> <subjekt> · passt (max <max>)', '<kanal>: <anzahl> <subjekt> · fits (max <max>)'],
	['layout.kappung.anzahl_zu_breit', '<kanal>: <anzahl> <subjekt> · zu breit — max <max>, weiter vorne = sicherer', '<kanal>: <anzahl> <subjekt> · too wide — max <max>, further forward = safer'],
	['layout.kappung.spalten_passt.one', '<kanal>: <count> Spalten (Label + <subjekt>) · passt (max <max>)', '<kanal>: <count> column (label + <subjekt>) · fits (max <max>)'],
	['layout.kappung.spalten_passt.other', '<kanal>: <count> Spalten (Label + <subjekt>) · passt (max <max>)', '<kanal>: <count> columns (label + <subjekt>) · fits (max <max>)'],
	['layout.kappung.spalten_zu_breit.one', '<kanal>: <count> Spalten (Label + <subjekt>) · zu breit — max <max>, weiter vorne = sicherer', '<kanal>: <count> column (label + <subjekt>) · too wide — max <max>, further forward = safer'],
	['layout.kappung.spalten_zu_breit.other', '<kanal>: <count> Spalten (Label + <subjekt>) · zu breit — max <max>, weiter vorne = sicherer', '<kanal>: <count> columns (label + <subjekt>) · too wide — max <max>, further forward = safer'],
	[
		'layout.hinweis.kanal_abwahl',
		'Ein Kanal zeigt höchstens, was in der Grundauswahl gewählt ist. Was dort fehlt, erscheint in keinem Kanal.',
		'A channel shows at most what is selected in the base selection. Anything missing there appears in no channel.'
	],
	// Korridor-Editor (Desktop und mobil teilen die Schluessel)
	['layout.korridor.eyebrow', 'Wertebereiche', 'Target ranges'],
	['layout.korridor.eyebrow_idealbereiche', 'Wertebereiche · Idealbereiche', 'Target ranges · ideal ranges'],
	['layout.korridor.wiederholen', 'Wiederholen', 'Retry'],
	['layout.korridor.lade', 'Lade Metriken…', 'Loading metrics…'],
	['layout.korridor.fehler_laden', 'Fehler beim Laden der Metriken', 'Failed to load metrics'],
	['layout.korridor.titel_route', 'Sag mir, welche Werte für dich passen', 'Tell me which values suit you'],
	['layout.korridor.titel_vergleich', 'Sag mir, welche Werte dir ideal sind', 'Tell me which values are ideal for you'],
	[
		'layout.korridor.einleitung_route',
		'Ein Wertebereich je Metrik legt fest, welche Werte du auf der Trip noch akzeptierst. Werte im Bereich werden im Briefing hervorgehoben. Warnungen zwischen den Briefings stellst du im Reiter Alarme ein.',
		'One target range per metric sets which values you still accept on the trip. Values within the range are highlighted in the briefing. You set warnings between briefings in the Alerts tab.'
	],
	[
		'layout.korridor.einleitung_vergleich',
		'Ein Wertebereich je Metrik legt deinen Idealbereich fest. Werte im Bereich werden im Briefing pro Ort grün markiert — kein Score, kein Ranking, nur eine Lese-Hilfe.',
		'One target range per metric sets your ideal range. Values within the range are marked green per location in the briefing — no score, no ranking, just a reading aid.'
	],
	[
		'layout.korridor.zusatz_fehlt',
		'Zusätzliche Metriken konnten nicht geladen werden — es stehen nur die Standard-Metriken zur Auswahl.',
		'Additional metrics could not be loaded — the standard metrics are available to choose from.'
	],
	['layout.korridor.legende_titel', 'So liest sich ein Wertebereich', 'How to read a target range'],
	['layout.korridor.legende_im_bereich', 'im Bereich =', 'within range ='],
	['layout.korridor.legende_markiert', 'markiert', 'marked'],
	['layout.korridor.pflicht', 'Mindestens eine Grenze (Von oder Bis) ist Pflicht: <metriken>', 'At least one limit (From or To) is required: <metriken>'],
	['layout.korridor.offen', 'offen', 'open'],
	['layout.korridor.von', 'Von', 'From'],
	['layout.korridor.bis', 'Bis', 'To'],
	['layout.korridor.grenze_setzen', 'offen · + Grenze', 'open · + limit'],
	['layout.korridor.grenze_oeffnen', 'Grenze öffnen', 'Open limit'],
	['layout.korridor.markieren', 'Markieren', 'Mark'],
	['layout.korridor.entfernen', 'entfernen', 'remove'],
	['layout.korridor.metrik_hinzufuegen', 'Metrik hinzufügen', 'Add metric'],
	['layout.korridor.neutral', 'kein Score · kein Rang · Wertebereiche markieren nur, sie sortieren nicht', 'no score · no rank · target ranges only mark, they do not sort'],
	['layout.korridor.weitere_erhalten.one', '<count> weiterer Eintrag bleibt erhalten', '<count> more entry is kept'],
	['layout.korridor.weitere_erhalten.other', '<count> weitere Einträge bleiben erhalten', '<count> more entries are kept'],
	// Zeilen des Trip-Korridors (corridorEditorState.ts::ROUTE_METRIC_DEFS)
	['layout.korridor_zeile.wind_gust', 'Böen', 'Wind gusts'],
	['layout.korridor_zeile.precipitation_sum', 'Niederschlag', 'Precipitation'],
	['layout.korridor_zeile.temperature_min', 'Temperatur Min', 'Temperature min'],
	['layout.korridor_zeile.temperature_max', 'Temperatur Max', 'Temperature max'],
	['layout.korridor_zeile.snow_line', 'Schneefallgrenze', 'Snow line'],
	['layout.korridor_hinweis.wind_gust', 'Grat-kritisch', 'Critical on ridges'],
	['layout.korridor_hinweis.precipitation_sum', 'Nässe / Rutschgefahr', 'Wet / slip risk'],
	['layout.korridor_hinweis.temperature_min', 'Frost-Grenze', 'Frost limit'],
	['layout.korridor_hinweis.temperature_max', 'Hitze-Grenze', 'Heat limit'],
	['layout.korridor_hinweis.snow_line', 'Schnee statt Regen', 'Snow instead of rain'],
	// Profil-Metriken (corridorEditorState.ts::PROFILE_METRICS_WITH_SCALES)
	['layout.profil_metrik.snow_depth_cm', 'Schneehöhe', 'Snow depth'],
	['layout.profil_metrik.snow_new_sum_cm', 'Neuschnee', 'Fresh snow'],
	['layout.profil_metrik.sunny_hours_h', 'Sonnenstunden', 'Sunshine hours'],
	['layout.profil_metrik.wind_max_kmh', 'Windspitzen', 'Peak wind'],
	['layout.profil_metrik.cloud_avg_pct', 'Bewölkung Ø', 'Cloud cover Ø'],
	['layout.profil_metrik.visibility_min_m', 'Sichtweite min', 'Visibility min'],
	['layout.profil_metrik.precip_sum_mm', 'Niederschlag', 'Precipitation'],
	['layout.profil_metrik.thunder_level_max', 'Gewitter', 'Thunderstorm'],
	['layout.profil_metrik.uv_index_max', 'UV-Index max', 'UV index max'],
	['layout.profil_metrik.temp_max_c', 'Temperatur max', 'Temperature max'],
	// Ausgabe-Layout (OutputLayoutEditor)
	['layout.ausgabe.sms_eyebrow', 'SMS · Priorisierte Liste', 'SMS · priority list'],
	['layout.ausgabe.reihenfolge', 'Reihenfolge', 'Order'],
	[
		'layout.ausgabe.sms_hinweis',
		'SMS hat maximal 140 Zeichen. Reihenfolge: oben = wichtiger. Was nicht mehr in das Budget passt, wird automatisch weggelassen.',
		'SMS has at most 140 characters. Order: top = more important. Anything that no longer fits the budget is left out automatically.'
	],
	['layout.ausgabe.zeichen', 'Zeichen', 'Characters'],
	['layout.ausgabe.leer', 'Keine Metriken — aus „Nicht im Briefing" hinzufügen.', 'No metrics — add some from “Not in the briefing”.'],
	['layout.ausgabe.sms_liste', 'SMS-Metriken, Reihenfolge', 'SMS metrics, order'],
	['layout.ausgabe.entfernen', 'Entfernen', 'Remove'],
	['layout.ausgabe.preset_auswahl', 'Preset-Auswahl', 'Preset selection'],
	['layout.ausgabe.spalten_eyebrow', 'Im Briefing als Spalte', 'In the briefing as a column'],
	['layout.ausgabe.spalten', 'Spalten', 'Columns'],
	['layout.ausgabe.spalten_hinweis', 'Eine eigene Tabellen-Spalte je Metrik. Reihenfolge = von links nach rechts.', 'One table column per metric. Order = left to right.'],
	['layout.ausgabe.detail_eyebrow', 'Im Briefing als Detail', 'In the briefing as a detail'],
	['layout.ausgabe.detail_werte', 'Detail-Werte', 'Detail values'],
	['layout.ausgabe.detail_hinweis', 'Erscheinen als kompakte Zeile direkt unter der Tabelle.', 'Shown as a compact line directly below the table.'],
	// Ausblick-Steuerung (OutlookLayoutControls)
	['layout.ausblick.titel', '3-Tages-Ausblick', '3-day outlook'],
	['layout.ausblick.nur_email', 'Erscheint nur in der E-Mail.', 'Appears only in the email.'],
	// Mail-Inhalt (MailInhaltCard, mailInhaltKonstanten.ts)
	['layout.mail_inhalt.titel', 'E-Mail-Inhalt', 'Email content'],
	['layout.mail_inhalt.format', 'Format', 'Format'],
	['layout.mail_inhalt.ausfuehrlich', 'Ausführlich (HTML)', 'Detailed (HTML)'],
	['layout.mail_inhalt.kompakt', 'Kompakt (Nur-Text)', 'Compact (plain text)'],
	[
		'layout.mail_inhalt.kompakt_hinweis',
		'Im Kompakt-Modus werden fix Metriken-Überblick + Ausblick gezeigt. Die Inhalts-Bausteine unten sind deaktiviert.',
		'In compact mode, the metrics overview + outlook are always shown. The content blocks below are disabled.'
	],
	['layout.mail_inhalt.etappen_kennzahlen', 'Etappen-Kennzahlen', 'Stage figures'],
	['layout.mail_inhalt.etappen_kennzahlen_text', 'Distanz, Auf-/Abstieg und maximale Höhe der Etappe als Zahlenraster.', 'Distance, ascent/descent and maximum altitude of the stage as a number grid.'],
	['layout.mail_inhalt.quick_take', 'Quick-Take-Chips', 'Quick-take chips'],
	['layout.mail_inhalt.quick_take_text', 'Farbige Schlagwort-Pillen oben, z. B. „Trocken", „Windig".', 'Coloured keyword pills at the top, e.g. “Dry”, “Windy”.'],
	['layout.mail_inhalt.metriken_ueberblick', 'Metriken-Überblick', 'Metrics overview'],
	['layout.mail_inhalt.metriken_ueberblick_text', 'Ersetzt Quick-Take-Chips und Tages-Summe durch eine farbige Pille je aktiver Metrik.', 'Replaces quick-take chips and the daily summary with one coloured pill per active metric.'],
	['layout.mail_inhalt.ausblick', 'Ausblick', 'Outlook'],
	['layout.mail_inhalt.ausblick_text', 'Großwetterlage-Kopf, nächste Etappen und Vorhersage-Sicherheit am Mail-Ende.', 'Weather pattern header, next stages and forecast confidence at the end of the email.'],
	['layout.mail_inhalt.grosswetterlage', 'Großwetterlage', 'Weather pattern'],
	['layout.mail_inhalt.grosswetterlage_text', 'Einordnung der Wetterstabilität, z. B. „stabile Hochdrucklage".', 'Assessment of weather stability, e.g. “stable high pressure”.'],
	['layout.mail_inhalt.zusammenfassung', 'Zusammenfassung', 'Summary'],
	['layout.mail_inhalt.zusammenfassung_text', 'Kurzer Fließtext mit den wichtigsten Wetter-Highlights des Tages.', "Short text with the day's main weather highlights."],
	['layout.mail_inhalt.vortag_vergleich', 'Vortag-Vergleich', 'Comparison with yesterday'],
	['layout.mail_inhalt.vortag_vergleich_text', 'Vergleich des heutigen Wetters mit dem Vortag als Kurzzeile im Briefing.', "Today's weather compared with yesterday as a short line in the briefing."],
	// GPX-Upload (routes/gpx-upload/+page.svelte)
	['layout.gpx.titel', 'GPX hochladen', 'Upload GPX'],
	['layout.gpx.import_titel', 'GPX-Datei importieren', 'Import GPX file'],
	['layout.gpx.import_text', 'Lade eine GPX-Datei hoch, um daraus eine Etappe und einen Trip zu erstellen.', 'Upload a GPX file to create a stage and a trip from it.'],
	['layout.gpx.datei', 'GPX-Datei', 'GPX file'],
	['layout.gpx.datum', 'Datum (optional)', 'Date (optional)'],
	['layout.gpx.startzeit', 'Startzeit (Stunde)', 'Start time (hour)'],
	['layout.gpx.hochladen', 'Hochladen', 'Upload'],
	['layout.gpx.wird_hochgeladen', 'Wird hochgeladen...', 'Uploading...'],
	['layout.gpx.vorschau', 'Etappen-Vorschau', 'Stage preview'],
	['layout.gpx.spalte_name', 'Name', 'Name'],
	['layout.gpx.spalte_lat', 'Lat', 'Lat'],
	['layout.gpx.spalte_lon', 'Lon', 'Lon'],
	['layout.gpx.spalte_hoehe', 'Höhe', 'Elevation'],
	['layout.gpx.spalte_zeitfenster', 'Zeitfenster', 'Time window'],
	['layout.gpx.als_trip_speichern', 'Als Trip speichern', 'Save as trip'],
	['layout.gpx.wird_gespeichert', 'Wird gespeichert...', 'Saving...'],
	['layout.gpx.trip_name', 'Trip-Name', 'Trip name'],
	['layout.gpx.trip_name_eingeben', 'Trip-Name eingeben', 'Enter trip name'],
	['layout.gpx.gespeichert', 'Trip wurde erfolgreich gespeichert.', 'Trip saved successfully.'],
	['layout.gpx.zu_den_trips', 'Zu den Trips', 'Go to trips'],
	['layout.gpx.fehler_keine_datei', 'Bitte eine GPX-Datei auswählen.', 'Please select a GPX file.'],
	['layout.gpx.fehler_zu_gross', 'Datei zu groß (max. 10 MB).', 'File too large (max. 10 MB).'],
	['layout.gpx.fehler_nur_gpx', 'Nur .gpx Dateien erlaubt.', 'Only .gpx files are allowed.'],
	['layout.gpx.fehler_hochladen', 'Fehler beim Hochladen der GPX-Datei.', 'Failed to upload the GPX file.'],
	['layout.gpx.fehler_name', 'Trip-Name muss mindestens einen Buchstaben oder eine Zahl enthalten.', 'Trip name must contain at least one letter or number.'],
	['layout.gpx.fehler_speichern', 'Fehler beim Speichern des Trips.', 'Failed to save the trip.']
];
