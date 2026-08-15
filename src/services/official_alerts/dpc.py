"""DpcSource — italienischer Zivilschutz (Protezione Civile), Issue #1427 S2.

Dauerhaft additive amtliche Warnquelle fuer Italien (Gewitter/Hochwasser/
Erdrutsch), ergaenzt MeteoAlarmSource (Hitze/Wind/Regen/Gewitter, aus Sicht
der italienischen Luftwaffe) -- keine Zweitschrift, kein ``fallback_for``.

Laufzeit liest NUR die ``.dbf`` aus dem oeffentlichen DPC-Zip (dBase-III,
fester Satzbreite ASCII/latin-1 -- Standardlib-``struct``, keine neue
Geo-Abhaengigkeit). Die Geometrie der 187 Zonen liegt bereits offline
extrahiert in ``data/dpc_zones.json``.

Bezugstag (AC-3, wichtigster Punkt): Dateien heissen
``<YYYYMMDD>_<HHMM>_today.dbf``/``_tomorrow.dbf`` -- ``today`` meint den
AUSGABETAG des Bulletins, nicht den Abruftag. Ist der Ausgabetag = gestern,
gilt fuer heute der ``tomorrow``-Datensatz. Liegt das Bulletin weiter
zurueck, ist kein Datensatz mehr gueltig -> leere Liste.

SPEC: docs/specs/modules/feat_1427_dpc_warn_fallback.md (Fassung 2.0), AC-2..AC-7.
"""
from __future__ import annotations

import io
import json
import logging
import re
import struct
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

import httpx

from services.official_alerts import warn_egress
from services.official_alerts.geo_ray_cast import _point_in_ring
from services.official_alerts.models import OfficialAlert
from services.radar_service import (
    _ITALY_RADAR_LAT_MAX, _ITALY_RADAR_LAT_MIN,
    _ITALY_RADAR_LON_MAX, _ITALY_RADAR_LON_MIN,
)

logger = logging.getLogger("dpc")

DPC_ZIP_URL = (
    "https://raw.githubusercontent.com/pcm-dpc/"
    "DPC-Bollettini-Criticita-Idrogeologica-Idraulica/master/files/all/latest_all.zip"
)
TIMEOUT = 15.0  # 4,6 MB Zip -- grosszuegiger als die schlanken JSON-Quellen
CACHE_TTL = warn_egress.WARN_SUCCESS_TTL  # 1800s -- Bulletin aendert sich ~1x/Tag
FAILURE_CACHE_TTL = warn_egress.WARN_FAILURE_TTL
_CACHE_KEY = "national"
_cache: dict = {}

# Injizierbarer Uhr-Haken (Konvention analog meteoalarm._WALL_CLOCK_FN) --
# Default echte Wanduhr, Tests stellen ihn deterministisch.
def _default_now() -> datetime:
    return datetime.now(timezone.utc)


_NOW_FN: Callable[[], datetime] = _default_now

_ZONES_PATH = Path(__file__).resolve().parent / "data" / "dpc_zones.json"
_FILENAME_RE = re.compile(r"(\d{8})_(\d{4})_(today|tomorrow)\.dbf$", re.IGNORECASE)
_LEVEL_RE = re.compile(r"ALLERTA\s+(GIALLA|ARANCIONE|ROSSA)", re.IGNORECASE)
_LEVEL_MAP = {"GIALLA": 2, "ARANCIONE": 3, "ROSSA": 4}


def _load_zones(path: Path = _ZONES_PATH) -> list[dict]:
    """Fail-soft wie massif_zones.py::_load_massifs(): defekte/fehlende Datei
    -> Warnung + [], nie ein Raise beim Modul-Import."""
    try:
        return json.loads(path.read_text())
    except Exception:
        logger.warning("dpc: Zonen-Polygone nicht ladbar (%s) -- DPC deaktiviert", path, exc_info=True)
        return []


_ZONES: list[dict] = _load_zones()
_KNOWN_ZONE_CODES: set[str] = {zone["zona"] for zone in _ZONES}


def _zone_at(lat: float, lon: float) -> Optional[str]:
    """Punkt-in-Flaeche gegen alle geladenen DPC-Zonen (Zona-Code oder None)."""
    for zone in _ZONES:
        for ring in zone["rings"]:
            if _point_in_ring(lat, lon, ring):
                return zone["zona"]
    return None


def _parse_dbf(data: bytes) -> list[dict]:
    """dBase-III-Datensaetze fester Breite (32-Byte-Header, Feld-Deskriptoren
    bis 0x0D, danach ASCII/latin-1-Saetze) -- kein Shapefile-Binaerformat."""
    nrec, hlen, rlen = struct.unpack("<IHH", data[4:12])
    fields: list[tuple[str, int]] = []
    off = 32
    while data[off] != 0x0D:
        name = data[off:off + 11].split(b"\x00")[0].decode("latin-1")
        length = data[off + 16]
        fields.append((name, length))
        off += 32
    records: list[dict] = []
    for i in range(nrec):
        rec = data[hlen + i * rlen: hlen + (i + 1) * rlen]
        pos = 1
        row: dict = {}
        for name, length in fields:
            row[name] = rec[pos:pos + length].decode("latin-1").strip()
            pos += length
        records.append(row)
    return records


def _records_by_zone(records: list[dict]) -> dict[str, dict]:
    """Kreuzreferenziert DBF-Zonencodes gegen die geladene Geometrie (AC-5c):
    ein Code ohne Polygon-Eintrag wird geloggt statt kommentarlos zu
    verschwinden."""
    by_zone: dict[str, dict] = {}
    for row in records:
        code = row.get("Zona_all", "")
        if code not in _KNOWN_ZONE_CODES:
            logger.warning("dpc: unbekannter Zonencode %r im Bulletin (keine Geometrie)", code)
            # Issue #1434 Pfad A: trennen, ob die verworfene Zeile eine ECHTE
            # Warnstufe traegt (tatsaechlicher Verlust) oder nur NESSUNA
            # ALLERTA (harmlos) -- additive Ereigniszeile im Diagnose-Journal.
            # Laeuft innerhalb von warn_egress.cached_fetch(parse_fn=...) --
            # bei einem Cache-Treffer wird dieser Parse NICHT erneut
            # ausgefuehrt, es entsteht also eine Zeile je echtem Abruf, nicht
            # je Ort (gewollt, s. Spec Implementation Details Punkt 2).
            has_warning = any(
                _level_from_text(row.get(field, "")) is not None
                for field in ("Temporali", "Idrogeo", "Idraulico")
            )
            warn_egress.log_zone_drift("dpc", code, has_warning, "bulletin_only")
            continue
        by_zone[code] = row
    return by_zone


def _parse_bulletin_zip(resp: httpx.Response) -> dict:
    """Zip -> {bulletin_date, by_day: {"today"/"tomorrow": {zona: row}}}.
    Wirft bei defektem Zip/fehlenden Dateien -- ``warn_egress.cached_fetch``
    faengt das als Fehlschlag ab (AC-5a)."""
    by_day: dict[str, dict[str, dict]] = {}
    bulletin_date: Optional[date] = None
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        for name in zf.namelist():
            base = name.rsplit("/", 1)[-1]
            match = _FILENAME_RE.search(base)
            if not match:
                continue
            day_kind = match.group(3).lower()
            bulletin_date = datetime.strptime(match.group(1), "%Y%m%d").date()
            by_day[day_kind] = _records_by_zone(_parse_dbf(zf.read(name)))
    if bulletin_date is None or not by_day:
        raise ValueError("dpc: kein today/tomorrow-DBF im Bulletin gefunden")
    return {"bulletin_date": bulletin_date, "by_day": by_day}


def _get_cached_bulletin() -> Optional[dict]:
    def _do_request() -> httpx.Response:
        return httpx.get(DPC_ZIP_URL, timeout=TIMEOUT)

    return warn_egress.cached_fetch(
        cache=_cache, cache_key=_CACHE_KEY, service="dpc",
        host="raw.githubusercontent.com", request_fn=_do_request,
        parse_fn=_parse_bulletin_zip, log=logger,
        success_ttl=CACHE_TTL, failure_ttl=FAILURE_CACHE_TTL,
    )


def _select_day_records(bulletin: dict) -> Optional[dict[str, dict]]:
    """AC-3: Bezugstag aus dem Dateinamen-Zeitstempel ableiten, NIE blind
    'today' als 'heute' interpretieren."""
    now_date = _NOW_FN().date()
    bulletin_date = bulletin["bulletin_date"]
    if now_date == bulletin_date:
        return bulletin["by_day"].get("today")
    if now_date == bulletin_date + timedelta(days=1):
        return bulletin["by_day"].get("tomorrow")
    return None  # Bulletin ist aelter als "gestern" -- kein gueltiger Bezugstag mehr


def _level_from_text(text: str) -> Optional[int]:
    """Muster ``<Kritikalitaet> / ALLERTA <FARBE>``. 'NESSUNA ALLERTA' und
    jedes andere abweichende Muster liefern None (AC-5b: keine erfundene
    Warnung bei unbekanntem Freitext)."""
    match = _LEVEL_RE.search(text or "")
    if not match:
        return None
    return _LEVEL_MAP.get(match.group(1).upper())


def _alerts_for_zone(row: dict) -> list[OfficialAlert]:
    """Temporali -> thunderstorm; Idrogeo UND Idraulico -> flood (hoehere der
    beiden Stufen), Implementation Details Punkt 6/7."""
    alerts: list[OfficialAlert] = []
    zone_name = row.get("Nome_zona") or row.get("Zona_all", "")

    thunder_level = _level_from_text(row.get("Temporali", ""))
    if thunder_level:
        alerts.append(OfficialAlert(
            source="dpc", hazard="thunderstorm", level=thunder_level,
            label="Gewitter", region_label=zone_name,
        ))

    flood_levels = [
        lvl for lvl in (
            _level_from_text(row.get("Idrogeo", "")),
            _level_from_text(row.get("Idraulico", "")),
        ) if lvl is not None
    ]
    if flood_levels:
        alerts.append(OfficialAlert(
            source="dpc", hazard="flood", level=max(flood_levels),
            label="Hochwasser/Erdrutsch", region_label=zone_name,
        ))
    return alerts


class DpcSource:
    """Italienischer Zivilschutz -- additive Quelle fuer die Official-Alerts-
    Registry (#1427 S2), erfuellt ``OfficialAlertSource`` (base.py:24)."""

    @property
    def name(self) -> str:
        return "dpc"

    def covers(self, lat: float, lon: float) -> bool:
        """Grober Italien-Bbox-Vorfilter (kein Netzabruf) -- die feine
        Zonen-Zuordnung laeuft erst in ``fetch()``."""
        return (
            _ITALY_RADAR_LAT_MIN <= lat <= _ITALY_RADAR_LAT_MAX
            and _ITALY_RADAR_LON_MIN <= lon <= _ITALY_RADAR_LON_MAX
        )

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        zone_code = _zone_at(lat, lon)
        if zone_code is None:
            return []
        bulletin = _get_cached_bulletin()
        if bulletin is None:
            return []
        day_records = _select_day_records(bulletin)
        if not day_records:
            return []
        row = day_records.get(zone_code)
        if row is None:
            # Issue #1434 Pfad B: die eingecheckte Geometrie kennt die Zone,
            # das tagesaktuelle Bulletin fuehrt sie aber nicht mehr (Zonen-
            # Neuschnitt-Verdacht) -- das ist KEIN "keine Warnung", sondern
            # "fuer diesen Ort nicht abrufbar". Markiert den Abruf ueber den
            # bereits vorhandenen Haken als unvollstaendig; die Wirkung
            # (unavailable=True) entsteht in
            # base.py::get_official_alerts_with_status() ueber den
            # observe_fetch_failure()-Kontext -- kein neuer Mechanismus, kein
            # Raise (ADR-0018 Fail-soft). has_warning=True: ob die fehlende
            # Zeile eine Warnstufe getragen haette, ist unbekannt -- ein
            # fehlender Bulletin-Eintrag ist nachweislich eine Anomalie
            # (Spec Messung 2026-07-31), daher bewusst konservativ als
            # relevant markiert statt als Rauschen kleingerechnet.
            warn_egress.mark_fetch_incomplete()
            warn_egress.log_zone_drift("dpc", zone_code, True, "geometry_only")
            return []
        return _alerts_for_zone(row)
