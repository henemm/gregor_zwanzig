# Context: M4 — Scheduler nach Go + Cutover (#28)

## Request Summary

Go Cron-Scheduler für Morning/Evening Reports, Trip Reports, Alert Checks und Inbound Commands implementieren. Anschließend Cutover: Nginx auf Go+SvelteKit umstellen, NiceGUI-Code (`src/web/`) entfernen, Systemd-Services anpassen.

## Empfehlung: Split in M4a + M4b

| Sub-Milestone | Scope | Risiko |
|---------------|-------|--------|
| **M4a: Go Scheduler** | Cron-Library, Trigger-Endpoints, Scheduler-Package, Validierung | Niedrig (Rollback: einfach Python-Scheduler wieder aktivieren) |
| **M4b: Cutover** | Nginx, Systemd, NiceGUI löschen, SvelteKit-Service | Mittel (schwer rückgängig) |

48h Validierungspause zwischen M4a und M4b.

## Implementierungsreihenfolge (M4a)

### Step 0: Extraktion `run_comparison_for_subscription` (Prerequisite)
- Aus `src/web/pages/compare.py` nach `src/services/compare_subscription.py` verschieben
- Inkl. `ComparisonEngine`, `render_comparison_html`, `render_comparison_text`
- Import-Updates in `scheduler.py`, `cli.py`, `compare.py`
- ~80 LoC Move, 3 Import-Änderungen

### Step 1: `robfig/cron/v3` in go.mod
- `go get github.com/robfig/cron/v3`

### Step 2: Config erweitern (`internal/config/config.go`)
- `HeartbeatMorning`, `HeartbeatEvening`, `SchedulerTimezone` Fields
- ~8 LoC

### Step 3: Python Trigger-Endpoints (`api/routers/scheduler.py`)
- 5 POST-Endpoints (kein Request Body, synchron):
  - `POST /api/scheduler/morning-subscriptions`
  - `POST /api/scheduler/evening-subscriptions`
  - `POST /api/scheduler/trip-reports`
  - `POST /api/scheduler/alert-checks`
  - `POST /api/scheduler/inbound-commands`
- ~90 LoC, neues File + Router-Include in `api/main.py`

### Step 4: Go Scheduler (`internal/scheduler/scheduler.go`)
- `robfig/cron/v3` mit `WithLocation("Europe/Vienna")`
- `import _ "time/tzdata"` für eingebettete Timezone-Daten
- 5 Cron-Jobs triggern Python-Endpoints via HTTP POST
- Heartbeat-Ping nach Morning/Evening
- 120s Timeout für langläufige Jobs
- ~180 LoC

### Step 5: Wiring in `cmd/server/main.go`
- Scheduler init + defer Stop
- ~4 LoC

### Step 6: 48h Parallel-Betrieb
- Beide Scheduler laufen parallel
- Logs vergleichen, Heartbeats prüfen
- Dann APScheduler deaktivieren

## Related Files

### Zu erstellen (neu)
| File | LoC | Zweck |
|------|-----|-------|
| `src/services/compare_subscription.py` | ~80 | Extrahierte Comparison-Logik |
| `api/routers/scheduler.py` | ~90 | Python Trigger-Endpoints |
| `internal/scheduler/scheduler.go` | ~180 | Go Cron-Scheduler |

### Zu ändern
| File | Änderung |
|------|----------|
| `cmd/server/main.go` | +4 LoC: Scheduler init/stop |
| `internal/config/config.go` | +3 Config-Fields |
| `api/main.py` | +2 LoC: Router include |
| `go.mod` | +1 Dependency |
| `src/web/scheduler.py` | Import-Update (Step 0) |
| `src/app/cli.py` | Import-Update (Step 0) |
| `src/web/pages/compare.py` | Code entfernen, re-import (Step 0) |

### Cutover (M4b) — separat
| File | Änderung |
|------|----------|
| Nginx Config | `/` → SvelteKit:3000, `/api/` → Go:8090 |
| Systemd | Neuer `gregor-frontend.service`, ggf. `gregor-python-api.service` |
| `src/web/` | Komplett löschen |

## Scope-Estimate

| Metrik | Wert | Flag? |
|--------|------|-------|
| Dateien (geändert/neu) | 10 (M4a) + 3 (M4b) | >5 ⚠️ |
| LoC (netto-neu) | ~330 (M4a) | >250 ⚠️ |
| LoC (brutto) | ~410 (inkl. 80 Move) | |

Über den üblichen Schwellwerten, aber unvermeidbar bei Cross-Language-Migration. Komplexität ist niedrig — hauptsächlich Wiring und Konfiguration.

## Risiken

| # | Risiko | Schwere | Mitigation |
|---|--------|---------|------------|
| 1 | **FastAPI-Prozess-Abhängigkeit**: Wie läuft Port 8000 heute? Shared Process mit NiceGUI? | HOCH | `ps aux` prüfen vor Cutover, ggf. eigenen Service anlegen |
| 2 | **Timezone/tzdata**: `time.LoadLocation` braucht System-tzdata | MITTEL | `import _ "time/tzdata"` einbetten (450KB, null Risiko) |
| 3 | **Parallel-Betrieb Duplikate**: Beide Scheduler feuern gleichzeitig | NIEDRIG | Python-Jobs deaktivieren oder kurze Überlappung akzeptieren |
| 4 | **SvelteKit-Seiten unvollständig**: Compare, Subscriptions, Settings fehlen | INFO | Cutover nur wenn akzeptabel oder M6 vorher |

## Dependency Graph

```
Go Scheduler (robfig/cron)
  │
  ├─ POST /api/scheduler/morning-subscriptions → Python FastAPI
  │     └─ load_compare_subscriptions() → run_comparison → EmailOutput → SMTP
  │     └─ ping BetterStack Heartbeat
  │
  ├─ POST /api/scheduler/evening-subscriptions → Python FastAPI
  │     └─ (wie morning + weekly check)
  │     └─ ping BetterStack Heartbeat
  │
  ├─ POST /api/scheduler/trip-reports → Python FastAPI
  │     └─ TripReportSchedulerService.send_reports_for_hour()
  │         └─ OpenMeteo → Format → Email/Signal
  │
  ├─ POST /api/scheduler/alert-checks → Python FastAPI
  │     └─ TripAlertService.check_all_trips()
  │         └─ OpenMeteo → Change Detection → Email/Signal
  │
  └─ POST /api/scheduler/inbound-commands → Python FastAPI
        └─ InboundEmailReader.poll_and_process()
            └─ IMAP → Parse → TripCommandProcessor → SMTP Reply
```

## Existing Specs
- `docs/specs/modules/scheduler.md` v1.1 — Aktueller Python-Scheduler
- `docs/specs/modules/trip_report_scheduler.md` v1.0 — Trip Report Pipeline
- `docs/specs/bugfix/scheduler_per_trip_times.md` — Per-Trip-Zeiten (done)
- `docs/specs/bugfix/scheduler_provider_selection.md` — OpenMeteo-Only (done)
