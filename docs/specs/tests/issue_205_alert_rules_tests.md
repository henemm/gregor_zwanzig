---
entity_id: issue_205_alert_rules_tests
type: tests
created: 2026-05-14
updated: 2026-05-14
status: draft
version: "1.0"
tags: [tests, data-model, migration, alerts, issue-205]
parent: issue_205_alert_rules
phase: phase5_tdd_red
---

# Issue #205 — alert_rules Datenmodell + Migration (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für die Implementierung aus
`docs/specs/modules/issue_205_alert_rules.md`. Jeder pytest- bzw. Go-Test
mappt 1:1 auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/issue_205_alert_rules.md` v1.0

## Source

- **File:** `tests/tdd/test_alert_rules_model.py` (NEU — Python-Tests für
  Dataclass, Migration, Roundtrip)
- **File:** `internal/model/alert_rule_test.go` (NEU — Go-Test für
  JSON-Marshal-Verhalten)

## Test Inventory

Test-Funktionsnamen führen den AC-Index, damit der Spec-Enforcement-Hook
sie auflösen kann.

### Python (`tests/tdd/test_alert_rules_model.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_alert_rule_dataclass_fields_exist` | AC-1 | `AlertRule(id, kind, metric, threshold, unit, severity, enabled)` instanziierbar; `metric` als String-Enum vergleichbar mit `"wind_change"`. |
| `test_ac2_trip_has_alert_rules_field_default_empty` | AC-2 | `Trip(...)` ohne `alert_rules`-Argument hat `alert_rules == []` (kein None). |
| `test_ac3_migrate_legacy_creates_three_delta_rules` | AC-3 | `_migrate_legacy_alert_rules({report_config: {alert_on_changes: True, change_threshold_*}})` → drei `AlertRule` mit `kind=delta`, korrekten metric/threshold/unit, `severity=warning`, `enabled=True`, UUID-IDs. |
| `test_ac4_migrate_alert_on_changes_false_keeps_rules_disabled` | AC-4 | Bei `alert_on_changes=False` werden Rules dennoch generiert, aber mit `enabled=False`. |
| `test_ac5_migrate_with_existing_alert_rules_is_noop` | AC-5 | Trip-Dict mit existierendem `alert_rules`-Array wird 1:1 zurückgegeben, keine doppelten Rules. |
| `test_ac6_trip_roundtrip_preserves_alert_rules_and_legacy` | AC-6 | `_trip_to_dict()` → JSON → `load_trip()` → drei Rules identisch (gleiche IDs), Legacy `change_threshold_*` unverändert vorhanden. |
| `test_ac8_typescript_types_export` | AC-8 | Markdown-grep auf `frontend/src/lib/types.ts` — `AlertRule`, `AlertRuleKind`, `AlertSeverity`, `AlertMetric` exportiert; `alert_rules?: AlertRule[]` im Trip-Interface. |
| `test_ac9_all_production_trips_load_with_additive_migration` | AC-9 | Iteriert alle JSONs in `data/users/*/trips/*.json` — jeder lädt erfolgreich, Roundtrip ist additiv (alle alten Felder bytegleich, nur `alert_rules` ist neu hinzugekommen). |

### Go (`internal/model/alert_rule_test.go`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `TestAlertRule_JSONRoundtrip` | AC-7 (Vorbedingung) | `json.Marshal(AlertRule{...})` produziert alle Felder; `json.Unmarshal` liefert identisches Struct. |
| `TestTrip_AlertRulesEmptySerializesAsArray` | AC-7 | `Trip{AlertRules: []AlertRule{}}` marshalled zu JSON, das `"alert_rules":[]` enthält (KEIN omitempty, kein `null`). |

## Implementation Details

Tests folgen No-Mocks-Pattern:
- Echte `AlertRule`-Dataclass, echte `Trip`-Konstruktion
- Echtes Filesystem-IO für AC-6/AC-9 (gegen `data/users/`)
- Keine `Mock()`, `patch()`, `MagicMock`

In RED-Phase liefern alle Tests `ImportError`/`AttributeError`/`AssertionError`,
weil weder `AlertRule` noch `_migrate_legacy_alert_rules` noch das
`alert_rules`-Feld existieren.

## Expected Behavior

- **Input:** Synthetische Trip-Dicts + die echten Produktiv-Trip-JSONs.
- **Output:** Assertions auf Dataclass-Felder, Listen, Strings.
- **Side effects:** AC-6 und AC-9 lesen Filesystem; keine Schreib-Operationen
  auf Produktivdaten (Test-Trips werden in tmp_path kopiert oder nur gelesen).

## Acceptance Criteria

- **AC-T1:** Given die Test-Datei `tests/tdd/test_alert_rules_model.py` existiert
  und die Implementierung fehlt /
  When `pytest tests/tdd/test_alert_rules_model.py -v` läuft /
  Then schlagen mindestens 6 von 8 Tests fehl (RED-Phase erfolgreich).
  AC-T2 darf je nach aktueller Trip-Dataclass schon grün sein.

- **AC-T2:** Given GREEN-Phase ist abgeschlossen /
  When derselbe pytest-Lauf plus `go test ./internal/model/` ausgeführt werden /
  Then sind alle 10 Tests grün (8 Python + 2 Go), keine Mocks.

## Known Limitations

- AC-7 wird via Go-Test geprüft, nicht via Python.
- AC-9 ist destructive-read-only: testet gegen die echten Trip-JSONs in
  `data/users/`, schreibt aber niemals zurück.

## Changelog

- 2026-05-14: Initial — Test-Manifest für Issue #205.
