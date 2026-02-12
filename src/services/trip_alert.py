"""
Trip alert service - sends immediate alerts on significant weather changes.

Feature 3.4: Alert bei Änderungen (Story 3)
Detects significant weather changes and sends alert emails with throttling.

SPEC: docs/specs/modules/trip_alert.md v1.0
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, List, Optional

from app.config import Settings
from app.models import ChangeSeverity, SegmentWeatherData, WeatherChange
from formatters.trip_report import TripReportFormatter
from outputs.email import EmailOutput
from services.weather_change_detection import WeatherChangeDetectionService

if TYPE_CHECKING:
    from app.trip import Trip

logger = logging.getLogger("trip_alert")


class TripAlertService:
    """
    Service for sending weather change alerts.

    Detects significant weather changes and sends immediate alerts
    with throttling to prevent spam.

    Example:
        >>> service = TripAlertService()
        >>> sent = service.check_and_send_alerts(trip, cached_weather)
        >>> print(f"Alert sent: {sent}")
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        throttle_hours: int = 2,
    ) -> None:
        """
        Initialize the alert service.

        Args:
            settings: App settings (default: load from config)
            throttle_hours: Minimum hours between alerts per trip (default: 2)
        """
        self._settings = settings if settings else Settings()
        self._formatter = TripReportFormatter()
        self._change_detector = WeatherChangeDetectionService()
        self._throttle_hours = throttle_hours
        self._last_alert_times: dict[str, datetime] = {}

    def check_and_send_alerts(
        self,
        trip: "Trip",
        cached_weather: List[SegmentWeatherData],
        fresh_weather: Optional[List[SegmentWeatherData]] = None,
    ) -> bool:
        """
        Check for weather changes and send alert if significant.

        Args:
            trip: Trip to check
            cached_weather: Previously fetched weather data
            fresh_weather: Optional fresh weather (fetched if not provided)

        Returns:
            True if alert was sent, False otherwise
        """
        if not self._settings.can_send_email():
            logger.error("SMTP not configured, cannot send alerts")
            return False

        # 1b. Check if alerts are disabled for this trip
        if trip.report_config and not trip.report_config.alert_on_changes:
            logger.debug(f"Alerts disabled for trip {trip.id}")
            return False

        # 1. Check throttle
        if self._is_throttled(trip.id):
            logger.debug(f"Alert throttled for trip {trip.id}")
            return False

        # 2. Fetch fresh weather if not provided
        if fresh_weather is None:
            fresh_weather = self._fetch_fresh_weather(cached_weather)

        if not fresh_weather:
            logger.warning(f"No fresh weather data for trip {trip.id}")
            return False

        # 3. Detect changes across all segments
        all_changes = self._detect_all_changes(cached_weather, fresh_weather)

        # 4. Filter significant changes (MODERATE or MAJOR only)
        significant = self._filter_significant_changes(all_changes)

        if not significant:
            logger.debug(f"No significant changes for trip {trip.id}")
            return False

        logger.info(
            f"Detected {len(significant)} significant changes for trip {trip.id}"
        )

        # 5. Send alert
        try:
            self._send_alert(trip, fresh_weather, significant)
        except Exception as e:
            logger.error(f"Failed to send alert for {trip.id}: {e}")
            return False

        # 6. Update throttle (only on success)
        self._last_alert_times[trip.id] = datetime.now(timezone.utc)

        return True

    def _is_throttled(self, trip_id: str) -> bool:
        """
        Check if alert is throttled for this trip.

        Args:
            trip_id: Trip identifier

        Returns:
            True if throttled (too soon since last alert)
        """
        last_alert = self._last_alert_times.get(trip_id)
        if last_alert is None:
            return False

        elapsed = datetime.now(timezone.utc) - last_alert
        return elapsed < timedelta(hours=self._throttle_hours)

    def get_time_until_next_alert(self, trip_id: str) -> Optional[timedelta]:
        """
        Get remaining throttle time for a trip.

        Args:
            trip_id: Trip identifier

        Returns:
            Time remaining until next alert allowed, or None if not throttled
        """
        last_alert = self._last_alert_times.get(trip_id)
        if last_alert is None:
            return None

        elapsed = datetime.now(timezone.utc) - last_alert
        remaining = timedelta(hours=self._throttle_hours) - elapsed

        if remaining.total_seconds() <= 0:
            return None

        return remaining

    def clear_throttle(self, trip_id: str) -> None:
        """
        Clear throttle for a trip (for testing or manual override).

        Args:
            trip_id: Trip identifier
        """
        if trip_id in self._last_alert_times:
            del self._last_alert_times[trip_id]
            logger.debug(f"Throttle cleared for trip {trip_id}")

    def _detect_all_changes(
        self,
        cached_weather: List[SegmentWeatherData],
        fresh_weather: List[SegmentWeatherData],
    ) -> List[WeatherChange]:
        """
        Detect changes across all segments.

        Args:
            cached_weather: Old weather data
            fresh_weather: New weather data

        Returns:
            List of all detected changes
        """
        all_changes = []

        # Match segments by segment_id
        cached_by_id = {w.segment.segment_id: w for w in cached_weather}
        fresh_by_id = {w.segment.segment_id: w for w in fresh_weather}

        for segment_id, cached in cached_by_id.items():
            fresh = fresh_by_id.get(segment_id)
            if fresh is None:
                continue

            changes = self._change_detector.detect_changes(cached, fresh)
            all_changes.extend(changes)

        return all_changes

    def _filter_significant_changes(
        self,
        changes: List[WeatherChange],
    ) -> List[WeatherChange]:
        """
        Filter to only significant changes (MODERATE or MAJOR).

        Args:
            changes: All detected changes

        Returns:
            Only changes with severity >= MODERATE
        """
        significant_severities = {ChangeSeverity.MODERATE, ChangeSeverity.MAJOR}
        return [c for c in changes if c.severity in significant_severities]

    def _fetch_fresh_weather(
        self,
        cached_weather: List[SegmentWeatherData],
    ) -> List[SegmentWeatherData]:
        """
        Fetch fresh weather for the same segments.

        Args:
            cached_weather: Cached weather with segment info

        Returns:
            Fresh weather data
        """
        from providers.base import get_provider
        from services.segment_weather import SegmentWeatherService

        # OpenMeteo with automatic regional model selection
        provider = get_provider("openmeteo")

        service = SegmentWeatherService(provider)

        fresh_weather = []
        for cached in cached_weather:
            try:
                # Clear cache to force fresh fetch
                service._cache.clear()
                fresh = service.fetch_segment_weather(cached.segment)
                fresh_weather.append(fresh)
            except Exception as e:
                logger.error(
                    f"Failed to fetch fresh weather for segment "
                    f"{cached.segment.segment_id}: {e}"
                )

        return fresh_weather

    def _send_alert(
        self,
        trip: "Trip",
        weather: List[SegmentWeatherData],
        changes: List[WeatherChange],
    ) -> None:
        """
        Format and send alert email.

        Args:
            trip: Trip object
            weather: Current weather data
            changes: Detected changes to include
        """
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

        logger.info(
            f"Alert sent for trip {trip.name}: {len(changes)} changes detected"
        )
