---
entity_id: scheduler
type: module
created: 2025-12-30
updated: 2026-01-01
status: draft
version: "1.1"
tags: [scheduler, email, background, apscheduler, bugfix]
---

# Scheduler Module

## Approval

- [ ] Approved

## Purpose

Automatischer E-Mail-Versand fuer Compare Subscriptions im NiceGUI-Server.
Der Scheduler startet mit dem Server und fuehrt Subscriptions gemaess ihrem Schedule aus.
Keine externe Cron-Konfiguration noetig.

## Source

- **File:** `src/web/scheduler.py`
- **Identifier:** `init_scheduler()`, `SubscriptionScheduler`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `apscheduler` | external | Background Scheduler Library |
| `app.user.CompareSubscription` | dataclass | Subscription-Konfiguration |
| `app.user.Schedule` | enum | Schedule-Typen (DAILY_MORNING, etc.) |
| `app.loader.load_compare_subscriptions` | function | Subscriptions laden |
| `web.pages.compare.run_comparison_for_subscription` | function | E-Mail generieren |
| `outputs.email.EmailOutput` | class | E-Mail senden |
| `app.config.Settings` | class | SMTP-Konfiguration |

## Architecture

```
NiceGUI Server Start
    |
    v
app.on_startup(init_scheduler)
    |
    v
APScheduler BackgroundScheduler
    |
    +-- CronTrigger 07:00 --> run_morning_subscriptions()
    |
    +-- CronTrigger 18:00 --> run_evening_subscriptions()
    |
    +-- CronTrigger 18:00 Mo-So --> run_weekly_subscriptions()
```

## Implementation Details

### 1. Neue Dependency

```toml
# pyproject.toml
dependencies = [
    ...
    "apscheduler>=3.10",
]
```

### 2. Scheduler Modul

```python
# src/web/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler: BackgroundScheduler | None = None

def init_scheduler() -> None:
    """Initialize and start the background scheduler."""
    global scheduler
    scheduler = BackgroundScheduler()

    # Morning subscriptions at 07:00
    scheduler.add_job(
        run_morning_subscriptions,
        CronTrigger(hour=7, minute=0),
        id="morning_subscriptions",
    )

    # Evening subscriptions at 18:00
    scheduler.add_job(
        run_evening_subscriptions,
        CronTrigger(hour=18, minute=0),
        id="evening_subscriptions",
    )

    scheduler.start()

def run_morning_subscriptions() -> None:
    """Run all DAILY_MORNING subscriptions."""
    _run_subscriptions_by_schedule(Schedule.DAILY_MORNING)

def run_evening_subscriptions() -> None:
    """Run DAILY_EVENING and matching WEEKLY subscriptions."""
    _run_subscriptions_by_schedule(Schedule.DAILY_EVENING)
    _run_weekly_subscriptions()

def _run_weekly_subscriptions() -> None:
    """Run WEEKLY subscriptions if today matches the weekday."""
    from datetime import datetime
    current_weekday = datetime.now().weekday()

    for sub in load_compare_subscriptions():
        if sub.enabled and sub.schedule == Schedule.WEEKLY:
            if sub.weekday == current_weekday:
                _execute_subscription(sub)

def _run_subscriptions_by_schedule(schedule: Schedule) -> None:
    """Run all subscriptions matching the given schedule."""
    for sub in load_compare_subscriptions():
        if sub.enabled and sub.schedule == schedule:
            _execute_subscription(sub)

def _execute_subscription(sub: CompareSubscription) -> None:
    """Execute a single subscription and send email."""
    # ... generate and send email
```

### 3. Server Integration

```python
# src/web/main.py
from web.scheduler import init_scheduler

app.on_startup(init_scheduler)
```

## Configuration

| Parameter | Wert | Beschreibung |
|-----------|------|--------------|
| DAILY_MORNING | 07:00 | Feste Uhrzeit |
| DAILY_EVENING | 18:00 | Feste Uhrzeit |
| WEEKLY | 18:00 am Wochentag | Wochentag aus Subscription |
| Timezone | Europe/Vienna | Explizit gesetzt (v1.1 Fix) |

## v1.1 Bugfix: Timezone + Logging

### Problem (01.01.2026)

Scheduler triggerte nicht um 07:00 obwohl:
- Server lief
- Subscription existierte und enabled war
- Manueller Test funktionierte

### Ursache

1. **Keine explizite Timezone** - CronTrigger nutzte System-Default
2. **Mangelndes Logging** - Keine Bestaetigung dass Scheduler initialisiert wurde
3. **Silent Failure** - Fehler wurden nicht sichtbar geloggt

### Loesung

```python
from zoneinfo import ZoneInfo

# Explizite Timezone
TIMEZONE = ZoneInfo("Europe/Vienna")

# CronTrigger mit Timezone
CronTrigger(hour=7, minute=0, timezone=TIMEZONE)

# Logging auf stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

# Startup-Bestaetigung
logger.info(f"Scheduler gestartet: Morning 07:00, Evening 18:00 ({TIMEZONE})")
```

## Expected Behavior

- **Input:** Server-Start
- **Output:**
  - Scheduler laeuft im Hintergrund
  - E-Mails werden automatisch zur konfigurierten Zeit gesendet
- **Side effects:**
  - E-Mails via SMTP
  - Log-Eintraege bei Ausfuehrung/Fehlern

## Logging

```python
import logging
logger = logging.getLogger("scheduler")

# Bei jeder Ausfuehrung
logger.info(f"Running subscription: {sub.name}")
logger.info(f"Email sent for: {sub.name}")
logger.error(f"Failed to send email for {sub.name}: {error}")
```

## Known Limitations

- Uhrzeiten nicht konfigurierbar (fest 07:00/18:00)
- Keine Retry-Logik bei fehlgeschlagenen E-Mails
- Kein UI-Status (wann zuletzt gesendet)
- Server muss laufen fuer automatischen Versand

## Future Enhancements (Backlog)

- Konfigurierbare Uhrzeiten pro Subscription
- UI-Anzeige: Letzte Ausfuehrung, naechste geplante Ausfuehrung
- Retry-Mechanismus bei SMTP-Fehlern
- Manuelle Ausfuehrung aus dem UI ("Jetzt senden")

## Changelog

- 2026-01-01: v1.1 Bugfix - Explizite Timezone (Europe/Vienna), Logging auf stdout
- 2025-12-30: v1.0 Initial spec created
