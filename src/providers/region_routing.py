"""Region -> Direct-Provider routing for the Cross-Provider-Fallback (#1141).

Used ONLY at the total-outage seam in `OpenMeteoProvider.fetch_forecast`
(openmeteo.py:864), after the intra-Open-Meteo model fallback (#1115) has
itself been exhausted. Maps a coordinate to an infrastructure-independent
direct provider for its region (AT/DE/FR).

These bounds are BEWUSST gewaehlte Land/Alpen-Rechtecke (grobe Country/Alps
boxes) — sie sind NICHT identisch mit den Modell-Domaenen aus
`openmeteo.REGIONAL_MODELS` (die Modell-Abdeckung, keine Laendergrenzen,
beschreiben). Die Pruefreihenfolge AT -> DE -> FR loest Ueberlappungen
(z. B. Alpengrenze DE/AT, Oberrhein FR/DE) deterministisch auf: der
Alpenraum als Wander-Kernfall faellt bewusst an AT.

Import-Regel (Zyklus-Vermeidung): dieses Modul darf `providers.openmeteo`
NICHT importieren (nur die umgekehrte Richtung ist erlaubt).
"""
from __future__ import annotations

from typing import NamedTuple, Optional


class _RegionBounds(NamedTuple):
    name: str
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float
    provider: str


# Pruefreihenfolge AT -> DE -> FR, erste treffende Region gewinnt.
_REGIONS: tuple[_RegionBounds, ...] = (
    _RegionBounds("AT", 46.3, 49.1, 9.5, 17.2, "at_direct"),
    _RegionBounds("DE", 47.2, 55.1, 5.8, 15.1, "de_direct"),
    _RegionBounds("FR", 41.3, 51.1, -5.2, 8.3, "fr_direct"),
)


def direct_provider_for(lat: float, lon: float) -> Optional[str]:
    """Return the direct-provider name for the first matching region, or
    None if the coordinate lies outside all three region rectangles."""
    for region in _REGIONS:
        if region.min_lat <= lat <= region.max_lat and region.min_lon <= lon <= region.max_lon:
            return region.provider
    return None
