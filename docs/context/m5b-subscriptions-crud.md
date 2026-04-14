# Context: M5b Subscriptions CRUD

## Request Summary
Go CRUD-Endpoints für CompareSubscriptions, damit das SvelteKit-Frontend Subscriptions verwalten kann. Folgt dem etablierten Pattern von Locations/Trips.

## Besonderheit: Single-File Storage
Subscriptions werden NICHT als einzelne JSON-Dateien gespeichert (wie Locations/Trips), sondern in einer **einzelnen Datei** `compare_subscriptions.json` mit Wrapper:
```json
{"subscriptions": [{...}, {...}]}
```
→ Read-Modify-Write Pattern nötig (wie Python es macht).

## Datenmodell (CompareSubscription)

| Feld | Typ | Default | Bemerkung |
|------|-----|---------|-----------|
| id | string | - | Pflicht, aus Name generiert |
| name | string | - | Pflicht |
| enabled | bool | true | |
| locations | []string | [] | Location-IDs oder ["*"] für alle |
| forecast_hours | int | 48 | 24, 48 oder 72 |
| time_window_start | int | 9 | 0-23 |
| time_window_end | int | 16 | 0-23 |
| schedule | string | "weekly" | Enum: daily_morning, daily_evening, weekly |
| weekday | int | 4 | 0=Mo, 6=So |
| include_hourly | bool | true | |
| top_n | int | 3 | 1-10 |
| send_email | bool | true | |
| send_signal | bool | false | |
| display_config | object/null | null | Verschachtelt: metrics[] mit MetricConfig |

Legacy: `schedule: "weekly_friday"` → `schedule: "weekly"` + `weekday: 4`

## Endpoints

| Operation | Endpoint | Response |
|-----------|----------|----------|
| List | GET /api/subscriptions | 200 JSON array |
| Get one | GET /api/subscriptions/:id | 200 JSON oder 404 |
| Create | POST /api/subscriptions | 201 JSON |
| Update | PUT /api/subscriptions/:id | 200 JSON oder 404 |
| Delete | DELETE /api/subscriptions/:id | 204 |

**Kein Run-Endpoint in M5b** — POST /api/subscriptions/:id/run ist separate Aufgabe (braucht Python-Proxy für Comparison-Logik).

## Betroffene Dateien

| Datei | Änderung |
|-------|----------|
| `internal/model/subscription.go` | **NEU** — CompareSubscription + MetricConfig Structs |
| `internal/store/store.go` | Erweitern: Load/Save/Delete Subscriptions |
| `internal/handler/subscription.go` | **NEU** — CRUD Handlers |
| `cmd/server/main.go` | +5 Zeilen: Route-Registrierung |

## Bestehende Patterns (Referenz)

- **Handler:** `internal/handler/location.go` — LocationsHandler, Create/Update/Delete
- **Store:** `internal/store/store.go` — LoadLocations, SaveLocation, DeleteLocation
- **Model:** `internal/model/location.go` — Location struct mit JSON tags
- **Tests:** `internal/handler/location_write_test.go`, `handler_test.go`

## Python-Referenz

| Datei | Funktion |
|-------|----------|
| `src/app/user.py:27-138` | CompareSubscription Dataclass, Schedule Enum |
| `src/app/loader.py:664-819` | load/save/delete_compare_subscription(s) |
| `src/web/pages/subscriptions.py` | UI-Lifecycle (Create/Edit/Toggle/Delete) |
| `data/users/default/compare_subscriptions.json` | Produktionsdaten (2 Subscriptions) |

## Risiken

- **Single-File Concurrency:** Read-Modify-Write auf eine Datei — bei gleichzeitigen Requests Datenverlust möglich. Für V1 akzeptabel (Single-User).
- **display_config Komplexität:** Verschachteltes Objekt mit 25+ Metriken — als `map[string]interface{}` behandeln (wie Trip.DisplayConfig).
- **Legacy Migration:** `weekly_friday` → `weekly` + `weekday: 4` im Loader abfangen.
