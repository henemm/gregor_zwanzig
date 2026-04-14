---
entity_id: gpx_proxy
type: module
created: 2026-04-14
updated: 2026-04-14
status: implemented
version: "1.0"
tags: [gpx, proxy, go, fastapi, multipart, pipeline]
---

# GPX Proxy

## Approval

- [x] Approved

## Purpose

Go-Handler und Python-FastAPI-Router, die zusammen das Parsen von GPX-Dateien aus dem SvelteKit-Frontend ermoeglichen. Der Go-Handler nimmt die Multipart-Anfrage entgegen und leitet sie an den Python-Endpunkt weiter, der `gpx_to_stage_data()` aufruft und Stage-Daten mit Waypoints als JSON zurueckgibt.

## Scope

### In Scope
- Python FastAPI Router `api/routers/gpx.py` mit POST `/api/gpx/parse`
- Lazy Import von NiceGUI-Abhaengigkeiten innerhalb der Route-Funktion
- Go `GpxProxyHandler` in `internal/handler/proxy.go` mit Multipart- und Query-Param-Forwarding
- 30-Sekunden-Timeout fuer grosse GPX-Dateien
- Route-Registrierung in `cmd/server/main.go`
- Fehler-Handling: 400 bei fehlender/ungueltiger GPX, 503 bei Python nicht erreichbar

### Out of Scope
- GPX-Datei-Verwaltung (Speichern, Loeschen, Auflisten)
- Authentifizierung / Benutzer-Isolation
- Batch-Upload mehrerer GPX-Dateien
- Veraenderung der GPX-Parsing-Pipeline selbst

## Architecture

```
SvelteKit
    │
    └── POST /api/gpx/parse (multipart/form-data)
            │
            ▼
    Go Handler (:8090)
    internal/handler/proxy.go
    GpxProxyHandler
            │  multipart + query params weiterleiten
            │  30s Timeout
            ▼
    Python FastAPI (:8000)
    api/routers/gpx.py
    POST /api/gpx/parse
            │
            ▼
    gpx_to_stage_data()
    src/web/pages/trips.py
            │  GPX-Parsing-Pipeline:
            │  gpx_parser → segment_builder →
            │  elevation_analysis → hybrid_segmentation
            ▼
    JSON Response → Go → SvelteKit
```

## Source

### Go Handler (Erweiterung bestehender Datei)
- **File:** `internal/handler/proxy.go`
- **Identifier:** `GpxProxyHandler` (neu hinzufuegen)

### Python Router (neue Datei)
- **File:** `api/routers/gpx.py` **(NEU — wird in dieser Spec erstellt)**
- **Identifier:** `router` (FastAPI APIRouter), `parse_gpx()`

### Registrierung (bestehende Dateien erweitern)
- **Go:** `cmd/server/main.go` — Route `POST /api/gpx/parse` → `GpxProxyHandler` (1 Zeile hinzufuegen)
- **Python:** `api/main.py` — `app.include_router(gpx.router)` (2 Zeilen hinzufuegen)

## Endpoints

### POST /api/gpx/parse

**Request:**
- Content-Type: `multipart/form-data`
- Body field `file`: GPX-Datei (`.gpx`)
- Query-Param `stage_date` (optional): `YYYY-MM-DD`, wird an Python weitergeleitet
- Query-Param `start_hour` (optional): Integer, default `8`, wird an Python weitergeleitet

**Response 200:**
```json
{
  "name": "Tag 1: von Valldemossa nach Deià",
  "date": "2026-04-14",
  "waypoints": [
    {
      "id": "G1",
      "name": "Puig des Teix",
      "lat": 39.752,
      "lon": 2.785,
      "elevation_m": 1064,
      "time_window": "08:00-10:00"
    }
  ]
}
```

**Response 422:** Kein File-Field oder ungueltige Query-Params (FastAPI Validation)
```json
{"detail": [{"type": "missing", "loc": ["body", "file"], "msg": "Field required"}]}
```

**Response 400:** GPX nicht parsebar oder leere Datei
```json
{"detail": "Ungueltiges GPX-Format: ..."}
```

**Response 503:** Python-Backend nicht erreichbar
```json
{"error": "core_unavailable"}
```

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `go-chi/chi/v5` | go module | HTTP Router fuer Route-Registrierung |
| `net/http` | go stdlib | Multipart-Request bauen und an Python senden |
| Python FastAPI | service | Backend auf localhost:8000 |
| `gpxpy` | python package | GPX-Datei einlesen (via bestehende Pipeline) |
| `src/web/pages/trips.gpx_to_stage_data` | python function | Kern-Pipeline: GPX → Stage + Waypoints |
| `api/routers/gpx.py` | python module | FastAPI Router (neu) |

## Implementation Details

### Python Router (`api/routers/gpx.py`)

```python
from fastapi import APIRouter, UploadFile, File, Query, HTTPException
from typing import Optional
from datetime import date

router = APIRouter()

@router.post("/api/gpx/parse")
async def parse_gpx(
    file: UploadFile = File(...),
    stage_date: Optional[date] = Query(None),
    start_hour: int = Query(8, ge=0, le=23),
):
    # Lazy Import um NiceGUI-Abhaengigkeiten beim Modul-Load zu vermeiden
    from src.web.pages.trips import gpx_to_stage_data

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="no_file_content")

    try:
        # gpx_to_stage_data(content: bytes, filename: str, stage_date, start_hour)
        result = gpx_to_stage_data(content, file.filename, stage_date, start_hour)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result
```

### Go Handler (`internal/handler/proxy.go`)

```go
// GpxProxyHandler leitet POST /api/gpx/parse (Multipart) an Python weiter.
// Query-Params (stage_date, start_hour) werden unveraendert weitergeleitet.
// Content-Type (inkl. Multipart-Boundary) wird 1:1 kopiert.
func GpxProxyHandler(pythonURL string) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        client := &http.Client{Timeout: 30 * time.Second}

        url := pythonURL + "/api/gpx/parse"
        if r.URL.RawQuery != "" {
            url += "?" + r.URL.RawQuery
        }

        req, err := http.NewRequestWithContext(r.Context(), http.MethodPost, url, r.Body)
        if err != nil {
            w.Header().Set("Content-Type", "application/json")
            w.WriteHeader(500)
            w.Write([]byte(`{"error":"proxy_error"}`))
            return
        }
        req.Header.Set("Content-Type", r.Header.Get("Content-Type"))

        resp, err := client.Do(req)
        if err != nil {
            w.Header().Set("Content-Type", "application/json")
            w.WriteHeader(503)
            w.Write([]byte(`{"error":"core_unavailable"}`))
            return
        }
        defer resp.Body.Close()

        w.Header().Set("Content-Type", resp.Header.Get("Content-Type"))
        w.WriteHeader(resp.StatusCode)
        io.Copy(w, resp.Body)
    }
}
```

### Route-Registrierung (`cmd/server/main.go`)

```go
r.Post("/api/gpx/parse", handler.GpxProxyHandler)
```

### Router-Registrierung (`api/main.py`)

```python
from api.routers import gpx
app.include_router(gpx.router)
```

## Expected Behavior

- **Input:** SvelteKit sendet `POST /api/gpx/parse` mit GPX-Datei als Multipart-Field `file`; optionale Query-Params `stage_date=2026-01-17&start_hour=8`
- **Output:** JSON mit `name`, `date`, `waypoints[]` (je `id`, `name`, `lat`, `lon`, `elevation_m`, `time_window`)
- **Side effects:** GPX-Datei wird temporaer auf Disk geschrieben (in Python) und nach dem Parsen geloescht; GPX-Datei wird ausserdem durch `gpx_to_stage_data()` moeglicherweise im Nutzer-Verzeichnis persistiert (bestehendes Verhalten der Pipeline, wird akzeptiert)

### Error Cases

| Szenario | HTTP Status | Body |
|----------|-------------|------|
| Kein `file`-Field im Request | 422 | `{"detail": [{"type": "missing", ...}]}` (FastAPI Validation) |
| Leere GPX-Datei | 400 | `{"detail": "no_file_content"}` |
| GPX-Datei nicht parsebar | 400 | `{"detail": "Ungueltiges GPX-Format: ..."}` |
| Python-Backend nicht erreichbar | 503 | `{"error": "core_unavailable"}` |
| Timeout (> 30s) | 503 | `{"error": "core_unavailable"}` |

## Known Limitations

- NiceGUI-Import in `trips.py` erfordert Lazy Import in der Route-Funktion; bei Refactoring von `trips.py` muss geprueft werden ob der Lazy Import noch notwendig ist
- Disk-Seiteneffekt (temporaere GPX-Datei + ggf. Pipeline-Persistenz) ist akzeptiertes Verhalten, kein Aufraeum-Mechanismus fuer Pipeline-Artefakte
- Kein Streaming: GPX-Datei wird vollstaendig im Speicher gehalten bevor sie weitergeleitet wird; bei sehr grossen Dateien (> 32 MB) wird auf Disk ausgelagert
- `pythonBaseURL` wird aus bestehender Konfiguration uebernommen (analog zu anderen Proxy-Handlern)

## Changelog

- 2026-04-14: Initial spec (M5a — GPX Proxy, Go + Python FastAPI)
- 2026-04-14: Status → implemented; files api/routers/gpx.py (NEW), api/main.py, internal/handler/proxy.go, cmd/server/main.go
- 2026-04-14: Error Cases an FastAPI-Standardverhalten angepasst (422 statt 400 bei fehlendem File, detail-Format)
