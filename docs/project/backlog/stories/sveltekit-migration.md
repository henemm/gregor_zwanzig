# User Story: Hybrid-Migration (Go API + SvelteKit Frontend)

**Epic:** Tech Stack Migration
**Erstellt:** 2026-04-08
**Aktualisiert:** 2026-04-12
**Status:** Draft

## Story

Als PO moechte ich das Frontend von NiceGUI auf SvelteKit migrieren und eine Go REST API als Verbindungsschicht einbauen, damit die AI-gestuetzte Entwicklung weniger Fehler produziert — ohne funktionierenden Python-Core unnoetig neu zu schreiben.

## Motivation

### Problem

- AI (Claude) macht mit NiceGUI signifikant mehr Fehler (Safari-Closures, Session-Isolation, wenig Trainingsdaten)
- Multi-User (F13) ist in NiceGUI extrem aufwaendig
- Jeder UI-Feature-Zyklus hat zu viele Iterationen

### Was NICHT das Problem ist

- Die Weather-Pipeline (Provider, Normalizer, Risk Engine) funktioniert zuverlaessig
- GPX-Parsing mit gpxpy/numpy ist stabil und hat keine Go-Aequivalente gleicher Qualitaet
- Formatter und Output-Channels sind solide
- Services (Forecast, Aggregation, Caching) sind ausgereift (~5000 LOC)

### Entscheidung: Hybrid-Ansatz

**Nur ersetzen, was kaputt ist.** NiceGUI und das Web-Layer sind das Problem — nicht die Datenverarbeitung.

## Architektur nach Migration

```
┌─────────────────────────────────────────────────┐
│  SvelteKit Frontend (neu)                       │
│  - Ersetzt NiceGUI komplett                     │
│  - Auth / Multi-User (Lucia)                    │
│  - UI-Komponenten (shadcn-svelte o.ae.)         │
└──────────────────┬──────────────────────────────┘
                   │ REST API (JSON)
┌──────────────────▼──────────────────────────────┐
│  Go REST API (neu)                              │
│  - Chi Router, Auth-Middleware, Session          │
│  - Duenne Schicht: HTTP → Python-Core → JSON    │
│  - Scheduler (Cron fuer Morning/Evening Reports) │
└──────────────────┬──────────────────────────────┘
                   │ Python-Subprocess / HTTP
┌──────────────────▼──────────────────────────────┐
│  Python Core (bleibt)                           │
│  - providers/ (OpenMeteo, GeoSphere)  ~1450 LOC │
│  - services/ (Risk, Forecast, etc.)   ~5000 LOC │
│  - formatters/ (Email, SMS, Trip)     ~2000 LOC │
│  - core/ (GPX, Segmentation)           ~700 LOC │
│  - outputs/ (Email, Signal)             ~470 LOC │
│  - app/ (Config, Models, Loader)      ~2900 LOC │
│  Gesamt: ~12500 LOC bewahrt                     │
└─────────────────────────────────────────────────┘
```

### Go-Python Anbindung

Optionen (Entscheidung in M1):

| Option | Vorteil | Nachteil |
|---|---|---|
| **Python als HTTP-Microservice** | Saubere Trennung, unabhaengig deploybar | Zwei Prozesse, Latenz |
| **Python CLI aufrufen** | Einfachste Loesung, CLI existiert bereits | Kein Streaming, Startup-Overhead |
| **Shared SQLite/JSON** | Go schreibt Requests, Python pollt & verarbeitet | Komplexer, Polling-Delay |

**Tendenz:** Python als interner HTTP-Service auf localhost (FastAPI/Litestar Wrapper um bestehenden Core).

## Scope — Was wird ersetzt

| Komponente | Aktuell | Neu | LOC |
|---|---|---|---|
| Frontend | NiceGUI (`src/web/`) | **SvelteKit** | ~5500 → neu |
| API-Layer | Python-Funktionsaufrufe | **Go REST API** | neu |
| Scheduler | `src/web/scheduler.py` | **Go Cron** | ~200 → Go |
| Auth | Keins | **Go Middleware + Lucia** | neu |

## Scope — Was bleibt in Python

| Komponente | LOC | Grund |
|---|---|---|
| Weather Provider | ~1450 | httpx funktioniert, API-Anbindung stabil |
| Services (Risk, Forecast, etc.) | ~5000 | Komplexe Business-Logik, ausgereift |
| Formatter | ~2000 | HTML-Templates, SMS-Logik — kein Vorteil durch Go |
| Core (GPX, Segmentation) | ~700 | gpxpy/numpy haben keine Go-Aequivalente |
| Outputs (Email, Signal) | ~470 | Resend/Callmebot-Anbindung stabil |
| App (Config, Models) | ~2900 | Datenmodelle bleiben gleich |

## Meilensteine

### M1: Go API Setup
Go-Modul initialisieren, Chi Router, REST API Design (OpenAPI-Spec), Python-Core als interner HTTP-Service wrappen.

### M2: Auth + Multi-User
Go Auth-Middleware, Session-Management, User-Isolation in Python-Core.

### M3: SvelteKit Frontend Setup
Vite, UI-Library, Auth-Integration, erste Page (Dashboard).

### M4: Frontend Pages portieren
Trips, Locations, Weather, Subscriptions, Settings — alle NiceGUI-Pages als SvelteKit-Pages.

### M5: Scheduler nach Go
Morning/Evening Report Cron, BetterStack Heartbeats, Trip-Alerts.

### M6: Cutover
DNS/Nginx umstellen, NiceGUI-Code (`src/web/`) entfernen, Systemd-Services anpassen.

## Was NICHT portiert wird

- `src/providers/` — bleibt Python
- `src/services/` — bleibt Python
- `src/formatters/` — bleibt Python
- `src/core/` — bleibt Python
- `src/outputs/` — bleibt Python
- `src/app/` — bleibt Python (wird um HTTP-API-Wrapper ergaenzt)

## Risiken

| Risiko | Schwere | Mitigation |
|---|---|---|
| Go-Python Kommunikation fragil | Mittel | Klare API-Contracts, Integration Tests |
| Zwei Prozesse in Produktion | Niedrig | Systemd: Go-Service depends-on Python-Service |
| Feature-Freeze waehrend Migration | Hoch | Phasen-Ansatz, Python laeuft parallel bis Cutover |
| SvelteKit-Paradigmenwechsel | Niedrig | Vercel-backed, stabile Migration Guides |

## Abhaengigkeiten zu bestehenden Features

| Feature | Auswirkung |
|---|---|
| F13 (Multi-User) | Wird durch Auth-Layer in M2 direkt geloest |
| F12 (Channel-Switch) | In M4 als SvelteKit-Page |
| F14a/b (Subscription Metriken) | In M4 als SvelteKit-Page |
| BUG-TZ-01 (Timezone) | Im Python-Core fixen, unabhaengig von Migration |

## Erfolgskriterien

1. **NiceGUI komplett ersetzt** — `src/web/` geloescht
2. **Python-Core unveraendert funktional** — alle bestehenden Tests gruen
3. **Multi-User funktional** (Login, User-Isolation)
4. **E2E-Tests gruen** (Playwright gegen SvelteKit)
5. **Kein unnoetig portierter Code** — Python-Core bleibt Python

## Offene Entscheidungen

| Frage | Optionen | Status |
|---|---|---|
| Go-Python Anbindung | HTTP-Service vs. CLI vs. Shared State | Offen |
| SvelteKit Deploy-Modus | Node-Server vs. Static Adapter | Offen |
| Auth-Library | Lucia vs. eigene Session-Middleware | Offen |
| UI-Component-Library | Skeleton UI vs. shadcn-svelte | Offen |
| Python HTTP-Framework | FastAPI vs. Litestar vs. Flask | Offen |
