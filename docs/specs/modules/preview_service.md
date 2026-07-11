---
entity_id: preview_service
type: module
created: 2026-05-11
updated: 2026-07-11
status: approved
version: "1.0"
tags: [backend, preview, epic-140]
---

<!-- Sub-Spec des Epic #140 — siehe docs/specs/modules/epic_140_output_vorschau.md -->

# PreviewService

## Approval

- [x] Approved (Sub-Spec, deckt sich mit Master-Spec `epic_140_output_vorschau.md`)

## Purpose

Backend-Service, der Email-HTML und SMS-Token-Zeile als Vorschau erzeugt — ohne tatsächlichen Versand. Wiederverwendet die existierende Trip-Report-Pipeline (`TripReportSchedulerService` für Trip→Segments→Wetter, `TripReportFormatter.format_email()` für den Render).

Detail-Spec: `docs/specs/modules/epic_140_output_vorschau.md` (Master).

## Source

- **File:** `src/services/preview_service.py`
- **Identifier:** `class PreviewService`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.config.Settings` | bestehend | User-Profil-Routing |
| `app.loader.load_trip` / `get_trips_dir` | bestehend | Trip-File laden |
| `services.trip_report_scheduler.TripReportSchedulerService` | bestehend | Pipeline-Helper (Segments, Wetter) |
| `formatters.trip_report.TripReportFormatter` | bestehend | Email-Render |

## Implementation Details

```python
class PreviewService:
    def __init__(self, settings: Settings | None = None): ...
    def _load_trip(self, trip_id: str, user_id: str = "default") -> Trip: ...
    def _resolve_target_date(self, trip: Trip, given_date: str | None) -> date: ...
        # Seit Issue #990: Auto-Resolve (given_date leer) überspringt Stages
        # mit < 2 Wegpunkten und wählt die nächste renderbare Stage
        # (Zukunfts-Suche, sonst Fallback auf erste renderbare Stage überhaupt).
    def _build_report(self, trip: Trip, target: date, report_type: str) -> TripReport: ...
    def render_email_preview(self, trip_id, *, user_id, report_type, target_date) -> str: ...
    def render_sms_preview(self, trip_id, *, user_id, report_type, target_date) -> tuple[str, str]: ...
```

## Acceptance Criteria

- **AC-1:** Given gültiger Trip + Stage am Zieldatum / When `render_email_preview` läuft / Then liefert es das `email_html` aus `TripReportFormatter.format_email()`
- **AC-2:** Given Trip-ID nicht in `data/users/<user>/trips/` / When der Service aufgerufen wird / Then `FileNotFoundError`
- **AC-3:** Given Trip ohne Stage am Zieldatum / When der Service aufgerufen wird / Then `LookupError` mit "Keine Stage am ..." Meldung. Abgrenzung (Issue #990): existiert am Zieldatum eine Stage, hat sie aber weniger als 2 Wegpunkte, wirft der Service ebenfalls `LookupError`, jedoch mit einem Text, der das Wort „waypoints" enthält — dieser Fall ist von „keine Stage am Datum" zu unterscheiden. Details: `docs/specs/modules/fix_990_preview_empty_waypoints.md`.
- **AC-4:** Given Wetter-Provider liefert keine Daten (Rate-Limit etc.) / When der Service aufgerufen wird / Then `RuntimeError`
- **AC-5:** Given `report_type` weder "morning" noch "evening" / When der Service aufgerufen wird / Then `ValueError`

## Expected Behavior

- **Input:** trip_id, user_id, report_type, optional target_date (ISO)
- **Output:** Email-HTML-String **oder** Tupel `(subject, token_line)` für SMS
- **Side effects:** Keine — kein Versand, kein Logbuch-Eintrag, nur Wetter-Cache-Fetch über bestehende Pipeline

## Known Limitations

- SMS-Token-Pipeline ist implementiert (Issue #188).
- Wetter-Provider-Calls bei jeder Vorschau — Caching erfolgt über bestehende Service-Schicht.

## Changelog

- 2026-07-11: AC-3 präzisiert (Issue #990: Unterscheidung „keine Stage am Datum" vs. „Stage mit zu wenig Wegpunkten"), Implementation-Details um `_resolve_target_date`-Verhalten ergänzt
- 2026-05-11: Initial sub-spec für Epic #140, Implementation Phase 6
