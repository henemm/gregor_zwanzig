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
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.loader import _parse_trip, get_briefings_dir
from app.metric_catalog import format_metric_value
from app.models import UnifiedWeatherDisplayConfig
from app.trip import Trip
from services.trip_alert import TripAlertService
from services.validator_render_service import (
    render_alert_preview,
    render_compare_email_preview,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Internal helper: user-scoped trip loader that tolerates empty stages.
# ---------------------------------------------------------------------------

def _load_trip_raw(user_id: str, trip_id: str) -> Optional[dict]:
    """Read the raw briefing JSON for a user (no parsing, no migration).

    Issue #1250 Scheibe 7b (AC-37): der invertierte S7a-Zaun ist AUFGEHOBEN.
    `briefings/` haelt nach dem vergleich-Cutover BEIDE kinds; ein
    `kind=="vergleich"`-Briefing wird nicht mehr still auf None abgebildet,
    sondern als Roh-Dict zurueckgegeben, damit der External Validator es als
    ComparePreset lesen kann (`compare_preset_from_dict`). Die
    kind-spezifische Weiterverarbeitung passiert downstream: der Trip-Pfad
    (`_load_trip_for_validator`) lehnt vergleich explizit ab.
    """
    path = get_briefings_dir(user_id) / f"{trip_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


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

    # Issue #1250 Scheibe 7b (AC-37): ein vergleich-Briefing ist ein
    # ComparePreset, kein Trip -- nie in einen Trip fehl-parsen (der
    # kind-Guard wanderte aus _load_trip_raw hierher, damit der Raw-Pfad
    # vergleich weiterhin sichtbar macht).
    if data.get("kind") == "vergleich":
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

    return render_alert_preview(trip_obj, body)


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
    hourly_enabled: bool = True                # Issue #1107


@router.post("/api/_validator/compare-email-preview")
async def compare_email_preview(body: CompareEmailPreviewBody):
    """Rendert Compare-E-Mail HTML für den Validator.

    Spec: docs/specs/modules/issue_464_compare_email_preview_validator.md.
    Kein Wetterdaten-Fetch, kein SMTP. Pure Render-Funktion.
    """
    try:
        html = render_compare_email_preview(body)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"html": html}
