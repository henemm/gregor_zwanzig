# Mini-Spec: fix-945 — SMS-Test-Lücken schließen

## Was ändert sich

**A) `tests/unit/test_token_builder.py` — direkte Unit-Tests für `_sanitize_stage_name()`**

Neue Tests (alle `# doc-compliance-test`-frei — testen echtes Verhalten von `_sanitize_stage_name` via `build_token_line`):

- `test_stage_name_without_km` — Name ohne `km` → alter 10-Zeichen-Truncate-Pfad bleibt korrekt (Regressionssicherung)
- `test_stage_name_km_at_start` — Name der **mit** `km` beginnt (`km0-11 Teilstück`) → kein Prefix, nur `km0-11`
- `test_stage_name_multiple_km` — Name mit mehreren `km`-Vorkommen (`km0-11 km15-20`) → nur erstes `km`-Token wird bewahrt
- `test_stage_name_km_with_colon` — `km0-11:` im Input → `rstrip(":")` entfernt den Doppelpunkt
- `test_stage_name_km_space` — `km 0` Format (Leerzeichen nach km) → kein Split auf Leerzeichen-km-Substring, Ergebnis korrekt

**B) `tests/tdd/test_issue_936_sms_stub.py` — Extremwetter + morning + Stub-Isolation**

- `test_sms_text_length_extreme_weather` — Fixture mit max. Wetterwerten (Sturmböen G, hohe Niederschläge R/PR, alle Schwellen gleichzeitig), Render-Länge muss ≤ 140 Zeichen sein
- `test_sms_morning_report_km_format` — `report_type="morning"`, Etappenname mit km-Range → km-Format-Verhalten wie beim Abend-Report
- Stub-Isolation: `last_text()` durch `last_text_matching(contains: str)` ersetzen → Tests matchen anhand ihres eigenen Namens/Inhalts, keine Race-Condition bei Parallel-Ausführung

## Was darf sich nicht ändern

- `_sanitize_stage_name()` selbst wird **nicht** geändert — nur Tests
- Kein Produktionscode außer ggf. `_SMSStub.last_text_matching()` als neue Hilfsmethode im Test-File selbst
- Bestehende Tests in `test_token_builder.py` bleiben unverändert

## Manuelle Test-Schritte

1. `uv run pytest tests/unit/test_token_builder.py -v` — alle Tests grün, inkl. neue
2. `uv run pytest tests/tdd/test_issue_936_sms_stub.py -v` — alle Tests grün, inkl. neue
3. Kein Prod-Code geändert → kein Staging-Deploy erforderlich

## Inline-Test (wird während Implementierung geschrieben)

- [ ] `test_stage_name_without_km` — Name ohne km: 10-Zeichen-Truncate
- [ ] `test_stage_name_km_at_start` — km am Anfang: kein Prefix
- [ ] `test_stage_name_multiple_km` — mehrere km: nur erstes Token
- [ ] `test_stage_name_km_with_colon` — Doppelpunkt nach km wird entfernt
- [ ] `test_stage_name_km_space` — `km 0` Format korrekt behandelt
- [ ] `test_sms_text_length_extreme_weather` — Extremwetter ≤ 140 Zeichen
- [ ] `test_sms_morning_report_km_format` — morning-Report km-Format
- [ ] Stub-Isolation via `last_text_matching()`
