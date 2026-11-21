# Kontext und Analyse #3204: Anzeige-Metriken im Reiter Wetter (Trip) gegen Mockup Fassung 4

Refs #2913, #3151, #3086. Nur Analyse, kein Code.

## 1. Die 10 Besitzer-Einträge (`docs/context/einstellungen_neu/elementliste_besitzer.json`, verweis #3204)
Alle: ctx `trip`, reiter `wetter`, art `zusaetzlich`, Grund "im Mockup nicht vorhanden (#3151-Abgleich 20.11.)".

| Zustand/Text | DE | EN |
|---|---|---|
| Metrik-Name Tief | Tages-Tiefsttemperatur (Gehzeit) | Daytime low (walking hours) |
| Metrik-Name Hoch | Tages-Höchsttemperatur (Gehzeit) | Daytime high (walking hours) |
| Untertitel | °C · nur Anzeige, keine Ampel | °C · display only, no traffic light |
| Zeilenmitte | keine Ampel, nur Anzeige | no traffic light, display only |
| Erklärsatz | Nur Anzeige: keine Ampel und kein Alarm. Roh oder Einfach stellst du unten je Liste ein. | Display only: no traffic light and no alert. You set raw or simple below for each list. |

(Keine `id`-Spalte im Besitzer-Eintrag; Schlüssel ist ctx+reiter+text.) Kein Eintrag ist "abweichend" - alle zehn "zusaetzlich".

## 2. Herkunft im Code
- Metrik-Register Python: `src/app/metric_catalog.py:221` (`temperature_day_low`, Kürzel L, trip_default_rank 8) und `:250` (`temperature_day_high`, Kürzel D, rank 9). Eingeführt Issue #1728 Scheibe 1 (Commit c18f8eb7c, 2026-08-15; PO-Beobachtung 11.08.2026: "wo kann der User Höchst-/Tiefsttemperatur beeinflussen?"). Kürzel-Nachzug #1887 (245d00d59), Mehrsprachigkeit label_en #2662. Wert = Gehzeit-Aggregation (`collect_hiking_window_points`), nicht Tagesfenster 04-19. Reine Sichtbarkeits-Gates für SMS-Token L/D, keine Alarme.
- Einstufung "nur Anzeige": `metric_catalog.py:1308-1309` (`_REITER_WETTER`, display_only=True), Ausgabe als `display_only` über `reiter_wetter_eigenschaften` (`:1342-1348`). Gleiche Einstufung haben `wind_direction`, `precip_type`, `cloud_mid/high`, `pressure`, `wind_chill_night/_day_*`. Seit #2794 S3a (d3da25f15, 08.11.).
- Frontend-Namen: `frontend/src/lib/i18n/messages/de/wertebereiche.json:86-87` (auch en); sichtbar in `WeatherMetricsTab.svelte:1894` ff. (Symbolzeile).
- Erscheinen: Editor (Reiter Wetter, Gruppe Temperatur, nur Anzeige), E-Mail-Tabellenspalte nein (keine summary_fields), SMS/Telegram-Token L/D (Gates), Ortsvergleich bietet sie bewusst NICHT an (ADR-0011, Gehzeit-Exklusivität; #2944).
- Hinweistexte: `frontend/src/lib/i18n/messages/de/wetter.json:54` (`wetter.zeile.nur_anzeige`, genutzt `organisms/wetter-tab/MetrikZeile.svelte:72`), `:56` (`wetter.untertitel.nur_anzeige`, `shared/wetter-tab/ampelModell.ts:324`), `:84` (`wetter.erklaer.anzeige`, `ampelModell.ts:352`); EN-Pendants `en/wetter.json:54,56,84`. Eingeführt mit #2955 (Mockup-Angleichung).

## 3. Mockup (`docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html`)
- `TRIP_METRICS` (Z. 316-330) enthält 14 Zeilen, Gruppe Temperatur nur: Temperatur, Tiefsttemperatur Nacht, Gefühlte Temperatur. `TRIP_OFF` (Z. 332): Bewölkung, Sonnenstunden, Neuschnee, Schneehöhe, Taupunkt, Luftfeuchte, Luftdruck. Die zwei Gehzeit-Metriken fehlen in beiden. Das Mockup ist erkennbar ein Auszug: auch `precip_type`, `cloud_mid/high`, `wind_chill_night/_day_*` fehlen. Es gibt keinen Hinweis, dass das Weglassen bewusst ("gehört nicht in den Reiter") war; ein Ausschluss-Beschluss ist nirgends dokumentiert.
- Das Mockup kennt die Nur-Anzeige-Form bereits, am Beispiel Windrichtung (Flag `m[11]`): Untertitel `[Einheit, Hinweis].join(' · ')` = "° · nur Anzeige, keine Ampel" (Z. 470, 322), Zeilenmitte "keine Ampel, nur Anzeige" (Z. 471), Erklärsatz Z. 427: "Nur Anzeige: keine Ampel und kein Alarm. Roh oder Einfach stellst du unten unter „Was steht wo“ ein." Die App-Formen für 3 der 5 Texte sind also dieselbe Form (nur Einheit °C statt °) und gehören inhaltlich zur Mockup-Regel; sie stehen nur deshalb auf der Liste, weil die Zeilen im Mockup fehlen.
- Echte Wortlautabweichung: Erklärsatz App "…unten je Liste ein." gegen Mockup "…unten unter „Was steht wo“ ein." (App hat den Abschnitt "Was steht wo", `wetter.json:134`, #3122; der Mockup-Wortlaut ist also sachlich zutreffend).
- Luftdruck (Mockup): in `TRIP_OFF`, kein eigener Nur-Anzeige-Satz. Sonnenstunden: "zu wenig ist schlecht" (hat Ampel). Es gibt im Mockup keine andere Formulierung für Nur-Anzeige-Metriken als die oben. #3086 (Luftdruck zeigt zugleich "nur Anzeige" und "Nur im Briefing gefärbt") ist ein getrenntes Problem; Lösung dort darf die Nur-Anzeige-Sätze nicht ändern.

## 4. Optionen
- **A: Mockup ergänzen + App-Erklärsatz an Mockup angleichen.** Zeilen `temperature_day_low/high` (Gruppe Temperatur, hinter Nacht, display-only wie Windrichtung, Untertitel "°C · nur Anzeige, keine Ampel") ins Mockup (TRIP_METRICS bzw. wie Windrichtung als aus/an), Erklärsatz der App DE+EN auf "unter „Was steht wo“" ändern, 10 Besitzer-Einträge auflösen. Keine Nutzerfunktion verloren, keine Datenmigration.
- **B: Metriken aus dem Reiter entfernen.** Nimmt dem Nutzer die ausdrücklich gewünschte Wahl (#1728, PO 11.08.) weg, bricht SMS-Token L/D-Steuerung; Bestandstrips mit diesen Metriken (`trip_default_rank` 8/9, in Metrik-Konfigurationen aktiv) verlören die Auswahl oder erhielten verwaiste IDs. Verstößt gegen die Nutzerfunktions-Regel; abzulehnen.
- **C: Mischform** (Metriken nur im Mockup-Pfad "Nicht im Briefing"/Aufklapper): Mehraufwand ohne Gewinn; die Mockup-Mechanik (`m[11]`-Zeilen) trägt bereits die Zeilenform.

## 5. Empfehlung (Tech Lead)
**A.** Die Metriken sind PO-beauftragte Nutzerfunktion (#1728) und Teil des Katalogs; das Mockup ist Auszug. Der Erklärsatz folgt dem Mockup (Soll). Reihenfolge im Mockup nach `_REITER_WETTER`: Temperatur, Nacht, Tages-Tief, Tages-Hoch, Gefühlte. Ortsvergleich bleibt ohne diese Metriken (ADR-0011).
**Produktentscheidung des PO nötig: nein.** #1728 legt fest, dass die Metriken wählbar bleiben; die Nur-Anzeige-Form legt das Mockup selbst fest. Zu beachten: Das Mockup ist PO-Soll, die Ergänzung wird per Bildabgleich (ADR-0112 / mockup-bildpruefer) und Soll/Ist-Bild an Henning bestätigt, ohne neue Fragen. Hinweis: #3091 (Gehzeit vs. Tagesfenster, offen, Produktfrage) ist davon unabhängig, ändert aber die Bedeutung des Zusatzes "(Gehzeit)" im Namen, falls dort umentschieden wird.
