"""
Trip report scheduler service.

Feature 3.3: Scheduled trip weather reports (Morning 07:00, Evening 18:00).
Generates and sends HTML email reports for active trips.

SPEC: docs/specs/modules/trip_report_scheduler.md v1.0
"""
from __future__ import annotations

import dataclasses
import json
import logging
import math
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from app.config import Settings
from app.loader import load_all_trips, save_trip
from app.models import GPXPoint, NormalizedTimeseries, SegmentWeatherData, SegmentWeatherSummary, TripSegment
from formatters.trip_report import TripReportFormatter
from output.renderers.email.design_tokens import (
    FONT_UI, G_ACCENT, G_DANGER, G_INK, G_PAPER, G_SURFACE_1, WEB_FONT_LINK,
)
from outputs.email import EmailOutput
from utils.timezone import tz_for_coords

if TYPE_CHECKING:
    from app.trip import Stage, Trip

logger = logging.getLogger("trip_report_scheduler")


def _deg_to_compass(degrees) -> str:
    """Converts wind degrees to 8-point compass direction."""
    if degrees is None:
        return ""
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = round(float(degrees) / 45) % 8
    return directions[idx]


def _trend_note(thunder: str, precip_mm: float, wind_kmh: int) -> str | None:
    """Returns a hint text when conditions are notable, else None."""
    notes = []
    if thunder != "NONE":
        notes.append("Gewitter möglich")
    if precip_mm > 5:
        notes.append(f"Regen {precip_mm:.0f} mm")
    if wind_kmh > 40:
        notes.append(f"Böen bis {wind_kmh} km/h")
    return " · ".join(notes) if notes else None


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


def _parse_hhmm(value: str) -> Optional[time]:
    """Parse 'HH:MM' to a time; returns None on malformed input.

    Issue #296 — used to consume persisted Naismith arrival_calculated values.
    """
    try:
        return time.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def build_service_error_email_html(trip_name: str, report_type: str, error_lines: str) -> str:
    """Build the Service-Error E-Mail-Body with Design-System tokens.

    Used when an SMS-only trip cannot fetch weather data (provider error) and
    the user still needs to be informed via E-Mail fallback.

    Args:
        trip_name: Name of the affected trip.
        report_type: "morning" or "evening".
        error_lines: Pre-formatted multi-line error block (one segment per line).

    Returns:
        Complete HTML document string.
    """
    return (
        '<!DOCTYPE html>'
        '<html>'
        '<head>'
        '<meta charset="utf-8">'
        f'{WEB_FONT_LINK}'
        '<style>'
        f'body {{ margin:0; padding:0; background:{G_PAPER}; '
        f'font-family:{FONT_UI}; color:{G_INK}; }}'
        '.container { max-width:640px; margin:0 auto; padding:24px; }'
        f'.heading {{ border-bottom:2px solid {G_ACCENT}; color:{G_ACCENT}; '
        'padding-bottom:8px; margin:0 0 16px 0; font-size:20px; }'
        f'.meta {{ background:{G_SURFACE_1}; padding:12px 16px; '
        'border-radius:6px; margin-bottom:16px; font-size:14px; }'
        f'.error-block {{ border-left:4px solid {G_DANGER}; '
        f'background:{G_SURFACE_1}; padding:12px 16px; margin:16px 0; '
        'font-family: ui-monospace, SFMono-Regular, Menlo, monospace; '
        'font-size:13px; white-space:pre-wrap; }'
        f'.footer {{ background:{G_INK}; color:#ffffff; padding:16px 24px; '
        'text-align:center; font-size:12px; }'
        '.footer a { color:#ffffff; text-decoration:underline; }'
        '</style>'
        '</head>'
        '<body>'
        '<div class="container">'
        '<h2 class="heading">Service-Benachrichtigung</h2>'
        '<div class="meta">'
        f'<strong>Trip:</strong> {trip_name}<br>'
        f'<strong>Report:</strong> {report_type.title()}<br>'
        '<strong>Problem:</strong> Wetterdaten konnten nicht abgerufen werden.'
        '</div>'
        '<p><strong>Betroffene Segmente:</strong></p>'
        f'<div class="error-block">{error_lines}</div>'
        '<p style="font-size:13px; color:#5c5a52;">'
        'Diese E-Mail wurde automatisch gesendet, weil Ihr Trip nur SMS aktiviert '
        'hat und Anbieter-Fehler aufgetreten sind.'
        '</p>'
        '</div>'
        f'<div class="footer" style="background:{G_INK}; color:#ffffff;">'
        'Gregor Zwanzig &mdash; automatischer Wetter-Service'
        '</div>'
        '</body>'
        '</html>'
    )


class TripReportSchedulerService:
    """
    Service for scheduled trip weather reports.

    Generates and sends trip weather reports (HTML email)
    for all active trips at scheduled times.

    Example:
        >>> service = TripReportSchedulerService()
        >>> service.send_reports("morning")  # Send reports for today's trips
    """

    def __init__(self, settings: Optional[Settings] = None, user_id: str = "default") -> None:
        """
        Initialize the service.

        Args:
            settings: App settings (default: load from config)
            user_id: User identifier for data scoping
        """
        self._settings = settings if settings else Settings().with_user_profile(user_id)
        self._formatter = TripReportFormatter()
        self._user_id = user_id

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
        all_trips = load_all_trips(user_id=self._user_id)
        target_date = self._get_target_date(report_type)
        now_utc = datetime.now(timezone.utc)

        active = []
        for trip in all_trips:
            if trip.get_stage_for_date(target_date) is None:
                continue
            rc = trip.report_config
            if rc is not None:
                if rc.enabled is False:
                    continue
                if rc.paused_until is not None:
                    # Ensure tz-aware comparison
                    pu = rc.paused_until
                    if pu.tzinfo is None:
                        pu = pu.replace(tzinfo=timezone.utc)
                    if now_utc < pu:
                        continue
                if rc.skip_next is True:
                    # Consume the flag: RMW
                    new_rc = dataclasses.replace(rc, skip_next=False)
                    new_trip = dataclasses.replace(trip, report_config=new_rc)
                    save_trip(new_trip, user_id=self._user_id)
                    continue
            active.append(trip)

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

    def select_test_stage(self, trip: "Trip", report_type: str) -> Optional["Stage"]:
        """Pick the stage to use for a TEST briefing when no stage matches today/tomorrow.

        Issue #768 — Test-Pfad-Fallback (NICHT der reguläre Scheduler):

        - Wählt die zeitlich **nächste kommende** Etappe mit ``date >= heute``
          (kleinstes Datum). ``trip.get_future_stages`` ist strikt ``>`` und schließt
          „heute" aus — daher hier eine eigene ``>=``-Auswahl.
        - Liegen **alle** Etappen in der Vergangenheit, fällt es auf die chronologisch
          **erste** (früheste) Etappe zurück.
        - Leere ``stages`` → ``None``.

        Args:
            trip: Trip object.
            report_type: "morning" or "evening" (nicht ausschlaggebend für die Wahl,
                Teil des Kontrakts für Aufrufer-Symmetrie).

        Returns:
            Die gewählte Stage oder None bei leeren stages.
        """
        if not trip.stages:
            return None
        today = date.today()
        upcoming = sorted(
            (s for s in trip.stages if s.date >= today),
            key=lambda s: s.date,
        )
        if upcoming:
            return upcoming[0]
        return min(trip.stages, key=lambda s: s.date)

    def send_test_report(self, trip: "Trip", report_type: str) -> bool:
        """
        Send a manual test report for a trip.

        Public wrapper around _send_trip_report for UI-triggered sends.

        Issue #768: Test-Pfad aktiviert den Etappen-Fallback und kennzeichnet
        die Mail als Vorschau ([TEST]-Präfix + Hinweiszeile).

        Args:
            trip: Trip object
            report_type: "morning" or "evening"

        Returns:
            True if report was sent, False if no matching stage data found

        Raises:
            ValueError: If report_type is invalid
            Exception: If email sending fails
        """
        if report_type not in ("morning", "evening"):
            raise ValueError(f"Invalid report_type: {report_type}")
        return self._send_trip_report(trip, report_type, allow_test_fallback=True)

    def _send_trip_report(
        self,
        trip: "Trip",
        report_type: str,
        allow_test_fallback: bool = False,
    ) -> bool:
        """
        Generate and send report for a single trip.

        Args:
            trip: Trip object
            report_type: "morning" or "evening"

        Returns:
            True if report was sent, False if no matching stage/weather data found

        Raises:
            Exception: If weather fetch or email send fails
        """
        logger.info(f"Generating {report_type} report for trip: {trip.name}")

        # 1. Convert trip to segments
        target_date = self._get_target_date(report_type)
        segments = self._convert_trip_to_segments(trip, target_date)

        # Issue #768: Test-Pfad-Fallback — wenn am regulären Zieldatum keine
        # Etappe liegt, weicht NUR der Test-Versand auf die nächste kommende
        # (bzw. früheste) Etappe aus. Der reguläre Scheduler (Default False)
        # bleibt unberührt (AC-7).
        if not segments and allow_test_fallback:
            fb = self.select_test_stage(trip, report_type)
            if fb is not None:
                target_date = fb.date
                segments = self._convert_trip_to_segments(trip, target_date)

        if not segments:
            logger.warning(f"No segments for trip {trip.id} on {target_date}")
            return False

        logger.debug(f"Created {len(segments)} segments for {trip.id}")

        # 1b. Compute local timezone from coordinates for display
        # (tz_for_coords now imported top-level — Bug #401)
        trip_tz = tz_for_coords(segments[0].start_point.lat, segments[0].start_point.lon)

        # 2. Wind exposition detection (before weather fetch, needs TripSegments)
        from services.wind_exposition import WindExpositionService
        try:
            min_elev_kwargs = {}
            if trip.report_config and trip.report_config.wind_exposition_min_elevation_m is not None:
                min_elev_kwargs["min_elevation_m"] = trip.report_config.wind_exposition_min_elevation_m
            exposed_sections = WindExpositionService().detect_exposed_from_segments(
                segments, **min_elev_kwargs
            )
        except Exception as e:
            logger.warning(f"Wind exposition detection failed for {trip.id}: {e}")
            exposed_sections = []

        # 3. Fetch weather for each segment
        segment_weather = self._fetch_weather(segments)

        if not segment_weather:
            logger.warning(f"No weather data for trip {trip.id}")
            return False

        # 2b. Ensemble-Anreicherung: 1 API-Call für letzten Waypoint der letzten Etappe
        self._enrich_ensemble_for_trip(trip, segment_weather)

        # 2c. F12 / Issue #122 (refactored Issue #479):
        # Stabilitäts-Label für die kommenden Etappen — wird aus den bereits
        # vorhandenen `confidence_pct_min`-Werten der Folge-Segmente
        # abgeleitet; kein separater Z500-API-Call mehr.
        stability_result = None
        try:
            from services.weather_pattern import WeatherPatternService
            stability_result = WeatherPatternService().compute_for_trip(
                trip, target_date, segment_weather
            )
        except Exception as e:
            logger.warning(f"WeatherPatternService failed for {trip.id}: {e}")

        # 3. Stage info for header
        stage = trip.get_stage_for_date(target_date)
        stage_name = trip.numbered_stage_label(stage) if stage else None
        stage_stats = self._compute_stage_stats(stage) if stage else None

        # 4. Night weather (evening reports only)
        night_weather = None
        if report_type == "evening" and segment_weather:
            night_weather = self._fetch_night_weather(segment_weather[-1])

        # 5. Thunder forecast (+1/+2 days)
        thunder_forecast = self._build_thunder_forecast(
            segment_weather[-1], target_date, tz=trip_tz,
        )

        # 6. Multi-day trend (configurable per report type — read from report_config with fallback)
        multi_day_trend = None
        if segment_weather:
            rc = trip.report_config
            dc = trip.display_config
            trend_reports = (
                rc.multi_day_trend_reports
                if rc is not None
                else (dc.multi_day_trend_reports if dc else ["evening"])
            )
            if report_type in trend_reports:
                multi_day_trend = self._build_stage_trend(trip, target_date, tz=trip_tz)

        # 7. Usable daylight (F11) — respects report_config toggle
        daylight_window = None
        show_daylight = trip.report_config.show_daylight if trip.report_config else True
        if show_daylight:
            try:
                from services.daylight_service import compute_usable_daylight
                first_seg = segments[0]
                # Route max elevation from all waypoints in stage
                route_max_elev = stage_stats.get("max_elevation_m", first_seg.start_point.elevation_m) if stage_stats else first_seg.start_point.elevation_m
                # Collect all forecast data points for weather corrections
                all_forecast_data = []
                for sw in segment_weather:
                    if sw.timeseries and sw.timeseries.data:
                        all_forecast_data.extend(sw.timeseries.data)
                daylight_window = compute_usable_daylight(
                    lat=first_seg.start_point.lat,
                    lon=first_seg.start_point.lon,
                    target_date=target_date,
                    elevation_m=first_seg.start_point.elevation_m,
                    route_max_elevation_m=float(route_max_elev),
                    forecast_data=all_forecast_data,
                )
            except Exception as e:
                logger.warning(f"Daylight computation failed for {trip.id}: {e}")

        # Option A: patch display_config.show_compact_summary from report_config
        if trip.display_config and trip.report_config:
            trip.display_config.show_compact_summary = trip.report_config.show_compact_summary

        # 7b. Vortag-Vergleich (Issue #750): gestrigen Snapshot laden + Deltas
        # berechnen. Fail-soft — fehlt der Vortag, bleibt day_comparison None.
        day_comparison = None
        show_yc = trip.report_config.show_yesterday_comparison if trip.report_config else True
        if show_yc:
            try:
                from services.weather_snapshot import WeatherSnapshotService
                from services.day_comparison import DayComparisonService
                yday = WeatherSnapshotService(self._user_id).load_dated(
                    trip.id, target_date - timedelta(days=1))
                if yday:
                    day_comparison = DayComparisonService().compare(segment_weather, yday)
            except Exception as e:
                logger.warning(f"Vortag-Vergleich übersprungen für {trip.id}: {e}")
                day_comparison = None

        # 8. Format report (uses unified display config from trip)
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
            exposed_sections=exposed_sections,
            daylight=daylight_window,
            tz=trip_tz,
            profile=trip.aggregation.profile,
            stability_result=stability_result,
            report_config=trip.report_config,
            day_comparison=day_comparison,
            shortcode=getattr(trip, 'shortcode', None) or None,
        )

        # Issue #768 (AC-6): Test-Pfad kennzeichnen — [TEST]-Betreff + Hinweiszeile
        # mit der tatsächlich verwendeten Etappe + deren Datum. Nur im Test-Pfad.
        if allow_test_fallback:
            human_date = target_date.strftime("%d.%m.%Y")
            hint = f"Test-Vorschau für {stage_name or 'Etappe'} am {human_date}"
            report.email_subject = f"[TEST] {report.email_subject}"
            if report.email_plain:
                report.email_plain = f"{hint}\n\n{report.email_plain}"
            if report.email_html:
                report.email_html = report.email_html.replace(
                    "<body>", f"<body><p>{hint}</p>", 1,
                ) if "<body>" in report.email_html else f"<p>{hint}</p>{report.email_html}"
            if getattr(report, "telegram_text", None):
                report.telegram_text = f"{hint}\n\n{report.telegram_text}"

        # 7. Send via configured channels
        config = trip.report_config

        # 7a. Email (bugfix: respect send_email flag)
        # Issue #722: compact format sends single text/plain (html="" → html=False path)
        if not config or config.send_email:
            email_output = EmailOutput(self._settings)
            if report.email_html:
                email_output.send(
                    subject=report.email_subject,
                    body=report.email_html,
                    plain_text_body=report.email_plain,
                    mail_type="trip-briefing",
                    mail_format="full",
                )
            else:
                email_output.send(
                    subject=report.email_subject,
                    body=report.email_plain,
                    html=False,
                    mail_type="trip-briefing",
                    mail_format="compact",
                )

        # 7c. Send Telegram if configured (Issue #360: kanal-bewusster Body)
        if config and config.send_telegram and self._settings.can_send_telegram():
            try:
                from outputs.telegram import TelegramOutput
                TelegramOutput(self._settings).send(
                    subject=report.email_subject,
                    body=report.telegram_text or report.email_plain,
                )
            except Exception as e:
                logger.error(f"Telegram send failed for {trip.name}: {e}")

        # Issue #393: Briefing-Log für Cockpit-Kachel "Was geht heute raus".
        # Nur nach erfolgreichem Versand (kein Exception oben) anhängen.
        sent_channels: List[str] = []
        if not config or config.send_email:
            sent_channels.append("email")
        if config and config.send_telegram and self._settings.can_send_telegram():
            sent_channels.append("telegram")
        self._append_briefing_log(trip.id, report_type, sent_channels)

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
            _snapshot_svc = WeatherSnapshotService(self._user_id)
            _snapshot_svc.save(trip.id, segment_weather, target_date)
            _snapshot_svc.save_dated(trip.id, target_date, segment_weather)
        except Exception as e:
            logger.warning(f"Failed to save weather snapshot for {trip.id}: {e}")

        # 10. Issue #816 (B): Briefing = neue, stabile Alert-Referenz → das
        # Melde-Gedächtnis des Trips zurücksetzen, damit der nächste Alert wieder
        # gegen das frische Briefing vergleicht.
        self._reset_alert_state_after_briefing(trip.id)

        return True

    def _reset_alert_state_after_briefing(self, trip_id: str) -> None:
        """Issue #816 (B): Alert-Melde-Gedächtnis nach Briefing-Versand löschen."""
        try:
            from services.alert_state import AlertStateService
            AlertStateService(user_id=self._user_id).reset(trip_id)
        except Exception as e:
            logger.warning(f"Failed to reset alert_state for {trip_id}: {e}")

    def _append_briefing_log(self, trip_id: str, kind: str, channels: List[str]) -> None:
        """Issue #393: Hängt einen Briefing-Versand-Eintrag an briefing_log.json an.

        Wird von Go (GET /api/cockpit/status) read-only gelesen. Kein Bereinigen —
        das Frontend filtert auf "heute".
        """
        path = Path(f"data/users/{self._user_id}/briefing_log.json")
        data = json.loads(path.read_text()) if path.exists() else {"entries": []}
        data["entries"].append({
            "trip_id": trip_id,
            "kind": kind,
            "sent_at": datetime.now(tz=timezone.utc).isoformat(),
            "channels": channels,
        })
        path.write_text(json.dumps(data, indent=2))

    def _convert_trip_to_segments(
        self,
        trip: "Trip",
        target_date: date
    ) -> List[TripSegment]:
        """Thin delegator — real logic lives in services.trip_segments (Issue #822).

        Behaviour is bit-identical to the previous inline implementation;
        the refactor is a pure Extract Function with no semantic change.
        """
        from services.trip_segments import convert_trip_to_segments
        return convert_trip_to_segments(trip, target_date)

    def _fetch_weather(
        self,
        segments: List[TripSegment],
        provider=None,
    ) -> List[SegmentWeatherData]:
        """
        Fetch weather data for all segments.

        Uses SegmentWeatherService with provider fallback chain.

        Args:
            segments: List of TripSegment objects
            provider: Optional WeatherProvider instance. When None (default),
                the standard OpenMeteo provider is used. Injecting a
                FixtureProvider here enables the Demo-Mode (Issue #483)
                without any Live-API call.

        Returns:
            List of SegmentWeatherData objects
        """
        from providers.base import get_provider
        from services.segment_weather import SegmentWeatherService

        # OpenMeteo with automatic regional model selection (AROME, ICON-D2, ECMWF)
        # — unless caller injects an alternative provider (Issue #483: Demo-Mode).
        if provider is None:
            provider = get_provider("openmeteo")
        service = SegmentWeatherService(provider)

        weather_data = []
        for segment in segments:
            try:
                # Bug #288: Skip ensemble per-segment; will be added once via
                # _enrich_ensemble_for_trip() to keep API-Calls at 1/Report.
                data = service.fetch_segment_weather(segment, enrich_ensemble=False)
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
            # Bug #288: night fetch is part of the per-stage data; ensemble
            # is added once per trip via _enrich_ensemble_for_trip().
            night_data = service.fetch_segment_weather(night_segment, enrich_ensemble=False)
            return night_data.timeseries
        except Exception as e:
            logger.warning(f"Failed to fetch night weather: {e}")
            # Fallback: use last segment's timeseries (evening hours only)
            if last_segment.timeseries and last_segment.timeseries.data:
                return last_segment.timeseries
            return None

    def _enrich_ensemble_for_trip(
        self,
        trip: "Trip",
        weather_data: List[SegmentWeatherData],
    ) -> None:
        """Bug #288: Add ensemble-spread confidence once per trip.

        Performs a single Ensemble-API call for the last waypoint of the
        last stage, then propagates confidence_pct / spread_t2m_k /
        spread_precip_mm onto every DataPoint of every segment. Finally,
        SegmentWeatherSummary.confidence_pct_min is set retroactively
        (the dataclass is not frozen).

        Args:
            trip: Trip whose last stage / last waypoint anchors the call.
            weather_data: Segment-weather list to enrich in-place.
        """
        from providers.base import get_provider
        from providers.openmeteo import OpenMeteoProvider, compute_confidence_pct
        from app.config import Location

        if not weather_data or not trip.stages:
            return

        # 1. Last waypoint of last stage
        last_wp = trip.stages[-1].last_waypoint
        location = Location(
            latitude=last_wp.lat,
            longitude=last_wp.lon,
            name=last_wp.name or "Ziel",
            elevation_m=last_wp.elevation_m,
        )

        # 2. Derive time range from weather_data
        all_starts = [w.segment.start_time for w in weather_data if w.segment]
        all_ends = [w.segment.end_time for w in weather_data if w.segment]
        if not all_starts or not all_ends:
            return
        start = min(all_starts)
        end = max(all_ends)

        # 3. Ensemble-API call (best-effort: failures must not crash report)
        provider = get_provider("openmeteo")
        if not isinstance(provider, OpenMeteoProvider):
            return
        try:
            spreads = provider._fetch_ensemble_spread(location, start, end)
        except Exception as e:
            logger.warning("_enrich_ensemble_for_trip: ensemble fetch failed: %s", e)
            return

        if not spreads:
            return

        # 4. Timestamp-normalised lookup (mirrors openmeteo.py:770-787)
        now_utc = datetime.now(timezone.utc)
        spreads_naive: Dict[datetime, Tuple[Optional[float], Optional[float]]] = {}
        for k, v in spreads.items():
            k_naive = k.replace(tzinfo=None) if k.tzinfo is not None else k
            spreads_naive[k_naive] = v

        self._apply_ensemble_spreads(weather_data, spreads_naive, now_utc)

    def _apply_ensemble_spreads(
        self,
        weather_data: List[SegmentWeatherData],
        spreads_naive: Dict[datetime, Tuple[Optional[float], Optional[float]]],
        now_utc: datetime,
    ) -> None:
        """Propagate pre-computed ensemble spreads onto DataPoints and set confidence_pct_min.

        No API call — works exclusively on provided data. Extracted from
        _enrich_ensemble_for_trip() to allow direct testing without a live provider.
        """
        from providers.openmeteo import compute_confidence_pct

        # 5. Propagate confidence onto every DataPoint of every segment
        for weather_item in weather_data:
            seg = weather_item.segment
            seg_start = seg.start_time if seg is not None else None
            seg_end = seg.end_time if seg is not None else None

            # 5a. Per-DataPoint enrichment when timeseries exists
            if weather_item.timeseries is not None:
                for dp in weather_item.timeseries.data:
                    dp_ts_naive = dp.ts.replace(tzinfo=None) if dp.ts.tzinfo else dp.ts
                    spread = spreads_naive.get(dp_ts_naive)
                    if spread is None:
                        continue
                    s_t, s_p = spread
                    dp.spread_t2m_k = s_t
                    dp.spread_precip_mm = s_p
                    if s_t is not None and s_p is not None:
                        dp_ts_utc = dp.ts if dp.ts.tzinfo else dp.ts.replace(tzinfo=timezone.utc)
                        lead_h = max(0.0, (dp_ts_utc - now_utc).total_seconds() / 3600.0)
                        dp.confidence_pct = compute_confidence_pct(s_t, s_p, lead_h)

                # 6a. confidence_pct_min from DataPoints (SegmentWeatherSummary not frozen)
                valid_conf = [
                    dp.confidence_pct
                    for dp in weather_item.timeseries.data
                    if dp.confidence_pct is not None
                ]
                if valid_conf:
                    weather_item.aggregated.confidence_pct_min = min(valid_conf)
                    continue

            # 5b/6b. Fallback: aggregate confidence directly from spreads within
            # the segment time window (when timeseries is missing or empty)
            if seg_start is None or seg_end is None:
                continue
            seg_start_naive = (
                seg_start.replace(tzinfo=None) if seg_start.tzinfo else seg_start
            )
            seg_end_naive = (
                seg_end.replace(tzinfo=None) if seg_end.tzinfo else seg_end
            )
            spread_confs: List[float] = []
            for ts_naive, (s_t, s_p) in spreads_naive.items():
                if ts_naive < seg_start_naive or ts_naive > seg_end_naive:
                    continue
                if s_t is None or s_p is None:
                    continue
                ts_utc = ts_naive.replace(tzinfo=timezone.utc)
                lead_h = max(0.0, (ts_utc - now_utc).total_seconds() / 3600.0)
                spread_confs.append(compute_confidence_pct(s_t, s_p, lead_h))
            if spread_confs:
                weather_item.aggregated.confidence_pct_min = min(spread_confs)

    def _build_stage_trend(
        self,
        trip,
        target_date: date,
        tz=None,
    ) -> Optional[list[dict]]:
        """
        Build trend rows for each future stage (v4.0 column layout).

        SPEC: docs/specs/modules/multi_day_trend.md v4.0
        """
        from app.metric_catalog import build_default_display_config
        from providers.openmeteo import (
            OPENMETEO_MAX_FORECAST_DAYS,
            is_within_forecast_horizon,
        )
        from services.weather_metrics import aggregate_stage

        WEEKDAYS_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

        future_stages = trip.get_future_stages(target_date)
        if not future_stages:
            return None

        trend = []
        today = date.today()
        for stage in future_stages[:3]:
            if not is_within_forecast_horizon(stage.date, today):
                logger.debug(
                    "Stage %s (%s) beyond Open-Meteo forecast horizon (today+%d), skipping trend",
                    stage.id, stage.date, OPENMETEO_MAX_FORECAST_DAYS,
                )
                continue
            try:
                segments = self._convert_trip_to_segments(trip, stage.date)
                if not segments:
                    continue

                seg_weather = self._fetch_weather(segments)
                if not seg_weather:
                    continue

                agg = aggregate_stage(seg_weather)

                temp_lo = int(agg.temp_min_c) if agg.temp_min_c is not None else None
                temp_hi = int(agg.temp_max_c) if agg.temp_max_c is not None else None
                precip_mm = float(agg.precip_sum_mm or 0.0)
                wind_kmh = int(agg.wind_max_kmh or 0)
                wind_dir = _deg_to_compass(agg.wind_direction_avg_deg)
                thunder_level = agg.thunder_level_max
                thunder = thunder_level.name if thunder_level is not None else "NONE"
                note = _trend_note(thunder, precip_mm, wind_kmh)

                # Issue #640: Build HourlyValue samples from timeseries for @-time tokens.
                # Uses local hours (Bug #398/#401: tz required). No extra API call.
                from src.output.tokens.dto import HourlyValue
                from app.models import ThunderLevel as _TL
                from utils.timezone import local_hour as _lh
                _tz = tz if tz is not None else __import__("zoneinfo").ZoneInfo("UTC")
                _hourly_precip: list = []
                _hourly_wind: list = []
                _hourly_gust: list = []
                _hourly_thunder: list = []
                _THUNDER_NUM = {_TL.NONE: 0, _TL.MED: 1, _TL.HIGH: 2}
                for sw in seg_weather:
                    if sw.timeseries is None:
                        continue
                    for dp in sw.timeseries.data:
                        lh = _lh(dp.ts, _tz)
                        if dp.precip_1h_mm is not None:
                            _hourly_precip.append(HourlyValue(hour=lh, value=dp.precip_1h_mm))
                        if dp.wind10m_kmh is not None:
                            _hourly_wind.append(HourlyValue(hour=lh, value=dp.wind10m_kmh))
                        if dp.gust_kmh is not None:
                            _hourly_gust.append(HourlyValue(hour=lh, value=dp.gust_kmh))
                        if dp.thunder_level is not None:
                            _hourly_thunder.append(HourlyValue(
                                hour=lh, value=float(_THUNDER_NUM.get(dp.thunder_level, 0))
                            ))

                # Resolve per-metric sms_threshold from trip display config (AC-2)
                _sms_thr: dict = {}
                dc = getattr(trip, "display_config", None)
                if dc is not None:
                    for mc in dc.metrics:
                        if mc.sms_threshold is not None:
                            _sms_thr[mc.metric_id] = mc.sms_threshold

                # Issue #721: confidence_pct from stage-level aggregate (min over segments)
                _conf_pct = (
                    round(agg.confidence_pct_min)
                    if agg.confidence_pct_min is not None else None
                )

                trend.append(dict(
                    weekday=WEEKDAYS_DE[stage.date.weekday()],
                    name=stage.name,
                    temp_lo=temp_lo,
                    temp_hi=temp_hi,
                    precip_mm=precip_mm,
                    wind_dir=wind_dir,
                    wind_kmh=wind_kmh,
                    thunder=thunder,
                    note=note,
                    hourly_precip=tuple(_hourly_precip),
                    hourly_wind=tuple(_hourly_wind),
                    hourly_gust=tuple(_hourly_gust),
                    hourly_thunder=tuple(_hourly_thunder),
                    **{k: v for k, v in {
                        "sms_threshold_precip": _sms_thr.get("precipitation"),
                        "sms_threshold_wind": _sms_thr.get("wind"),
                        "sms_threshold_gust": _sms_thr.get("gust"),
                        "confidence_pct": _conf_pct,
                    }.items() if v is not None},
                ))
            except Exception as e:
                logger.warning(f"Failed to build trend for stage {stage.id}: {e}")
                continue

        return trend if trend else None

    def _build_thunder_forecast(
        self,
        last_segment: SegmentWeatherData,
        target_date: date,
        tz=None,
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
                    "text": f"Gewitter möglich ab {max_level.ts.astimezone(tz).strftime('%H:%M') if tz else max_level.ts.strftime('%H:%M')}",
                }
            else:
                forecast[key] = {
                    "date": fc_date.strftime("%d.%m.%Y"),
                    "level": ThunderLevel.HIGH,
                    "text": f"Starkes Gewitter erwartet ab {max_level.ts.astimezone(tz).strftime('%H:%M') if tz else max_level.ts.strftime('%H:%M')}",
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
        body = build_service_error_email_html(
            trip_name=trip.name,
            report_type=report_type,
            error_lines=error_lines,
        )
        try:
            EmailOutput(self._settings).send(subject=subject, body=body, html=True)
            logger.info(f"Service error email sent for {trip.name}")
        except Exception as e:
            logger.error(f"Failed to send service error email: {e}")
