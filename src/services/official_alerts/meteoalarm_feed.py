"""MeteoAlarmFeedSource — kontingentfreier CAP-Feed fuer Italien, Oesterreich
und Deutschland (Issue #1445 S1/S3, #1681).

Ersetzt den kontingentierten EDR-Index-Weg (``meteoalarm.py``) durch
``feeds.meteoalarm.org`` -- eine Momentaufnahme ALLER aktuell gueltigen
Warnungen des jeweiligen Landes mit vollem CAP-Inhalt in einem einzigen,
unauthentifizierten Abruf. Ein Code, zwei Instanzen ueber den Konstruktor-
Parameter ``country`` (Implementation Details Punkt 1 der S3-Spec):
``MeteoAlarmFeedSource("IT")`` / ``MeteoAlarmFeedSource("AT")``.

Der CAP-Mapper wird NICHT nachgebaut: ``meteoalarm._group_and_map_info_entries``
(formatunabhaengige Haelfte des ehemaligen ``_extract_alerts_from_cap``) wird
aus dem hier gebauten JSON-Normalform aufgerufen -- identische Filterregeln fuer
beide Sammelwege UND beide Laender.

Oesterreichs Punkt->Zone-Aufloesung (``_zone_for_point_at``) braucht -- anders
als Italiens reine Geometrie-Funktion ``_zone_for_point`` -- drei Zustaende
statt zwei: sie nutzt die ohnehin gecachte ZAMG-Antwort
(``geosphere_warn._get_cached_warnings``) weiter und muss "nicht zustaendig"
(ZAMG 404) von einem echten Fetch-Fehlschlag unterscheiden (S3 Implementation
Details Punkt 2).

SPEC: docs/specs/modules/feat_1445_s1_feed_bestandsquelle.md, AC-1..AC-7
SPEC: docs/specs/modules/feat_1445_s3_oesterreich_feed.md, AC-1..AC-8
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Literal, Optional

import httpx

from services.official_alerts import dwd_zones, geosphere_warn, warn_egress
from services.official_alerts.department_mapper import lookup_department
from services.official_alerts.dpc import _zone_at
from services.official_alerts.geo_ray_cast import _point_in_ring
from services.official_alerts.meteoalarm import _group_and_map_info_entries
from services.official_alerts.models import OfficialAlert
from services.official_alerts.region_mapper import RegionMapper
from services.official_alerts.slf import REGIONS_FILE as _SLF_REGIONS_FILE
from services.radar_service import (
    _INCA_LAT_MAX,
    _INCA_LAT_MIN,
    _INCA_LON_MAX,
    _INCA_LON_MIN,
)

logger = logging.getLogger("meteoalarm_feed")

# Analog meteoalarm.METEOALARM_BASE_URL -- von Tests umlenkbar (lokaler Server).
# EIN gemeinsames Modul-Attribut fuer beide Laender (Produktion: ein Host,
# zwei Pfade, s. _FEED_PATHS).
FEED_BASE_URL = "https://feeds.meteoalarm.org"
_FEED_PATHS: dict[str, str] = {
    "IT": "/api/v1/warnings/feeds-italy",
    "AT": "/api/v1/warnings/feeds-austria",
    "DE": "/api/v1/warnings/feeds-germany",
    # Issue #1442 S1/S2: ohne Geocode -- Zuordnung per Punkt-in-Polygon.
    "CH": "/api/v1/warnings/feeds-switzerland",
    "NO": "/api/v1/warnings/feeds-norway",
    "SE": "/api/v1/warnings/feeds-sweden",
    # Issue #1442 S2: nur EMMA_ID, Zonengeometrie eingecheckt (data/README.md).
    "FI": "/api/v1/warnings/feeds-finland",
}
# Issue #1681: Geocode-Art je Land -- DE ordnet ueber die DWD-``WARNCELLID``
# zu (1:1 im Feed, traegt die eingecheckte Kreisgeometrie), IT/AT/FI ueber EMMA.
_GEOCODE_NAME: dict[str, str] = {
    "IT": "EMMA_ID", "AT": "EMMA_ID", "DE": "WARNCELLID", "FI": "EMMA_ID",
}
# Kuesten-/Seezellen (Praefix 501) liegen bewusst nicht in der Kreisgeometrie.
_DE_COAST_PREFIX = "501"
TIMEOUT = 15.0  # ~1,4-2,4 MB, kein gzip (Spec Antrag) -- grosszuegiger als schlanke JSON-Quellen
# Modul-Cache, Konvention analog dpc._cache -- SCHLUESSEL ist der Laender-Code
# (S3 Implementation Details Punkt 1): ein AT-Abruf und ein IT-Abruf bleiben
# zwei unabhaengige Cache-Eintraege, keine gegenseitige Invalidierung.
_cache: dict = {}

# Spec Implementation Details Punkt 3: aus dem echten Feed-Datensatz extrahiert
# und gegen alle 187 dpc-Zonencodes verifiziert (volle Herleitung in
# tests/fixtures/meteoalarm_feed/README.md).
_REGION_PREFIX_TO_EMMA: dict[str, str] = {
    "Cala": "IT001", "Tren": "IT002", "Lomb": "IT003", "VDAo": "IT004",
    "Piem": "IT005", "Vene": "IT006", "Ligu": "IT007", "Emil": "IT008",
    "Tosc": "IT009", "Umbr": "IT010", "Marc": "IT011", "Lazi": "IT012",
    "Abru": "IT013", "Moli": "IT014", "Pugl": "IT015", "Camp": "IT016",
    "Basi": "IT017", "Sici": "IT018", "Sard": "IT019", "Friu": "IT020",
}


def _zone_for_point(lat: float, lon: float) -> Optional[str]:
    """Punkt -> EMMA-Zonen-ID ueber die eingecheckte DPC-Geometrie
    (``dpc._zone_at``) plus Regions-Praefix-Tabelle. ``None``, wenn der
    Punkt keiner der 187 DPC-Zonen zugeordnet werden kann (Spec
    Implementation Details Punkt 4: bewusst kein Kilometer-Rueckfall)."""
    zone_code = _zone_at(lat, lon)
    if zone_code is None:
        return None
    prefix = zone_code.split("-", 1)[0]
    return _REGION_PREFIX_TO_EMMA.get(prefix)


def _zone_for_point_de(lat: float, lon: float) -> Optional[str]:
    """Punkt -> DWD-``WARNCELLID`` ueber die eingecheckte Kreisgeometrie
    (Issue #1681). EINE Funktion fuer ``covers()`` UND ``fetch()`` (Spec
    Implementation Details Punkt 2) -- ``None`` heisst "nicht in Deutschland"
    (bzw. Kuesten-/Seegebiet), also nicht zustaendig."""
    return dwd_zones.warncell_at(lat, lon)


def _ist_auswertbare_gemeindenr(gemeindenr: object) -> bool:
    """Formprüfung VOR der Zonen-Ableitung (Adversary-Fund F1, Issue #1445
    S3 Fix-Loop): ``str(gemeindenr)`` muss rein numerisch UND mindestens
    dreistellig sein, sonst kann keine sinnvolle dreistellige EMMA-Zone
    daraus geschnitten werden (``""`` -> ``"AT"``, ``0`` -> ``"AT0"``,
    ``"12"`` -> ``"AT12"`` -- keine dieser Zonen matcht je einen echten
    fünfstelligen EMMA-Code).

    Adversary-Fund F3 (Fix-Loop): ``str.isdigit()`` allein akzeptiert auch
    Nicht-ASCII-Ziffern (arabisch-indisch, hochgestellt etc.) -- die live
    ankommende ``gemeindenr`` ist immer eine JSON-Zahl (also ASCII), aber die
    Prüfung soll halten, was sie verspricht. ``str.isascii()`` verschärft
    zusätzlich."""
    text = str(gemeindenr)
    return text.isascii() and text.isdigit() and len(text) >= 3


def _zone_for_point_at(lat: float, lon: float) -> tuple[Optional[str], bool]:
    """Punkt -> EMMA-Zonen-ID fuer Oesterreich, DREI Zustaende statt zwei
    (S3 Implementation Details Punkt 2) -- nutzt die ohnehin gecachte ZAMG-
    Antwort weiter (``geosphere_warn._get_cached_warnings``), kein eigener
    Netzabruf:

    - ZAMG-Abruf real fehlgeschlagen (``None``) -> ``(None, True)``
      (Fall 2, "ich weiss es nicht").
    - ZAMG antwortet "nicht zustaendig" (404, ueber ``not_covered_statuses``
      als ``{}`` gecacht) ODER liefert ein Dict OHNE das Feld ``gemeindenr``
      ODER liefert ``gemeindenr: null`` -> ``(None, False)`` (Fall 1, "hier
      gelten keine oesterreichischen Warnungen") -- das Feld fehlt hier
      strukturell, das ist keine kaputte Antwort.
    - ZAMG liefert ein VORHANDENES ``gemeindenr``, dessen Form aber
      unbrauchbar ist (Adversary-Fund F1, Issue #1445 S3 Fix-Loop:
      ``str(gemeindenr)`` nicht rein numerisch oder kuerzer als drei
      Zeichen, z.B. ``""``, ``0``, ``"12"``) -> ``(None, True)``, DENSELBEN
      Sicherheits-Rueckzug wie Fall 2. Begruendung: ein vorhandener, aber
      unbrauchbar geformter Wert ist ein DATENFEHLER, kein "hier gilt
      nichts" -- Fall 1 zu waehlen wuerde eine defekte Antwort als "hier
      gelten keine Warnungen" tarnen und echte Warnungen geraeuschlos
      verschwinden lassen (gemessen: Sillian/Karnischer Hoehenweg verliert
      dabei fuenf aktive Warnungen spurlos). Dieselbe Abwaegung wie bei den
      Findings der Schwesterscheibe S1 (F001/F003/F005): ein unauswertbarer,
      aber VORHANDENER Wert zaehlt als Fehlschlag, nicht als stille Leere.
    - ZAMG liefert eine formgueltige ``gemeindenr`` -> ``(zone, False)``
      (Fall 3), EMMA-Zone = ``"AT" + str(gemeindenr)[:3]`` -- ``gemeindenr``
      kommt real als Ganzzahl, NICHT als String (live verifiziert
      2026-08-01)."""
    data = geosphere_warn._get_cached_warnings(lat, lon)
    if data is None:
        return None, True
    try:
        gemeindenr = data["properties"]["location"]["properties"]["gemeindenr"]
    except (KeyError, TypeError):
        return None, False
    if gemeindenr is None:
        return None, False
    if not _ist_auswertbare_gemeindenr(gemeindenr):
        return None, True
    return "AT" + str(gemeindenr)[:3], False


def _area_desc(areas: list, zone: Optional[str], geocode_name: str) -> Optional[str]:
    """``areaDesc`` des Gebiets, dessen Geocode die abgefragte Zone ist --
    ein DE-Alert nennt oft mehrere Kreise; ohne ``zone`` (IT/AT, unveraendert)
    das erste Gebiet."""
    if not areas:
        return None
    if zone is not None:
        for area in areas:
            if any(g.get("valueName") == geocode_name and str(g.get("value")) == zone
                   for g in area.get("geocode") or []):
                return area.get("areaDesc")
    return areas[0].get("areaDesc")


def _info_entries_from_alert(
    alert: dict, zone: Optional[str] = None, geocode_name: str = "EMMA_ID",
) -> list[dict]:
    """Baut aus einem Feed-``alert``-Objekt (``info[]``) dieselbe normalisierte
    Info-Struktur wie ``meteoalarm._collect_cap_info_entries`` fuer den
    XML-Weg -- Voraussetzung fuer die geteilte Gruppieren/Mappen-Funktion.
    Issue #1681: ``responseType`` wird mitgefuehrt (AllClear-Filter im
    geteilten Umsetzer)."""
    entries: list[dict] = []
    for info in alert.get("info") or []:
        params = {p.get("valueName"): p.get("value") for p in info.get("parameter") or []}
        area_desc = _area_desc(info.get("area") or [], zone, geocode_name)
        entries.append({
            "lang": info.get("language") or "",
            "event": info.get("event"),
            "headline": info.get("headline"),
            "onset": info.get("onset"),
            "expires": info.get("expires"),
            "area_desc": area_desc,
            "level_raw": params.get("awareness_level"),
            "type_raw": params.get("awareness_type"),
            "response_type": info.get("responseType"),
        })
    return entries


def _emma_ids_for_alert(alert: dict, geocode_name: str = "EMMA_ID") -> set[str]:
    """Alle Zonen-IDs, die dieser Warnung zugeordnet sind (ueber jeden
    ``info[].area[].geocode[]`` mit ``valueName == geocode_name``; Issue
    #1681: ``WARNCELLID`` fuer DE, sonst ``EMMA_ID``)."""
    ids: set[str] = set()
    for info in alert.get("info") or []:
        for area in info.get("area") or []:
            for geocode in area.get("geocode") or []:
                if geocode.get("valueName") == geocode_name and geocode.get("value"):
                    ids.add(str(geocode["value"]))
    return ids


_drift_checked: dict = {}


def _log_unknown_zone_drift(
    feed: dict, country: str, known: "set[str] | frozenset[str]", drift: str,
    ignore_prefix: Optional[str] = None,
) -> None:
    """Drift-Waechter (Issue #1681 AC-9, #1442 S2): jede Zonen-ID im Feed, die
    nicht in der eingecheckten Geometrie liegt (DE: ausser Kuestenzellen
    ``501...``), landet im Warn-Dienst-Journal. Laeuft auf dem Auswertungspfad
    (auch bei Cache-Treffer). Kein Ausfall-Signal. Einmal je Land und
    Feed-Momentaufnahme, nicht je Wegpunkt (sonst flutet ein Trip mit N
    Punkten das Journal N-fach)."""
    if _drift_checked.get(country) is feed:  # Referenz statt id(): keine Wiederverwendung
        return
    _drift_checked[country] = feed
    for warning in feed.get("warnings") or []:
        alert = warning.get("alert") if isinstance(warning, dict) else None
        if not isinstance(alert, dict) or not isinstance(alert.get("info"), list):
            continue
        for cell in _emma_ids_for_alert(alert, _GEOCODE_NAME[country]):
            if cell not in known and not (ignore_prefix and cell.startswith(ignore_prefix)):
                warn_egress.log_zone_drift(f"meteoalarm_feed:{country}", cell, True, drift)


def _parse_feed(resp: httpx.Response) -> dict:
    """Parst die Feed-Antwort UND verlangt einen strukturell gueltigen
    ``"warnings"``-Listen-Schluessel (Adversary-Fund F001, Issue #1445 S1
    Fix-Loop): syntaktisch gueltiges JSON ohne diesen Schluessel (z.B. ``{}``)
    oder mit falschem Typ (``null``, Objekt, String statt Liste) besteht die
    reine ``isinstance(data, dict)``-Pruefung, waere aber inhaltlich eine
    kaputte Antwort -- ohne diese zusaetzliche Pruefung wuerde ``fetch()`` sie
    still als "keine Warnung" statt "nicht abrufbar" auswerten. Ein
    tatsaechlich LEERES ``{"warnings": []}`` ist dagegen eine gueltige
    fachliche Aussage ("derzeit keine Warnungen") und bleibt Erfolg."""
    data = resp.json()
    if not isinstance(data, dict):
        raise ValueError(f"Feed-Antwort ist kein Objekt (type={type(data).__name__})")
    warnings = data.get("warnings")
    if not isinstance(warnings, list):
        raise ValueError(
            f"Feed-Antwort hat keinen gueltigen 'warnings'-Listen-Schluessel "
            f"(erhalten: {warnings!r})"
        )
    return data


def _get_cached_feed(country: str) -> Optional[dict]:
    """TTL-gecachter Feed-Abruf ueber ``warn_egress.cached_fetch()`` -- ein
    Cache-Treffer innerhalb der (default) Erfolgs-TTL loest keinen Netz-Call
    aus (AC-2/AC-4). Ein nationaler Abruf deckt alle Zonen des jeweiligen
    Landes ab -- der Cache-Schluessel ist der Laender-Code selbst, damit AT
    und IT zwei unabhaengige Eintraege bleiben (S3 Implementation Details
    Punkt 1)."""
    def _do_request() -> httpx.Response:
        return httpx.get(f"{FEED_BASE_URL}{_FEED_PATHS[country]}", timeout=TIMEOUT)

    return warn_egress.cached_fetch(
        cache=_cache, cache_key=country, service=f"meteoalarm_feed:{country}",
        host="feeds.meteoalarm.org", request_fn=_do_request,
        parse_fn=_parse_feed, log=logger,
    )


def _alerts_for_zone(
    feed: dict, zone: "str | set[str]", country: str = "IT",
) -> list[OfficialAlert]:
    """Wertet eine Feed-Momentaufnahme fuer EINE Zone aus -- geteilter
    Malformations-/Reihenfolge-Schutz (F003/F005 aus S1) fuer BEIDE Laender,
    EIN Codepfad (S3 Implementation Details Punkt 2, letzter Absatz).
    Issue #1442 S2: FI uebergibt eine Zonen-MENGE (Kuestenort liegt in Land-
    UND Seezone); jede Warnung zaehlt trotzdem nur einmal."""
    zones = {zone} if isinstance(zone, str) else zone
    alerts: list[OfficialAlert] = []
    for warning in feed.get("warnings") or []:
        alert = warning.get("alert") or {}
        info = alert.get("info")
        info_is_list = isinstance(info, list)

        # Adversary-Fund F005 (Fix-Loop 3): Zonenzugehoerigkeit MUSS vor
        # der Malformations-Pruefung entschieden werden. Der nationale
        # Feed traegt taeglich hunderte Eintraege -- ein einzelner
        # andersfoermiger Eintrag irgendwo im Land darf nicht JEDE
        # Ortsabfrage als "nicht abrufbar" einfaerben, wenn der abgefragte
        # Ort seine vollstaendige, korrekte Warnung bekommt. Ist "info" eine
        # Liste, koennen wir die betroffenen Zonen unabhaengig von sonstiger
        # Malformation ermitteln.
        if info_is_list:
            geocode_name = _GEOCODE_NAME.get(country, "EMMA_ID")
            emma_ids = _emma_ids_for_alert(alert, geocode_name)
            if emma_ids:
                if emma_ids & zones:
                    # DE: areaDesc des abgefragten Kreises (mehrere je Alert).
                    area_zone = zone if country == "DE" else None
                    alerts.extend(_group_and_map_info_entries(
                        _info_entries_from_alert(alert, area_zone, geocode_name)
                    ))
                # sonst: nachweislich eine ANDERE Zone -- geht uns nichts an.
                continue
            # info ist eine Liste, traegt aber KEIN einziges Geocode --
            # Zonenzugehoerigkeit bleibt trotz vorhandener Struktur
            # unbestimmbar, faellt unten in die Abwaegung.

        # Ab hier ist die Zonenzugehoerigkeit NICHT bestimmbar (entweder
        # "info" ist keine Liste, oder eine Liste ohne jedes Geocode).
        # CAP-Konvention: ein Rueckzug (msgType "Cancel") traegt
        # regelkonform KEIN info[] -- kein Datenfehler, kein Fehlschlag.
        # Ein Rueckzug enthaelt keine Warn-Information und traegt nichts
        # zum Ergebnis bei.
        if not info_is_list and alert.get("msgType") == "Cancel":
            continue

        # Weder einer Zone zuordenbar noch als legitimer Rueckzug
        # erkennbar (Adversary-Fund F003, Fix-Loop 2, weiterhin gueltig):
        # dieser Zweig erreicht NUR Eintraege ohne jede auswertbare
        # Zonenangabe -- der haeufige Fall (andersfoermiger, aber klar
        # zuordenbarer Eintrag) wird bereits oben abgefangen. Abwaegung
        # (F005): "lieber einmal zu viel gewarnt" gewinnt hier gegen
        # "der Waechter wird unbrauchbar", weil dieser Rest-Zweig selten
        # bleibt statt wie vor dem Fix bei JEDEM Feed mit irgendeinem
        # andersfoermigen Eintrag anzuschlagen.
        warn_egress.log_zone_drift(
            "meteoalarm_feed", None, True, "broken_warning_entry",
        )
        warn_egress.mark_fetch_incomplete()
    return alerts


# ── CH/NO/SE (Issue #1442 S1/S2): Punkt-in-Polygon statt Geocode ─────────────
# Lokale Zustaendigkeit ohne Netz: CH ueber die SLF-Regionspolygone, NO/SE ueber
# bewusst aufgeweitete Landesumrisse (Natural Earth, data/README.md).
_DATA_DIR = Path(__file__).resolve().parent / "data"
_ch_regions = RegionMapper(_SLF_REGIONS_FILE)
_nordic_outlines = RegionMapper(_DATA_DIR / "meteoalarm_outlines_nordics.geojson.json")
_POLYGON_COUNTRIES = ("CH", "NO", "SE")
# FI (Issue #1442 S2): EMMA_ID-Zonengeometrie aus MeteoAlarm-geocodes.json.
_fi_zones = RegionMapper(_DATA_DIR / "meteoalarm_zones_FI.geojson.json")
# Ausgewerteter Feed (BBoxen, Ringe, Rueckzuege) je Land und Momentaufnahme --
# haengt per Objekt-Referenz am gecachten Feed und lebt dessen 30-min-TTL mit.
_polygon_index_memo: dict = {}


def _parse_ring(text: object) -> Optional[list[tuple[float, float]]]:
    """CAP-Ring ``"lat,lon lat,lon ..."`` -> ``[(lon, lat), ...]`` (Reihenfolge
    von ``_point_in_ring``); unlesbar oder < 3 Punkte -> ``None``."""
    try:
        ring = [(float(lon), float(lat))
                for lat, lon in (pair.split(",") for pair in str(text).split())]
    except ValueError:
        return None
    return ring if len(ring) >= 3 else None


def _area_index(area: object) -> Optional[tuple]:
    """``(areaDesc, bbox, rings)`` eines Gebiets; ``None`` ohne lesbaren Ring."""
    if not isinstance(area, dict) or not isinstance(area.get("polygon"), list):
        return None
    rings = [r for r in (_parse_ring(t) for t in area["polygon"]) if r]
    if not rings:
        return None
    lons = [p[0] for r in rings for p in r]
    lats = [p[1] for r in rings for p in r]
    return area.get("areaDesc"), (min(lons), min(lats), max(lons), max(lats)), rings


def _referenced_ids(alert: dict) -> set[str]:
    """CAP ``references`` (``"sender,identifier,sent ..."``) -> Kennungen."""
    parts = (ref.split(",") for ref in str(alert.get("references") or "").split())
    return {p[1] for p in parts if len(p) >= 2}


def _alert_areas(alert: dict, country: str) -> list[tuple]:
    """Alle lesbaren Gebiete eines Alerts; gleiche Polygone der Sprachbloecke
    werden nur einmal gerechnet. Unlesbares Polygon -> Journal, kein Ausfall
    (AC-9: faerbt keine anderen Orte ein)."""
    seen: set = set()
    areas: list[tuple] = []
    for info in alert["info"]:
        for area in (info.get("area") or []) if isinstance(info, dict) else []:
            key = repr(area.get("polygon")) if isinstance(area, dict) else None
            if key in seen:
                continue
            seen.add(key)
            indexed = _area_index(area)
            if indexed is None:
                warn_egress.log_zone_drift(f"meteoalarm_feed:{country}", None, True,
                                           "broken_polygon")
            else:
                areas.append(indexed)
    return areas


def _polygon_index(feed: dict, country: str) -> dict:
    """Wertet den Feed EINMAL je Land und Momentaufnahme aus (BBox-Vorfilter)."""
    memo = _polygon_index_memo.get(country)  # EIN Eintrag je Land: kein Paar-Race
    if memo is not None and memo[0] is feed:  # Referenz statt id(): keine Wiederverwendung
        return memo[1]
    entries: list[tuple] = []
    superseded: set[str] = set()
    broken = 0
    for warning in feed.get("warnings") or []:
        alert = warning.get("alert") if isinstance(warning, dict) else None
        if isinstance(alert, dict) and alert.get("msgType") == "Cancel":
            # Rueckzug: hebt nur auf, ist NIE selbst eine Warnung (auch mit info[]).
            superseded |= _referenced_ids(alert)
            continue
        if not isinstance(alert, dict) or not isinstance(alert.get("info"), list):
            # Nicht zuordenbar: nur Journal, KEIN Ausfall (Spec Punkt 5 -- ein
            # einzelner Eintrag irgendwo im Land faerbt nicht jede Ortsabfrage ein).
            broken += 1
            warn_egress.log_zone_drift(f"meteoalarm_feed:{country}", None, True,
                                       "broken_warning_entry")
            continue
        if alert.get("msgType") == "Update":
            superseded |= _referenced_ids(alert)
        areas = _alert_areas(alert, country)
        if areas:
            entries.append((alert, areas))
        else:
            broken += 1
    # Spec Punkt 4: kaputte Eintraege OHNE einen einzigen verwertbaren -> unlesbar.
    # Cancel ist neutral; ein leerer Feed bleibt "keine Warnung".
    index = {"entries": entries, "superseded": superseded, "unreadable": broken > 0 and not entries}
    _polygon_index_memo[country] = (feed, index)
    return index


def _hit_area(areas: list[tuple], lat: float, lon: float) -> Optional[tuple]:
    """Erstes Gebiet, das den Punkt enthaelt. Gerade-Ungerade-Regel ueber alle
    Ringe: Punkt im Aussenring und nicht im Loch; disjunkte Mehrfachringe."""
    for area in areas:
        x0, y0, x1, y1 = area[1]
        if x0 <= lon <= x1 and y0 <= lat <= y1 \
                and sum(_point_in_ring(lat, lon, ring) for ring in area[2]) % 2 == 1:
            return area
    return None


def _alerts_for_point_polygon(
    feed: dict, lat: float, lon: float, country: str,
) -> list[OfficialAlert]:
    """CH/NO/SE-Gegenstueck zu ``_alerts_for_zone``: Punkt-in-Polygon gegen die
    Feed-Gebiete; per ``Update``/``Cancel`` ersetzte Warnungen entfallen,
    Hoehenband (``altitude``/``ceiling``) wird bewusst ignoriert."""
    index = _polygon_index(feed, country)
    if index["unreadable"]:
        warn_egress.mark_fetch_incomplete()
        return []
    alerts: list[OfficialAlert] = []
    for alert, areas in index["entries"]:
        if alert.get("identifier") in index["superseded"]:
            continue
        hit = _hit_area(areas, lat, lon)
        if hit is None:
            continue
        entries = _info_entries_from_alert(alert)
        for entry in entries:
            entry["area_desc"] = hit[0]
        alerts.extend(_group_and_map_info_entries(entries))
    return alerts


def _cached_feed_without_network(country: str) -> Optional[dict]:
    """Frischer Feed des Landes aus dem Modul-Cache oder ``None`` -- nie ein Abruf."""
    entry = _cache.get(country)
    if not warn_egress._is_fresh(entry, time.monotonic()):
        return None
    return entry.get("data")


def _in_outline(country: str, lat: float, lon: float) -> bool:
    """CH: SLF-Regionen; NO/SE: aufgeweiteter Landesumriss (lieber zu gross)."""
    if country == "CH":
        return bool(_ch_regions.regions_at(lat, lon))
    return country in _nordic_outlines.regions_at(lat, lon)


def _covers_polygon(country: str, lat: float, lon: float) -> bool:
    """Lokaler Umriss, sonst Fallback: Punkt in einem gecachten Feed-Polygon."""
    if _in_outline(country, lat, lon):
        return True
    feed = _cached_feed_without_network(country)
    if not isinstance(feed, dict):
        return False
    entries = _polygon_index(feed, country)["entries"]
    return any(_hit_area(areas, lat, lon) for _alert, areas in entries)


def _zones_for_point_fi(lat: float, lon: float) -> set[str]:
    """Punkt -> ALLE getroffenen FI-``EMMA_ID`` (Kuestenort: Land- UND Seezone)."""
    return set(_fi_zones.regions_at(lat, lon))


def _fi_known_zones() -> set[str]:
    return {region_id for region_id, _geo, _box in _fi_zones._loaded()}


class MeteoAlarmFeedSource:
    """Feed-Bestandsquelle Italien+Oesterreich (#1445 S1/S3) -- erfuellt
    ``OfficialAlertSource`` (base.py:24). ``OfficialAlert.source`` bleibt
    ``"meteoalarm"`` (Spec Implementation Details Punkt 8): nur der interne
    Abrufweg aendert sich. Ein Code, eine Instanz je Land ueber den
    Konstruktor-Parameter ``country`` (IT/AT/DE/FI Zonenweg, CH/NO/SE
    Punkt-in-Polygon, Issue #1442 S1/S2)."""

    def __init__(
        self, country: Literal["IT", "AT", "DE", "CH", "NO", "SE", "FI"],
    ) -> None:
        self.country = country

    @property
    def name(self) -> str:
        return "meteoalarm_feed"

    def covers(self, lat: float, lon: float) -> bool:
        """Zustaendigkeits-Vorfilter, rein lokal (kein Netzabruf, wie
        DpcSource).

        AT (S3 Implementation Details Punkt 5): INCA-Bbox reicht, KEIN
        Grenz-Ausschluss noetig -- ein Punkt innerhalb der Bbox, aber real
        ausserhalb Oesterreichs, wird bereits ueber ``_zone_for_point_at()``
        Fall 1 (ZAMG 404) sauber als "nicht zustaendig" behandelt, ohne
        einen Ausfallhinweis auszuloesen.

        IT (SPEC: docs/specs/modules/fix_1397_s4_it_grenze.md): ECHTE
        ZONEN-GEOMETRIE statt der groben DPC-Radar-Bbox -- Vorbild
        ``massif_closure.covers()``. Die Bbox (lat 36,0-47,5 / lon 6,5-19,0)
        enthaelt weite Teile Oesterreichs, der Schweiz, Sloweniens und
        Kroatiens; ein Punkt dort galt als zustaendig, fand in ``fetch()``
        keine Zone und loeste ueber ``mark_fetch_incomplete()`` einen falschen
        "nicht abrufbar"-Hinweis aus (Prod: 39 Punkte EINER Tour, fortlaufend).
        ``_zone_for_point()`` ist dieselbe rein lokale Funktion, die ``fetch()``
        ohnehin zur Zonenaufloesung nutzt -- kein Netzabruf, kein neuer Zustand.
        Semantik (Spec "Abwaegung"): nicht zuordenbar => nicht zustaendig =>
        schweigen; real italienische Punkte, die die vereinfachten Polygone
        knapp verfehlen, schweigen mit -- geometrisch nicht unterscheidbar
        (Known Limitation). Die franzoesische Ausnahme bleibt EIGENER,
        expliziter Schritt (S4 Punkt 2, #1397 S2b) und wird NICHT durch die
        Geometrie ersetzt: an der Grenze koennen die Polygone ungenau sein,
        ``lookup_department()`` ist bewaehrt -- beide Pruefungen zusammen sind
        strenger als jede einzelne."""
        if self.country == "AT":
            return _INCA_LAT_MIN <= lat <= _INCA_LAT_MAX and _INCA_LON_MIN <= lon <= _INCA_LON_MAX
        if self.country == "DE":
            # Issue #1681: dieselbe Zonenfunktion wie fetch() -- keine Bbox.
            return _zone_for_point_de(lat, lon) is not None
        if self.country in _POLYGON_COUNTRIES:
            # Issue #1442 S1/S2: lokaler Umriss, Fallback gecachte Feed-Polygone.
            return _covers_polygon(self.country, lat, lon)
        if self.country == "FI":
            # Issue #1442 S2: dieselbe Zonenfunktion wie fetch() (Muster DE).
            return bool(_zones_for_point_fi(lat, lon))
        if lookup_department(lat, lon) is not None:
            return False
        return _zone_for_point(lat, lon) is not None

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        if self.country in _POLYGON_COUNTRIES:
            return self._fetch_polygon(lat, lon)
        if self.country == "FI":
            return self._fetch_fi(lat, lon)
        if self.country == "AT":
            zone, fetch_failed = _zone_for_point_at(lat, lon)
            if fetch_failed:
                # Fall 2 (S3 Implementation Details Punkt 2): ZAMG-Abruf
                # real fehlgeschlagen -- "ich weiss es nicht", NICHT
                # verwechselbar mit Fall 1.
                warn_egress.mark_fetch_incomplete()
                return []
            if zone is None:
                # Fall 1: ZAMG antwortet "nicht zustaendig" (404) -- kein
                # Ausfall, einfach keine oesterreichischen Warnungen hier.
                # Issue #1681: nicht zustaendig => kompensiert keinen Ausfall.
                warn_egress.mark_not_covered()
                return []
        elif self.country == "DE":
            zone = _zone_for_point_de(lat, lon)
            if zone is None:
                # Ausland/See: konsistent mit covers() -- nicht zustaendig,
                # kein Ausfall (AC-4). Ueber die Registry unerreichbar
                # (base.py ruft fetch() nur nach covers() == True mit
                # derselben Zonenfunktion) -- bleibt nur, damit direkte
                # Aufrufe keinen 5-MB-Feedabruf ausloesen; daher bewusst
                # KEIN mark_not_covered() (Adversary F001).
                return []
        else:
            zone = _zone_for_point(lat, lon)
            if zone is None:
                # SICHERHEITSNETZ, KEIN AKTIVER WAECHTER (#1397 S4 Punkt 4):
                # ueber den Registry-Pfad NICHT MEHR ERREICHBAR -- base.py
                # ruft immer erst ``covers()``, das seit S4 mit DERSELBEN
                # Geometrie genau die Punkte ausfiltert, die hier auf ``None``
                # traefen. Wer ihn fuer eine laufende Drift-Ueberwachung haelt,
                # irrt. Er bleibt fuer DIREKTE ``fetch()``-Aufrufe ausserhalb
                # der Registry (Tests, kuenftige Aufrufer) stehen, damit dort
                # keine leere Liste still als "keine Warnung" durchgeht.
                # Unveraendert (S1 Punkt 4): kein Kilometer-Rueckfall.
                warn_egress.log_zone_drift("meteoalarm_feed", None, True, "point_unmapped")
                warn_egress.mark_fetch_incomplete()
                return []
        feed = _get_cached_feed(self.country)
        if feed is None:
            return []
        if self.country == "DE":
            _log_unknown_zone_drift(feed, "DE", dwd_zones.KNOWN_WARNCELLIDS,
                                    "unknown_warncell", _DE_COAST_PREFIX)
        return _alerts_for_zone(feed, zone, self.country)

    def _fetch_polygon(self, lat: float, lon: float) -> list[OfficialAlert]:
        """Drei Zustaende (Spec #1442 S1 Punkt 4, S2 Punkt 5): ausserhalb des
        Landes -> nicht zustaendig; Feed nicht abrufbar -> ``cached_fetch``
        meldet den Ausfall; sonst Treffer oder "keine Warnung"."""
        if not _covers_polygon(self.country, lat, lon):
            warn_egress.mark_not_covered()
            return []
        feed = _get_cached_feed(self.country)
        if feed is None:
            warn_egress.mark_fetch_incomplete()
            return []
        return _alerts_for_point_polygon(feed, lat, lon, self.country)

    def _fetch_fi(self, lat: float, lon: float) -> list[OfficialAlert]:
        """FI (Spec #1442 S2 Punkt 7): Zonenweg ueber ``EMMA_ID`` wie IT/AT/DE;
        keine Zone -> nicht zustaendig; unbekannte Feed-Zonen -> Drift-Journal."""
        zones = _zones_for_point_fi(lat, lon)
        if not zones:
            warn_egress.mark_not_covered()
            return []
        feed = _get_cached_feed("FI")
        if feed is None:
            warn_egress.mark_fetch_incomplete()
            return []
        _log_unknown_zone_drift(feed, "FI", _fi_known_zones(), "unknown_zone")
        return _alerts_for_zone(feed, zones, "FI")
