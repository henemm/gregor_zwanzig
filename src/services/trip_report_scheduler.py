"""
Trip report scheduler service.

Feature 3.3: Scheduled trip weather reports (Morning 07:00, Evening 18:00).
Generates and sends HTML email reports for active trips.

SPEC: docs/specs/modules/trip_report_scheduler.md v1.0
"""
from __future__ import annotations

import logging
import math
from datetime import date, datetime, time, timedelta, timezone
from typing import TYPE_CHECKING, List, Optional

from app.config import Settings
from app.loader import load_all_trips
from app.models import GPXPoint, NormalizedTimeseries, SegmentWeatherData, SegmentWeatherSummary, TripSegment
from formatters.trip_report import TripReportFormatter
from outputs.email import EmailOutput

if TYPE_CHECKING:
    from app.trip import Trip

logger = logging.getLogger("trip_report_scheduler")


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


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

    def send_reports_for_hour(self, current_hour: int) -> int:
        """
        Send reports for trips whose configured time matches current_hour.

        Called hourly by the scheduler. Checks both morning and evening
        times per trip against the current hour.

        Args:
            current_hour: Current hour (0-23) in Europe/Vienna

        Returns:
            Number of reports successfully sent
        """
        if not self._settings.can_send_email():
            return 0

        sent = 0

        # Check morning reports
        for trip in self._get_active_trips("morning"):
            if self._get_morning_hour(trip) == current_hour:
                try:
                    self._send_trip_report(trip, "morning")
                    sent += 1
                except Exception as e:
                    logger.error(f"Failed morning report for {trip.id}: {e}")

        # Check evening reports
        for trip in self._get_active_trips("evening"):
            if self._get_evening_hour(trip) == current_hour:
                try:
                    self._send_trip_report(trip, "evening")
                    sent += 1
                except Exception as e:
                    logger.error(f"Failed evening report for {trip.id}: {e}")

        return sent

    def _get_morning_hour(self, trip: "Trip") -> int:
        """Get configured morning hour for trip (default: 7)."""
        if trip.report_config and trip.report_config.morning_time:
            return trip.report_config.morning_time.hour
        return 7

    def _get_evening_hour(self, trip: "Trip") -> int:
        """Get configured evening hour for trip (default: 18)."""
        if trip.report_config and trip.report_config.evening_time:
            return trip.report_config.evening_time.hour
        return 18

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

    def _compute_stage_stats(self, stage) -> dict:
        """Compute aggregate stats for a stage from its waypoints."""
        wps = stage.waypoints
        if len(wps) < 2:
            return {}

        total_dist = 0.0
        total_ascent = 0.0
        total_descent = 0.0
        max_elev = max(wp.elevation_m for wp in wps)

        for i in range(len(wps) - 1):
            total_dist += _haversine_km(
                wps[i].lat, wps[i].lon, wps[i + 1].lat, wps[i + 1].lon,
            )
            diff = wps[i + 1].elevation_m - wps[i].elevation_m
            if diff > 0:
                total_ascent += diff
            else:
                total_descent += abs(diff)

        return {
            "distance_km": round(total_dist, 1),
            "ascent_m": round(total_ascent),
            "descent_m": round(total_descent),
            "max_elevation_m": max_elev,
        }

    def send_test_report(self, trip: "Trip", report_type: str) -> None:
        """
        Send a manual test report for a trip.

        Public wrapper around _send_trip_report for UI-triggered sends.

        Args:
            trip: Trip object
            report_type: "morning" or "evening"

        Raises:
            ValueError: If report_type is invalid
            Exception: If email sending fails
        """
        if report_type not in ("morning", "evening"):
            raise ValueError(f"Invalid report_type: {report_type}")
        self._send_trip_report(trip, report_type)

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

        # 3. Stage info for header
        stage = trip.get_stage_for_date(target_date)
        stage_name = stage.name if stage else None
        stage_stats = self._compute_stage_stats(stage) if stage else None

        # 4. Night weather (evening reports only)
        night_weather = None
        if report_type == "evening" and segment_weather:
            night_weather = self._fetch_night_weather(segment_weather[-1])

        # 5. Thunder forecast (+1/+2 days)
        thunder_forecast = self._build_thunder_forecast(
            segment_weather[-1], target_date,
        )

        # 6. Multi-day trend (configurable per report type)
        multi_day_trend = None
        if segment_weather:
            dc = trip.display_config
            trend_reports = dc.multi_day_trend_reports if dc else ["evening"]
            if report_type in trend_reports:
                multi_day_trend = self._build_stage_trend(trip, target_date)

        # 7. Format report (uses unified display config from trip)
        report = self._formatter.format_email(
            segments=segment_weather,
            trip_name=trip.name,
            report_type=report_type,
            display_config=trip.display_config,
            night_weather=night_weather,
            thunder_forecast=thunder_forecast,
            multi_day_trend=multi_day_trend,
            stage_name=stage_name,
            stage_stats=stage_stats,
        )

        # 7. Send email
        email_output = EmailOutput(self._settings)
        email_output.send(
            subject=report.email_subject,
            body=report.email_html,
            plain_text_body=report.email_plain,
        )

        logger.info(f"Trip report sent: {trip.name} ({report_type})")

        # 8. WEATHER-04: Service-E-Mail bei SMS-only + Fehler
        errors = [s for s in segment_weather if s.has_error]
        if errors:
            config = trip.report_config
            is_sms_only = config and config.send_sms and not config.send_email
            if is_sms_only:
                self._send_service_error_email(trip, errors, report_type)

        # 9. Save weather snapshot for alert comparison
        try:
            from services.weather_snapshot import WeatherSnapshotService
            WeatherSnapshotService().save(trip.id, segment_weather, target_date)
        except Exception as e:
            logger.warning(f"Failed to save weather snapshot for {trip.id}: {e}")

    def _interpolate_arrival_time(
        self,
        from_wp,
        to_wp,
        base_time: time,
    ) -> time:
        """Estimate arrival time based on distance and elevation change.

        Uses standard hiking speeds: 4 km/h flat, 300 Hm/h ascent, 500 Hm/h descent.
        """
        dist_km = _haversine_km(from_wp.lat, from_wp.lon, to_wp.lat, to_wp.lon)
        elev_diff = (to_wp.elevation_m or 0) - (from_wp.elevation_m or 0)

        # Hiking time from distance (flat terrain)
        time_flat_h = dist_km / 4.0

        # Hiking time from elevation
        if elev_diff > 0:
            time_elev_h = elev_diff / 300.0
        else:
            time_elev_h = abs(elev_diff) / 500.0

        # Use the larger of flat vs elevation time (dominates hiking duration)
        total_hours = max(time_flat_h, time_elev_h)
        # Minimum 15 minutes between waypoints
        total_hours = max(total_hours, 0.25)

        base_dt = datetime.combine(date.today(), base_time)
        arrival_dt = base_dt + timedelta(hours=total_hours)
        return arrival_dt.time()

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
        # Use stage.start_time as fallback for first waypoint without time_window
        default_start = stage.start_time if stage.start_time else time(8, 0)
        cumulative_time = default_start

        for i in range(len(waypoints) - 1):
            wp1 = waypoints[i]
            wp2 = waypoints[i + 1]

            # Get wp1 start time (with interpolation fallback)
            if wp1.time_window is None:
                if i == 0:
                    wp1_start = default_start
                else:
                    wp1_start = self._interpolate_arrival_time(
                        waypoints[i - 1], wp1, cumulative_time,
                    )
                    logger.info(f"Interpolated time for {wp1.id}: {wp1_start}")
            else:
                wp1_start = wp1.time_window.start

            cumulative_time = wp1_start

            # Get wp2 start time (with interpolation fallback)
            if wp2.time_window is None:
                wp2_start = self._interpolate_arrival_time(
                    wp1, wp2, wp1_start,
                )
                logger.info(f"Interpolated time for {wp2.id}: {wp2_start}")
            else:
                wp2_start = wp2.time_window.start

            # Convert time to datetime with UTC timezone
            start_dt = datetime.combine(
                target_date,
                wp1_start,
                tzinfo=timezone.utc
            )
            end_dt = datetime.combine(
                target_date,
                wp2_start,
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

            # Calculate distance and ascent/descent
            elev1 = wp1.elevation_m if wp1.elevation_m else 0
            elev2 = wp2.elevation_m if wp2.elevation_m else 0
            elev_diff = elev2 - elev1
            dist_km = _haversine_km(wp1.lat, wp1.lon, wp2.lat, wp2.lon)

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
                distance_km=round(dist_km, 1),
                ascent_m=float(max(0, elev_diff)),
                descent_m=float(max(0, -elev_diff)),
            )
            segments.append(segment)

        # Destination segment: weather at the final waypoint (Zielort)
        if segments and waypoints:
            last_wp = waypoints[-1]
            arrival_time = segments[-1].end_time
            elev = float(last_wp.elevation_m) if last_wp.elevation_m else 0.0

            destination_segment = TripSegment(
                segment_id="Ziel",
                start_point=GPXPoint(
                    lat=last_wp.lat,
                    lon=last_wp.lon,
                    elevation_m=elev,
                ),
                end_point=GPXPoint(
                    lat=last_wp.lat,
                    lon=last_wp.lon,
                    elevation_m=elev,
                ),
                start_time=arrival_time,
                end_time=arrival_time + timedelta(hours=2),
                duration_hours=2.0,
                distance_km=0.0,
                ascent_m=0.0,
                descent_m=0.0,
            )
            segments.append(destination_segment)

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

        # OpenMeteo with automatic regional model selection (AROME, ICON-D2, ECMWF)
        provider = get_provider("openmeteo")
        service = SegmentWeatherService(provider)

        weather_data = []
        for segment in segments:
            try:
                data = service.fetch_segment_weather(segment)
                weather_data.append(data)
            except Exception as e:
                logger.error(
                    f"Weather fetch failed for segment {segment.segment_id}: {e}"
                )
                # WEATHER-04: Error-Placeholder statt auslassen
                error_data = SegmentWeatherData(
                    segment=segment,
                    timeseries=None,
                    aggregated=SegmentWeatherSummary(),
                    fetched_at=datetime.now(timezone.utc),
                    provider="unknown",
                    has_error=True,
                    error_message=str(e),
                )
                weather_data.append(error_data)

        return weather_data

    def _fetch_night_weather(
        self,
        last_segment: SegmentWeatherData,
    ) -> Optional[NormalizedTimeseries]:
        """
        Fetch night weather from arrival until 06:00 next morning.

        Creates a temporary segment at the arrival point spanning two days
        so the provider returns data for both evening and next morning.

        Args:
            last_segment: Weather data for the last segment of the day

        Returns:
            NormalizedTimeseries covering arrival hour through 06:00 next day
        """
        from providers.base import get_provider
        from services.segment_weather import SegmentWeatherService

        seg = last_segment.segment
        arrival = seg.end_time
        next_morning = datetime.combine(
            arrival.date() + timedelta(days=1),
            datetime.min.time(),
            tzinfo=timezone.utc,
        ).replace(hour=6)

        # Create a temporary segment spanning arrival → 06:00 next day
        night_segment = TripSegment(
            segment_id=999,
            start_point=seg.end_point,
            end_point=seg.end_point,
            start_time=arrival,
            end_time=next_morning,
            duration_hours=(next_morning - arrival).total_seconds() / 3600,
            distance_km=0.0,
            ascent_m=0.0,
            descent_m=0.0,
        )

        try:
            provider = get_provider("openmeteo")
            service = SegmentWeatherService(provider)
            night_data = service.fetch_segment_weather(night_segment)
            return night_data.timeseries
        except Exception as e:
            logger.warning(f"Failed to fetch night weather: {e}")
            # Fallback: use last segment's timeseries (evening hours only)
            if last_segment.timeseries and last_segment.timeseries.data:
                return last_segment.timeseries
            return None

    def _build_stage_trend(
        self,
        trip,
        target_date: date,
    ) -> Optional[list[dict]]:
        """
        Build trend rows for each future stage using CompactSummaryFormatter.

        Same algorithm as the daily compact summary (F2) — DRY principle.

        SPEC: docs/specs/modules/multi_day_trend.md v3.0
        """
        from formatters.compact_summary import CompactSummaryFormatter
        from app.metric_catalog import build_default_display_config

        WEEKDAYS_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        formatter = CompactSummaryFormatter()
        dc = trip.display_config or build_default_display_config()

        future_stages = trip.get_future_stages(target_date)
        if not future_stages:
            return None

        trend = []
        for stage in future_stages:
            try:
                segments = self._convert_trip_to_segments(trip, stage.date)
                if not segments:
                    continue

                seg_weather = self._fetch_weather(segments)
                if not seg_weather:
                    continue

                summary = formatter.format_stage_summary(seg_weather, stage.name, dc)

                trend.append({
                    "weekday": WEEKDAYS_DE[stage.date.weekday()],
                    "date": stage.date,
                    "stage_name": stage.name,
                    "summary": summary,
                })
            except Exception as e:
                logger.warning(f"Failed to build trend for stage {stage.id}: {e}")
                continue

        return trend if trend else None

    def _build_thunder_forecast(
        self,
        last_segment: SegmentWeatherData,
        target_date: date,
    ) -> Optional[dict]:
        """
        Build thunder forecast for +1 and +2 days from timeseries data.

        Scans the full provider timeseries for thunder levels on future days.

        Args:
            last_segment: Weather data with timeseries
            target_date: Base date

        Returns:
            Dict with "+1" and "+2" entries, or None if no thunder data
        """
        from app.models import ThunderLevel

        if not last_segment.timeseries or not last_segment.timeseries.data:
            return None

        # Check if timeseries extends beyond target_date
        forecast = {}
        for offset, key in [(1, "+1"), (2, "+2")]:
            fc_date = target_date + timedelta(days=offset)
            thunder_dps = [
                dp for dp in last_segment.timeseries.data
                if dp.ts.date() == fc_date and dp.thunder_level
            ]
            if not thunder_dps:
                continue

            max_level = max(
                thunder_dps,
                key=lambda dp: (
                    0 if dp.thunder_level == ThunderLevel.NONE
                    else 1 if dp.thunder_level == ThunderLevel.MED
                    else 2
                ),
            )
            if max_level.thunder_level == ThunderLevel.NONE:
                forecast[key] = {
                    "date": fc_date.strftime("%d.%m.%Y"),
                    "level": ThunderLevel.NONE,
                    "text": "Kein Gewitter erwartet",
                }
            elif max_level.thunder_level == ThunderLevel.MED:
                forecast[key] = {
                    "date": fc_date.strftime("%d.%m.%Y"),
                    "level": ThunderLevel.MED,
                    "text": f"Gewitter möglich ab {max_level.ts.strftime('%H:%M')}",
                }
            else:
                forecast[key] = {
                    "date": fc_date.strftime("%d.%m.%Y"),
                    "level": ThunderLevel.HIGH,
                    "text": f"Starkes Gewitter erwartet ab {max_level.ts.strftime('%H:%M')}",
                }

        return forecast if forecast else None

    # WEATHER-04: Service email for SMS-only trips with provider errors
    def _send_service_error_email(
        self,
        trip: "Trip",
        errors: list[SegmentWeatherData],
        report_type: str,
    ) -> None:
        """Service-E-Mail bei Provider-Fehler fuer SMS-only Trips."""
        error_lines = "\n".join(
            f"  - Segment {e.segment.segment_id}: {e.error_message}"
            for e in errors
        )
        subject = f"[{trip.name}] Wetterdaten nicht verfuegbar"
        body = (
            f"<h3>Service-Benachrichtigung</h3>"
            f"<p><b>Trip:</b> {trip.name}<br>"
            f"<b>Report:</b> {report_type.title()}<br>"
            f"<b>Problem:</b> Wetterdaten konnten nicht abgerufen werden.</p>"
            f"<p><b>Betroffene Segmente:</b></p>"
            f"<pre>{error_lines}</pre>"
            f"<p><small>Diese E-Mail wurde automatisch gesendet, weil Ihr Trip "
            f"nur SMS aktiviert hat und Anbieter-Fehler aufgetreten sind.</small></p>"
        )
        try:
            EmailOutput(self._settings).send(subject=subject, body=body, html=True)
            logger.info(f"Service error email sent for {trip.name}")
        except Exception as e:
            logger.error(f"Failed to send service error email: {e}")
