"""Geteilte Hilfen fuer die SLF-Lawinen-Lagebericht-Tests (Issue #1441 Scheibe S3).

SPEC: docs/specs/modules/feat_1441_s3_slf.md
VORBILD: tests/helpers/avalanche_report_support.py (S1) -- Uhr, Journal-Zeilen, Registry-Reduktion
und Abruf mit Status werden von dort WIEDERVERWENDET, nicht kopiert.

Kein Mock-Theater: ``SlfFixtureTransport`` ist ein ECHTER ``httpx.BaseTransport``, der die
AUFGEZEICHNETEN SLF-Antworten (``tests/fixtures/slf/``, ``GET aws.slf.ch/api/bulletin/caaml/de/json``)
ausliefert und jeden Zugriff zaehlt. Er wird der echten Quelle ueber den Konstruktor-Parameter
``transport`` uebergeben; die Abrufschicht ``warn_egress.cached_fetch`` laeuft unveraendert.
(Bewusst KEIN lokaler ``http.server``: ``--disable-socket`` sperrt auch Loopback.)

Isolation wie in S1: jede Quelle bekommt einen EIGENEN Cache (``cache={}``) und EINE ``FakeClock``
fuer beides -- ``clock`` (Sekunden, Cache-TTL) und ``now_fn`` (Gueltigkeit). Das Warn-Dienst-Journal
lenkt die autouse-Fixture ``_isolate_warn_calls_path`` (``tests/conftest.py``) je Test auf tmp um.

Punkte in Mikroregionen bestimmt ``interior_point`` aus dem Umriss der Fixture-Datei -- mit
eigenem Ray-Cast, damit der Helper nicht vom Pruefling abhaengt.

Alle Importe der zu pruefenden Module (``services.official_alerts.slf``/``caaml``/``base``) stehen
INNERHALB der Funktionen, damit ein fehlendes Modul im RED nur den jeweiligen Test rot macht,
nicht das Sammeln.
"""
from __future__ import annotations

import copy
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional, Union

import httpx

from tests.helpers.avalanche_report_support import (  # noqa: F401  (Wiederverwendung, Re-Export)
    P_MUENCHEN,
    P_TIROL_AT_07_05,
    P_TIROL_AT_07_28,
    P_ZELL_AM_SEE,
    FakeClock,
    alerts_with_status,
    call_log,
    only_source,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "slf"
REGIONS_FILE = FIXTURES / "CH_micro-regions.geojson.json"

SLF_URL = "https://www.slf.ch/de/lawinenbulletin-und-schneesituation/"
SLF_LABEL = "WSL-Institut für Schnee- und Lawinenforschung SLF"
SLF_MASSGEBLICH = "Maßgeblich ist der Originalbericht des SLF."
SLF_API_HOST = "aws.slf.ch"
SLF_API_PATH = "/api/bulletin/caaml/de/json"
SLF_REGISTRY_NAME = "slf_bulletin"

# Aufgezeichnete Antworten (Dateinamen unveraendert aus docs/artifacts/feat-1441-s3-slf/raw/)
WINTER_MORGEN = "at_2026-03-01T08:00:00Z.json"
WINTER_ABEND = "at_2026-03-01T17:30:00Z.json"
ABEND_FOLGETAG_FRUEH = "at_2026-03-02T06:00:00Z.json"
MORGEN_UPDATE = "at_2026-03-02T08:00:00Z.json"
DEZEMBER = "at_2025-12-20T08:00:00Z.json"
JANUAR = "at_2026-01-15T08:00:00Z.json"
FEBRUAR = "at_2026-02-10T08:00:00Z.json"
APRIL = "at_2026-04-10T08:00:00Z.json"
LEER = "leer.json"

# Feste Punkte AUSSERHALB der Schweiz (AC-12) bzw. im Mittelland (AC-13/14)
P_INNSBRUCK = (47.27, 11.39)
P_BREGENZ = (47.50, 9.75)
P_AOSTA = (45.74, 7.32)
P_FELDBERG = (47.87, 8.00)
# ACHTUNG (Datenpruefung 17.10.2026): (47.37, 8.54) liegt laut Umriss in CH-9311, NICHT in CH-9211
# (die Grenze laeuft durch Zuerich; S1-Punkt (47.3769, 8.5417) liegt in CH-9211). Beide Regionen
# sind in KEINER der acht Stichproben bewertet -- das Verhalten (leer, "nicht zustaendig") ist gleich.
P_ZUERICH = (47.37, 8.54)
P_ZUERICH_CH_9211 = (47.3769, 8.5417)   # = S1 ``P_ZUERICH``; Grenznah, fuer Region-ID-Aussagen
                                       # lieber ``interior_point("CH-9211")`` nutzen
# Nie bewertete Mikroregionen (keine der acht Stichproben), nur fuer Testauswahl -- nicht im Code!
NIE_BEWERTET = ("CH-8214", "CH-8215", "CH-8216", "CH-8222", "CH-8223", "CH-8224", "CH-8225",
                "CH-8226", "CH-8227", "CH-8228", "CH-9111", "CH-9211", "CH-9311")

EAWS_WORDS = ("low", "moderate", "considerable", "high", "very_high")


# ------------------------------------------------------------------ Fixture-Zugriff
def slf_raw(name: str) -> bytes:
    """Rohbytes einer aufgezeichneten Antwort aus ``tests/fixtures/slf/``."""
    return (FIXTURES / name).read_bytes()


def slf_doc(name: str) -> dict:
    """Geparste aufgezeichnete Antwort aus ``tests/fixtures/slf/``."""
    return json.loads(slf_raw(name).decode("utf-8"))


def region_ids_in(doc: dict) -> set[str]:
    """Alle in einem SLF-Dokument bewerteten Mikroregionen-IDs."""
    return {
        str(region.get("regionID"))
        for bulletin in doc.get("bulletins") or []
        for region in bulletin.get("regions") or []
        if region.get("regionID")
    }


def bulletin_of(doc: dict, region_id: str) -> dict:
    """Das (einzige) Bulletin, das ``region_id`` bewertet. Fehlt es -> ``KeyError`` (laut)."""
    hits = [b for b in doc.get("bulletins") or []
            if any(r.get("regionID") == region_id for r in b.get("regions") or [])]
    if len(hits) != 1:
        raise KeyError(f"{region_id}: {len(hits)} Bulletins bewerten die Region (erwartet 1)")
    return hits[0]


def _word(value: Union[int, str]) -> str:
    if isinstance(value, int):
        if not 1 <= value <= 5:
            raise ValueError(f"EAWS-Stufe {value} ausserhalb 1..5")
        return EAWS_WORDS[value - 1]
    if value not in EAWS_WORDS:
        raise ValueError(f"unbekanntes EAWS-Wort {value!r}")
    return value


def derive(doc: dict, region_id: str, *, main_value: Union[int, str, None] = None,
           problem_values: Optional[dict[str, Union[int, str]]] = None) -> dict:
    """Abgeleitete Variante (fuer Stufe 4/5 und Absenkungen, im Testnamen "abgeleitet" nennen).

    Tiefe Kopie; geaendert wird NUR im Bulletin der Region:
    - ``main_value``: ``dangerRatings[].mainValue`` ALLER Ratings dieses Bulletins,
    - ``problem_values`` (Schluessel ``problemType``): ``avalancheProblems[].dangerRatingValue``.
    Werte als Ziffer 1..5 oder EAWS-Wort. Achtung: ein SLF-Bulletin gilt fuer MEHRERE
    Mikroregionen -- die Aenderung trifft alle Regionen dieses Bulletins. Nichts sonst wird
    angefasst (keine Hoehe, keine Feinstufe, keine Zeiten, keine IDs). Ein unbekannter
    ``problemType`` ist ein Fehler, kein stilles Nichts.
    """
    out = copy.deepcopy(doc)
    bulletin = bulletin_of(out, region_id)
    if main_value is not None:
        word = _word(main_value)
        for rating in bulletin.get("dangerRatings") or []:
            rating["mainValue"] = word
    for problem_type, value in (problem_values or {}).items():
        problems = [p for p in bulletin.get("avalancheProblems") or []
                    if p.get("problemType") == problem_type]
        if not problems:
            raise KeyError(f"{region_id}: kein Problem {problem_type!r} im Bulletin")
        for problem in problems:
            problem["dangerRatingValue"] = _word(value)
    return out


def doc_bytes(doc: dict) -> bytes:
    return json.dumps(doc, ensure_ascii=False).encode("utf-8")


# ------------------------------------------------------------------ Geometrie (eigener Ray-Cast)
def _in_ring(lat: float, lon: float, ring: list) -> bool:
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat):
            x_cross = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < x_cross:
                inside = not inside
        j = i
    return inside


def _polygons(geometry: dict) -> list:
    coords = geometry.get("coordinates") or []
    return [coords] if geometry.get("type") == "Polygon" else list(coords)


def _in_geometry(lat: float, lon: float, geometry: dict) -> bool:
    for poly in _polygons(geometry):
        if poly and _in_ring(lat, lon, poly[0]) and not any(_in_ring(lat, lon, h) for h in poly[1:]):
            return True
    return False


@lru_cache(maxsize=1)
def _ch_features() -> tuple:
    doc = json.loads(REGIONS_FILE.read_text(encoding="utf-8"))
    return tuple((str(f["properties"]["id"]), f["geometry"]) for f in doc["features"])


def ch_regions_at(lat: float, lon: float) -> list[str]:
    """Helper-eigene Punkt-in-Polygon-Abfrage gegen die CH-Fixture (sortiert)."""
    return sorted(rid for rid, geo in _ch_features() if _in_geometry(lat, lon, geo))


def _seg_dist(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _edge_distance(lat: float, lon: float, geometry: dict) -> float:
    """Abstand zum naechsten Rand (lon mit cos(lat) skaliert, ~Grad)."""
    k = math.cos(math.radians(lat))
    best = math.inf
    for poly in _polygons(geometry):
        for ring in poly:
            for (ax, ay), (bx, by) in zip(ring, ring[1:] + ring[:1]):
                best = min(best, _seg_dist(lon * k, lat, ax * k, ay, bx * k, by))
    return best


@lru_cache(maxsize=None)
def interior_point(region_id: str, *, grid: int = 40) -> tuple[float, float]:
    """Deterministischer Punkt ``(lat, lon)``, der in GENAU dieser CH-Mikroregion liegt.

    Rasterabtastung der Bounding-Box (fester ``grid``); unter allen Rasterpunkten, die im Umriss
    (inkl. Loecher) und in KEINER anderen CH-Mikroregion liegen, gewinnt der mit dem groessten
    Randabstand (stabiler Gleichstand: kleinstes (lat, lon)). Schwerpunkt allein reicht bei
    nicht-konvexen Umrissen nicht. Auf 4 Nachkommastellen gerundet und danach erneut geprueft.
    """
    features = dict(_ch_features())
    if region_id not in features:
        raise KeyError(f"{region_id} nicht in {REGIONS_FILE.name}")
    geometry = features[region_id]
    pts = [p for poly in _polygons(geometry) for p in poly[0]]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    best: Optional[tuple[float, float, float]] = None
    for iy in range(1, grid):
        lat = round(y0 + (y1 - y0) * iy / grid, 4)
        for ix in range(1, grid):
            lon = round(x0 + (x1 - x0) * ix / grid, 4)
            if not _in_geometry(lat, lon, geometry):
                continue
            if ch_regions_at(lat, lon) != [region_id]:
                continue
            d = _edge_distance(lat, lon, geometry)
            if best is None or d > best[0] or (d == best[0] and (lat, lon) < (best[1], best[2])):
                best = (d, lat, lon)
    if best is None:
        raise ValueError(f"{region_id}: kein innerer Rasterpunkt gefunden (grid={grid})")
    return best[1], best[2]


# ------------------------------------------------------------------ Transport
@dataclass
class Reply:
    """Antwort des Fixture-Transports: Status + Bytes ODER eine auszuloesende Exception."""

    status: int = 200
    body: bytes = b""
    error: Optional[Exception] = None


def ok(name: str) -> Reply:
    """HTTP 200 mit einer aufgezeichneten Datei."""
    return Reply(200, slf_raw(name))


def ok_doc(doc: dict) -> Reply:
    """HTTP 200 mit einem beliebigen (z. B. per ``derive`` abgeleiteten) Dokument."""
    return Reply(200, doc_bytes(doc))


def leer() -> Reply:
    """Die aufgezeichnete Antwort ausser Saison: HTTP 200, ``{"bulletins":[]}``."""
    return ok(LEER)


# Fehlerarten (AC-10)
def netzfehler() -> Reply:
    return Reply(error=httpx.ConnectError("Verbindung verweigert"))


def http_503() -> Reply:
    return Reply(503, b"Service Unavailable")


def kaputtes_json() -> Reply:
    return Reply(200, b"<html>kein json</html>")


def ohne_bulletins() -> Reply:
    """200 mit gueltigem JSON, aber ohne ``bulletins``-Schluessel (realistisch: nur ``customData``)."""
    return Reply(200, b'{"customData":{}}')


FEHLERARTEN = {
    "netzfehler": netzfehler,
    "http-503": http_503,
    "kaputtes-json": kaputtes_json,
    "ohne-bulletins": ohne_bulletins,
}


class SlfFixtureTransport(httpx.BaseTransport):
    """Liefert die gewaehlte Antwort fuer ``aws.slf.ch/api/bulletin/caaml/de/json``.

    ``calls`` haelt die VOLLE URL jedes Zugriffs (inkl. Query -- so ist pruefbar, dass KEIN
    ``activeAt`` gesendet wird). ``set(reply)`` schaltet die Antwort zur Laufzeit um
    (Mehrlauf-Tests). Jeder andere Host -> ``ConnectError`` (wie ein geblockter Egress),
    ein anderer Pfad -> 404.
    """

    def __init__(self, reply: Union[Reply, str, dict, None] = None) -> None:
        self.reply: Reply = self._coerce(reply if reply is not None else LEER)
        self.calls: list[str] = []

    @staticmethod
    def _coerce(reply: Union[Reply, str, dict]) -> Reply:
        if isinstance(reply, Reply):
            return reply
        if isinstance(reply, str):
            return ok(reply)
        if isinstance(reply, dict):
            return ok_doc(reply)
        raise TypeError(f"unbekannte Antwort {reply!r}")

    def set(self, reply: Union[Reply, str, dict]) -> None:
        self.reply = self._coerce(reply)

    @property
    def count(self) -> int:
        """Anzahl der Zugriffe auf den SLF-Host (= echte Abrufe)."""
        return sum(1 for url in self.calls if httpx.URL(url).host == SLF_API_HOST)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(str(request.url))
        if request.url.host != SLF_API_HOST:
            raise httpx.ConnectError(f"unerwarteter Host {request.url.host}", request=request)
        if request.url.path != SLF_API_PATH:
            return httpx.Response(404, content=b"", request=request)
        reply = self.reply
        if reply.error is not None:
            raise reply.error
        headers = {"Content-Type": "application/json"} if reply.body else {}
        return httpx.Response(reply.status, content=reply.body, headers=headers, request=request)


# ------------------------------------------------------------------ Quelle und Registry
def make_slf_source(transport: SlfFixtureTransport, clock: Optional[FakeClock] = None, **kw):
    """Echte ``SlfSource`` mit Fixture-Transport, eigener Uhr und EIGENEM Cache.

    Angenommene Schnittstelle (analog ``AvalancheReportSource``):
    ``SlfSource(*, transport, clock, now_fn, cache)``. ``kw`` ueberstimmt die Vorgaben.
    """
    from services.official_alerts.slf import SlfSource

    args = {"transport": transport, "cache": {}}
    if clock is not None:
        args.update(clock=clock, now_fn=clock.now)
    args.update(kw)
    return SlfSource(**args)


def registered_names() -> list[str]:
    """Namen der echten Standard-Registry, in Registrierungsreihenfolge."""
    from services.official_alerts import base

    return [s.name for s in base._REGISTERED_SOURCES]


def registry_without(monkeypatch, name: str = SLF_REGISTRY_NAME) -> None:
    """Echte Registry OHNE die Quelle ``name`` (simuliert die entfernte Registrierungszeile)."""
    from services.official_alerts import base

    monkeypatch.setattr(base, "_REGISTERED_SOURCES",
                        [s for s in base._REGISTERED_SOURCES if s.name != name])


def registry_replacing(monkeypatch, *replacements) -> None:
    """Echte Registry, darin jede Quelle gleichen Namens durch die uebergebene ersetzt
    (Position bleibt). Unbekannte Namen werden ans Ende gehaengt."""
    from services.official_alerts import base

    by_name = {s.name: s for s in replacements}
    current = list(base._REGISTERED_SOURCES)
    out = [by_name.pop(s.name, s) for s in current]
    out.extend(by_name.values())
    monkeypatch.setattr(base, "_REGISTERED_SOURCES", out)


def only_slf(monkeypatch, transport: SlfFixtureTransport, clock: Optional[FakeClock] = None,
             *, others: Iterable = (), **kw):
    """Registry nur mit einer frischen ``SlfSource`` (plus ``others``); gibt die Quelle zurueck."""
    source = make_slf_source(transport, clock, **kw)
    only_source(monkeypatch, source, *others)
    return source
