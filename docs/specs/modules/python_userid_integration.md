---
entity_id: python_userid_integration
type: module
created: 2026-04-16
updated: 2026-04-16
status: draft
version: "1.0"
tags: [python, multi-user, scheduler, f13]
---

# F13 Phase 3 — Python user_id Integration

## Approval

- [ ] Approved

## Purpose

Die FastAPI Scheduler-Endpoints sollen den `user_id` Query-Parameter lesen, den der Go-Proxy seit Phase 1 weiterleitet, und ihn an alle Loader-Funktionen und Services durchreichen. Damit werden Subscriptions, Trips und Alerts user-scoped verarbeitet statt immer fuer `"default"`.

## Scope

### In Scope

- `api/routers/scheduler.py` — `user_id` Query-Param in allen 5 Endpoints lesen
- `src/services/trip_report_scheduler.py` — `user_id` Parameter akzeptieren
- `src/services/trip_alert.py` — `user_id` Parameter akzeptieren, THROTTLE_FILE dynamisch

### Out of Scope

- User-Profil mit individuellen Channel-Einstellungen (E-Mail, Signal pro User)
- Aenderungen an Go-API oder SvelteKit
- Aenderungen an Loader-Signaturen (akzeptieren `user_id` bereits)

## Source

- **File:** `api/routers/scheduler.py` **(ERWEITERT)**
- **Identifier:** `trigger_morning`, `trigger_evening`, `trigger_trip_reports`, `trigger_alert_checks`, `trigger_inbound`

### Weitere betroffene Dateien

- **File:** `src/services/trip_report_scheduler.py` **(ERWEITERT)**
- **File:** `src/services/trip_alert.py` **(ERWEITERT)**

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.loader.load_all_locations` | python | Akzeptiert `user_id` Parameter bereits |
| `app.loader.load_compare_subscriptions` | python | Akzeptiert `user_id` Parameter bereits |
| `app.loader.load_all_trips` | python | Akzeptiert `user_id` Parameter bereits |
| `fastapi.Query` | python | Query-Parameter Deklaration |

## Implementation Details

### Step 1: Scheduler-Endpoints (`api/routers/scheduler.py`)

Alle 5 Endpoints erhalten `user_id: str = "default"` als Query-Parameter:

```python
@router.post("/morning-subscriptions")
def trigger_morning(user_id: str = "default"):
    count = _run_subscriptions_by_schedule(Schedule.DAILY_MORNING, user_id)
    return {"status": "ok", "count": count}
```

Die Helper-Funktionen `_run_subscriptions_by_schedule` und `_run_weekly_subscriptions` erhalten `user_id` als Parameter und geben ihn an `load_compare_subscriptions(user_id)` und `load_all_locations(user_id)` weiter.

`trigger_trip_reports` gibt `user_id` an `TripReportSchedulerService(user_id=user_id)` weiter.

`trigger_alert_checks` gibt `user_id` an `TripAlertService(user_id=user_id)` weiter.

`trigger_inbound` bleibt global (IMAP polling ist nicht user-scoped — ein Postfach fuer alle).

### Step 2: TripReportSchedulerService (`src/services/trip_report_scheduler.py`)

```python
def __init__(self, settings=None, user_id="default"):
    self._user_id = user_id
    # ...
```

In `send_reports_for_hour` und internen Methoden: `load_all_trips(user_id=self._user_id)` statt `load_all_trips()`.

### Step 3: TripAlertService (`src/services/trip_alert.py`)

```python
def __init__(self, settings=None, throttle_hours=2, user_id="default"):
    self._user_id = user_id
    self._throttle_file = Path(f"data/users/{user_id}/alert_throttle.json")
    # ...
```

In `check_all_trips`: `load_all_trips(user_id=self._user_id)` statt `load_all_trips()`.

`WeatherSnapshotService` akzeptiert bereits `user_id` — wird mit `self._user_id` aufgerufen.

## Expected Behavior

- **Input:** Go-Proxy sendet `POST /api/scheduler/morning-subscriptions?user_id=alice`
- **Output:** Python laedt Subscriptions/Locations/Trips fuer User `alice` aus `data/users/alice/`
- **Ohne user_id:** Default `"default"` — identisches Verhalten wie bisher

## Known Limitations

- `trigger_inbound` bleibt global — IMAP polling ist nicht user-scoped
- Channel-Einstellungen (SMTP, Signal) sind weiterhin global aus `.env` — nicht per-User

## Changelog

- 2026-04-16: Initial spec (F13 Phase 3 — Python user_id Integration, GitHub Issue #12)
