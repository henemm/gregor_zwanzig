"""
Trip alert service - sends immediate alerts on significant weather changes.

Feature 3.4: Alert bei Änderungen (Story 3)
Detects significant weather changes and sends alert emails with throttling.

SPEC: docs/specs/modules/trip_alert.md v2.0
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from app.config import Settings
from app.models import ChangeSeverity, SegmentWeatherData, WeatherChange
from services.weather_change_detection import WeatherChangeDetectionService

if TYPE_CHECKING:
    from app.trip import Trip

logger = logging.getLogger("trip_alert")


class TripAlertService:
    """
    Service for sending weather change alerts.

    Detects significant weather changes and sends immediate alerts
    with throttling to prevent spam.

    v2.0: Per-trip thresholds via from_trip_config(), file-based throttle persistence,
    check_all_trips() for scheduler integration.

    Example:
        >>> service = TripAlertService()
        >>> sent = service.check_and_send_alerts(trip, cached_weather)
        >>> print(f"Alert sent: {sent}")
    """

    THROTTLE_FILE = Path("data/users/default/alert_throttle.json")

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
        self._change_detector = WeatherChangeDetectionService()
        self._throttle_hours = throttle_hours
        self._last_alert_times: dict[str, datetime] = self._load_throttle_times()

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

        # 1a. Create change detector with per-trip thresholds
        # Priority: display_config (per-metric) > report_config (legacy 3-slider) > catalog defaults
        if trip.display_config and trip.display_config.get_alert_enabled_metrics():
            self._change_detector = WeatherChangeDetectionService.from_display_config(
                trip.display_config
            )
        elif trip.report_config:
            self._change_detector = WeatherChangeDetectionService.from_trip_config(
                trip.report_config
            )
        else:
            self._change_detector = WeatherChangeDetectionService()

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

        # 6. Update throttle (only on success) + persist
        self._last_alert_times[trip.id] = datetime.now(timezone.utc)
        self._save_throttle_times()

        return True

    def check_all_trips(self) -> int:
        """
        Check all active trips for weather changes and send alerts.

        Called by scheduler every 30 minutes.

        Returns:
            Number of alerts sent
        """
        from app.loader import load_all_trips

        alerts_sent = 0
        for trip in load_all_trips():
            if not trip.report_config or not trip.report_config.alert_on_changes:
                continue

            # Skip if no cached weather available
            cached = self._get_cached_weather(trip)
            if not cached:
                continue

            try:
                if self.check_and_send_alerts(trip, cached):
                    alerts_sent += 1
            except Exception as e:
                logger.error(f"Alert check failed for trip {trip.id}: {e}")

        return alerts_sent

    def _get_cached_weather(self, trip: "Trip") -> Optional[List[SegmentWeatherData]]:
        """
        Get cached weather data for a trip from the weather cache.

        Args:
            trip: Trip to get cached weather for

        Returns:
            Cached weather data or None if not available
        """
        try:
            from services.trip_report_scheduler import TripReportSchedulerService

            scheduler = TripReportSchedulerService()
            segments = scheduler._convert_trip_to_segments(trip)
            if not segments:
                return None

            weather_data = scheduler._fetch_weather(segments, trip)
            return weather_data if weather_data else None
        except Exception as e:
            logger.debug(f"No cached weather for trip {trip.id}: {e}")
            return None

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
            self._save_throttle_times()
            logger.debug(f"Throttle cleared for trip {trip_id}")

    # --- Throttle Persistence ---

    def _load_throttle_times(self) -> dict[str, datetime]:
        """Load throttle times from JSON file."""
        if not self.THROTTLE_FILE.exists():
            return {}
        try:
            data = json.loads(self.THROTTLE_FILE.read_text())
            return {k: datetime.fromisoformat(v) for k, v in data.items()}
        except (json.JSONDecodeError, ValueError, OSError) as e:
            logger.warning(f"Failed to load throttle file: {e}")
            return {}

    def _save_throttle_times(self) -> None:
        """Save throttle times to JSON file."""
        try:
            self.THROTTLE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {k: v.isoformat() for k, v in self._last_alert_times.items()}
            self.THROTTLE_FILE.write_text(json.dumps(data, indent=2))
        except OSError as e:
            logger.error(f"Failed to save throttle file: {e}")

    # --- Change Detection ---

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
        Delegate alert dispatch to AlertProcessor (multi-channel).

        Args:
            trip: Trip object
            weather: Current weather data
            changes: Detected changes to include

        Raises:
            RuntimeError: If no channel delivered the alert
        """
        from services.alert_processor import AlertProcessor

        processor = AlertProcessor(self._settings)
        results = processor.process_alert(trip, weather, changes)

        sent_channels = [ch for ch, ok in results.items() if ok]
        if not sent_channels:
            raise RuntimeError(f"No channel delivered alert for {trip.name}")

        logger.info(
            f"Alert for {trip.name}: {len(changes)} changes via {', '.join(sent_channels)}"
        )
