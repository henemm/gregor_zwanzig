"""MeteoAlarmFeedSource — kontingentfreier CAP-Feed fuer Italien+Oesterreich
(Issue #1445 S1/S3).

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
from typing import Literal, Optional

import httpx

from services.official_alerts import geosphere_warn, warn_egress
from services.official_alerts.department_mapper import lookup_department
from services.official_alerts.dpc import _zone_at
from services.official_alerts.meteoalarm import _group_and_map_info_entries
from services.official_alerts.models import OfficialAlert
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
}
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


def _info_entries_from_alert(alert: dict) -> list[dict]:
    """Baut aus einem Feed-``alert``-Objekt (``info[]``) dieselbe normalisierte
    Info-Struktur wie ``meteoalarm._collect_cap_info_entries`` fuer den
    XML-Weg -- Voraussetzung fuer die geteilte Gruppieren/Mappen-Funktion."""
    entries: list[dict] = []
    for info in alert.get("info") or []:
        params = {p.get("valueName"): p.get("value") for p in info.get("parameter") or []}
        areas = info.get("area") or []
        area_desc = areas[0].get("areaDesc") if areas else None
        entries.append({
            "lang": info.get("language") or "",
            "event": info.get("event"),
            "headline": info.get("headline"),
            "onset": info.get("onset"),
            "expires": info.get("expires"),
            "area_desc": area_desc,
            "level_raw": params.get("awareness_level"),
            "type_raw": params.get("awareness_type"),
        })
    return entries


def _emma_ids_for_alert(alert: dict) -> set[str]:
    """Alle EMMA-Zonen-IDs, die dieser Warnung zugeordnet sind (ueber jeden
    ``info[].area[].geocode[]`` mit ``valueName == "EMMA_ID"``)."""
    ids: set[str] = set()
    for info in alert.get("info") or []:
        for area in info.get("area") or []:
            for geocode in area.get("geocode") or []:
                if geocode.get("valueName") == "EMMA_ID" and geocode.get("value"):
                    ids.add(geocode["value"])
    return ids


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


def _alerts_for_zone(feed: dict, zone: str) -> list[OfficialAlert]:
    """Wertet eine Feed-Momentaufnahme fuer EINE Zone aus -- geteilter
    Malformations-/Reihenfolge-Schutz (F003/F005 aus S1) fuer BEIDE Laender,
    EIN Codepfad (S3 Implementation Details Punkt 2, letzter Absatz)."""
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
            emma_ids = _emma_ids_for_alert(alert)
            if emma_ids:
                if zone in emma_ids:
                    alerts.extend(
                        _group_and_map_info_entries(_info_entries_from_alert(alert))
                    )
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


class MeteoAlarmFeedSource:
    """Feed-Bestandsquelle Italien+Oesterreich (#1445 S1/S3) -- erfuellt
    ``OfficialAlertSource`` (base.py:24). ``OfficialAlert.source`` bleibt
    ``"meteoalarm"`` (Spec Implementation Details Punkt 8): nur der interne
    Abrufweg aendert sich. Ein Code, zwei Instanzen ueber den
    Konstruktor-Parameter ``country``."""

    def __init__(self, country: Literal["IT", "AT"]) -> None:
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
        if lookup_department(lat, lon) is not None:
            return False
        return _zone_for_point(lat, lon) is not None

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
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
        return _alerts_for_zone(feed, zone)
