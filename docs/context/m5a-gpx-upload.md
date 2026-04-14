# Context: M5a GPX Upload — Python-Proxy

## Request Summary
Go-Endpoint für GPX-Upload via Python-Proxy: GPX-Datei hochladen, an bestehende Python-Pipeline weiterleiten, Stage/Waypoints zurückgeben.

## Entscheidung: Python-Proxy statt Go-Neuimplementierung

Die vollständige Segmentierungslogik (Naismith's Rule + Elevation Detection + Hybrid Optimization) ist ~500+ LOC in Python. Statt alles in Go neu zu schreiben: Go-Endpoint nimmt GPX entgegen, leitet an Python `gpx_to_stage_data()` weiter. ~85 LOC total, 4 Dateien.

## Architektur

```
SvelteKit → Go POST /api/gpx/parse (Multipart) → Python POST /api/gpx/parse → gpx_to_stage_data() → JSON Response
```

## Implementierungsplan

### Dateien (4 Stück, ~85 LOC)

| Datei | Änderung |
|-------|----------|
| `api/routers/gpx.py` | **NEU** — FastAPI-Router, nimmt Multipart (GPX file + query params), ruft `gpx_to_stage_data()` |
| `api/main.py` | +2 Zeilen: Import + `app.include_router(gpx.router)` |
| `internal/handler/proxy.go` | +30 LOC: `GpxProxyHandler` — POST+Multipart+Query-Params Forwarding, 30s Timeout |
| `cmd/server/main.go` | +1 Zeile: `r.Post("/api/gpx/parse", handler.GpxProxyHandler(cfg.PythonCoreURL))` |

### Reihenfolge
1. `api/routers/gpx.py` — FastAPI-Endpoint erstellen
2. `api/main.py` — Router registrieren
3. `internal/handler/proxy.go` — Go-Proxy-Handler
4. `cmd/server/main.go` — Route registrieren

## Input/Output

**Request:** `POST /api/gpx/parse`
- Body: `multipart/form-data` mit GPX-Datei
- Query-Params: `stage_date` (optional, YYYY-MM-DD), `start_hour` (optional, default 8)

**Response (200):**
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

**Errors:** 400 (bad GPX), 503 (Python unavailable)

## Risiken & Mitigationen

| Risiko | Mitigation |
|--------|-----------|
| NiceGUI-Import in `trips.py` | Lazy Import innerhalb der Route-Funktion |
| Disk-Seiteneffekt (GPX wird gespeichert) | Akzeptiertes Verhalten, gleich wie NiceGUI-UI |
| Timeout bei großen GPX-Dateien | 30s Timeout im Go-Proxy |

## Was NICHT geändert wird

- `internal/model/trip.go` — Stage/Waypoint-Structs matchen bereits
- `internal/store/` — Endpoint ist parse-only
- Auth-Middleware — greift automatisch

## Related Files

| File | Relevance |
|------|-----------|
| `src/web/pages/trips.py:31-76` | `gpx_to_stage_data()` — die Python-Funktion |
| `src/web/pages/gpx_upload.py` | `process_gpx_upload()`, `compute_full_segmentation()`, `segments_to_trip()` |
| `src/core/gpx_parser.py` | GPX-Parser (gpxpy) |
| `src/core/segment_builder.py` | Naismith's Rule Segmentierung |
| `src/core/elevation_analysis.py` | Waypoint Detection |
| `src/core/hybrid_segmentation.py` | Boundary Optimization |
| `internal/handler/proxy.go` | Bestehendes Go↔Python Proxy-Pattern |
| `cmd/server/main.go` | Go-Router-Setup |
| `api/main.py` | FastAPI-App |
| `api/routers/forecast.py` | Referenz für neuen Router |

## Existing Specs
- `docs/specs/modules/gpx_parser.md`
- `docs/specs/modules/gpx_upload.md`
- `docs/specs/modules/segment_builder.md`
- `docs/specs/modules/hybrid_segmentation.md`
- `docs/specs/modules/elevation_analysis.md`
- `docs/specs/modules/go_proxy_binary.md`
