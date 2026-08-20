# Mini-Spec: fix-1998-sonnenstunden-min-anzeige

## Acceptance Criteria

- **AC-1:** Given ein Trip-Datenpunkt mit Sonnenschein (DNI-Wert oberhalb der Sonnenschein-Schwelle) / When die E-Mail-Karten-Übersicht die Sonne-Pille über `_pill_for_metric("sunshine", ...)` rendert / Then lautet der Pillentext `Sonne <Stunden>h` mit genau einer Nachkommastelle (Katalog: `unit="h"`, `decimals=1`) und enthält weder die Zeichenfolge `min` noch einen mit 60 multiplizierten Minutenwert.

- **AC-2:** Given die bestehende Byte-golden-Absicherung des Pilleninhalts in Katalogordnung / When `test_ac_s7_6b_pilleninhalt_bleibt_bei_katalogordnung_bytegleich` läuft / Then ist die erwartete Sonnen-Zeile auf den neuen Stundentext nachgezogen und der Test bleibt grün, ohne dass andere Pilleninhalte sich ändern.

- **AC-3:** Given die übrigen Kanäle (SMS, Telegram, Ortsvergleich) sowie `WeatherMetricsService.calculate_sunny_hours()` / When der Fix angewandt ist / Then bleiben deren Ausgaben und der neutrale Ampel-Ton `_PILL_NEUTRAL_TONE` der Sonne-Pille unverändert.

- **AC-4:** Given `.claude/hooks/briefing_mail_validator.py::_check_metric_plausibility` (AC-4 des Mail-Gates) liest die Sonne-Pille bislang über eine fest auf `"min"` verankerte Regex, um sie gegen die Stundentabellen-Summe zu prüfen / When die Pille künftig `Sonne X.Xh` statt `Sonne X min` zeigt / Then wird die Regex auf das Stunden-Format umgestellt, damit die Plausibilitätsprüfung weiter greift (nicht durch die reine Formatänderung stillschweigend nie wieder anschlägt) — inklusive Nachzug der zugehörigen Werkzeug-Tests `tests/tdd/test_issue_833_gate.py` und `tests/unit/test_briefing_validator_sonne_plausibilitaet.py`, deren synthetische Test-Mails ebenfalls `"X min"`-Pillen bauen.

- **AC-5:** Given `tests/tdd/test_issue_808_sonne_pill.py::TestAC1SunshinePillPositiveMinutes` prüft den echten Renderer-Output über eine `"X min"`-Regex / When der Renderer auf Stunden umstellt / Then wird die Assertion auf das neue Format nachgezogen, sodass der Test grün bleibt und weiterhin beweist, dass sonnige Datenpunkte eine positive Sonnenschein-Pille erzeugen.

## Was ändert sich
- E-Mail-Trip-Briefing, Karten-Übersicht "METRIKEN-ÜBERBLICK": Die Sonne-Pille zeigt bislang
  `Sonne <N> min` (Minuten, z.B. "Sonne 546 min") statt der im Metrik-Katalog definierten
  Einheit Stunden (`sunshine`: `unit="h"`, `decimals=1`).
- `src/output/renderers/email/helpers.py:1629` (`_pill_for_metric`, Zweig `metric_id == "sunshine"`):
  Formatierung auf `format_value("sunshine", total, style="bare")` + `"h"` umstellen —
  identisches Muster wie bereits im Ortsvergleich (`src/output/renderers/comparison.py:116`).
  Ergebnis z.B. `Sonne 9.1h` statt `Sonne 546 min`.
- **Nachgezogene Konsumenten des alten Formats** (bei Implementierung entdeckt): Der
  Mail-Acceptance-Validator `.claude/hooks/briefing_mail_validator.py` prüft die
  Sonne-Pille per Regex gegen die Stundentabellen-Summe (AC-4 des Mail-Gates,
  `_check_metric_plausibility`) — diese Regex ist fest auf `"min"` verankert und muss
  auf `"h"` umgestellt werden, sonst verstummt die Prüfung dauerhaft (kein Fehler, aber
  auch keine Wirkung mehr). Zwei Testdateien bauen synthetische `"X min"`-Pillen zum
  Testen dieses Validators (`tests/tdd/test_issue_833_gate.py`,
  `tests/unit/test_briefing_validator_sonne_plausibilitaet.py`) und müssen mitziehen.
  Zusätzlich prüft `tests/tdd/test_issue_808_sonne_pill.py` den echten Renderer-Output
  per `"min"`-Regex und wird sonst fälschlich rot.

## Was sich nicht ändert
- `WeatherMetricsService.calculate_sunny_hours()` (liefert bereits Stunden) bleibt unverändert.
- Alle anderen Kanäle (SMS, Telegram, Ortsvergleich) zeigen die Sonnenstunden bereits korrekt
  in Stunden — nur dieser eine E-Mail-Pill-Zweig ist betroffen.
- Ampel-Ton (`_PILL_NEUTRAL_TONE`) bleibt neutral.

## Manuelle Test-Schritte
1. Trip-Briefing-Test-E-Mail (Format `full`) für einen Trip mit DNI-Daten rendern.
2. In der Karten-Übersicht die Sonne-Pille prüfen: Text lautet `Sonne <Zahl>h` (eine Nachkomma-
   stelle), nicht `<Zahl> min`.
3. Byte-golden-Regressionstest `tests/tdd/test_channel_metric_matrix.py::test_ac_s7_6b_pilleninhalt_bleibt_bei_katalogordnung_bytegleich`
   auf die neue erwartete Zeile (`Sonne 2.5h` statt `Sonne 150 min`) nachziehen.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] Test für `_pill_for_metric("sunshine", ...)`: Rückgabetext folgt dem Muster `Sonne \d+\.\d h`
      (Stunden mit einer Nachkommastelle), nicht `min`.
