---
issue: 115
title: Validator-Endpoint /api/_internal/trip/{id}/loaded
status: phase1-context
---

# Context: Issue #115 — Internal-Endpoint für Loader-Output

## Request Summary

Read-Only Endpoint `GET /api/_internal/trip/{id}/loaded`, der das via Python-Loader hydrierte Trip-Objekt (inklusive auto-injizierter `display_config`) als JSON zurückgibt. Macht den Loader-Output für External Validator beobachtbar (folgt aus Validator-Report von Issue #111).

## Architektur — wichtig zu verstehen

Zwei Backends teilen sich `data/users/*/trips/*.json`:
- **Go-API** (`gregor-api`, Port 8090) — CRUD über `/api/trips/...`. Behandelt `display_config` als opaque `map[string]interface{}`. Kennt Loader-Logik nicht.
- **Python NiceGUI** (`gregor-python`, Port 8080) — UI + Scheduler + Reports. Besitzt den Python-Loader.

`nginx` routet ALLES unter `/api/*` zu Go. Python ist nur unter `/` und auf Sub-Pfaden wie `/_health`, `/_scheduler_status` direkt erreichbar.

Auth ist Go-Side (Cookie `gz_session`, HMAC-signiert, Middleware in `internal/middleware/auth.go`). Python hat keine eigene Auth.

## Related Files

| Datei | Relevanz |
|------|----------|
| `cmd/server/main.go` | Route-Registrierung; bestehender Proxy-Pattern für Python (`/api/gpx/parse`, `/api/notify/test`, `/api/compare`) |
| `internal/handler/proxy.go` | `ProxyHandler(pythonCoreURL, path)`-Helper inkl. `appendUserID` |
| `internal/handler/trip.go` | Bestehender `TripHandler` für GET /api/trips/{id} (echo aus Disk) |
| `internal/middleware/auth.go` | Auth-Middleware mit Public-Whitelist (Zeile 34-37) |
| `src/web/main.py` | Python NiceGUI HTTP-Routen — Pattern `@app.get("/_health")`, `@app.get("/_scheduler_status")` |
| `src/app/loader.py` | `load_trip_from_dict()` (mit Issue-#111-Default) und `_trip_to_dict()` (Serialisierung) |
| `docs/specs/modules/external_validator_auth.md` | Auth-Schema für Validator (Issue #110) — gleiches Auth-Modell wiederverwenden |
| `nginx/gregor20.henemm.com.conf` (henemm-infra) | Routing — keine Änderung nötig wenn Endpoint via Go läuft |

## Existing Patterns

### Pattern A — Go proxiert zu Python
Bestehende Routen wie `/api/gpx/parse`, `/api/notify/test`, `/api/compare` werden in `cmd/server/main.go` als Proxy zu Python registriert. Auth wird automatisch durch Go-Middleware enforced. Python-Route ist die eigentliche Implementation.

### Pattern B — Python-Routen via Starlette
NiceGUI-App nutzt Starlette darunter. Python-Routen werden via `@app.get("/path")` registriert; können `JSONResponse(...)` zurückgeben. Pfade `/_*` (z.B. `/_health`) sind etabliert.

### Pattern C — Trip-Serialisierung
`_trip_to_dict()` in `loader.py` macht JSON-saubere Serialisierung (datetimes via `.isoformat()`, enums via `.value`). Ist die kanonische Quelle.

## Dependencies

- **Upstream:** Loader (`load_trip_from_dict`), Trip-Serialisierung (`_trip_to_dict`), Go-Proxy-Helper, Auth-Middleware
- **Downstream:** External Validator nutzt den Endpoint, um Loader-Output (Default-display_config etc.) zu verifizieren

## Existing Specs

- `docs/specs/modules/external_validator_auth.md` — Auth-Modell (Issue #110)
- `docs/specs/modules/loader_display_config_default.md` — Issue #111, validiert dann via diesen Endpoint

## Risks & Considerations

1. **Auth-Pfad:** Endpoint MUSS hinter Cookie-Auth stehen (gleiche Mechanik wie andere `/api/*`-Routen). Go-Middleware reicht — Python-Route bleibt im internen Netz unter Port 8080.
2. **Python-Loader-Performance:** Loader liest JSON von Disk. Bei großen User-Daten könnte das lahm sein — aber Validator macht maximal wenige Requests. Kein Problem.
3. **Pfad-Konvention `_internal`:** Signalisiert „nicht für UI". Sollte in Auth-Whitelist NICHT freigegeben werden — Auth bleibt aktiv.
4. **trip_id-Auflösung:** Loader kennt nur Trip-ID; Auth-Context liefert User-ID. Endpoint muss prüfen, ob die trip_id zum eingeloggten User gehört (oder `user_id` als Query-Param übergeben — wie im bestehenden Proxy-Pattern via `appendUserID`).
5. **Konsistenz mit GET /api/trips/{id}:** Die normale Route gibt das JSON-as-stored zurück (Go-Side, ohne Loader). Der neue `/loaded` ist explizit „nach Loader-Hydration". Klarer Unterschied im Spec dokumentieren.

## Phase-2-Befunde (Recherche-Ergebnisse)

### Korrektur: Python-Backend ist FastAPI auf Port 8000, nicht NiceGUI auf 8080

`PYTHON_CORE_URL` zeigt auf `http://localhost:8000` (`internal/config/config.go:7`). Das ist der **FastAPI-Wrapper** in `api/main.py`, NICHT die NiceGUI-App. NiceGUI hört auf Port 8080 und ist nicht im Proxy-Pfad.

Bestehende Routen-Struktur:
- `api/main.py` registriert Router: `health, config, forecast, gpx, scheduler, compare, notify`
- Pattern (`api/routers/notify.py:24-28`):
  ```python
  @router.post("/api/notify/test")
  async def test_notify(req: TestRequest, user_id: str = Query(...)):
      settings = Settings().with_user_profile(user_id)
  ```

### Go-Proxy-Pattern für URL-Params

`ProxyHandler(pythonURL, path)` aus `internal/handler/proxy.go:41` nimmt nur fixe Pfade. Für `{id}`-Param brauchen wir einen eigenen Handler, der `chi.URLParam(r, "id")` extrahiert und die Python-URL dynamisch baut. Vorbild: `CompareProxyHandler` (`proxy.go:71-98`) mit `appendUserID` (`proxy.go:137-145`).

Auth ist global aktiviert (`cmd/server/main.go:49-51`), neue Routes sind automatisch geschützt — `_internal`-Pfade NICHT in die Whitelist (`internal/middleware/auth.go:34-39`) eintragen.

### User-Scope im Loader

`load_all_trips(user_id)` (`src/app/loader.py:520`) filtert per User. Wir können nach `trip_id` aus dieser Liste suchen — sauberer als manuell den Pfad zu konstruieren.

## Empfehlung (Tech-Lead)

**Drei kleine Änderungen:**

1. **Python:** Neuer Router `api/routers/internal.py`
   ```python
   @router.get("/api/_internal/trip/{trip_id}/loaded")
   async def loaded_trip(trip_id: str, user_id: str = Query(...)):
       trip = next((t for t in load_all_trips(user_id) if t.id == trip_id), None)
       if trip is None:
           raise HTTPException(404, f"Trip {trip_id} nicht gefunden für User {user_id}")
       return _trip_to_dict(trip)
   ```
   In `api/main.py` einbinden: `app.include_router(internal.router)`.

2. **Go:** Neuer Handler `LoadedTripProxyHandler` in `internal/handler/proxy.go`
   ```go
   func LoadedTripProxyHandler(pythonURL string) http.HandlerFunc {
       return func(w http.ResponseWriter, r *http.Request) {
           id := chi.URLParam(r, "id")
           query := appendUserID("", middleware.UserIDFromContext(r.Context()))
           url := pythonURL + "/api/_internal/trip/" + id + "/loaded?" + query
           // ... standard proxy forwarding (siehe ProxyHandler)
       }
   }
   ```

3. **Go:** Route registrieren in `cmd/server/main.go`
   ```go
   r.Get("/api/_internal/trip/{id}/loaded", handler.LoadedTripProxyHandler(cfg.PythonCoreURL))
   ```
   Auth automatisch durch globale Middleware. Whitelist NICHT anpassen.

## Scope

- **Dateien:** 4 — `api/routers/internal.py` (neu), `api/main.py` (1 Zeile), `internal/handler/proxy.go` (+ Handler), `cmd/server/main.go` (1 Zeile)
- **LoC:** ~50 (~20 Python, ~30 Go)
- Unter Limit (5 Dateien / 250 LoC).

## Risiken

1. **`_trip_to_dict` rohe Rückgabe:** Existing helper. Falls darin später Felder fehlen, ist auch unser Endpoint betroffen — aber das ist die kanonische Serialisierung, also korrekt. Kein zusätzlicher Code, kein Risiko.
2. **trip_id-Eindeutigkeit:** `load_all_trips` durchläuft `glob("*.json")`. Bei doppelten IDs nimmt unser `next(...)` den ersten Treffer. Sollte bei einer User-Scope nicht passieren.
3. **Cross-User-Schutz:** `user_id` kommt aus dem Auth-Context (Go-Middleware), nicht vom Client. Validator kann nur seinen eigenen User-Scope abfragen — gut.
4. **Python-Service-Restart:** Die FastAPI-App muss neu starten, damit der neue Router aktiv ist. `gregor-python-staging` wird durch `auto-deploy-gregor-staging.sh` schon restartet.

## Nächster Schritt

`/3-write-spec` — formale Spec für `validator_internal_loaded_endpoint`.
