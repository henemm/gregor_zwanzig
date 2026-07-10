"""
Service: compute_stage_weather -- Etappen-Wetter + Risiko-Zusammenfassung.

Slice R1 von Issue #1212 (ADR-0015). Spiegelt den Go-Handler
`StagesWeatherHandler` (internal/handler/stage_weather.go) fachlich, nutzt
aber die Python-RiskEngine als Single Source of Truth der Risikostufe --
damit Cockpit und Briefing fuer identische Wetterdaten dieselbe Farbe zeigen.

Spec: docs/specs/modules/stage_weather_python_endpoint.md
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date as date_type, timezone
from typing import TYPE_CHECKING, Optional

from app.models import RiskLevel, SegmentWeatherData
from services.risk_engine import RiskEngine
from services.segment_weather import SegmentWeatherService
from services.trip_segments import convert_trip_to_segments
from services.weather_metrics import aggregate_stage
from services.wind_exposition import WindExpositionService

if TYPE_CHECKING:
    from app.trip import Trip
    from providers.base import WeatherProvider

logger = logging.getLogger(__name__)

_LEVEL_ORDER = {RiskLevel.LOW: 0, RiskLevel.MODERATE: 1, RiskLevel.HIGH: 2}
_RISK_TO_COLOR = {RiskLevel.HIGH: "red", RiskLevel.MODERATE: "yellow"}
_DEFAULT_MIN_ELEVATION_M = 1500.0


def _segments_for_stage(trip: "Trip", stage) -> list:
    """Segmente einer einzelnen Stage, isoliert von Datums-Kollisionen.

    `convert_trip_to_segments` sucht intern die Stage per
    `trip.get_stage_for_date` -- bei mehreren Stages mit identischem Datum
    (Randfall) waere sonst die FALSCHE (erste) Stage getroffen. Ein
    Scoped-Trip mit nur dieser einen Stage macht die Zuordnung eindeutig.
    """
    if not stage.date:
        return []
    from app.trip import Trip as _Trip

    scoped_trip = _Trip(id=trip.id, name=trip.name, stages=[stage], activity=trip.activity)
    return convert_trip_to_segments(scoped_trip, stage.date)


def _fetch_one(service: SegmentWeatherService, segment) -> Optional[SegmentWeatherData]:
    """Fetch Wetter fuer ein Segment; Fehler killen nur dieses Segment."""
    try:
        return service.fetch_segment_weather(segment, enrich_ensemble=False)
    except Exception:  # noqa: BLE001 -- pro Segment fangen, andere nicht killen
        return None


def _to_utc_date(ts) -> date_type:
    if ts.tzinfo is not None:
        return ts.astimezone(timezone.utc).date()
    return ts.date()


def _derive_is_day(weather_list: list[SegmentWeatherData], stage_date: date_type) -> Optional[int]:
    """Analog Go `computeIsDay` (internal/handler/stage_weather.go:122)."""
    any_flag = False
    saw_day = False
    for sw in weather_list:
        if sw.timeseries is None:
            continue
        for pt in sw.timeseries.data:
            if _to_utc_date(pt.ts) != stage_date or pt.is_day is None:
                continue
            any_flag = True
            if pt.is_day == 1:
                saw_day = True
    if not any_flag:
        return None
    return 1 if saw_day else 0


def _compute_one_stage(trip: "Trip", stage, segments: list, weather_list: list) -> Optional[dict]:
    if not stage.date or not stage.waypoints or not segments:
        return None

    ok = [w for w in weather_list if w is not None and not w.has_error]
    if not ok:
        return None

    min_elev = _DEFAULT_MIN_ELEVATION_M
    if trip.report_config and trip.report_config.wind_exposition_min_elevation_m is not None:
        min_elev = trip.report_config.wind_exposition_min_elevation_m
    exposed = WindExpositionService().detect_exposed_from_segments(segments, min_elevation_m=min_elev)

    engine = RiskEngine()
    max_level = RiskLevel.LOW
    for sw in ok:
        level = engine.get_max_risk_level(engine.assess_segment(sw, exposed))
        if _LEVEL_ORDER[level] > _LEVEL_ORDER[max_level]:
            max_level = level

    try:
        summary = aggregate_stage(ok)
    except ValueError:
        return None

    weather_summary = {
        "temp_min_c": summary.temp_min_c,
        "temp_max_c": summary.temp_max_c,
        "wind_max_kmh": summary.wind_max_kmh,
        "precip_mm": summary.precip_sum_mm,
        "wmo_code": summary.dominant_wmo_code,
        "is_day": _derive_is_day(ok, stage.date),
    }
    return {"weather_summary": weather_summary, "risk": _RISK_TO_COLOR.get(max_level, "green")}


def compute_stage_weather(trip: "Trip", provider: "WeatherProvider") -> dict[str, Optional[dict]]:
    """Pro Stage in trip.stages: Wetter-Summary + Risiko (green/yellow/red).

    Leere Stage-ID -> Stage komplett uebersprungen. Fail-soft -> None bei
    fehlendem Datum, 0 Waypoints, keinen Segmenten oder falls alle Segment-
    Fetches scheitern. Segmente werden PARALLEL (ThreadPoolExecutor) ueber
    alle Stages hinweg gefetcht (Regel 10/Confidence bewusst nicht gefetcht --
    siehe Spec Known Limitations).
    """
    stages = [s for s in trip.stages if s.id != ""]

    # F001 (Adversary, Issue #1212): Segmentbildung kann pro Stage werfen
    # (z.B. Waypoint mit lat/lon=None -> TypeError in haversine_km). Ein
    # Fehler in EINER Stage darf die anderen Stages nicht mitreissen --
    # daher pro Stage isoliert fangen, betroffene Stage sofort auf None.
    segments_by_stage: dict[str, list] = {}
    broken_stages: set[str] = set()
    for stage in stages:
        try:
            segments_by_stage[stage.id] = _segments_for_stage(trip, stage)
        except Exception:  # noqa: BLE001 -- pro Stage fangen, andere nicht killen
            logger.warning(
                "compute_stage_weather: Segmentbildung fuer Stage %r fehlgeschlagen", stage.id,
                exc_info=True,
            )
            segments_by_stage[stage.id] = []
            broken_stages.add(stage.id)

    # Eigene Cache-Instanz je Stage: der Cache-Key basiert nur auf
    # segment_id+Zeitfenster (nicht Koordinaten) -- bei Stages mit
    # identischem Datum/identischen Ankunftszeiten wuerde ein geteilter
    # Cache sonst falsche Segment-Daten zwischen Stages verwechseln.
    services_by_stage = {stage.id: SegmentWeatherService(provider) for stage in stages}

    flat = [(stage.id, seg) for stage in stages for seg in segments_by_stage[stage.id]]
    fetched: list[Optional[SegmentWeatherData]] = [None] * len(flat)
    if flat:
        with ThreadPoolExecutor(max_workers=min(len(flat), 8)) as executor:
            future_to_idx = {
                executor.submit(_fetch_one, services_by_stage[stage_id], seg): idx
                for idx, (stage_id, seg) in enumerate(flat)
            }
            for future, idx in future_to_idx.items():
                fetched[idx] = future.result()

    weather_by_stage: dict[str, list] = {stage.id: [] for stage in stages}
    for (stage_id, _), sw in zip(flat, fetched):
        weather_by_stage[stage_id].append(sw)

    results: dict[str, Optional[dict]] = {}
    for stage in stages:
        if stage.id in broken_stages:
            results[stage.id] = None
            continue
        try:
            results[stage.id] = _compute_one_stage(
                trip, stage, segments_by_stage[stage.id], weather_by_stage[stage.id]
            )
        except Exception:  # noqa: BLE001 -- pro Stage fangen, andere nicht killen
            logger.warning(
                "compute_stage_weather: Pro-Stage-Pipeline fuer Stage %r fehlgeschlagen", stage.id,
                exc_info=True,
            )
            results[stage.id] = None
    return results
