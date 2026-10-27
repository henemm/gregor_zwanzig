"""MeteoAlarm-CAP-Mapper — geteilte Abbildung amtlicher MeteoAlarm-Warnungen.

Bildet MeteoAlarm-Warneinträge (``awareness_level``/``awareness_type`` samt
Sprachblöcken) auf ``OfficialAlert`` ab. Einziger Produktivnutzer ist der
kontingentfreie Feed-Weg ``meteoalarm_feed.MeteoAlarmFeedSource`` (AT/IT/DE),
der ``_group_and_map_info_entries`` importiert.

Die frühere kontingentierte EDR-Klasse ``MeteoAlarmSource`` (Index, Budget,
Drossel, Geometrie) ist mit Issue #2266 zurückgebaut. ``_collect_cap_info_entries``
und ``_extract_alerts_from_cap`` haben danach keinen Produktivaufrufer mehr,
bleiben aber als dokumentierte CAP-XML-Schnittstelle des Mappers erhalten:
Kern-Tests (``tests/tdd/test_meteoalarm_cap_mapper.py`` u. a.) und die Ratsche
``tests/test_resolution_loss_guard.py`` nutzen sie.

SPEC: docs/specs/modules/refactor_2266_meteoalarm_edr_rueckbau.md
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

from services.official_alerts.models import OfficialAlert

logger = logging.getLogger("meteoalarm")


# awareness_type (führende Ganzzahl) -> App-hazard. 11 (flood), 12 (flooding),
# 13 (rain-flood) sind Ueberschwemmungs-Warnarten und werden auf "flood"
# abgebildet (Issue #1427 S1; 12 war zuvor faelschlich "rain", 13 unabgebildet).
# 9 (avalanche) -> "avalanche" (Issue #1430). 4 (fog), 7 (coastal-event):
# keine App-Kategorie, bewusst NICHT gemappt (s. _DISCARDED_TYPES) -> wird
# uebersprungen (analog unbekannter warntypid bei GeoSphere, kein Crash).
_TYPE_HAZARD_MAP: dict[int, str] = {
    1: "wind_gust",
    2: "snow",
    3: "thunderstorm",
    5: "extreme_heat",
    6: "extreme_cold",
    8: "wildfire_risk",
    9: "avalanche",
    10: "rain",
    11: "flood",
    12: "flood",
    13: "flood",
}

# Bewusst verworfene awareness_types (Issue #1430) -- nur fuer die Debug-Zeile.
_DISCARDED_TYPES: dict[int, str] = {
    4: "Nebel",
    7: "Kueste",
}


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


def _collect_cap_info_entries(cap_source: "str | bytes") -> list[dict]:
    """Sammelt jeden ``<info>``-Block einer CAP-XML-Antwort als normalisiertes
    Dict (Issue #1445 S1: XML-spezifische Haelfte des ehemaligen
    ``_extract_alerts_from_cap`` -- ``_group_and_map_info_entries`` uebernimmt
    danach den formatunabhaengigen Teil, gemeinsam mit dem JSON-Feed-Weg in
    ``meteoalarm_feed.py``). Kaputtes XML liefert ``[]``, ein defekter
    einzelner ``<info>``-Block wird uebersprungen -- unveraendertes
    Fail-soft-Verhalten."""
    text = cap_source.decode("utf-8", errors="replace") if isinstance(cap_source, bytes) else cap_source
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []

    entries: list[dict] = []
    for info in root:
        if _local_tag(info) != "info":
            continue
        try:
            entries.append({
                "lang": _child_text(info, "language") or "",
                "event": _child_text(info, "event"),
                "headline": _child_text(info, "headline"),
                "onset": _child_text(info, "onset"),
                "expires": _child_text(info, "expires"),
                "area_desc": _find_area_desc(info),
                "level_raw": _find_parameter(info, "awareness_level"),
                "type_raw": _find_parameter(info, "awareness_type"),
            })
        except Exception:
            continue
    return entries


def _group_and_map_info_entries(entries: list[dict]) -> list[OfficialAlert]:
    """Gruppiert normalisierte Info-Eintraege (identische ``type_raw``/
    ``level_raw``/``onset``/``expires``/``area_desc``) zu je EINER Warnung,
    waehlt daraus den bevorzugten Sprachblock fuer den Text (Issue #1445 S1:
    formatunabhaengige Haelfte -- gemeinsam genutzt vom XML-Sammelweg
    (``_collect_cap_info_entries``) UND dem JSON-Feed-Sammelweg
    (``meteoalarm_feed._info_entries_from_alert``)). Eintraege ohne
    ``level_raw``/``type_raw`` oder mit unbekanntem/gefiltertem Typ/Level
    werden uebersprungen -- nie ein Crash der gesamten Antwort."""
    groups: dict[tuple, list[dict]] = {}
    order: list[tuple] = []
    for entry in entries:
        level_raw = entry.get("level_raw")
        type_raw = entry.get("type_raw")
        if not level_raw or not type_raw:
            continue
        # Issue #1681 (AC-5): eine amtliche Aufhebung ist keine aktive Warnung.
        # Bewusst eng: nur "AllClear" (IT/AT tragen None/"Monitor").
        if "AllClear" in (entry.get("response_type") or ()):
            continue
        key = (type_raw, level_raw, entry.get("onset"), entry.get("expires"), entry.get("area_desc"))
        lang_entry = {"lang": entry.get("lang") or "", "event": entry.get("event"), "headline": entry.get("headline")}
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(lang_entry)

    alerts: list[OfficialAlert] = []
    for key in order:
        type_raw, level_raw, onset, expires, area_desc = key
        try:
            level = _leading_int(level_raw)
            if level is None or level < 2:
                continue
            type_num = _leading_int(type_raw)
            hazard = _TYPE_HAZARD_MAP.get(type_num)
            if hazard is None:
                name = _DISCARDED_TYPES.get(type_num)
                grund = "bewusst nicht unterstuetzt" if name else "unbekannter awareness_type"
                logger.debug(
                    "MeteoAlarm awareness_type %s (%s) Stufe %s verworfen: %s",
                    type_num, name or type_raw, level, grund,
                )
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


def _extract_alerts_from_cap(cap_source: "str | bytes") -> list[OfficialAlert]:
    """Wandelt eine CAP-XML-Antwort in eine Liste von ``OfficialAlert`` um.

    Duenner Wrapper (Issue #1445 S1) um die zwei getrennten Haelften: XML
    sammeln (``_collect_cap_info_entries``), dann formatunabhaengig
    gruppieren/mappen (``_group_and_map_info_entries``) -- unveraendertes
    Verhalten (Regressionsschutz: ``tests/tdd/test_meteoalarm_cap_mapper.py``).
    """
    return _group_and_map_info_entries(_collect_cap_info_entries(cap_source))
