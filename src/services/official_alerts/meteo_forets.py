"""MeteoForetsSource — Météo-France Waldbrand-Gefahrenstufe (Issue #1036, Slice 3).

Dritte Quelle für die #1034-Official-Alerts-Registry. Ruft die amtliche
Météo-France-„Météo des forêts"-API ab und liefert die Waldbrand-Gefahrenstufe
(1–4) pro Département — nur während der Saison Juni–September, in der die Quelle
überhaupt Werte liefert.

Anders als Vigilance ist der Endpunkt bereits département-scoped
(``id-departement={dep}``): ein nationaler Bulk-Call ist strukturell nicht
möglich, daher wird PRO Département gecacht (TTL 300s Erfolg / 60s Fehlschlag,
identische Werte wie ``vigilance.py``). Kein Mindest-Schwellwert: JEDE Stufe 1–4
wird als ``OfficialAlert`` geliefert.

Fail-soft: fehlende ENV oder HTTP-Fehler -> ``fetch()`` liefert ``[]`` (kein
Crash, kein Retry-Loop). Kein Mock in Tests: AC-1 ruft die echte API.

SPEC: docs/specs/modules/issue_1036_meteo_forets_source.md
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

logger = logging.getLogger("meteo_forets")

METEO_FORETS_URL = (
    "https://public-api.meteofrance.fr/public/DPMeteoForets/v1/carte/departement/encours"
)
TIMEOUT = 8.0
# Issue #1348: Erfolgs-/Failure-TTL aus dem geteilten Egress-Kern (1800s/60s).
CACHE_TTL = warn_egress.WARN_SUCCESS_TTL  # 1800.0 — Erfolgs-Fenster pro Département
FAILURE_CACHE_TTL = warn_egress.WARN_FAILURE_TTL  # 60.0 — kurzes Failure-Fenster

# Saison Juni–September: nur in diesen Monaten liefert die Quelle Werte.
_SEASON_MONTHS = {6, 7, 8, 9}

# Modul-Level-Cache PRO Département: {dep: {"data": ..., "fetched_at": ..., "ttl": ...}}
_cache: dict = {}
_warned_missing_key = False


def _is_season(month: int) -> bool:
    """Reine Funktion (kein ``datetime.now()``): Monat in Juni–September?"""
    return month in _SEASON_MONTHS


def _warn_once_missing_key() -> None:
    global _warned_missing_key
    if not _warned_missing_key:
        logger.warning(
            "GZ_METEOFRANCE_APIKEY nicht gesetzt — Waldbrand-Warnungen "
            "werden übersprungen (fail-soft)."
        )
        _warned_missing_key = True


def _get_cached_departement(department: str) -> Optional[list]:
    """Liefert die département-scoped Antwort, gecacht via ``warn_egress``.

    30-Min-Erfolgs-Cache + 429-bewusster Rückzug + Egress-Zähler über den
    geteilten Kern (Issue #1348). Der ENV-Check bleibt in ``fetch()`` — hier wird
    der Key nur für den Header gelesen. ``None`` bei Fehler."""
    def _do_request() -> httpx.Response:
        key = os.environ.get("GZ_METEOFRANCE_APIKEY")
        return httpx.get(
            METEO_FORETS_URL,
            params={
                "format": "json",
                "echeance": "J1",
                "id-departement": department,
            },
            headers={"apikey": key},
            timeout=TIMEOUT,
        )

    return warn_egress.cached_fetch(
        cache=_cache, cache_key=department, service="meteo_forets",
        host="public-api.meteofrance.fr", request_fn=_do_request,
        parse_fn=lambda resp: resp.json(), log=logger,
    )


def _extract_alert(data: list, department: str) -> list[OfficialAlert]:
    """Wandelt die département-Antwort in eine (i.d.R. einelementige) Alert-Liste."""
    alerts: list[OfficialAlert] = []
    if not isinstance(data, list):
        return alerts
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            level = int(item.get("niveau_j1"))
        except (TypeError, ValueError):
            continue
        alerts.append(
            OfficialAlert(
                source="meteo_forets",
                hazard="wildfire_risk",
                level=level,
                label=f"Waldbrand-Gefahr — Stufe {level}",
                region_label=department,
            )
        )
    return alerts


class MeteoForetsSource:
    """Météo-France-Waldbrand-Quelle für die Official-Alerts-Registry (#1036)."""

    @property
    def name(self) -> str:
        return "meteo_forets"

    def covers(self, lat: float, lon: float) -> bool:
        """Saison-Gate (Juni–September) plus Frankreich-Bounding-Box (kein API-Call)."""
        if not _is_season(datetime.now().month):
            return False
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
        data = _get_cached_departement(department)
        if data is None:
            return []
        return _extract_alert(data, department)
