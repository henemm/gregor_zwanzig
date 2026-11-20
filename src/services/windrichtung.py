"""Windrichtung als abgeleitete skalare Ampelgroesse (Issue #3222, ADR-0126).

Spec ``docs/specs/modules/feat_3222_windrichtung.md``. Reine Funktionen: die
Richtung wird VOR der Ampel zu ``wind_unerwuenscht_kmh`` reduziert und dann
mit den normalen oberen Grenzen (km/h) bewertet; ``severity_from_thresholds``
bleibt unberuehrt (ADR-0106).

Konvention: ``herkunft_deg`` ist die Richtung, AUS der der Wind kommt
(0 = N, 90 = O); ``peilung_deg`` die Richtung, IN die gefahren wird. Gegenwind
heisst: der Wind kommt aus der Fahrtrichtung.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any, Optional

from utils.geo import bearing_deg, degrees_to_compass, haversine_km

#: Modi von ``ampel.metrics.wind_direction.modus``; fehlt das Feld, gilt "aus".
MODI = ("aus", "gegenwind", "sektoren")
#: Die 8 Sektoren (deutsche Protokoll-Token, nie uebersetzt).
SEKTOREN = ("N", "NO", "O", "SO", "S", "SW", "W", "NW")
#: Unter dieser Luftlinie Start -> Ende hat ein Segment keine Fahrtrichtung.
MIN_LUFTLINIE_KM = 0.3


def sektor_von(herkunft_deg: Optional[float]) -> Optional[str]:
    """8er-Sektor einer Herkunftsrichtung (Grenzen +-22,5 Grad, 359 -> N).
    Dieselbe Zuordnung wie die Anzeige ``WD:{Sektor}`` (``degrees_to_compass``),
    damit gefaerbter Sektor und angezeigter Sektor nie auseinanderfallen."""
    return degrees_to_compass(herkunft_deg, language="de") or None


def gegenwind_kmh(wind_kmh: float, herkunft_deg: float, peilung_deg: float) -> float:
    """Gegenwindkomponente ``max(0, kmh * cos(herkunft - peilung))``, auf eine
    Nachkommastelle gerundet: Rueckenwind und reiner Seitenwind ergeben 0."""
    komponente = wind_kmh * math.cos(math.radians(herkunft_deg - peilung_deg))
    return round(max(0.0, komponente), 1)


def sektor_kmh(wind_kmh: float, herkunft_deg: float, sektoren: Iterable[str]) -> float:
    """Volle Windstaerke, wenn die Herkunft in einem markierten Sektor liegt, sonst 0."""
    return float(wind_kmh) if sektor_von(herkunft_deg) in set(sektoren or ()) else 0.0


def wind_unerwuenscht_kmh(
    modus: Optional[str],
    sektoren: Optional[Iterable[str]],
    wind_kmh: Optional[float],
    herkunft_deg: Optional[float],
    peilung_deg: Optional[float] = None,
) -> Optional[float]:
    """Abgeleiteter Wert je Stunde/Segment/Ort; ``None`` = nicht bestimmbar
    (Modus aus/unbekannt, Winddaten fehlen, Gegenwind ohne Fahrtrichtung)."""
    if modus not in ("gegenwind", "sektoren") or wind_kmh is None or herkunft_deg is None:
        return None
    if modus == "sektoren":
        return sektor_kmh(wind_kmh, herkunft_deg, sektoren or ())
    if peilung_deg is None:
        return None
    return gegenwind_kmh(wind_kmh, herkunft_deg, peilung_deg)


def segment_peilung_deg(segment: Any) -> Optional[float]:
    """Fahrtpeilung eines Segments als Luftlinie ``start_point`` -> ``end_point``;
    ``None`` ohne Punkte oder unter ``MIN_LUFTLINIE_KM`` (z. B. Rundkurs)."""
    start = getattr(segment, "start_point", None)
    ende = getattr(segment, "end_point", None)
    if start is None or ende is None:
        return None
    if haversine_km(start.lat, start.lon, ende.lat, ende.lon) < MIN_LUFTLINIE_KM:
        return None
    return bearing_deg(start.lat, start.lon, ende.lat, ende.lon)
