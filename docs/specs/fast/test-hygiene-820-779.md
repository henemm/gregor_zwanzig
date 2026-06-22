# Mini-Spec: test-hygiene-820-779

Issues: #820, #779

## Was ändert sich

**#820 — `test_issue_685_selftest_menu_gate.py`:**
- `EXPECTED_COMMANDS` Liste um `'now'` ergänzen (nach `'morgen'`, vor `'heute_gewitter'`)
- Korrekte Liste: `["glance", "heute", "morgen", "now", "heute_gewitter", "timeline_heute", "timeline_morgen", "hilfe"]`

**#779 — `internal/store/store_test.go`:**
- `TestLoadLocationsFromRealData` auf `t.Skip()` umstellen mit Begründung:
  "Liest Live-Daten aus data/users/default/locations/ — gitignored, nur in befüllten Instanzen vorhanden"
- `TestLoadLocationsEmptyDir` und andere isolierte Tests bleiben unverändert

## Was darf sich nicht ändern

- Kein Produktivcode (weder Python noch Go)
- `test_ac2_younger_session_blocked` und alle anderen Tests in `test_session_singleton_guard.py` bleiben unberührt
- `test_ac2_bot_menu_live` in `test_issue_685_selftest_menu_gate.py` (Live-Socket-Test) bleibt unberührt

## Manuelle Test-Schritte

1. `uv run pytest tests/tdd/test_issue_685_selftest_menu_gate.py::test_ac1_load_bot_commands_without_pydantic -v` → grün
2. `/usr/local/go/bin/go test ./internal/store/... -v` → kein FAIL mehr (Skip ist ok)

## Acceptance Criteria

**AC-1:** Given `test_ac1_load_bot_commands_without_pydantic` läuft, When pytest ausgeführt wird, Then schlägt der Test nicht mehr fehl weil `EXPECTED_COMMANDS` den `now`-Befehl enthält.

**AC-2:** Given `TestLoadLocationsFromRealData` in einem Clean-Checkout ohne `data/users/default/locations/`, When `go test ./internal/store/...` ausgeführt wird, Then wird der Test übersprungen (SKIP) statt mit FAIL zu beenden.

## Inline-Test

- Beide bestehenden Tests werden durch den Fix direkt grün/skip — kein neuer Test nötig
