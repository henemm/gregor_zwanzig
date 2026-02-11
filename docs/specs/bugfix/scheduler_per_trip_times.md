---
entity_id: scheduler_per_trip_times
type: bugfix
created: 2026-02-10
updated: 2026-02-10
status: draft
version: "1.0"
tags: [bugfix, story-3, feature-3.3, scheduler, config]
---

# Bugfix: Scheduler nutzt per-Trip Report-Zeiten

## Approval

- [ ] Approved

## Purpose

Feature 3.3 (Report-Scheduler) hat globale Cron-Jobs bei 07:00/18:00. Feature 3.5 erlaubt dem User, Morning/Evening-Zeiten pro Trip zu konfigurieren (z.B. 06:00/20:00). Der Scheduler ignoriert diese per-Trip-Zeiten komplett.

## Source

- **File 1:** `src/web/scheduler.py` — Cron-Triggers hardcoded auf 07:00/18:00
- **File 2:** `src/services/trip_report_scheduler.py` — `send_reports()` prüft keine Trip-Zeiten

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripReportConfig` | DTO | models.py — enthält `morning_time`, `evening_time` |
| `Trip` | Model | trip.py — hat `report_config: Optional[TripReportConfig]` |

## Architektur-Entscheidung

**Ansatz: Stündliche Cron-Jobs mit Zeitfilter**

1. Beide Trip-Report-Cron-Jobs laufen **stündlich** statt 1x täglich
2. `send_reports()` bekommt die aktuelle Stunde und filtert Trips nach konfigurierter Zeit
3. Nur Trips, deren konfigurierte Stunde mit der aktuellen übereinstimmt, werden bedient

**Vorteile:** Minimal-invasiv, kein komplexes Per-Trip-Scheduling, Default-Verhalten bleibt identisch.
**Kosten:** 24 statt 2 Job-Runs pro Tag — für einen Headless-Service mit wenigen Trips vernachlässigbar.

## Implementation Details

### scheduler.py: Stündliche Cron-Triggers

```python
# ALT: Feste Zeiten
_scheduler.add_job(run_morning_trip_reports, CronTrigger(hour=7, minute=0, ...))
_scheduler.add_job(run_evening_trip_reports, CronTrigger(hour=18, minute=0, ...))

# NEU: Stündlich, Zeitfilter in send_reports()
_scheduler.add_job(
    run_trip_reports_check,
    CronTrigger(minute=0, timezone=TIMEZONE),  # Jede volle Stunde
    id="trip_reports_hourly",
    name="Trip Reports (hourly check)",
)
```

### scheduler.py: Neue Funktion `run_trip_reports_check()`

```python
def run_trip_reports_check() -> None:
    """Check which trips need reports at this hour."""
    from services.trip_report_scheduler import TripReportSchedulerService

    now = datetime.now(TIMEZONE)
    current_hour = now.hour

    service = TripReportSchedulerService()
    count = service.send_reports_for_hour(current_hour)
    if count > 0:
        logger.info(f"Trip reports at {current_hour:02d}:00: {count} sent")
```

### trip_report_scheduler.py: `send_reports_for_hour()`

```python
def send_reports_for_hour(self, current_hour: int) -> int:
    """Send reports for trips whose configured time matches current_hour."""
    morning_trips = [
        t for t in self._get_active_trips("morning")
        if self._get_morning_hour(t) == current_hour
    ]
    evening_trips = [
        t for t in self._get_active_trips("evening")
        if self._get_evening_hour(t) == current_hour
    ]

    sent = 0
    for trip in morning_trips:
        try:
            self._send_trip_report(trip, "morning")
            sent += 1
        except Exception as e:
            logger.error(f"Failed morning report for {trip.id}: {e}")

    for trip in evening_trips:
        try:
            self._send_trip_report(trip, "evening")
            sent += 1
        except Exception as e:
            logger.error(f"Failed evening report for {trip.id}: {e}")

    return sent

def _get_morning_hour(self, trip: "Trip") -> int:
    """Get configured morning hour (default: 7)."""
    if trip.report_config and trip.report_config.morning_time:
        return trip.report_config.morning_time.hour
    return 7

def _get_evening_hour(self, trip: "Trip") -> int:
    """Get configured evening hour (default: 18)."""
    if trip.report_config and trip.report_config.evening_time:
        return trip.report_config.evening_time.hour
    return 18
```

### Bestehende `send_reports()` bleibt erhalten

Die alte `send_reports("morning"/"evening")` bleibt als Fallback (für manuelle Trigger / Tests). Die neue `send_reports_for_hour()` wird vom Cron-Job aufgerufen.

## Expected Behavior

- **Trip ohne Config:** Morning 07:00, Evening 18:00 (Default, keine Regression)
- **Trip mit morning_time=06:00:** Report wird um 06:00 gesendet, NICHT um 07:00
- **Trip mit evening_time=20:00:** Report wird um 20:00 gesendet, NICHT um 18:00
- **Zwei Trips mit verschiedenen Zeiten:** Jeder wird zur eigenen Zeit bedient

## Tests

```python
def test_default_hours_without_config():
    """Trip ohne Config bekommt Default 07/18."""
    assert service._get_morning_hour(trip_without_config) == 7
    assert service._get_evening_hour(trip_without_config) == 18

def test_custom_hours_with_config():
    """Trip mit Config bekommt konfigurierte Zeiten."""
    trip.report_config = TripReportConfig(trip_id="t", morning_time=time(6, 0), evening_time=time(20, 0))
    assert service._get_morning_hour(trip) == 6
    assert service._get_evening_hour(trip) == 20

def test_send_reports_filters_by_hour():
    """Nur Trips mit passender Stunde werden bedient."""
    # Trip mit morning=07:00 wird bei hour=7 inkludiert, bei hour=6 nicht
```

## Scope

- **Dateien geändert:** 2 (`scheduler.py`, `trip_report_scheduler.py`)
- **Dateien für Tests:** 1 (`test_trip_report_scheduler.py`)
- **LoC Änderungen:** ~40 (Produktion) + ~30 (Tests)

## Known Limitations

- Zeiten werden auf volle Stunden gerundet (07:30 → wird um 07:00 gesendet). Für Weitwanderer-Reports ist das ausreichend.

## Changelog

- 2026-02-10: Initial spec created
