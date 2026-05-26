# Context: Issue #303 — Naismith + algorithmische Wegpunktvorschläge (Backend)

## Request Summary

Backend-Ergänzung: Wegpunkte bekommen strukturierte `origin`/`confirmed`/`suggestion_reason`/`arrival_override`-Felder; der GPX-Upload liefert algorithmisch erkannte Vorschläge (Gipfel, Täler) bereits im API-Response; ein neuer PATCH-Endpoint bestätigt oder verwirft Vorschläge.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `internal/model/trip.go` | Go `Waypoint`-Struct — hier `Origin`, `Confirmed`, `SuggestionReason`, `ArrivalOverride` ergänzen |
| `internal/model/naismith.go` | `ComputeStageArrivals()` — vorhanden, kein Change |
| `internal/model/waypoint_arrival_marshal_test.go` | AC-6 aus #296 prüft EXPLIZIT, dass `origin`/`confirmed` NICHT existieren → muss für #303 umgebaut werden |
| `internal/handler/trip.go` | `UpdateTripHandler` — ruft schon `ComputeStageArrivals` auf; confirm-Handler kommt neu hinzu |
| `internal/store/trip_arrival_roundtrip_test.go` | Roundtrip-Test — nutzt `Suggested bool`; muss auf neues `Origin`-Feld angepasst werden |
| `cmd/server/main.go` | Router — neuen PATCH `/api/trips/{id}/stages/{stage_id}/waypoints/{wp_id}/confirm` registrieren |
| `src/core/elevation_analysis.py` | `detect_waypoints()` — vorhandene GIPFEL/TAL-Erkennung, wird von route_analyzer gewrappt |
| `src/app/models.py` | `DetectedWaypoint`, `WaypointType` — Basis für den Mapper |
| `src/services/gpx_processing.py` | `gpx_to_stage_data()` — API-Contract stable; muss `origin`/`confirmed`/`suggestion_reason` zurückgeben |
| `api/routers/gpx.py` | POST `/api/gpx/parse` — kein Change nötig (Delegation an gpx_processing) |
| `src/app/trip.py` | Python `Waypoint` — `origin`, `confirmed`, `suggestion_reason`, `arrival_override` ergänzen |
| `src/app/loader.py` | `_parse_trip` — neue Felder aus JSON übernehmen |
| `frontend/src/lib/types.ts` | TypeScript `Waypoint` — neue Felder typisieren |
| `tests/tdd/test_issue_296_be_arrival.py` | Vorhandene #296-Tests — kein Conflict, da Python-Seite nur addiert |
| `internal/model/naismith_test.go` | Vorhandene Naismith-Tests — bleiben unverändert |

## Existing Patterns

- **Additives Schema-Pattern:** Neue Felder immer `omitempty` (Go) / `Optional` (Python) — keine Migration nötig, Legacy-JSONs laden sauber. Gilt auch für #303.
- **Read-Modify-Write in UpdateTripHandler:** Bestehender Handler mergt, ruft dann `ComputeStageArrivals` auf. Confirm-Handler folgt demselben Pattern.
- **Go ist der authoritative Store:** Python liest nur. Neue Felder persistieren in Go, Python-Loader übernimmt sie.
- **GPX → Python → Go-Proxy:** `POST /api/gpx/parse` wird durch `GpxProxyHandler` direkt an Python weitergeleitet. Python-Response landet 1:1 beim Frontend. Neue Felder im Python-Response erscheinen automatisch beim Frontend.
- **detect_waypoints() ist vorhanden:** `src/core/elevation_analysis.py` erkennt bereits GIPFEL/TAL per Sliding-Window. `route_analyzer.py` wird ein dünner Adapter darüber — kein neuer Algorithmus.
- **`Suggested bool` ist Legacy:** Eingeführt in #296 als Platzhalter. #303 baut `origin: "algorithm" | "manual"` dazu — `suggested` bleibt als `omitempty`-Alias (backward compat mit Altdaten), wird aber bei neuem Code nicht mehr gesetzt.

## Key Design Decisions

### 1. Welche Felder neu?

```go
// internal/model/trip.go — Waypoint
type Waypoint struct {
    // ... bestehende Felder ...
    Suggested         bool    `json:"suggested,omitempty"`          // Legacy — erhalten, omitempty
    ArrivalCalculated *string `json:"arrival_calculated,omitempty"` // #296 — unverändert
    // NEU (#303):
    Origin            string  `json:"origin,omitempty"`             // "manual" | "algorithm"; leer = "manual"
    Confirmed         bool    `json:"confirmed,omitempty"`          // true = bestätigt; false = Vorschlag
    SuggestionReason  *string `json:"suggestion_reason,omitempty"`  // "peak" | "valley" | "pass"
    ArrivalOverride   *string `json:"arrival_override,omitempty"`   // User-Override HH:MM
}
```

### 2. Welche Methode für Zeiten?

`ArrivalCalculated` bleibt die Naismith-Berechnung. `ArrivalOverride` ist der User-Wert.
Die Pipeline-Logik (welcher Wert gewinnt) bleibt in Python — `arrival_override` hat Vorrang, dann `arrival_calculated`.

### 3. Confirm-Endpoint — Go oder Python?

**Go.** Der Store ist in Go. Confirm = `confirmed=true` setzen + Arrivals neu berechnen + speichern.
Python hat keinen direkten Store-Zugriff.

### 4. Bestehender Test TestWaypointJSON_HasArrivalNotOriginConfirmed

Dieser Test aus #296 prüft, dass `origin`/`confirmed` NICHT im JSON erscheinen.
#303 macht ihn obsolet — er muss umgebaut werden (neue Prüfung: `origin` und `confirmed` *müssen* marshallierbar sein).

## Dependencies

- **Upstream:** `src/core/elevation_analysis.py::detect_waypoints` (bereits vorhanden)
- **Upstream:** `internal/model/naismith.go::ComputeStageArrivals` (bereits vorhanden)
- **Downstream:** Frontend Issues #06, #11 (Wegpunkt-Editor, Wizard Step 2) — lesen die neuen Felder
- **Downstream:** Python-Pipeline `trip_report_scheduler.py` — `arrival_override` > `arrival_calculated` > Interpolation

## Existing Specs

- `docs/specs/modules/issue_296_be_naismith_arrival.md` — Sub-Spec des Vorgängers; enthält explizit "NICHT hinzufügen: `origin`, `confirmed`" — #303 ist die vorgesehene Fortsetzung
- `docs/specs/modules/epic_136_step3_waypoints.md` — Wegpunkt-Editor (Frontend)
- `docs/specs/tests/issue_296_be_arrival_tests.md` — Testplan #296

## Analysis Results (Phase 2)

### Implementierungsreihenfolge (13 Schritte)

1. **Go — Test REBUILD** `waypoint_arrival_marshal_test.go` — `TestWaypointJSON_HasArrivalNotOriginConfirmed` muss von "darf NICHT existieren" auf "muss existieren" umgebaut werden (TDD RED)
2. **Go — Struct** `internal/model/trip.go` — 4 Felder ergänzen → Test wird grün
3. **Go — Roundtrip-Test** `trip_arrival_roundtrip_test.go` — neuer Test mit allen 4 neuen Feldern
4. **Go — Handler** `internal/handler/trip.go` — `ConfirmWaypointHandler` + DTO (~80 LoC)
5. **Go — Handler-Test** `internal/handler/trip_confirm_test.go` — NEUE Datei (~60 LoC)
6. **Go — Router** `cmd/server/main.go` — PATCH-Endpoint registrieren (2 Zeilen)
7. **Python — Modell** `src/app/trip.py` — 4 optionale Felder in Waypoint-Dataclass
8. **Python — Loader** `src/app/loader.py` — `_parse_trip` + `_trip_to_dict` lesen/schreiben neue Felder
9. **Python — route_analyzer** `src/services/route_analyzer.py` — NEUE Datei, ~60 LoC
10. **Python — GPX** `src/services/gpx_processing.py` — `gpx_to_stage_data` ruft route_analyzer auf
11. **Python — Scheduler** `src/services/trip_report_scheduler.py` — `arrival_override`-Priorität einbauen
12. **TS — Typen** `frontend/src/lib/types.ts` — 4 optionale Felder in Waypoint-Interface
13. **TS — Strip** `frontend/src/lib/utils/waypointEditor.ts` — neue Felder vor PUT herausfiltern

### Scope

- **13 Dateien** (inkl. 2 neue), ~**378 LoC** gesamt (~150 Test-Code, ~228 Produktion)
- Sprachen: Go (Handler/Modell), Python (Modell/Service/Loader), TypeScript (Typen)

### Kritischer Befund: Fehlendes Strip in Frontend

`waypointEditor.ts` filtert heute nur `suggested` aus dem PUT-Payload. `origin/confirmed/suggestion_reason` müssen ebenfalls gestripped werden — sonst überschreibt der Editor BE-berechnete Felder.

### Acceptance Criteria (10 ACs)

- AC-1: Go Waypoint-Struct hat genau 4 neue json-getaggte Felder (omitempty)
- AC-2: Waypoint mit `origin="algorithmic"`, `confirmed=true` serialisiert beide Felder; leere Felder fehlen im JSON
- AC-3: Roundtrip mit allen 4 neuen Feldern verlustfrei
- AC-4: PATCH `/api/trips/{id}/waypoints/{wpId}/confirm` — confirmed+arrival_override werden gespeichert, 404 bei miss
- AC-5: Legacy `Suggested=true` ohne `Origin` wird durch confirm auf `origin="algorithmic"` normalisiert
- AC-6: GPX-Parse-Response enthält `origin/confirmed/suggestion_reason` für erkannte Gipfel/Täler
- AC-7: Prioritätskette in Scheduler: `time_window > arrival_override > arrival_calculated > interpolation`
- AC-8: Python loader — alle 4 Felder werden verlustfrei gelesen und geschrieben
- AC-9: `detect_waypoints`-Pipeline läuft unverändert durch — route_analyzer mappt NUR an der API-Grenze
- AC-10: Frontend-Typen typisiert; neue Felder werden vor PUT gestripped

## Risks & Considerations

- **Bestehender Test-Conflict:** `TestWaypointJSON_HasArrivalNotOriginConfirmed` muss explizit umgebaut werden — er ist TDD-RED-Kandidat für #303.
- **`Suggested bool` Transition:** Bestehende Trips haben `"suggested": true` im JSON. Neues Code setzt `origin="algorithm"`. Beide können koexistieren (`omitempty`), aber der confirm-Handler muss beide verstehen (wenn `suggested=true` und `origin=""`, treat als `algorithm`).
- **route_analyzer.py ist thin Adapter:** Keine neuen Algorithmen. Nur Mapping `DetectedWaypoint.type` → `suggestion_reason` String.
- **GPX-Response Erweiterung bricht niemanden:** Frontend ignoriert unbekannte Felder. Python-Response fügt `origin/confirmed/suggestion_reason` zu Waypoints hinzu — backward compat OK.
- **confirm-Endpoint erfordert neue Route in main.go:** Kein bestehender Precedent für sub-resource PATCH auf Waypoint.
- **arrival_override Speicher-Pipeline:** Python `_interpolate_arrival_time` muss `arrival_override` vor `arrival_calculated` bevorzugen — kleine Python-Änderung nötig.
