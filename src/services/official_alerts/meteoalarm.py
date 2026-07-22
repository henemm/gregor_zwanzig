"""MeteoAlarmSource — amtliche Warnungen Österreich/Italien (Issue #1086, Slice 2).

Zweite Nicht-Frankreich-Quelle für die #1034-Official-Alerts-Registry. Ruft
die amtliche OGC-EDR-API ``api.meteoalarm.org`` ab (Länder-Index -> exakte
Fläche via ``geometry``-Link -> Punkt-in-Fläche-Filter -> CAP-XML via
``hubLink``) und bringt Italien erstmals in die amtlichen Warnungen sowie
Österreich redundant zu ``GeoSphereWarnSource``. Cross-Source-Dedup pro
einzelnem Punkt in ``get_official_alerts_for_location()`` (``base.py``,
Issue #1086 Adversary-Korrektur F002) -- ``dedup_id`` bleibt ``None``.

Fail-soft: fehlende ENV ``GZ_METEOALARM_APIKEY`` oder jeder HTTP-/Parse-Fehler
(Index-JSON, geometry-Link, CAP-XML) -> ``fetch()`` liefert ``[]`` bzw.
überspringt das betroffene Feature/Land, wirft nie.

SPEC: docs/specs/modules/issue_1086_meteoalarm_source.md
"""
from __future__ import annotations

import logging
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from services.official_alerts import warn_egress
from services.official_alerts.models import OfficialAlert
from services.radar_service import (
    _DPC_LAT_MAX,
    _DPC_LAT_MIN,
    _DPC_LON_MAX,
    _DPC_LON_MIN,
    _INCA_LAT_MAX,
    _INCA_LAT_MIN,
    _INCA_LON_MAX,
    _INCA_LON_MIN,
)

logger = logging.getLogger("meteoalarm")

METEOALARM_BASE_URL = "https://api.meteoalarm.org/edr/v1"
TIMEOUT = 8.0
# Issue #1348: Erfolgs-/Failure-TTL aus dem geteilten Egress-Kern (1800s/60s).
# Attributname + Rolle im Cache-Eintrag bleiben, der Wert steigt auf 1800s.
CACHE_TTL = warn_egress.WARN_SUCCESS_TTL  # 1800.0 — Erfolgs-Fenster (30 min)
FAILURE_CACHE_TTL = warn_egress.WARN_FAILURE_TTL  # 60.0 — kurzes Failure-Fenster

# awareness_type (führende Ganzzahl) -> App-hazard. 4 (fog), 7 (coastal-event),
# 9 (avalanche), 11 (flood): keine App-Kategorie, bewusst NICHT gemappt ->
# wird uebersprungen (analog unbekannter warntypid bei GeoSphere, kein Crash).
_TYPE_HAZARD_MAP: dict[int, str] = {
    1: "wind_gust",
    2: "snow",
    3: "thunderstorm",
    5: "extreme_heat",
    6: "extreme_cold",
    8: "wildfire_risk",
    10: "rain",
    12: "rain",
}

# Modul-Level-Caches: Index pro Land, geometry-/CAP-Inhalte pro URL.
_index_cache: dict[str, dict] = {}
_geometry_cache: dict[str, dict] = {}
_cap_cache: dict[str, dict] = {}

_warned_missing_key = False


def _warn_once_missing_key() -> None:
    global _warned_missing_key
    if not _warned_missing_key:
        logger.warning(
            "GZ_METEOALARM_APIKEY nicht gesetzt — MeteoAlarm-Warnungen "
            "werden übersprungen (fail-soft)."
        )
        _warned_missing_key = True


def _local_tag(elem: ET.Element) -> str:
    tag = elem.tag
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _child_text(elem: ET.Element, name: str) -> Optional[str]:
    for child in elem:
        if _local_tag(child) == name:
            text = (child.text or "").strip()
            return text or None
    return None


def _find_parameter(info_elem: ET.Element, value_name: str) -> Optional[str]:
    for child in info_elem:
        if _local_tag(child) != "parameter":
            continue
        if _child_text(child, "valueName") == value_name:
            return _child_text(child, "value")
    return None


def _find_area_desc(info_elem: ET.Element) -> Optional[str]:
    for child in info_elem:
        if _local_tag(child) == "area":
            return _child_text(child, "areaDesc")
    return None


def _leading_int(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    match = re.match(r"\s*(\d+)", raw)
    return int(match.group(1)) if match else None


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _pick_preferred_entry(entries: list[dict]) -> dict:
    """Bevorzugt ``xml:lang="de*"``, Fallback ``en*``, sonst der erste Eintrag."""
    for entry in entries:
        if entry["lang"].lower().startswith("de"):
            return entry
    for entry in entries:
        if entry["lang"].lower().startswith("en"):
            return entry
    return entries[0]


def _extract_alerts_from_cap(cap_source: "str | bytes") -> list[OfficialAlert]:
    """Wandelt eine CAP-XML-Antwort in eine Liste von ``OfficialAlert`` um.

    Gruppiert die ``<info>``-Sprachvarianten (identische ``awareness_type``/
    ``awareness_level``/``onset``/``expires``/``areaDesc``) zu je EINER
    Warnung, wählt daraus den bevorzugten Sprachblock für den Text. Kaputtes
    XML oder unbekannte/gefilterte Warnungen führen NIE zu einem Crash der
    gesamten Antwort — betroffene Warnungen werden übersprungen.
    """
    text = cap_source.decode("utf-8", errors="replace") if isinstance(cap_source, bytes) else cap_source
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []

    groups: dict[tuple, list[dict]] = {}
    order: list[tuple] = []
    for info in root:
        if _local_tag(info) != "info":
            continue
        try:
            lang = _child_text(info, "language") or ""
            event = _child_text(info, "event")
            headline = _child_text(info, "headline")
            onset = _child_text(info, "onset")
            expires = _child_text(info, "expires")
            area_desc = _find_area_desc(info)
            level_raw = _find_parameter(info, "awareness_level")
            type_raw = _find_parameter(info, "awareness_type")
        except Exception:
            continue
        if not level_raw or not type_raw:
            continue
        key = (type_raw, level_raw, onset, expires, area_desc)
        entry = {"lang": lang, "event": event, "headline": headline}
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(entry)

    alerts: list[OfficialAlert] = []
    for key in order:
        type_raw, level_raw, onset, expires, area_desc = key
        try:
            level = _leading_int(level_raw)
            if level is None or level < 2:
                continue
            hazard = _TYPE_HAZARD_MAP.get(_leading_int(type_raw))
            if hazard is None:
                continue
            preferred = _pick_preferred_entry(groups[key])
            label = preferred.get("event") or preferred.get("headline") or hazard
            alerts.append(
                OfficialAlert(
                    source="meteoalarm",
                    hazard=hazard,
                    level=level,
                    label=label,
                    valid_from=_parse_iso(onset),
                    valid_to=_parse_iso(expires),
                    region_label=area_desc,
                )
            )
        except Exception:
            logger.warning("MeteoAlarm-CAP-Mapping fehlgeschlagen", exc_info=True)
            continue
    return alerts


def _get_cached_index(country: str) -> Optional[dict]:
    """Liefert den Länder-Index, gecacht via ``warn_egress``. ``None`` bei Fehler."""
    def _do_request() -> httpx.Response:
        key = os.environ.get("GZ_METEOALARM_APIKEY")
        now_dt = datetime.now(timezone.utc)
        start = (now_dt - timedelta(hours=23)).strftime("%Y-%m-%dT%H:%M:%SZ")
        end = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"{METEOALARM_BASE_URL}/collections/warnings/locations/{country}"
        return httpx.get(
            url,
            params={"datetime": f"{start}/{end}"},
            headers={"Authorization": f"Bearer {key}"},
            timeout=TIMEOUT,
        )

    def _parse(resp: httpx.Response) -> dict:
        # 204/leerer Body ist der reguläre "keine Warnung"-Fall (z.B. Italien bei
        # gutem Wetter), kein Fehler -- als leeres, gültiges Ergebnis behandeln.
        if resp.status_code == 204 or not resp.content.strip():
            return {"features": []}
        return resp.json()

    return warn_egress.cached_fetch(
        cache=_index_cache, cache_key=country, service="meteoalarm",
        host="api.meteoalarm.org", request_fn=_do_request, parse_fn=_parse,
        log=logger,
    )


def _fetch_geometry_link(feature: dict) -> Optional[dict]:
    """Lädt die exakte Fläche (``rel="geometry"``-Link), gecacht pro URL."""
    href = next(
        (link.get("href") for link in feature.get("links") or [] if link.get("rel") == "geometry"),
        None,
    )
    if not href:
        return None
    return warn_egress.cached_fetch(
        cache=_geometry_cache, cache_key=href, service="meteoalarm",
        host="api.meteoalarm.org",
        request_fn=lambda: httpx.get(href, timeout=TIMEOUT),
        parse_fn=lambda resp: resp.json().get("geometry"),
        log=logger,
    )


def _fetch_cap(url: str) -> Optional[str]:
    """Lädt die CAP-XML (auth-frei), gecacht pro URL."""
    return warn_egress.cached_fetch(
        cache=_cap_cache, cache_key=url, service="meteoalarm",
        host="api.meteoalarm.org",
        request_fn=lambda: httpx.get(url, timeout=TIMEOUT),
        parse_fn=lambda resp: resp.text,
        log=logger,
    )


def _point_in_ring(lat: float, lon: float, ring: list) -> bool:
    """Ray-Casting gegen einen einzelnen GeoJSON-Ring ([lon, lat]-Paare)."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat):
            x_at_lat = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < x_at_lat:
                inside = not inside
        j = i
    return inside


def _point_in_polygon_coords(lat: float, lon: float, coords: list) -> bool:
    if not coords:
        return False
    if not _point_in_ring(lat, lon, coords[0]):
        return False
    return not any(_point_in_ring(lat, lon, hole) for hole in coords[1:])


def _point_in_geometry(lat: float, lon: float, geometry: dict) -> bool:
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if gtype == "Polygon":
        return _point_in_polygon_coords(lat, lon, coords)
    if gtype == "MultiPolygon":
        return any(_point_in_polygon_coords(lat, lon, poly) for poly in coords or [])
    return False


class MeteoAlarmSource:
    """MeteoAlarm-Quelle (AT + IT) für die Official-Alerts-Registry (#1086)."""

    @property
    def name(self) -> str:
        return "meteoalarm"

    def covers(self, lat: float, lon: float) -> bool:
        """AT- (INCA-Bbox) ∪ IT-Bbox (DPC) Vorfilter (kein API-Call)."""
        in_at = _INCA_LAT_MIN <= lat <= _INCA_LAT_MAX and _INCA_LON_MIN <= lon <= _INCA_LON_MAX
        in_it = _DPC_LAT_MIN <= lat <= _DPC_LAT_MAX and _DPC_LON_MIN <= lon <= _DPC_LON_MAX
        return in_at or in_it

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        if not os.environ.get("GZ_METEOALARM_APIKEY"):
            _warn_once_missing_key()
            return []

        alerts: list[OfficialAlert] = []
        for country in ("AT", "IT"):
            index = _get_cached_index(country)
            if index is None:
                continue
            for feature in index.get("features") or []:
                try:
                    geometry = _fetch_geometry_link(feature)
                    if geometry is None or not _point_in_geometry(lat, lon, geometry):
                        continue
                    hub_link = feature["properties"]["hubLink"]
                    cap_text = _fetch_cap(hub_link)
                    if cap_text is None:
                        continue
                    alerts.extend(_extract_alerts_from_cap(cap_text))
                except Exception:
                    logger.warning(
                        "MeteoAlarm-Feature-Verarbeitung fehlgeschlagen", exc_info=True
                    )
                    continue
        return alerts
