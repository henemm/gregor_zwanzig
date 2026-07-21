---
entity_id: issue_802_fahrrad_segment_zeit
type: module
created: 2026-06-14
updated: 2026-06-14
status: draft
version: "2.0"
parent_issue: 802
issues: [802]
tags: [python, go, naismith, activity-type, cycling, arrival-times, scheduler, persistence, migration]
---

# Issue #802 — Ankunftszeiten konsolidieren: Compute-on-Save + Scheduler als reiner Leser

## Approval

- [x] Approved

## Purpose

Fahrrad-Trips (`activity="fahrrad_NN"`) bekommen falsche Segment-Zeitfenster, weil der
Python-Scheduler die Ankunftszeiten **bei jedem Briefing-Lauf live** mit fester
Wandergeschwindigkeit (4 km/h) interpoliert. Ursache ist eine **derive-on-read**-Architektur:
Das persistierte Feld `arrival_calculated` ist in den Bestandsdaten leer (gr221: 0 von 16
Wegpunkten), Go berechnet es nur beim Edit, und der Scheduler rechnet daher selbst nach —
mit hartkodiertem Wandertempo.

Diese Spec stellt auf **derive-on-write** um: Ankunftszeiten werden an **jeder**
Speicher-Stelle einmal berechnet und persistiert (Go `store.SaveTrip` UND Python
`save_trip`), die Bestandsdaten werden per Migration nachgezogen, und **alle Lesepfade
(Scheduler) werden reine Leser** ohne eigene Zeitberechnung. Bike-Korrektheit kommt damit
automatisch aus dem persistierten Wert (Go-Logik #674).

**PO-Entscheidung (2026-06-14):** Vollumbau bewusst gewählt — trotz des Befunds, dass zwei
unabhängige Backends (Go-Web-API + Python-Services) Trips schreiben und der Umbau die Zahl
der Naismith-Implementierungen nicht senkt, sondern die Python-Berechnung vom Lese- auf den
Schreibzeitpunkt verschiebt.

## Architektur

```
SCHREIBEN (derive-on-write):
  Go:     jeder Trip-Write → store.SaveTrip → ComputeStageArrivals(ActivitySpeed(trip.Activity))
  Python: jeder Trip-Write → save_trip → compute_stage_arrivals(stage, trip.activity)
                                          (bit-genauer Spiegel von Go)
LESEN (pure reader):
  Scheduler liest arrival_calculated. KEINE eigene Zeitberechnung mehr.
BESTAND:
  Backfill-Migration re-saved alle Trips → arrival_calculated wird befüllt.
```

## Source

**Schicht: Go-API + Python-Backend (gemischt) + Datenmigration**

- `internal/store/store.go` — `SaveTrip`: vor `MarshalIndent` für jede Stage
  `ComputeStageArrivals(&trip.Stages[i], ActivitySpeed(trip.Activity))` aufrufen
  (zentrale Compute-on-Save-Stelle für alle Go-Schreiber).
- `internal/handler/trip.go` — die nun **redundanten** expliziten `ComputeStageArrivals`-
  Aufrufe in `UpdateTripHandler` (Z.232, Z.384) entfernen (Logik lebt jetzt in SaveTrip).
- `src/core/naismith.py` (NEU) — Python-Spiegel von `internal/model/naismith.go`:
  `activity_speeds(activity)`, `compute_stage_arrivals(stage, activity)` mit
  SUM-Naismith, `_format_hhmm` (Clamp 23:59), Haversine (R=6371.0088). **Bit-genau** zu Go.
- `src/app/trip.py` — `Trip.activity: str = ""` (Python muss die Aktivität zum Rechnen kennen).
- `src/app/loader.py` — `_parse_trip` liest `activity`; `_trip_to_dict` serialisiert es;
  `save_trip` ruft `compute_stage_arrivals` für jede Stage vor der Serialisierung.
- `src/services/trip_report_scheduler.py` — `_interpolate_arrival_time` ENTFERNEN; die
  Interpolations-Zweige in `_convert_trip_to_segments` durch ein sicheres Degenerat ersetzen
  (kein Wandertempo-Default mehr).
- `scripts/backfill_arrival_calculated_802.py` (NEU) — Einmal-Migration: alle Trips aller
  Nutzer laden und über `save_trip` neu schreiben (befüllt `arrival_calculated`).

**Single Source of Behavior (Naismith):** `internal/model/naismith.go` — Python spiegelt,
ändert Go nicht. ActivitySpeed: `fahrrad_15/20/25` → 15/20/25 km/h + 600/1000 Hm/h;
sonst Wanderer 4/300/500. naismithHours = SUMME. formatHHMM clamped auf "23:59".

## Estimated Scope

- **LoC:** ~220 (Go ~15, Python neu ~90, loader/trip ~15, scheduler ~−30, Migration ~50, Tests ~80) — LoC-Override nötig.
- **Files:** 7 (Quellcode) + Tests (Go + Python)
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/store/store.go` `SaveTrip` | file (edit) | Zentrale Compute-on-Save-Stelle (alle Go-Writer) |
| `internal/model/naismith.go` `ComputeStageArrivals`/`ActivitySpeed` | reference | Go-Quelle, unverändert; Python spiegelt |
| `internal/handler/trip.go` `UpdateTripHandler` | file (edit) | redundante Compute-Aufrufe entfernen |
| `src/core/naismith.py` | file (new) | Python-Naismith (Spiegel) |
| `src/app/loader.py` `save_trip`/`_parse_trip`/`_trip_to_dict` | file (edit) | Compute-on-Save + activity-Roundtrip |
| `src/app/trip.py` `Trip` | file (edit) | Feld `activity` |
| `src/services/trip_report_scheduler.py` `_convert_trip_to_segments` | file (edit) | reiner Leser, Interpolation raus |
| `scripts/backfill_arrival_calculated_802.py` | file (new) | Bestandsdaten-Migration (#102-konform) |

## Implementation Details

### §1 Go — Compute-on-Save zentralisieren

In `store.SaveTrip`, nach der AlertRules-Coercion, vor `json.MarshalIndent`:
```go
speeds := model.ActivitySpeed(trip.Activity)
for i := range trip.Stages {
    model.ComputeStageArrivals(&trip.Stages[i], speeds)
}
```
`ComputeStageArrivals` setzt nur das abgeleitete `arrival_calculated` — `time_window`,
`arrival_override` und Identität bleiben unberührt (idempotent). Die expliziten Aufrufe in
`UpdateTripHandler` (Z.232/384) werden entfernt (Doppelberechnung vermeiden).

### §2 Python — `src/core/naismith.py` (bit-genauer Spiegel)

```python
import math

_EARTH_KM = 6371.0088

def activity_speeds(activity: str) -> tuple[float, float, float]:
    if activity == "fahrrad_15": return (15.0, 600.0, 1000.0)
    if activity == "fahrrad_20": return (20.0, 600.0, 1000.0)
    if activity == "fahrrad_25": return (25.0, 600.0, 1000.0)
    return (4.0, 300.0, 500.0)

def _haversine_km(lat1, lon1, lat2, lon2) -> float: ...  # R=6371.0088, identisch Go

def _parse_start_minutes(start_time: str | None) -> int:  # "HH:MM" → min; invalid → 08:00
    ...

def _format_hhmm(total_min: int) -> str:                  # Clamp 23:59, "%02d:%02d"
    total_min = min(total_min, 24*60 - 1)
    return f"{total_min // 60:02d}:{total_min % 60:02d}"

def _naismith_hours(dist_km, asc_m, desc_m, sp) -> float:  # SUMME
    return dist_km/sp[0] + asc_m/sp[1] + desc_m/sp[2]

def compute_stage_arrivals(stage, activity: str) -> None:
    """Setzt waypoint.arrival_calculated für jeden Wegpunkt (in-place / RMW).
    Spiegelt internal/model/naismith.go::ComputeStageArrivals byte-genau."""
    ...
```
Rundung wie Go: `_format_hhmm(round(cur))` (Banker-Rundung vermeiden → Go nutzt math.Round =
round-half-away; Python `round()` ist banker's → stattdessen `math.floor(cur + 0.5)`).

### §3 Python — `save_trip` ruft Compute-on-Save

In `loader.save_trip`, nach dem Laden/Mergen, vor `_trip_to_dict`: für jede Stage
`compute_stage_arrivals(stage, trip.activity)`. `_parse_trip` liest `activity`,
`_trip_to_dict` serialisiert es (omitempty).

### §4 Scheduler — Leser mit Self-Heal über die geteilte Funktion

`_interpolate_arrival_time` und jede eigene/duplizierte Tempo-Logik im Scheduler entfernen.
In `_convert_trip_to_segments` bleibt die Prioritätskette
`time_window > arrival_override > stage.start_time(i==0) > arrival_calculated`.

**Self-Heal (Robustheit):** Trägt die Etappe (≥2 Wegpunkte) noch KEINE persistierten
`arrival_calculated` (z.B. im Deploy-Fenster vor der Migration, oder ein Schreibpfad, der
noch nicht über save_trip lief), leitet der Scheduler sie einmalig über DIESELBE kanonische
`core.naismith.compute_stage_arrivals(stage, trip.activity)` ab — **kein Duplikat, kein
hartkodiertes Tempo im Scheduler**. So entsteht NIE eine leere Briefing-Mail, und es gibt
genau EINE Python-Naismith-Implementierung. Der häufige Fall (persistierte Werte vorhanden)
liest unverändert nur. Das `end <= start`-Guard bleibt als letzte Absicherung gegen echte
Nulldaten.

### §5 Backfill-Migration `scripts/backfill_arrival_calculated_802.py`

Idempotent, #102-konform:
1. Pre-Snapshot wird vom Hook `data_schema_backup.py` erstellt (Schema-Datei-Edit).
2. Pro Nutzer alle Trips via `load_all_trips` laden, `save_trip` aufrufen (rechnet+persistiert).
3. Post-Verifikation: Stage- und Waypoint-Counts vor/nach identisch; `time_window`/
   `arrival_override` unverändert; nur `arrival_calculated` neu/aktualisiert.
4. Dry-run-Flag (`--dry-run`) listet betroffene Trips ohne Schreiben.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit einer Etappe (≥2 Wegpunkte) ohne `arrival_calculated` / When er über Python `save_trip` ODER Go `store.SaveTrip` gespeichert wird / Then trägt jeder Wegpunkt danach ein `arrival_calculated` ("HH:MM"); eine Pausen-Etappe (0 Wegpunkte) bekommt keines.

- **AC-2:** Given ein Trip `activity="fahrrad_20"`, flache ~20-km-Etappe, Start 08:00 / When gespeichert / Then ist `arrival_calculated` des 2. Wegpunkts ~"09:00" (20 km/h), NICHT ~"13:00" (Wandertempo).

- **AC-3:** Given identische Wegpunkte + `activity` + `start_time` / When `src/core/naismith.compute_stage_arrivals` und Go `model.ComputeStageArrivals` darauf laufen / Then sind die erzeugten `arrival_calculated`-Strings identisch (gleiches Fixture; inkl. Rundungs- und 23:59-Clamp-Randfall).

- **AC-4:** Given `activity=""` und eine Etappe mit Distanz + Aufstieg / When gespeichert / Then entspricht `arrival_calculated` exakt der bisherigen Wanderer-Naismith-SUMME (4/300/500) — keine Änderung für bestehende Wander-Trips.

- **AC-5:** Given die Bestandsdaten (z.B. gr221: 16 Wegpunkte, 0 `arrival_calculated`) / When `scripts/backfill_arrival_calculated_802.py` läuft / Then tragen danach alle Wegpunkte `arrival_calculated`, Stage-/Waypoint-Counts sind unverändert, und `time_window`/`arrival_override` sind unberührt.

- **AC-6:** Given ein Trip mit befülltem `arrival_calculated` / When der Scheduler Segmente baut / Then nutzt er die persistierten Werte; `_interpolate_arrival_time` und `_activity_speeds` existieren NICHT mehr im Scheduler (kein Live-Compute-Pfad).

- **AC-7:** Given ein Trip mit `arrival_override` und `time_window` an Wegpunkten / When er zweimal gespeichert wird / Then sind die `arrival_calculated`-Werte beider Läufe identisch, und `arrival_override`/`time_window` bleiben über Save erhalten.

- **AC-8:** Given eine Etappe (≥2 Wegpunkte) ohne persistierte `arrival_calculated`, ohne `time_window`, ohne `arrival_override` / When der Scheduler Segmente baut / Then leitet er die Zeiten EINMALIG über die geteilte `core.naismith.compute_stage_arrivals(stage, trip.activity)` ab (Self-Heal) und liefert korrekte, aktivitätsgerechte Segmente — KEINE leere Briefing-Mail, KEIN dupliziertes/hartkodiertes Tempo im Scheduler, kein Crash.

## Out of Scope

- Vereinheitlichung der zwei Trip-Schreiber (Go + Python) zu einem Backend — separate
  Architektur-Frage.
- Frontend-TS-Vorschau (`naismith.ts`) bleibt (instant Editor-Feedback, kein Persistenzpfad).
- Naismith-Formel-Parameter ändern (Tempo-Konstanten bleiben wie #674/#296).

## Changelog

- 2.0 (2026-06-14): **Umbau auf derive-on-write** (Compute-on-Save Go+Python, Backfill,
  Scheduler reiner Leser). Ersetzt den Python-Interpolations-Fix aus v1.0. PO-Entscheidung
  Vollumbau.
- 1.0 (2026-06-14): Initialer Python-Interpolations-Fix (verworfen zugunsten v2.0).
