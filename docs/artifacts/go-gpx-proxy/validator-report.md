# External Validator Report

**Spec:** docs/specs/modules/gpx_proxy.md
**Datum:** 2026-04-14T06:30:00Z
**Server:** https://gregor20.henemm.com (Go :8090, Python :8000)

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | POST /api/gpx/parse mit GPX-Datei → JSON mit name, date, waypoints[] | Go: 404 (Route nicht registriert), Python: 404 (Router nicht geladen) | **FAIL** |
| 2 | Query-Params stage_date, start_hour werden akzeptiert | Nicht testbar — Endpoint existiert nicht | **FAIL** |
| 3 | Kein file-Field → 400 | Nicht testbar — Endpoint existiert nicht | **FAIL** |
| 4 | Ungueltige GPX → 400 | Nicht testbar — Endpoint existiert nicht | **FAIL** |
| 5 | Python nicht erreichbar → 503 | Nicht testbar — Endpoint existiert nicht | **FAIL** |

## Findings

### Finding 1: Go-Binary nicht neugebaut — Route fehlt
- **Severity:** CRITICAL
- **Expected:** POST /api/gpx/parse ist auf dem Go-Server (Port 8090) erreichbar
- **Actual:** Go-Server antwortet mit `404 page not found` (nach erfolgreicher Auth)
- **Evidence:** 
  - Binary-Timestamp: `2026-04-13 08:21:05` 
  - Source-Timestamp (`cmd/server/main.go`): `2026-04-14 06:04:57`
  - Source-Timestamp (`internal/handler/proxy.go`): `2026-04-14 06:04:48`
  - Der laufende Go-Prozess (pid 2677479, gestartet 2026-04-13 12:46) basiert auf dem alten Binary ohne GPX-Route

### Finding 2: Python-Router nicht geladen
- **Severity:** CRITICAL
- **Expected:** FastAPI-Router `/api/gpx/parse` ist auf Python-Backend (Port 8000) registriert
- **Actual:** Python OpenAPI listet nur `/health`, `/config`, `/forecast` — kein `/api/gpx/parse`
- **Evidence:**
  - `curl http://localhost:8000/api/gpx/parse` → `{"detail":"Not Found"}` (404)
  - `api/main.py` modifiziert am 2026-04-14 06:04:38
  - `api/routers/gpx.py` erstellt am 2026-04-14 06:04:33
  - Service `gregor_zwanzig.service` zuletzt gestartet: 2026-04-13 19:59:22
  - Weder Go-Binary neugebaut noch Python-Service neugestartet seit Code-Aenderung

### Finding 3: Feature ist nicht deployed
- **Severity:** CRITICAL
- **Expected:** Feature ist auf https://gregor20.henemm.com erreichbar
- **Actual:** Externe URL gibt 401 (Auth) zurueck, aber selbst mit gueltigem Session-Cookie wuerde der Go-Server 404 liefern
- **Evidence:** Alle Code-Aenderungen existieren nur auf Disk, nicht im laufenden System

## Verdict: BROKEN

### Begruendung

Das Feature **existiert nur als nicht-kompilierter/nicht-geladener Quellcode**. Kein einziger Expected-Behavior-Punkt ist testbar, da weder der Go-Server die Route kennt noch der Python-Server den Router geladen hat.

**Ursache:** Die Go-Binary wurde seit den Code-Aenderungen nicht neu gebaut (`go build`), und der Python-Service wurde nicht neugestartet. Die Implementierung auf Code-Ebene mag korrekt sein, aber das Feature ist **nicht deployed** und somit aus Sicht der laufenden App **nicht existent**.

**Erforderliche Schritte vor erneuter Validierung:**
1. Go-Binary neu bauen: `cd cmd/server && go build -o ../../gregor-api`
2. Go-Prozess neustarten
3. Python-Service neustarten: `systemctl restart gregor_zwanzig`
4. Erneute Validierung nach Neustart beider Services
