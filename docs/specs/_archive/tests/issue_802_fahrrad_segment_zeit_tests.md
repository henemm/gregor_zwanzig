---
entity_id: issue_802_fahrrad_segment_zeit_tests
type: tests
created: 2026-06-14
updated: 2026-06-14
version: "2.0"
tags: [tests, python, go, naismith, cycling, persistence, migration, scheduler, issue-802]
parent: issue_802_fahrrad_segment_zeit
phase: phase5_tdd_red
---

# Issue #802 — Ankunftszeiten konsolidieren (Tests v2.0)

## Approval

- [x] Approved

## Purpose

Test-Manifest für den Umbau auf **derive-on-write** aus
`docs/specs/modules/issue_802_fahrrad_segment_zeit.md` v2.0. Mock-frei: echte
`compute_stage_arrivals`, echter `save_trip`-Roundtrip auf Disk (tmp), echter Scheduler,
echte Backfill-Migration. Cross-Language-Konsistenz (AC-3) wird über einen **fixen
Wertekontrakt** geprüft, den Python- UND Go-Test gegen dieselben erwarteten Strings asserten.

Parent-Spec: `docs/specs/modules/issue_802_fahrrad_segment_zeit.md` v2.0

## Source

- **Python:** `tests/tdd/test_issue_802_fahrrad_segment_zeit.py` —
  `src/core/naismith.compute_stage_arrivals`, `loader.save_trip`, Scheduler-Reader,
  `scripts/backfill_arrival_calculated_802.py`.
- **Go:** `internal/model/naismith_802_test.go` + `internal/store/store_802_test.go` —
  Konsistenz gegen denselben Wertekontrakt + Compute-on-Save in `store.SaveTrip`.
  (Go-Tests unterliegen nicht dem Python-spec_enforcement.)

## Fixer Wertekontrakt (AC-3, beide Sprachen, haversine-unabhängig: gleiche lat/lon)

Start `08:00`, alle Wegpunkte lat=47.0 lon=11.0 (Distanz=0 → nur Höhe zählt):

| Fixture | activity | Höhen (m) | Erwartete arrival_calculated |
|---|---|---|---|
| A | fahrrad_20 | 500,1100,1100,500 | 08:00, 09:00, 09:00, 09:36 |
| B (Rundung) | fahrrad_20 | 500,505 | 08:00, 08:01 |
| C (Clamp) | fahrrad_20 | 500,10500 | 08:00, 23:59 |
| W (Wanderer) | "" | 500,800,300 | 08:00, 09:00, 10:00 |

## Test Inventory (Python)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `ac1_save_trip_populates_arrival_calculated` | AC-1 | `save_trip` auf Disk → jeder Wegpunkt trägt danach arrival_calculated. |
| `ac1_pause_stage_gets_no_arrival` | AC-1 | Etappe mit <2/0 Wegpunkten → kein arrival_calculated, kein Crash. |
| `ac2_fahrrad20_flat_arrives_around_nine` | AC-2 | fahrrad_20, ~20 km flach → 2. Wegpunkt ~09:00 (nicht ~13:00). |
| `ac3_python_naismith_matches_fixed_contract` | AC-3 | `compute_stage_arrivals` == fixer Kontrakt A/B/C/W (Python-Seite). |
| `ac4_wanderer_default_naismith_sum` | AC-4 | activity="" → Wanderer-SUM, Kontrakt W. |
| `ac5_backfill_populates_and_preserves` | AC-5 | Backfill befüllt Bestandstrip; Counts + time_window/override unberührt. |
| `ac6_scheduler_reads_persisted_arrival` | AC-6 | Scheduler nutzt persistierte arrival_calculated für Segmentzeiten. |
| `ac6_scheduler_interpolation_removed` | AC-6 | `_interpolate_arrival_time`/`_activity_speeds` nicht mehr importierbar. |
| `ac7_save_idempotent_preserves_override` | AC-7 | 2× save → identische Werte; arrival_override/time_window überleben. |
| `ac8_degenerate_waypoint_no_crash_no_hiking` | AC-8 | Wegpunkt ohne Zeitdaten → kein Crash, kein Wandertempo-Default. |

## Acceptance Criteria (Test-Meta)

- **AC-T1:** RED — `compute_stage_arrivals` (src/core/naismith) und der Backfill-Script
  existieren nicht → ImportError; `ac6_scheduler_interpolation_removed` rot, weil das Symbol
  noch existiert.
- **AC-T2:** GREEN — alle Python-Tests grün; Go-Konsistenztest grün gegen denselben Kontrakt;
  keine Regression in scheduler/loader/trip/store/naismith-Suiten.

## Changelog

- 2.0 (2026-06-14): Umbau derive-on-write (Compute-on-Save, Backfill, Reader, Cross-Lang-Kontrakt).
- 1.0 (2026-06-14): Python-Interpolations-Fix (verworfen).
