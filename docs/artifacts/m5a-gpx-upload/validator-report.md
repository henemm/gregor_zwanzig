# External Validator Report

**Spec:** docs/specs/modules/gpx_proxy.md
**Datum:** 2026-04-14T06:37:00Z
**Server:** https://gregor20.henemm.com (+ localhost:8090/8000)

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | POST /api/gpx/parse mit GPX-Datei liefert JSON mit name, date, waypoints[] | Python OpenAPI zeigt nur 3 Routen: /health, /config, /forecast. GPX-Route existiert NICHT. Alle Requests liefern `{"detail":"Not Found"}` HTTP 404. | **FAIL** |
| 2 | Query-Params stage_date und start_hour werden akzeptiert | Nicht testbar — Route existiert nicht (404) | **FAIL** |
| 3 | Kein file-Field im Request liefert 400 mit error/detail | Nicht testbar — Route existiert nicht (404) | **FAIL** |
| 4 | Ungueltige GPX-Datei liefert 400 | Nicht testbar — Route existiert nicht (404) | **FAIL** |
| 5 | Python nicht erreichbar liefert 503 mit core_unavailable | Go-Proxy leitet an Python weiter, Python antwortet 404 (Route fehlt). Go gibt den 404 transparent durch statt 503. | **FAIL** |

## Findings

### Finding 1: Python-Route /api/gpx/parse nicht registriert (CRITICAL)
- **Severity:** CRITICAL
- **Expected:** `POST /api/gpx/parse` existiert als registrierte FastAPI-Route in Python (api/main.py includet gpx.router)
- **Actual:** Python-OpenAPI listet nur 3 Routen: `/health`, `/config`, `/forecast`. Die GPX-Route fehlt komplett. Direkte Requests an `http://localhost:8000/api/gpx/parse` liefern `{"detail":"Not Found"}` (404).
- **Evidence:** `curl -s http://localhost:8000/openapi.json` → `["/health", "/config", "/forecast"]`; `curl -X POST http://localhost:8000/api/gpx/parse -F file=@test.gpx` → 404

### Finding 2: Go-Route existiert, Python-Route fehlt — Chain ist broken
- **Severity:** CRITICAL
- **Expected:** Go leitet Multipart-Request an Python weiter, Python parst GPX und liefert JSON
- **Actual:** Go-Auth greift (401 ohne Cookie, durchlass mit Cookie). Go leitet an Python weiter. Python antwortet 404. Gesamter Chain ist non-functional.
- **Evidence:** Mit Auth-Cookie: `curl -X POST http://localhost:8090/api/gpx/parse -b gz_session=... -F file=@test.gpx` → `{"detail":"Not Found"}` (404)

### Finding 3: Server moeglicherweise nicht neu gestartet nach Implementation
- **Severity:** HIGH
- **Expected:** Nach Code-Aenderung wird der Python-Server (uvicorn) neu gestartet, damit neue Routen aktiv sind
- **Actual:** Python-Prozess (PID 2301305) laeuft seit Apr 12, also 2 Tage vor dem Spec-Datum (Apr 14). Der Router wurde entweder nicht in api/main.py registriert, oder der Server wurde nach der Aenderung nicht neu gestartet.
- **Evidence:** `ps aux | grep uvicorn` zeigt Start-Datum Apr 12

## Verdict: BROKEN

### Begruendung

Der gesamte GPX-Proxy-Chain ist **nicht funktional** auf dem laufenden Server. Die Python-Route `/api/gpx/parse` existiert nicht — weder in der OpenAPI-Spec noch als tatsaechlicher Endpoint. Kein einziger Expected-Behavior-Punkt aus der Spec ist erfuellbar. Die wahrscheinlichste Ursache ist, dass der GPX-Router nicht in `api/main.py` registriert wurde oder der Python-Server nach der Implementation nicht neu gestartet wurde. Alle 5 Testpunkte: **FAIL**.
