# ADR-0106: Die Profil-Ampel ist die einzige Bewertung einer Wettergröße — Briefing-Farbe, SMS-Hervorhebung und Alarm lesen dieselbe beidseitige Skala aus der Vorlage

- **Status:** Vorgeschlagen
- **Datum:** 2026-11-03
- **Bezug:** Epic „Einstellungen neu“ (Scheiben S1, S2, S7), Kontext `docs/context/einstellungen_neu.md` §2, §4; **löst bei Annahme ADR-0043 ab** und **ADR-0013 teilweise ab**; ADR-0040 ist schon durch ADR-0043 abgelöst und bleibt es; **bestätigt** ADR-0009 (Abweichungs-Wächter), ADR-0056 (rollierender Anker), ADR-0010 (Vorboten ohne Alarm), ADR-0046 (Kanal-Schwelle regelt den Weg, nicht das Ob), ADR-0025 (eine Gewitter-Quelle)

## Kontext

Eine Wettergröße wird heute an bis zu **vier Stellen** bewertet, die einander nicht kennen:

1. **Display-Ampel** (`display_thresholds`, `src/app/metric_catalog.py:57`): global, für alle Nutzer gleich, nur 10 Metriken, Ticket für Ticket gewachsen (#759 ff.). Sie färbt das Briefing.
2. **Wertebereich** (`corridors`, `src/app/models.py:1282`): „grün markieren“. Seit ADR-0043 ohne Alarm-Wirkung.
3. **SMS-Schwellwert** (`MetricConfig.sms_threshold`, `models.py:689`, Stufen Sensibel/Standard/Robust, nur Trip).
4. **Δ-Empfindlichkeit** (`metric_alert_levels`, `models.py:848`, off/entspannt/standard/sensibel; ADR-0043).

Der PO nennt die Oberfläche dazu „eine Katastrophe“. Nutzer denken in „gefährlich / unangenehm / ideal“ und „wann“ (JTBD-Analyse), nicht in Δ-Werten. Eine globale Skala kann nicht abbilden, dass dieselbe Größe je Aktivität in **beide** Richtungen kritisch wird: Skitour bei −30 °C und bei +15 °C rot, Flaute beim Segeln schlecht (PO-Notiz 2026-11-03).

## Entscheidung

1. **Eine Bewertung je Metrik: die Ampel** mit vier Stufen grün · gelb · orange · rot. Sie ist **beidseitig**: unten rot < orange < gelb, oben gelb < orange < rot, grün dazwischen. Jede Seite kann offen sein. Gewitter (ordinal) bekommt eine Farbe je Stufe: „keins“ immer grün, „mittel“ gelb/orange/rot, „hoch“ orange/rot.
2. **Die Ampel kommt aus der Vorlage** (die 7 Vorlagen aus `WEATHER_TEMPLATES`, mit den vom PO angenommenen Grenzen, Kontext §4.4) und ist **je Trip/Ort änderbar**. Abweichungen werden gezählt. Eine eigene Vorlage speichert Auswahl, Ampel und Alarmstufen zusammen. **Kein globaler Toleranz-Regler.**
3. **Alle Leser nutzen dieselbe Ampel:** die Farbe im Briefing (alle vier Kanäle, ADR-0095), die Hervorhebung in SMS/Premium-SMS/Telegram („@14 ab 14 Uhr gelb oder schlechter“) und der Alarm.
4. **Der Alarm hängt an der Ampel** und bleibt ein **Abweichungs-Wächter** (ADR-0009, Anker nach ADR-0056). Je Metrik gilt **„Alarm ab: Nie · Gelb · Orange · Rot“** (Gewitter: Nie · Orange · Rot). Ein Alarm kommt,
   - wenn die Ampelstufe gegenüber dem Anker **auf oder über** die eingestellte Stufe **steigt** (Stufenwechsel), **oder**
   - bei einem **sehr großen Sprung innerhalb einer Stufe** (z.B. Böen 65 → 95 km/h, beides rot). Die Sprunggröße legt das System je Metrik fest, nicht der Nutzer.
   - **Entwarnung**, wenn die Stufe wieder unter die eingestellte Stufe fällt (symmetrisch wie ADR-0043).
   - Ein unveränderter Wert meldet nie.
5. **Vorboten** (ADR-0010) werden gefärbt, lösen aber nie einen Alarm aus. Reine Anzeigegrößen ohne Ampel: Luftdruck, Windrichtung, Niederschlagsart, mittlere und hohe Wolken. Luftfeuchte wird über den Taupunkt bewertet. CAPE geht in der Gewitter-Zeile auf und hat keine eigene Ampel.
6. **Relative Größen:** Nullgradgrenze und Schneefallgrenze werden relativ zur höchsten Stelle der Etappe bzw. zur Ortshöhe bewertet (Meter darüber, negativ darunter). Sonnenstunden sind umgekehrt skaliert, der Taupunkt nutzt eine Schwüle-Skala, die Schneehöhe hängt von der Vorlage ab.
7. **Entfallen** als eigene Einstellungen: Wertebereiche (`corridors`, `ideal_ranges`), Markieren, SMS-Schwellwerte, die Δ-Empfindlichkeitsstufen (`metric_alert_levels`, `alert_rules`). Bestandsdaten werden per **Read-Modify-Write mit Merge** (ADR-0101) in Ampel-Grenzen und „Alarm ab“ überführt. Nichts geht verloren, die Abbildung steht in der Spec von S1/S2.
8. **Unverändert:** Kanal-Schwelle „Alarm schon ab Dringlichkeit“ je Kanal (ADR-0046), Cooldown (unter Zustellung → Anpassen), Stille Stunden, amtliche Warnungen als eigener Typ (ADR-0016), Radar-Alarm mit absoluter Schwelle (ADR-0096).

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
  - **Bei Annahme** wird nachgezogen: ADR-0043 Status „Abgelöst durch ADR-0106“; ADR-0013 Status „Teilweise abgelöst durch ADR-0106 (Auslösung über Stufenwechsel; `threshold` bleibt als Sprung-Schwelle)“; ADR-0040 Kopfzeile „Ergänzt durch: ADR-0106“; ADR-0009 Kopfzeile „Ergänzt durch: ADR-0106 (Auslöser ist der Stufenwechsel der Ampel)“; Index `docs/adr/README.md` und `tests/test_adr_index_drift.py` grün.
