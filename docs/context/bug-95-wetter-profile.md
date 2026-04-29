---
bug_id: 95
title: "Wetter-Profile Dropdown leer (Trip-Wizard Step 3)"
created: 2026-04-29
status: analyzed
---

# Context: Bug #95 — Wetter-Profile Dropdown leer

## Symptom

Im Trip-Wizard Step 3 (`Wetter-Profil`) ist die Dropdown-Liste leer. Nur „Kein Profil" sichtbar, keine 7 Templates (Alpen-Trekking, Wandern, Skitouren, Wintersport, Radtour, Wassersport, Allgemein).

## User-Hypothese

„Wetter-Profile sind spezifiziert aber nicht umgesetzt."

## Tatsächliche Lage: Code IST vollständig implementiert

| Layer | Datei | Zeile | Status |
|-------|-------|-------|--------|
| Python Registry | `src/app/metric_catalog.py` | 381 | ✅ `WEATHER_TEMPLATES` mit 7 Einträgen |
| Python Endpoint | `api/routers/config.py` | 23 | ✅ `GET /templates` |
| Go Proxy | `cmd/server/main.go` | 67 | ✅ `r.Get("/api/templates", ...)` |
| Frontend Fetch | `frontend/src/lib/components/wizard/WizardStep3Weather.svelte` | 114 | ✅ `api.get<Template[]>('/api/templates')` |

Direkt-Call gegen Python-Core (Port 8000) liefert korrekt 7 Templates.

## Root Cause: Stale Go-Binary

| Artifact | Datum |
|----------|-------|
| F76 Merge (Templates Spec → Code) | 2026-04-20 11:58 UTC |
| Go-Binary `/home/hem/gregor_zwanzig/gregor-api` mtime | **2026-04-18 16:46 UTC** |
| `gregor-api.service` Active seit | 2026-04-23 13:35 UTC (mit altem Binary) |

Das deployte Go-Binary wurde **vor** dem F76-Merge gebaut. Es kennt die Route `/api/templates` nicht.

**Beweis aus Service-Log (`journalctl -u gregor-api`):**
```
2026/04/29 04:26:55 "GET http://localhost:8090/api/templates HTTP/1.1" - 404 19B
```

Mit Auth-Cookie: 404 (Route fehlt). Ohne Auth-Cookie: 401 (AuthMiddleware blockiert vor Routing).

Frontend hat `.catch(() => [] as Template[])` → bei 404 wird Liste leer → Dropdown leer.

## Fix

```bash
cd /home/hem/gregor_zwanzig
go build -o gregor-api ./cmd/server
sudo systemctl restart gregor-api.service
```

Kein Code-Change nötig.

## Test (Verify Fix)

1. Nach Restart: `curl -sb cookie http://127.0.0.1:8090/api/templates` → JSON-Array mit 7 Einträgen
2. Browser: Trip-Wizard Step 3 öffnen → Dropdown enthält 7 Profile
3. Hard-Reload Safari (Cmd+Shift+R) zur Sicherheit

## Effort

**Small** — Rebuild + Restart, ~30 Sekunden.

## Lessons / Process-Frage

Warum hat das Deploy von F76 das Go-Binary nicht rebuilt? → Deployment-Pipeline-Audit empfohlen, aber out-of-scope für diesen Bug.
