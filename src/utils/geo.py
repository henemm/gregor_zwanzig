"""Geographic utilities — single source of truth for haversine and compass.

Issue #1027: degrees_to_compass and haversine_km were duplicated across the
codebase with minor differences. This module provides one canonical
implementation for each.
"""
from __future__ import annotations

import math

_EARTH_KM = 6371.0088  # identical to Go earthRadiusKm

_COMPASS_LABELS = {
    "en": ["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
    "de": ["N", "NO", "O", "SO", "S", "SW", "W", "NW"],
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points in kilometres."""
    rad = math.pi / 180.0
    d_lat = (lat2 - lat1) * rad
    d_lon = (lon2 - lon1) * rad
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(lat1 * rad) * math.cos(lat2 * rad) * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return _EARTH_KM * c


def _auf_vollkreis(grad: float) -> float:
    """Winkel auf [0, 360) -- ``% 360`` allein kann bei -1e-15 genau 360.0 liefern."""
    grad = grad % 360.0
    return 0.0 if grad >= 360.0 else grad


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Anfangspeilung (Grosskreis) von Punkt 1 nach Punkt 2 in Grad [0, 360),
    0 = N, 90 = O (Issue #3222, ADR-0126)."""
    rad = math.pi / 180.0
    phi1, phi2 = lat1 * rad, lat2 * rad
    d_lon = (lon2 - lon1) * rad
    x = math.sin(d_lon) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lon)
    return _auf_vollkreis(math.degrees(math.atan2(x, y)))


def mean_direction_deg(degs, weights=None) -> float | None:
    """Vektorielles (zirkulaeres) Mittel von Winkeln in Grad [0, 360), nie
    arithmetisch: 350 und 10 ergeben 0, nicht 180 (ADR-0126). Fehlende Winkel
    (``None``) zaehlen nicht. ``None``, wenn nichts bleibt oder sich die
    Richtungen aufheben (z. B. 0 und 180)."""
    werte = list(degs)
    gewichte = [1.0] * len(werte) if weights is None else list(weights)
    if len(gewichte) != len(werte):
        raise ValueError("mean_direction_deg: Anzahl Gewichte != Anzahl Winkel")  # i18n-log
    paare = [(math.radians(d), w) for d, w in zip(werte, gewichte) if d is not None]
    s = sum(w * math.sin(r) for r, w in paare)
    c = sum(w * math.cos(r) for r, w in paare)
    if math.hypot(s, c) < 1e-9:
        return None
    return _auf_vollkreis(math.degrees(math.atan2(s, c)))


def point_to_segment_m(
    lat: float, lon: float,
    a_lat: float, a_lon: float, b_lat: float, b_lon: float,
) -> tuple[float, float]:
    """Abstand eines Punkts zur Strecke A-B in Metern und Streckenanteil
    ``frac`` (0 = A, 1 = B) des Lotfusspunkts (Issue #2327).

    Lokale Equirectangular-Projektion um die Breite des Punkts -- auf
    Etappen-Massstab (wenige km) liegt der Fehler weit unter einem Meter.
    Gemessen wird zur STRECKE, nicht zum naechsten Endpunkt: ein Punkt mitten
    auf einem langen Abschnitt hat 0 m Abstand, egal wie weit A und B weg sind.
    """
    rad = math.pi / 180.0
    r_m = _EARTH_KM * 1000.0
    k = math.cos(lat * rad)

    def _xy(p_lat: float, p_lon: float) -> tuple[float, float]:
        return ((p_lon - lon) * rad * k * r_m, (p_lat - lat) * rad * r_m)

    ax, ay = _xy(a_lat, a_lon)
    bx, by = _xy(b_lat, b_lon)
    dx, dy = bx - ax, by - ay
    len2 = dx * dx + dy * dy
    frac = 0.0 if len2 <= 0.0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / len2))
    fx, fy = ax + frac * dx, ay + frac * dy
    return math.hypot(fx, fy), frac


def degrees_to_compass(
    degrees: int | float | None,
    *,
    language: str = "en",
    none_label: str = "",
) -> str:
    """Convert wind direction in degrees (0-360) to an 8-point compass label.

    Args:
        degrees: Wind direction in degrees (0=N, 90=E, 180=S, 270=W).
        language: "en" or "de".
        none_label: Value returned when ``degrees`` is None.

    Returns:
        Compass direction string or ``none_label`` when the input is None.
    """
    if degrees is None:
        return none_label
    degrees = int(degrees) % 360
    directions = _COMPASS_LABELS.get(language, _COMPASS_LABELS["en"])
    return directions[round(degrees / 45) % 8]
