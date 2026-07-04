"""
GPX processing pipeline (UI-frei).

Pure functions for GPX file ingestion, segmentation, and conversion to
Trip / Stage data structures. Extracted from src/web/pages/gpx_upload.py
and src/web/pages/trips.py in Epic #129 Phase A.2.

Function order matches the spec:
  1. process_gpx_upload
  2. compute_full_segmentation
  3. segments_to_trip
  4. compute_default_start_date
  5. gpx_to_stage_data           (API-Contract stable!)
  6. process_bulk_gpx_uploads

API-Contract: gpx_to_stage_data is consumed by api/routers/gpx.py
(Production endpoint POST /api/gpx/parse). Signature
(content, filename, stage_date, start_hour, upload_dir) and return
shape (dict with keys name, date, waypoints) MUST stay stable.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from app.models import EtappenConfig, GPXTrack, TripSegment
from app.trip import ActivityProfile, AggregationConfig, Stage, TimeWindow, Trip, Waypoint
from core.elevation_analysis import detect_waypoints
from core.gpx_parser import parse_gpx
from core.hybrid_segmentation import optimize_segments
from core.natural_sort import natural_sort_key
from core.segment_builder import build_segments


# Default upload directories (preserved from original modules)
_DEFAULT_UPLOAD_DIR = Path("data/users/default/gpx")
_GPX_UPLOAD_DIR = Path("data/users/default/gpx")


def process_gpx_upload(
    content: bytes,
    filename: str,
    upload_dir: Path = _DEFAULT_UPLOAD_DIR,
) -> GPXTrack:
    """Validate, save, and parse an uploaded GPX file.

    Args:
        content: Raw file content bytes.
        filename: Original filename (must end with .gpx).
        upload_dir: Directory to save the file to.

    Returns:
        Parsed GPXTrack object.

    Raises:
        ValueError: If filename does not end with .gpx.
        GPXParseError: If GPX content is invalid.
    """
    if not filename.lower().endswith(".gpx"):
        raise ValueError(f"Nur .gpx Dateien erlaubt, nicht '{filename}'")

    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_path = upload_dir / filename

    saved_path.write_bytes(content)

    try:
        return parse_gpx(saved_path)
    except Exception:
        # Clean up saved file on parse error
        if saved_path.exists():
            saved_path.unlink()
        raise


def compute_full_segmentation(
    track: GPXTrack,
    config: EtappenConfig,
    start_time: datetime,
) -> List[TripSegment]:
    """Run complete segmentation pipeline.

    Combines build_segments (1.4) + detect_waypoints (1.3) +
    optimize_segments (1.5) into a single call.

    Args:
        track: Parsed GPX track.
        config: Hiking speed and duration configuration.
        start_time: Start time of the hike (UTC).

    Returns:
        List of optimized TripSegment objects.
    """
    segments = build_segments(track, config, start_time)
    waypoints = detect_waypoints(track)
    return optimize_segments(segments, waypoints, track, config)


def segments_to_trip(
    segments: List[TripSegment],
    track: GPXTrack,
    trip_date: date,
    trip_name: Optional[str] = None,
) -> Trip:
    """Convert computed segments to a Trip object for weather/reports.

    Creates N+1 Waypoints for N segments (one at each boundary).
    Each waypoint gets a TimeWindow so the trip_report_scheduler
    can create weather segments between consecutive waypoints.

    Args:
        segments: Computed TripSegment list.
        track: Original GPX track (for name).
        trip_date: Date of the hike.
        trip_name: Optional override for trip name.

    Returns:
        Trip object ready for save_trip().
    """
    name = trip_name or track.name
    trip_id = name.lower().replace(" ", "-")
    trip_id = "".join(c for c in trip_id if c.isalnum() or c == "-")

    waypoints: List[Waypoint] = []

    for i, seg in enumerate(segments):
        # Waypoint at segment start
        wp_name = f"Seg {seg.segment_id} Start"
        if i == 0:
            wp_name = "Start"
        elif seg.adjusted_to_waypoint and seg.waypoint:
            wp_name = seg.waypoint.name or seg.waypoint.type.value

        tw = TimeWindow(
            start=seg.start_time.time(),
            end=seg.start_time.time(),
        )
        waypoints.append(Waypoint(
            id=f"G{i + 1}",
            name=wp_name,
            lat=seg.start_point.lat,
            lon=seg.start_point.lon,
            elevation_m=int(seg.start_point.elevation_m),
            time_window=tw,  # Issue #1004: GPX-Import-Artefakt, nie autoritativ
        ))

    # Last waypoint: end of last segment
    last = segments[-1]
    tw_end = TimeWindow(
        start=last.end_time.time(),
        end=last.end_time.time(),
    )
    waypoints.append(Waypoint(
        id=f"G{len(segments) + 1}",
        name="Ziel",
        lat=last.end_point.lat,
        lon=last.end_point.lon,
        elevation_m=int(last.end_point.elevation_m),
        time_window=tw_end,  # Issue #1004: GPX-Import-Artefakt, nie autoritativ
    ))

    stage = Stage(
        id="T1",
        name=name,
        date=trip_date,
        waypoints=waypoints,
    )

    return Trip(
        id=trip_id,
        name=name,
        stages=[stage],
        aggregation=AggregationConfig.for_profile(ActivityProfile.SUMMER_TREKKING),
    )


def compute_default_start_date(stages_data: list[dict]) -> date:
    """Default start date for a Multi-GPX-Upload commit row.

    Returns last_stage_date + 1 day if stages exist, otherwise date.today().
    Used by the Multi-Upload-UI to pre-fill the date picker.

    Spec: docs/specs/modules/gpx_multi_import.md
    """
    if not stages_data:
        return date.today()
    try:
        last = date.fromisoformat(stages_data[-1]["date"])
    except (KeyError, TypeError, ValueError):
        return date.today()
    return last + timedelta(days=1)


def gpx_to_stage_data(
    content: bytes,
    filename: str,
    stage_date: Optional[date] = None,
    start_hour: int = 8,
    upload_dir: Path = _GPX_UPLOAD_DIR,
) -> dict:
    """Parse GPX file and return a single stage dict for the trip dialog.

    1 GPX file = 1 Stage with N Waypoints.

    API-CONTRACT (do not break): consumed by api/routers/gpx.py for
    POST /api/gpx/parse. Signature and return shape MUST stay stable.

    Args:
        content: Raw GPX file bytes.
        filename: Original filename (must end with .gpx).
        stage_date: Date for the stage (defaults to today).
        start_hour: Start hour of the hike (0-23).
        upload_dir: Directory to save the GPX file.

    Returns:
        Dict with keys: name, date, waypoints[]
    """
    track = process_gpx_upload(content, filename, upload_dir=upload_dir)
    d = stage_date or date.today()

    config = EtappenConfig()
    start_time = datetime(d.year, d.month, d.day, start_hour, 0, 0,
                          tzinfo=timezone.utc)
    segments = compute_full_segmentation(track, config, start_time)
    trip = segments_to_trip(segments, track, d)

    stage = trip.stages[0]  # 1 GPX = 1 Stage
    waypoint_dicts = [
        {
            "id": wp.id,
            "name": wp.name,
            "lat": wp.lat,
            "lon": wp.lon,
            "elevation_m": wp.elevation_m,
            "time_window": str(wp.time_window) if wp.time_window else None,
        }
        for wp in stage.waypoints
    ]

    # Issue #303 — algorithmische Wegpunkt-Anreicherung. Zweiter, unabhängiger
    # detect_waypoints-Aufruf NACH der Segmentierung; greift NICHT in die
    # Segmentierungspipeline ein. Additiv — Fehler dürfen den Parse nicht kippen.
    try:
        from services.route_analyzer import enrich_waypoints_from_detected
        detected = detect_waypoints(track)
        waypoint_dicts = enrich_waypoints_from_detected(
            waypoint_dicts, detected, track
        )
    except Exception:
        pass

    return {
        "name": stage.name,
        "date": stage.date.isoformat(),
        "waypoints": waypoint_dicts,
    }


def process_bulk_gpx_uploads(
    files: list[tuple[str, bytes]],
    start_date: date,
    upload_dir: Path = _GPX_UPLOAD_DIR,
) -> list[dict]:
    """Process multiple uploaded GPX files in natural-sort order.

    Behavior (per spec docs/specs/modules/gpx_multi_import.md):
        1. Filenames are sorted via natural_sort_key (numeric-aware).
        2. Each file is parsed individually via gpx_to_stage_data().
        3. Dates are propagated sequentially: first valid stage gets
           start_date, second gets start_date+1, etc.
        4. Corrupt files are SKIPPED — they do not consume a date slot.
           Valid files following a corrupt one still get gapless dates.

    Args:
        files: List of (filename, content_bytes) tuples as collected
            from the multi-upload buffer (browser FileList order).
        start_date: First valid stage's date.
        upload_dir: Directory to save the GPX file copies.

    Returns:
        List of stage dicts (same shape as gpx_to_stage_data output),
        in natural-sort order, with sequential gapless dates.

    Note: Pure function — no ui.notify, no UI side effects. The caller
    handles user-facing messages based on the return value.
    """
    sorted_files = sorted(files, key=lambda t: natural_sort_key(t[0]))

    stages: list[dict] = []
    for filename, content in sorted_files:
        stage_date = start_date + timedelta(days=len(stages))
        try:
            stage_dict = gpx_to_stage_data(
                content, filename, stage_date, upload_dir=upload_dir,
            )
            stages.append(stage_dict)
        except Exception:
            # Corrupt / unsupported file — skip, do not consume a date slot.
            continue
    return stages
