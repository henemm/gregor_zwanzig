---
entity_id: issue_303_waypoint_suggestions
type: module
created: 2026-05-26
updated: 2026-05-26
status: draft
version: "1.0"
parent_issue: 303
related: issue_296_be_naismith_arrival
issues: [303, 296]
tags: [backend, go, python, frontend, waypoint, suggestion, confirm, arrival-override, route-analyzer, gpx]
---

# Issue #303 — Algorithmische Wegpunktvorschläge + arrival_override

## Approval

- [ ] Approved

## Purpose

Vier neue Felder (`origin`, `confirmed`, `suggestion_reason`, `arrival_override`) auf dem `Waypoint`-Modell einführen, die von Issue #296 explizit auf diese Spec vertagt wurden. Das Ziel ist zweiteilig: (a) die GPX-Parse-Antwort reichert erkannte Gipfel und Täler automatisch mit Algorithmus-Metadaten an, damit das Frontend Vorschläge von manuell gesetzten Wegpunkten unterscheiden kann; (b) ein neuer PATCH-Endpoint ermöglicht es, einen Vorschlag zu bestätigen und optional eine manuelle Ankunftszeit (`arrival_override`) zu setzen, die in der Wetter-Pipeline Vorrang vor der berechneten Zeit erhält.

## Source

**Schicht: Go-API + Python-Backend + Frontend (gemischt)** — alle drei Schichten lesen und schreiben dieselbe JSON-Datei `data/users/{userID}/trips/{tripID}.json`.

**EDIT — Go:**
- `internal/model/trip.go` — `Waypoint`-Struct: 4 neue Felder
- `internal/model/waypoint_arrival_marshal_test.go` — bestehenden Test umbauen (Assertions invertieren)
- `internal/store/trip_arrival_roundtrip_test.go` — neue Roundtrip-Testfall
- `internal/handler/trip.go` — `ConfirmWaypointHandler` hinzufügen
- `internal/handler/trip_confirm_test.go` (**NEU**) — Handler-Tests
- `cmd/server/main.go` — Route registrieren

**EDIT — Python:**
- `src/app/trip.py` — `Waypoint`-Dataclass: 4 neue optionale Felder
- `src/app/loader.py` — `_parse_trip` + `_trip_to_dict`: neue Felder lesen/schreiben
- `src/services/route_analyzer.py` (**NEU**) — Thin Adapter `enrich_waypoints_from_detected`
- `src/services/gpx_processing.py` — `gpx_to_stage_data`: route_analyzer nach Segmentierung aufrufen
- `src/services/trip_report_scheduler.py` — `_convert_trip_to_segments`: `arrival_override` als höchste Priorität

**EDIT — Frontend:**
- `frontend/src/lib/types.ts` — `Waypoint`-Interface: 4 neue optionale Felder
- `frontend/src/lib/utils/waypointEditor.ts` — `origin`, `confirmed`, `suggestion_reason` vor PUT herausfiltern

**Identifier:** `Waypoint.Origin`, `Waypoint.ArrivalOverride`, `ConfirmWaypointHandler`, `enrich_waypoints_from_detected`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/model/trip.go` `Waypoint` | file (edit) | Basis-Struct; 4 neue Felder additiv anhängen |
| `internal/model/naismith.go` `ComputeStageArrivals` | reference | Wird im confirm-Handler nach dem Schreiben von `ArrivalOverride` aufgerufen, damit `arrival_calculated` aktuell bleibt |
| `internal/store/store.go` `LoadTrip`/`SaveTrip` | reference | Persistenz unverändert; neue Felder werden automatisch mitserialisiert (omitempty) |
| `internal/model/waypoint_arrival_marshal_test.go` | file (rebuild) | Behauptet bisher, dass `origin`/`confirmed` NICHT im JSON erscheinen — muss auf neue Semantik umgebaut werden |
| `src/core/elevation_analysis.py` `detect_waypoints` | reference | Liefert `list[DetectedWaypoint]` mit `WaypointType` (GIPFEL/TAL/PASS); Input für `route_analyzer` |
| `src/core/elevation_analysis.py` `_point_distance_approx` | reference | Equirektanguläre Näherungsdistanz; `route_analyzer` nutzt dieselbe Methode für Proximity-Matching |
| `src/services/hybrid_segmentation.py` `optimize_segments` | reference | Erhält weiterhin `list[DetectedWaypoint]` — bleibt unberührt; `route_analyzer` arbeitet ausschließlich auf der Dict-Schicht nach der Segmentierung |
| `src/services/gpx_processing.py` `gpx_to_stage_data` | file (edit) | Aufrufort für `route_analyzer.enrich_waypoints_from_detected` nach `segments_to_trip()` |
| `src/app/trip.py` `Waypoint` | file (edit) | Python-Dataclass; 4 neue optionale Felder |
| `src/app/loader.py` `_parse_trip`/`_trip_to_dict` | file (edit) | Lesen und Schreiben der 4 neuen Felder; Datenverlust-Regel gilt |
| `src/services/trip_report_scheduler.py` `_convert_trip_to_segments` | file (edit) | Prioritätskette um `arrival_override` erweitern |
| `frontend/src/lib/types.ts` `Waypoint` | file (edit) | TypeScript-Interface; 4 neue optionale Felder |
| `frontend/src/lib/utils/waypointEditor.ts` | file (edit) | Strip-Logik: backend-computed Felder vor PUT herausfiltern |

## Implementation Details

### §1 Datenmodell — additiv, omitempty

```go
// internal/model/trip.go — Waypoint — 4 neue Felder (bestehende unberührt)
type Waypoint struct {
    ID                string  `json:"id"`
    Name              string  `json:"name"`
    Lat               float64 `json:"lat"`
    Lon               float64 `json:"lon"`
    ElevationM        int     `json:"elevation_m"`
    TimeWindow        *string `json:"time_window,omitempty"`
    Suggested         bool    `json:"suggested,omitempty"`
    ArrivalCalculated *string `json:"arrival_calculated,omitempty"`
    // NEU — #303:
    Origin           string  `json:"origin,omitempty"`           // "manual" | "algorithmic"; leer = "manual"
    Confirmed        bool    `json:"confirmed,omitempty"`        // true = vom User bestätigt
    SuggestionReason *string `json:"suggestion_reason,omitempty"`// "detected_peak" | "detected_valley" | "detected_pass"
    ArrivalOverride  *string `json:"arrival_override,omitempty"` // User-Override "HH:MM"
}
```

```python
# src/app/trip.py — Waypoint frozen dataclass — 4 neue optionale Felder
@dataclass(frozen=True)
class Waypoint:
    id: str
    name: str
    lat: float
    lon: float
    elevation_m: int
    time_window: Optional[TimeWindow] = None
    arrival_calculated: Optional[str] = None
    # NEU — #303:
    origin: Optional[str] = None              # "manual" | "algorithmic"
    confirmed: Optional[bool] = None          # True = bestätigt
    suggestion_reason: Optional[str] = None   # "detected_peak" | "detected_valley" | "detected_pass"
    arrival_override: Optional[str] = None    # "HH:MM"
```

```typescript
// frontend/src/lib/types.ts — Waypoint interface — 4 neue optionale Felder
export interface Waypoint {
  // ... bestehende Felder ...
  arrival_calculated?: string;
  // NEU — #303:
  origin?: string;
  confirmed?: boolean;
  suggestion_reason?: string;
  arrival_override?: string;
}
```

### §2 Test-Umbau: `waypoint_arrival_marshal_test.go`

Der bestehende Test `TestWaypointJSON_HasArrivalNotOriginConfirmed` behauptet, dass `origin` und `confirmed` nicht im JSON erscheinen. Nach diesem Issue ist das falsch. Der Test wird umgebaut:

- Neue Assertion: `Waypoint{Origin:"algorithmic", Confirmed:true, SuggestionReason:ptr("detected_peak")}` → JSON enthält alle drei Keys `"origin"`, `"confirmed"`, `"suggestion_reason"`.
- Zweite Assertion: `Waypoint{}` (zero-value) → JSON enthält keinen der 4 neuen Keys (omitempty greift).
- Testname nach Umbau: `TestWaypointJSON_NewFieldsMarshalAndOmit` (alter Name entfernen, um semantischen Widerspruch zu vermeiden).

### §3 Neues Modul: `src/services/route_analyzer.py`

Thin Adapter — keine eigene Detektionslogik, nur Mapping von `DetectedWaypoint` auf Waypoint-Dict-Metadaten.

```python
PROXIMITY_THRESHOLD_KM = 0.5  # identisch zu _match_gpx_waypoints

WAYPOINT_TYPE_TO_REASON = {
    WaypointType.GIPFEL: "detected_peak",
    WaypointType.TAL:    "detected_valley",
    WaypointType.PASS:   "detected_pass",
}

def enrich_waypoints_from_detected(
    waypoint_dicts: list[dict],
    detected: list[DetectedWaypoint],
    track: GPXTrack,
) -> list[dict]:
    """
    Für jeden waypoint_dict: prüfe, ob ein DetectedWaypoint innerhalb von
    PROXIMITY_THRESHOLD_KM liegt (equirektanguläre Näherung via
    _point_distance_approx aus elevation_analysis).
    Bei Treffer:
      - waypoint_dict["origin"] = "algorithmic"
      - waypoint_dict["confirmed"] = False
      - waypoint_dict["suggestion_reason"] = WAYPOINT_TYPE_TO_REASON[detected.type]
    Kein Treffer → waypoint_dict unverändert zurückgeben.
    Gibt neue list[dict] zurück (keine In-place-Mutation).
    """
```

**KRITISCH:** `optimize_segments()` in `hybrid_segmentation.py` erhält weiterhin `list[DetectedWaypoint]` — `route_analyzer` greift NICHT in die Segmentierungspipeline ein. Der Aufruf von `detect_waypoints()` in `gpx_processing.py` für die Anreicherung ist ein zweiter, unabhängiger Aufruf nach `segments_to_trip()`.

### §4 GPX-Parse-Anreicherung in `gpx_processing.py`

```python
# Nach segments_to_trip():
from src.services import route_analyzer
detected = detect_waypoints(track)   # zweiter Aufruf, unabhängig von Segmentierung
waypoint_dicts = route_analyzer.enrich_waypoints_from_detected(
    waypoint_dicts, detected, track
)
# waypoint_dicts enthält jetzt origin/confirmed/suggestion_reason für erkannte Punkte
```

- `arrival_override` wird bei GPX-Parse NICHT gesetzt (nur via confirm-Endpoint).
- Segmentgrenz-Wegpunkte ohne Erkennung erhalten kein `origin`-Feld.

### §5 Neuer Go-Endpoint: `PATCH /api/trips/{id}/waypoints/{waypointId}/confirm`

```go
// internal/handler/trip.go — Request-Body
type confirmWaypointRequest struct {
    Confirmed       bool    `json:"confirmed"`
    ArrivalOverride *string `json:"arrival_override,omitempty"`
}
```

Handler-Ablauf (Schritt für Schritt):
1. Trip per `LoadTrip(id)` laden → 404 wenn nicht gefunden.
2. Alle Stages durchsuchen, Waypoint per ID finden → 404 wenn nicht gefunden; Index der Stage merken.
3. **Legacy-Kompatibilität:** Wenn `Waypoint.Suggested == true` UND `Waypoint.Origin == ""` → `Origin = "algorithmic"` setzen, `SuggestionReason = ptr("legacy_suggested")`.
4. `Waypoint.Confirmed = req.Confirmed` setzen.
5. `Waypoint.ArrivalOverride = req.ArrivalOverride` setzen.
6. `model.ComputeStageArrivals(&trip.Stages[stageIndex])` aufrufen (aktualisiert `arrival_calculated`).
7. Trip via `SaveTrip` speichern.
8. 200 mit vollständigem Trip-Body zurückgeben.

Route-Registrierung in `cmd/server/main.go`:
```go
r.PATCH("/api/trips/:id/waypoints/:waypointId/confirm", handler.ConfirmWaypointHandler)
```

### §6 Python-Scheduler-Prioritätskette

In `trip_report_scheduler._convert_trip_to_segments`:

```python
# Priorität: time_window > arrival_override > arrival_calculated > interpolation
if wp.time_window:
    arrival = _parse_hhmm(wp.time_window, base_date)
elif wp.arrival_override:
    arrival = _parse_hhmm(wp.arrival_override, base_date)
elif wp.arrival_calculated:
    arrival = _parse_hhmm(wp.arrival_calculated, base_date)
else:
    arrival = self._interpolate_arrival_time(...)  # Fallback unverändert
```

### §7 Frontend-Strip vor PUT

In `frontend/src/lib/utils/waypointEditor.ts`:

```typescript
// Felder herausfiltern, die das Backend selbst setzt — nie in PUT-Payload senden
const BACKEND_COMPUTED_FIELDS = ['origin', 'confirmed', 'suggestion_reason'] as const;

function stripBackendFields(waypoint: Waypoint): Waypoint {
  const copy = { ...waypoint };
  for (const field of BACKEND_COMPUTED_FIELDS) {
    delete copy[field];
  }
  return copy;
}
```

`arrival_override` wird NICHT herausgefiltert — es ist ein User-Wert, der via confirm-Endpoint gesetzt und nicht über PUT transportiert wird. Im regulären PUT-Payload taucht es nicht auf, da der Editor das Feld nicht editiert.

### §8 Migration / Datenverlust

- Alle 4 Felder sind additiv + `omitempty`/`Optional` → kein Migrations-Skript nötig.
- Bestehende Trip-JSONs ohne neue Felder: Go `LoadTrip` → Null-/Zero-Values, Python `load_trip` → `None`. Kein Fehler.
- Pre-Snapshot-Hook (`data_schema_backup.py`) greift automatisch bei Edit von `internal/model/trip.go` / `src/app/trip.py` / `src/app/loader.py`.

## Expected Behavior

- **Input (GPX-Parse):** `POST /api/gpx/parse` mit einer GPX-Datei, die Gipfel/Täler enthält.
- **Output (GPX-Parse):** Response-JSON enthält für erkannte Punkte `"origin":"algorithmic"`, `"confirmed":false`, `"suggestion_reason":"detected_peak"` (oder `"detected_valley"` / `"detected_pass"`). Nicht erkannte Segmentgrenz-Wegpunkte haben kein `origin`-Feld.

- **Input (Confirm):** `PATCH /api/trips/{id}/waypoints/{wpId}/confirm` mit `{"confirmed":true,"arrival_override":"11:45"}`.
- **Output (Confirm):** 200, vollständiger Trip-Body. Waypoint hat `confirmed:true`, `arrival_override:"11:45"`. `arrival_calculated` wurde neu berechnet und bleibt im JSON aktuell.

- **Input (Scheduler):** Trip mit Waypoint, der `arrival_override="14:00"` und `arrival_calculated="13:30"` hat.
- **Output (Scheduler):** Segment-Startzeit ist `14:00:00`.

- **Side effects:** `data/users/{id}/trips/{id}.json` enthält neue Felder. Alle bestehenden Felder bleiben unverändert. `origin`/`confirmed`/`suggestion_reason` werden nicht in reguläre PUT-Payloads aufgenommen.

## Acceptance Criteria

- **AC-1 (Modell Go):** Given das `Waypoint`-Struct in `internal/model/trip.go` / When es inspiziert wird / Then hat es genau die 4 neuen json-getaggten Felder `origin` (string, omitempty), `confirmed` (bool, omitempty), `suggestion_reason` (*string, omitempty), `arrival_override` (*string, omitempty); kein bestehendes Feld wurde entfernt.
  - Test: (populated after /tdd-red)

- **AC-2 (Serialisierung Go):** Given `Waypoint{Origin:"algorithmic", Confirmed:true, SuggestionReason:ptr("detected_peak")}` / When nach JSON marshalt / Then enthält das JSON alle drei Keys `"origin"`, `"confirmed"`, `"suggestion_reason"`. Given `Waypoint{}` (zero-value) / When marshalt / Then enthält das JSON keinen der 4 neuen Keys.
  - Test: `internal/model/waypoint_arrival_marshal_test.go::TestWaypointJSON_NewFieldsMarshalAndOmit`

- **AC-3 (Roundtrip Go):** Given ein Trip-JSON mit allen 4 neuen Feldern gesetzt / When `LoadTrip → SaveTrip → LoadTrip` durchläuft / Then gehen keine Feldwerte verloren.
  - Test: `internal/store/trip_arrival_roundtrip_test.go::TestTripRoundTrip_WithConfirmationFields`

- **AC-4 (Confirm-Endpoint — Happy Path):** Given ein existierender Trip mit einem Waypoint / When `PATCH /api/trips/{id}/waypoints/{wpId}/confirm` mit `{"confirmed":true,"arrival_override":"11:45"}` aufgerufen wird / Then antwortet der Server 200 und der Waypoint hat `confirmed:true` und `arrival_override:"11:45"`.
  - Test: `internal/handler/trip_confirm_test.go::TestConfirmWaypoint_SetsConfirmedAndOverride`

- **AC-5 (Confirm-Endpoint — 404):** Given ein nicht existierender Trip oder Waypoint / When der confirm-PATCH aufgerufen wird / Then antwortet der Server 404.
  - Test: `internal/handler/trip_confirm_test.go::TestConfirmWaypoint_NotFound`

- **AC-6 (Legacy Suggested):** Given ein Waypoint mit `suggested:true` und leerem `origin` / When der confirm-PATCH aufgerufen wird / Then setzt der Handler `origin="algorithmic"` und `suggestion_reason="legacy_suggested"` und schlägt nicht fehl.
  - Test: `internal/handler/trip_confirm_test.go::TestConfirmWaypoint_LegacySuggested`

- **AC-7 (GPX-Anreicherung):** Given eine GPX-Datei mit einem erkannten Gipfel / When `POST /api/gpx/parse` aufgerufen wird / Then enthält die Response für den Gipfel-Wegpunkt `"origin":"algorithmic"`, `"confirmed":false`, `"suggestion_reason":"detected_peak"`. Segmentgrenz-Wegpunkte ohne Erkennung haben kein `origin`-Feld in der Response.
  - Test: (populated after /tdd-red)

- **AC-8 (Scheduler-Priorität — override gewinnt):** Given ein Waypoint mit `arrival_override="14:00"` und `arrival_calculated="13:30"` / When `_convert_trip_to_segments` läuft / Then ist die Segment-Startzeit `14:00:00`.
  - Test: (populated after /tdd-red)

- **AC-9 (Scheduler-Priorität — calculated als Fallback):** Given ein Waypoint ohne `arrival_override` aber mit `arrival_calculated="13:30"` / When `_convert_trip_to_segments` läuft / Then ist die Segment-Startzeit `13:30:00`.
  - Test: (populated after /tdd-red)

- **AC-10 (Python Loader):** Given ein Trip-JSON mit allen 4 neuen Feldern / When `load_trip` aufgerufen wird / Then hat das Python-`Waypoint`-Objekt alle 4 Felder korrekt gesetzt. `_trip_to_dict` schreibt alle 4 Felder zurück; bei `None`-Wert wird das Feld weggelassen.
  - Test: (populated after /tdd-red)

- **AC-11 (Pipeline-Isolation):** Given beliebige GPX-Daten / When die volle GPX-Parse-Pipeline läuft / Then erhält `optimize_segments()` weiterhin `list[DetectedWaypoint]` unverändert; alle bestehenden Tests für `detect_waypoints` und `optimize_segments` laufen durch.
  - Test: bestehende Tests in `tests/` (kein neuer Test nötig, aber Regression-Guard)

- **AC-12 (Frontend-Typen + Strip):** Given das TypeScript-`Waypoint`-Interface / When inspiziert / Then hat es die 4 neuen optionalen Felder. `waypointEditor` filtert `origin`, `confirmed`, `suggestion_reason` vor PUT heraus; `arrival_override` wird nicht gefiltert.
  - Test: (populated after /tdd-red)

## Known Limitations

- `arrival_calculated` wird auch dann neu berechnet (via `ComputeStageArrivals`), wenn `arrival_override` gesetzt ist — `arrival_override` gewinnt in der Python-Prioritätskette, aber das Feld `arrival_calculated` bleibt im JSON aktuell. Das ist gewollt: zwei unabhängige Felder.
- `arrival_override` als HH:MM ohne Datum — gleiche Limitation wie `arrival_calculated` (Etappen sind Tagesabschnitte; Mehrtages-Etappen out of scope).
- Proximity-Matching in `route_analyzer` nutzt equirektanguläre Näherung (wie `elevation_analysis._point_distance_approx`), keine exakte Geodäsie. Schwellwert 0,5 km; für Streckenlängen <100 km ausreichend genau.
- `detect_waypoints()` wird in `gpx_processing.py` ein zweites Mal aufgerufen (zusätzlich zum Aufruf in `hybrid_segmentation.py`). Das ist bewusst akzeptiert, um die Segmentierungs-Pipeline unberührt zu lassen. Performance-Impact vernachlässigbar (reine In-Memory-Berechnung auf bereits geladenen Höhendaten).

## Changelog

- 2026-05-26: Initiale Spec. Setzt Issue #296 fort: 4 neue Waypoint-Felder (Go+Python+TS), neues `route_analyzer`-Modul, GPX-Anreicherung, PATCH-confirm-Endpoint mit Legacy-Kompatibilität, Scheduler-Prioritätskette mit `arrival_override`. 12 Acceptance Criteria. Direktes Folge-Issue zu #296 (Naismith-Fundament).
