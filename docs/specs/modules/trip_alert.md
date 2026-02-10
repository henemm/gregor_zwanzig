---
entity_id: trip_alert
type: module
created: 2026-02-10
updated: 2026-02-10
status: draft
version: "1.0"
tags: [alert, trip, weather, change-detection, story3]
---

# Trip Alert Service

## Approval

- [x] Approved

## Purpose

Sendet sofortige Email-Alerts bei signifikanten Wetteraenderungen (severity >= moderate).
Nutzt WeatherChangeDetectionService (Feature 2.5) und TripReportFormatter (Feature 3.1).
Implementiert Throttling (max 1 Alert pro 2h pro Trip) um Spam zu vermeiden.

## Source

- **File:** `src/services/trip_alert.py` (NEW)
- **Identifier:** `TripAlertService`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/weather_change_detection.py` | module | Erkennt signifikante Aenderungen |
| `src/services/trip_report_scheduler.py` | module | Shared: _convert_trip_to_segments, _fetch_weather |
| `src/formatters/trip_report.py` | module | Formatiert Alert-Email mit changes |
| `src/outputs/email.py` | module | Sendet Email |
| `src/app/models.WeatherChange` | dataclass | Change-DTO |
| `src/app/models.ChangeSeverity` | enum | MINOR/MODERATE/MAJOR |

## Architecture

```
TripAlertService
    |
    +-- check_and_send_alerts(trip: Trip, cached_weather: list[SegmentWeatherData])
    |       |
    |       +-- 1. Fetch fresh weather for segments
    |       +-- 2. Compare: WeatherChangeDetectionService.detect_changes()
    |       +-- 3. Filter: severity in [MODERATE, MAJOR]
    |       +-- 4. Throttle: check _last_alert_times[trip.id]
    |       +-- 5. Format: TripReportFormatter(type="alert", changes=...)
    |       +-- 6. Send: EmailOutput.send()
    |       +-- 7. Update: _last_alert_times[trip.id] = now
    |
    +-- _last_alert_times: dict[str, datetime]  # In-memory throttle store
    +-- _throttle_hours: int = 2
```

## Implementation Details

### 1. TripAlertService Class

```python
# src/services/trip_alert.py

class TripAlertService:
    """
    Service for sending weather change alerts.

    Detects significant weather changes and sends immediate alerts
    with throttling to prevent spam.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        throttle_hours: int = 2,
    ) -> None:
        self._settings = settings if settings else Settings()
        self._formatter = TripReportFormatter()
        self._change_detector = WeatherChangeDetectionService()
        self._throttle_hours = throttle_hours
        self._last_alert_times: dict[str, datetime] = {}

    def check_and_send_alerts(
        self,
        trip: Trip,
        cached_weather: list[SegmentWeatherData],
    ) -> bool:
        """
        Check for weather changes and send alert if significant.

        Args:
            trip: Trip to check
            cached_weather: Previously fetched weather data

        Returns:
            True if alert was sent, False otherwise
        """
        # 1. Check throttle
        if self._is_throttled(trip.id):
            logger.debug(f"Alert throttled for trip {trip.id}")
            return False

        # 2. Fetch fresh weather
        fresh_weather = self._fetch_fresh_weather(cached_weather)

        # 3. Detect changes
        all_changes = []
        for cached, fresh in zip(cached_weather, fresh_weather):
            changes = self._change_detector.detect_changes(cached, fresh)
            all_changes.extend(changes)

        # 4. Filter significant changes (MODERATE or MAJOR)
        significant = [
            c for c in all_changes
            if c.severity in [ChangeSeverity.MODERATE, ChangeSeverity.MAJOR]
        ]

        if not significant:
            logger.debug(f"No significant changes for trip {trip.id}")
            return False

        # 5. Send alert
        self._send_alert(trip, fresh_weather, significant)

        # 6. Update throttle
        self._last_alert_times[trip.id] = datetime.now(timezone.utc)

        return True

    def _is_throttled(self, trip_id: str) -> bool:
        """Check if alert is throttled for this trip."""
        last_alert = self._last_alert_times.get(trip_id)
        if last_alert is None:
            return False

        elapsed = datetime.now(timezone.utc) - last_alert
        return elapsed < timedelta(hours=self._throttle_hours)

    def _send_alert(
        self,
        trip: Trip,
        weather: list[SegmentWeatherData],
        changes: list[WeatherChange],
    ) -> None:
        """Format and send alert email."""
        report = self._formatter.format_email(
            segments=weather,
            trip_name=trip.name,
            report_type="alert",
            trip_config=trip.weather_config,
            changes=changes,
        )

        email_output = EmailOutput(self._settings)
        email_output.send(
            subject=report.email_subject,
            html_body=report.email_html,
            plain_text_body=report.email_plain,
        )

        logger.info(f"Alert sent for trip {trip.name}: {len(changes)} changes")
```

### 2. Integration mit Scheduler (optional)

Kann spaeter in Scheduler integriert werden um periodisch zu pruefen:

```python
# In scheduler.py (future enhancement)
def run_alert_checks() -> None:
    """Check all trips for weather changes."""
    service = TripAlertService()
    cache = WeatherCacheService()

    for trip in load_all_trips():
        cached = cache.get_trip_weather(trip.id)
        if cached:
            service.check_and_send_alerts(trip, cached)
```

### 3. Alert Email Format

TripReportFormatter generiert bereits Alert-Emails mit `changes` Section:

- **Subject:** `[{trip_name}] Weather Alert - {date}`
- **Header:** Warning icon + "Weather Changes Detected"
- **Changes Section:** List of changed metrics with old→new values
- **Segments Table:** Normal segment weather table

## Configuration

| Parameter | Default | Beschreibung |
|-----------|---------|--------------|
| throttle_hours | 2 | Min. Zeit zwischen Alerts pro Trip |
| severity_filter | MODERATE, MAJOR | Welche Severities triggern Alert |

Keine config.ini Erweiterung noetig - Defaults sind sinnvoll.

## Expected Behavior

- **Input:** Trip + cached weather data
- **Output:**
  - Alert Email wenn signifikante Aenderungen (severity >= MODERATE)
  - Keine Email wenn throttled (< 2h seit letztem Alert)
  - Keine Email wenn nur MINOR changes
- **Side effects:**
  - SMTP Email-Versand
  - Update _last_alert_times

### Beispiel Alert Email:

```
Subject: [GR20 Etappe 3] Weather Alert - 10.02.2026

⚠️ Weather Changes Detected

• temperature: 18.0 → 25.0 (Δ +7.0)
• wind_max_kmh: 30.0 → 55.0 (Δ +25.0)

[Normal segment table follows...]
```

## Files to Create/Modify

| File | Action | LOC |
|------|--------|-----|
| `src/services/trip_alert.py` | NEW | ~100 |
| `tests/integration/test_trip_alert.py` | NEW | ~80 |

**Total: ~180 LOC** (unter 250 Limit)

## Testing Strategy

### Unit Tests

```python
def test_filter_significant_changes():
    """Only MODERATE and MAJOR severity should trigger alert."""

def test_throttle_prevents_spam():
    """Second alert within 2h should be blocked."""

def test_throttle_expires():
    """Alert after 2h should be allowed."""
```

### Integration Tests

```python
def test_detect_and_send_alert():
    """Full flow: detect change → format → send email."""
    # Uses real WeatherChangeDetectionService
    # Uses real TripReportFormatter
    # Mocks only EmailOutput (or uses real SMTP in E2E)
```

## Known Limitations

- Throttle ist in-memory (verloren bei Server-Restart)
- Keine Persistenz der letzten Alert-Zeiten
- Kein SMS-Versand (nur Email im MVP)
- Keine User-Config fuer Throttle-Zeit (Feature 3.5)

## Error Handling

```python
try:
    self._send_alert(trip, weather, changes)
except SMTPError as e:
    logger.error(f"Failed to send alert for {trip.id}: {e}")
    # Don't update throttle - allow retry
except Exception as e:
    logger.error(f"Unexpected error for {trip.id}: {e}")
```

## Changelog

- 2026-02-10: v1.0 Initial spec created (Feature 3.4)
