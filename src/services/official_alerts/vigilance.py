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
import time
from datetime import datetime
from typing import Optional

import httpx

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
CACHE_TTL = 300.0  # Sekunden — ein National-Call pro Fenster für alle Lookups
# Fehlschlag-TTL bewusst kürzer (60s statt 300s): Der Kern-Fix (F001) ist, dass
# ein API-Ausfall NICHT zu einem echten HTTP-Call pro verglichenem Ort führt —
# innerhalb eines Compare-Laufs (Sekundenbereich) reicht schon ein sehr kurzes
# Fenster, um den Call-pro-Ort-Sturm zu unterbinden. Gleichzeitig soll ein nur
# temporärer Ausfall (Timeout/5xx) nicht die volle Erfolgs-TTL lang "eingefroren"
# bleiben, damit sich die Warnungen nach kurzer Erholung wieder zeigen.
FAILURE_CACHE_TTL = 60.0  # Sekunden — kurzes Failure-Fenster gegen Call-pro-Ort-Sturm

# Scope: nur Sturmböen (1), Gewitter (3), Extreme Hitze (6).
_PHENOMENON_MAP = {
    "1": ("wind_gust", "Sturmböen"),
    "3": ("thunderstorm", "Gewitter"),
    "6": ("extreme_heat", "Extreme Hitze"),
}

_cache: dict = {"data": None, "fetched_at": None, "ttl": CACHE_TTL}
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
    """Liefert die nationale Vigilance-Antwort, gecacht mit TTL. ``None`` bei Fehler."""
    now = time.monotonic()
    fetched_at = _cache["fetched_at"]
    # Cache-Treffer gilt für Erfolg (data != None, TTL 300s) UND Fehlschlag
    # (data == None, Failure-TTL 60s): In beiden Fällen wird KEIN neuer echter
    # HTTP-Call ausgelöst, solange das jeweilige TTL-Fenster gilt (F001-Fix).
    if fetched_at is not None and (now - fetched_at) < _cache["ttl"]:
        return _cache["data"]

    key = os.environ.get("GZ_METEOFRANCE_APIKEY")
    try:
        resp = httpx.get(VIGILANCE_URL, headers={"apikey": key}, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        logger.warning("Vigilance-API-Abruf fehlgeschlagen", exc_info=True)
        # F001: Fehlschlag ebenfalls cachen (mit kürzerer Failure-TTL), damit
        # nicht jeder weitere fetch()-Aufruf im selben Compare-Lauf erneut einen
        # echten Netzwerk-Call auslöst. data bleibt None -> Aufrufer erhält wie
        # bisher None (fail-soft), aber ohne Call-pro-Ort-Sturm.
        _cache["data"] = None
        _cache["fetched_at"] = now
        _cache["ttl"] = FAILURE_CACHE_TTL
        return None

    _cache["data"] = data
    _cache["fetched_at"] = now
    _cache["ttl"] = CACHE_TTL
    return data


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
