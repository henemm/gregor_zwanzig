"""
Trip report scheduler service.

Feature 3.3: Scheduled trip weather reports (Morning 07:00, Evening 18:00).
Generates and sends HTML email reports for active trips.

SPEC: docs/specs/modules/trip_report_scheduler.md v1.0
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, List, Optional

from app.config import Settings
from app.loader import load_all_trips
from app.models import GPXPoint, SegmentWeatherData, TripSegment
from formatters.trip_report import TripReportFormatter
from outputs.email import EmailOutput

if TYPE_CHECKING:
    from app.trip import Trip

logger = logging.getLogger("trip_report_scheduler")


class TripReportSchedulerService:
    """
    Service for scheduled trip weather reports.

    Generates and sends trip weather reports (HTML email)
    for all active trips at scheduled times.

    Example:
        >>> service = TripReportSchedulerService()
        >>> service.send_reports("morning")  # Send reports for today's trips
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """
        Initialize the service.

        Args:
            settings: App settings (default: load from config)
        """
        self._settings = settings if settings else Settings()
        self._formatter = TripReportFormatter()

    def send_reports(self, report_type: str) -> int:
        """
        Send reports for all active trips.

        Args:
            report_type: "morning" or "evening"

        Returns:
            Number of reports successfully sent
        """
        if not self._settings.can_send_email():
            logger.error("SMTP not configured, cannot send trip reports")
            return 0

        active_trips = self._get_active_trips(report_type)
        logger.info(f"Found {len(active_trips)} active trips for {report_type} reports")

        sent_count = 0
        for trip in active_trips:
            try:
                self._send_trip_report(trip, report_type)
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send report for trip {trip.id}: {e}")

        logger.info(f"Sent {sent_count}/{len(active_trips)} {report_type} reports")
        return sent_count

    def _get_active_trips(self, report_type: str) -> List["Trip"]:
        """
        Get trips that are active for the given report type.

        - morning: Trips with a stage for today
        - evening: Trips with a stage for tomorrow

        Args:
            report_type: "morning" or "evening"

        Returns:
            List of active Trip objects
        """
        all_trips = load_all_trips()
        target_date = self._get_target_date(report_type)

        active = [
            trip for trip in all_trips
            if trip.get_stage_for_date(target_date) is not None
        ]

        logger.debug(f"Active trips for {target_date}: {[t.id for t in active]}")
        return active

    def _get_target_date(self, report_type: str) -> date:
        """
        Get the target date for the report type.

        Args:
            report_type: "morning" or "evening"

        Returns:
            date object (today for morning, tomorrow for evening)
        """
        today = date.today()
        if report_type == "morning":
            return today
        else:  # evening
            return today + timedelta(days=1)

    def _send_trip_report(self, trip: "Trip", report_type: str) -> None:
        """
        Generate and send report for a single trip.

        Args:
            trip: Trip object
            report_type: "morning" or "evening"

        Raises:
            Exception: If weather fetch or email send fails
        """
        logger.info(f"Generating {report_type} report for trip: {trip.name}")

        # 1. Convert trip to segments
        target_date = self._get_target_date(report_type)
        segments = self._convert_trip_to_segments(trip, target_date)

        if not segments:
            logger.warning(f"No segments for trip {trip.id} on {target_date}")
            return

        logger.debug(f"Created {len(segments)} segments for {trip.id}")

        # 2. Fetch weather for each segment
        segment_weather = self._fetch_weather(segments)

        if not segment_weather:
            logger.warning(f"No weather data for trip {trip.id}")
            return

        # 3. Format report
        report = self._formatter.format_email(
            segments=segment_weather,
            trip_name=trip.name,
            report_type=report_type,
            trip_config=trip.weather_config,
        )

        # 4. Send email
        email_output = EmailOutput(self._settings)
        email_output.send(
            subject=report.email_subject,
            html_body=report.email_html,
            plain_text_body=report.email_plain,
        )

        logger.info(f"Trip report sent: {trip.name} ({report_type})")

    def _convert_trip_to_segments(
        self,
        trip: "Trip",
        target_date: date
    ) -> List[TripSegment]:
        """
        Convert Trip waypoints to TripSegment DTOs.

        Creates segments between consecutive waypoints in the stage
        for the target date.

        Args:
            trip: Trip object with stages and waypoints
            target_date: Date to get the stage for

        Returns:
            List of TripSegment objects
        """
        stage = trip.get_stage_for_date(target_date)
        if stage is None:
            return []

        if len(stage.waypoints) < 2:
            logger.warning(f"Stage {stage.id} has less than 2 waypoints")
            return []

        segments = []
        waypoints = stage.waypoints

        for i in range(len(waypoints) - 1):
            wp1 = waypoints[i]
            wp2 = waypoints[i + 1]

            # Get time windows (use defaults if not set)
            if wp1.time_window is None or wp2.time_window is None:
                logger.warning(
                    f"Waypoint {wp1.id} or {wp2.id} missing time_window, skipping"
                )
                continue

            # Convert time to datetime with UTC timezone
            start_dt = datetime.combine(
                target_date,
                wp1.time_window.start,
                tzinfo=timezone.utc
            )
            end_dt = datetime.combine(
                target_date,
                wp2.time_window.start,
                tzinfo=timezone.utc
            )

            # Handle case where end is before start (shouldn't happen normally)
            if end_dt <= start_dt:
                logger.warning(
                    f"Invalid time window: {wp1.time_window} -> {wp2.time_window}"
                )
                continue

            # Calculate duration
            duration_hours = (end_dt - start_dt).total_seconds() / 3600

            # Calculate ascent/descent
            elev1 = wp1.elevation_m if wp1.elevation_m else 0
            elev2 = wp2.elevation_m if wp2.elevation_m else 0
            elev_diff = elev2 - elev1

            segment = TripSegment(
                segment_id=i + 1,
                start_point=GPXPoint(
                    lat=wp1.lat,
                    lon=wp1.lon,
                    elevation_m=float(elev1),
                ),
                end_point=GPXPoint(
                    lat=wp2.lat,
                    lon=wp2.lon,
                    elevation_m=float(elev2),
                ),
                start_time=start_dt,
                end_time=end_dt,
                duration_hours=duration_hours,
                distance_km=0.0,  # Not available from Trip model
                ascent_m=float(max(0, elev_diff)),
                descent_m=float(max(0, -elev_diff)),
            )
            segments.append(segment)

        return segments

    def _fetch_weather(
        self,
        segments: List[TripSegment]
    ) -> List[SegmentWeatherData]:
        """
        Fetch weather data for all segments.

        Uses SegmentWeatherService with provider fallback chain.

        Args:
            segments: List of TripSegment objects

        Returns:
            List of SegmentWeatherData objects
        """
        from providers.base import get_provider
        from services.segment_weather import SegmentWeatherService

        # Get default provider (uses fallback chain)
        try:
            provider = get_provider("geosphere")
        except Exception:
            logger.warning("GeoSphere unavailable, falling back to OpenMeteo")
            provider = get_provider("openmeteo")

        service = SegmentWeatherService(provider)

        weather_data = []
        for segment in segments:
            try:
                data = service.fetch_segment_weather(segment)
                weather_data.append(data)
            except Exception as e:
                logger.error(
                    f"Failed to fetch weather for segment {segment.segment_id}: {e}"
                )

        return weather_data
