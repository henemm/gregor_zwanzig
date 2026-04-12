# Context: Go API Setup (M1)

## Request Summary

Go REST API als dünne HTTP-Schicht aufsetzen, die den bestehenden Python-Core wrapppt. Erster Schritt der Hybrid-Migration (Go API + SvelteKit Frontend, Python-Core bleibt).

## Related Files

| File | Relevance |
|------|-----------|
| `src/web/main.py` | Aktuelle NiceGUI-App — definiert alle Routen (/, /locations, /trips, /compare, /subscriptions, /settings, /gpx-upload) + Health-Check + Scheduler-Init |
| `src/web/scheduler.py` | Background-Scheduler (APScheduler) — Morning/Evening Cron, Trip Reports, Alerts, Inbound Email Poll. Muss nach Go portiert werden (M5) |
| `src/web/pages/*.py` | NiceGUI-Pages — UI-Logik die durch SvelteKit ersetzt wird (M3/M4) |
| `src/app/models.py` | DTOs: ForecastDataPoint, NormalizedTimeseries, Risk*, TripReport, TripReportConfig, WeatherChange, etc. (~586 LOC) — Go API muss diese als JSON serialisieren |
| `src/app/config.py` | Settings (Pydantic) — Env-Vars mit GZ_ Prefix, SMTP, SMS, Signal Config |
| `src/app/user.py` | User-Model: SavedLocation, Subscriptions (Location/Trip/Compare), UserPreferences |
| `src/app/loader.py` | JSON CRUD — load/save für Trips, Locations, CompareSubscriptions. Filesystem-basiert (data/users/{user_id}/) |
| `src/app/trip.py` | Trip-Model: Stages, Waypoints, TimeWindows, AggregationConfig |
| `src/app/metric_catalog.py` | MetricCatalog — alle verfügbaren Wetter-Metriken mit Defaults |
| `src/providers/*.py` | Weather Provider (OpenMeteo, GeoSphere) — bleiben Python |
| `src/services/*.py` | Business-Logik (Risk Engine, Forecast, Aggregation, etc.) — bleiben Python |
| `src/formatters/*.py` | Report-Formatter (Email HTML, SMS, Trip Report) — bleiben Python |
| `src/outputs/*.py` | Output-Channels (Email/Resend, Signal/Callmebot, Console) — bleiben Python |
| `docs/reference/api_contract.md` | DTO-Spezifikation (Single Source of Truth) |

## Existing Patterns

### Daten-Persistenz
- **Filesystem-basiert**: JSON-Dateien unter `data/users/{user_id}/`
  - `locations/*.json` — einzelne Location-Files
  - `trips/*.json` — einzelne Trip-Files
  - `compare_subscriptions.json` — alle Subscriptions in einer Datei
  - `weather_snapshots/` — gecachte Forecasts
- **Kein DB** — bewusste Entscheidung, einfach gehalten
- Go API muss entweder: (a) diese JSON-Files direkt lesen/schreiben, oder (b) Python-Core via HTTP fragen

### Routing / Pages
- 7 Pages: Dashboard, Locations, Trips, GPX Upload, Compare, Subscriptions, Settings
- Health-Check auf `/_health` (gibt UUID zurück für Restart-Detection)
- NiceGUI nutzt Starlette unter der Haube

### Scheduler
- APScheduler (BackgroundScheduler)
- 5 Jobs: Morning (07:00), Evening (18:00), Trip Reports (stündlich), Alerts (30min), Inbound Email (5min)
- BetterStack Heartbeat nach Morning/Evening

### Config
- Pydantic BaseSettings mit `GZ_` Prefix
- `.env` Datei für Secrets (SMTP, Signal, etc.)

## Dependencies

### Upstream (was Python-Core nutzt)
- `httpx` — HTTP-Client für API-Calls
- `pydantic` / `pydantic-settings` — Config
- `apscheduler` — Scheduler
- `nicegui` — Web UI (wird ersetzt)
- `gpxpy` — GPX-Parsing
- `astral` — Sonnenauf-/untergang

### Downstream (was den Python-Core nutzt)
- Aktuell: NiceGUI Pages rufen Services direkt auf
- Nach Migration: Go API ruft Python-Core via HTTP auf

## Existing Specs

- `docs/specs/modules/scheduler.md` — Scheduler-Spec
- `docs/specs/modules/trip_report_scheduler.md` — Trip Report Scheduler
- `docs/reference/api_contract.md` — DTO-Spezifikation

## Architektur-Entscheidungen

### Go-Python Anbindung
Die zentrale Entscheidung: Wie kommuniziert Go mit Python?

**Option A: Python als interner HTTP-Service (Favorit)**
- FastAPI/Litestar Wrapper um bestehende Services
- Go ruft `http://localhost:8081/api/...` auf
- Vorteile: Saubere Trennung, unabhängig testbar, Python-Prozess kann unabhängig restarten
- Nachteile: Zwei Prozesse in Produktion

**Option B: Python CLI-Aufrufe**
- Go ruft `python -m src.app.cli --report morning --format json` auf
- Vorteile: Einfach, CLI existiert
- Nachteile: Startup-Overhead pro Aufruf, kein Streaming

**Option C: Shared Filesystem**
- Go schreibt Requests als JSON, Python pollt und verarbeitet
- Nachteile: Zu komplex, Polling-Delay

### REST API Endpoints (Vorläufig)
Basierend auf den NiceGUI-Pages:

```
GET  /api/locations              — Alle Locations
POST /api/locations              — Location anlegen
PUT  /api/locations/{id}         — Location bearbeiten
DEL  /api/locations/{id}         — Location löschen

GET  /api/trips                  — Alle Trips
POST /api/trips                  — Trip anlegen
PUT  /api/trips/{id}             — Trip bearbeiten
DEL  /api/trips/{id}             — Trip löschen
POST /api/trips/{id}/gpx         — GPX hochladen

GET  /api/subscriptions          — Alle Compare-Subscriptions
POST /api/subscriptions          — Subscription anlegen
PUT  /api/subscriptions/{id}     — Subscription bearbeiten
DEL  /api/subscriptions/{id}     — Subscription löschen

GET  /api/weather/{location_id}  — Forecast für Location
GET  /api/compare                — Ski-Resort-Vergleich
POST /api/reports/morning        — Morning Report triggern
POST /api/reports/evening        — Evening Report triggern

GET  /api/health                 — Health-Check
GET  /api/scheduler/status       — Scheduler-Status
```

## Risks & Considerations

1. **Serialisierung**: Python-Dataclasses → JSON → Go-Structs. Die DTOs sind komplex (verschachtelte Dataclasses, Enums, Optional-Felder). OpenAPI-Spec als Contract ist wichtig.
2. **Zwei Prozesse**: Systemd muss Go-Service + Python-Service managen. Go depends-on Python.
3. **Auth**: Aktuell kein Auth (Single-User). Go bringt Auth-Middleware mit (M2). Python-Service muss nicht auth-aware sein (nur von localhost erreichbar).
4. **Filesystem-Zugriff**: Sowohl Go als auch Python lesen/schreiben `data/users/`. Race Conditions bei gleichzeitigem Zugriff? → Python-HTTP-Service als einziger Schreiber.
5. **Migration-Zeitraum**: Während der Migration laufen NiceGUI + Go API parallel. Nginx muss sauber routen.
