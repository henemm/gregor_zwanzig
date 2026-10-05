# ADR-0082: Budget je Alarmart — die Radar-Jobs laufen im 5-Minuten-Takt mit eigenem, an den Takt gebundenem Budget

- **Status:** Akzeptiert (ergänzt ADR-0070, bezieht sich auf ADR-0038)
- **Datum:** 2026-10-05
- **Bezug:** GitHub-Issue #2261 (Epic A-2, Scheibe S2), Spec `docs/specs/modules/feat_2261_a2s2_radar_takt.md`

## Kontext

ADR-0070 legt für alle Alarm-Fan-out-Jobs ein gemeinsames Budget fest
(Wartebudget 300 s, Laufbudget 720 s, Deckel 1800 s = „zwei Takte" à 15 Minuten).
Ein Regenbeginn wurde dadurch im Schnitt erst rund 32 Minuten nach der Quelle
gemeldet (Takt 15 + Datenalter bis 5 + Verarbeitung/Laufbudget 12). PO-Entscheid
03.10.: Radar-Verzögerung auf rund 15 Minuten verkürzen. Die zwei Radar-Jobs
(`radar_alert_checks`, `compare_radar_alert_checks`) laufen deshalb alle 5
Minuten. Ein Laufbudget von 720 s passt nicht mehr in einen 300-s-Takt; die
übrigen Alarm-Jobs brauchen ihr Wartebudget von 300 s weiter (Python-Grenze
`ALERT_RUN_DEADLINE_SECONDS = 180` plus Überhang).

## Entscheidung

1. **Budget je Alarmart.** `budgetsFor(jobID)` unterscheidet drei Familien:
   Radar 240 / 270 / 600 s (Wartebudget / Laufbudget / Deckel), übrige
   Alarm-Jobs unverändert 300 / 720 / 1800 s, Briefing 600 / 1440 / 0 s.
2. **Takt:** Cron `3-58/5 * * * *` für beide Radar-Jobs (Minuten 3, 8, … 58).
   Kollidiert nicht mit den `*/5`-/`*/15`-Jobs (Minute ≡ 0 mod 5) und nicht mit
   `briefing_dispatch` (:00), hält 3 Minuten Abstand zu :00/:30 (#1628) und
   verlässt die Minute :07 (108 von 109 Open-Meteo-503 in 10 Tagen).
3. **Ungleichungskette (bindend, mit Puffer, kein Null-Puffer).** Takt T = 300 s,
   Zeitgrenze D = 45 s, längster Einzelquellenschritt E = 188 s (INCA 180 +
   Sidecar 8), Nacharbeit N = 10 s:
   - D + E = 233 < 240 = Wartebudget (ADR-0038: Python-Grenze strikt unter Go-Wartezeit)
   - Wartebudget 240 ≤ Laufbudget 270
   - Laufbudget + N = 280 < 300 = T (Überlappungsinvariante, sonst überspringt
     `recordRun` per TryLock den Folgetick)
   - Deckel 600 = 2 × T
   - Cache-TTL 240 ≤ T − D = 255 (jeder Lauf bekommt frische Daten)
4. **Die Zeitgrenze reicht in die Quellenkette hinein.** `get_nowcast(...,
   deadline_at=None)` prüft vor jeder Quelle; abgelaufen ⇒
   `RadarDeadlineExceeded`, nichts im Cache. Worst Case: Zeitgrenze + ein
   Einzelschritt. Eine Prüfung nur zwischen den Einheiten ließe die Laufzeit
   unbegrenzt (ein `get_nowcast` kann die Summe aller Quellen dauern).
5. **Wiederverwendung des Fairness-Mechanismus aus A-2 S1.** Je Alarmart eine
   eigene Stempeldatei (`alert_last_checked_radar.json`,
   `alert_last_checked_compare_radar.json`) über denselben
   `AlertCheckStateStore` und denselben Sortier-Helfer; Trip und Ortsvergleich
   teilen Baustein und Konstante `RADAR_RUN_DEADLINE_SECONDS = 45`. Ein
   Grenzabbruch ist kein Quellenausfall und keine Entwarnung: keine
   Auswertung, kein Protokolleintrag, keine Sperrzeit-/Tageslimit-Buchung,
   kein Stempel.
6. **Laufzählende Schwellen bleiben 3 / 8.** Echtzeit ändert sich: Radar-
   Störmeldung nach 15 statt 45 Minuten, Teilausfall nach 40 statt 120.

## Verworfene Alternativen

- **Ein Budget für alle Jobs.** Zwänge `alert_checks` auf ≤ 240 s und verletzte
  dessen Python-Grenze 180 s + Überhang.
- **Takt 3 Minuten.** Kein Gewinn gegenüber dem Quellen-Rhythmus (RADOLAN 5,
  INCA/AROME-FR/Open-Meteo 15 Minuten); mehr Last auf Cache und Open-Meteo-Budget.
- **Zeitgrenze nur vor `get_nowcast`.** Worst Case nicht begrenzbar.

## Konsequenzen

- **Positiv:** erwartete Radar-Verzögerung im Schlechtesten Fall 5 + 4 + 4,5 =
  13,5 Minuten (Ist 32), typisch 9–10 Minuten.
- **Negativ / Preis:** ×3 Läufe — mehr Gelegenheiten für Sperrzeit-Überholung
  und Tageslimit-Durchbruch, Open-Meteo-Tagesbudget (Drossel 80 %/95 % bleibt
  Sicherung), `alert_log`/`alert_input_capture` füllen sich schneller. Das
  externe Monitoring braucht eine Radar-eigene Altersschwelle (12 Minuten),
  umgestellt erst nach dem Prod-Selftest.
- **Folgepflichten:** Wer Radar-Takt, -Budget, `RADAR_RUN_DEADLINE_SECONDS`,
  Cache-TTL oder die Quellenkette ändert, muss die Kette aus Punkt 3 in
  Go-Test (`radar_budget_per_alarmart_test.go`) und Python-Test
  (`test_radar_alarmlauf_zeitgrenze.py`) mitziehen.
