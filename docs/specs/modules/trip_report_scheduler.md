---
entity_id: trip_report_scheduler
type: module
created: 2026-02-09
updated: 2026-02-09
status: draft
version: "1.0"
tags: [scheduler, trip, report, email, story3]
---

# Trip Report Scheduler

## Approval

- [x] Approved

## Purpose

Automatischer E-Mail-Versand fuer Trip-Weather-Reports 2x taeglich (Morning 07:00, Evening 18:00 Europe/Vienna).
Erweitert den bestehenden `src/web/scheduler.py` um Trip-Report Jobs parallel zu den Compare-Subscription Jobs.

## Source

- **File:** `src/services/trip_report_scheduler.py` (NEW)
- **Integration:** `src/web/scheduler.py` (MODIFY)
- **Identifier:** `TripReportSchedulerService`, `run_morning_trip_reports()`, `run_evening_trip_reports()`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/web/scheduler.py` | module | Bestehender APScheduler - wird erweitert |
| `src/app/loader.load_all_trips` | function | Trips laden |
| `src/app/trip.Trip` | dataclass | Trip-Datenstruktur mit Stages/Waypoints |
| `src/formatters/trip_report.TripReportFormatter` | class | HTML/Plain-Text Email generieren |
| `src/formatters/sms_trip.SMSTripFormatter` | class | SMS generieren (optional) |
| `src/services/segment_weather.SegmentWeatherService` | class | Wetter fuer Segmente abrufen |
| `src/outputs/email.EmailOutput` | class | SMTP Email senden |
| `src/app/models.TripReport` | dataclass | Report-DTO |
| `apscheduler` | external | Background Scheduler Library |

## Architecture

```
scheduler.py (bestehend)
    |
    +-- init_scheduler()
    |       |
    |       +-- CronTrigger 07:00 → run_morning_subscriptions()  (Compare - bestehend)
    |       +-- CronTrigger 07:00 → run_morning_trip_reports()   (NEU)
    |       |
    |       +-- CronTrigger 18:00 → run_evening_subscriptions()  (Compare - bestehend)
    |       +-- CronTrigger 18:00 → run_evening_trip_reports()   (NEU)


trip_report_scheduler.py (NEU)
    |
    +-- TripReportSchedulerService
            |
            +-- send_reports(report_type: str)
            |       |
            |       +-- load_all_trips()
            |       +-- for each trip:
            |               +-- convert_trip_to_segments(trip) → TripSegment[]
            |               +-- fetch_segment_weather(segment) → SegmentWeatherData[]
            |               +-- TripReportFormatter.format_email(...) → TripReport
            |               +-- EmailOutput.send(...)
            |
            +-- _convert_trip_to_segments(trip: Trip) → list[TripSegment]
            +-- _is_trip_active_today(trip: Trip) → bool
```

## Implementation Details

### 1. Trip → TripSegment Konvertierung

Das Trip-Model (`src/app/trip.py`) nutzt Waypoints mit TimeWindows.
Die Story-2-Services erwarten `TripSegment` DTOs.

**Mapping:**
```python
def _convert_trip_to_segments(trip: Trip, target_date: date) -> list[TripSegment]:
    """
    Konvertiert Trip-Waypoints zu TripSegments fuer einen bestimmten Tag.

    Ein Segment = Strecke zwischen zwei aufeinanderfolgenden Waypoints.
    """
    segments = []
    stage = trip.get_stage_for_date(target_date)
    if stage is None:
        return []

    for i, (wp1, wp2) in enumerate(zip(stage.waypoints[:-1], stage.waypoints[1:])):
        # TimeWindow to datetime
        start_dt = datetime.combine(target_date, wp1.time_window.start, tzinfo=timezone.utc)
        end_dt = datetime.combine(target_date, wp2.time_window.start, tzinfo=timezone.utc)

        segment = TripSegment(
            segment_id=i + 1,
            start_point=GPXPoint(lat=wp1.lat, lon=wp1.lon, elevation_m=wp1.elevation_m),
            end_point=GPXPoint(lat=wp2.lat, lon=wp2.lon, elevation_m=wp2.elevation_m),
            start_time=start_dt,
            end_time=end_dt,
            duration_hours=(end_dt - start_dt).total_seconds() / 3600,
            distance_km=0.0,  # Nicht verfuegbar aus Trip-Model
            ascent_m=max(0, wp2.elevation_m - wp1.elevation_m),
            descent_m=max(0, wp1.elevation_m - wp2.elevation_m),
        )
        segments.append(segment)

    return segments
```

### 2. Active Trip Filter

Nur Trips mit Stage fuer heute (Morning) oder morgen (Evening) werden verarbeitet:

```python
def _get_active_trips(report_type: str) -> list[Trip]:
    """
    Filtert Trips die fuer den Report-Typ relevant sind.

    - morning: Trips mit Stage fuer heute
    - evening: Trips mit Stage fuer morgen
    """
    all_trips = load_all_trips()
    today = date.today()
    tomorrow = today + timedelta(days=1)

    target_date = today if report_type == "morning" else tomorrow

    return [
        trip for trip in all_trips
        if trip.get_stage_for_date(target_date) is not None
    ]
```

### 3. Scheduler Integration

```python
# src/web/scheduler.py (MODIFY)

def init_scheduler() -> None:
    global _scheduler

    if _scheduler is not None:
        return

    _scheduler = BackgroundScheduler()

    # Bestehende Compare-Subscription Jobs
    _scheduler.add_job(
        run_morning_subscriptions,
        CronTrigger(hour=7, minute=0, timezone=TIMEZONE),
        id="morning_subscriptions",
    )
    _scheduler.add_job(
        run_evening_subscriptions,
        CronTrigger(hour=18, minute=0, timezone=TIMEZONE),
        id="evening_subscriptions",
    )

    # NEU: Trip-Report Jobs
    _scheduler.add_job(
        run_morning_trip_reports,
        CronTrigger(hour=7, minute=0, timezone=TIMEZONE),
        id="morning_trip_reports",
        name="Morning Trip Reports (07:00)",
    )
    _scheduler.add_job(
        run_evening_trip_reports,
        CronTrigger(hour=18, minute=0, timezone=TIMEZONE),
        id="evening_trip_reports",
        name="Evening Trip Reports (18:00)",
    )

    _scheduler.start()


def run_morning_trip_reports() -> None:
    """Run morning trip reports for all active trips."""
    from services.trip_report_scheduler import TripReportSchedulerService
    logger.info("Running morning trip reports...")
    service = TripReportSchedulerService()
    service.send_reports("morning")


def run_evening_trip_reports() -> None:
    """Run evening trip reports for all active trips."""
    from services.trip_report_scheduler import TripReportSchedulerService
    logger.info("Running evening trip reports...")
    service.send_reports("evening")
```

### 4. Service Implementation

```python
# src/services/trip_report_scheduler.py (NEW)

class TripReportSchedulerService:
    """
    Service for scheduled trip weather reports.

    Generates and sends trip weather reports (HTML email)
    for all active trips at scheduled times.
    """

    def __init__(self) -> None:
        self._settings = Settings()
        self._formatter = TripReportFormatter()
        self._email_output = EmailOutput(self._settings)

    def send_reports(self, report_type: str) -> None:
        """
        Send reports for all active trips.

        Args:
            report_type: "morning" or "evening"
        """
        if not self._settings.can_send_email():
            logger.error("SMTP not configured, cannot send trip reports")
            return

        active_trips = self._get_active_trips(report_type)
        logger.info(f"Found {len(active_trips)} active trips for {report_type} reports")

        for trip in active_trips:
            try:
                self._send_trip_report(trip, report_type)
            except Exception as e:
                logger.error(f"Failed to send report for trip {trip.id}: {e}")

    def _send_trip_report(self, trip: Trip, report_type: str) -> None:
        """Generate and send report for a single trip."""
        # 1. Convert trip to segments
        target_date = self._get_target_date(report_type)
        segments = self._convert_trip_to_segments(trip, target_date)

        if not segments:
            logger.warning(f"No segments for trip {trip.id} on {target_date}")
            return

        # 2. Fetch weather for each segment
        segment_weather = self._fetch_weather(segments)

        # 3. Format report
        report = self._formatter.format_email(
            segments=segment_weather,
            trip_name=trip.name,
            report_type=report_type,
            trip_config=trip.weather_config,
        )

        # 4. Send email
        self._email_output.send(
            subject=report.email_subject,
            html_body=report.email_html,
            plain_text_body=report.email_plain,
        )

        logger.info(f"Trip report sent: {trip.name} ({report_type})")
```

## Configuration

| Parameter | Wert | Beschreibung |
|-----------|------|--------------|
| Morning Time | 07:00 | Europe/Vienna |
| Evening Time | 18:00 | Europe/Vienna |
| Timezone | Europe/Vienna | Explizit gesetzt |
| Provider | geosphere/openmeteo | Via bestehende Provider-Chain |

Keine zusaetzliche config.ini Erweiterung noetig - nutzt bestehende SMTP-Config.

## Expected Behavior

- **Input:** Scheduler Trigger um 07:00 oder 18:00
- **Output:**
  - HTML Email mit Trip-Report an konfigurierte Adresse
  - Log-Eintraege pro verarbeitetem Trip
- **Side effects:**
  - SMTP Email-Versand
  - Weather-API Calls (gecached durch Feature 2.4)

### Beispiel Email:

```
Subject: [GR20 Etappe 3] Morning Report - 09.02.2026

+----------+-------------+----------+--------+--------+---------+--------+
| Segment  | Time        | Duration | Temp   | Wind   | Precip  | Risk   |
+----------+-------------+----------+--------+--------+---------+--------+
| #1       | 08:00-10:00 | 2.0h     | 12-18C | 30km/h | 5.0mm   | OK     |
| #2       | 10:00-12:00 | 2.0h     | 15-20C | 25km/h | 2.0mm   | OK     |
+----------+-------------+----------+--------+--------+---------+--------+

Summary: Max 20C, Max Wind 30km/h, Total 7.0mm
```

## Files to Create/Modify

| File | Action | LOC |
|------|--------|-----|
| `src/services/trip_report_scheduler.py` | NEW | ~120 |
| `src/web/scheduler.py` | MODIFY | ~15 |
| `tests/integration/test_trip_report_scheduler.py` | NEW | ~80 |

**Total: ~215 LOC** (unter 250 Limit)

## Testing Strategy

### Integration Tests (Real API - NO MOCKS!)

```python
def test_send_morning_report_real_email():
    """E2E: Generate and send real trip report via SMTP."""
    # 1. Create test trip with today's date
    # 2. Call service.send_reports("morning")
    # 3. Verify email via IMAP
    # 4. Check email content with email_spec_validator

def test_active_trip_filter():
    """Verify only trips with today's/tomorrow's stage are processed."""

def test_convert_trip_to_segments():
    """Verify Trip→TripSegment conversion."""
```

### E2E Test Hook

```bash
# Nach Implementation
uv run python3 .claude/hooks/e2e_browser_test.py email --check "Trip Report" --send-from-ui
uv run python3 .claude/hooks/email_spec_validator.py
```

## Known Limitations

- Uhrzeiten nicht pro Trip konfigurierbar (Feature 3.5 wird das ergaenzen)
- Keine SMS-Versand Integration (nur Email im MVP)
- Kein Retry bei fehlgeschlagenen Emails
- Server muss laufen fuer automatischen Versand

## Error Handling

```python
try:
    self._send_trip_report(trip, report_type)
except ProviderRequestError as e:
    logger.error(f"Weather fetch failed for {trip.id}: {e}")
except SMTPError as e:
    logger.error(f"Email send failed for {trip.id}: {e}")
except Exception as e:
    logger.error(f"Unexpected error for {trip.id}: {e}")
```

Fehler bei einem Trip blockieren NICHT die anderen Trips.

## Changelog

- 2026-02-16: Updated with error handling (WEATHER-04) - handles error segments and sends service emails
- 2026-02-09: v1.0 Initial spec created (Feature 3.3)
