"""TDD RED — MeteoAlarm: Rueckschau und Abrufaufwand entkoppeln (Issue #1397 S1).

SPEC: docs/specs/modules/fix_1397_meteoalarm_coverage_budget.md (AC-1 bis AC-5)

Pruefling ist ``src/services/official_alerts/meteoalarm.py`` (Slot-/Fenster-/
Cache-Mechanik). Der Pruefling wird ueber ``conftest.py`` relativ zu DIESER
Datei aufgeloest (``sys.path`` -> ``<repo>/src``); ``_assert_pruefling_aus_
diesem_baum()`` belegt das bei jedem Test (Projektregel #1409: ein Test darf
NIE die unveraenderte Hauptrepo-Kopie messen).

Kein Mock-Theater, kein Netz:
- **Fake-Transport = echter lokaler HTTP-Server** (``http.server``, echter
  Socket-Roundtrip wie in ``test_meteoalarm_source.py``). Er liefert
  aufgezeichnete Antworten aus und ZAEHLT jeden Abruf, der ihn tatsaechlich
  erreicht -- ein Cache-Treffer erreicht ihn nie, die Zahl ist damit der
  echte Netz-Verbrauch, nicht eine Selbstauskunft des Pruefling-Codes.
- **Aufgezeichnete Fixtures:** ``index_at_feature_template.json`` (echtes
  AT-Index-Feature, api.meteoalarm.org, 2026-07-14, bbox Villach),
  ``cap_villach_heat.xml`` / ``cap_villach_heat_orange.xml`` (CAP-Dokumente),
  ``at_publication_profile_storm_day.json`` (Veroeffentlichungs-Profil eines
  Gewittertags, kalibriert an den Messungen vom 27./29.07.2026).
- **Injizierte Uhr:** ``_FakeClock`` speist ``meteoalarm._WALL_CLOCK_FN`` UND
  ``meteoalarm.datetime.now()`` aus derselben Quelle; ``_SLEEP_FN`` ist ein
  No-Op (kein echtes Warten im Kern-Testlauf).

Der Fake-Transport bildet die Semantik der echten EDR-API nach: der
``datetime``-Query filtert nach dem VEROEFFENTLICHUNGS-Zeitpunkt der Warnung
(``hubTime``), Seitengroesse 100 (``metadata.total_pages`` wie aufgezeichnet).
Genau daraus entsteht der Bug: was laenger her veroeffentlicht wurde als das
angefragte Fenster, kommt nicht mehr mit -- auch wenn es weiter gilt.
"""
from __future__ import annotations

import http.server
import json
import math
import threading
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Live-Schicht (Test-Politik, CLAUDE.md): braucht echtes Netz/echte Dienste --
# lief im Kern nie gruen (CI-Vermessung 2026-08-04, #1196) und gehoert per
# Marker in den /e2e-verify-Lauf, nicht auf eine Ausnahmeliste.
pytestmark = pytest.mark.live

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "meteoalarm"
_REPO_ROOT = Path(__file__).resolve().parents[2]

VILLACH = (46.61, 13.85)  # abgedeckter AT-Punkt, liegt in der aufgezeichneten bbox
_QUERY_FMT = "%Y-%m-%dT%H:%M:%SZ"

# Exakte Flaeche (geometry-Link-Antwort) um Villach -- enthaelt den Testpunkt.
_VILLACH_SHAPE = {
    "type": "Polygon",
    "coordinates": [[[13.60, 46.50], [13.60, 46.72], [14.05, 46.72], [14.05, 46.50], [13.60, 46.50]]],
}
# bbox weit weg vom Testpunkt (Vorarlberg) -- Grundrauschen des Tages, das den
# Punkt garantiert nicht abdeckt und deshalb KEIN Flaechen-/CAP-Nachladen
# ausloest (``_bbox_may_contain``).
_FAR_BBOX = {
    "type": "Polygon",
    "coordinates": [[[9.60, 47.00], [9.60, 47.35], [10.05, 47.35], [10.05, 47.00], [9.60, 47.00]]],
}


def _assert_pruefling_aus_diesem_baum() -> None:
    """#1409: der importierte Pruefling MUSS aus dem Baum dieser Testdatei
    stammen -- sonst misst der Test aus einem Worktree die unveraenderte
    Hauptrepo-Kopie und meldet falsches Gruen."""
    from services.official_alerts import meteoalarm

    modul = Path(meteoalarm.__file__).resolve()
    assert str(modul).startswith(str(_REPO_ROOT)), (
        f"Pruefling {modul} liegt ausserhalb von {_REPO_ROOT} -- der Test wuerde "
        f"eine fremde Kopie messen"
    )


@pytest.fixture(autouse=True)
def _kalter_prozess(monkeypatch):
    """Jeder Test startet mit leeren Modul-Caches (= frischer Prozess) und
    einem hohen Tagesbudget: gemessen werden soll der ECHTE Abrufbedarf, nicht
    die Selbstbremse ``MeteoAlarmBudgetGate`` (die diese Scheibe laut Spec
    ausdruecklich NICHT veraendert)."""
    from services.official_alerts import meteoalarm

    def _leeren() -> None:
        meteoalarm._index_cache.clear()
        meteoalarm._geometry_cache.clear()
        meteoalarm._cap_cache.clear()

    _leeren()
    monkeypatch.setenv("GZ_METEOALARM_APIKEY", "dummy-test-token-index-coverage")
    monkeypatch.setenv("GZ_METEOALARM_DAILY_BUDGET", "100000")
    monkeypatch.delenv("GZ_METEOALARM_WINDOW_HOURS", raising=False)
    _assert_pruefling_aus_diesem_baum()
    yield
    _leeren()


# ---------------------------------------------------------------------------
# Injizierte Uhr
# ---------------------------------------------------------------------------

class _FakeClock:
    """Eine Uhr, die der Test vorstellt -- Quelle fuer BEIDE Zeitzugriffe des
    Pruefling-Moduls (``_WALL_CLOCK_FN`` und ``datetime.now()``)."""

    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> float:  # _WALL_CLOCK_FN-Signatur
        return self.now.timestamp()

    def sleep(self, seconds: float) -> None:
        """Gekoppelter Ersatz fuer ``time.sleep``: eine Entzerr-Pause kostet
        dieselbe Zeit, die die Uhr danach anzeigt -- in Produktion sind
        ``time.sleep`` und ``time.time()`` dieselbe Wanduhr. Nur so greift das
        Seiten-Zeitbudget (``_PAGE_FETCH_BUDGET_SECONDS``) im Test ueberhaupt."""
        self.now = self.now + timedelta(seconds=seconds)

    def advance(self, **kwargs) -> None:
        self.now = self.now + timedelta(**kwargs)


def _uhr_einsetzen(monkeypatch, clock: _FakeClock, *, gekoppelt: bool = False) -> None:
    from services.official_alerts import meteoalarm

    class _PatchedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: D102 - stdlib-Signatur
            return clock.now if tz is None else clock.now.astimezone(tz)

    monkeypatch.setattr(meteoalarm, "datetime", _PatchedDatetime)
    monkeypatch.setattr(meteoalarm, "_WALL_CLOCK_FN", clock)
    monkeypatch.setattr(
        meteoalarm, "_SLEEP_FN", clock.sleep if gekoppelt else (lambda _seconds: None)
    )


def _fensterbreiten_h(zaehler: "_Zaehler", country: str) -> list[float]:
    """Angefragte Fensterbreiten EINES Landes (``fensterlaengen_h()`` mischt
    beide Laender und verdeckt damit den Deckel-Nachweis)."""
    return sorted({
        round((ende - start).total_seconds() / 3600.0, 2)
        for land, _p, start, ende in zaehler.index
        if land == country and start
    })


# ---------------------------------------------------------------------------
# Fake-Transport: echter lokaler Server + Zaehler + aufgezeichnete Zeitachse
# ---------------------------------------------------------------------------

class _Zaehler:
    """Zaehlt ausschliesslich Anfragen, die den Server WIRKLICH erreichen."""

    def __init__(self) -> None:
        self.index: list[tuple] = []  # (country, page, window_start, window_end)
        self.details: list[str] = []  # geometry-/CAP-Pfade

    @property
    def index_abrufe(self) -> int:
        return len(self.index)

    def fensterlaengen_h(self) -> list[float]:
        return sorted({round((e - s).total_seconds() / 3600.0, 2) for _c, _p, s, e in self.index if s})


class _AufgezeichneterFeed:
    """Zeitachse veroeffentlichter Warnungen je Land. ``seite()`` beantwortet
    eine Anfrage wie die echte API: Filter auf den Veroeffentlichungszeitpunkt
    im angefragten ``datetime``-Fenster, Seitengroesse 100."""

    page_size = 100

    def __init__(self) -> None:
        self.features: dict[str, list[dict]] = {"AT": [], "IT": []}
        self.stoerungen: dict[tuple, dict] = {}  # (country, page) -> {"status":..,"headers":{}}

    def add(self, country: str, feature: dict) -> None:
        self.features.setdefault(country, []).append(feature)

    def seite(self, country: str, start, end, page_num: int) -> dict:
        treffer = [
            f for f in self.features.get(country, [])
            if start is None
            or start <= datetime.strptime(f["properties"]["hubTime"], _QUERY_FMT) <= end
        ]
        total_pages = max(1, math.ceil(len(treffer) / self.page_size))
        chunk = treffer[(page_num - 1) * self.page_size: page_num * self.page_size]
        return {
            "type": "FeatureCollection",
            "metadata": {"page_size": self.page_size, "total_count": len(treffer),
                         "total_pages": total_pages, "page": page_num},
            "features": chunk,
        }


def _server_starten(feed: _AufgezeichneterFeed, zaehler: _Zaehler, cap_bodies: dict):
    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib-Signatur
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            if parsed.path.startswith("/collections/warnings/locations/"):
                country = parsed.path.rsplit("/", 1)[-1]
                page_num = int(qs.get("page", ["1"])[0])
                start = end = None
                if qs.get("datetime"):
                    roh_start, roh_end = qs["datetime"][0].split("/")
                    start = datetime.strptime(roh_start, _QUERY_FMT)
                    end = datetime.strptime(roh_end, _QUERY_FMT)
                zaehler.index.append((country, page_num, start, end))
                if start is not None and (end - start) >= timedelta(hours=24):
                    # Echte API-Grenze (Live-Messung 2026-07-15 gegen
                    # api.meteoalarm.org, Issue #1086): der ``datetime``-Bereich
                    # ist Pflicht UND muss unter 24 Stunden bleiben -- ein
                    # breiterer Bereich wird hart abgelehnt, der Zyklus liefert
                    # dann gar nichts. Der Fake-Transport bildet das nach, damit
                    # ein Fenster-Regress hier sofort auffaellt statt still
                    # teurer zu werden.
                    self.send_response(400)
                    self.end_headers()
                    return
                stoerung = feed.stoerungen.get((country, page_num))
                if stoerung:
                    self.send_response(stoerung["status"])
                    for name, value in stoerung.get("headers", {}).items():
                        self.send_header(name, value)
                    self.end_headers()
                    return
                self._senden(json.dumps(feed.seite(country, start, end, page_num)).encode(),
                             "application/json")
                return
            zaehler.details.append(parsed.path)
            if parsed.path.startswith("/geometry/"):
                shape = {"villach": _VILLACH_SHAPE}.get(
                    parsed.path.rsplit("/", 1)[-1], _FAR_BBOX)
                self._senden(json.dumps({"geometry": shape}).encode(), "application/json")
            else:
                self._senden(cap_bodies[parsed.path].encode("utf-8"), "application/xml")

        def _senden(self, body: bytes, content_type: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):  # Testlauf-Output nicht zumuellen
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


_TEMPLATE_TEXT = (_FIXTURES / "index_at_feature_template.json").read_text(encoding="utf-8")
_CAP_GELB = (_FIXTURES / "cap_villach_heat.xml").read_text(encoding="utf-8")
_CAP_ORANGE = (_FIXTURES / "cap_villach_heat_orange.xml").read_text(encoding="utf-8")


def _feature(port: int, alert_id: str, hub_time: datetime, *, country: str = "AT",
             geometry_key: str = "villach", cap_key: str = "villach-heat",
             bbox: dict | None = None, superseded_by: str | None = None) -> dict:
    """Ein Index-Feature aus der aufgezeichneten Vorlage, mit gesetztem
    Veroeffentlichungszeitpunkt (``hubTime``)."""
    text = (
        _TEMPLATE_TEXT
        .replace("TESTSERVER", f"127.0.0.1:{port}")
        .replace("{OBJECT_ID}", f"OID-{alert_id}")
        .replace("{ALERT_ID}", alert_id)
        .replace("{COUNTRY}", country)
        .replace("{HUB_TIME}", hub_time.strftime(_QUERY_FMT))
        .replace("{GEOMETRY_KEY}", geometry_key)
        .replace("{CAP_KEY}", cap_key)
    )
    feature = json.loads(text)
    feature.pop("_recorded_from", None)
    if bbox is not None:
        feature["geometry"] = bbox
    if superseded_by is not None:
        feature["properties"]["supersededByAlertId"] = superseded_by
        feature["properties"]["supersededAt"] = hub_time.strftime(_QUERY_FMT)
    return feature


def _grundrauschen_eines_gewittertags(feed: _AufgezeichneterFeed, port: int, tag0: datetime,
                                      tage_zurueck: int = 1) -> None:
    """Fuellt die Zeitachse mit dem aufgezeichneten Veroeffentlichungsprofil
    (Vortage + Tag), damit auch eine Rueckschau ueber Mitternacht bedient wird.
    ``tage_zurueck`` > 1 fuer Szenarien, in denen eine haengende
    Fortschrittsmarke mehrere Tage zurueckreicht -- dort muss die Zeitachse so
    weit zurueck ueberhaupt Veroeffentlichungen anbieten."""
    profil = json.loads((_FIXTURES / "at_publication_profile_storm_day.json").read_text())
    pro_stunde = profil["publications_per_hour"]
    for tag in [tag0 - timedelta(days=d) for d in range(tage_zurueck, 0, -1)] + [tag0]:
        for stunde in range(24):
            anzahl = int(pro_stunde[str(stunde)])
            for i in range(anzahl):
                zeitpunkt = tag + timedelta(hours=stunde, minutes=int(60 * i / anzahl))
                feed.add("AT", _feature(
                    port, f"noise-{tag:%m%d}-{stunde:02d}-{i:03d}", zeitpunkt,
                    geometry_key="vorarlberg", bbox=_FAR_BBOX,
                ))


# ---------------------------------------------------------------------------
# AC-1: Eine vor 5 Stunden veroeffentlichte, weiter gueltige Warnung bleibt
# sichtbar -- auch nachdem der Zeitslot gewechselt hat.
# ---------------------------------------------------------------------------

def test_ac1_warnung_von_vor_fuenf_stunden_bleibt_nach_slotwechsel_sichtbar(monkeypatch):
    """AC-1: GIVEN eine amtliche Hitzewarnung fuer Villach wurde um 07:00 UTC
    veroeffentlicht und gilt den ganzen Tag, WHEN der Dienst sie in einem
    ersten Zyklus (08:00 UTC) findet und ein zweiter Zyklus fuenf Stunden nach
    der Veroeffentlichung (12:00 UTC, neuer Zeitslot) laeuft, THEN erscheint
    sie im zweiten Zyklus weiterhin -- statt unsichtbar zu werden, nur weil
    ihre Veroeffentlichung aus dem angefragten Zeitfenster gerutscht ist."""
    from services.official_alerts import meteoalarm

    feed, zaehler = _AufgezeichneterFeed(), _Zaehler()
    server, thread = _server_starten(feed, zaehler, {"/cap/villach-heat": _CAP_GELB})
    try:
        port = server.server_port
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{port}")
        veroeffentlicht = datetime(2026, 7, 15, 7, 0, tzinfo=timezone.utc)
        feed.add("AT", _feature(port, "villach-hitze-langlaeufer",
                                veroeffentlicht.replace(tzinfo=None)))

        clock = _FakeClock(datetime(2026, 7, 15, 8, 0, tzinfo=timezone.utc))
        _uhr_einsetzen(monkeypatch, clock)

        erster_zyklus = meteoalarm.MeteoAlarmSource().fetch(*VILLACH)
        assert any(a.hazard == "extreme_heat" for a in erster_zyklus), (
            f"Aufbaupruefung: eine Stunde nach der Veroeffentlichung MUSS die Warnung "
            f"gefunden werden, erhalten: {erster_zyklus}"
        )

        clock.advance(hours=4)  # 12:00 UTC -- Veroeffentlichung liegt 5h zurueck
        zweiter_zyklus = meteoalarm.MeteoAlarmSource().fetch(*VILLACH)

        assert any(a.hazard == "extreme_heat" for a in zweiter_zyklus), (
            f"Warnung wurde vor 5 Stunden veroeffentlicht, gilt weiter und war im "
            f"vorigen Zyklus bereits im Index -- sie muss weiterhin erscheinen. "
            f"Erhalten: {zweiter_zyklus}; angefragte Fensterlaengen (h): "
            f"{zaehler.fensterlaengen_h()}"
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)


# ---------------------------------------------------------------------------
# AC-2: 24 Stunden Normalbetrieb an einem Gewittertag -> unter 100 echte
# Index-Abrufe.
# ---------------------------------------------------------------------------

def test_ac2_vierundzwanzig_stunden_gewittertag_bleiben_unter_hundert_abrufen(monkeypatch):
    """AC-2: GIVEN ein Gewittertag mit Blaetter-Ausbruechen (aufgezeichnetes
    Veroeffentlichungsprofil, mehrseitige Antworten), WHEN der Dienst 24
    Stunden im heutigen Aufrufmuster laeuft (alle 15 Minuten ein
    ``fetch()``-Aufruf wie durch die Alarmpruefung), THEN bleibt die Zahl der
    Abrufe, die den amtlichen Dienst tatsaechlich erreichen, unter 100."""
    from services.official_alerts import meteoalarm

    feed, zaehler = _AufgezeichneterFeed(), _Zaehler()
    server, thread = _server_starten(feed, zaehler, {})
    try:
        port = server.server_port
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{port}")
        tag0 = datetime(2026, 7, 15, 0, 0)
        _grundrauschen_eines_gewittertags(feed, port, tag0)

        clock = _FakeClock(tag0.replace(tzinfo=timezone.utc))
        _uhr_einsetzen(monkeypatch, clock)

        quelle = meteoalarm.MeteoAlarmSource()
        for _viertelstunde in range(96):  # 24h im 15-Minuten-Takt
            quelle.fetch(*VILLACH)
            clock.advance(minutes=15)

        assert zaehler.index_abrufe < 100, (
            f"24h Normalbetrieb an einem Gewittertag duerfen unter 100 echte Abrufe "
            f"bleiben, gemessen: {zaehler.index_abrufe} "
            f"(angefragte Fensterlaengen in h: {zaehler.fensterlaengen_h()})"
        )
        assert zaehler.index_abrufe >= 24, (
            f"mindestens stuendlich muss echt aufgefrischt werden (sonst waeren die "
            f"Warnungen veraltet), gemessen: {zaehler.index_abrufe}"
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)


# ---------------------------------------------------------------------------
# AC-3: Kaltstart -- gleiche Rueckschau-Tiefe wie im eingeschwungenen Betrieb.
# ---------------------------------------------------------------------------

def test_ac3_kaltstart_sieht_zwanzig_stunden_alte_warnung_sofort(monkeypatch):
    """AC-3: GIVEN ein frisch gestarteter Prozess (leerer Bestand) und eine
    amtliche Warnung, die vor 20 Stunden veroeffentlicht wurde und weiter
    gilt, WHEN der erste Zyklus nach dem Start laeuft, THEN erscheint diese
    Warnung sofort -- der Neustart darf die Rueckschau nicht verkuerzen."""
    from services.official_alerts import meteoalarm

    feed, zaehler = _AufgezeichneterFeed(), _Zaehler()
    server, thread = _server_starten(feed, zaehler, {"/cap/villach-heat": _CAP_GELB})
    try:
        port = server.server_port
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{port}")
        feed.add("AT", _feature(port, "villach-hitze-gestern-abend",
                                datetime(2026, 7, 14, 16, 0)))

        clock = _FakeClock(datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc))
        _uhr_einsetzen(monkeypatch, clock)

        alerts = meteoalarm.MeteoAlarmSource().fetch(*VILLACH)

        assert any(a.hazard == "extreme_heat" for a in alerts), (
            f"erster Zyklus nach dem Neustart muss dieselbe Rueckschau-Tiefe haben wie "
            f"der Dauerbetrieb (20h alte, weiter gueltige Warnung). Erhalten: {alerts}; "
            f"angefragte Fensterlaengen (h): {zaehler.fensterlaengen_h()}"
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)


# ---------------------------------------------------------------------------
# AC-4 (REGRESSIONSSCHUTZ, heute bereits gruen): abgebrochener Zyklus meldet
# weiterhin "nicht abrufbar", NIE "keine Warnung".
# ---------------------------------------------------------------------------

def test_ac4_abgebrochener_zyklus_meldet_weiterhin_nicht_abrufbar(monkeypatch):
    """AC-4 (Regressionsschutz): GIVEN der amtliche Dienst bremst einen Zyklus
    mitten im Blaettern aus (HTTP 429 mit Tageskontingent-Reset auf Seite 2),
    WHEN das Briefing fuer einen betroffenen Ort gerendert wird, THEN meldet
    die Auskunft weiterhin "nicht abrufbar" -- nie faelschlich "keine
    Warnung"."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_with_status, meteoalarm

    feed, zaehler = _AufgezeichneterFeed(), _Zaehler()
    server, thread = _server_starten(feed, zaehler, {"/cap/villach-heat": _CAP_GELB})
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        port = server.server_port
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{port}")
        jetzt = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
        # Genug Veroeffentlichungen in der letzten Stunde, dass geblaettert
        # werden MUSS (>1 Seite) -- Seite 2 wird ausgebremst.
        for i in range(140):
            feed.add("AT", _feature(port, f"gewitter-{i:03d}",
                                    datetime(2026, 7, 15, 11, 30) + timedelta(seconds=i),
                                    geometry_key="vorarlberg", bbox=_FAR_BBOX))
        feed.stoerungen[("AT", 2)] = {
            "status": 429, "headers": {"x-ratelimit-reset": str(int(jetzt.timestamp()) + 86399)},
        }

        clock = _FakeClock(jetzt)
        _uhr_einsetzen(monkeypatch, clock)
        oa_base._REGISTERED_SOURCES.append(meteoalarm.MeteoAlarmSource())

        _alerts, unavailable = get_official_alerts_with_status(*VILLACH, now=jetzt)

        assert unavailable is True, (
            "ein an einer Grenze abgebrochener Zyklus muss weiterhin als 'nicht "
            "abrufbar' gelten -- sonst wird ein Ausfall als 'keine Warnung' ausgeliefert"
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


# ---------------------------------------------------------------------------
# AC-5: ueberholte Fassung erscheint im wachsenden Bestand NICHT zusaetzlich.
# ---------------------------------------------------------------------------

def test_ac5_ueberholte_fassung_erscheint_nicht_zusaetzlich_im_bestand(monkeypatch):
    """AC-5: GIVEN eine Hitzewarnung (gelb) wird spaeter durch eine
    nachgefuehrte Fassung (orange) ersetzt, WHEN der Bestand ueber drei
    Zyklen waechst und danach ausgewertet wird, THEN erscheint genau die
    gueltige (orange) Fassung -- die ueberholte gelbe weder zusaetzlich noch
    an ihrer Stelle."""
    from services.official_alerts import meteoalarm

    feed, zaehler = _AufgezeichneterFeed(), _Zaehler()
    server, thread = _server_starten(
        feed, zaehler,
        {"/cap/villach-heat": _CAP_GELB, "/cap/villach-heat-orange": _CAP_ORANGE},
    )
    try:
        port = server.server_port
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{port}")
        alt = _feature(port, "villach-hitze-gelb", datetime(2026, 7, 15, 7, 0))
        feed.add("AT", alt)

        clock = _FakeClock(datetime(2026, 7, 15, 8, 0, tzinfo=timezone.utc))
        _uhr_einsetzen(monkeypatch, clock)
        quelle = meteoalarm.MeteoAlarmSource()

        # Zyklus 1: nur die gelbe Fassung ist bekannt.
        assert [a.level for a in quelle.fetch(*VILLACH)] == [2], (
            "Aufbaupruefung: im ersten Zyklus muss genau die gelbe Fassung erscheinen"
        )

        # Zyklus 2: die Behoerde fuehrt nach -- die alte Fassung traegt jetzt
        # den Ueberholt-Vermerk, die neue (orange) kommt hinzu.
        alt["properties"]["supersededByAlertId"] = "villach-hitze-orange"
        alt["properties"]["supersededAt"] = "2026-07-15T09:00:00Z"
        feed.add("AT", _feature(port, "villach-hitze-orange", datetime(2026, 7, 15, 9, 0),
                                cap_key="villach-heat-orange"))
        clock.advance(hours=2)  # 10:00 UTC
        quelle.fetch(*VILLACH)

        # Zyklus 3: beide Veroeffentlichungen liegen laenger zurueck.
        clock.advance(hours=4)  # 14:00 UTC
        alerts = quelle.fetch(*VILLACH)

        stufen = sorted(a.level for a in alerts if a.hazard == "extreme_heat")
        assert stufen == [3], (
            f"im gewachsenen Bestand darf genau die gueltige (orange, Stufe 3) Fassung "
            f"stehen -- nicht zusaetzlich die ueberholte (gelb, Stufe 2) und nicht gar "
            f"keine. Erhalten Stufen: {stufen} (Alerts: {alerts}); angefragte "
            f"Fensterlaengen (h): {zaehler.fensterlaengen_h()}"
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)


# ---------------------------------------------------------------------------
# Adversary F001 (Fix-Loop 1): das mitwachsende Auffrisch-Fenster hatte im
# Dauerbetrieb keine Obergrenze. Bleibt die Fortschrittsmarke haengen (kein
# Zyklus wird je vollstaendig), wuchs es unbegrenzt weiter -- und mit ihm die
# Seitenzahl je Zyklus, bis kein Zyklus mehr in ein Zeitbudget passte.
# ---------------------------------------------------------------------------

def _marke_haengt_seit(country: str, jetzt: datetime, tage: float) -> None:
    """Ausgangszustand "seit ``tage`` Tagen wurde kein Zyklus mehr
    vollstaendig": die Fortschrittsmarke steht auf einem alten Slot-Ende."""
    from services.official_alerts import meteoalarm

    meteoalarm._country_store(country)["last_complete"] = jetzt - timedelta(days=tage)


def test_f001_auffrischfenster_bleibt_auf_kaltstart_breite_gedeckelt(monkeypatch):
    """F001-1: GIVEN die Fortschrittsmarke haengt seit 44 Tagen (kein Zyklus
    wurde seither vollstaendig), WHEN der naechste Auffrischungs-Zyklus laeuft,
    THEN fragt er beim amtlichen Dienst hoechstens die Kaltstart-Breite ab --
    nachgewiesen an der Anfrage, die den lokalen Server tatsaechlich erreicht,
    nicht an einer Selbstauskunft des Pruefling-Codes."""
    from services.official_alerts import meteoalarm

    feed, zaehler = _AufgezeichneterFeed(), _Zaehler()
    server, thread = _server_starten(feed, zaehler, {"/cap/villach-heat": _CAP_GELB})
    try:
        port = server.server_port
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{port}")
        feed.add("AT", _feature(port, "villach-hitze", datetime(2026, 7, 15, 7, 0)))

        jetzt = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
        clock = _FakeClock(jetzt)
        _uhr_einsetzen(monkeypatch, clock)
        _marke_haengt_seit("AT", jetzt, tage=44)

        meteoalarm.MeteoAlarmSource().fetch(*VILLACH)

        breiten = _fensterbreiten_h(zaehler, "AT")
        assert breiten, "es muss ueberhaupt eine Index-Anfrage beim Dienst angekommen sein"
        assert max(breiten) <= meteoalarm.DEFAULT_INDEX_WINDOW_HOURS, (
            f"ein 44 Tage alter Rueckstand darf das Abfragefenster nicht ueber die "
            f"Kaltstart-Breite ({meteoalarm.DEFAULT_INDEX_WINDOW_HOURS}h) hinaus "
            f"aufblaehen -- der amtliche Dienst sah Fensterbreiten (h): {breiten}"
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_f001_haengende_fortschrittsmarke_sprengt_das_abrufbudget_nicht(monkeypatch):
    """F001-2: GIVEN dasselbe 24-Stunden-Gewittertagsprofil wie AC-2, aber die
    Zyklen sind bisher nie vollstaendig geworden (Fortschrittsmarke haengt seit
    drei Tagen; Entzerr-Pausen kosten Zeit wie in Produktion, das
    Seiten-Zeitbudget greift also wirklich), WHEN der Dienst 24 Stunden im
    heutigen Aufrufmuster weiterlaeuft, THEN bleibt die Zahl der Abrufe, die
    den amtlichen Dienst tatsaechlich erreichen, unter 100 -- statt sich in
    einem immer breiteren Fenster mit immer mehr Seiten selbst zu verstaerken,
    das nie fertig wird."""
    from services.official_alerts import meteoalarm

    feed, zaehler = _AufgezeichneterFeed(), _Zaehler()
    server, thread = _server_starten(feed, zaehler, {})
    try:
        port = server.server_port
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{port}")
        tag0 = datetime(2026, 7, 15, 0, 0)
        # Zeitachse ueber vier Tage: nur dann liefert ein ungedeckeltes
        # Drei-Tage-Fenster auch wirklich drei Tage Veroeffentlichungen.
        _grundrauschen_eines_gewittertags(feed, port, tag0, tage_zurueck=3)

        clock = _FakeClock(tag0.replace(tzinfo=timezone.utc))
        _uhr_einsetzen(monkeypatch, clock, gekoppelt=True)
        _marke_haengt_seit("AT", clock.now, tage=3)

        quelle = meteoalarm.MeteoAlarmSource()
        for viertelstunde in range(96):  # 24h im 15-Minuten-Takt
            quelle.fetch(*VILLACH)
            clock.now = tag0.replace(tzinfo=timezone.utc) + timedelta(minutes=15 * (viertelstunde + 1))

        assert zaehler.index_abrufe < 100, (
            f"auch mit haengender Fortschrittsmarke duerfen 24h Gewittertag unter 100 "
            f"echte Abrufe bleiben, gemessen: {zaehler.index_abrufe} "
            f"(AT-Fensterbreiten in h: {_fensterbreiten_h(zaehler, 'AT')})"
        )
        assert max(_fensterbreiten_h(zaehler, "AT")) < 24.0, (
            f"sparsam ist nur, was auch ankommt: ueber der Anbieter-Grenze (<24h) lehnt "
            f"der Dienst jede Anfrage ab -- ein niedriger Zaehler waere dann ein toter, "
            f"kein genuegsamer Dienst. AT-Fensterbreiten (h): "
            f"{_fensterbreiten_h(zaehler, 'AT')}"
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)


def _cap_mit_ablauf(ablauf: datetime) -> str:
    """Das aufgezeichnete Villach-Hitze-CAP mit gesetzter Gueltigkeitsgrenze:
    unveraenderte Struktur der Aufzeichnung, nur ``expires`` auf den vom
    Szenario gebrauchten Zeitpunkt gesetzt (einmal mehrtaegig laufend, einmal
    bereits abgelaufen). Aufgezeichnet ist ein Tages-Ablauf -- mehrtaegige
    Hitze-/Kaeltewarnungen sind bei denselben Behoerden ueblich."""
    return _CAP_GELB.replace(
        "2026-07-15T23:59:59+02:00", ablauf.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    )


def test_f004_gueltige_warnung_ueberlebt_ausfall_laenger_als_die_rueckschau(monkeypatch):
    """F004: GIVEN eine mehrtaegige amtliche Hitzewarnung wurde gesehen, danach
    ist der amtliche Dienst 30 Stunden lang gar nicht erreichbar (laenger als
    die Rueckschau-Tiefe), WHEN der Dienst wieder anlaeuft (der eine
    Wiederanlauf-Zyklus ist gekappt) und danach weitere Briefings gerendert
    werden, THEN erscheint die weiterhin gueltige Warnung in diesen Briefings
    weiter -- und eine zwischenzeitlich abgelaufene erscheint nicht mehr.

    Ohne den Fix lebte ein Bestands-Eintrag nur so lange, wie er zuletzt im
    Abfragefenster GESEHEN wurde (23h): nach dem 30-Stunden-Ausfall war er
    weg, und weil der Anbieter seinen Index nach dem Veroeffentlichungs-
    Zeitpunkt filtert, konnte er nie wieder hereinkommen -- die Briefings ab
    dem zweiten Zyklus meldeten wieder eine unauffaellige Lage
    (``unavailable=False``) bei bestehender Gefahr."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_with_status, meteoalarm

    laeuft_bis = datetime(2026, 7, 17, 18, 0, tzinfo=timezone.utc)  # mehrtaegig
    abgelaufen_seit = datetime(2026, 7, 15, 20, 0, tzinfo=timezone.utc)
    feed, zaehler = _AufgezeichneterFeed(), _Zaehler()
    server, thread = _server_starten(feed, zaehler, {
        "/cap/villach-heat-mehrtaegig": _cap_mit_ablauf(laeuft_bis),
        "/cap/villach-heat-kurz": _cap_mit_ablauf(abgelaufen_seit),
    })
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        port = server.server_port
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{port}")
        veroeffentlicht = datetime(2026, 7, 15, 6, 0)
        feed.add("AT", _feature(port, "villach-hitze-mehrtaegig", veroeffentlicht,
                                cap_key="villach-heat-mehrtaegig"))
        feed.add("AT", _feature(port, "villach-hitze-kurz", veroeffentlicht,
                                cap_key="villach-heat-kurz"))

        clock = _FakeClock(datetime(2026, 7, 15, 7, 0, tzinfo=timezone.utc))
        _uhr_einsetzen(monkeypatch, clock)
        oa_base._REGISTERED_SOURCES.append(meteoalarm.MeteoAlarmSource())

        vorher, _u = get_official_alerts_with_status(*VILLACH, now=clock.now)
        assert {a.valid_to for a in vorher} == {laeuft_bis, abgelaufen_seit}, (
            f"Aufbaupruefung: eine Stunde nach der Veroeffentlichung muessen BEIDE "
            f"Warnungen gefunden werden (mehrtaegige + kurze). Erhalten: {vorher}"
        )

        # 30 Stunden Ausfall: der amtliche Dienst antwortet auf JEDE Index-Seite
        # mit HTTP 503, der Bestand bekommt in dieser Zeit keine frische Antwort.
        feed.stoerungen[("AT", 1)] = {"status": 503}
        for _sechs_stunden in range(5):
            clock.advance(hours=6)
            _im_ausfall, ausfall_unavailable = get_official_alerts_with_status(
                *VILLACH, now=clock.now)
            assert ausfall_unavailable is True, (
                "Aufbaupruefung: waehrend des Ausfalls muss 'nicht abrufbar' gelten"
            )
        del feed.stoerungen[("AT", 1)]

        # Wiederanlauf: der Dienst antwortet wieder, der Rueckstand ist aber
        # groesser als die Rueckschau -> genau EIN gekappter Zyklus. Der Zyklus
        # laeuft im naechsten Zeitslot (im laufenden liegt der Fehlschlag des
        # Ausfalls noch im kurzen Failure-Fenster des Seiten-Caches -- so
        # verhaelt sich auch die Produktion).
        clock.advance(hours=1)
        wiederanlauf, wiederanlauf_unavailable = get_official_alerts_with_status(
            *VILLACH, now=clock.now)
        assert wiederanlauf_unavailable is True, (
            f"der Wiederanlauf-Zyklus ist gekappt und muss 'nicht abrufbar' melden; "
            f"AT-Fensterbreiten (h): {_fensterbreiten_h(zaehler, 'AT')}"
        )

        clock.advance(hours=1)  # naechster, regulaerer Zyklus
        danach, danach_unavailable = get_official_alerts_with_status(*VILLACH, now=clock.now)

        # Fix-Loop 5: das Ausfall-Signal haengt wieder AUSSCHLIESSLICH an echten
        # Stoerungen. Dieser Zyklus laeuft regulaer durch -- der Dienst antwortet,
        # die Rueckschau ist nicht gekappt, keine Ratenbremse. Also KEIN Hinweis,
        # obwohl die angezeigte Warnung seit 32 Stunden nicht mehr frisch im Index
        # gesehen wurde: sie IST abrufbar und wird gezeigt, sie ist nur nicht
        # erneut bestaetigt -- das ist keine Luecke (PO-Entscheidung an #1348).
        assert danach_unavailable is False, (
            f"nach dem einen gekappten Wiederanlauf-Zyklus antwortet der Dienst wieder "
            f"vollstaendig -- dann darf das Briefing keinen Ausfall behaupten. Erhalten: "
            f"unavailable={danach_unavailable}, Alerts: {danach}"
        )
        assert laeuft_bis in {a.valid_to for a in wiederanlauf}, (
            f"schon der gekappte Wiederanlauf-Zyklus muss die weiter gueltige, vor dem "
            f"Ausfall gesehene Warnung wieder mitbringen (der Bestand haelt sie bis zu "
            f"ihrem Ablauf, nicht bis 23h nach dem letzten Sehen). Erhalten: "
            f"{wiederanlauf}; AT-Fensterbreiten (h): {_fensterbreiten_h(zaehler, 'AT')}"
        )
        assert laeuft_bis in {a.valid_to for a in danach}, (
            f"die mehrtaegige Warnung gilt noch bis {laeuft_bis:%d.%m. %H:%M} und war "
            f"vor dem Ausfall bereits gesehen -- sie MUSS im Briefing nach dem "
            f"Wiederanlauf weiter erscheinen, sonst meldet der Dienst stillschweigend "
            f"'keine Warnung' bei bestehender Gefahr. Erhalten im Wiederanlauf-Zyklus: "
            f"{wiederanlauf}; im Folgezyklus: {danach}"
        )
        bestand_ids = {
            schluessel[0] for schluessel in meteoalarm._country_store("AT")["features"]
        }
        assert "villach-hitze-mehrtaegig" in bestand_ids, (
            f"die weiter gueltige Warnung muss im Bestand stehen, erhalten: {bestand_ids}"
        )
        assert "villach-hitze-kurz" not in bestand_ids, (
            f"die abgelaufene Warnung muss den Bestand verlassen (Obergrenze gegen "
            f"unbegrenztes Wachstum), erhalten: {bestand_ids}"
        )
        assert abgelaufen_seit not in {a.valid_to for a in danach}, (
            f"eine seit {abgelaufen_seit:%d.%m. %H:%M} abgelaufene Warnung darf nicht "
            f"mehr im Briefing stehen. Erhalten: {danach}"
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


# ---------------------------------------------------------------------------
# Das Ausfall-Signal gehoert echten Stoerungen (Fix-Loop 5, PO-Entscheidung
# 2026-07-30 an Issue #1348).
#
# Die Vorstufen banden den Hinweis "amtliche Warnungen aktuell nicht abrufbar"
# an einen Bestands-Eintrag, der laenger nicht frisch im Index gesehen wurde --
# erst als gezielte Rueckfrage (Fix-Loop 3, riss AC-2 und liess Eintraege
# verhungern), dann als reine Kennzeichnung (Fix-Loop 4). Gemessen stand der
# Hinweis damit in 81,9 % aller Zyklen eines 3-Tage-Laufs, sobald irgendwo eine
# mehrtaegige Warnung lief -- OHNE jede Stoerung. Beides ist zurueckgebaut.
# Geprueft wird jetzt die Anforderung selbst: eine laufende mehrtaegige Warnung
# loest den Hinweis NICHT aus, eine echte Stoerung weiterhin schon.
# ---------------------------------------------------------------------------

_MEHRTAEGIG_GUELTIG_BIS = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)  # 5 Tage
_CAP_MEHRTAEGIG = "/cap/villach-heat-mehrtaegig"


def _caches_leeren() -> None:
    from services.official_alerts import meteoalarm

    meteoalarm._index_cache.clear()
    meteoalarm._geometry_cache.clear()
    meteoalarm._cap_cache.clear()


def _stundenlauf(monkeypatch, *, zyklen: int, widerruf_nach_h: "int | None" = 10,
                 neu_gelistet: bool = False, stoerung_ab_zyklus: "int | None" = None) -> list:
    """Dauerbetrieb im Stundentakt (KEIN Ausfall -- die Fortschrittsmarke rueckt
    planmaessig vor, das Auffrisch-Fenster bleibt also eng, genau der
    Kernmechanismus dieser Scheibe). Eine mehrtaegig gueltige Hitzewarnung fuer
    Villach wird 06:00 veroeffentlicht, der erste Zyklus laeuft 07:00.

    ``widerruf_nach_h``: nach so vielen Stunden zieht der Anbieter sie zurueck
    (Vermerk am Index-Feature bei unveraenderter ``hubTime`` -- so, wie es auch
    der AC-5-Test konstruiert); ``None`` = kein Widerruf.
    ``neu_gelistet``: der Anbieter listet die Warnung in JEDEM Zyklus erneut
    (``hubTime`` rueckt mit) -- sie wird also weiterhin frisch gesehen.
    ``stoerung_ab_zyklus``: ab diesem Zyklus antwortet der amtliche Dienst auf
    jede Index-Seite mit HTTP 503 -- eine ECHTE Stoerung (Gegenprobe).

    Liefert je Zyklus ``(sichtbar, nicht_abrufbar)``, gemessen am NUTZER-Pfad
    ``get_official_alerts_with_status()``."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_with_status, meteoalarm

    _caches_leeren()
    feed, zaehler = _AufgezeichneterFeed(), _Zaehler()
    server, thread = _server_starten(
        feed, zaehler, {_CAP_MEHRTAEGIG: _cap_mit_ablauf(_MEHRTAEGIG_GUELTIG_BIS)})
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        port = server.server_port
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{port}")
        veroeffentlicht = datetime(2026, 7, 15, 6, 0)
        orig = _feature(port, "villach-hitze-mehrtaegig", veroeffentlicht,
                        cap_key="villach-heat-mehrtaegig")
        feed.add("AT", orig)

        clock = _FakeClock(datetime(2026, 7, 15, 7, 0, tzinfo=timezone.utc))
        _uhr_einsetzen(monkeypatch, clock)
        oa_base._REGISTERED_SOURCES.append(meteoalarm.MeteoAlarmSource())

        verlauf = []
        for stunde in range(zyklen):
            jetzt_naiv = clock.now.replace(tzinfo=None)
            if stoerung_ab_zyklus is not None and stunde >= stoerung_ab_zyklus:
                feed.stoerungen[("AT", 1)] = {"status": 503}
            if (widerruf_nach_h is not None
                    and jetzt_naiv >= veroeffentlicht + timedelta(hours=widerruf_nach_h)):
                orig["properties"]["supersededByAlertId"] = "villach-hitze-neu"
                orig["properties"]["supersededAt"] = (
                    veroeffentlicht + timedelta(hours=widerruf_nach_h)).strftime(_QUERY_FMT)
            if neu_gelistet:
                orig["properties"]["hubTime"] = (
                    jetzt_naiv - timedelta(minutes=5)).strftime(_QUERY_FMT)
            alerts, unavailable = get_official_alerts_with_status(*VILLACH, now=clock.now)
            verlauf.append((any(a.hazard == "extreme_heat" for a in alerts), unavailable))
            clock.advance(hours=1)
        return verlauf
    finally:
        server.shutdown()
        thread.join(timeout=2)
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


def test_laufende_mehrtaegige_warnung_loest_keinen_ausfall_hinweis_aus(monkeypatch):
    """PO-Entscheidung 2026-07-30 (Kommentar an Issue #1348): Der Hinweis
    "amtliche Warnungen aktuell nicht abrufbar" darf NUR bei einer echten
    Luecke erscheinen -- ein Sicherheitshinweis, der fast immer dasteht, wird
    ueberlesen.

    GIVEN eine mehrtaegig gueltige amtliche Hitzewarnung laeuft und der
    Anbieter listet sie nach ihrer Veroeffentlichung nicht erneut (der Regelfall
    ausserhalb des schmalen Auffrisch-Fensters), WHEN drei Tage lang im
    Stundentakt Briefings gerendert werden und der amtliche Dienst dabei ohne
    jede Stoerung antwortet, THEN traegt KEIN einziger Zyklus den Hinweis -- und
    die Warnung ist in jedem Zyklus sichtbar.

    Gegenprobe im selben Test: bricht der Abruf ab Zyklus 10 wirklich weg
    (HTTP 503), traegt jeder Zyklus danach den Hinweis. Das Signal bleibt also
    wirksam, es haengt nur wieder ausschliesslich an echten Stoerungen."""
    verlauf = _stundenlauf(monkeypatch, zyklen=72, widerruf_nach_h=None)

    mit_hinweis = [i for i, (_s, unavailable) in enumerate(verlauf) if unavailable]
    assert not mit_hinweis, (
        f"eine laufende mehrtaegige Warnung ist KEINE Stoerung: der Dienst antwortet in "
        f"jedem dieser 72 Zyklen vollstaendig. Der Hinweis erschien trotzdem in "
        f"{len(mit_hinweis)} von 72 Zyklen ({100 * len(mit_hinweis) / 72:.1f} %) -- "
        f"Zyklen: {mit_hinweis}"
    )
    assert all(sichtbar for sichtbar, _u in verlauf), (
        f"die Warnung gilt noch mehrere Tage und darf in KEINEM Zyklus still "
        f"verschwinden (Adversary F004). Verlauf (sichtbar, nicht_abrufbar): {verlauf}"
    )

    gestoert = _stundenlauf(monkeypatch, zyklen=14, widerruf_nach_h=None,
                            stoerung_ab_zyklus=10)
    assert not any(unavailable for _s, unavailable in gestoert[:10]), (
        f"Aufbaupruefung: vor der Stoerung darf kein Hinweis stehen. Verlauf: {gestoert}"
    )
    assert all(unavailable for _s, unavailable in gestoert[10:]), (
        f"eine echte Stoerung (HTTP 503 auf jede Index-Seite) MUSS den Hinweis weiterhin "
        f"ausloesen -- sonst wird ein Ausfall als 'keine Warnung' ausgeliefert. Verlauf: "
        f"{gestoert}"
    )
    # Und genau darin liegt das Gewicht des Hinweises: waehrend eines
    # vollstaendigen Ausfalls liefert das Land gar keine Warnung mehr (der
    # Bestand wird nur ueber eine erfolgreiche Antwort ausgespielt) -- der
    # Hinweis ist dann die EINZIGE Information, die der Nutzer bekommt. Deshalb
    # darf er nicht durch Dauerpraesenz abgestumpft werden.
    assert not any(sichtbar for sichtbar, _u in gestoert[10:]), (
        f"Aufbaupruefung zur Aussagekraft: waehrend des Ausfalls kann fuer AT nichts "
        f"ausgeliefert werden -- der Hinweis traegt die Information allein. Verlauf: "
        f"{gestoert}"
    )


def test_frisch_gesehener_rueckzug_entfernt_die_warnung_sofort(monkeypatch):
    """AC-5 im Dauerbetrieb: GIVEN der Anbieter listet eine mehrtaegige Warnung
    in jedem Zyklus erneut und zieht sie nach 10 Stunden zurueck
    (Ueberholt-Vermerk am erneut gelisteten Feature), WHEN die naechsten
    Briefings gerendert werden, THEN ist sie ab dem ersten Zyklus, der den
    Vermerk sieht, verschwunden -- ohne Ausfall-Hinweis, denn der Abruf selbst
    hat einwandfrei funktioniert."""
    verlauf = _stundenlauf(monkeypatch, zyklen=14, widerruf_nach_h=10, neu_gelistet=True)

    assert all(sichtbar for sichtbar, _u in verlauf[:9]), (
        f"Aufbaupruefung: vor dem Rueckzug muss die Warnung sichtbar sein. Verlauf: "
        f"{verlauf}"
    )
    assert not any(sichtbar for sichtbar, _u in verlauf[9:]), (
        f"ein frisch im Index gesehener Rueckzug MUSS den Eintrag sofort entfernen -- "
        f"sonst zeigt das Briefing eine Warnung, die es nicht mehr gibt. Verlauf: "
        f"{verlauf}"
    )
    assert not any(unavailable for _s, unavailable in verlauf), (
        f"der Abruf lief in jedem Zyklus vollstaendig -- kein Zyklus darf einen Ausfall "
        f"behaupten. Verlauf: {verlauf}"
    )


def _ortsrelevant_machen(feed: _AufgezeichneterFeed, port: int, tag0: datetime,
                         anzahl: int) -> None:
    """Wandelt ``anzahl`` Grundrauschen-Warnungen des Sturmtags in
    ortsrelevante, mehrtaegig gueltige Warnungen um -- unter BEIBEHALTUNG ihrer
    Veroeffentlichungs-Zeitpunkte.

    Damit ist die Seiten-Arithmetik des Index (Zeilen je Antwortfenster,
    Seitengroesse 100) fuer jedes ``anzahl`` identisch: was die Messung unten
    vergleicht, ist allein die Mechanik -- nicht eine zufaellig ueberschrittene
    Seitengrenze."""
    fenster = (tag0 + timedelta(hours=1), tag0 + timedelta(hours=4))
    ersetzt = 0
    for i, alt in enumerate(feed.features["AT"]):
        if ersetzt >= anzahl:
            break
        hub = datetime.strptime(alt["properties"]["hubTime"], _QUERY_FMT)
        if not (fenster[0] <= hub < fenster[1]):
            continue
        feed.features["AT"][i] = _feature(
            port, f"villach-mehrtaegig-{ersetzt:03d}", hub, cap_key="villach-heat-mehrtaegig")
        ersetzt += 1
    assert ersetzt == anzahl, f"Testaufbau: nur {ersetzt} von {anzahl} Warnungen ersetzt"


def _gewittertag_abrufe(monkeypatch, anzahl: int) -> int:
    """Echte Index-Abrufe eines 24-Stunden-Gewittertags (15-Minuten-Takt wie
    heute durch die Alarmpruefung), mit ``anzahl`` gleichzeitig gueltigen,
    ortsrelevanten mehrtaegigen Warnungen."""
    from services.official_alerts import meteoalarm

    _caches_leeren()
    feed, zaehler = _AufgezeichneterFeed(), _Zaehler()
    server, thread = _server_starten(
        feed, zaehler, {_CAP_MEHRTAEGIG: _cap_mit_ablauf(_MEHRTAEGIG_GUELTIG_BIS)})
    try:
        port = server.server_port
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{port}")
        tag0 = datetime(2026, 7, 15, 0, 0)
        _grundrauschen_eines_gewittertags(feed, port, tag0)
        _ortsrelevant_machen(feed, port, tag0, anzahl)

        clock = _FakeClock(tag0.replace(tzinfo=timezone.utc))
        _uhr_einsetzen(monkeypatch, clock)
        quelle = meteoalarm.MeteoAlarmSource()
        for _viertelstunde in range(96):  # 24h im 15-Minuten-Takt
            quelle.fetch(*VILLACH)
            clock.advance(minutes=15)
        return zaehler.index_abrufe
    finally:
        server.shutdown()
        thread.join(timeout=2)
        _caches_leeren()


def test_abrufzahl_haengt_nicht_an_der_zahl_gueltiger_warnungen(monkeypatch):
    """AC-2 (Fix-Loop 4): GIVEN dasselbe kalibrierte 24-Stunden-Gewittertagsprofil
    und einmal 0, einmal 15, einmal 60 gleichzeitig gueltige, ortsrelevante
    mehrtaegige Warnungen (plausibel bei einer landesweiten, bezirksweise
    ausgesprochenen Hitzewelle -- der Bestand ist laenderweit geteilt, nicht pro
    Tour), WHEN der Dienst 24 Stunden im heutigen Aufrufmuster laeuft, THEN ist
    die Zahl der echten Abrufe in allen drei Faellen GLEICH und unter 100.

    Das war der Kern von Adversary F007: mit der Rueckfrage-Mechanik aus
    Fix-Loop 3 wuchs der Verbrauch nahezu linear mit der Zahl angezeigter
    Warnungen (gemessen 114-146 Abrufe/24h bei n=30-80, AC-2 gerissen). Seit sie
    zurueckgebaut ist, kostet eine angezeigte Warnung keinen eigenen Abruf mehr
    -- die Grundlast ist von ihrer Zahl entkoppelt."""
    zahlen = {anzahl: _gewittertag_abrufe(monkeypatch, anzahl) for anzahl in (0, 15, 60)}

    assert len(set(zahlen.values())) == 1, (
        f"die Abrufzahl muss unabhaengig von der Zahl gleichzeitig gueltiger Warnungen "
        f"sein, gemessen (Warnungen -> Abrufe/24h): {zahlen}"
    )
    assert max(zahlen.values()) < 100, (
        f"24h Gewittertag muessen unter 100 echte Abrufe bleiben, gemessen: {zahlen}"
    )


def test_f001_gekappte_rueckschau_meldet_nicht_abrufbar(monkeypatch):
    """F001-3: GIVEN der Rueckstand ist groesser als die Kaltstart-Breite (die
    Rueckschau wird also gekappt -- ein Stueck Vergangenheit bleibt
    ungeprueft), WHEN das Briefing fuer einen betroffenen Ort gerendert wird,
    THEN meldet die Auskunft "nicht abrufbar" statt faelschlich "keine
    Warnung"; der Folgezyklus faengt sich wieder von selbst (keine dauerhafte
    Sackgasse)."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_with_status, meteoalarm

    feed, zaehler = _AufgezeichneterFeed(), _Zaehler()
    server, thread = _server_starten(feed, zaehler, {})
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        port = server.server_port
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{port}")
        jetzt = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
        for i in range(5):
            feed.add("AT", _feature(port, f"ferne-warnung-{i}",
                                    datetime(2026, 7, 15, 11, 30) + timedelta(minutes=i),
                                    geometry_key="vorarlberg", bbox=_FAR_BBOX))

        clock = _FakeClock(jetzt)
        _uhr_einsetzen(monkeypatch, clock)
        oa_base._REGISTERED_SOURCES.append(meteoalarm.MeteoAlarmSource())
        _marke_haengt_seit("AT", jetzt, tage=44)

        _alerts, unavailable = get_official_alerts_with_status(*VILLACH, now=jetzt)

        assert unavailable is True, (
            "wurde die Rueckschau gekappt, fehlt dem Zyklus ein Stueck Vergangenheit -- "
            "das muss wie ein abgebrochener Zyklus als 'nicht abrufbar' erscheinen, "
            "sonst wird eine Luecke still als 'keine Warnung' ausgeliefert"
        )

        clock.advance(hours=1)  # naechster Zeitslot, Rueckstand jetzt wieder klein
        _alerts2, unavailable2 = get_official_alerts_with_status(*VILLACH, now=clock.now)

        assert unavailable2 is False, (
            f"nach dem einmal gekappten Zyklus muss sich der Dienst von selbst fangen -- "
            f"sonst meldet er dauerhaft 'nicht abrufbar', ohne dass die Kappung je "
            f"aufgeholt wuerde. AT-Fensterbreiten (h): {_fensterbreiten_h(zaehler, 'AT')}"
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)
