# Context: Go Proxy Binary

## Request Summary
Go HTTP-Server mit Chi Router als externen Proxy vor dem Python FastAPI Wrapper. Vervollstaendigt M1 (Proof-of-Concept: Go ruft Python auf, Response kommt durch).

## Related Files
| File | Relevance |
|------|-----------|
| `api/main.py` | Python FastAPI App — das Backend das Go proxied |
| `api/routers/health.py` | GET /health → {"status": "ok", "version": "0.1.0"} |
| `api/routers/config.py` | GET /config → Settings ohne Secrets |
| `api/routers/forecast.py` | GET /forecast?lat=&lon=&hours= → NormalizedTimeseries JSON |
| `docs/specs/modules/go_api_setup.md` | Spec mit Architektur, Endpoints, Error-Handling |

## Existing Patterns
- Python FastAPI laeuft auf localhost:8000 (nur intern)
- Go soll auf :8090 laufen (extern, zum Testen neben NiceGUI auf :8080)
- Alle Endpoints unter /api/ Prefix in Go

## Dependencies
- Go 1.22.2 installiert
- Chi Router (go-chi/chi/v5) — leichtgewichtiger HTTP-Router
- Python FastAPI auf localhost:8000 muss laufen

## Existing Specs
- `docs/specs/modules/go_api_setup.md` — definiert Go-Seite (Architektur, Proxy-Logik, Health-Retry)

## Go-Proxy Verhalten (aus Spec)
1. GET /api/health → eigenes JSON + Python-Health-Check
2. GET /api/config → Proxy zu Python /config
3. GET /api/forecast?lat=&lon=&hours= → Proxy zu Python /forecast
4. Python nicht erreichbar → 503 {"error": "core_unavailable"}
5. Startup: 3 Retries gegen Python /health (je 1s Pause)

## Risks
- Go-Tests brauchen laufenden Python-Server (oder MockServer)
- Chi Router muss als Dependency gemanagt werden (go.mod)
