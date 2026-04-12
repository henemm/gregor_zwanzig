# Migrationsplan: Python/NiceGUI → Go/SvelteKit

**Erstellt:** 2026-04-12
**Status:** Entscheidungen getroffen — bereit für M1

## Ist-Zustand

| Package | LOC | Beschreibung |
|---------|-----|-------------|
| `src/app/` | ~3.400 | Kern-DTOs, Config, Datenmodell |
| `src/providers/` | ~1.450 | Wetter-APIs (OpenMeteo, GeoSphere) |
| `src/services/` | ~5.030 | Business-Logik (Risk Engine, Alerts, etc.) |
| `src/formatters/` | ~1.990 | HTML/SMS Report-Generierung |
| `src/core/` | ~716 | GPX-Verarbeitung |
| `src/outputs/` | ~350 | E-Mail, Signal |
| `src/web/` | ~5.460 | NiceGUI Web-UI (9 Pages) |
| **Gesamt** | **~18.630** | 67 Python-Dateien + ~20.400 LOC Tests |

## Strategie: Phased Incremental

- **Kein Big Bang** — Python läuft in Produktion bis Go+SvelteKit komplett ist
- **Backend-first, Frontend-second**
- **Golden-File Regression:** Python-Output als JSON speichern, Go-Output dagegen vergleichen
- **Ziel:** Maximal 8 Wochen

## Abhängigkeitsgraph

```
M1 (Go Setup)
 ├── M2 (Provider) → M3 (Risk Engine) → M4 (Formatter + Scheduler)
 │                                              │
 └── M5 (SvelteKit Setup + Auth) ──────────── M6 (Pages portieren)
                                                │
                                                M7 (Cutover)
```

**Kritischer Pfad:** M1 → M2 → M3 → M4 → M6 → M7
**Parallelisierbar:** M5 kann parallel zu M2-M4 laufen

## Phase M1: Go-Backend Setup (2-3 Tage)

**Issue:** #22 | **Abhängigkeiten:** Keine

- `go mod init github.com/henemm/gregor-api`
- Projektstruktur: `cmd/server/`, `cmd/cli/`, `internal/`, `api/`
- Chi Router + Middleware (CORS, Logging, Recovery)
- Config mit `envconfig` (GZ_ Prefix beibehalten)
- JSON Store — muss bestehendes `data/users/` Format lesen
- Health-Endpoint + Smoke-Test CRUD für Trips
- Systemd-Unit `gregor-api.service` vorbereiten (Port 8081)

**Kritisch:** JSON Store muss das bestehende Format aus `loader.py` (819 LOC) korrekt lesen. Das Format ist organisch gewachsen mit Legacy-Feldern und optionaler Verschachtelung.

## Phase M2: Provider portieren — OpenMeteo (3-4 Tage)

**Issue:** #23 | **Abhängigkeiten:** M1

- Alle DTOs aus `models.py` (585 LOC) nach Go Structs portieren
- WeatherProvider Interface + OpenMeteo-Implementierung
- Regionale Modell-Selektion (AROME, ICON-D2, MetNo, ICON-EU, ECMWF)
- Retry mit Exponential Backoff (5 Versuche)
- **BUG-TZ-01 (#21) wird als Nebenprodukt gelöst** (konsequent `time.UTC`)
- Golden-File Test gegen Python-Output für 3 Locations

## Phase M3: Risk Engine portieren (2-3 Tage)

**Issue:** #24 | **Abhängigkeiten:** M2

- Segment-Aggregation (MIN/MAX/AVG/SUM)
- MetricCatalog mit Thresholds
- RiskEngine: Thunder, CAPE, Wind, Gust, Precipitation, Rain Probability, Wind Chill, Visibility, Wind Exposition
- Deduplizierung pro RiskType (höchstes Level gewinnt)
- Golden-File Test: Identische Risiko-Bewertung für 5 Test-Szenarien

## Phase M4: Formatter + Scheduler (5-7 Tage)

**Issue:** #25 | **Abhängigkeiten:** M3

**Größte Phase.** Trip Report Formatter allein hat 1.139 LOC.

- Trip Report HTML-Formatter → Go `html/template`
- Compact Summary (3-5 Zeilen)
- SMS-Formatter (≤160 Zeichen)
- SMTP-Versand (Resend) + Signal (Callmebot)
- Cron-Scheduler (`robfig/cron`):
  - Morning/Evening Subscriptions
  - Trip Reports (stündlich)
  - Alert Checks (alle 30 Min)
  - Inbound Command Poll (alle 5 Min)
  - BetterStack Heartbeats
- GPX-Parser + Hybrid-Segmentierung
- Weather Change Detection + Alert-Versand
- IMAP Polling + Command Parsing

**Nach M4 ist Go-Backend eigenständig lauffähig.**

## Phase M5: SvelteKit Frontend Setup + Auth (3-4 Tage)

**Issue:** #26 | **Abhängigkeiten:** M1 (braucht REST API)

- SvelteKit 5 + TypeScript + Vite
- shadcn-svelte + Tailwind CSS
- Auth-System (löst gleichzeitig F13 Multi-User, Issue #12)
- API Client mit TypeScript-Types (aus OpenAPI generiert)
- Layout + Navigation
- **Kann parallel zu M2-M4 laufen**

## Phase M6: Frontend Pages portieren (7-10 Tage)

**Issue:** #27 | **Abhängigkeiten:** M5 + M4

| Prio | Page | Python LOC | Anmerkung |
|------|------|-----------|-----------|
| P0 | Trips CRUD | 747 | Kern-Workflow |
| P0 | Locations CRUD | 258 | Einfache CRUD-Page |
| P0 | Weather Table | ~500 | Kern-Feature |
| P1 | GPX Upload | 401 | Drag&Drop + Analyse |
| P1 | Compare | 1.828 | Komplexeste Page — Business-Logik ins Go-Backend |
| P1 | Subscriptions | 446 | Compare-Email Config |
| P1 | Report Config | 252 | Zeiten, Channels |
| P1 | Weather Config | 716 | Metrik-Auswahl |
| P2 | Settings | 297 | Channel-Switch |
| P2 | Dashboard | 75 | Übersicht |

## Phase M7: Cutover (2-3 Tage)

**Issue:** #28 | **Abhängigkeiten:** M6

- Nginx: `/api/*` → Go (8081), `/*` → SvelteKit (3000)
- Systemd-Services: `gregor-api.service` + `gregor-web.service`
- Alten `gregor_zwanzig.service` stoppen + disablen
- BetterStack Heartbeats auf Go-Scheduler umstellen
- E2E-Tests mit Playwright
- 48h Beobachtungsperiode nach Cutover

## Go-Bibliotheken

| Bereich | Library | Begründung |
|---------|---------|-----------|
| Router | `go-chi/chi` | Leichtgewichtig, gute Middleware |
| Config | `kelseyhightower/envconfig` | Env-basiert wie pydantic-settings |
| Retry | `cenkalti/backoff` | Exponential Backoff wie tenacity |
| GPX | `tkrajina/gpxgo` | Alternative zu gpxpy |
| Timezone | `ringsaturn/tzf` | Koordinate zu Timezone |
| Cron | `robfig/cron/v3` | Ersatz für APScheduler |
| Logging | `log/slog` (stdlib) | Strukturiertes Logging |
| SMTP | `jordan-wright/email` | Email-Versand |
| Testing | `stretchr/testify` | Assertions |

## REST API (Kern-Endpoints)

```
GET/POST   /api/trips
GET/PUT/DELETE /api/trips/:id
GET        /api/trips/:id/weather
GET/PUT    /api/trips/:id/weather-config
GET/PUT    /api/trips/:id/report-config
POST       /api/trips/:id/test-report

GET/POST   /api/locations
PUT/DELETE /api/locations/:id

POST       /api/gpx/upload
POST       /api/gpx/analyze

GET/POST   /api/subscriptions
PUT/DELETE /api/subscriptions/:id
POST       /api/subscriptions/:id/run

GET        /api/compare
GET        /api/settings
GET        /_health
```

## Go-Projektstruktur

```
gregor-api/
  cmd/
    server/main.go
    cli/main.go
  internal/
    config/config.go
    model/forecast.go, risk.go, trip.go, user.go, gpx.go, weather.go
    provider/provider.go, openmeteo.go, geosphere.go
    risk/engine.go
    formatter/trip_report.go, compact_summary.go, sms_trip.go
    service/aggregation.go, weather_cache.go, trip_forecast.go, ...
    core/gpx.go, elevation.go, segmentation.go
    output/email.go, signal.go
    scheduler/scheduler.go
    handler/trip.go, location.go, weather.go, subscription.go, ...
    store/json_store.go
  api/openapi.yaml
```

## SvelteKit-Projektstruktur

```
gregor-web/
  src/
    lib/api/client.ts, types.ts
    lib/components/WeatherTable.svelte, RiskBadge.svelte, ...
    lib/stores/trips.ts, locations.ts
    routes/
      +layout.svelte
      +page.svelte (Dashboard)
      trips/, locations/, gpx-upload/, compare/
      subscriptions/, settings/, login/
    hooks.server.ts
```

## Risiken

| Risiko | Schwere | Mitigation |
|--------|---------|-----------|
| JSON-Loader Kompatibilität | HOCH | Alle realen Trip-JSONs als Golden Files testen |
| HTML-Email Regression | MITTEL | Visueller Vergleich, nicht Byte-Diff |
| Feature Requests während Migration | MITTEL | Konsequentes Nein — Bugs in Python, Features nach Cutover |
| Parallel-Betrieb zu lang | MITTEL | Harte Deadline 8 Wochen, Scope reduzieren wenn nötig |
| Auth-Komplexität (Lucia + Go) | MITTEL | Erstmal Single-User Basic Auth, Lucia als Enhancement |

## Getroffene Entscheidungen (2026-04-12)

1. **SvelteKit Deploy:** Node-Server (adapter-node) — eigener Prozess auf Port 3000, Nginx proxied
2. **Auth:** Lucia in SvelteKit — Go validiert nur Session-Cookie per Middleware
3. **Datenbank:** JSON-Files beibehalten für V1 — SQLite als separates Issue nach Cutover
4. **Provider:** Nur OpenMeteo für V1 — GeoSphere als separates Issue nach Cutover
5. **UI-Components:** shadcn-svelte (bits-ui) + Tailwind CSS

## Zeitplan

| Phase | Dauer | Woche |
|-------|-------|-------|
| M1: Go Setup | 2-3 Tage | 1 |
| M2: Provider | 3-4 Tage | 1-2 |
| M3: Risk Engine | 2-3 Tage | 2-3 |
| M4: Formatter + Scheduler | 5-7 Tage | 3-4 |
| M5: SvelteKit (parallel) | 3-4 Tage | 2-3 |
| M6: Frontend Pages | 7-10 Tage | 4-6 |
| M7: Cutover | 2-3 Tage | 6-7 |
| Puffer | 1 Woche | 8 |
