# Mini-Spec: fix-857-860-test-hygiene

Issues: #857, #860

## Was ändert sich

**#857 — Fixture prüft alten Env-Namen**
- `tests/tdd/test_issue_811_mode_matrix.py:619`
- `os.environ.get("GZ_ACTIVE_WORKFLOW", "")` erweitern auf OR-Check mit `OPENSPEC_ACTIVE_WORKFLOW`
- Fix: `if not (os.environ.get("OPENSPEC_ACTIVE_WORKFLOW", "").strip() or os.environ.get("GZ_ACTIVE_WORKFLOW", "").strip()):`

**#860 — Stale Test nach #819**
- `tests/integration/test_config_persistence.py::TestFriendlyFormatRespectsConfig::test_visibility_friendly_on_shows_label`
- Seit #819 ist `visibility.has_friendly_format=False` — `"good"` wird nie mehr zurückgegeben
- Test anpassen: `assert result == "good"` → `assert result in ("15", "15 km")` (roher numerischer Wert)

## Was darf sich nicht ändern

- Kein Produktionscode berührt
- Alle anderen Tests in beiden Dateien bleiben grün

## Manuelle Test-Schritte

1. `uv run pytest tests/tdd/test_issue_811_mode_matrix.py -x` → grün
2. `uv run pytest tests/integration/test_config_persistence.py::TestFriendlyFormatRespectsConfig -x` → grün
3. Gesamte Test-Suite: `uv run pytest` → keine neuen Fehler

## Inline-Test (bereits vorhanden)

- [ ] #857: autouse-Fixture feuert bei `OPENSPEC_ACTIVE_WORKFLOW` gesetzt
- [ ] #860: `test_visibility_friendly_on_shows_label` erwartet numerischen Wert
