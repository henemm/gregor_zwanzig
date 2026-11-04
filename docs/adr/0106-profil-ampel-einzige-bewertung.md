# ADR-0106: Die Profil-Ampel ist die einzige Bewertung einer Wettergröße — Briefing-Farbe, SMS-Hervorhebung und Alarm lesen dieselbe beidseitige Skala aus der Vorlage

- **Status:** Akzeptiert (PO-Annahme 2026-11-04 per Rückfrage, mit den drei Präzisierungen unten)
- **Datum:** 2026-11-03 (Entwurf), 2026-11-04 (angenommen)
- **Bezug:** Epic #2791, Scheiben S1 #2792, S2 #2793, S7 #2799, Kontext `docs/context/einstellungen_neu.md` §2, §4; **löst ADR-0043 ab** und **ADR-0013 teilweise ab**; ADR-0040 ist schon durch ADR-0043 abgelöst und bleibt es; **bestätigt** ADR-0009 (Abweichungs-Wächter), ADR-0056 (rollierender Anker), ADR-0010 (Vorboten ohne Alarm), ADR-0046 (Kanal-Schwelle regelt den Weg, nicht das Ob), ADR-0025 (eine Gewitter-Quelle)

## Kontext

Eine Wettergröße wird heute an bis zu **vier Stellen** bewertet, die einander nicht kennen:

1. **Display-Ampel** (`display_thresholds`, `src/app/metric_catalog.py:57`): global, für alle Nutzer gleich, nur 10 Metriken, Ticket für Ticket gewachsen (#759 ff.). Sie färbt das Briefing.
2. **Wertebereich** (`corridors`, `src/app/models.py:1282`): „grün markieren“. Seit ADR-0043 ohne Alarm-Wirkung.
3. **SMS-Schwellwert** (`MetricConfig.sms_threshold`, `models.py:689`, Stufen Sensibel/Standard/Robust, nur Trip).
4. **Δ-Empfindlichkeit** (`metric_alert_levels`, `models.py:848`, off/entspannt/standard/sensibel; ADR-0043).

Der PO nennt die Oberfläche dazu „eine Katastrophe“. Nutzer denken in „gefährlich / unangenehm / ideal“ und „wann“ (JTBD-Analyse), nicht in Δ-Werten. Eine globale Skala kann nicht abbilden, dass dieselbe Größe je Aktivität in **beide** Richtungen kritisch wird: Skitour bei −30 °C und bei +15 °C rot, Flaute beim Segeln schlecht (PO-Notiz 2026-11-03).

## Entscheidung

1. **Eine Bewertung je Metrik: die Ampel** mit vier Stufen grün · gelb · orange · rot. Sie ist **beidseitig**: unten rot < orange < gelb, oben gelb < orange < rot, grün dazwischen. Jede Seite kann offen sein. Gewitter (ordinal) bekommt eine Farbe je Stufe: „keins“ immer grün, „mittel“ gelb/orange/rot, „hoch“ orange/rot, „leicht“ immer gelb (siehe Präzisierung P2).
2. **Die Ampel kommt aus der Vorlage** (die 7 Vorlagen aus `WEATHER_TEMPLATES`, mit den vom PO angenommenen Grenzen, Kontext §4.4) und ist **je Trip/Ort änderbar**. Abweichungen werden gezählt. Eine eigene Vorlage speichert Auswahl, Ampel und Alarmstufen zusammen. **Kein globaler Toleranz-Regler.**
3. **Alle Leser nutzen dieselbe Ampel:** die Farbe im Briefing (alle vier Kanäle, ADR-0095), die Hervorhebung in SMS/Premium-SMS/Telegram („@14 ab 14 Uhr gelb oder schlechter“) und der Alarm.
4. **Der Alarm hängt an der Ampel** und bleibt ein **Abweichungs-Wächter** (ADR-0009, Anker nach ADR-0056). Je Metrik gilt **„Alarm ab: Nie · Gelb · Orange · Rot“** (Gewitter: Nie · Orange · Rot). Ein Alarm kommt,
   - wenn die Ampelstufe gegenüber dem Anker **auf oder über** die eingestellte Stufe **steigt** (Stufenwechsel), **oder**
   - bei einem **sehr großen Sprung innerhalb einer Stufe** (z.B. Böen 65 → 95 km/h, beides rot). Die Sprunggröße legt das System je Metrik fest, nicht der Nutzer.
   - **Entwarnung**, wenn die Stufe wieder unter die eingestellte Stufe fällt (symmetrisch wie ADR-0043).
   - Ein unveränderter Wert meldet nie.
5. **Vorboten** (ADR-0010) werden gefärbt, lösen aber nie einen Alarm aus. Reine Anzeigegrößen ohne Ampel: Luftdruck, Windrichtung, Niederschlagsart, mittlere und hohe Wolken. Luftfeuchte wird über den Taupunkt bewertet. CAPE geht in der Gewitter-Zeile auf und hat keine eigene Ampel (siehe Präzisierung P1).
6. **Relative Größen:** Nullgradgrenze und Schneefallgrenze werden relativ zur höchsten Stelle der Etappe bzw. zur Ortshöhe bewertet (Meter darüber, negativ darunter). Sonnenstunden sind umgekehrt skaliert, der Taupunkt nutzt eine Schwüle-Skala, die Schneehöhe hängt von der Vorlage ab.
7. **Entfallen** als eigene Einstellungen: Wertebereiche (`corridors`, `ideal_ranges`), Markieren, SMS-Schwellwerte, die Δ-Empfindlichkeitsstufen (`metric_alert_levels`, `alert_rules`). Bestandsdaten werden per **Read-Modify-Write mit Merge** (ADR-0101) in Ampel-Grenzen und „Alarm ab“ überführt. Nichts geht verloren, die Abbildung steht in der Spec von S1/S2.
8. **Unverändert:** Kanal-Schwelle „Alarm schon ab Dringlichkeit“ je Kanal (ADR-0046), Cooldown (unter Zustellung → Anpassen), Stille Stunden, amtliche Warnungen als eigener Typ (ADR-0016), Radar-Alarm mit absoluter Schwelle (ADR-0096).

### Präzisierungen bei der Annahme (PO, 2026-11-04)

- **P1 · CAPE geht wie heute in die Gewitterstufe ein.** CAPE bleibt eine der fusionierten Zutaten der Gewitterstufe, über die geeichte Leiter je Modell und Gebiet und mit Dämpfung durch CIN (`src/providers/thunder_enrichment.py` `_fuse_thunder_levels`, `src/output/metric_format.py` `thunder_level_from_signals`; ADR-0025, ADR-0057). Es entsteht keine neue Rechnung. Es **entfallen**: die eigene CAPE-Zeile, ihre globale Farbe (300/800/1500 J/kg in `display_thresholds`) und der eigene CAPE-Δ-Alarm (`alert_preset.py`, 1200/600/200). Eine gespeicherte CAPE-Auswahl wird auf „Gewitter an“ abgebildet. Verworfen: CAPE-Grenzen je Vorlage (hebelt die Eichung aus, widerspricht ADR-0025) und die CAPE-Zahl als Zusatz in der Gewitter-Zeile (A6: Erklärung weg).
- **P2 · Gewitterstufe „leicht“ ist immer gelb.** Die Skala hat vier Stufen (keins · leicht · mittel · hoch, `ThunderLevel`, Issue #1474). „Keins“ ist fest grün, „leicht“ fest gelb (wie heute, `metric_format.py`), je Vorlage einstellbar sind nur „mittel“ und „hoch“. „Alarm ab“ für Gewitter bleibt **Nie · Orange · Rot**; „leicht“ allein löst nie einen Alarm aus (wie heute: auch „sensibel“ meldet erst ab „mittel“).
- **P3 · Alte Empfindlichkeitsstufen werden relativ zur Vorlage abgebildet** (Umsetzung in S2 #2793, per Read-Modify-Write mit Merge). Reihenfolge der Empfindlichkeit: Nie < Rot < Orange < Gelb.
  - `off` → **Nie**
  - `standard` → **Vorgabe der Vorlage** für diese Metrik (meist Orange). Wer nie etwas geändert hat, bekommt dasselbe wie ein neuer Trip.
  - `sensibel` → **eine Stufe empfindlicher als die Vorgabe** (Orange → Gelb, Rot → Orange, Nie → Rot), höchstens bis zur empfindlichsten erlaubten Stufe (Gelb; bei Gewitter Orange).
  - `entspannt` → **Rot**.
  - Vorboten (ADR-0010) bekommen unabhängig vom Altwert keinen Alarm. Der Altwert wird protokolliert; die Abbildung ist eine Annäherung, weil die alten Stufen eine Δ-Größe, die neuen eine erreichte Farbe meinen.
  - Verworfen: feste Zuordnung ohne Vorlage (weicht bei Gewitter und bei Vorgabe „Nie“ von neuen Trips ab) und „alles auf Vorlage“ (bewusst gesetzte Wahl ginge verloren).

## Verworfene Alternativen

- **Δ wie heute, nur einfacher benannt** (Karte `alarm_logik`, Variante „delta_einfach“): Die Ampel hätte nur das Briefing gefärbt und der Alarm einen zweiten Maßstab behalten. Damit blieben zwei Skalen je Metrik.
- **Nur Stufenwechsel ohne Sprung:** Ein Sprung von 65 auf 95 km/h Böen bliebe stumm, weil beides rot ist. Verworfen zugunsten von „beides“.
- **Wichtigkeit in eigenen Wörtern** („Egal · Normal · Wichtig · Sehr wichtig“ oder die heutigen „Aus · Entspannt · Standard · Sensibel“): Man sieht nicht, welche Farbe dahintersteckt, und „Sensibel“ meinte heute in zwei Reitern Verschiedenes.
- **Ampel nur für die heutigen 10 Metriken:** Nullgradgrenze, Schneefallgrenze und Schneehöhe hätten ihren Δ-Alarm behalten, und der Wertebereich wäre nicht vollständig ersetzbar gewesen.
- **Globaler Toleranz-Regler** (vorsichtig · normal · erfahren): ein Regler mehr, die Vorlage reicht.

## Konsequenzen

- **Positiv:** Ein Regler je Frage. „Was ist für mich kritisch?“ heißt Ampel, „ab wann will ich gestört werden?“ heißt „Alarm ab“. Die Farbe im Briefing erklärt den Alarm. Aktivitäten mit beidseitigen Grenzen werden abbildbar.
- **Negativ / Preis:** Die Grenzen sind nicht mehr global. Jeder Renderer braucht die Ampel des Abos statt des Katalogs, und Tests mit globalen Erwartungswerten müssen umgestellt werden. Die Migration der Bestandsdaten ist ein Daten-Schema-Rework. Die Abbildung der alten Empfindlichkeitsstufen ist nur angenähert.
- **Folgepflichten:**
  - Kein Renderer und kein Alarmpfad liest nach der Umstellung noch `display_thresholds` als Nutzer-Bewertung. Der Katalog liefert nur noch die Vorgaben der Vorlage „Allgemein“.
  - Jede neue Metrik wird mit Ampel-Art (beidseitig, nur oben, nur unten, ordinal, keine) und Grenzen je Vorlage eingeführt.
  - Erklärsätze und Begriffe gibt es in DE und EN (ADR-0104).
  - **Bei Annahme nachgezogen (2026-11-04):** ADR-0043 Status „Abgelöst durch ADR-0106“; ADR-0013 Status „Teilweise abgelöst durch ADR-0106 (Auslösung über Stufenwechsel; `threshold` bleibt als Sprung-Schwelle)“; ADR-0040 Kopfzeile „Ergänzt durch: ADR-0106“; ADR-0009 Kopfzeile „Ergänzt durch: ADR-0106 (Auslöser ist der Stufenwechsel der Ampel)“; Index `docs/adr/README.md`; `tests/test_adr_index_drift.py` grün.
