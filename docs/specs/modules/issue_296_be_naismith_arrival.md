---
entity_id: issue_296_be_naismith_arrival
type: module
created: 2026-05-23
updated: 2026-05-23
status: draft
version: "1.0"
parent_issue: 296
related: issue_296_fe_profile_editor
issues: [296]
tags: [backend, go, python, naismith, trip, waypoint, schema, arrival-times]
---

# Issue #296-BE — Naismith-Ankunftszeiten: Modell-Feld + Berechnung beim Speichern + Pipeline-Konsum

## Approval

- [ ] Approved

## Purpose

Pro Wegpunkt eine **berechnete Ankunftszeit** (`arrival_calculated`) persistieren, sodass (a) der visuelle Editor sie anzeigen kann und (b) die Wetter-Pipeline **dieselbe** Zeit nutzt, zu der real Wetter abgerufen wird. Heute existiert kein solches Feld; die Pipeline interpoliert zur Laufzeit mit einer divergenten Formel (`max()` statt Summe). Diese Sub-Spec ist das Backend-/Daten-Fundament für den Frontend-Editor (`issue_296_fe_profile_editor`).

## Source

**Schicht: Go-API + Python-Backend (gemischt)** — beide lesen/schreiben dieselbe JSON-Datei `data/users/{userID}/trips/{tripID}.json`.

**EDIT — Go:**
- `internal/model/trip.go` — `Waypoint`-Struct: Feld `ArrivalCalculated *string` ergänzen
- `internal/handler/trip.go` — `UpdateTripHandler`: nach Stage-Merge Naismith-Zeiten berechnen + setzen
- `internal/model/naismith.go` (**NEU**) — `ComputeStageArrivals(stage)` + `naismithHours()` + `haversineKm()` (falls kein bestehender Helper)

**EDIT — Python:**
- `src/app/trip.py` — `Waypoint`-Dataclass: Feld `arrival_calculated: Optional[str] = None`
- `src/app/loader.py` — `_parse_trip`/Waypoint-Parsing: `arrival_calculated` aus JSON übernehmen (Datenverlust-Regel)
- `src/services/trip_report_scheduler.py` — `_convert_trip_to_segments`/`_interpolate_arrival_time`: persistierten `arrival_calculated` bevorzugen

**EDIT — Frontend-Typ (nur Feld, Nutzung in FE-Spec):**
- `frontend/src/lib/types.ts` — `Waypoint`: `arrival_calculated?: string`

**Identifier:** `Waypoint.ArrivalCalculated` (Go), `Waypoint.arrival_calculated` (Python/TS), `ComputeStageArrivals`, `naismithHours`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/store/store.go` | file (lesen) | `LoadTrip`/`SaveTrip` — Persistenz unverändert, neues Feld wird mitserialisiert |
| `internal/handler/trip.go` `UpdateTripHandler` | file (edit) | Read-Modify-Write-Merge, Berechnungspunkt nach Stage-Merge |
| `src/core/segment_builder.py` `compute_hiking_time` | reference | Maßgebliche Naismith-Formel (Summe), Vorbild für Go |
| `src/app/models.py` `EtappenConfig` | reference | Single Source der Tempo-Konstanten: `speed_flat_kmh=4.0`, `speed_ascent_mh=300.0`, `speed_descent_mh=500.0` |
| `src/services/trip_report_scheduler.py` `_interpolate_arrival_time` | file (edit) | divergente `max()`-Logik — wird umgangen durch Bevorzugung des persistierten Werts |

## Implementation Details

### §1 Datenmodell — additiv, omitempty

```go
// internal/model/trip.go — Waypoint
type Waypoint struct {
    ID                string  `json:"id"`
    Name              string  `json:"name"`
    Lat               float64 `json:"lat"`
    Lon               float64 `json:"lon"`
    ElevationM        int     `json:"elevation_m"`
    TimeWindow        *string `json:"time_window,omitempty"`
    Suggested         bool    `json:"suggested,omitempty"`
    ArrivalCalculated *string `json:"arrival_calculated,omitempty"` // NEU — "HH:MM", vom Backend berechnet
}
```

```python
# src/app/trip.py — Waypoint
@dataclass(frozen=True)
class Waypoint:
    id: str
    name: str
    lat: float
    lon: float
    elevation_m: int
    time_window: Optional[TimeWindow] = None
    arrival_calculated: Optional[str] = None  # NEU — "HH:MM"
```

**NICHT hinzufügen:** `origin`, `confirmed` (redundant zu `suggested`), `arrival_override` (Folge-Issue).

### §2 Naismith-Berechnung in Go (`internal/model/naismith.go`)

```go
// Konstanten gespiegelt aus src/app/models.py EtappenConfig (Single Source dort).
// Bei Änderung dort: hier nachziehen.
const (
    speedFlatKmh   = 4.0
    speedAscentMh  = 300.0
    speedDescentMh = 500.0
)

// naismithHours: angepasste Naismith's Rule (SUMME, nicht max!).
func naismithHours(distKm, ascentM, descentM float64) float64 {
    return distKm/speedFlatKmh + ascentM/speedAscentMh + descentM/speedDescentMh
}

// ComputeStageArrivals setzt Waypoint.ArrivalCalculated für jeden Wegpunkt.
// Start = stage.StartTime (parse "HH:MM") oder Default "08:00".
// arrival[0] = Start; arrival[i] = arrival[i-1] + naismithHours(dist, ascent, descent).
// dist = haversineKm zwischen Wegpunkt i-1 und i.
// ascent = max(0, elev[i]-elev[i-1]); descent = max(0, elev[i-1]-elev[i]).
func ComputeStageArrivals(stage *Stage) { ... }
```

- `haversineKm(lat1, lon1, lat2, lon2)`: Standard-Haversine (Erdradius 6371.0088 km). Vor Implementierung grep auf bestehenden Go-Haversine — wiederverwenden statt duplizieren.
- Ausgabeformat: `"HH:MM"` (24h, zero-padded). Überlauf >24h: weiterzählen modulo 24 NICHT — stattdessen `"HH:MM"` mit Stunden ggf. >23 vermeiden; bei Mehrtages-Etappen ist das ein Known-Limitation (Etappen sind per Definition Tagesabschnitte).
- Pausentag (`len(waypoints) == 0`): keine Berechnung, kein Feld.
- Einzelner Wegpunkt: `arrival_calculated = Start`.

### §3 Berechnungspunkt — `UpdateTripHandler`

Nach dem bestehenden Stage-Merge (Read-Modify-Write), vor `SaveTrip`:

```go
for i := range existing.Stages {
    model.ComputeStageArrivals(&existing.Stages[i])
}
```

Merge-Prinzip bleibt: nur explizit gelieferte Felder überschreiben, Rest erhalten (Datenverlust-Regel). `arrival_calculated` wird IMMER aus den (ggf. neuen) Wegpunkten frisch berechnet — es ist abgeleitet, nicht user-geliefert.

### §4 Python-Pipeline bevorzugt persistierten Wert

In `trip_report_scheduler._convert_trip_to_segments` (bzw. dort wo `_interpolate_arrival_time` greift):

```python
# Wenn der Wegpunkt eine persistierte Ankunftszeit hat, diese nutzen
# (stammt aus Go-Berechnung beim Speichern) — statt selbst zu interpolieren.
if wp.arrival_calculated:
    arrival = _parse_hhmm(wp.arrival_calculated, base_date)
else:
    arrival = self._interpolate_arrival_time(...)  # Fallback unverändert
```

Die divergente `max()`-Formel in `_interpolate_arrival_time` wird in DIESER Spec **nicht umgeschrieben** (Risiko-Minimierung am Live-System) — sie bleibt nur als Fallback für Trips ohne persistierten Wert. Hinweis-Kommentar setzen, dass die korrekte Formel die Summe ist (siehe `segment_builder.compute_hiking_time`); echte Konsolidierung = Folge-Bug-Issue.

### §5 Migration / Datenverlust

- Additiv + `omitempty`/`Optional` → **keine** Migrations-Skript nötig.
- Bestehende Trip-JSONs ohne `arrival_calculated`: Go `LoadTrip` → `nil`, Python `load_trip` → `None`. Kein Fehler.
- Roundtrip-Test PFLICHT (siehe AC-4): alt laden → speichern → neu laden → keine Daten-Diff an bestehenden Feldern.
- Pre-Snapshot-Hook (`data_schema_backup.py`) greift automatisch bei Edit von `internal/model/trip.go` / `src/app/trip.py` / `src/app/loader.py`.

## Expected Behavior

- **Input:** PUT `/api/trips/:id` mit `stages[].waypoints[]` (lat/lon/elevation_m), optional `stage.start_time`.
- **Output:** Gespeicherter Trip, in dem jeder Nicht-Pausen-Wegpunkt ein `arrival_calculated` "HH:MM" trägt. Python-Pipeline nutzt diese Zeiten für Segment-/Wetterabruf-Zeitpunkte.
- **Side effects:** JSON-Datei `data/users/{id}/trips/{id}.json` enthält neues Feld. Keine Änderung an bestehenden Feldern.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit einer Stage (`start_time` "08:00") und 2 flachen Wegpunkten 4 km auseinander (gleiche Höhe) / When der Trip via PUT `/api/trips/:id` gespeichert wird / Then trägt Wegpunkt 2 `arrival_calculated == "09:00"` (4 km ÷ 4 km/h = 1 h)
  - Test: `internal/model/naismith_test.go::TestComputeStageArrivals_Flat`

- **AC-2:** Given eine Stage ohne `start_time` mit ≥1 Wegpunkt / When die Ankunftszeiten berechnet werden / Then ist `arrival_calculated` des ersten Wegpunkts "08:00" (Default-Startzeit)
  - Test: `internal/model/naismith_test.go::TestComputeStageArrivals_DefaultStart`

- **AC-3:** Given ein Wegpunkt-Paar mit +300 m Aufstieg und ~0 km Horizontaldistanz / When Naismith berechnet wird / Then beträgt das Ankunfts-Inkrement 1 h (300 m ÷ 300 m/h) — beweist die Summen-Formel inklusive Höhenterm, nicht `max()`
  - Test: `internal/model/naismith_test.go::TestNaismithHours`, `::TestComputeStageArrivals_Ascent`

- **AC-4:** Given eine bestehende Trip-JSON-Datei OHNE `arrival_calculated`-Feld / When sie von Go `LoadTrip` und Python `load_trip` geladen wird / Then tritt kein Fehler auf und alle bestehenden Wegpunkt-Felder (name, lat, lon, elevation_m, suggested) bleiben unverändert (Roundtrip-Datenverlust-Guard)
  - Test: `internal/store/trip_arrival_roundtrip_test.go::TestTripRoundTrip_PreservesFieldsWithoutArrival`; Python `tests/tdd/test_issue_296_be_arrival.py::test_loader_preserves_arrival_calculated`, `::test_loader_handles_missing_arrival_calculated`

- **AC-5:** Given ein Trip dessen Wegpunkte `arrival_calculated` persistiert haben / When `trip_report_scheduler` Segmente baut / Then leiten sich die Segment-Zeiten aus den persistierten `arrival_calculated`-Werten ab, nicht aus `_interpolate_arrival_time`
  - Test: `tests/tdd/test_issue_296_be_arrival.py::test_scheduler_prefers_persisted_arrival`

- **AC-6:** Given das geänderte `Waypoint`-Modell (Go + Python) / When die Struct/Dataclass inspiziert wird / Then existiert genau ein neues Feld `arrival_calculated`; die Felder `origin` und `confirmed` wurden NICHT hinzugefügt
  - Test: `internal/model/waypoint_arrival_marshal_test.go::TestWaypointJSON_HasArrivalNotOriginConfirmed`, `::TestWaypointJSON_ArrivalOmitEmpty`

- **AC-7:** Given eine Stage die ein Pausentag ist (`len(waypoints) == 0`) / When Ankunftszeiten berechnet werden / Then tritt kein Fehler auf und es wird kein `arrival_calculated` gesetzt
  - Test: `internal/model/naismith_test.go::TestComputeStageArrivals_Pause`

- **AC-8:** Given ein Trip mit einer Stage aus 3 Wegpunkten (flach→Aufstieg→flach) / When gespeichert / Then sind die `arrival_calculated`-Werte streng monoton steigend im Format "HH:MM"
  - Test: `internal/model/naismith_test.go::TestComputeStageArrivals_Monotonic`

## Known Limitations

- **Mehrtages-Etappen:** `arrival_calculated` ist "HH:MM" ohne Datum. Etappen sind per Definition Tagesabschnitte; >24 h Gehzeit pro Etappe ist out of scope.
- **Konstanten doppelt:** Tempo-Konstanten (4.0/300/500) leben in Python `EtappenConfig` (Source) und gespiegelt in Go (`naismith.go`). Akzeptabel für 3 Floats; Querverweis-Kommentar pflicht. Echte SSOT via Endpoint = Folge-Issue.
- **Python `max()`-Divergenz bleibt** als Fallback bestehen (nicht in dieser Spec konsolidiert) — eigenes Bug-Issue.
- **Distanz aus lat/lon** (Haversine), nicht aus echter GPX-Spur → leichte Unterschätzung gegenüber tatsächlicher Wegstrecke. Konsistent mit bestehender Pipeline-Schätzung.

## Changelog

- 2026-05-23: Initiale Spec. Additives Feld `arrival_calculated` (Go+Python+TS), Go-Berechnung in `UpdateTripHandler` via neuem `internal/model/naismith.go`, Python-Pipeline bevorzugt persistierten Wert. 8 Acceptance Criteria. Sub-Spec von Issue #296 (Backend-Fundament), Partner: `issue_296_fe_profile_editor`.
