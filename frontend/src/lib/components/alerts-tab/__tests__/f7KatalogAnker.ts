// Issue #2656 (i18n F7) — feste Literal-Anker fuer JEDEN Katalogwert des Pakets
// (alarme.*): Schluessel -> de | en, Platzhalter als <name> eingesetzt. Die
// deutschen Literale sind gegen den Wortlaut in origin/main (Quelltexte VOR der
// Umstellung, Commit 849819622) abgeglichen: shared/AlarmeTab.svelte,
// shared/AlertChannelPicker.svelte, shared/alarme-tab/{alarmeTabSections,
// alertChannelState,premiumSmsAlarmGate}.ts, alerts-tab/*.svelte,
// alerts-tab/alertMetricTable.ts, lib/utils/alertMetricLabels.ts. Satzteile, die
// im Bestand um ein Element herum standen (<strong>, Link), stehen als
// Platzhalter. Kein Plural im Paket (keine Zaehlform je Anzahl).
// Metrik-Namen (alarme.metrik.*): de wortgleich zu ALERT_METRIC_LABELS, en laut
// Spec Abschnitt 3. Issue #1895 S4: die Anker der toten Bausteine (AlertsTab,
// AlertCard, AlertMetricTable/-Row, AlertPresetSelector samt Preset-Zeilen)
// sind mit ihren Katalogschluesseln entfallen.
// NICHT aus dem Katalog nachziehen: eine Abweichung ist ein Befund.
// Verwendet in alarme_tab_sprache.test.ts (Wertvergleich + statischer Gegencheck).

export const F7_ANKER: [schluessel: string, de: string, en: string][] = [
	// Alarme-Reiter (AlarmeTab, alarmeTabSections.ts)
	['alarme.gruppe.amtlich', 'Amtliche Warnungen', 'Official warnings'],
	['alarme.gruppe.amtlich_radar', 'Amtliche & Radar-Warnungen', 'Official & radar warnings'],
	['alarme.amtlich.label', 'Amtliche Warnungen lösen Alert aus', 'Official warnings trigger an alert'],
	['alarme.radar.label', 'Radar-Alarm', 'Rain alert (radar)'],
	['alarme.beispiel_warnung', 'Beispiel-Warnung', 'Example warning'],
	['alarme.metriken.keine_gewaehlt', 'Wähle im Reiter Wetter Metriken aus, um Alarm-Schwellen zu konfigurieren.', 'Select metrics in the Weather tab to configure alert thresholds.'], // #2794 S3a 4b (AC-33)
	['alarme.metriken.nur_ohne_alarm', 'Keine der gewählten Größen kann einen Alarm auslösen: <namen>. Sie erscheinen weiterhin im Briefing, lösen aber keine Warnung aus.', 'None of the selected metrics can trigger an alert: <namen>. They still appear in the briefing but do not trigger a warning.'],
	['alarme.metriken.ohne_alarm', 'Für diese Größen gibt es keinen Alarm: <namen>. Sie erscheinen weiterhin im Briefing, lösen aber keine Warnung aus.', 'There is no alert for these metrics: <namen>. They still appear in the briefing but do not trigger a warning.'],
	// Alarm-Kanaele (AlertChannelPicker, alertChannelState.ts, premiumSmsAlarmGate.ts)
	['alarme.kanaele.titel', 'Alert-Kanäle', 'Alert channels'],
	['alarme.kanaele.schwelle', 'Dringlichkeits-Schwelle', 'Urgency threshold'],
	['alarme.kanaele.schwelle_aria', 'Dringlichkeits-Schwelle <kanal>', 'Urgency threshold <kanal>'],
	['alarme.kanaele.aktiv', '<anzahl> aktiv', '<anzahl> active'],
	['alarme.kanaele.kein_kanal', 'kein Kanal — Alerts gehen nirgends hin', 'no channel — alerts go nowhere'],
	['alarme.kanaele.einleitung', 'Alerts sind kurze Sofort-Meldungen — <kanaele> sind dafür ideal. Das geplante Briefing (die Tabelle) läuft davon getrennt weiter über seine eigenen Kanäle.', 'Alerts are short instant notifications — <kanaele> are ideal for them. The planned briefing (the table) continues separately over its own channels.'],
	['alarme.kanaele.umschalten', '<kanal> umschalten', 'Toggle <kanal>'],
	['alarme.kanaele.sub.telegram', 'sofortiger Push', 'instant push'],
	['alarme.kanaele.sub.sms', 'sofort · ≤ 140 Z.', 'instant · ≤ 140 chars'],
	['alarme.kanaele.sub.premium_sms', 'Satellit · auch ohne Handynetz', 'satellite · works without mobile network'],
	['alarme.kanaele.sub.email', 'optional · langsamer als Push', 'optional · slower than push'],
	// #1895 S3b1: Kanäle je Wettergröße (AlertMetricChannelsBlock)
	['alarme.kanaele.ueberschrift', 'Kanäle je Wettergröße', 'Channels per weather variable'],
	['alarme.kanaele.wie_abo', 'wie Alert-Kanäle', 'same as alert channels'],
	['alarme.kanaele.eigene_wahl', 'eigene Wahl', 'own choice'],
	['alarme.kanaele.nicht_im_abo', 'In den Alert-Kanälen ausgeschaltet: <kanaele>. Die Wahl wird trotzdem gespeichert.', 'Switched off in the alert channels: <kanaele>. The choice is saved anyway.'],
	['alarme.kanaele.metrikfrei_hinweis', 'Radar- und Regen-Alarme sowie amtliche Warnungen gehen immer über die Alert-Kanäle, nicht über die Wahl je Wettergröße.', 'Radar and rain alerts as well as official warnings always use the alert channels, not the choice per weather variable.'],
	['alarme.kanaele.wind_hinweis', 'Ein Alarm zur Windänderung folgt je nach Auslöser der Kanalwahl der Böen- oder der Wind-Zeile.', 'A wind change alert follows the channel choice of the gust or the wind row, depending on what triggered it.'],
	['alarme.kanaele.nicht_verfuegbar', 'Kanäle je Wettergröße sind gerade nicht verfügbar. Es gelten die Alert-Kanäle.', 'Channels per weather variable are currently unavailable. The alert channels apply.'],
	['alarme.kanaele.stufe.low', 'gering', 'low'],
	['alarme.kanaele.stufe.moderate', 'mittel', 'moderate'],
	['alarme.kanaele.stufe.high', 'hoch', 'high'],
	// #1895 S3b2: Hinweise „Kanal ohne Empfänger" und „Kanal-Schwelle über Metrik-Stufe" (AC-75).
	['alarme.kanaele.kein_empfaenger', '<kanal> hat keinen Empfänger — diese Alarme kommen dort nicht an. Eintragen im Reiter Zustellung bzw. im Profil.', '<kanal> has no recipient — these alerts will not arrive there. Add it in the Delivery tab or in your profile.'],
	['alarme.kanaele.schwelle_hinweis', '<kanal> hat die Dringlichkeits-Schwelle „<schwelle>“ — schwächere Warnungen kommen über diesen Kanal nicht an.', '<kanal> has the urgency threshold "<schwelle>" — weaker warnings will not arrive over this channel.'],
	['alarme.premium_sms.tarif_wird_geprueft', 'Tarif wird geprüft — der Kanal lässt sich einen Moment lang nicht umschalten.', 'Checking your level — the channel cannot be switched for a moment.'],
	// Cooldown und Stille Stunden
	['alarme.cooldown.titel', 'Cooldown', 'Cooldown'],
	['alarme.cooldown.einheit', 'Minuten', 'minutes'],
	['alarme.cooldown.hinweis', 'Mindestabstand zwischen zwei Alerts derselben Metrik — verhindert Spam bei zappelnden Werten.', 'Minimum gap between two alerts for the same metric — prevents spam from fluctuating values.'],
	['alarme.stille_stunden.titel', 'Stille Stunden', 'Quiet hours'],
	['alarme.stille_stunden.aktiv', 'Aktiv', 'Active'],
	['alarme.stille_stunden.hinweis', 'In diesem Zeitraum keine Alerts senden (Ortszeit <zonen_bezug>) — gestaute Alerts gehen mit dem nächsten Morgen-Briefing mit.', 'Do not send alerts in this period (local time <zonen_bezug>) — queued alerts go out with the next morning briefing.'],
	['alarme.stille_stunden.bezug_route', 'der Trip', 'of the trip'],
	['alarme.stille_stunden.bezug_vergleich', 'des ersten Orts', 'of the first location'],
	['alarme.stille_stunden.von', 'Von', 'From'],
	['alarme.stille_stunden.bis', 'Bis', 'To'],
	['alarme.stille_stunden.mitternacht', 'Stille Stunden über Mitternacht (<von> bis <bis> des nächsten Tages).', 'Quiet hours across midnight (<von> to <bis> of the next day).'],
	// Empfindlichkeits-Tabelle (AlertMetricLevelTable/-Row)
	['alarme.tabelle.leer', 'Keine alertable Metriken aktiv. Wähle Metriken im Reiter Wetter.', 'No alertable metrics active. Select metrics in the Weather tab.'], // #2794 S3a 4b (AC-33)
	['alarme.tabelle.metrik', 'Metrik', 'Metric'],
	// #2793 S2b: nur lesbare Tabelle „Alarm ab" (Spec §6).
	['alarme.alarm_ab.titel', 'Alarm ab', 'Alert from'],
	['alarme.alarm_ab.wert', 'Alarm ab: {stufe}', 'Alert from: {stufe}'],
	['alarme.alarm_ab.stufe.never', 'Nie', 'Never'],
	['alarme.alarm_ab.stufe.yellow', 'Gelb', 'Yellow'],
	['alarme.alarm_ab.stufe.orange', 'Orange', 'Orange'],
	['alarme.alarm_ab.stufe.red', 'Rot', 'Red'],
	['alarme.alarm_ab.vorbote', 'kein Alarm (Vorbote)', 'no alert (precursor)'],
	[
		'alarme.alarm_ab.umbau_hinweis',
		// #2794 S3a 4b: der Reiter Wetter ist da, der Hinweis nennt ihn als Ort der Einstellung.
		'Alarme folgen jetzt der Ampel. ‚Alarm ab‘ stellst du im Reiter Wetter ein.',
		'Alerts now follow the traffic light. You set ‘Alert from’ in the Weather tab.'
	],
	['alarme.richtwert', 'Richtwert — wird je Wettermodell und Gebiet umgerechnet', 'Guide value — converted per weather model and area'],
	['alarme.empfindlichkeit.aus', 'Aus', 'Off'],
	['alarme.stufe.info', 'Info', 'Info'],
	['alarme.stufe.warning', 'Warnung', 'Warning'],
	['alarme.stufe.critical', 'Kritisch', 'Critical'],
	// Stufen-Namen (AlertMetricLevelTable/-Row; Schliessen auch LocationNewModal)
	['alarme.preset.entspannt', 'Entspannt', 'Relaxed'],
	['alarme.preset.standard', 'Standard', 'Standard'],
	['alarme.preset.sensibel', 'Sensibel', 'Sensitive'],
	['alarme.preset.schliessen', 'Schließen', 'Close'],
	// Alarm-Metrik-Namen (ALERT_METRIC_LABELS, alertMetricLabel; Spec Abschnitt 3)
	['alarme.metrik.wind_gust', 'Böen', 'Wind gusts'],
	['alarme.metrik.precipitation_sum', 'Niederschlag', 'Precipitation'],
	['alarme.metrik.thunder_level', 'Gewitter', 'Thunderstorm'],
	['alarme.metrik.snow_line', 'Schneefallgrenze', 'Snow line'],
	['alarme.metrik.temperature_min', 'Temperatur (Minimum)', 'Temperature (minimum)'],
	['alarme.metrik.temperature_max', 'Temperatur (Maximum)', 'Temperature (maximum)'],
	['alarme.metrik.temperature_change', 'Temperatur (Änderung)', 'Temperature (change)'],
	['alarme.metrik.wind_change', 'Wind (Änderung)', 'Wind (change)'],
	['alarme.metrik.precipitation_change', 'Niederschlag (Änderung)', 'Precipitation (change)'],
	['alarme.metrik.fresh_snow', 'Neuschnee', 'Fresh snow'],
	['alarme.metrik.cape', 'Gewitterenergie (CAPE)', 'Thunderstorm energy (CAPE)'],
	['alarme.metrik.visibility', 'Sichtweite', 'Visibility'],
	['alarme.metrik.humidity', 'Luftfeuchtigkeit', 'Humidity'],
	['alarme.metrik.freezing_level', 'Nullgradgrenze', 'Freezing level'],
	['alarme.metrik.thunder_onset', 'Gewitter (Beginn)', 'Thunderstorm (onset)'],
	['alarme.metrik.precipitation_heavy_onset', 'Starkregen (Beginn)', 'Heavy rain (onset)'],
	// Beispiel-Warnung (AlertPreviewCard)
	['alarme.vorschau.keine_metriken', 'Keine alert-fähigen Wetter-Metriken aktiv. Aktiviere zuerst Wetter-Metriken (z.B. Windböen, Temperatur) im Tab <link>.', 'No alert-capable weather metrics active. First activate weather metrics (e.g. wind gusts, temperature) in the <link> tab.'],
	['alarme.vorschau.reiter_wetter_metriken', 'Wetter', 'Weather'], // #2794 S3a 4b (AC-33)
	['alarme.vorschau.nach_speichern', 'Die Vorschau mit echten Daten ist nach dem Speichern verfügbar.', 'The preview with real data is available after saving.'],
	['alarme.vorschau.keine_orte', 'Noch keine Orte konfiguriert — im Reiter <reiter> Kandidaten hinzufügen.', 'No locations configured yet — add candidates in the <reiter> tab.'],
	['alarme.vorschau.reiter_orte', 'Orte', 'Locations'],
	['alarme.vorschau.regel_aktivieren', 'Aktiviere mindestens eine Alert-Regel, um die Vorschau zu laden.', 'Activate at least one alert rule to load the preview.'],
	['alarme.vorschau.laden', 'Vorschau laden', 'Load preview'],
	['alarme.vorschau.lade', 'Lade…', 'Loading…'],
	// Issue #1839 AC-6: Ladehinweis waehrend der Berechnung (neu, kein Bestandstext).
	['alarme.vorschau.berechnet', 'Vorschau wird berechnet…', 'Computing preview…'],
	['alarme.vorschau.fehler', 'Vorschau konnte nicht geladen werden', 'Preview could not be loaded'],
	['alarme.vorschau.iframe_titel', 'Alert-Vorschau E-Mail', 'Alert preview email']
];
