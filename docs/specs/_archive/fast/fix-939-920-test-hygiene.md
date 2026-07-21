# Mini-Spec: Test-Hygiene (#939 + #920)

## Was ändert sich

1. **#939** — `tests/tdd/test_issue_930_golden_gate.py::test_renderer_mail_gate_has_golden_check`
   prüft aktuell nur `"golden_ok" in source` (Dateiinhalt-Check, verboten laut CLAUDE.md).
   Wird ersetzt durch einen echten Subprozess-Verhaltenstest nach dem etablierten Muster aus
   `tests/tdd/test_issue_830_radar_alert_validator.py::_run_gate` /
   `_make_temp_git_repo_with_workflow`:
   - Temp-Git-Repo mit Kopie des echten `tests/golden/email/`-Verzeichnisses anlegen
   - Eine Mail-Renderer-Datei (`src/output/renderers/email/html.py`) stagen
   - Einen Golden-Snapshot absichtlich korrumpieren (Byte-Mismatch)
   - `renderer_mail_gate.py` als Subprozess ausführen (`cwd=tmpdir`)
   - Erwartung: Exit-Code 2, Block-Message enthält `"regenerate.py"`
   - Der `# doc-compliance-test`-Marker entfällt (ist jetzt echter Verhaltenstest).

2. **#920** (== #938, dupliziert und geschlossen) —
   `tests/tdd/test_issue_862_849_col_labels.py` Zeile 17/125: `import requests` /
   `requests.get(...)` wird durch `httpx` ersetzt (bereits Projekt-Standard, siehe
   `test_issue_830_radar_alert_validator.py`). Keine neue Dependency nötig.

## Was sich nicht ändern darf

- Die anderen beiden Tests in `test_issue_930_golden_gate.py`
  (`test_regenerate_script_exists`, `test_settings_json_has_preToolUse_renderer_gate`)
  bleiben unverändert — das sind legitime `# doc-compliance-test`-Fälle (prüfen
  Workflow-Artefakte selbst, keine Verhaltens-Mocks).
- Das eigentliche Gate-Verhalten (`renderer_mail_gate.py`) wird NICHT verändert —
  nur die Testabdeckung dafür.
- `test_api_metrics_returns_col_label` bleibt inhaltlich identisch (nur `requests` → `httpx`),
  Marker `@pytest.mark.staging` bleibt erhalten.

## Manuelle Test-Schritte

1. `uv run pytest tests/tdd/test_issue_930_golden_gate.py -v` → 3 grün, neuer Test beweist
   echtes Blockier-Verhalten (nicht nur String-Presence).
2. `uv run pytest tests/tdd/test_issue_862_849_col_labels.py --collect-only` → keine
   `ModuleNotFoundError` mehr.
3. Voller `uv run pytest tests/tdd/ -q` Lauf ohne neue Fehlschläge.

## Inline-Test (wird während Implementierung geschrieben)

- [ ] Neuer Subprozess-Test in `test_issue_930_golden_gate.py` schlägt fehl, wenn
      `golden_ok`-Check im Gate entfernt würde (Kontrollprobe: Gate temporär patchen,
      Test muss rot werden, dann zurücksetzen)
- [ ] `test_api_metrics_returns_col_label` läuft weiterhin nur mit `@pytest.mark.staging`
