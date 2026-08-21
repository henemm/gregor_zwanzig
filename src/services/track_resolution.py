"""Track-Auflösung fuer Bestandstrips ohne gemessene Wegstrecke (Issue #2036).

Wegpunkte importierter Etappen SIND Original-Trackpunkte -- gemessener
Abstand 0,0 m. Liegt der zugehoerige GPX-Track noch im Bestand des Nutzers
(``data/users/<user_id>/gpx/``), laesst sich die beim Import verworfene
Wegstrecke deshalb eindeutig nachtragen, statt sie aus Luftlinie zu
schaetzen.

Zwei Regeln machen das Nachtragen belastbar statt raterisch:

* **Vollstaendigkeit** -- ein Track passt nur, wenn er JEDEN Wegpunkt der
  Etappe innerhalb der Toleranz enthaelt. Ein einziger manuell verschobener
  oder ergaenzter Wegpunkt (>10 m abseits) laesst die GANZE Etappe
  unvermessen (AC-12).
* **Eindeutigkeit** -- passen mehrere Dateien gleichermassen (etwa eine
  Einzeletappen- UND eine Gesamt-GPX), wird KEINE geraten (AC-11).

Ohne eindeutigen Treffer liefert die Auflösung ``None``; die Ortsangabe
bleibt dann byte-identisch bei ``Segment N`` (AC-10).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

from utils.geo import haversine_km

logger = logging.getLogger("track_resolution")

# Toleranz Wegpunkt <-> Trackpunkt. Original-Trackpunkte liegen bei 0,0 m,
# die naechstbeste (falsche) Datei im gemessenen Bestand bei >= 4.672 m --
# 10 m deckt Koordinatenrundung ab und liegt drei Groessenordnungen unter
# dem Fehlerfall (Spec "Festgelegte Schwellenwerte").
DEFAULT_TOLERANCE_M = 10.0


def _match_track(
    waypoints: List, points: List, tolerance_m: float,
) -> Optional[Dict[str, float]]:
    """Distanz je Wegpunkt aus DIESEM Track -- oder ``None``, wenn auch nur
    ein Wegpunkt weiter als die Toleranz vom naechstgelegenen Trackpunkt
    entfernt liegt (alles oder nichts, AC-12)."""
    result: Dict[str, float] = {}
    for wp in waypoints:
        best_km: Optional[float] = None
        best_dist: Optional[float] = None
        for pt in points:
            d = haversine_km(wp.lat, wp.lon, pt.lat, pt.lon)
            if best_dist is None or d < best_dist:
                best_dist = d
                best_km = pt.distance_from_start_km
        if best_dist is None or best_dist * 1000.0 > tolerance_m:
            return None
        result[wp.id] = best_km
    return result


def resolve_stage_track_km(
    stage, gpx_dir, tolerance_m: float = DEFAULT_TOLERANCE_M,
) -> Optional[Dict[str, float]]:
    """Gemessene Wegstrecke je Wegpunkt der Etappe aus dem GPX-Bestand.

    Args:
        stage: Etappe mit ``waypoints`` (je ``id``/``lat``/``lon``).
        gpx_dir: Verzeichnis des Nutzer-GPX-Bestands.
        tolerance_m: Hoechstabstand Wegpunkt <-> Trackpunkt in Metern.

    Returns:
        ``{waypoint_id: distance_from_start_km}`` bei GENAU einem passenden
        Track, sonst ``None`` (kein Treffer, mehrdeutig, oder mindestens ein
        Wegpunkt abseits).
    """
    from core.gpx_parser import parse_gpx

    waypoints = list(getattr(stage, "waypoints", None) or [])
    directory = Path(gpx_dir)
    if not waypoints or not directory.is_dir():
        return None

    matches: List[Dict[str, float]] = []
    for path in sorted(directory.glob("*.gpx")):
        try:
            track = parse_gpx(path)
        except Exception as e:
            logger.warning(
                "Track-Aufloesung: %s nicht lesbar, uebersprungen (%s)",
                path.name, e,
            )
            continue
        hit = _match_track(waypoints, track.points or [], tolerance_m)
        if hit is not None:
            matches.append(hit)
        if len(matches) > 1:
            return None  # mehrdeutig -- nicht raten (AC-11)
    if len(matches) != 1:
        return None
    return matches[0]


# Etappen, fuer die in DIESEM Prozess bereits erfolglos gesucht wurde. Ohne
# diese Sperre parst jeder Alarmlauf den kompletten GPX-Bestand des Nutzers
# neu, obwohl das Ergebnis feststeht -- der Lauf hat eine Zeitobergrenze.
# Ein Neustart (oder ein frisch hochgeladener Track nach einem Neustart)
# hebt sie auf; das ist die "lazy"-Grenze aus den Known Limitations der Spec.
_failed_lookups: set = set()


def backfill_stage_distances(
    trip, user_id: str, target_date, *, persist: bool = True,
) -> object:
    """Traegt die gemessene Wegstrecke der Etappe zu ``target_date`` einmalig
    nach und schreibt sie additiv an den Trip zurueck (Issue #2036 AC-7).

    Der Rueckschreibweg ist ``save_trip`` -- Read-Modify-Write mit Merge
    (``loader._deep_merge_preserve_unknown``); Felder, die Python nicht
    modelliert (Go-/Legacy-Felder), bleiben erhalten. Betroffen ist NUR die
    eine Etappe: die uebrigen Wegpunkte werden unveraendert durchgereicht.

    Fail-soft: jeder Fehler laesst den Trip unveraendert -- eine fehlende
    Kilometerangabe ist ein Schoenheitsfehler, ein ausgefallener Alarm nicht.

    Args:
        persist: Bei ``False`` (Issue #2036 CI-Nachschlag, PR #2055) wird die
            aufgeloeste Distanz nur INS RUECKGABEOBJEKT geschrieben, nicht
            via ``save_trip`` auf die Platte. Fuer reine Vorschau-Pfade
            (``PreviewService`` -- "kein Versand, nur Render"): eine Ansicht
            darf den Trip-Bestand nicht als Seiteneffekt veraendern, egal
            welcher ``user_id`` sie zugerechnet wird. Alarm- und
            Briefing-Versandpfade lassen den Default (persistieren).

    Returns:
        Den (ggf. ergaenzten) Trip -- immer ein verwendbares Objekt.
    """
    try:
        import dataclasses

        from app.loader import get_data_dir

        stage = trip.get_stage_for_date(target_date)
        if stage is None or not stage.waypoints:
            return trip
        if all(
            getattr(wp, "distance_from_start_km", None) is not None
            for wp in stage.waypoints
        ):
            return trip  # bereits vermessen -- nichts zu tun
        key = (user_id, trip.id, stage.id)
        if key in _failed_lookups:
            return trip
        distances = resolve_stage_track_km(stage, get_data_dir(user_id) / "gpx")
        if distances is None or any(
            wp.id not in distances for wp in stage.waypoints
        ):
            _failed_lookups.add(key)
            return trip
        new_stage = dataclasses.replace(stage, waypoints=[
            dataclasses.replace(wp, distance_from_start_km=distances[wp.id])
            for wp in stage.waypoints
        ])
        updated = dataclasses.replace(trip, stages=[
            new_stage if s.id == stage.id else s for s in trip.stages
        ])
        if persist:
            from app.loader import save_trip

            save_trip(updated, user_id=user_id)
        logger.info(
            "Track-Aufloesung: Etappe %s von Trip %s nachtraeglich vermessen "
            "(%d Wegpunkte, persist=%s)", stage.id, trip.id, len(distances), persist,
        )
        return updated
    except Exception as e:
        logger.warning(
            "Track-Aufloesung fuer Trip %s fehlgeschlagen, Etappe bleibt "
            "unvermessen (%s)", getattr(trip, "id", "?"), e,
        )
        return trip
