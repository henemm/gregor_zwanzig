# Context: Go Trip Model + CRUD (M1d)

## Request Summary
Trip-Model (Trip/Stage/Waypoint) als Go Structs, JSON Store CRUD (Load/Save/Delete), und REST Endpoints (GET/POST/PUT/DELETE /api/trips). Vervollstaendigt M1.

## Related Files
| File | Relevance |
|------|-----------|
| src/app/trip.py | Python Trip/Stage/Waypoint Dataclasses — Referenz |
| src/app/models.py | Python Config-DTOs (AggregationConfig, DisplayConfig, ReportConfig) |
| src/app/loader.py | Python CRUD: save_trip, delete_trip, load_trip |
| internal/model/location.go | Go Location Struct — Pattern-Referenz |
| internal/store/store.go | Go Store mit LoadLocations — erweitern |
| internal/handler/location.go | Go LocationsHandler — Pattern-Referenz |
| data/users/default/trips/*.json | Echte Trip-Dateien |

## Existing Patterns
- **Go Model:** JSON-Tags mit omitempty, Pointer fuer optionale Felder, map[string]interface{} fuer komplexe Nested-Configs
- **Go Store:** ReadDir + Unmarshal Loop, Fehler loggen + ueberspringen, leeres Slice bei fehlendem Dir
- **Go Handler:** Closure-Pattern mit Store-Injection, JSON Response

## Trip-Datenmodell (Python → Go)
- **Trip:** id, name, stages[], avalanche_regions[], aggregation, display_config (opt), report_config (opt)
- **Stage:** id, name, date, waypoints[], start_time (opt)
- **Waypoint:** id, name, lat, lon, elevation_m, time_window (opt, "HH:MM-HH:MM")
- **Configs:** aggregation, display_config, report_config als opaque maps (typisiert erst in M2+)

## Dependencies
- Upstream: internal/store (erweitern), internal/model (erweitern), chi Router
- Downstream: Zukuenftige M2-M4 Features bauen auf Trip-CRUD auf

## Risks & Considerations
- Trip-JSON ist komplex verschachtelt (3 Ebenen: Trip → Stage → Waypoint)
- Optionale Configs (display_config, report_config) muessen als opaque maps bleiben
- Scope: ~250 LoC Limit — Trip-Model + Store CRUD + Handler ist knapp
- Write-Operationen (POST/PUT/DELETE) brauchen Input-Validierung
