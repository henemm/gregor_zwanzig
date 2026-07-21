---
entity_id: bug_401_segment_localtime_tests
type: tests
created: 2026-05-27
updated: 2026-05-27
status: draft
version: "2.0"
tags: [tests, timezone, scheduler, segment, alert, cest, utc, bug-400, bug-401]
parent: bug_401_segment_localtime
phase: phase5_tdd_red
---

# Bug #400 + #401 — Lokalzeit-Korrektur: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/bug_401_segment_localtime.md` (kombiniert #400 + #401).
Jeder pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/bug_401_segment_localtime.md` v1.1

Source-Inspection-Ansatz (kein Mock): `trip_alert.py` und `trip_report_scheduler.py` haben
viele Deps (SMTP, Provider). Geprüft wird der relevante Quelltext + eine echte CEST→UTC-Konvertierung.

## Source

- **File:** `tests/tdd/test_bug_400_alert_tz.py` (NEU) — Bug #400
- **File:** `tests/tdd/test_bug_401_segment_localtime.py` (NEU) — Bug #401

## Test Inventory

### Bug #400 — Alert-Mail Zeitzone (`tests/tdd/test_bug_400_alert_tz.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `alert_imports_tz_for_coords` | AC-1 | `trip_alert.py` importiert `tz_for_coords` |
| `alert_passes_tz_to_format_email` | AC-2 | `format_email()`-Aufruf in `trip_alert.py` übergibt `tz=` |

### Bug #401 — Segment-Startzeiten Lokalzeit→UTC (`tests/tdd/test_bug_401_segment_localtime.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `segment_start_time_is_true_utc_for_cest_location` | AC-4 | `_convert_trip_to_segments` gibt UTC 06:00 zurück (nicht 08:00) für CEST 08:00-Eingabe |
| `segment_header_shows_configured_local_departure_time` | AC-4 | `render_plain`-Header zeigt "08:00" nach korrekter UTC-Konvertierung |
| `hourly_filter_selects_cest_correct_window` | AC-4 | `_extract_hourly_rows` selektiert UTC 6–8 (= CEST 8–10), nicht UTC 8–10 |
| `utc_location_segment_unchanged` | AC-4 | UTC-Tour (Reykjavik): `start_time.hour = 8` — keine Regression |

## Test-Ausführung

```bash
# RED-Phase (vor Implementation — Source-Inspection-Tests sollen FAIL)
uv run pytest tests/tdd/test_bug_400_alert_tz.py tests/tdd/test_bug_401_segment_localtime.py -v

# GREEN-Phase (nach Implementation)
uv run pytest tests/tdd/test_bug_400_alert_tz.py tests/tdd/test_bug_401_segment_localtime.py -v
```

## Changelog

- 2026-05-27: Initial test manifest erstellt für Bug #401 (_convert_trip_to_segments Lokalzeit→UTC).
- 2026-05-27: v2.0 — auf kombinierten Workflow `bug-400-401-timezone-localtime` erweitert; Test-Namen an
  tatsächliche Source-Inspection-Tests (test_bug_400_alert_tz.py + test_bug_401_segment_localtime.py) angeglichen.
