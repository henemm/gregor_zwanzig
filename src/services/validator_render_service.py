"""Validator render service.

Encapsulates alert-channel and compare-email rendering used by the validator
router so that api/routers/validator.py does not import output.renderers.*
directly.
"""
from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, time, timezone
from typing import Any

from app.models import (
    ChangeSeverity,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripSegment,
    WeatherChange,
)
from app.profile import ActivityProfile
from app.trip import Trip
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.alert.model import AlertMessage, OnsetEvent
from output.renderers.alert.project import to_alert_message
from output.renderers.alert.render import (
    render_email,
    render_sms,
    render_subject,
    render_telegram,
)
from output.renderers.email.compare_html import render_compare_html
from utils.timezone import local_fmt, tz_for_coords


def _alert_tz_for_trip(trip_obj: Trip):
    """Best-effort timezone for alert rendering from trip coordinates."""
    stages = getattr(trip_obj, "stages", None) or []
    for stage in stages:
        waypoints = getattr(stage, "waypoints", None) or []
        for wp in waypoints:
            lat = getattr(wp, "lat", None)
            lon = getattr(wp, "lon", None)
            if lat is not None and lon is not None:
                return tz_for_coords(float(lat), float(lon))
    return timezone.utc


def _stub_segment(seg_time: Any) -> SegmentWeatherData:
    """Minimal renderer stub. Pattern from tests/unit/test_issue_131_alert_klarheit.py."""
    today = datetime.now(timezone.utc).date()
    start_h, start_m = (int(p) for p in seg_time.start.split(":"))
    end_h, end_m = (int(p) for p in seg_time.end.split(":"))
    start_dt = datetime.combine(today, time(start_h, start_m), tzinfo=timezone.utc)
    end_dt = datetime.combine(today, time(end_h, end_m), tzinfo=timezone.utc)
    segment = TripSegment(
        segment_id=seg_time.segment_id,
        start_point=GPXPoint(lat=0.0, lon=0.0, elevation_m=0),
        end_point=GPXPoint(lat=0.0, lon=0.0, elevation_m=0),
        start_time=start_dt,
        end_time=end_dt,
        duration_hours=max(0.0, (end_dt - start_dt).total_seconds() / 3600.0),
        distance_km=0.0,
        ascent_m=0.0,
        descent_m=0.0,
    )
    return SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(
                provider=Provider.OPENMETEO, model="validator-stub",
                run=datetime.now(timezone.utc), grid_res_km=1.0, interp="stub",
            ),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def render_alert_preview(
    trip_obj: Trip,
    body: Any,
) -> dict:
    """Render alert preview across all channels.

    Returns a dict with subject, email_html, email_plain, telegram, sms.
    """
    alert_tz = _alert_tz_for_trip(trip_obj)
    stand_at = local_fmt(datetime.now(timezone.utc), alert_tz)
    has_onset = body.onset is not None

    if has_onset:
        onset_ev = OnsetEvent(
            onset_minutes=body.onset.onset_minutes,
            onset_time=body.onset.onset_time,
            km_from=body.onset.km_from,
            km_to=body.onset.km_to,
            is_convective=body.onset.is_convective,
            intensity_label=body.onset.intensity_label,
            source_label=body.onset.source_label,
        )
        msg = AlertMessage(
            trip_short=trip_obj.name,
            stand_at=stand_at,
            events=(onset_ev,),
            source=body.onset.source_label,
            cooldown_display=body.onset.cooldown_display,
        )
    else:
        changes = [
            WeatherChange(
                metric=c.metric,
                old_value=c.old_value,
                new_value=c.new_value,
                delta=c.delta,
                threshold=c.threshold,
                severity=ChangeSeverity(c.severity),
                direction=c.direction,
                segment_id=c.segment_id,
            )
            for c in body.changes
        ]
        segments = [_stub_segment(st) for st in body.segment_times]
        msg = to_alert_message(
            changes, segments, trip_obj.name,
            tz=alert_tz, stand_at=stand_at,
        )

    subject = render_subject(msg)
    email_html, email_plain = render_email(msg)
    telegram = render_telegram(msg)
    sms = render_sms(msg)
    return {
        "subject": subject,
        "email_html": email_html,
        "email_plain": email_plain,
        "telegram": telegram,
        "sms": sms,
    }


def render_compare_email_preview(body: Any) -> str:
    """Render compare-email HTML for the validator without fetching weather data."""
    profile_enum = ActivityProfile(body.profile)
    target_date = date_type.fromisoformat(body.target_date)

    stub_location = SavedLocation(
        id="preview-1",
        name="Vorschau-Ort",
        lat=47.0,
        lon=11.0,
        elevation_m=2000,
    )
    loc_result = LocationResult(
        location=stub_location,
        score=85,
        error=None,
    )
    result = ComparisonResult(
        locations=[loc_result],
        time_window=(body.time_window[0], body.time_window[1]),
        target_date=target_date,
    )
    return render_compare_html(
        result,
        profile=profile_enum,
        hourly_enabled=body.hourly_enabled,
    )
