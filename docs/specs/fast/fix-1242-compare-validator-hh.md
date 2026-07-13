# Mini-Spec: fix-1242-compare-validator-hh

Issue #1242 — Der Ortsvergleichs-Prüfer erwartet in der Stundentabelle noch `HH:MM` und weist damit eine Mail zurück, die nach der freigegebenen Spec zu #1237 korrekt ist.

## Was ändert sich

- `.claude/hooks/email_spec_validator.py::validate_hourly_table` (Zeile 412): Die Erwartung wird vom Format `09:00` auf das Format `09` umgestellt — dasselbe Format, das der Renderer laut PO-Freigabe erzeugt.
- `main()` (Zeile 458 ff.): Das Flag `--mail-type` wird ergänzt. Die anderen beiden Mail-Prüfer kennen es, dieser bricht ohne es bislang mit Exit 2 ab, obwohl die Projekt-Konvention den Aufruf mit `--mail-type` vorschreibt. Der Prüfer akzeptiert `compare` und lehnt einen offensichtlich falschen Typ (z.B. `trip-briefing`) mit klarer Meldung ab — das verhindert genau die Fehldiagnose, die zum Renderer-Gate-Erosionsproblem geführt hat.

## Was darf sich nicht ändern

- Alle übrigen Prüfungen: Struktur, Orts-Anzahl (`--min-locations`), Plausibilität, Format, Score/Winner-Negativcheck.
- Die Vollständigkeits-Logik selbst: Es wird weiterhin **pro Ort** geprüft, ob jede erwartete Stunde in der Tabelle steht (nicht bloß String-Presence im Body, Issue #1108).
- Exit-Codes und das YAML-Log bleiben unverändert.

## Manuelle Test-Schritte

1. Prüfer gegen die bereits zugestellte Vergleichs-Mail (Zeit-Zellen `09`…`16`) laufen lassen → Exit 0.
2. Prüfer mit `--mail-type compare` aufrufen → läuft normal durch.
3. Prüfer mit `--mail-type trip-briefing` aufrufen → klare Ablehnung („falscher Validator"), kein stiller Durchlauf.

## Inline-Test (wird während der Implementierung geschrieben)

- [ ] Tabelle mit Zeit-Zellen `09`…`16` → keine „fehlende Stunden"-Fehler
- [ ] Tabelle mit fehlender Stunde (`09`, `11`, …) → Fehler nennt die fehlende Stunde
- [ ] `--mail-type` wird akzeptiert
