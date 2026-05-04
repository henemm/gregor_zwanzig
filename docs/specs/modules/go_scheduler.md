---
entity_id: go_scheduler
type: module
created: 2026-04-14
updated: 2026-04-14
status: draft
version: "1.0"
tags: [migration, go, scheduler, cron, heartbeat]
---

# M4a: Go Cron-Scheduler

## Approval

- [ ] Approved

## Purpose

Go-basierter Cron-Scheduler ersetzt den Python APScheduler (`src/web/scheduler.py`). Triggert Python-Services via HTTP POST an FastAPI-Endpoints. Ermoeglicht spaeteres Entfernen von NiceGUI (M4b Cutover) ohne Scheduler-Verlust.

## Scope

### In Scope
- Go Cron-Scheduler mit `robfig/cron/v3`
- 5 Cron-Jobs (identisch zum Python-Scheduler)
- BetterStack Heartbeat-Pings nach Morning/Evening
- Python FastAPI Trigger-Endpoints (5 POST-Routes)
- Extraktion `run_comparison_for_subscription()` aus `src/web/pages/compare.py`
- Scheduler-Status-Endpoint in Go (`GET /api/scheduler/status`)
- Config-Erweiterung (Heartbeat URLs, Timezone)

### Out of Scope
- Cutover (Nginx, Systemd, NiceGUI-Entfernung) → M4b
- Port von Python-Services nach Go (bleiben Python)
- SvelteKit-Frontend-Aenderungen
- Retry-Logik fuer fehlgeschlagene Jobs (Backlog)
- Scheduler-UI im Frontend (Backlog)

## Relation to Existing Scheduler

**Bestehend:** `src/web/scheduler.py` (v1.1) — APScheduler im NiceGUI-Prozess, 5 identische Jobs.

**Transition-Strategie:**

1. **Phase "Parallel"** (48h): Beide Scheduler laufen. Python-Jobs in `_execute_subscription()` und `run_trip_reports_check()` laufen weiterhin. Go-Scheduler triggert die gleichen Jobs via HTTP. Doppelte E-Mails werden in Kauf genommen.
2. **Phase "Go Only"**: Python APScheduler wird deaktiviert (`init_scheduler()` Call in `src/web/main.py` auskommentieren + neu deployen). Go-Scheduler ist alleiniger Scheduler.
3. **Phase "Cutover" (M4b)**: NiceGUI-Prozess wird gestoppt. Python FastAPI laeuft separat weiter. Go-Scheduler bleibt.

**Rollback in jeder Phase moeglich**: Go-Scheduler-Init auskommentieren → Python APScheduler uebernimmt wieder.

**Warum kein Deduplizierungs-Mechanismus?** Die Parallel-Phase dauert maximal 48h. Doppelte Reports sind harmlos (gleicher Inhalt). Komplexitaet fuer Idempotenz lohnt nicht.

## Architecture

```
Go Server (:8090)
  │
  ├── robfig/cron/v3 (Europe/Vienna)
  │     │
  │     ├── 07:00 ─── POST /api/scheduler/morning-subscriptions ──→ Python (:8000)
  │     │                                                               └→ BetterStack Heartbeat
  │     ├── 18:00 ─── POST /api/scheduler/evening-subscriptions ──→ Python (:8000)
  │     │                                                               └→ BetterStack Heartbeat
  │     ├── :00   ─── POST /api/scheduler/trip-reports ───────────→ Python (:8000)
  │     ├── :00/:30 ─ POST /api/scheduler/alert-checks ──────────→ Python (:8000)
  │     └── */5   ─── POST /api/scheduler/inbound-commands ──────→ Python (:8000)
  │
  └── GET /api/scheduler/status → JSON mit Job-Liste + naechste Ausfuehrung
```

## Source

### Go (neu)
- **File:** `internal/scheduler/scheduler.go`
- **Identifier:** `Scheduler`, `New()`, `Start()`, `Stop()`, `Status()`

### Python Trigger-Endpoints (neu)
- **File:** `api/routers/scheduler.py`
- **Identifier:** `trigger_morning()`, `trigger_evening()`, `trigger_trip_reports()`, `trigger_alert_checks()`, `trigger_inbound()`

### Python Extraktion (refactor)
- **File:** `src/services/compare_subscription.py` (neu)
- **Identifier:** `run_comparison_for_subscription()`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `robfig/cron/v3` | go module | Cron-Scheduler Library |
| `time/tzdata` | go stdlib | Eingebettete Timezone-Daten |
| Python FastAPI | service | Backend auf localhost:8000 |
| `internal/config` | go package | Heartbeat URLs, Timezone, PythonCoreURL |
| `src/services/trip_report_scheduler` | python module | Trip Report Pipeline |
| `src/services/trip_alert` | python module | Weather Change Alerts |
| `src/services/inbound_email_reader` | python module | IMAP Command Polling |
| `src/services/compare_subscription` | python module | Subscription Reports (extrahiert) |
| BetterStack | external | Heartbeat Monitoring |

## File Structure

```
internal/
└── scheduler/
    └── scheduler.go       # Cron-Scheduler (~180 LoC)

api/
└── routers/
    └── scheduler.py       # Trigger-Endpoints (~90 LoC)

src/
└── services/
    └── compare_subscription.py  # Extrahiert (~80 LoC)
```

## Implementation Details

### Step 0: Extraktion aus compare.py

`run_comparison_for_subscription()` und Hilfs-Klassen aus `src/web/pages/compare.py` extrahieren:

```python
# src/services/compare_subscription.py

from app.user import CompareSubscription
from app.loader import load_all_locations

# Hilfsklassen die mitziehen:
# - ComparisonEngine (reine Logik, kein NiceGUI)
# - render_comparison_html()
# - render_comparison_text()

def run_comparison_for_subscription(
    sub: CompareSubscription,
    all_locations: list | None = None,
) -> tuple[str, str, str]:
    """Run comparison and return (subject, html_body, text_body)."""
    if all_locations is None:
        all_locations = load_all_locations()
    # ... bestehende Logik ...
```

Import-Updates:
- `src/web/scheduler.py`: `from services.compare_subscription import run_comparison_for_subscription`
- `src/app/cli.py`: gleicher Import-Update
- `src/web/pages/compare.py`: importiert von `services.compare_subscription` statt lokal

### Step 1: Go Config-Erweiterung

```go
// internal/config/config.go — neue Fields
type Config struct {
    // ... bestehende Fields ...
    HeartbeatMorning  string `envconfig:"HEARTBEAT_MORNING" default:""`
    HeartbeatEvening  string `envconfig:"HEARTBEAT_EVENING" default:""`
    SchedulerTimezone string `envconfig:"SCHEDULER_TIMEZONE" default:"Europe/Vienna"`
}
```

### Step 2: Python Trigger-Endpoints

```python
# api/routers/scheduler.py
from fastapi import APIRouter, HTTPException
import logging

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])
logger = logging.getLogger("scheduler.trigger")

@router.post("/morning-subscriptions")
def trigger_morning():
    """Trigger morning subscription reports."""
    from app.user import Schedule
    from services.compare_subscription import run_comparison_for_subscription
    from app.loader import load_compare_subscriptions, load_all_locations
    from app.config import Settings
    from outputs.email import EmailOutput
    # ... Logik aus scheduler._run_subscriptions_by_schedule(DAILY_MORNING)
    # ... + _execute_subscription() fuer jede Subscription
    return {"status": "ok", "count": count}

@router.post("/evening-subscriptions")
def trigger_evening():
    """Trigger evening + weekly subscription reports."""
    # ... Logik aus scheduler.run_evening_subscriptions()
    return {"status": "ok", "count": count}

@router.post("/trip-reports")
def trigger_trip_reports(hour: int | None = None):
    """Trigger trip reports for current or specified hour."""
    from services.trip_report_scheduler import TripReportSchedulerService
    from datetime import datetime
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Europe/Vienna")
    current_hour = hour if hour is not None else datetime.now(tz).hour
    service = TripReportSchedulerService()
    count = service.send_reports_for_hour(current_hour)
    return {"status": "ok", "count": count}

@router.post("/alert-checks")
def trigger_alert_checks():
    """Trigger weather change alert checks."""
    from services.trip_alert import TripAlertService
    service = TripAlertService()
    count = service.check_all_trips()
    return {"status": "ok", "count": count}

@router.post("/inbound-commands")
def trigger_inbound():
    """Trigger inbound email command polling."""
    from app.config import Settings
    from services.inbound_email_reader import InboundEmailReader
    settings = Settings()
    imap_user = settings.imap_user or settings.smtp_user
    imap_pass = settings.imap_pass or settings.smtp_pass
    if not imap_user or not imap_pass:
        return {"status": "skipped", "reason": "imap_not_configured"}
    reader = InboundEmailReader()
    count = reader.poll_and_process(settings)
    return {"status": "ok", "count": count}
```

Integration in `api/main.py`:
```python
from api.routers import scheduler
app.include_router(scheduler.router)
```

### Step 3: Go Scheduler

```go
// internal/scheduler/scheduler.go
package scheduler

import (
    _ "time/tzdata"  // Eingebettete Timezone-Daten
    "fmt"
    "io"
    "log"
    "net/http"
    "time"

    "github.com/robfig/cron/v3"
    "github.com/henemm/gregor-api/internal/config"
)

type Scheduler struct {
    cron             *cron.Cron
    pythonURL        string
    heartbeatMorning string
    heartbeatEvening string
    client           *http.Client
}

func New(cfg *config.Config) (*Scheduler, error) {
    loc, err := time.LoadLocation(cfg.SchedulerTimezone)
    if err != nil {
        return nil, fmt.Errorf("invalid timezone %q: %w", cfg.SchedulerTimezone, err)
    }

    s := &Scheduler{
        cron:             cron.New(cron.WithLocation(loc)),
        pythonURL:        cfg.PythonCoreURL,
        heartbeatMorning: cfg.HeartbeatMorning,
        heartbeatEvening: cfg.HeartbeatEvening,
        client:           &http.Client{Timeout: 120 * time.Second},
    }

    // Morning subscriptions at 07:00
    s.cron.AddFunc("0 7 * * *", s.morningSubscriptions)
    // Evening subscriptions at 18:00
    s.cron.AddFunc("0 18 * * *", s.eveningSubscriptions)
    // Trip reports hourly
    s.cron.AddFunc("0 * * * *", s.tripReports)
    // Alert checks every 30 minutes
    s.cron.AddFunc("0,30 * * * *", s.alertChecks)
    // Inbound commands every 5 minutes
    s.cron.AddFunc("*/5 * * * *", s.inboundCommands)

    return s, nil
}

func (s *Scheduler) Start() {
    s.cron.Start()
    log.Printf("Scheduler started: 5 jobs, timezone %s", s.cron.Location())
}

func (s *Scheduler) Stop() {
    ctx := s.cron.Stop()
    <-ctx.Done()
    log.Println("Scheduler stopped")
}

func (s *Scheduler) morningSubscriptions() {
    log.Println("[scheduler] Running morning subscriptions...")
    if err := s.triggerEndpoint("/api/scheduler/morning-subscriptions"); err != nil {
        log.Printf("[scheduler] Morning subscriptions failed: %v", err)
        return
    }
    s.pingHeartbeat(s.heartbeatMorning)
}

func (s *Scheduler) eveningSubscriptions() {
    log.Println("[scheduler] Running evening subscriptions...")
    if err := s.triggerEndpoint("/api/scheduler/evening-subscriptions"); err != nil {
        log.Printf("[scheduler] Evening subscriptions failed: %v", err)
        return
    }
    s.pingHeartbeat(s.heartbeatEvening)
}

func (s *Scheduler) tripReports() {
    if err := s.triggerEndpoint("/api/scheduler/trip-reports"); err != nil {
        log.Printf("[scheduler] Trip reports failed: %v", err)
    }
}

func (s *Scheduler) alertChecks() {
    if err := s.triggerEndpoint("/api/scheduler/alert-checks"); err != nil {
        log.Printf("[scheduler] Alert checks failed: %v", err)
    }
}

func (s *Scheduler) inboundCommands() {
    if err := s.triggerEndpoint("/api/scheduler/inbound-commands"); err != nil {
        log.Printf("[scheduler] Inbound commands failed: %v", err)
    }
}

func (s *Scheduler) triggerEndpoint(path string) error {
    url := s.pythonURL + path
    resp, err := s.client.Post(url, "application/json", nil)
    if err != nil {
        return fmt.Errorf("HTTP error: %w", err)
    }
    defer resp.Body.Close()
    body, _ := io.ReadAll(resp.Body)

    if resp.StatusCode >= 400 {
        return fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(body))
    }
    log.Printf("[scheduler] %s → %d", path, resp.StatusCode)
    return nil
}

func (s *Scheduler) pingHeartbeat(url string) {
    if url == "" {
        return
    }
    client := &http.Client{Timeout: 5 * time.Second}
    resp, err := client.Get(url)
    if err != nil {
        log.Printf("[scheduler] Heartbeat ping failed: %v", err)
        return
    }
    resp.Body.Close()
    log.Printf("[scheduler] Heartbeat ping OK: ...%s", url[len(url)-8:])
}

// Status returns current scheduler state for API exposure.
func (s *Scheduler) Status() map[string]any {
    entries := s.cron.Entries()
    jobs := make([]map[string]any, 0, len(entries))
    for _, e := range entries {
        jobs = append(jobs, map[string]any{
            "id":       int(e.ID),
            "next_run": e.Next.Format(time.RFC3339),
        })
    }
    return map[string]any{
        "running": true,
        "jobs":    jobs,
        "timezone": s.cron.Location().String(),
    }
}
```

### Step 4: Wiring in main.go

```go
// cmd/server/main.go — nach Store/Provider init, vor ListenAndServe

sched, err := scheduler.New(cfg)
if err != nil {
    log.Fatalf("scheduler error: %v", err)
}
sched.Start()
defer sched.Stop()

// Optional: Status-Endpoint
r.Get("/api/scheduler/status", func(w http.ResponseWriter, r *http.Request) {
    json.NewEncoder(w).Encode(sched.Status())
})
```

## Cron-Expressions

| Job | Expression | Timezone | Beschreibung |
|-----|-----------|----------|--------------|
| Morning Subscriptions | `0 7 * * *` | Europe/Vienna | Taeglich 07:00 |
| Evening Subscriptions | `0 18 * * *` | Europe/Vienna | Taeglich 18:00 |
| Trip Reports | `0 * * * *` | Europe/Vienna | Stuendlich zur vollen Stunde |
| Alert Checks | `0,30 * * * *` | Europe/Vienna | Alle 30 Minuten |
| Inbound Commands | `*/5 * * * *` | Europe/Vienna | Alle 5 Minuten |

## Expected Behavior

### Normaler Betrieb
- **Input:** Go-Server startet
- **Output:** 5 Cron-Jobs laufen im Hintergrund, triggern Python-Endpoints
- **Side effects:** E-Mails, Signal-Nachrichten, BetterStack Heartbeats, Log-Eintraege

### Python nicht erreichbar
- **Input:** Python-Server auf Port 8000 nicht erreichbar
- **Output:** Job loggt Fehler, kehrt zurueck, blockiert nicht andere Jobs
- **Side effects:** Kein BetterStack-Heartbeat → Monitoring-Alert nach Grace Period

### Manueller Trigger
- **Input:** `curl -X POST http://localhost:8000/api/scheduler/morning-subscriptions`
- **Output:** `{"status": "ok", "count": 2}` (Anzahl gesendeter Reports)

## Testing

### Go Unit Tests (`internal/scheduler/scheduler_test.go`)

1. `TestNew_ValidTimezone` — Scheduler erstellt mit Europe/Vienna
2. `TestNew_InvalidTimezone` — Error bei ungueltiger Timezone
3. `TestTriggerEndpoint_Success` — Mock-HTTP-Server, 200 Response
4. `TestTriggerEndpoint_PythonDown` — Connection refused → Error
5. `TestTriggerEndpoint_PythonError` — 500 Response → Error
6. `TestPingHeartbeat_Success` — Mock-HTTP-Server, 200
7. `TestPingHeartbeat_Failure` — Timeout → Warning-Log, kein Error
8. `TestStatus` — Gibt Jobs mit next_run zurueck

### Python Integration Tests (`tests/tdd/test_scheduler_triggers.py`)

1. `test_morning_trigger` — POST /api/scheduler/morning-subscriptions → 200
2. `test_evening_trigger` — POST /api/scheduler/evening-subscriptions → 200
3. `test_trip_reports_trigger` — POST /api/scheduler/trip-reports → 200
4. `test_alert_checks_trigger` — POST /api/scheduler/alert-checks → 200
5. `test_inbound_trigger` — POST /api/scheduler/inbound-commands → 200
6. `test_trip_reports_with_hour` — POST /api/scheduler/trip-reports?hour=7 → 200

### Validierungsperiode (manuell, 48h)

1. Beide Scheduler parallel laufen lassen
2. Logs vergleichen: gleiche Jobs feuern zur gleichen Zeit
3. BetterStack Dashboard pruefen: Heartbeats kommen an
4. Python APScheduler deaktivieren, nur Go-Scheduler laeuft
5. 24h beobachten

## Known Limitations

- Jobs laufen synchron (kein Worker-Pool) — ein langsamer Job blockiert seinen Slot. Akzeptabel, da Jobs unterschiedliche Cron-Zeiten haben und keiner laenger als ~60s dauert (OpenMeteo-Calls + E-Mail-Versand)
- HTTP-Timeout 120s: Grosszuegig bemessen fuer den Fall vieler Subscriptions mit langsamen Provider-Responses. Typische Ausfuehrung: 5-30s
- Kein Retry bei fehlgeschlagenen Jobs (Job wird beim naechsten Cron-Intervall erneut versucht)
- Keine persistente Job-Historie (nur Logs)
- Waehrend Validierungsperiode koennten doppelte E-Mails gesendet werden
- `robfig/cron/v3` 5-Field Format (Minute-basiert, keine Sekunden-Praezision)

## Rollback

Go-Scheduler stoppen und Python APScheduler wieder aktivieren:
1. Scheduler-Init in `main.go` auskommentieren
2. Go-Binary neu deployen
3. NiceGUI-Server (mit APScheduler) laeuft wie vorher

## Changelog

- 2026-04-14: v1.0 Initial spec (M4a — Go Cron-Scheduler)
