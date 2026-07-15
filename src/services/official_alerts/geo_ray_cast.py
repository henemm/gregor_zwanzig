"""Geteilter Ray-Cast-Helper (Jordan-Kurven-Test), Issue #1254.

Extrahiert aus `massif_zones.py` (Issue #1037), damit `massif_zones.py` UND
`department_mapper.py` dieselbe Point-in-Polygon-Implementierung nutzen —
keine zweite Copy-Paste-Implementierung (Projekt-Konsolidierungsregel).

SPEC: docs/specs/modules/issue_1254_department_boundaries.md
"""
from __future__ import annotations


def _point_in_ring(lat: float, lon: float, ring: list[tuple[float, float]]) -> bool:
    """Reines Ray-Casting (Jordan-Kurven-Test), Standardlib, keine Dependency.

    `ring` ist eine Liste von (lon, lat)-Punkten (GeoJSON-Konvention). Zaehlt,
    wie oft ein horizontaler Strahl vom Testpunkt nach rechts die Ring-Kanten
    schneidet — ungerade Anzahl = innerhalb.
    """
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside
