"""Validator Observability Endpoints (Issue #221).

Spec: docs/specs/modules/issue_221_validator_observability_endpoints.md

Drei cookie-geschützte Read-/Render-Endpoints für den External Validator
(Issue #110), die interne Python-Funktionen rund um Alert-Mail-Format,
Detector-Auswahl und Metric-Formatierung von außen prüfbar machen.

Endpoints (tooling-API — nicht versionsstabil, nicht für Frontend):
- GET  /api/_validator/format-metric
- POST /api/trips/{trip_id}/alert-preview
- GET  /api/_validator/detector-thresholds
"""
from __future__ import annotations

import json
from datetime import date as date_type
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.app.loader import _parse_trip, get_trips_dir
from src.app.metric_catalog import format_metric_value
from src.app.models import (
    ChangeSeverity,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripSegment,
    UnifiedWeatherDisplayConfig,
    WeatherChange,
)
from src.app.profile import ActivityProfile
from src.app.trip import Trip
from src.app.user import ComparisonResult, LocationResult, SavedLocation
from src.output.renderers.alert.model import AlertMessage, OnsetEvent
from src.output.renderers.alert.project import to_alert_message
from src.output.renderers.alert.render import (
    render_email,
    render_sms,
    render_subject,
    render_telegram,
)
from src.output.renderers.email.compare_html import render_compare_html
from src.services.trip_alert import TripAlertService

router = APIRouter()


# ---------------------------------------------------------------------------
# Internal helper: user-scoped trip loader that tolerates empty stages.
# ---------------------------------------------------------------------------

def _load_trip_raw(user_id: str, trip_id: str) -> Optional[dict]:
    """Read the raw trip JSON for a user (no parsing, no migration)."""
    path = get_trips_dir(user_id) / f"{trip_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _load_trip_for_validator(user_id: str, trip_id: str) -> Optional[Trip]:
    """Load a trip JSON via the production loader.

    The validator endpoints only consume name / display_config / report_config /
    alert_rules, so trips without stages (synthetic test fixtures) must remain
    loadable. We inject a single placeholder stage *only when missing* before
    delegating to ``_parse_trip`` — production data with stages is unaffected.
    Returns ``None`` if the trip file does not exist for the given user.
    """
    data = _load_trip_raw(user_id, trip_id)
    if data is None:
        return None

    if not data.get("stages"):
        # Synthetic placeholder so Trip.__post_init__ doesn't reject the trip.
        data["stages"] = [{
            "id": "validator-stub",
            "name": "validator-stub",
            "date": datetime.now(timezone.utc).date().isoformat(),
            "waypoints": [{
                "id": "G1", "name": "stub",
                "lat": 0.0, "lon": 0.0, "elevation_m": 0,
            }],
        }]
    try:
        return _parse_trip(data)
    except Exception:
        return None


def _config_source_from_raw(raw: dict, trip_obj: Trip) -> str:
    """Determine config_source by inspecting the raw JSON.

    The hydrated Trip can't be used directly because the loader auto-migrates
    legacy ``report_config`` into ``alert_rules`` and auto-injects a default
    ``display_config`` — both would mask the user's true configuration intent.
    Priority mirrors ``TripAlertService._select_change_detector``:
    alert_rules > display_config > report_config > defaults.
    """
    if "alert_rules" in raw and any(
        bool(r.get("enabled", False)) for r in (raw.get("alert_rules") or [])
    ):
        return "from_alert_rules"
    if "display_config" in raw and trip_obj.display_config \
            and trip_obj.display_config.get_enabled_metrics():
        return "from_display_config"
    if "report_config" in raw and trip_obj.report_config:
        return "from_trip_config"
    return "defaults"


def _effective_detector_source(trip: Trip) -> str:
    """Mirror von TripAlertService._select_change_detector — welcher Factory-Pfad?

    Spiegelt die effektive Detector-Auswahl (post Loader-Migration), während
    ``_config_source_from_raw`` den User-Intent aus der rohen JSON zeigt. Beide
    können divergieren (Adversary-Finding AC-11): User legt nur ``report_config``
    mit ``alert_on_changes=False`` an → ``config_source="from_trip_config"``,
    aber Loader injiziert Default-Display-Config → ``effective="from_display_config"``.
    """
    active_rules = [r for r in (trip.alert_rules or []) if r.enabled]
    if active_rules:
        return "from_alert_rules"
    if trip.display_config and trip.display_config.get_enabled_metrics():
        return "from_display_config"
    if trip.report_config:
        return "from_trip_config"
    return "defaults"


def _determine_cascade_source(
    dc: "UnifiedWeatherDisplayConfig | None",
    channel: str,
    report_type: str,
) -> str:
    """Spiegel von UnifiedWeatherDisplayConfig.get_metrics_for_channel() in models.py.

    Ermittelt welche Kaskadenstufe aktiv ist: per_report → per_channel → global.
    Eine leere Liste auf Stufe 1/2 ist expliziter User-Wunsch — kein Fallback
    auf die nächste Stufe. Spec: docs/specs/modules/issue_448_validator_metrics_for_channel.md.
    """
    if dc is None:
        return "global"
    per_report = (dc.per_report_layouts or {}).get(report_type, {})
    if channel in per_report:
        return "per_report"
    per_channel = dc.per_channel_layouts or {}
    if channel in per_channel:
        return "per_channel"
    return "global"


# ---------------------------------------------------------------------------
# Endpoint #1 — Pure format_metric_value wrapper (AC-1, AC-2).
# ---------------------------------------------------------------------------

@router.get("/api/_validator/format-metric")
async def format_metric(
    unit: str = Query(..., description="Unit code: m, km, hPa, %, km/h, °C, mm"),
    value: float = Query(...),
    signed: bool = Query(False),
):
    """Wrapper um app.metric_catalog.format_metric_value (Issue #131 AC-4..AC-6)."""
    return {"formatted": format_metric_value(unit, value, signed=signed)}


# ---------------------------------------------------------------------------
# Endpoint #3 — Detector thresholds + config-source (AC-7, AC-8, AC-9).
# ---------------------------------------------------------------------------

@router.get("/api/_validator/detector-thresholds")
async def detector_thresholds(
    trip: str = Query(..., description="Trip-ID"),
    user_id: str = Query(...),
):
    raw = _load_trip_raw(user_id, trip)
    trip_obj = _load_trip_for_validator(user_id, trip)
    if raw is None or trip_obj is None:
        raise HTTPException(
            status_code=404,
            detail=f"Trip {trip} nicht gefunden für User {user_id}",
        )

    config_source = _config_source_from_raw(raw, trip_obj)
    effective_source = _effective_detector_source(trip_obj)
    # Detector reflects the resolved priority (already encoded in the hydrated Trip).
    detector = TripAlertService(user_id=user_id)._select_change_detector(trip_obj)

    return {
        "config_source": config_source,
        "effective_detector": effective_source,
        "thresholds": {k: float(v) for k, v in detector._thresholds.items()},
    }


# ---------------------------------------------------------------------------
# Endpoint #2 — Alert mail render preview (AC-4, AC-5, AC-6).
# ---------------------------------------------------------------------------

class ChangePayload(BaseModel):
    metric: str
    old_value: float
    new_value: float
    delta: float
    threshold: float
    severity: str  # "minor" | "moderate" | "major"
    direction: str  # "increase" | "decrease" | "above" | "below"
    segment_id: str


class SegmentTimePayload(BaseModel):
    segment_id: str
    start: str  # "HH:MM"
    end: str    # "HH:MM"


class OnsetPayload(BaseModel):
    onset_minutes: int
    onset_time: str
    km_from: float
    km_to: float
    is_convective: bool
    intensity_label: str
    source_label: str
    cooldown_display: str | None = None


class AlertPreviewBody(BaseModel):
    changes: list[ChangePayload] = Field(default_factory=list)
    segment_times: list[SegmentTimePayload] = Field(default_factory=list)
    onset: OnsetPayload | None = None


def _stub_segment(seg_time: SegmentTimePayload) -> SegmentWeatherData:
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


@router.post("/api/trips/{trip_id}/alert-preview")
async def alert_preview(
    trip_id: str,
    body: AlertPreviewBody,
    user_id: str = Query(...),
):
    trip_obj = _load_trip_for_validator(user_id, trip_id)
    if trip_obj is None:
        raise HTTPException(
            status_code=404,
            detail=f"Trip {trip_id} nicht gefunden für User {user_id}",
        )

    has_onset = body.onset is not None
    has_deviation = bool(body.changes and body.segment_times)
    if has_onset == has_deviation:
        raise HTTPException(
            status_code=422,
            detail="Body muss genau einen von 'onset' ODER 'changes'+'segment_times' enthalten",
        )

    stand_at = datetime.now(timezone.utc).strftime("%H:%M")
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
            trip_short=trip_obj.name[:16],
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
            tz=timezone.utc, stand_at=stand_at,
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


# ---------------------------------------------------------------------------
# Endpoint #4 — Metrics-for-channel cascade visibility (Issue #448).
# ---------------------------------------------------------------------------

@router.get("/api/_validator/metrics-for-channel")
async def metrics_for_channel(
    trip: str = Query(..., description="Trip-ID"),
    channel: str = Query(..., description="email|telegram|sms"),
    report: str = Query(..., description="morning|evening"),
    user_id: str = Query(..., description="Vom Go-Proxy injiziert (Anti-Spoofing)"),
):
    """Macht die dreistufige get_metrics_for_channel-Kaskade von außen prüfbar.

    Spec: docs/specs/modules/issue_448_validator_metrics_for_channel.md.
    Response: {"source": "per_report|per_channel|global", "metric_ids": [...]}.
    """
    trip_obj = _load_trip_for_validator(user_id, trip)
    if trip_obj is None:
        raise HTTPException(
            status_code=404,
            detail=f"Trip {trip} nicht gefunden für User {user_id}",
        )

    dc = trip_obj.display_config  # kann None sein (Loader injiziert i.d.R. Default)
    source = _determine_cascade_source(dc, channel, report)
    metrics = dc.get_metrics_for_channel(channel, report) if dc else []
    return {"source": source, "metric_ids": [mc.metric_id for mc in metrics]}


# ---------------------------------------------------------------------------
# Endpoint #5 — Compare-E-Mail Preview für Validator (Issue #464).
# ---------------------------------------------------------------------------

class WinnerTag(BaseModel):
    tone: str   # "good" | "warn" | "bad" | "neutral" | "info"
    label: str


class CompareEmailPreviewBody(BaseModel):
    profile: str                              # ActivityProfile-Wert, z. B. "wintersport"
    time_window: list[int] = Field(..., min_length=2, max_length=2)
    target_date: str                          # ISO-8601, z. B. "2026-05-31"
    winner_tags: list[WinnerTag] = []


@router.post("/api/_validator/compare-email-preview")
async def compare_email_preview(body: CompareEmailPreviewBody):
    """Rendert Compare-E-Mail HTML für den Validator.

    Spec: docs/specs/modules/issue_464_compare_email_preview_validator.md.
    Kein Wetterdaten-Fetch, kein SMTP. Pure Render-Funktion.
    """
    try:
        profile_enum = ActivityProfile(body.profile)
    except ValueError:
        raise HTTPException(
            status_code=422, detail=f"Unbekanntes Profil: {body.profile}"
        )

    try:
        target_date = date_type.fromisoformat(body.target_date)
    except ValueError:
        raise HTTPException(
            status_code=422, detail=f"Ungültiges Datum: {body.target_date}"
        )

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
        error=None,   # KRITISCH: None → result.winner ist nicht None
    )
    result = ComparisonResult(
        locations=[loc_result],
        time_window=(body.time_window[0], body.time_window[1]),
        target_date=target_date,
    )
    winner_tags_raw = [{"tone": t.tone, "label": t.label} for t in body.winner_tags]
    html = render_compare_html(result, profile=profile_enum, winner_tags=winner_tags_raw)
    return {"html": html}
