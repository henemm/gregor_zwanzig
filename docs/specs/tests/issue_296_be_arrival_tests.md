---
entity_id: issue_296_be_arrival_tests
type: tests
created: 2026-05-23
updated: 2026-05-23
status: draft
version: "1.0"
tags: [tests, backend, naismith, arrival-times, trip, waypoint, issue-296]
parent: issue_296_be_naismith_arrival
phase: phase5_tdd_red
---

# Issue #296-BE — Naismith-Ankunftszeiten (Test-Manifest)

## Approval

- [x] Approved

## Purpose

Test-Manifest fuer die Naismith-Ankunftszeiten aus
`docs/specs/modules/issue_296_be_naismith_arrival.md`. Jeder Test mappt 1:1 auf
ein Acceptance Criterion der Parent-Spec. Go-Tests pruefen Formel + Berechnung +
JSON-Marshalling + Roundtrip; Python-Tests pruefen Loader-Persistenz und
Scheduler-Konsum.

Parent-Spec: `docs/specs/modules/issue_296_be_naismith_arrival.md` v1.0

## Source

- **File (Go):** `internal/model/naismith_test.go` (NEU)
- **File (Go):** `internal/model/waypoint_arrival_marshal_test.go` (NEU)
- **File (Go):** `internal/store/trip_arrival_roundtrip_test.go` (NEU)
- **File (Python):** `tests/tdd/test_issue_296_be_arrival.py` (NEU)

## Test Inventory

### Go (`internal/model/naismith_test.go`)

| Test-Funktion | AC | Was geprueft wird |
|---|---|---|
| `TestNaismithHours` | AC-3/AC-6 | `naismithHours` = SUMME (dist/4 + ascent/300 + descent/500), nicht max(). |
| `TestComputeStageArrivals_Flat` | AC-1 | Stage 08:00, 2 Wegpunkte 4 km flach → wp[1] == "09:00". |
| `TestComputeStageArrivals_DefaultStart` | AC-2 | Stage ohne start_time → wp[0] == "08:00". |
| `TestComputeStageArrivals_Ascent` | AC-3 | +300 m, ~0 km → Inkrement 1 h (Hoehenterm). |
| `TestComputeStageArrivals_Pause` | AC-7 | 0 Wegpunkte → kein Panic, keine Arrival. |
| `TestComputeStageArrivals_Monotonic` | AC-8 | 3 Wegpunkte → streng monoton steigend, Format "HH:MM". |
| `TestFormatHHMM_ClampsOverflow` | F001 | Kumulierte Zeit >= 24 h → `arrival_calculated` auf "23:59" geclamped (Stunden-Teil <= 23), damit Python `_parse_hhmm` den Wert konsumieren kann. |
| `TestParseStartMinutes_RejectsNonsense` | F002 | start_time "99:99" (Stunde >23 / Minute >59) → Fallback auf Default "08:00". |

### Go (`internal/model/waypoint_arrival_marshal_test.go`)

| Test-Funktion | AC | Was geprueft wird |
|---|---|---|
| `TestWaypointJSON_HasArrivalNotOriginConfirmed` | AC-6 | `arrival_calculated` im JSON; KEINE Felder `origin`/`confirmed`. |
| `TestWaypointJSON_ArrivalOmitEmpty` | AC-6 | Leeres Feld wird nicht serialisiert (omitempty). |

### Go (`internal/store/trip_arrival_roundtrip_test.go`)

| Test-Funktion | AC | Was geprueft wird |
|---|---|---|
| `TestTripRoundTrip_PreservesFieldsWithoutArrival` | AC-4 | Legacy-JSON ohne Feld → LoadTrip → SaveTrip → LoadTrip ohne Datenverlust; persistierter Wert bleibt erhalten. |

### Python (`tests/tdd/test_issue_296_be_arrival.py`)

| Test-Funktion | AC | Was geprueft wird |
|---|---|---|
| `test_loader_preserves_arrival_calculated` | AC-4 | Fixture MIT `arrival_calculated` → geladener Waypoint traegt den Wert. |
| `test_loader_handles_missing_arrival_calculated` | AC-4 | Fixture OHNE Feld → kein Fehler, `arrival_calculated is None`. |
| `test_scheduler_prefers_persisted_arrival` | AC-5 | Trip mit persistiertem Wert → Segment-Endzeit stammt aus `arrival_calculated`, nicht aus `_interpolate_arrival_time`. |

## Implementation Details

Tests folgen dem No-Mocks-Pattern des Projekts:
- Go: echte Structs, echte Store-Roundtrips ueber temporaere JSON-Dateien (`t.TempDir`).
- Python: echte Trip-JSON-Fixtures auf `tmp_path`, echtes `load_trip`, echte
  `TripReportScheduler`-Instanz.
- Keine `Mock()`, `patch()`, `MagicMock`.

In RED-Phase schlagen alle Tests fehl, weil `naismithHours`,
`ComputeStageArrivals` und `Waypoint.ArrivalCalculated` (Go) bzw.
`Waypoint.arrival_calculated` + Loader-/Scheduler-Konsum (Python) noch nicht
existieren.

## Expected Behavior

- **Input:** Echte lat/lon (0.036° ≈ 4 km), Stage/Waypoint-Objekte, JSON-Fixtures.
- **Output:** Assertions ueber `arrival_calculated`-Werte, JSON-Felder,
  Roundtrip-Erhalt und Segment-Endzeit.
- **Side effects:** Schreibvorgaenge ausschliesslich in `t.TempDir`/`tmp_path`.

## Acceptance Criteria

- **AC-T1:** Given die Test-Dateien existieren und Implementierung fehlt /
  When `go test ./internal/model/ ./internal/store/` und
  `pytest tests/tdd/test_issue_296_be_arrival.py -v` laufen /
  Then schlagen alle Tests fehl (RED-Phase erfolgreich).

- **AC-T2:** Given GREEN-Phase abgeschlossen /
  When dieselben Test-Suiten ausgefuehrt werden /
  Then sind alle Tests gruen, keine Mocks.

## Known Limitations

- Mehrtages-Etappen (>24 h) sind out of scope (Etappen sind Tagesabschnitte).
- Distanz aus Haversine (lat/lon), nicht aus echter GPX-Spur — konsistent mit
  bestehender Pipeline-Schaetzung.

## Changelog

- 2026-05-23: Initial — Test-Manifest fuer Issue #296-BE (Naismith-Ankunftszeiten).
- 2026-05-23: Adversary-Hardening F001/F002 — `TestFormatHHMM_ClampsOverflow` (Clamp >=24h auf "23:59") + `TestParseStartMinutes_RejectsNonsense` (Unsinns-Startzeit → Default 08:00) ergaenzt.
