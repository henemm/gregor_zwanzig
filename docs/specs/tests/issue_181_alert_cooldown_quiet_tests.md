---
entity_id: issue_181_alert_cooldown_quiet_tests
type: tests
created: 2026-05-18
updated: 2026-05-18
status: draft
version: "1.0"
tags: [tests, alerts, cooldown, quiet-hours, issue-181, epic-139]
parent: issue_181_alert_cooldown_quiet_hours
phase: phase5_tdd_red
---

# Issue #181 — Alert Cooldown + Stille Stunden (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für die Implementierung aus
`docs/specs/modules/issue_181_alert_cooldown_quiet_hours.md`. Jeder pytest-Test
mappt 1:1 auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/issue_181_alert_cooldown_quiet_hours.md` v1.0

## Source

- **File:** `tests/tdd/test_alert_cooldown_quiet.py` (NEU — Python-Tests für
  Cooldown-Auflösung, Quiet-Hours-Logik mit Mitternacht-Wrap, Loader-Roundtrip)

## Test Inventory

Test-Funktionsnamen führen den AC-Index, damit der Spec-Enforcement-Hook
sie auflösen kann.

### Python (`tests/tdd/test_alert_cooldown_quiet.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_no_cooldown_field_uses_global_default` | AC-1 | `Trip(...)` ohne `alert_cooldown_minutes` hat das Feld als `None` (kein AttributeError). |
| `test_ac2_cooldown_60_throttles_after_30_min` | AC-2 | `_is_throttled_with_cooldown(trip)` mit `alert_cooldown_minutes=60` und letztem Alert vor 30 Min → True. |
| `test_ac3_cooldown_zero_skips_throttle` | AC-3 | `_is_throttled_with_cooldown(trip)` mit `alert_cooldown_minutes=0` → False (kein Limit). |
| `test_ac4_quiet_hours_midnight_wrap_active` | AC-4 | `_is_quiet_hours(trip, now)` mit `22:00–07:00` und `now=23:30` → True. |
| `test_ac5_quiet_hours_midnight_wrap_ended` | AC-5 | `_is_quiet_hours(trip, now)` mit `22:00–07:00` und `now=07:01` → False. |
| `test_ac6_quiet_hours_normal_window_active` | AC-6 | `_is_quiet_hours(trip, now)` mit `08:00–22:00` und `now=15:00` → True. |
| `test_ac7_loader_roundtrip_cooldown_minutes` | AC-7 | `_trip_to_dict()` → JSON → `load_trip()`: `alert_cooldown_minutes=45`, `alert_quiet_from="22:00"`, `alert_quiet_to="07:00"` sind nach Roundtrip identisch. |
| `test_ac8_legacy_trip_without_cooldown_loads_as_none` | AC-8 | Trip-JSON ohne neue Felder lädt ohne Crash; alle drei neuen Felder sind `None`. |
| `test_boundary_quiet_hours_exact_to_time_not_suppressed` | Grenzwert | `_is_quiet_hours()` mit `22:00–07:00` und `now=07:00` exakt → False (`< to`, nicht `<=`). |
| `test_no_quiet_hours_setting_returns_false` | AC-1 (Seitenfall) | `_is_quiet_hours()` ohne `alert_quiet_from/to` → False, kein Fehler. |
| `test_half_config_quiet_hours_returns_false` | Known Limitation | Nur `alert_quiet_from` gesetzt, kein `alert_quiet_to` → `_is_quiet_hours()` = False (Halbkonfiguration ignoriert). |

## Implementation Details

Tests folgen No-Mocks-Pattern:
- Echte `Trip`-Dataclass (nach Erweiterung)
- `TripAlertService` wird minimal instanziiert (nur `_throttle_hours` + `_last_alert_times`)
- `_is_quiet_hours()` und `_is_throttled_with_cooldown()` werden direkt aufgerufen
- Filesystem-IO nur bei AC-7 und AC-8 (tmp_path via pytest)
- Keine `Mock()`, `patch()`, `MagicMock` für Kern-Logik

In RED-Phase liefern alle Tests `AttributeError` oder `ImportError`,
weil `trip.alert_cooldown_minutes`, `_is_quiet_hours()` und
`_is_throttled_with_cooldown()` noch nicht existieren.

## Expected Behavior

- **Input:** `Trip`-Objekte mit verschiedenen Cooldown/QuietHours-Konfigurationen,
  `datetime`-Objekte für "jetzt".
- **Output:** Boolean-Assertions (`True`/`False`) für Throttle- und QuietHours-Checks.
- **Side effects:** AC-7/AC-8 lesen/schreiben in `tmp_path` (pytest fixture), keine
  Produktivdaten berührt.

## Acceptance Criteria

- **AC-T1:** Given die Test-Datei `tests/tdd/test_alert_cooldown_quiet.py` existiert
  und die Implementierung fehlt /
  When `pytest tests/tdd/test_alert_cooldown_quiet.py -v` läuft /
  Then schlagen mindestens 8 von 11 Tests fehl (RED-Phase erfolgreich).

- **AC-T2:** Given GREEN-Phase ist abgeschlossen /
  When `pytest tests/tdd/test_alert_cooldown_quiet.py -v` ausgeführt wird /
  Then sind alle 11 Tests grün, keine Mocks.

## Known Limitations

- `_is_throttled_with_cooldown()` ist eine neue Hilfsmethode — falls die
  Implementierung das Cooldown-Handling anders benennt, müssen AC-2/AC-3 angepasst werden.
- Tests prüfen UTC-Zeit. Die Zeitzone-Frage (UTC vs. Lokalzeit) ist Implementierungsdetail.

## Changelog

- 2026-05-18: Initial — Test-Manifest für Issue #181 (Cooldown + Stille Stunden).
