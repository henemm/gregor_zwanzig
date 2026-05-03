---
entity_id: validator_internal_loaded_endpoint
type: module
created: 2026-05-03
updated: 2026-05-03
status: draft
version: "1.0"
tags: [validator, api, observability, tooling, loader]
---

# Validator Internal Loaded Endpoint

## Approval

- [ ] Approved

## Purpose

Read-Only Internal-Endpoint `GET /api/_internal/trip/{id}/loaded`, der den hydrierten Loader-Output eines Trips als JSON zurueckgibt — inklusive der vom Loader auto-injizierten `display_config`. Macht damit den Python-Loader fuer den External Validator (Issue #110) direkt beobachtbar, sodass kuenftige Validator-Reports (Folge aus Issue #111) ohne Workarounds pruefen koennen, was tatsaechlich aus Disk geladen wurde.

## Source

- **File:** `api/routers/internal.py` (NEU), `internal/handler/proxy.go`, `cmd/server/main.go`, `api/main.py`
- **Identifier:** `loaded_trip` (FastAPI-Route), `LoadedTripProxyHandler` (Go-Proxy)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `loader` | aufgerufen | `load_all_trips(user_id)` + `_trip_to_dict(trip)` — kanonische User-gefilterte Hydration und Serialisierung |
| `proxy` (Go) | erweitert | Neuer `LoadedTripProxyHandler` mit `chi.URLParam("id")` + bestehendem `appendUserID` (Vorbild: `CompareProxyHandler`) |
| `auth` (Go) | genutzt | Bestehende globale `AuthMiddleware` enforcet `gz_session`-Cookie; `_internal`-Pfade NICHT in die Whitelist (`internal/middleware/auth.go:34-39`) |
| `external_validator_auth` | konsumiert | Validator nutzt diesen Endpoint via dem im Launcher injizierten Auth-Cookie |

## Implementation Details

### `api/routers/internal.py` — NEU (~20 LoC)

```python
from fastapi import APIRouter, HTTPException, Query
from src.app.loader import load_all_trips, _trip_to_dict

router = APIRouter()

@router.get("/api/_internal/trip/{trip_id}/loaded")
async def loaded_trip(trip_id: str, user_id: str = Query(...)):
    trip = next((t for t in load_all_trips(user_id) if t.id == trip_id), None)
    if trip is None:
        raise HTTPException(404, f"Trip {trip_id} nicht gefunden fuer User {user_id}")
    return _trip_to_dict(trip)
```

### `api/main.py` — Router einbinden (1 Zeile)

```python
from api.routers import internal
app.include_router(internal.router)
```

### `internal/handler/proxy.go` — Neuer Handler (~25 LoC)

```go
func LoadedTripProxyHandler(pythonURL string) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        id := chi.URLParam(r, "id")
        query := appendUserID("", middleware.UserIDFromContext(r.Context()))
        url := pythonURL + "/api/_internal/trip/" + id + "/loaded?" + query
        // Standard Forwarding analog ProxyHandler / CompareProxyHandler:
        //   GET-Request bauen, Response-Body + Status + Content-Type durchreichen.
    }
}
```

### `cmd/server/main.go` — Route registrieren (1 Zeile)

```go
r.Get("/api/_internal/trip/{id}/loaded", handler.LoadedTripProxyHandler(cfg.PythonCoreURL))
```

## Expected Behavior

- **Input:** `GET /api/_internal/trip/{id}/loaded` mit gueltigem `gz_session`-Cookie. nginx routet `/api/*` nach Go (Port 8090), Go-Auth-Middleware enforcet das Cookie, Go-Proxy haengt `?user_id=<aus-context>` an und leitet nach Python (FastAPI Port 8000) weiter.
- **Output:** `200 OK` + JSON des hydrierten Trips wie von `_trip_to_dict` erzeugt — inkl. vom Loader auto-injiziertem `display_config`, datetimes als ISO-Strings, Enums als `.value`. `404 Not Found` wenn `trip_id` im User-Scope nicht existiert. `401 Unauthorized` ohne gueltiges Cookie (durch globale Middleware).
- **Side effects:** Keine. Reine Read-Operation — der Loader liest von Disk, es wird nichts geschrieben.

## Known Limitations

- `_trip_to_dict` ist ein privater Helper im Loader. Der Endpoint koppelt sich bewusst daran, weil das die kanonische Serialisierung ist; eine Signatur-Aenderung dort betrifft auch diesen Endpoint.
- Endpoint exposed alle Trip-Felder inkl. evtl. zukuenftiger sensibler Daten. Da Auth-geschuetzt und nur fuer Validator-User sinnvoll, verzichten wir auf Sanitization.
- Die `_internal`-Pfad-Konvention signalisiert: Tooling-/Validator-Endpoint, nicht versionsstabil im Sinne einer Public-API. Frontend und Endbenutzer nutzen ihn nicht.

## Changelog

- 2026-05-03: Initial spec — Issue #115 (Read-Only Internal-Endpoint fuer Loader-Observability)
