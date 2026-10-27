"""GPS-Fix aus eingehender Premium-SMS -- Plausibilitaet, Snapping, Persistenz
(Issue #2327, ADR-0102).

Ein Fix wird nur uebernommen, wenn er hoechstens ``FIX_RADIUS_M`` neben der
STRECKE (nicht dem naechsten Trackpunkt) der Heute-Etappe genau EINES Trips
des Nutzers liegt. Gespeichert wird der Lotfusspunkt auf der Strecke, je
Nutzer in ``data/users/<user_id>/position_fix.json`` -- nicht im Trip-JSON
(Go roundtrippt es und kennt das Feld nicht). Schreiben per
Read-Modify-Write mit Merge (ADR-0101); ein aelterer Journal-Eintrag ersetzt
nie einen juengeren (Spec-Entscheidung 3).

Gelesen wird der Fix ausschliesslich ueber :func:`load_position_fix` aus der
zentralen Positionsquelle ``trip_segments`` -- gueltig nur fuer denselben Trip
und dasselbe Etappen-Datum (Entscheidung 1).

SPEC: docs/specs/modules/feat_2327_gps_etappenfortschritt.md
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

from app.loader import get_data_dir, load_all_trips
from services.file_lock import share_state_file
from utils.geo import point_to_segment_m
from utils.timezone import local_dt, tz_for_coords

logger = logging.getLogger(__name__)

FIX_RADIUS_M = 100.0  # Grenze inklusive (Spec-Entscheidung 5)
_FIX_FILE = "position_fix.json"


def _fix_path(user_id: str) -> Path:
    return get_data_dir(user_id) / _FIX_FILE


def _heute_etappe(trip, observed_at: datetime):
    """Etappe, deren Datum der Ortstag von ``observed_at`` ist."""
    for stage in getattr(trip, "stages", None) or []:
        wps = stage.waypoints or []
        if len(wps) < 2:
            continue
        ortstag = local_dt(observed_at, tz_for_coords(wps[0].lat, wps[0].lon)).date()
        if stage.date == ortstag:
            return stage
    return None


def _etappen_track(stage, gpx_dir: Path, cache: Dict[Path, list]) -> Optional[list]:
    """Trackpunkte der Etappe (erster bis letzter Wegpunkt) aus dem GPX, das
    ALLE Wegpunkte der Etappe enthaelt (dieselbe Zuordnung wie #2036)."""
    from core.gpx_parser import parse_gpx
    from services.track_resolution import DEFAULT_TOLERANCE_M, _match_track

    if not gpx_dir.is_dir():
        return None
    for path in sorted(gpx_dir.glob("*.gpx")):
        if path not in cache:
            try:
                cache[path] = parse_gpx(path).points or []
            except Exception as e:
                logger.warning("GPS-Fix: %s nicht lesbar (%s)", path.name, e)
                cache[path] = []
        hit = _match_track(stage.waypoints, cache[path], DEFAULT_TOLERANCE_M)
        if hit is None:
            continue
        lo, hi = min(hit.values()), max(hit.values())
        teil = [p for p in cache[path] if lo - 1e-9 <= p.distance_from_start_km <= hi + 1e-9]
        if len(teil) >= 2:
            return teil
    return None


def _snap(punkte: list, lat: float, lon: float) -> Optional[dict]:
    """Naechster Lotfusspunkt auf dem Polygonzug; km auf den Etappenstart normiert."""
    best = None
    for a, b in zip(punkte, punkte[1:]):
        d_m, frac = point_to_segment_m(lat, lon, a.lat, a.lon, b.lat, b.lon)
        if best is None or d_m < best[0]:
            best = (d_m, frac, a, b)
    if best is None:
        return None
    d_m, frac, a, b = best
    km = a.distance_from_start_km + frac * (b.distance_from_start_km - a.distance_from_start_km)
    return {
        "distance_m": d_m,
        "lat": a.lat + frac * (b.lat - a.lat),
        "lon": a.lon + frac * (b.lon - a.lon),
        "progress_km": km - punkte[0].distance_from_start_km,
    }


def _kandidaten(user_id: str, lat: float, lon: float, observed_at: datetime) -> List[dict]:
    gpx_dir = get_data_dir(user_id) / "gpx"
    cache: Dict[Path, list] = {}
    treffer: List[dict] = []
    for trip in load_all_trips(user_id):
        stage = _heute_etappe(trip, observed_at)
        punkte = _etappen_track(stage, gpx_dir, cache) if stage is not None else None
        snap = _snap(punkte, lat, lon) if punkte else None
        if snap is None:
            continue
        if snap["distance_m"] > FIX_RADIUS_M:
            logger.info(
                "GPS-Fix verworfen fuer Trip %s: %.1f m neben der Heute-Etappe "
                "(Grenze %.0f m)", trip.id, snap["distance_m"], FIX_RADIUS_M,
            )
            continue
        snap.update(trip_id=trip.id, stage_date=stage.date.isoformat())
        treffer.append(snap)
    return treffer


def record_position_fix(
    user_id: str, lat: float, lon: float, observed_at: datetime,
) -> Optional[dict]:
    """Fix pruefen und bei Plausibilitaet speichern. Rueckgabe: der
    gespeicherte Eintrag oder ``None`` (verworfen / nicht juenger)."""
    if not user_id:
        logger.warning("GPS-Fix ohne Nutzerzuordnung verworfen (nie 'default', AC-9)")
        return None
    treffer = _kandidaten(user_id, lat, lon, observed_at)
    if not treffer:
        logger.info("GPS-Fix verworfen: keine Heute-Etappe innerhalb %.0f m", FIX_RADIUS_M)
        return None
    if len(treffer) > 1:
        logger.warning(
            "GPS-Fix verworfen: mehrdeutig, liegt auf %d Trips (%s)",
            len(treffer), ", ".join(t["trip_id"] for t in treffer),
        )
        return None
    eintrag = dict(treffer[0], raw_lat=lat, raw_lon=lon, observed_at=observed_at.isoformat())
    return _speichere(user_id, eintrag, observed_at)


def _speichere(user_id: str, eintrag: dict, observed_at: datetime) -> Optional[dict]:
    """Read-Modify-Write mit Merge (ADR-0101), atomar ersetzt."""
    pfad = _fix_path(user_id)
    bestand = _lese(pfad)
    alt = bestand.get("fix") or {}
    try:
        if alt and datetime.fromisoformat(alt["observed_at"]) >= observed_at:
            logger.info("GPS-Fix nicht uebernommen: gespeicherter Fix ist juenger")
            return None
    except (KeyError, TypeError, ValueError):
        pass  # unlesbarer Altbestand -> neuer Fix gewinnt
    bestand["fix"] = {**alt, **eintrag}
    pfad.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=pfad.parent, prefix=".position_fix_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            share_state_file(f.fileno())
            json.dump(bestand, f, ensure_ascii=False, indent=2)
        os.replace(tmp, pfad)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return bestand["fix"]


def _lese(pfad: Path) -> dict:
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return daten if isinstance(daten, dict) else {}


def load_position_fix(user_id: str, trip_id: str, stage_date: date) -> Optional[dict]:
    """Gueltiger Fix fuer genau diesen Trip und dieses Etappen-Datum, sonst
    ``None`` (Lesezeit-Pruefung, kein Aufraeum-Job)."""
    if not user_id or not trip_id:
        return None
    fix = _lese(_fix_path(user_id)).get("fix")
    if not isinstance(fix, dict):
        return None
    if fix.get("trip_id") != trip_id or fix.get("stage_date") != stage_date.isoformat():
        return None
    if not isinstance(fix.get("lat"), (int, float)) or not isinstance(fix.get("lon"), (int, float)):
        return None
    return fix
