---
entity_id: issue_667_snapshot_hourly_clip_fix_tests
type: tests
created: 2026-06-08
updated: 2026-06-08
status: draft
version: "1.0"
tags: [weather-snapshot, drilldown, persistence, bugfix, tdd]
---

# Tests — #667 Snapshot-Stundenreihe nicht aufs Etappenfenster beschneiden

## Approval

- [x] Approved (PO 'go' 2026-06-08)

## Purpose

TDD-Test-Inventar für die Entfernung des Stunden-Clips in
`weather_snapshot.py::_serialize_segment`. Modul-Spec:
`docs/specs/modules/issue_667_snapshot_hourly_clip_fix.md`.

Alle Tests beweisen Nutzerverhalten über **echte Datei-I/O** (Snapshot speichern via
`WeatherSnapshotService`, neu laden, Telegram-`process()`) — **keine** Mocks, keine
Dateiinhalt-Checks auf Quellcode. Entscheidend: das Segment-Reisefenster ist
**realistisch schmal** (4 h), die `timeseries` aber 12 h breit — so beißt der Clip
nachweisbar (Gegenmuster zum #654-Test mit künstlich 11h-breitem Segment).

## Test-Funktionen (Datei: `tests/tdd/test_issue_667_snapshot_hourly_clip_fix.py`)

| Test-Funktion | AC | Beweist |
|---------------|----|---------|
| `test_ac1_full_hourly_persisted_despite_narrow_segment` | AC-1 | Segment 4 h, timeseries 12 h → gespeicherter+neu geladener Snapshot enthält ≥12 Stundenpunkte (vor Fix nur ~4 → rot). |
| `test_ac2_drilldown_exceeds_segment_window` | AC-2 | `/hg` (bzw. `dd_thunder_today`) liefert deutlich mehr als die ~4 Etappen-`🕐`-Zeilen (bis 12 h) — der Nutzer sieht die volle Vorschau. |
| `test_ac3_aggregated_unchanged_after_roundtrip` | AC-3 | `aggregated`-Summary des Segments ist nach Speichern/Laden identisch zur Vor-Persistenz-Aggregation (Clip betraf nie `aggregated`). |
| `test_ac4_old_clipped_snapshot_still_loads` | AC-4 | Ein manuell schmal (geclippt) geschriebener Snapshot lädt nach dem Fix fehlerfrei ohne Exception. |

## Acceptance Criteria (Verweis)

Siehe Modul-Spec AC-1…AC-4. Dieser Test-Spec dient der `spec_enforcement`-Registrierung
der obigen Test-Entitäten und ist mit der Modul-Spec freizugeben.
