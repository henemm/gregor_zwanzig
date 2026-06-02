---
entity_id: bug_557_confidence_pct_min_tests
type: tests
created: 2026-06-02
updated: 2026-06-02
status: draft
version: "1.0"
tags: [tests, ensemble, confidence, apply-ensemble-spreads, issue-557]
parent: bug_557_confidence_pct_min
phase: phase5_tdd_red
---

# Bug #557 — confidence_pct_min nicht gesetzt (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für den Fix aus `docs/specs/modules/bug_557_confidence_pct_min.md`.
Jeder pytest-Test mappt 1:1 auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/bug_557_confidence_pct_min.md` v1.0

## Source

- **File:** `tests/tdd/test_bug_557_apply_ensemble_spreads.py` (NEU — Tests für
  die neue `_apply_ensemble_spreads()`-Methode und deren Fähigkeit,
  `confidence_pct_min` ohne Netzwerkzugriff korrekt zu setzen)

## Test Inventory

### Python (`tests/tdd/test_bug_557_apply_ensemble_spreads.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_apply_ensemble_spreads_sets_confidence_when_timeseries_none` | AC-1 | `_apply_ensemble_spreads()` setzt `confidence_pct_min` wenn `timeseries=None` und Spreads das Segment-Fenster abdecken. |
| `test_ac1_apply_ensemble_spreads_exact_value_matches_compute_confidence` | AC-1 | `confidence_pct_min` entspricht dem Ergebnis von `compute_confidence_pct()` für den Spread-Eintrag. |
| `test_ac2_apply_ensemble_spreads_uses_minimum_across_datapoints` | AC-2 | `confidence_pct_min` ist das Minimum über alle DataPoint-Konfidenzwerte wenn `timeseries` vorhanden. |
| `test_ac3_former_xfail_now_passes_via_apply_ensemble_spreads` | AC-3 | Vorheriger xfail-Test (AC-3 aus Bug #288) läuft grün über `_apply_ensemble_spreads()`. |
| `test_ac4_spreads_outside_segment_window_are_ignored` | AC-4 | Spreads außerhalb des Segment-Zeitfensters werden ignoriert; `confidence_pct_min` bleibt None. |

## Implementation Details

Tests folgen dem No-Mocks-Pattern des Projekts:
- Echte `Trip`/`Stage`/`Segment`/`SegmentWeatherData`-Dataclasses
- `TripReportSchedulerService` wird minimal via `__new__()` instanziiert
- Spread-Daten als echtes `Dict[datetime, Tuple[float, float]]` konstruiert
- `compute_confidence_pct` aus `providers.openmeteo` — reine Funktion, kein HTTP
- Keine `Mock()`, `patch()`, `MagicMock`

In RED-Phase liefern alle Tests `AttributeError: '_apply_ensemble_spreads' not found`.

## Expected Behavior

- **Input:** Minimale Segment-Objekte; Hand-konstruierte Spread-Dicts mit naiven UTC-Datetimes.
- **Output:** Assertions über `weather_item.aggregated.confidence_pct_min`.
- **Side effects:** Keine — kein Netzwerkzugriff, kein Dateisystem.

## Acceptance Criteria

- **AC-T1:** Given die Test-Datei existiert und Implementierung fehlt /
  When `pytest tests/tdd/test_bug_557_apply_ensemble_spreads.py -v` läuft /
  Then schlagen alle 5 Tests fehl mit `AttributeError` (RED-Phase erfolgreich).

- **AC-T2:** Given GREEN-Phase abgeschlossen /
  When `pytest tests/tdd/test_bug_557_apply_ensemble_spreads.py -v` ausgeführt /
  Then alle 5 Tests grün, keine Mocks.

## Changelog

- 2026-06-02: Initial — Test-Manifest für Bug #557 (_apply_ensemble_spreads Extraktion).
