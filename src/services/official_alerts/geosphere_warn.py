"""GeoSphereWarnSource — amtliche Warnungen Österreich (Issue #1085, Slice 1).

Erste Nicht-Frankreich-Quelle für die #1034-Official-Alerts-Registry. Ruft die
GeoSphere-Warn-API (Österreich) pro Koordinate ab und liefert Sturm-, Regen-,
Schnee-, Glatteis-, Gewitter-, Hitze- und Kälte-Warnungen.

Anders als Vigilance ist der Endpunkt pro Koordinate scoped (kein nationaler
Bulk-Call möglich), daher wird PRO gerundeter Koordinate gecacht (TTL 300s
Erfolg / 60s Fehlschlag, analog ``meteo_forets.py``). Kein ENV nötig
(auth-frei) — fail-soft deckt HTTP-Fehler (inkl. 404), Timeout und kaputtes
JSON.

SPEC: docs/specs/modules/issue_1085_geosphere_warn_source.md
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from services.official_alerts import warn_egress
from services.official_alerts.models import OfficialAlert
from services.radar_service import (
    _INCA_LAT_MAX,
    _INCA_LAT_MIN,
    _INCA_LON_MAX,
    _INCA_LON_MIN,
)

logger = logging.getLogger("geosphere_warn")

GEOSPHERE_WARN_URL = "https://warnungen.zamg.at/wsapp/api/getWarningsForCoords"
TIMEOUT = 8.0
# Issue #1348: Erfolgs-/Failure-TTL aus dem geteilten Egress-Kern (1800s/60s).
CACHE_TTL = warn_egress.WARN_SUCCESS_TTL  # 1800.0 — Erfolgs-Fenster pro Koordinate
FAILURE_CACHE_TTL = warn_egress.WARN_FAILURE_TTL  # 60.0 — kurzes Failure-Fenster

# warntypid -> (hazard, deutsches Label). Wo ein Vigilance-hazard existiert,
# wird derselbe Bezeichner verwendet (Konsistenz für nachgelagerte Filter).
_HAZARD_MAP: dict[int, tuple[str, str]] = {
    1: ("wind_gust", "Sturm"),
    2: ("rain", "Starkregen"),
    3: ("snow", "Schneefall"),
    4: ("black_ice", "Glatteis"),
    5: ("thunderstorm", "Gewitter"),
    6: ("extreme_heat", "Hitze"),
    7: ("extreme_cold", "Kälte"),
}

# Modul-Level-Cache PRO gerundeter Koordinate: {(lat, lon): {"data": ..., "fetched_at": ..., "ttl": ...}}
_cache: dict = {}


def _round_coord(lat: float, lon: float) -> tuple[float, float]:
    return round(lat, 4), round(lon, 4)


def _parse_epoch(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        return None


def _get_cached_warnings(lat: float, lon: float) -> Optional[dict]:
    """Liefert die koordinaten-scoped Antwort, gecacht via ``warn_egress``.

    30-Min-Erfolgs-Cache + 429-bewusster Rückzug + Egress-Zähler über den
    geteilten Kern (Issue #1348). ``None`` bei Fehler."""
    key = _round_coord(lat, lon)

    def _do_request() -> httpx.Response:
        return httpx.get(
            GEOSPHERE_WARN_URL,
            params={"lat": key[0], "lon": key[1], "lang": "de"},
            timeout=TIMEOUT,
        )

    return warn_egress.cached_fetch(
        cache=_cache, cache_key=key, service="geosphere_warn",
        host="warnungen.zamg.at", request_fn=_do_request,
        parse_fn=lambda resp: resp.json(), log=logger,
    )


def _extract_alerts(data: dict) -> list[OfficialAlert]:
    """Wandelt eine GeoSphere-Antwort in eine Liste von ``OfficialAlert`` um.

    Unbekannte ``warntypid``-Werte werden pro Warnung übersprungen, nicht als
    Crash der gesamten Antwort behandelt.
    """
    alerts: list[OfficialAlert] = []
    try:
        properties = data["properties"]
        region_label = properties["location"]["properties"]["name"]
        warnings = properties["warnings"]
    except (KeyError, TypeError):
        return alerts

    for warning in warnings or []:
        try:
            props = warning["properties"]
            warntypid = int(props["warntypid"])
            warnstufeid = int(props["warnstufeid"])
        except (KeyError, TypeError, ValueError):
            continue

        mapping = _HAZARD_MAP.get(warntypid)
        if mapping is None:
            continue
        hazard, label = mapping

        rawinfo = props.get("rawinfo") or {}
        valid_from = _parse_epoch(rawinfo.get("start"))
        valid_to = _parse_epoch(rawinfo.get("end"))

        alerts.append(
            OfficialAlert(
                source="geosphere_warn",
                hazard=hazard,
                level=warnstufeid + 1,
                label=label,
                valid_from=valid_from,
                valid_to=valid_to,
                region_label=region_label,
            )
        )
    return alerts


class GeoSphereWarnSource:
    """GeoSphere-Warn-Quelle (Österreich) für die Official-Alerts-Registry (#1085)."""

    @property
    def name(self) -> str:
        return "geosphere_warn"

    def covers(self, lat: float, lon: float) -> bool:
        """Österreich-Bounding-Box-Vorfilter (kein API-Call)."""
        return (
            _INCA_LAT_MIN <= lat <= _INCA_LAT_MAX
            and _INCA_LON_MIN <= lon <= _INCA_LON_MAX
        )

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        data = _get_cached_warnings(lat, lon)
        if data is None:
            return []
        return _extract_alerts(data)
