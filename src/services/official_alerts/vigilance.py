"""VigilanceSource — Météo-France amtliche Warnungen (Issue #1035, Slice 2).

Erste echte Quelle für die #1034-Official-Alerts-Registry. Ruft die nationale
Météo-France-Vigilance-API ab (ein gecachter Call pro TTL-Fenster bedient alle
Département-Lookups) und liefert Sturmböen-, Gewitter- und Extreme-Hitze-
Warnungen (Phänomene 1/3/6) ab Farbstufe 2 für Frankreich (Metropole inkl.
Korsika).

Fail-soft: fehlende ENV oder HTTP-Fehler -> ``fetch()`` liefert ``[]`` (kein
Crash, kein Retry-Loop). Kein Mock in Tests: AC-1/AC-4 rufen die echte API.

SPEC: docs/specs/modules/issue_1035_vigilance_source.md
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional

import httpx

from services.official_alerts import warn_egress
from services.official_alerts.department_mapper import lookup_department
from services.official_alerts.models import OfficialAlert
from services.radar_service import (
    _AROME_FR_LAT_MAX,
    _AROME_FR_LAT_MIN,
    _AROME_FR_LON_MAX,
    _AROME_FR_LON_MIN,
)

logger = logging.getLogger("vigilance")

VIGILANCE_URL = (
    "https://public-api.meteofrance.fr/public/DPVigilance/v1/cartevigilance/encours"
)
TIMEOUT = 8.0
# Issue #1348: Erfolgs-/Failure-TTL aus dem geteilten Egress-Kern (1800s/60s).
# Ein National-Call pro Fenster bedient weiterhin alle Orts-Lookups (fester
# cache_key "national"). Die kürzere Failure-TTL (60s statt Erfolgs-TTL) bewahrt
# den F001-Fix: ein API-Ausfall friert die Warnungen nicht die volle Erfolgs-TTL
# lang ein, unterbindet aber den Call-pro-Ort-Sturm im Compare-Lauf.
CACHE_TTL = warn_egress.WARN_SUCCESS_TTL  # 1800.0 — ein National-Call pro Fenster
FAILURE_CACHE_TTL = warn_egress.WARN_FAILURE_TTL  # 60.0 — kurzes Failure-Fenster

# Scope: nur Sturmböen (1), Gewitter (3), Extreme Hitze (6).
_PHENOMENON_MAP = {
    "1": ("wind_gust", "Sturmböen"),
    "3": ("thunderstorm", "Gewitter"),
    "6": ("extreme_heat", "Extreme Hitze"),
}

# Adapter auf die keyed ``warn_egress``-Cache-Vertragsform (Issue #1348): der
# flache National-Cache wird zu einem keyed Dict mit festem Schlüssel "national".
# So bedient EIN nationaler Call weiterhin alle Orts-Lookups im TTL-Fenster.
_CACHE_KEY = "national"
_cache: dict = {}
_warned_missing_key = False


def _warn_once_missing_key() -> None:
    global _warned_missing_key
    if not _warned_missing_key:
        logger.warning(
            "GZ_METEOFRANCE_APIKEY nicht gesetzt — Vigilance-Warnungen "
            "werden übersprungen (fail-soft)."
        )
        _warned_missing_key = True


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _get_cached_cartevigilance() -> Optional[dict]:
    """Liefert die nationale Vigilance-Antwort, gecacht via ``warn_egress``.

    Fester ``cache_key`` "national": EIN Call im Erfolgs- wie Fehlschlag-Fenster
    bedient alle Orts-Lookups (F001-Fix, bewahrt). 30-Min-Erfolgs-Cache +
    429-bewusster Rückzug + Egress-Zähler über den geteilten Kern (Issue #1348).
    Der ENV-Check bleibt in ``fetch()`` — hier wird der Key nur für den Header
    gelesen. ``None`` bei Fehler."""
    def _do_request() -> httpx.Response:
        key = os.environ.get("GZ_METEOFRANCE_APIKEY")
        return httpx.get(VIGILANCE_URL, headers={"apikey": key}, timeout=TIMEOUT)

    return warn_egress.cached_fetch(
        cache=_cache, cache_key=_CACHE_KEY, service="vigilance",
        host="public-api.meteofrance.fr", request_fn=_do_request,
        parse_fn=lambda resp: resp.json(), log=logger,
    )


def _extract_alerts(data: dict, department: str) -> list[OfficialAlert]:
    """Filtert die nationale Antwort auf das Département und den Phänomen-Scope."""
    alerts: list[OfficialAlert] = []
    try:
        periods = data["product"]["periods"]
    except (KeyError, TypeError):
        return alerts

    for period in periods:
        valid_from = _parse_iso(period.get("begin_validity_time"))
        valid_to = _parse_iso(period.get("end_validity_time"))
        domain_ids = (period.get("timelaps") or {}).get("domain_ids") or []
        for domain in domain_ids:
            if str(domain.get("domain_id")) != department:
                continue
            for item in domain.get("phenomenon_items") or []:
                phenomenon_id = str(item.get("phenomenon_id"))
                mapping = _PHENOMENON_MAP.get(phenomenon_id)
                if mapping is None:
                    continue
                level = item.get("phenomenon_max_color_id")
                try:
                    level = int(level)
                except (TypeError, ValueError):
                    continue
                if level < 2:
                    continue
                hazard, label = mapping
                alerts.append(
                    OfficialAlert(
                        source="meteofrance_vigilance",
                        hazard=hazard,
                        level=level,
                        label=label,
                        valid_from=valid_from,
                        valid_to=valid_to,
                        region_label=department,
                    )
                )
    return alerts


class VigilanceSource:
    """Météo-France-Vigilance-Quelle für die Official-Alerts-Registry (#1035)."""

    @property
    def name(self) -> str:
        return "meteofrance_vigilance"

    def covers(self, lat: float, lon: float) -> bool:
        """Frankreich-Bounding-Box-Vorfilter (kein API-Call)."""
        return (
            _AROME_FR_LAT_MIN <= lat <= _AROME_FR_LAT_MAX
            and _AROME_FR_LON_MIN <= lon <= _AROME_FR_LON_MAX
        )

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        if not os.environ.get("GZ_METEOFRANCE_APIKEY"):
            _warn_once_missing_key()
            return []
        department = lookup_department(lat, lon)
        if department is None:
            return []
        data = _get_cached_cartevigilance()
        if data is None:
            return []
        return _extract_alerts(data, department)
