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
    render_sms_fidelity_preview,
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

    Issue #1677 AC-9: delegiert an ``UnifiedWeatherDisplayConfig.
    cascade_source_for_channel()`` -- dem models.py-Helfer, den auch das
    Aktivierungs-Gate der Trip-Kurzform (trip_report.py) nutzt. Kein zweiter,
    unabhaengig gepflegter Ableitungsweg mehr.
    """
    if dc is None:
        return "global"
    return dc.cascade_source_for_channel(channel, report_type)


# ---------------------------------------------------------------------------
# Endpoint #1 — Pure format_metric_value wrapper (AC-1, AC-2).
# ---------------------------------------------------------------------------

@router.get("/api/_validator/format-metric")
def format_metric(
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
def detector_thresholds(
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
    """Issue #1948 S5 (AC-15, Vorbedingung aus S4): `segment_id` additiv
    nachgezogen -- `OfficialAlertPayload` transportiert die Segment-Kennung
    ueber `segment_ids` schon heute, dieser Zweig fiel ohne sie auf den
    km-Rueckfall zurueck."""
    onset_minutes: int
    onset_time: str
    km_from: float
    km_to: float
    is_convective: bool
    intensity_label: str
    source_label: str
    cooldown_display: str | None = None
    segment_id: str | None = None
    # Issue #2046: Mengenangabe der Onset-Kurznachricht (mm der Stunde ab dem
    # Beginn), additiv und optional -- Muster `segment_id` o. Ohne sie rendert
    # der Vorschauweg die zahlenlose Alt-Form.
    onset_precip_mm: float | None = None
    # Issue #2054: Tagesbezug des Beginns und seine Darstellung in der
    # Kurzform, additiv und optional -- Muster `onset_precip_mm` o. Ohne die
    # Felder verwirft pydantic sie STILL und die Vorschau zeigt einen
    # Zeitpunkt von heute, wo der Versand einen von morgen meldet.
    onset_day_offset: int = 0
    onset_weekday: str | None = None
    # Issue #2051 S1: Ende des Ereignisses ("HH:MM") und sein eigener
    # Tagesbezug, additiv und optional -- Muster `onset_precip_mm` o. Ohne sie
    # rendert der Vorschauweg die Ausweichform ohne Ende.
    event_end_time: str | None = None
    event_end_day_offset: int = 0
    event_end_weekday: str | None = None  # Issue #2054
    # Issue #2051 S1 (Spec v1.1): der R4-Waechter braucht ein EIGENES Feld --
    # seit der Umkehr auf die Untergrenzen-Form loest ihn die erzeugende Seite
    # nicht mehr in einem fehlenden Ende auf, er waehlt die Textform. Ohne das
    # Feld zeigte die Vorschau im Waechterfall die falsche der beiden Formen
    # und damit nicht mehr das, was der Produktivpfad sendet.
    event_ongoing_beyond_horizon: bool = False


class OfficialAlertPayload(BaseModel):
    """Issue #1948 Scheibe S2 (Zweig b): strukturierte Testmeldung fuer eine
    amtliche Warnung — Feldspiegel von ``OfficialAlert``
    (services/official_alerts/models.py:15) plus die betroffenen Segmente."""
    source: str
    hazard: str
    level: int
    label: str
    valid_from: str | None = None
    valid_to: str | None = None
    url: str | None = None
    region_label: str | None = None
    dedup_id: str | None = None
    segment_ids: list[str] = Field(default_factory=list)


class NowcastFramePayload(BaseModel):
    timestamp: str
    precip_mm_h: float
    is_convective: bool = False


class NowcastFramesPayload(BaseModel):
    """Issue #1948 Scheibe S2 (Zweig c): Replay eines S1-Nowcast-Mitschnitts."""
    source: str
    frames: list[NowcastFramePayload]
    km_from: float = 0.0
    km_to: float = 0.0
    # #1948 S5 (AC-15): wie `OnsetPayload` -- ohne Segment-Kennung nennt der
    # Frame-Replay nur den km-Rueckfall statt des Segments.
    segment_id: str | None = None


class AlertPreviewBody(BaseModel):
    changes: list[ChangePayload] = Field(default_factory=list)
    segment_times: list[SegmentTimePayload] = Field(default_factory=list)
    onset: OnsetPayload | None = None
    official: list[OfficialAlertPayload] | None = None
    nowcast_frames: NowcastFramesPayload | None = None


@router.post("/api/trips/{trip_id}/alert-preview")
def alert_preview(
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

    # Issue #1948 Scheibe S2 (AC-1): Vier-Wege-Exklusivitaet statt binaerem
    # Alt-Gate (onset XOR changes+segment_times). segment_times ist bei
    # changes seit S2 optional (Zweig-a-Synthese aus dem Trip, s.u.).
    provided = [
        bool(body.onset), bool(body.changes), bool(body.official),
        bool(body.nowcast_frames),
    ]
    if sum(provided) != 1:
        raise HTTPException(
            status_code=422,
            detail=(
                "Body muss genau einen von 'onset', 'changes', 'official' "
                "oder 'nowcast_frames' enthalten"
            ),
        )

    if body.official:
        _validate_official_segment_ids(trip_obj, body.official)
    if body.changes:
        _validate_change_metrics(body.changes)
        _validate_change_segment_ids(trip_obj, body.changes)
        if not body.segment_times:
            body.segment_times = _synthesize_segment_times(trip_obj, body.changes)

    return render_alert_preview(trip_obj, body)


def _real_segment_ids_for_today(trip_obj: Trip) -> set[str]:
    """Echte Segment-IDs des Trips fuer HEUTE (dieselbe Quelle wie AC-3:
    ``convert_trip_to_segments``). Leer, wenn der Trip fuer heute keine
    echten Segmente hat (Stub-/Test-Trip) -- die Aufrufer behandeln das
    dann als No-Op (fix-1948-s2-preview-eingaben: sonst brechen die
    bestehenden S2-Tests, die durchgaengig ``stages: []``-Trips nutzen)."""
    from services.trip_day import trip_local_today
    from services.trip_segments import convert_trip_to_segments

    today = trip_local_today(trip_obj, datetime.now(timezone.utc))
    return {str(s.segment_id) for s in convert_trip_to_segments(trip_obj, today)}


def _reject_unknown_segment_id(real_ids: set[str], segment_id: str) -> None:
    if real_ids and segment_id not in real_ids:
        raise HTTPException(
            status_code=422,
            detail=f"Unbekannte segment_id '{segment_id}' im Trip",
        )


def _validate_official_segment_ids(
    trip_obj: Trip, payloads: "list[OfficialAlertPayload]",
) -> None:
    """fix-1948-s2-preview-eingaben (Bug B Teil 1): ``official[].segment_ids``
    gegen die echten Trip-Segmente pruefen -- unbekannte ID (bei einem Trip
    MIT echten Segmenten) -> 422 mit der ID. Leere Liste bleibt erlaubt."""
    real_ids = _real_segment_ids_for_today(trip_obj)
    for p in payloads:
        for sid in p.segment_ids:
            _reject_unknown_segment_id(real_ids, sid)


def _validate_change_metrics(changes: "list[ChangePayload]") -> None:
    """fix-1948-s2-preview-eingaben (Bug A): ``changes[].metric`` gegen den
    Metrik-Katalog pruefen (gleiche Quelle wie ``project.py:_resolve_metric_id``)
    -- unbekannte Metrik -> 422 mit dem Namen, statt spaeter als KeyError zu
    crashen."""
    from app.metric_catalog import _METRICS

    known = {f for m in _METRICS for f in m.summary_fields.values()}
    for c in changes:
        if c.metric not in known:
            raise HTTPException(
                status_code=422,
                detail=f"Unbekannte Metrik '{c.metric}' in changes",
            )


def _validate_change_segment_ids(
    trip_obj: Trip, changes: "list[ChangePayload]",
) -> None:
    """fix-1948-s2-preview-eingaben: dieselbe Pruefung wie bei ``official``,
    aber fuer ``changes[].segment_id`` -- schliesst die Luecke, dass bei
    EXPLIZIT mitgeliefertem ``segment_times`` (kein Aufruf von
    ``_synthesize_segment_times``, dessen AC-3-Pruefung sonst greift) eine
    unbekannte ``segment_id`` bislang ungeprueft blieb."""
    real_ids = _real_segment_ids_for_today(trip_obj)
    for c in changes:
        _reject_unknown_segment_id(real_ids, c.segment_id)


def _synthesize_segment_times(
    trip_obj: Trip, changes: "list[ChangePayload]",
) -> "list[SegmentTimePayload]":
    """Issue #1948 Scheibe S2 (AC-2/AC-3): Segment-Zeiten der in ``changes``
    genannten ``segment_id``s aus dem bereits geladenen Trip synthetisieren
    — dieselbe Produktions-Segmentierung wie der Versandpfad."""
    from services.trip_day import trip_local_today
    from services.trip_segments import convert_trip_to_segments

    today = trip_local_today(trip_obj, datetime.now(timezone.utc))
    real_segments = {
        str(s.segment_id): s for s in convert_trip_to_segments(trip_obj, today)
    }
    synthesized: list[SegmentTimePayload] = []
    for c in changes:
        seg = real_segments.get(c.segment_id)
        if seg is None:
            raise HTTPException(
                status_code=422,
                detail=f"Unbekannte segment_id '{c.segment_id}' im Trip",
            )
        synthesized.append(SegmentTimePayload(
            segment_id=c.segment_id,
            start=seg.start_time.strftime("%H:%M"),
            end=seg.end_time.strftime("%H:%M"),
        ))
    return synthesized


# ---------------------------------------------------------------------------
# Endpoint #4 — Metrics-for-channel cascade visibility (Issue #448).
# ---------------------------------------------------------------------------

@router.get("/api/_validator/metrics-for-channel")
def metrics_for_channel(
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
    # Issue #1406 Scheibe B (AC-8): Stundenverlauf-Auswahl (Renderer-Feldnamen
    # wie "t2m_c"). `None` = nie eingestellt -> Vorgabemenge des Renderers.
    hourly_metrics: list[str] | None = None


@router.post("/api/_validator/compare-email-preview")
def compare_email_preview(body: CompareEmailPreviewBody):
    """Rendert Compare-E-Mail HTML für den Validator.

    Spec: docs/specs/modules/issue_464_compare_email_preview_validator.md.
    Kein Wetterdaten-Fetch, kein SMTP. Pure Render-Funktion.
    """
    try:
        html = render_compare_email_preview(body)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"html": html}


# ---------------------------------------------------------------------------
# Endpoint #6 — Briefing-SMS-Fidelity-Vorschau (Issue #923, ADR-0011).
# ---------------------------------------------------------------------------

class SmsFidelityPreviewBody(BaseModel):
    metric_ids: list[str] = Field(default_factory=list)


@router.post("/api/_validator/sms-fidelity-preview")
def sms_fidelity_preview(body: SmsFidelityPreviewBody):
    """Rendert die SMS-Kurzform fuer die Metrik-Editor-Vorschau.

    Spec: docs/specs/modules/fix_923_sms_fidelity_backend.md.
    Zustandslos wie alert-preview/compare-email-preview (kein user_id,
    keine Trip-/Nutzerdaten): beispielwertbasiert, kein Wetterdaten-Fetch.
    """
    return render_sms_fidelity_preview(body.metric_ids)
