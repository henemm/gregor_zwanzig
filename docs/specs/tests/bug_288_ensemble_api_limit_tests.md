---
entity_id: bug_288_ensemble_api_limit_tests
type: tests
created: 2026-05-20
updated: 2026-05-20
status: draft
version: "1.0"
tags: [tests, ensemble, api-limit, open-meteo, issue-288]
parent: bug_288_ensemble_api_limit
phase: phase5_tdd_red
---

# Bug #288 — Ensemble-API Limit (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für den Fix aus `docs/specs/modules/bug_288_ensemble_api_limit.md`.
Jeder pytest-Test mappt 1:1 auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/bug_288_ensemble_api_limit.md` v1.0

## Source

- **File:** `tests/tdd/test_bug_288_ensemble_api_limit.py` (NEU — Tests für
  enrich_ensemble-Flag-Propagation, _enrich_ensemble_for_trip-Methode,
  Backward-Compatibility und Edge-Cases)

## Test Inventory

### Python (`tests/tdd/test_bug_288_ensemble_api_limit.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_fetch_forecast_signature_has_enrich_ensemble` | AC-1 | `OpenMeteoProvider.fetch_forecast()` hat Parameter `enrich_ensemble` mit Default `True`. |
| `test_ac1_segment_weather_signature_has_enrich_ensemble` | AC-1 | `SegmentWeatherService.fetch_segment_weather()` hat Parameter `enrich_ensemble` mit Default `True`. |
| `test_ac1_fetch_segment_weather_accepts_enrich_ensemble_false` | AC-1 | Echte API: `fetch_segment_weather(segment, enrich_ensemble=False)` liefert Daten ohne Ensemble; alle `confidence_pct=None`. |
| `test_ac2_enrich_ensemble_for_trip_method_exists` | AC-2 | `TripReportSchedulerService` hat callable `_enrich_ensemble_for_trip`. |
| `test_ac2_enrich_uses_last_waypoint_of_last_stage` | AC-2 | `_enrich_ensemble_for_trip(trip, [])` läuft ohne Exception; greift auf `trip.stages[-1].last_waypoint` zu. |
| `test_ac2_single_stage_trip_no_index_error` | AC-2/AC-5 | Einetappiger Trip: `_enrich_ensemble_for_trip` liefert keinen `IndexError`. |
| `test_ac3_confidence_propagated_to_all_segments_after_enrichment` | AC-3 | Nach `_enrich_ensemble_for_trip()` hat `SegmentWeatherSummary.confidence_pct_min` einen Wert (nicht None). |
| `test_ac4_fetch_forecast_default_true_is_backward_compatible` | AC-4 | `fetch_forecast(enrich_ensemble=True)` auf echte API: kein TypeError, Ergebnis mit Daten. |
| `test_ac4_geosphere_accepts_enrich_ensemble_parameter` | AC-4 | `GeoSphereProvider.fetch_forecast()` hat `enrich_ensemble`-Parameter (wird ignoriert). |
| `test_ac5_single_stage_last_waypoint_resolves_correctly` | AC-5 | Einetappiger Trip: `trip.stages[-1].last_waypoint` == zweiter Waypoint; `_enrich_ensemble_for_trip` ohne Fehler. |

## Implementation Details

Tests folgen dem No-Mocks-Pattern des Projekts:
- Echte `Trip`/`Stage`/`Waypoint`-Dataclasses
- `TripReportSchedulerService` wird minimal via `__new__()` instanziiert
- Signatur-Tests via `inspect.signature()`
- API-Tests (AC-1, AC-4) machen echte OpenMeteo-Requests (kein Ensemble-API)
- Keine `Mock()`, `patch()`, `MagicMock`

In RED-Phase liefern alle Tests `TypeError` (fehlender Parameter) oder
`AttributeError` (`_enrich_ensemble_for_trip` existiert nicht).

## Expected Behavior

- **Input:** Minimale Trip/Stage/Segment-Objekte; echte OpenMeteo-Koordinaten (Innsbruck).
- **Output:** Boolean/Assertions über Signatur, Methoden-Existenz und Feld-Werte.
- **Side effects:** AC-1/AC-4 rufen die echte OpenMeteo-Haupt-API auf (kein Ensemble),
  kein Quota-Problem.

## Acceptance Criteria

- **AC-T1:** Given die Test-Datei existiert und Implementierung fehlt /
  When `pytest tests/tdd/test_bug_288_ensemble_api_limit.py -v` läuft /
  Then schlagen mindestens 8 von 10 Tests fehl (RED-Phase erfolgreich).

- **AC-T2:** Given GREEN-Phase abgeschlossen /
  When `pytest tests/tdd/test_bug_288_ensemble_api_limit.py -v` ausgeführt /
  Then alle 10 Tests grün, keine Mocks.

## Known Limitations

- AC-1-API-Test (`test_ac1_fetch_segment_weather_accepts_enrich_ensemble_false`) macht
  einen echten Wetter-API-Call — schlägt fehl wenn OpenMeteo nicht erreichbar.
- `test_ac2_enrich_uses_last_waypoint_of_last_stage` prüft nur kein-Exception,
  nicht ob der richtige API-Endpunkt aufgerufen wurde (kein Call-Counter).

## Changelog

- 2026-05-20: Initial — Test-Manifest für Bug #288 (Ensemble-API-Limit).
