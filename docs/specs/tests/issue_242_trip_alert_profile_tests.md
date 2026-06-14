---
entity_id: issue_242_trip_alert_profile_tests
type: tests
created: 2026-05-17
updated: 2026-05-17
status: draft
version: "1.0"
tags: [tests, email, activity-profile, trip-alert, issue-242]
parent: issue_242_trip_alert_profile
phase: phase5_tdd_red
---

# Issue #242 — Trip-Alert-Mail: ActivityProfile durchreichen (Test-Manifest)

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_242_trip_alert_profile.md`. Jeder
pytest-Test mappt 1:1 auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/issue_242_trip_alert_profile.md` v1.0.0

## Source

- **File:** `tests/tdd/test_trip_alert_profile.py` (NEU)

## Test Inventory (`tests/tdd/test_trip_alert_profile.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_trip_alert_passes_profile_to_formatter` | AC-1 | Source-Inspection: `src/services/trip_alert.py` enthält `profile=trip.aggregation.profile` im `format_email`-Call (Substring-Check, keine Mocks) — superseded by Issue #816 Slice 1 (s. unten) |
| `test_ac1_trip_alert_uses_compact_renderer_not_format_email` | AC-1-816 | Issue #816 Slice 1: `_send_alert` nutzt `render_deviation_alert` statt `format_email`/profile. Beweist knappen Alert-Render-Pfad (Baustein D). |
| `test_ac2_trip_alert_render_with_wintersport_profile` | AC-2 | `TripReportFormatter().format_email(report_type="alert", profile=WINTERSPORT, changes=[...])` → `report.email_html` enthält `#4a7fb5` und `Wintersport` |
| `test_ac2_trip_alert_render_with_wandern_profile` | AC-2 | Analog für `WANDERN` → `report.email_html` enthält `#3a7d44` und `Wandern` |

AC-3 (keine Regression in den 52 bestehenden Tests) wird durch parallelen
Lauf der drei bestehenden Suiten verifiziert, nicht durch einen eigenen Test.

## Test-Ausführung

```bash
uv run pytest tests/tdd/test_trip_alert_profile.py -v
uv run pytest tests/tdd/test_email_profile_pipeline.py tests/tdd/test_email_design_tokens.py tests/unit/test_renderers_email.py -v
```

## Erwartetes RED-Verhalten (vor Implementation)

- AC-1: Substring `"profile=trip.aggregation.profile"` fehlt in `trip_alert.py` → `AssertionError`
- AC-2: `format_email`-Call ohne `profile`-kwarg → Render geht auf ALLGEMEIN, Hex `#4a7fb5` fehlt im HTML → `AssertionError`

## Erwartetes GREEN-Verhalten (nach Implementation)

Alle 3 Tests grün, bestehende 52 Tests ebenfalls grün.

## Changelog

- 2026-05-17: Test-Manifest für #242 (Sub-Issue 4 von Epic #236)
