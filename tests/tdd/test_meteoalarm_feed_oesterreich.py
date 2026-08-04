"""TDD RED — MeteoAlarm Österreich: Feed-Bestandsquelle statt EDR-Index (Issue #1445 S3).

SPEC: docs/specs/modules/feat_1445_s3_oesterreich_feed.md ("## Acceptance
Criteria", AC-1 bis AC-8)

Pruefling ist ``src/services/official_alerts/meteoalarm_feed.py`` -- existiert
bereits fuer Italien (Issue #1445 S1), bekommt in dieser Scheibe einen
Land-Parameter (``MeteoAlarmFeedSource("AT"|"IT")``) sowie die AT-spezifische
Drei-Zustands-Zonenauflösung ``_zone_for_point_at()``. In der RED-Phase
schlagen ALLE Tests dieser Datei fehl: entweder weil ``MeteoAlarmFeedSource``
noch KEINEN Konstruktor-Parameter akzeptiert (``TypeError``) oder weil
``_zone_for_point_at``/``_FEED_PATHS`` noch nicht existieren (``AttributeError``).
``_assert_pruefling_aus_diesem_baum()`` belegt bei jedem Test, dass der
Pruefling aus DIESEM Baum stammt (Projektregel #1409).

Kein Mock-Theater, kein echtes Netz:
- **Fake-Transport = echte lokale HTTP-Server** (``http.server``, Muster aus
  ``test_meteoalarm_feed_italien.py``/``test_issue_1085_geosphere_warn.py``):
  ``_JsonServer`` (Feed, ein Pfad), ``_DualPathServer`` (Feed, ZWEI Pfade --
  noetig, weil ``FEED_BASE_URL`` fuer IT UND AT ein gemeinsames Modul-Attribut
  ist) und ``_ZamgServer`` (ZAMG-Ersatz, routet nach gerundeter Koordinate wie
  der echte ``_round_coord``-Cache-Schluessel). Jeder Server ZAEHLT echte
  Treffer -- ein Cache-Treffer erreicht ihn nie.
- **Aufgezeichnete Fixture:** ``tests/fixtures/meteoalarm_feed/feed_austria_sample.json``
  -- 6 reale, unveraenderte Eintraege aus einem echten Vollabruf von
  ``https://feeds.meteoalarm.org/api/v1/warnings/feeds-austria`` (2026-07-31,
  Herkunft/Auswahl s. README.md im selben Verzeichnis), darunter zwingend eine
  gueltige Warnung fuer AT707 (Lienz/Sillian, Karnischer Hoehenweg).
- **ZAMG-Antwortform:** live gegen ``https://warnungen.zamg.at`` verifiziert
  (2026-08-01, s. Bericht dieser RED-Phase): ``properties.location.properties``
  traegt ``gemeindenr`` (Sillian: 70728, Innsbruck: 70101) als GANZZAHL, nicht
  als String -- die Spec-Formulierung ``gemeindenr[:3]`` setzt eine
  String-Slicing-Operation voraus, die auf einem ``int`` einen ``TypeError``
  wirft. Jede ``_zamg_body()``-Antwort dieser Datei traegt ``gemeindenr``
  bewusst als ``int``, damit dieser Formfehler nicht unbemerkt bleibt.

Reale, live verifizierte Punkt->Zone-Paare (Spec Implementation Details
Punkt 2, hier als Testkonstanten verwendet): Sillian 70728->AT707 (Karnischer
Hoehenweg, italienische Seite/Sillianer Huette liefert HTTP 404), Wien
90101->AT901, Graz 60101->AT601, Eisenstadt 10101->AT101.
"""
from __future__ import annotations

import http.server
import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import pytest

from services.official_alerts.models import OfficialAlert

# Live-Schicht (Test-Politik, CLAUDE.md): braucht echtes Netz/echte Dienste --
# lief im Kern nie gruen (CI-Vermessung 2026-08-04, #1196) und gehoert per
# Marker in den /e2e-verify-Lauf, nicht auf eine Ausnahmeliste.
pytestmark = pytest.mark.live

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "meteoalarm_feed"

# Reale, live verifizierte Punkte (2026-08-01, s. Modul-Docstring).
SILLIAN = (46.7597, 12.4177)  # gemeindenr 70728 -> AT707 (Karnischer Hoehenweg)
WIEN = (48.2082, 16.3738)  # gemeindenr 90101 -> AT901
GRAZ = (47.0707, 15.4395)  # gemeindenr 60101 -> AT601
EISENSTADT = (47.8455, 16.5253)  # gemeindenr 10101 -> AT101 (in Sample-Fixture OHNE Warnung)
# Innerhalb der INCA-Bbox, aber real ausserhalb Oesterreichs -- live verifiziert
# HTTP 404 (2026-08-01), identischer Punkt wie tests/tdd/test_issue_1085_geosphere_warn.py.
AUSSERHALB_AT = (46.85, 9.53)
INNSBRUCK = (47.2692, 11.4041)
PARIS = (48.8566, 2.3522)  # ausserhalb der INCA-Bbox
HAMBURG = (53.55, 9.99)  # ausserhalb der INCA-Bbox

TEST_NOW = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)

# Aufnahmezeitpunkt der AC-5-Aequivalenz-Aufzeichnung: ALLE DREI Seiten wurden
# zu dieser Minute ueber den echten Produktivcode gezogen -- die EDR-Seite nach
# ``edr_snapshot_at.json``, der zugehoerige Feed-Bestand nach
# ``feed_austria_equivalence.json``, die Zonenzuordnung nach
# ``zamg_snapshot_at.json``. Bewusst NICHT ``TEST_NOW``: das ist auf die
# aeltere, kuratierte ``feed_austria_sample.json`` (2026-07-31) abgestimmt und
# haette mit dieser Aufzeichnung nichts zu tun.
AUFNAHME_UTC = datetime(2026, 8, 1, 16, 19, 43, tzinfo=timezone.utc)


def _assert_pruefling_aus_diesem_baum() -> None:
    """#1409: der importierte Pruefling MUSS aus dem Baum DIESER Testdatei
    stammen -- sonst misst der Test aus einem Worktree die unveraenderte
    Hauptrepo-Kopie und meldet falsches Gruen."""
    from services.official_alerts import meteoalarm_feed

    modul = Path(meteoalarm_feed.__file__).resolve()
    assert str(modul).startswith(str(_REPO_ROOT)), (
        f"Pruefling {modul} liegt ausserhalb von {_REPO_ROOT} -- der Test wuerde "
        f"eine fremde Kopie messen"
    )


@pytest.fixture(autouse=True)
def _caches_leeren():
    """Frischer ZAMG- UND Feed-Cache je Test -- No-Op, solange die Module noch
    unveraendert sind (RED-Phase). Zwingend, weil mehrere Tests DIESELBEN
    Koordinaten (z.B. SILLIAN) mit UNTERSCHIEDLICHEN simulierten ZAMG-Antworten
    verwenden -- ohne Leerung wuerde der zweite Test den gecachten Wert des
    ersten sehen."""
    from services.official_alerts import geosphere_warn

    geosphere_warn._cache.clear()
    try:
        from services.official_alerts import meteoalarm_feed
        meteoalarm_feed._cache.clear()
    except ImportError:
        pass
    yield
    geosphere_warn._cache.clear()
    try:
        from services.official_alerts import meteoalarm_feed
        meteoalarm_feed._cache.clear()
    except ImportError:
        pass


def _load_sample_feed() -> dict:
    return json.loads((_FIXTURES / "feed_austria_sample.json").read_text(encoding="utf-8"))


def _load_equivalence_feed() -> dict:
    """AUSSCHLIESSLICH fuer das AC-5-Aequivalenz-Gate: der Feed-Bestand DERSELBEN
    Minute wie ``edr_snapshot_at.json``/``zamg_snapshot_at.json``
    (2026-08-01T16:19:43Z), Eintraege 1:1 aus dem Vollabruf.
    ``feed_austria_sample.json`` taugt dafuer NICHT -- das ist eine fuer
    Testabdeckung kuratierte Auswahl von 6 aus 1220 Eintraegen, und ein
    Bruchteil kann strukturell nie Obermenge eines vollstaendigen EDR-Index
    sein (gemessen 2026-08-01 mit der Sample-Fixture: alle 8 Tourpunkte
    meldeten Abweichungen). Alle uebrigen Tests dieser Datei benutzen
    weiterhin ``feed_austria_sample.json``."""
    return json.loads((_FIXTURES / "feed_austria_equivalence.json").read_text(encoding="utf-8"))


def _zamg_body(gemeindenr: int, name: str) -> dict:
    """Baut eine ZAMG-Erfolgsantwort in der live verifizierten Form
    (2026-08-01): ``gemeindenr`` als GANZZAHL neben ``name``, Geschwister von
    ``properties.location.properties.name`` (bereits von
    ``geosphere_warn._extract_alerts()`` gelesen)."""
    return {
        "type": "Feature",
        "properties": {
            "location": {
                "type": "Municipal",
                "properties": {"gemeindenr": gemeindenr, "name": name, "urlname": name.lower()},
            },
            "warnings": [],
        },
    }


class _Zaehler:
    """Zaehlt ausschliesslich Anfragen, die den lokalen Server WIRKLICH erreichen."""

    def __init__(self) -> None:
        self.treffer = 0
        self.pfade: list[str] = []


class _JsonServer:
    """Echter lokaler HTTP-Server (kein Mock): liefert ``.body`` als JSON oder
    ``.fail_status`` als festen Fehlerstatus. Ein Pfad -- fuer den AT-Feed
    ALLEIN ausreichend (analog ``test_meteoalarm_feed_italien.py``)."""

    def __init__(self, body: dict, *, fail_status: "int | None" = None) -> None:
        self.body = body
        self.fail_status = fail_status
        self.zaehler = _Zaehler()
        aussen = self

        class _Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 - stdlib-Signatur
                aussen.zaehler.treffer += 1
                aussen.zaehler.pfade.append(self.path)
                if aussen.fail_status is not None:
                    self.send_response(aussen.fail_status)
                    self.end_headers()
                    return
                payload = json.dumps(aussen.body).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_args):  # Testlauf-Output nicht zumuellen
                pass

        self._httpd = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    @property
    def port(self) -> int:
        return self._httpd.server_port

    def shutdown(self) -> None:
        self._httpd.shutdown()
        self._thread.join(timeout=2)


class _DualPathServer:
    """Echter lokaler HTTP-Server, der ZWEI Pfade (feeds-austria/feeds-italy)
    unterschiedlich beantwortet -- noetig fuer AC-8 (gleichzeitiger IT-Ausfall):
    ``FEED_BASE_URL`` ist EIN gemeinsames Modul-Attribut fuer beide Laender
    (Produktion: ein Host ``feeds.meteoalarm.org``, zwei Pfade)."""

    def __init__(
        self,
        path_bodies: "dict[str, dict]",
        path_fail: "dict[str, int] | None" = None,
    ) -> None:
        self.path_bodies = path_bodies
        self.path_fail = path_fail or {}
        self.zaehler = _Zaehler()
        aussen = self

        class _Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                aussen.zaehler.treffer += 1
                aussen.zaehler.pfade.append(self.path)
                path_only = self.path.split("?", 1)[0]
                if path_only in aussen.path_fail:
                    self.send_response(aussen.path_fail[path_only])
                    self.end_headers()
                    return
                body = aussen.path_bodies.get(path_only, {"warnings": []})
                payload = json.dumps(body).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_args):
                pass

        self._httpd = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    @property
    def port(self) -> int:
        return self._httpd.server_port

    def shutdown(self) -> None:
        self._httpd.shutdown()
        self._thread.join(timeout=2)


class _ZamgServer:
    """Echter lokaler HTTP-Server als ZAMG-Ersatz (``warnungen.zamg.at``):
    routet nach der GERUNDETEN Koordinate aus dem Query-String (wie
    ``geosphere_warn._round_coord``) auf eine vorab hinterlegte Antwort --
    entweder ein JSON-Body (Erfolg) oder ein fester Fehlerstatus (int).
    ``.responses`` ist zwischen zwei Anfragen mutierbar (Restrisiko-Test:
    404-Cache maskiert einen NACHFOLGENDEN echten Ausfall)."""

    def __init__(self, responses: "dict[tuple[float, float], object]") -> None:
        self.responses = responses
        self.zaehler = _Zaehler()
        aussen = self

        class _Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                aussen.zaehler.treffer += 1
                aussen.zaehler.pfade.append(self.path)
                qs = parse_qs(urlparse(self.path).query)
                try:
                    key = (round(float(qs["lat"][0]), 4), round(float(qs["lon"][0]), 4))
                except (KeyError, ValueError, IndexError):
                    key = None
                resp = aussen.responses.get(key)
                if isinstance(resp, int):
                    self.send_response(resp)
                    self.end_headers()
                    return
                if resp is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                payload = json.dumps(resp).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_args):
                pass

        self._httpd = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    @property
    def port(self) -> int:
        return self._httpd.server_port

    def shutdown(self) -> None:
        self._httpd.shutdown()
        self._thread.join(timeout=2)


def _round4(lat: float, lon: float) -> "tuple[float, float]":
    from services.official_alerts.geosphere_warn import _round_coord
    return _round_coord(lat, lon)


# ---------------------------------------------------------------------------
# Grundlagen: Konstruktor-Parameter, Feed-Pfade, Quellenname, Bbox-Vorfilter.
# ---------------------------------------------------------------------------

def test_feed_paths_enthaelt_beide_laender_mit_den_richtigen_pfaden():
    """Spec Implementation Details Punkt 1: ``_FEED_PATHS`` loest ``AT`` auf
    ``feeds-austria`` und ``IT`` (unveraendert seit S1) auf ``feeds-italy``
    auf."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    assert meteoalarm_feed._FEED_PATHS["AT"] == "/api/v1/warnings/feeds-austria"
    assert meteoalarm_feed._FEED_PATHS["IT"] == "/api/v1/warnings/feeds-italy"


def test_source_name_und_land_parameter_at():
    """``MeteoAlarmFeedSource("AT")`` muss instanziierbar sein UND weiterhin
    ``name == "meteoalarm_feed"`` liefern -- ein Code, zwei Instanzen (Spec
    Implementation Details Punkt 1)."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    source = meteoalarm_feed.MeteoAlarmFeedSource("AT")
    assert source.name == "meteoalarm_feed"


def test_covers_at_inca_bbox_ohne_departement_ausschluss():
    """Spec Implementation Details Punkt 5: AT braucht -- anders als IT --
    KEINEN Grenz-Ausschluss in ``covers()``, nur die grobe INCA-Bbox."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    source = meteoalarm_feed.MeteoAlarmFeedSource("AT")
    assert source.covers(*INNSBRUCK) is True
    assert source.covers(*PARIS) is False
    assert source.covers(*HAMBURG) is False


# ---------------------------------------------------------------------------
# Die zentrale Pruefung (Spec Implementation Details Punkt 2): drei Zustaende,
# sauber getrennt. ``_zone_for_point_at()`` liefert ein Tupel
# ``(zone: str | None, fetch_failed: bool)``:
#   Fall 3 (Erfolg, Zone bestimmbar):        (zone, False)
#   Fall 1 (ZAMG 404, nicht zustaendig):     (None, False)
#   Fall 2 (ZAMG-Abruf real fehlgeschlagen): (None, True)
# ---------------------------------------------------------------------------

def test_zone_for_point_at_fall3_erfolg_liefert_zone_ohne_fetch_fehler(monkeypatch):
    """Fall 3: GIVEN ZAMG liefert erfolgreich eine ``gemeindenr`` (Sillian,
    70728) fuer einen oesterreichischen Punkt, WHEN ``_zone_for_point_at()``
    aufgerufen wird, THEN liefert es die daraus abgeleitete EMMA-Zone AT707
    UND ``fetch_failed=False``."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import geosphere_warn, meteoalarm_feed

    server = _ZamgServer({_round4(*SILLIAN): _zamg_body(70728, "Sillian")})
    try:
        monkeypatch.setattr(geosphere_warn, "GEOSPHERE_WARN_URL", f"http://127.0.0.1:{server.port}")

        zone, fetch_failed = meteoalarm_feed._zone_for_point_at(*SILLIAN)

        assert zone == "AT707", (
            f"gemeindenr 70728 (int, LIVE VERIFIZIERT 2026-08-01) muss auf "
            f"AT707 abgebildet werden -- 'AT' + str(gemeindenr)[:3]. Erhalten: {zone!r}"
        )
        assert fetch_failed is False
    finally:
        server.shutdown()


def test_zone_for_point_at_fall1_404_liefert_keine_zone_ohne_fetch_fehler(monkeypatch):
    """Fall 1: GIVEN ZAMG antwortet mit HTTP 404 (nicht zustaendig, ueber
    ``not_covered_statuses`` als ``{}`` gecacht), WHEN ``_zone_for_point_at()``
    aufgerufen wird, THEN liefert es KEINE Zone UND ``fetch_failed=False`` --
    dieser Fall darf NICHT mit Fall 2 verwechselt werden."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import geosphere_warn, meteoalarm_feed

    server = _ZamgServer({_round4(*AUSSERHALB_AT): 404})
    try:
        monkeypatch.setattr(geosphere_warn, "GEOSPHERE_WARN_URL", f"http://127.0.0.1:{server.port}")

        zone, fetch_failed = meteoalarm_feed._zone_for_point_at(*AUSSERHALB_AT)

        assert zone is None
        assert fetch_failed is False, (
            "ein ZAMG-404 (nicht zustaendig) darf NICHT als Fetch-Fehlschlag "
            "zaehlen -- das waere Fall 2 statt Fall 1 (Spec Implementation "
            "Details Punkt 2)"
        )
    finally:
        server.shutdown()


def test_zone_for_point_at_fall2_fetch_fehlschlag_liefert_keine_zone_mit_fetch_fehler(monkeypatch):
    """Fall 2: GIVEN der ZAMG-Abruf schlaegt real fehl (HTTP 500, echter
    Dienstfehler -- KEIN 404), WHEN ``_zone_for_point_at()`` aufgerufen wird,
    THEN liefert es KEINE Zone UND ``fetch_failed=True``."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import geosphere_warn, meteoalarm_feed

    server = _ZamgServer({_round4(*SILLIAN): 500})
    try:
        monkeypatch.setattr(geosphere_warn, "GEOSPHERE_WARN_URL", f"http://127.0.0.1:{server.port}")

        zone, fetch_failed = meteoalarm_feed._zone_for_point_at(*SILLIAN)

        assert zone is None
        assert fetch_failed is True, (
            "ein echter ZAMG-Dienstfehler (HTTP 500) MUSS als Fetch-Fehlschlag "
            "zaehlen -- Fall 2, nicht Fall 1"
        )
    finally:
        server.shutdown()


# ---------------------------------------------------------------------------
# F3 (Adversary-Fund, Issue #1445 S3 Fix-Loop, ``meteoalarm_feed.py:97``):
# ``str.isdigit()`` akzeptiert auch Nicht-ASCII-Ziffern (z.B. arabisch-indisch,
# hochgestellt) -- die Formpruefung muss auf ASCII-Ziffern verschaerft werden,
# ohne echte, live verifizierte Gemeindenummern zurueckzuweisen.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "unbrauchbare_gemeindenr",
    ["٧٠٧٢٨", "⁷⁰⁷"],
    ids=["arabisch-indische-ziffern", "hochgestellte-ziffern"],
)
def test_ist_auswertbare_gemeindenr_weist_nicht_ascii_ziffern_zurueck(unbrauchbare_gemeindenr):
    """F3: GIVEN eine ``gemeindenr`` aus Nicht-ASCII-Ziffern (z.B.
    arabisch-indisch ``"٧٠٧٢٨"`` oder hochgestellt ``"⁷⁰⁷"``), WHEN
    ``_ist_auswertbare_gemeindenr()`` aufgerufen wird, THEN liefert es
    ``False`` -- ``str.isdigit()`` allein akzeptiert diese Zeichen faelschlich
    und wuerde eine Zone wie ``"AT٧٠٧"`` erzeugen, die nie einen echten
    fuenfstelligen EMMA-Code trifft (stille Leere statt ehrlicher Aussage)."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    assert meteoalarm_feed._ist_auswertbare_gemeindenr(unbrauchbare_gemeindenr) is False, (
        f"Nicht-ASCII-Ziffern-Form {unbrauchbare_gemeindenr!r} muss als unbrauchbar "
        f"erkannt werden -- str.isdigit() akzeptiert sie faelschlich als 'numerisch'"
    )


@pytest.mark.parametrize(
    "gueltige_gemeindenr",
    [70728, 90101, 60101, 10101, 70101, 20201, 50510, 50101, 80207, 40101, 30201, 70716, 50628],
    ids=[
        "sillian", "wien", "graz", "eisenstadt", "innsbruck", "villach",
        "tamsweg", "salzburg", "bregenz", "linz", "sankt-poelten", "lienz",
        "zell-am-see",
    ],
)
def test_ist_auswertbare_gemeindenr_akzeptiert_alle_realen_gemeindenummern(gueltige_gemeindenr):
    """Kontrollfall: GIVEN eine der 13 echten, live verifizierten oester-
    reichischen Gemeindenummern, WHEN ``_ist_auswertbare_gemeindenr()``
    aufgerufen wird, THEN liefert es ``True`` -- die F3-Verschaerfung auf
    ASCII-Ziffern darf keinen Fehlalarm bei echten Werten erzeugen."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    assert meteoalarm_feed._ist_auswertbare_gemeindenr(gueltige_gemeindenr) is True, (
        f"echte Gemeindenummer {gueltige_gemeindenr!r} muss weiterhin als "
        f"auswertbar durchgehen"
    )


# ---------------------------------------------------------------------------
# F1 (Adversary-Fund, Issue #1445 S3 Fix-Loop, ``meteoalarm_feed.py:89-113``):
# eine VORHANDENE, aber unbrauchbar geformte ``gemeindenr`` darf NICHT als
# Fall 1 durchrutschen -- sie ist ein Datenfehler und muss denselben
# Sicherheits-Rueckzug wie ein echter Fetch-Fehlschlag ausloesen (Fall 2,
# ``fetch_failed=True``). Vorher liess eine unbrauchbare Gemeindenummer echte
# Warnungen (Sillian/Karnischer Hoehenweg) geraeuschlos verschwinden.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("unbrauchbare_gemeindenr", ["", 0, "12"])
def test_zone_for_point_at_unbrauchbare_gemeindenr_loest_fetch_fehler_statt_fall1_aus(
    unbrauchbare_gemeindenr, monkeypatch
):
    """F1: GIVEN ZAMG liefert eine VORHANDENE, aber unbrauchbar geformte
    ``gemeindenr`` (leer, ``0`` oder zu kurz -- keine dieser Formen kann eine
    dreistellige EMMA-Zone liefern, die je einen echten fuenfstelligen
    EMMA-Code matcht), WHEN ``_zone_for_point_at()`` aufgerufen wird, THEN
    liefert es KEINE Zone UND ``fetch_failed=True`` (Fall 2, nicht Fall 1) --
    sonst wuerden echte Warnungen fuer diesen Punkt geraeuschlos
    verschwinden."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import geosphere_warn, meteoalarm_feed

    server = _ZamgServer({_round4(*SILLIAN): _zamg_body(unbrauchbare_gemeindenr, "Sillian")})
    try:
        monkeypatch.setattr(geosphere_warn, "GEOSPHERE_WARN_URL", f"http://127.0.0.1:{server.port}")

        zone, fetch_failed = meteoalarm_feed._zone_for_point_at(*SILLIAN)

        assert zone is None, (
            f"eine unbrauchbar geformte gemeindenr ({unbrauchbare_gemeindenr!r}) darf "
            f"KEINE Zone liefern, erhalten: {zone!r}"
        )
        assert fetch_failed is True, (
            f"eine unbrauchbar geformte gemeindenr ({unbrauchbare_gemeindenr!r}) ist ein "
            f"Datenfehler und MUSS denselben Sicherheits-Rueckzug ausloesen wie ein "
            f"echter Fetch-Fehlschlag (Fall 2) -- sonst rutscht sie als Fall 1 durch "
            f"und echte Warnungen verschwinden spurlos"
        )
    finally:
        server.shutdown()


def test_zone_for_point_at_gemeindenr_fehlt_ganz_bleibt_fall1_ohne_fetch_fehler(monkeypatch):
    """Kontrollfall ``None``: GIVEN ZAMG liefert ``gemeindenr: null`` (das
    Feld fehlt strukturell, keine kaputte Antwort), WHEN
    ``_zone_for_point_at()`` aufgerufen wird, THEN bleibt es Fall 1
    (``fetch_failed=False``) -- unveraendert gegenueber dem F1-Fix, der NUR
    vorhandene, unbrauchbar geformte Werte betrifft."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import geosphere_warn, meteoalarm_feed

    server = _ZamgServer({_round4(*SILLIAN): _zamg_body(None, "Sillian")})
    try:
        monkeypatch.setattr(geosphere_warn, "GEOSPHERE_WARN_URL", f"http://127.0.0.1:{server.port}")

        zone, fetch_failed = meteoalarm_feed._zone_for_point_at(*SILLIAN)

        assert zone is None
        assert fetch_failed is False, (
            "gemeindenr=null bleibt Fall 1 (kein Datenfehler, das Feld fehlt "
            "strukturell) -- NICHT zu verwechseln mit einem vorhandenen, aber "
            "unbrauchbar geformten Wert"
        )
    finally:
        server.shutdown()


def test_zone_for_point_at_gueltige_gemeindenr_bleibt_fall3_kontrollfall(monkeypatch):
    """Kontrollfall gueltig: GIVEN ZAMG liefert eine formgueltige
    ``gemeindenr`` (Sillian, 70728), WHEN ``_zone_for_point_at()`` aufgerufen
    wird, THEN liefert es weiterhin die korrekte Zone AT707 UND
    ``fetch_failed=False`` -- der F1-Fix darf den Normalbetrieb nicht
    beeintraechtigen."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import geosphere_warn, meteoalarm_feed

    server = _ZamgServer({_round4(*SILLIAN): _zamg_body(70728, "Sillian")})
    try:
        monkeypatch.setattr(geosphere_warn, "GEOSPHERE_WARN_URL", f"http://127.0.0.1:{server.port}")

        zone, fetch_failed = meteoalarm_feed._zone_for_point_at(*SILLIAN)

        assert zone == "AT707"
        assert fetch_failed is False
    finally:
        server.shutdown()


def test_f1_sillian_end_zu_ende_gueltige_gemeindenr_liefert_warnungen(monkeypatch):
    """F1 end-zu-ende, Kontrollfall: GIVEN Sillian (Karnischer Hoehenweg) hat
    eine formgueltige ``gemeindenr``, WHEN die amtlichen Warnungen ermittelt
    werden, THEN erscheinen seine echten AT707-Warnungen UND
    ``unavailable=False``."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import geosphere_warn, get_official_alerts_with_status, meteoalarm_feed

    _assert_pruefling_aus_diesem_baum()
    zamg = _ZamgServer({_round4(*SILLIAN): _zamg_body(70728, "Sillian")})
    feed_server = _JsonServer(_load_sample_feed())
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        monkeypatch.setattr(geosphere_warn, "GEOSPHERE_WARN_URL", f"http://127.0.0.1:{zamg.port}")
        monkeypatch.setattr(meteoalarm_feed, "FEED_BASE_URL", f"http://127.0.0.1:{feed_server.port}")
        oa_base._REGISTERED_SOURCES.append(meteoalarm_feed.MeteoAlarmFeedSource("AT"))

        alerts, unavailable = get_official_alerts_with_status(*SILLIAN, now=TEST_NOW)

        assert unavailable is False
        assert alerts, "Sillian muss bei gueltiger gemeindenr seine echten AT707-Warnungen bekommen"
    finally:
        zamg.shutdown()
        feed_server.shutdown()
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


def test_f1_sillian_end_zu_ende_unbrauchbare_gemeindenr_meldet_nicht_abrufbar_statt_stiller_leere(monkeypatch):
    """F1 end-zu-ende, der eigentliche Bug: GIVEN Sillian (Karnischer
    Hoehenweg) hat eine VORHANDENE, aber unbrauchbar geformte ``gemeindenr``
    (leer statt 70728), WHEN die amtlichen Warnungen ermittelt werden, THEN
    meldet das Ergebnis 'nicht abrufbar' -- NICHT eine stille leere Liste,
    die fuenf aktive Warnungen (Gewitter/Hitze) spurlos verschwinden liesse."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import geosphere_warn, get_official_alerts_with_status, meteoalarm_feed

    _assert_pruefling_aus_diesem_baum()
    zamg = _ZamgServer({_round4(*SILLIAN): _zamg_body("", "Sillian")})
    feed_server = _JsonServer(_load_sample_feed())
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        monkeypatch.setattr(geosphere_warn, "GEOSPHERE_WARN_URL", f"http://127.0.0.1:{zamg.port}")
        monkeypatch.setattr(meteoalarm_feed, "FEED_BASE_URL", f"http://127.0.0.1:{feed_server.port}")
        oa_base._REGISTERED_SOURCES.append(meteoalarm_feed.MeteoAlarmFeedSource("AT"))

        alerts, unavailable = get_official_alerts_with_status(*SILLIAN, now=TEST_NOW)

        assert unavailable is True, (
            f"eine vorhandene, aber unbrauchbar geformte gemeindenr MUSS 'nicht "
            f"abrufbar' melden, statt fuenf aktive Warnungen (Gewitter/Hitze) still "
            f"verschwinden zu lassen. Erhalten: alerts={alerts}, "
            f"unavailable={unavailable}"
        )
    finally:
        zamg.shutdown()
        feed_server.shutdown()
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


# ---------------------------------------------------------------------------
# Sicherheitsfrage aus der Spec (Known Limitations, geerbtes Restrisiko F002
# aus #1085): der 404-Cache haelt 24h -- faerbt er einen NACHFOLGENDEN echten
# ZAMG-Ausfall faelschlich als Fall 1 ein? Dieser Test belegt das Risiko
# MESSBAR (er ist bewusst KEIN Fehlschlag-Erwartungstest im Sinne eines zu
# behebenden Bugs dieser Scheibe -- s. Bericht).
# ---------------------------------------------------------------------------

def test_bekanntes_restrisiko_404_cache_maskiert_nachfolgenden_echten_zamg_ausfall(monkeypatch):
    """GIVEN ein Punkt erhaelt zuerst ein ECHTES HTTP-404 von ZAMG (24h als
    Fall 1 gecacht), WHEN ZAMG DANACH (innerhalb der 24h-TTL, OHNE Cache-Reset)
    tatsaechlich ausfaellt (HTTP 500) UND derselbe Punkt erneut abgefragt wird,
    THEN liefert der gecachte 404-Eintrag WEITERHIN Fall 1 -- der echte
    Ausfall bleibt bis zum Cache-Ablauf unsichtbar (geerbtes, dokumentiertes
    Restrisiko F002 aus #1085, ``geosphere_warn.py:82-89``, NICHT Teil dieser
    Scheibe zu beheben)."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import geosphere_warn, meteoalarm_feed

    punkt_key = _round4(*AUSSERHALB_AT)
    server = _ZamgServer({punkt_key: 404})
    try:
        monkeypatch.setattr(geosphere_warn, "GEOSPHERE_WARN_URL", f"http://127.0.0.1:{server.port}")

        zone1, failed1 = meteoalarm_feed._zone_for_point_at(*AUSSERHALB_AT)
        assert zone1 is None and failed1 is False, "Aufbaupruefung: erster Aufruf ist der echte 404-Fall"
        assert server.zaehler.treffer == 1

        # Anbieter faellt jetzt WIRKLICH aus -- OHNE den 24h-404-Cache zu
        # leeren, wie es ein echter ZAMG-Ausfall waehrend der TTL waere.
        server.responses[punkt_key] = 500

        zone2, failed2 = meteoalarm_feed._zone_for_point_at(*AUSSERHALB_AT)

        assert server.zaehler.treffer == 1, (
            "der zweite Aufruf muss aus dem 24h-404-Cache bedient werden -- "
            "der lokale Server (jetzt auf 500 gestellt) darf gar nicht erneut "
            "erreicht werden"
        )
        assert zone2 is None and failed2 is False, (
            "BEKANNTER, GEERBTER BEFUND (F002 aus #1085): ein binnen der "
            "24h-404-TTL nachfolgender ECHTER ZAMG-Ausfall bleibt bis zum "
            "Cache-Ablauf als Fall 1 maskiert statt als Fall 2 erkannt zu "
            "werden. Dieser Test dokumentiert das akzeptierte Risiko messbar."
        )
    finally:
        server.shutdown()


# ---------------------------------------------------------------------------
# AC-1: Ort ausserhalb Oesterreichs (ZAMG-404) -> leere Liste, kein Ausfall.
# ---------------------------------------------------------------------------

def test_ac1_ort_ausserhalb_oesterreichs_liefert_leere_liste_ohne_ausfallhinweis(monkeypatch):
    """AC-1: GIVEN ein Ort liegt nachweislich ausserhalb Oesterreichs (ZAMG
    antwortet mit HTTP 404, 'nicht zustaendig'), WHEN die amtlichen Warnungen
    fuer diesen Ort ermittelt werden, THEN erscheint keine oesterreichische
    Warnung UND das Ergebnis wird NICHT als 'nicht abrufbar' gemeldet."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import geosphere_warn, get_official_alerts_with_status, meteoalarm_feed

    _assert_pruefling_aus_diesem_baum()
    zamg = _ZamgServer({_round4(*AUSSERHALB_AT): 404})
    feed_server = _JsonServer(_load_sample_feed())
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        monkeypatch.setattr(geosphere_warn, "GEOSPHERE_WARN_URL", f"http://127.0.0.1:{zamg.port}")
        monkeypatch.setattr(meteoalarm_feed, "FEED_BASE_URL", f"http://127.0.0.1:{feed_server.port}")
        oa_base._REGISTERED_SOURCES.append(meteoalarm_feed.MeteoAlarmFeedSource("AT"))

        alerts, unavailable = get_official_alerts_with_status(*AUSSERHALB_AT, now=TEST_NOW)

        assert alerts == [], f"ausserhalb Oesterreichs darf keine Warnung erscheinen, erhalten {alerts}"
        assert unavailable is False, (
            f"ein ZAMG-404 (nicht zustaendig) darf NICHT als 'nicht abrufbar' "
            f"gemeldet werden. Erhalten: unavailable={unavailable}"
        )
    finally:
        zamg.shutdown()
        feed_server.shutdown()
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


# ---------------------------------------------------------------------------
# AC-2: ZAMG real nicht erreichbar -> unavailable=True.
# ---------------------------------------------------------------------------

def test_ac2_zamg_nicht_erreichbar_meldet_nicht_abrufbar(monkeypatch):
    """AC-2: GIVEN die oesterreichische Zuordnungsquelle (ZAMG) ist zum
    Abrufzeitpunkt nicht erreichbar (hier: HTTP 500, echter Dienstfehler),
    WHEN die amtlichen Warnungen fuer einen betroffenen oesterreichischen Ort
    ermittelt werden, THEN meldet das Ergebnis 'nicht abrufbar' statt
    faelschlich eine warnungsfreie Lage zu zeigen."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import geosphere_warn, get_official_alerts_with_status, meteoalarm_feed

    _assert_pruefling_aus_diesem_baum()
    zamg = _ZamgServer({_round4(*SILLIAN): 500})
    feed_server = _JsonServer(_load_sample_feed())
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        monkeypatch.setattr(geosphere_warn, "GEOSPHERE_WARN_URL", f"http://127.0.0.1:{zamg.port}")
        monkeypatch.setattr(meteoalarm_feed, "FEED_BASE_URL", f"http://127.0.0.1:{feed_server.port}")
        oa_base._REGISTERED_SOURCES.append(meteoalarm_feed.MeteoAlarmFeedSource("AT"))

        alerts, unavailable = get_official_alerts_with_status(*SILLIAN, now=TEST_NOW)

        assert unavailable is True, (
            f"ein fehlgeschlagener ZAMG-Abruf muss 'nicht abrufbar' melden "
            f"statt faelschlich 'keine Warnung'. Erhalten: alerts={alerts}, "
            f"unavailable={unavailable}"
        )
    finally:
        zamg.shutdown()
        feed_server.shutdown()
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


# ---------------------------------------------------------------------------
# AC-3: Zone eindeutig, aber aktuell keine gueltige Warnung -> leere Liste,
# kein Ausfall.
# ---------------------------------------------------------------------------

def test_ac3_zone_ohne_gueltige_warnung_liefert_leere_liste_ohne_ausfallhinweis(monkeypatch):
    """AC-3: GIVEN ein Ort in Oesterreich (Eisenstadt) ist eindeutig der Zone
    AT101 zugeordnet, fuer die im aktuellen (kuratierten) Feed KEINE Warnung
    steht, WHEN die amtlichen Warnungen fuer diesen Ort ermittelt werden,
    THEN liefert das Ergebnis eine leere, nicht als Ausfall markierte Liste."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import geosphere_warn, get_official_alerts_with_status, meteoalarm_feed

    _assert_pruefling_aus_diesem_baum()
    zamg = _ZamgServer({_round4(*EISENSTADT): _zamg_body(10101, "Eisenstadt")})
    feed_server = _JsonServer(_load_sample_feed())
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        monkeypatch.setattr(geosphere_warn, "GEOSPHERE_WARN_URL", f"http://127.0.0.1:{zamg.port}")
        monkeypatch.setattr(meteoalarm_feed, "FEED_BASE_URL", f"http://127.0.0.1:{feed_server.port}")
        oa_base._REGISTERED_SOURCES.append(meteoalarm_feed.MeteoAlarmFeedSource("AT"))

        alerts, unavailable = get_official_alerts_with_status(*EISENSTADT, now=TEST_NOW)

        assert alerts == [], (
            f"AT101 hat in der Sample-Fixture keine Warnung (s. README.md), "
            f"erhalten {alerts}"
        )
        assert unavailable is False, (
            f"eine erfolgreich aufgeloeste, aber warnungsfreie Zone darf NICHT "
            f"'nicht abrufbar' melden. Erhalten unavailable={unavailable}"
        )
    finally:
        zamg.shutdown()
        feed_server.shutdown()
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


# ---------------------------------------------------------------------------
# AC-4: mehrere Punkte im selben Fenster -> hoechstens EIN Feed-Abruf, KEIN
# zusaetzlicher ZAMG-Abruf ueber das hinaus, was GeoSphereWarnSource ohnehin
# ausgeloest haette, kein Journal-Eintrag gegen api.meteoalarm.org.
# ---------------------------------------------------------------------------

def test_ac4_mehrere_punkte_loesen_nur_einen_feedabruf_und_keine_zusaetzlichen_zamg_abrufe_aus(monkeypatch):
    """AC-4: GIVEN Wien (AT901) und Graz (AT601) werden innerhalb desselben
    Auffrischungsfensters abgefragt (Registrierungsreihenfolge wie in
    ``__init__.py``: GeoSphereWarnSource VOR MeteoAlarmFeedSource("AT"), Spec
    Implementation Details Punkt 4/6), WHEN die amtlichen Warnungen fuer beide
    Orte ermittelt werden, THEN loest hoechstens EIN echter Netzabruf gegen
    den AT-Feed dieses Fenster aus, ZAMG wird NUR je Punkt EINMAL erreicht
    (kein zusaetzlicher Abruf durch MeteoAlarmFeedSource("AT")), UND im
    Diagnose-Journal erscheint kein Eintrag mit host=api.meteoalarm.org."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import geosphere_warn, get_official_alerts_with_status, meteoalarm_feed, warn_egress
    from services.official_alerts.geosphere_warn import GeoSphereWarnSource

    _assert_pruefling_aus_diesem_baum()
    zamg = _ZamgServer({
        _round4(*WIEN): _zamg_body(90101, "Wien"),
        _round4(*GRAZ): _zamg_body(60101, "Graz"),
    })
    feed_server = _JsonServer(_load_sample_feed())
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        monkeypatch.setattr(geosphere_warn, "GEOSPHERE_WARN_URL", f"http://127.0.0.1:{zamg.port}")
        monkeypatch.setattr(meteoalarm_feed, "FEED_BASE_URL", f"http://127.0.0.1:{feed_server.port}")
        oa_base._REGISTERED_SOURCES.append(GeoSphereWarnSource())
        oa_base._REGISTERED_SOURCES.append(meteoalarm_feed.MeteoAlarmFeedSource("AT"))

        get_official_alerts_with_status(*WIEN, now=TEST_NOW)
        get_official_alerts_with_status(*GRAZ, now=TEST_NOW)

        assert feed_server.zaehler.treffer <= 1, (
            f"zwei Orte im selben Fenster duerfen den AT-Feed-Host hoechstens "
            f"EINMAL erreichen, gemessen: {feed_server.zaehler.treffer}"
        )
        assert zamg.zaehler.treffer == 2, (
            f"ZAMG darf NUR je Punkt EINMAL erreicht werden (genau das, was "
            f"GeoSphereWarnSource allein ausgeloest haette) -- "
            f"MeteoAlarmFeedSource('AT') darf KEINEN zusaetzlichen ZAMG-Abruf "
            f"ausloesen (Spec Implementation Details Punkt 4). Gemessen: "
            f"{zamg.zaehler.treffer} echte ZAMG-Treffer"
        )
        journal = warn_egress.WARN_CALLS_PATH.read_text(encoding="utf-8") \
            if warn_egress.WARN_CALLS_PATH.exists() else ""
        assert '"host": "api.meteoalarm.org"' not in journal, (
            f"kein Abruf gegen den bisherigen kontingentierten Warndienst darf "
            f"verzeichnet sein. Journal:\n{journal}"
        )
    finally:
        zamg.shutdown()
        feed_server.shutdown()
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


# ---------------------------------------------------------------------------
# AC-5: Aequivalenz-Pflicht-Gate gegen einen zeitgleich aufgezeichneten
# EDR-Snapshot (Oesterreich). Die Aufzeichnung liegt seit
# ``AUFNAHME_UTC`` (2026-08-01T16:19:43Z) vor -- alle drei Seiten zur selben
# Minute ueber den Produktivcode gezogen: ``edr_snapshot_at.json`` (EDR-Index,
# lueckenlos ueber 38 Seiten geblaettert), ``feed_austria_equivalence.json``
# (Feed-Bestand) und ``zamg_snapshot_at.json`` (Zonenzuordnung je Tourpunkt),
# Herkunft s. README im Fixture-Verzeichnis. Das Gate laeuft seither scharf,
# die frueher noetige ``xfail``-Markierung ist ersatzlos entfallen.
#
# Die Vergleichslogik selbst (F002-Lehre aus S1: NICHT nur eine
# Existenzpruefung) bleibt zusaetzlich per Gegenprobe
# (``test_pruefe_obermenge_...``, kuenstliche tmp_path-Datei, NICHT die echten
# Fixtures) in BEIDE Richtungen bewiesen -- sie belegt die Vergleichslogik
# unabhaengig davon, was die echten Fixtures gerade enthalten.
# ---------------------------------------------------------------------------

def _alert_identitaet(alert: "OfficialAlert") -> tuple:
    """Stabile Kennung fuer den AC-5-Obermengen-Vergleich: Gefahrenart +
    Stufe + Region + Gueltigkeitszeitraum (identisch zur IT-Kennung aus S1,
    F004-Lehre: ``region_label`` MUSS mit rein, sonst maskieren zwei
    zeitfeldlose Warnungen einander; Vergleich ueber ``datetime``-OBJEKTE,
    nicht ``.isoformat()``-Strings, sonst falscher Alarm bei zwei Notationen
    desselben Zeitpunkts)."""
    return (
        alert.hazard,
        alert.level,
        alert.region_label,
        alert.valid_from,
        alert.valid_to,
    )


def _pruefe_obermenge(
    tourpunkte: "list[tuple[float, float]]",
    feed_je_punkt: dict,
    edr_je_punkt: dict,
) -> "list[str]":
    """Vergleicht je Tourpunkt die Feed- gegen die EDR-Warnungsmenge. Liefert
    eine Liste menschenlesbarer Abweichungen -- leer bedeutet: die Feed-Menge
    ist fuer JEDEN Tourpunkt eine Obermenge der EDR-Menge (AC-5)."""
    abweichungen: "list[str]" = []
    for punkt in tourpunkte:
        feed_ids = {_alert_identitaet(a) for a in feed_je_punkt.get(punkt, [])}
        edr_ids = {_alert_identitaet(a) for a in edr_je_punkt.get(punkt, [])}
        fehlend = edr_ids - feed_ids
        if fehlend:
            abweichungen.append(
                f"Tourpunkt {punkt}: im EDR-Snapshot, aber NICHT im Feed: {sorted(fehlend)}"
            )
    return abweichungen


def _lade_alert_liste_aus_json(eintraege: "list[dict]") -> dict:
    """Laedt eine Liste von ``{"lat", "lon", "alerts": [...]}``-Eintraegen
    (Schema von ``edr_snapshot_at.json``, s. README im Fixture-Verzeichnis)
    in eine Punkt -> ``OfficialAlert``-Liste-Abbildung fuer ``_pruefe_obermenge``."""
    ergebnis: dict = {}
    for eintrag in eintraege:
        punkt = (eintrag["lat"], eintrag["lon"])
        ergebnis[punkt] = [
            OfficialAlert(
                source="meteoalarm",
                hazard=a["hazard"],
                level=a["level"],
                label=a.get("label", ""),
                region_label=a.get("region_label"),
                valid_from=datetime.fromisoformat(a["valid_from"]) if a.get("valid_from") else None,
                valid_to=datetime.fromisoformat(a["valid_to"]) if a.get("valid_to") else None,
            )
            for a in eintrag.get("alerts", [])
        ]
    return ergebnis


def test_pruefe_obermenge_erkennt_fehlende_edr_warnung_im_feed(tmp_path):
    """Gegenprobe fuer die AC-5-Vergleichslogik (F002-Lehre aus S1): eine
    kleine, KUENSTLICH konstruierte Vergleichsdatei in ``tmp_path`` (NICHT die
    echte Fixture, die weiterhin fehlt) beweist BEIDE Richtungen der
    Obermengen-Pruefung -- Obermenge erfuellt => gruen, eine im EDR vorhandene
    Warnung fehlt im Feed => rot."""
    edr_datei = tmp_path / "edr_konstruiert_at.json"
    edr_datei.write_text(json.dumps([
        {
            "lat": 46.7597, "lon": 12.4177,
            "alerts": [{
                "hazard": "extreme_heat", "level": 2, "region_label": "Lienz",
                "valid_from": "2026-08-01T00:00:00+02:00",
                "valid_to": "2026-08-01T23:59:59+02:00",
            }],
        },
    ]), encoding="utf-8")
    edr_je_punkt = _lade_alert_liste_aus_json(json.loads(edr_datei.read_text(encoding="utf-8")))
    punkt = (46.7597, 12.4177)

    # Richtung 1: Obermenge erfuellt -- Feed enthaelt dieselbe Warnung UND
    # eine zusaetzliche.
    cest = timezone(timedelta(hours=2))
    feed_je_punkt_obermenge = {
        punkt: [
            OfficialAlert(
                source="meteoalarm", hazard="extreme_heat", level=2, label="Hitze",
                region_label="Lienz",
                valid_from=datetime(2026, 8, 1, tzinfo=cest),
                valid_to=datetime(2026, 8, 1, 23, 59, 59, tzinfo=cest),
            ),
            OfficialAlert(source="meteoalarm", hazard="thunderstorm", level=2, label="Gewitter"),
        ],
    }
    assert _pruefe_obermenge([punkt], feed_je_punkt_obermenge, edr_je_punkt) == [], (
        "eine Feed-Menge, die die EDR-Warnung UND eine weitere enthaelt, muss "
        "als Obermenge durchgehen (keine Abweichung)"
    )

    # Richtung 2: Obermenge verletzt -- die EDR-Warnung fehlt im Feed.
    feed_je_punkt_luecke = {punkt: []}
    abweichungen = _pruefe_obermenge([punkt], feed_je_punkt_luecke, edr_je_punkt)
    assert abweichungen, (
        "eine im EDR-Snapshot vorhandene, im Feed fehlende Warnung MUSS als "
        "Abweichung erkannt werden -- sonst ist die Obermengen-Pruefung wirkungslos"
    )
    assert "extreme_heat" in abweichungen[0]


def test_ac5_feed_menge_ist_obermenge_der_edr_menge_fuer_reale_tourpunkte(monkeypatch):
    """AC-5 (Pflicht-Gate vor Freigabe): GIVEN ein zur selben Minute
    aufgezeichneter EDR-Ausschnitt, der Feed-Ausschnitt UND die ZAMG-Antwort
    fuer dieselbe Liste realer oesterreichischer Tourpunkte (inkl. Karnischer
    Hoehenweg), WHEN beide Ergebnismengen ueber ``_pruefe_obermenge``
    gegenuebergestellt werden, THEN ist die Feed-Menge fuer JEDEN Tourpunkt
    eine Obermenge der EDR-Menge (Vergleichs-Kennung: ``_alert_identitaet`` --
    Gefahrenart + Stufe + Region + Gueltigkeitszeitraum, s. Docstring dort).

    Aufzeichnung: ``AUFNAHME_UTC`` (2026-08-01T16:19:43Z), alle drei Seiten
    zur selben Minute ueber den Produktivcode gezogen --
    ``edr_snapshot_at.json`` (8 reale Tourpunkte, EDR-Index lueckenlos ueber
    38 Seiten geblaettert) gegen ``feed_austria_equivalence.json``
    (Feed-Bestand derselben Minute), Zonenzuordnung aus
    ``zamg_snapshot_at.json``. Herkunft und Auswahlkriterium: README im
    Fixture-Verzeichnis.

    Adversary-Fund F2 (Issue #1445 S3 Fix-Loop): dieser Test MUSS wie alle
    anderen ueber ``_ZamgServer`` gegen einen lokalen Server laufen, NIE
    gegen das echte ``warnungen.zamg.at`` -- sonst vergliche er gegen den
    AKTUELLEN ZAMG-Zustand statt gegen den zum Aufnahmezeitpunkt gueltigen,
    eine Stoerung/Ratenbremse dort erzeugte irrefuehrende Fehlschlaege, und
    er verletzte die Kern-Testschicht-Regel 'kein Netz'."""
    edr_path = _FIXTURES / "edr_snapshot_at.json"
    feed_path = _FIXTURES / "feed_austria_equivalence.json"
    zamg_path = _FIXTURES / "zamg_snapshot_at.json"
    for pfad in (edr_path, feed_path, zamg_path):
        assert pfad.exists(), (
            f"Aequivalenz-Pflicht-Gate (AC-5) kann ohne alle drei Seiten der "
            f"Aufzeichnung nicht gefuehrt werden: {pfad} fehlt. Dieser Test MUSS "
            f"dann rot bleiben -- ein pytest.skip wuerde den fehlenden "
            f"Sicherheitsnachweis als Erfolg tarnen."
        )

    import services.official_alerts.base as oa_base
    from services.official_alerts import geosphere_warn, meteoalarm_feed

    _assert_pruefling_aus_diesem_baum()
    edr_je_punkt = _lade_alert_liste_aus_json(json.loads(edr_path.read_text(encoding="utf-8")))
    tourpunkte = list(edr_je_punkt.keys())
    assert len(tourpunkte) == 8 and all(edr_je_punkt[p] for p in tourpunkte), (
        f"Aufbaupruefung: die Aufzeichnung muss 8 Tourpunkte mit JE mindestens "
        f"einer EDR-Warnung tragen -- gegen leere EDR-Mengen ist jede "
        f"Obermengen-Pruefung trivial erfuellt und beweist nichts. Erhalten: "
        f"{[(p, len(edr_je_punkt[p])) for p in tourpunkte]}"
    )
    zamg_eintraege = json.loads(zamg_path.read_text(encoding="utf-8"))
    zamg_antworten = {
        _round4(eintrag["lat"], eintrag["lon"]): (
            eintrag["status"] if "status" in eintrag else eintrag["response"]
        )
        for eintrag in zamg_eintraege
    }
    assert all(_round4(*punkt) in zamg_antworten for punkt in tourpunkte), (
        f"Aufbaupruefung: die ZAMG-Aufzeichnung muss JEDEN Tourpunkt des "
        f"EDR-Snapshots abdecken -- ein fehlender Punkt liefe sonst in den "
        f"404-Zweig des lokalen Servers und meldete faelschlich 'nicht "
        f"zustaendig'. Fehlend: "
        f"{[p for p in tourpunkte if _round4(*p) not in zamg_antworten]}"
    )

    # Gleichbehandlung beider Seiten -- dieselbe Entscheidung wie im
    # IT-Pendant (``test_ac3_...`` in test_meteoalarm_feed_italien.py) und aus
    # demselben Grund uebernommen: verglichen wird auf BEIDEN Seiten die ROHE
    # Quellenausgabe zum Aufnahmezeitpunkt -- die EDR-Seite so, wie
    # ``MeteoAlarmSource.fetch()`` sie lieferte, die Feed-Seite ueber
    # ``MeteoAlarmFeedSource.fetch()`` statt ueber
    # ``get_official_alerts_with_status(now=...)``. Zwei Gruende:
    # (1) Zeitfenster: filtert man nur die Feed-Seite auf ``now``, verschwinden
    #     dort zum Aufnahmezeitpunkt bereits abgelaufene Warnungen, waehrend sie
    #     auf der EDR-Seite stehenbleiben -- gemeldet wuerde eine Luecke, die
    #     allein aus der ungleichen Behandlung stammt. Die Fensterfilterung
    #     sitzt ohnehin in ``base.py`` HINTER beiden Quellen und kann in
    #     Produktion keinen Unterschied ZWISCHEN ihnen erzeugen -- sie gehoert
    #     damit nicht in einen Quellen-Aequivalenzbeweis.
    # (2) Der Zwei-Pass-Dedup in ``base.py`` kollabiert Warnungen mit gleichem
    #     ``(hazard, valid_from, valid_to)`` auf die hoechste Stufe. Eine im EDR
    #     vorhandene, im Feed fehlende Warnung koennte dadurch MASKIERT werden --
    #     genau die Richtung, die dieses Gate ausschliessen soll.
    # Anders als in Italien ist Grund (1) hier nicht theoretisch, sondern
    # gemessen: die oesterreichische EDR-Aufzeichnung traegt Warnungen, die zum
    # Aufnahmezeitpunkt bereits abgelaufen sind (Stand der Aufzeichnung: 24 von
    # 118). Eine einseitige ``now``-Filterung der Feed-Seite haette genau diese
    # als vermeintliche Luecken gemeldet. Der Rohvergleich ist damit zugleich
    # die STRENGERE Variante -- er verlangt vom Feed auch die abgelaufenen
    # Warnungen, und der Feed liefert sie (er reicht weiter zurueck als der
    # EDR-Index).
    alle_edr = [a for punkt in tourpunkte for a in edr_je_punkt[punkt]]
    gefiltert = oa_base.filter_alerts_to_window(alle_edr, AUFNAHME_UTC, None)
    assert len(gefiltert) < len(alle_edr), (
        f"Aufbaupruefung: die EDR-Aufzeichnung muss zum Aufnahmezeitpunkt "
        f"bereits abgelaufene Warnungen enthalten -- genau sie belegen, dass "
        f"eine einseitige now-Filterung der Feed-Seite unzulaessig waere. "
        f"Erhalten: {len(gefiltert)} von {len(alle_edr)} ueberleben die "
        f"Filterung. Sind es alle, ist der Rohvergleich zwar weiterhin korrekt, "
        f"aber diese Begruendung muss dann neu belegt werden."
    )

    server = _JsonServer(_load_equivalence_feed())
    zamg = _ZamgServer(zamg_antworten)
    try:
        monkeypatch.setattr(meteoalarm_feed, "FEED_BASE_URL", f"http://127.0.0.1:{server.port}")
        monkeypatch.setattr(geosphere_warn, "GEOSPHERE_WARN_URL", f"http://127.0.0.1:{zamg.port}")
        quelle = meteoalarm_feed.MeteoAlarmFeedSource("AT")

        feed_je_punkt = {}
        for punkt in tourpunkte:
            assert quelle.covers(*punkt) is True, (
                f"Aufbaupruefung: {punkt} muss von der Feed-Quelle abgedeckt sein "
                f"-- sonst vergleicht das Gate einen Punkt, den die Quelle in "
                f"Produktion gar nicht bedient"
            )
            feed_je_punkt[punkt] = quelle.fetch(*punkt)

        abweichungen = _pruefe_obermenge(tourpunkte, feed_je_punkt, edr_je_punkt)
        assert not abweichungen, "\n".join(abweichungen)
    finally:
        server.shutdown()
        zamg.shutdown()


# ---------------------------------------------------------------------------
# AC-6: strukturell leere Feed-Antwort -> unavailable=True (geteilte
# ``_parse_feed()``-Pruefung aus S1/F001, hier ueber den echten AT-Pfad
# end-zu-ende bewiesen).
# ---------------------------------------------------------------------------

def test_ac6_strukturell_leere_feed_antwort_meldet_nicht_abrufbar(monkeypatch):
    """AC-6: GIVEN der Feed-Abruf fuer Oesterreich liefert eine syntaktisch
    gueltige, aber strukturell leere Antwort (kein auswertbarer
    'warnings'-Listen-Schluessel), WHEN die amtlichen Warnungen fuer einen
    abgedeckten oesterreichischen Ort ermittelt werden, THEN liefert der
    Aufruf unavailable=True statt einer leeren, als 'keine Warnung'
    interpretierbaren Liste."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import geosphere_warn, get_official_alerts_with_status, meteoalarm_feed

    _assert_pruefling_aus_diesem_baum()
    zamg = _ZamgServer({_round4(*SILLIAN): _zamg_body(70728, "Sillian")})
    feed_server = _JsonServer({})  # kein "warnings"-Schluessel
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        monkeypatch.setattr(geosphere_warn, "GEOSPHERE_WARN_URL", f"http://127.0.0.1:{zamg.port}")
        monkeypatch.setattr(meteoalarm_feed, "FEED_BASE_URL", f"http://127.0.0.1:{feed_server.port}")
        oa_base._REGISTERED_SOURCES.append(meteoalarm_feed.MeteoAlarmFeedSource("AT"))

        alerts, unavailable = get_official_alerts_with_status(*SILLIAN, now=TEST_NOW)

        assert unavailable is True, (
            f"eine strukturell leere Feed-Antwort ohne 'warnings'-Schluessel "
            f"muss als Fehlschlag gelten. Erhalten: alerts={alerts}, "
            f"unavailable={unavailable}"
        )
    finally:
        zamg.shutdown()
        feed_server.shutdown()
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


# ---------------------------------------------------------------------------
# AC-7: genau der Eintrag fuer die eigene Zone liegt kaputt vor ->
# unavailable=True (geteilter F003-Schutz aus S1, hier ueber den echten
# AT-Pfad end-zu-ende bewiesen).
# ---------------------------------------------------------------------------

def _wohlgeformter_alert_fuer_wien() -> dict:
    """Ein vollstaendiges, gueltiges CAP-``alert``-Objekt fuer AT901 (Wien) --
    Hitzewarnung, Stufe orange/3, gueltig zum Testzeitpunkt (entspricht dem
    echten, in ``feed_austria_sample.json`` enthaltenen Eintrag)."""
    return {
        "identifier": "test-ac7-ac8-wien-heat-001",
        "info": [{
            "language": "de-DE",
            "event": "Hitzewarnung",
            "headline": "Hitzewarnung",
            "onset": "2026-08-01T00:00:00+02:00",
            "expires": "2026-08-02T23:59:59+02:00",
            "parameter": [
                {"valueName": "awareness_level", "value": "3; orange; Severe"},
                {"valueName": "awareness_type", "value": "5; high-temperature"},
            ],
            "area": [{
                "areaDesc": "Wien",
                "geocode": [{"valueName": "EMMA_ID", "value": "AT901"}],
            }],
        }],
    }


def test_ac7_kaputter_eintrag_fuer_eigene_zone_meldet_nicht_abrufbar(monkeypatch):
    """AC-7: GIVEN genau der Eintrag, der fuer die Zone des abgefragten Ortes
    (AT707, Sillian/Karnischer Hoehenweg) infrage kaeme, liegt im AT-Feed
    strukturell kaputt vor (weder auswertbare Zonenangabe noch
    CAP-Cancel-Kennzeichnung -- neben einer wohlgeformten Warnung fuer eine
    ANDERE Zone, AT901/Wien), WHEN die amtlichen Warnungen fuer Sillian
    ermittelt werden, THEN verschwindet die Warnung nicht stillschweigend,
    sondern das Ergebnis meldet 'nicht abrufbar'."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import geosphere_warn, get_official_alerts_with_status, meteoalarm_feed

    _assert_pruefling_aus_diesem_baum()
    zamg = _ZamgServer({_round4(*SILLIAN): _zamg_body(70728, "Sillian")})
    feed = {"warnings": [{"alert": _wohlgeformter_alert_fuer_wien()}, {}]}
    feed_server = _JsonServer(feed)
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        monkeypatch.setattr(geosphere_warn, "GEOSPHERE_WARN_URL", f"http://127.0.0.1:{zamg.port}")
        monkeypatch.setattr(meteoalarm_feed, "FEED_BASE_URL", f"http://127.0.0.1:{feed_server.port}")
        oa_base._REGISTERED_SOURCES.append(meteoalarm_feed.MeteoAlarmFeedSource("AT"))

        alerts, unavailable = get_official_alerts_with_status(*SILLIAN, now=TEST_NOW)

        assert unavailable is True, (
            f"ein einzelner kaputter warnings[]-Eintrag ohne auswertbare "
            f"Zonenangabe muss als Fehlschlag zaehlen -- er haette ausgerechnet "
            f"die Warnung fuer AT707 sein koennen. Erhalten: alerts={alerts}, "
            f"unavailable={unavailable}"
        )
    finally:
        zamg.shutdown()
        feed_server.shutdown()
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


# ---------------------------------------------------------------------------
# AC-8: kaputter Eintrag fuer FREMDE Zone + gleichzeitiger IT-Ausfall duerfen
# einen vollstaendig bedienbaren AT-Ort NICHT einfaerben (geteilter
# F005-Schutz aus S1 + Laender-Isolation ueber covers(), analog dem
# IT-Pendant test_ac7_at_indexfehlschlag_faerbt_it_ergebnis_nicht_ein in
# test_meteoalarm_feed_italien.py, hier in umgekehrter Richtung).
# ---------------------------------------------------------------------------

def _cancel_ohne_info_fuer_sillian() -> dict:
    """Ein CAP-Ruecknahme-Eintrag (msgType 'Cancel') fuer eine ANDERE Zone
    (Sillian/AT707) -- traegt konventionsgemaess KEIN info[]. Regelkonforme
    Form, kein Datenfehler (F005-Lehre aus S1)."""
    return {
        "identifier": "test-ac8-cancel-sillian-001",
        "msgType": "Cancel",
        "references": "GeoSphere Austria,test-ac8-original-001,2026-07-31T00:00:00+02:00",
    }


def test_ac8_kaputter_eintrag_fremder_zone_und_gleichzeitiger_it_ausfall_faerben_wien_nicht_ein(monkeypatch):
    """AC-8: GIVEN im AT-Feed liegt ein CAP-Ruecknahme-Eintrag (msgType
    'Cancel', ohne info[]) fuer eine ANDERE Zone (Sillian/AT707) NEBEN einer
    wohlgeformten, gueltigen Warnung fuer Wien (AT901) UND GLEICHZEITIG
    schlaegt der Feed-Abruf fuer einen italienischen Ort fehl (HTTP 503,
    Wien liegt ausserhalb der DPC-Bbox -- IT deckt Wien also gar nicht ab),
    WHEN die amtlichen Warnungen fuer Wien ermittelt werden, THEN bleibt
    Wiens Ergebnis unbeeinflusst: unavailable=False, seine eigene Warnung
    erscheint."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import geosphere_warn, get_official_alerts_with_status, meteoalarm_feed

    _assert_pruefling_aus_diesem_baum()
    zamg = _ZamgServer({_round4(*WIEN): _zamg_body(90101, "Wien")})
    at_feed = {"warnings": [
        {"alert": _cancel_ohne_info_fuer_sillian()},
        {"alert": _wohlgeformter_alert_fuer_wien()},
    ]}
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    dual = None
    try:
        # _FEED_PATHS existiert erst nach der Implementierung -- die
        # Server-Konfiguration greift bewusst schon jetzt darauf zu (RED).
        dual = _DualPathServer(
            path_bodies={meteoalarm_feed._FEED_PATHS["AT"]: at_feed},
            path_fail={meteoalarm_feed._FEED_PATHS["IT"]: 503},
        )
        monkeypatch.setattr(geosphere_warn, "GEOSPHERE_WARN_URL", f"http://127.0.0.1:{zamg.port}")
        monkeypatch.setattr(meteoalarm_feed, "FEED_BASE_URL", f"http://127.0.0.1:{dual.port}")
        oa_base._REGISTERED_SOURCES.append(meteoalarm_feed.MeteoAlarmFeedSource("IT"))
        oa_base._REGISTERED_SOURCES.append(meteoalarm_feed.MeteoAlarmFeedSource("AT"))

        alerts, unavailable = get_official_alerts_with_status(*WIEN, now=TEST_NOW)

        assert unavailable is False, (
            f"weder ein fremder kaputter Eintrag im eigenen Feed (Sillian-"
            f"Cancel) noch ein gleichzeitiger IT-Ausfall darf Wien einfaerben. "
            f"Erhalten: alerts={alerts}, unavailable={unavailable}"
        )
        assert any(a.hazard == "extreme_heat" and a.level == 3 and a.source == "meteoalarm" for a in alerts), (
            f"Wien muss trotz des fremden kaputten Eintrags und des IT-Ausfalls "
            f"seine eigene, vollstaendige Warnung bekommen. Erhalten: {alerts}"
        )
    finally:
        zamg.shutdown()
        if dual is not None:
            dual.shutdown()
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)
