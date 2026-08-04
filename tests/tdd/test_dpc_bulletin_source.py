"""TDD RED -- Issue #1427 Scheibe S2: DpcSource (italienischer Zivilschutz,
dauerhaft additive amtliche Warnquelle).

SPEC: docs/specs/modules/feat_1427_dpc_warn_fallback.md (Fassung 2.0), AC-2 bis AC-7.
S1 (Gefahrenart "flood" im SSOT-Katalog, MeteoAlarm-Typen 11/12/13) ist bereits
live -- diese Datei deckt AUSSCHLIESSLICH S2 ab.

Diese Tests schlagen ABSICHTLICH fehl, solange ``services.official_alerts.dpc``
noch nicht existiert -> ModuleNotFoundError/ImportError beim jeweils ersten
Import innerhalb der Testfunktion (= korrektes RED).

Angenommene Schnittstelle von ``dpc.py`` (RED-Phase-Designentscheidung, analog
bestehender Quellen -- Begruendung im Bericht des Entwickler-Agents):

- ``DpcSource`` implementiert ``OfficialAlertSource`` (``base.py:24``)
  unveraendert: ``name``, ``covers(lat, lon)``, ``fetch(lat, lon)``, kein
  Konstruktor-Argument (wird als ``DpcSource()`` registriert, analog
  ``MeteoAlarmSource()``).
- Modul-Konstante ``DPC_ZIP_URL`` (Konvention analog
  ``meteoalarm.METEOALARM_BASE_URL``/``geosphere_warn.GEOSPHERE_WARN_URL``/
  ``vigilance.VIGILANCE_URL``) -- injizierbar fuer Tests via monkeypatch,
  kein echter Netzwerk-Call.
- Modul-Attribut ``_NOW_FN: Callable[[], datetime]`` (Konvention analog
  ``meteoalarm._WALL_CLOCK_FN``) -- injizierbarer Uhr-Haken fuer den
  Tagesversatz-Vergleich (AC-3), Default ``datetime.now(timezone.utc)``.
- ``OfficialAlert.source`` enthaelt die Zeichenkette ``"dpc"`` (Konvention
  analog ``"meteoalarm"``, ``"vigilance"``, ``"geosphere_warn"``).

KEINE Mocks (Projektkonvention): alle HTTP-Antworten kommen von einem ECHTEN
lokalen ``http.server``-Socket (analog ``_BrokenJSONHandler`` in
``test_meteoalarm_source.py``), alle Registry-Test-Quellen sind echte Objekte,
die das Protocol strukturell erfuellen (kein ``Mock()``/``patch()``/
``MagicMock``). Fixtures sind ECHTE aufgezeichnete DPC-Bulletins (Ausnahme:
zwei explizit als SYNTHETISCH gekennzeichnete Fail-soft-Fixtures fuer AC-5,
Praezedenzfall ``tests/fixtures/meteoalarm/cap_broken.xml`` -- s.
``tests/fixtures/dpc/README.md``).
"""
from __future__ import annotations

import http.server
import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import pytest


# Live-Schicht (Test-Politik, CLAUDE.md): braucht echtes Netz/echte Dienste --
# lief im Kern nie gruen (CI-Vermessung 2026-08-04, #1196) und gehoert per
# Marker in den /e2e-verify-Lauf, nicht auf eine Ausnahmeliste.
pytestmark = pytest.mark.live

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "dpc"

# Repraesentative Punkte je Zone -- berechnet gegen die generierte
# src/services/official_alerts/data/dpc_zones.json (Punkt-in-Zone-
# Selbstpruefung im Bericht des Entwickler-Agents: jeder Punkt liegt in
# GENAU einer Zone).
KHW_TREN_A = (46.7248, 12.2254)  # Karnischer Hoehenweg, IT-Seite -- Zone Tren-A
ABRU_A_QUIET = (42.638137, 13.724605)  # Bacini Tordino Vomano -- in beiden Fixtures NESSUNA
SICI_A_GIALLA = (38.114738, 15.158302)  # Nord-Orientale, versante tirrenico -- Temporali GIALLA
CALA_6_ARANCIONE = (39.228314, 16.860471)  # Versante Jonico Centro-settentrionale -- ARANCIONE alle drei Rischi
SARD_E_FLOOD_ARANCIONE = (40.095178, 9.014603)  # Bacino del Tirso -- NUR Idrogeo ARANCIONE
SARD_A_FLOOD_ROSSA = (39.121980, 8.609139)  # Iglesiente -- Idrogeo ROSSA (Stufen-Abbildung Level 4)


def _read_fixture_bytes(name: str) -> bytes:
    return (FIXTURES_DIR / name).read_bytes()


class _ZipBytesHandler(http.server.BaseHTTPRequestHandler):
    """Echter lokaler HTTP-Server (kein Mock): liefert fuer JEDEN Pfad
    dieselben festen Bytes (analog ``_BrokenJSONHandler`` in
    ``test_meteoalarm_source.py``)."""

    payload: bytes = b""

    def do_GET(self):  # noqa: N802 - stdlib-Signatur
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(len(self.payload)))
        self.end_headers()
        self.wfile.write(self.payload)

    def log_message(self, *_args):  # Testlauf-Output nicht zumuellen
        pass


@contextmanager
def _serve_bytes(payload: bytes):
    """Startet einen echten lokalen HTTP-Server, der ``payload`` fuer jeden
    GET liefert, und liefert die Basis-URL. Kein Mock der HTTP-Bibliothek."""
    handler_cls = type("_Handler", (_ZipBytesHandler,), {"payload": payload})
    server = http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/latest_all.zip"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def _reset_dpc_module_caches(dpc_module) -> None:
    """Leert NUR das modul-eigene Cache-Attribut ``_cache`` (Cache-Konvention
    dieses Projekts, s. ``geosphere_warn._cache``/``vigilance._cache``/
    ``meteo_forets._cache`` -- durchweg exakt so benannt). Verhindert, dass
    ein TTL-Cache-Treffer aus einem fruoheren Test die Fixture des naechsten
    Tests ueberdeckt (Testisolation, kein Mock).

    ZWEI FALLEN (nicht kopieren -- beide real aufgetreten, s. Bericht):

    1. ``vars(modul)`` enthaelt bei importierten Modulen auch
       ``__builtins__`` -- in CPython eine GETEILTE Referenz auf
       ``builtins.__dict__``. Ein generisches ``.clear()`` ueber ALLE
       dict-Werte in ``vars(modul)`` leert damit die Built-ins des gesamten
       Prozesses (u.a. ``len``, ``str``, ``Exception``) und reisst jeden
       weiteren Test in derselben pytest-Session mit.
    2. Selbst OHNE Dunder-Treffer bleibt "jedes dict-Attribut leeren" falsch:
       ein Modul kann neben dem TTL-Cache auch fachliche Konstanten-Dicts
       fuehren (z.B. eine Stufen-Abbildung wie ``dpc._LEVEL_MAP =
       {"GIALLA": 2, ...}``). Ein generischer Sweep loescht die MIT und
       produziert stille Fehlschlaege, die aussehen wie ein Produktivbug
       (leere Warnungen trotz korrektem Bulletin), aber nur ein kaputtes
       Test-Aufraeumen sind. Deshalb NUR das exakt benannte ``_cache``-
       Attribut anfassen, nichts Generisches."""
    cache = getattr(dpc_module, "_cache", None)
    if isinstance(cache, dict):
        cache.clear()


def _set_now(monkeypatch, dpc_module, when: datetime) -> None:
    """Injiziert eine feste 'jetzt'-Zeit ueber den modul-globalen Clock-Hook
    ``_NOW_FN`` (Konvention analog ``meteoalarm._WALL_CLOCK_FN``).
    Deterministisch -- kein Test haengt am tatsaechlichen Tagesdatum."""
    monkeypatch.setattr(dpc_module, "_NOW_FN", lambda: when)


# ---------------------------------------------------------------------------
# AC-2: gewarnte Zone liefert die Warnung, ungewarnte Zone liefert []
# ---------------------------------------------------------------------------

def test_ac2_zona_gewarnt_liefert_thunderstorm_zone_ungewarnt_liefert_leer(monkeypatch):
    """AC-2: GIVEN der italienische Zivilschutz warnt fuer eine Zone
    (Tren-A, Temporali GIALLA im Ruhetags-Bulletin), WHEN DpcSource.fetch()
    fuer einen Punkt in dieser Zone laeuft, THEN liefert es eine
    OfficialAlert mit hazard='thunderstorm', level=2, source kennzeichnet
    DPC. Ein Punkt in einer ungewarnten Zone (Abru-A, in BEIDEN Datensaetzen
    des Bulletins NESSUNA) liefert eine leere Liste.

    now = 31.07. 04:57 UTC (Folgetag des Bulletins) -- damit ist automatisch
    der 'tomorrow'-Datensatz der Bezugstag (s. AC-3); Tren-A ist NUR dort
    gewarnt, NICHT in 'today'."""
    from services.official_alerts.dpc import DpcSource
    import services.official_alerts.dpc as dpc_module

    _reset_dpc_module_caches(dpc_module)
    _set_now(monkeypatch, dpc_module, datetime(2026, 7, 31, 4, 57, tzinfo=timezone.utc))

    payload = _read_fixture_bytes("ruhetag_20260730_1511.zip")
    with _serve_bytes(payload) as url:
        monkeypatch.setattr(dpc_module, "DPC_ZIP_URL", url)
        source = DpcSource()

        warned = source.fetch(*KHW_TREN_A)
        thunder = [a for a in warned if a.hazard == "thunderstorm"]
        assert len(thunder) == 1, (
            f"Tren-A ist im Bezugstag GIALLA bei Temporali -- erwartet genau "
            f"EINE thunderstorm-Warnung, erhalten: {warned}"
        )
        assert thunder[0].level == 2, f"GIALLA muss level=2 sein, war {thunder[0].level}"
        assert "dpc" in thunder[0].source.lower(), (
            f"source muss die DPC-Quelle kennzeichnen, war {thunder[0].source!r}"
        )

        quiet = source.fetch(*ABRU_A_QUIET)
        assert quiet == [], f"Ungewarnte Zone muss [] liefern, erhalten: {quiet}"


# ---------------------------------------------------------------------------
# AC-3: Tagesversatz -- WICHTIGSTER TEST
# ---------------------------------------------------------------------------

def test_ac3_tagesversatz_liest_tomorrow_datensatz_nicht_today(monkeypatch):
    """AC-3 (WICHTIGSTER TEST): GIVEN das neueste verfuegbare Bulletin
    (20260730_1511) wurde am VORTAG veroeffentlicht, WHEN am Folgetag frueh
    (31.07. 04:57 UTC) ein Punkt in der gewarnten Zone (Tren-A) abgefragt
    wird, THEN liefert fetch() die Warnung aus dem 'tomorrow'-Teil des
    Bulletins (= 'heute' aus Nutzersicht) -- NICHT aus 'today' (= gestern,
    dort ist Tren-A NESSUNA). Ein naiv 'today.dbf' lesender Code liefert an
    dieser Stelle faelschlich [] -- exakt der Bug, den #1427 S2 behebt.

    Gegenprobe (zweite Haelfte desselben Tests, gleiches Fixture): wird
    DASSELBE Bulletin am Tag SEINER EIGENEN Veroeffentlichung abgefragt
    (30.07., selbes Kalenderdatum wie der Dateiname), muss die Zuordnung
    umgekehrt greifen -- 'today' ist dann Bezugstag, Tren-A ist dort
    NESSUNA -> []. Das beweist, dass die Auswahl tatsaechlich vom
    Datumsvergleich abhaengt und nicht zufaellig 'immer tomorrow' liefert."""
    from services.official_alerts.dpc import DpcSource
    import services.official_alerts.dpc as dpc_module

    payload = _read_fixture_bytes("ruhetag_20260730_1511.zip")

    _reset_dpc_module_caches(dpc_module)
    _set_now(monkeypatch, dpc_module, datetime(2026, 7, 31, 4, 57, tzinfo=timezone.utc))
    with _serve_bytes(payload) as url:
        monkeypatch.setattr(dpc_module, "DPC_ZIP_URL", url)
        alerts_folgetag = DpcSource().fetch(*KHW_TREN_A)
    assert alerts_folgetag, (
        "Folgetag-Abfrage (Bezugstag = tomorrow-Datensatz) muss die GIALLA-"
        f"Warnung liefern; ein today.dbf-lesender Code liefert hier "
        f"faelschlich [], erhalten: {alerts_folgetag}"
    )

    _reset_dpc_module_caches(dpc_module)
    _set_now(monkeypatch, dpc_module, datetime(2026, 7, 30, 16, 0, tzinfo=timezone.utc))
    with _serve_bytes(payload) as url:
        monkeypatch.setattr(dpc_module, "DPC_ZIP_URL", url)
        alerts_veroeffentlichungstag = DpcSource().fetch(*KHW_TREN_A)
    assert alerts_veroeffentlichungstag == [], (
        "Am Veroeffentlichungstag selbst ist 'today' der Bezugstag -- dort "
        f"ist Tren-A NESSUNA, erwartet [], erhalten: "
        f"{alerts_veroeffentlichungstag}"
    )


# ---------------------------------------------------------------------------
# Test Plan Punkt 4: zwei Zonen gleichzeitig, unterschiedliche Rischi/Stufen
# ---------------------------------------------------------------------------

def test_zwei_zonen_gleichzeitig_thunderstorm_gelb_und_flood_orange(monkeypatch):
    """Test Plan Punkt 4: GIVEN ein Bulletin mit einer Zone in ALLERTA
    GIALLA bei Temporali (Sici-A) UND einer anderen Zone in ALLERTA
    ARANCIONE bei Idrogeo (Cala-6), WHEN DpcSource.fetch() fuer Punkte in
    beiden Zonen laeuft, THEN liefert die erste eine thunderstorm-Warnung
    Level 2 und die zweite eine flood-Warnung Level 3 (Unwettertag-
    Bulletin, Bezugstag = Veroeffentlichungstag selbst -> 'today')."""
    from services.official_alerts.dpc import DpcSource
    import services.official_alerts.dpc as dpc_module

    payload = _read_fixture_bytes("unwettertag_20260118_1515.zip")
    _reset_dpc_module_caches(dpc_module)
    _set_now(monkeypatch, dpc_module, datetime(2026, 1, 18, 16, 0, tzinfo=timezone.utc))
    with _serve_bytes(payload) as url:
        monkeypatch.setattr(dpc_module, "DPC_ZIP_URL", url)
        source = DpcSource()

        gialla_alerts = source.fetch(*SICI_A_GIALLA)
        thunder = [a for a in gialla_alerts if a.hazard == "thunderstorm" and a.level == 2]
        assert thunder, (
            f"Sici-A ist Temporali GIALLA -- erwartet thunderstorm level=2, "
            f"erhalten: {gialla_alerts}"
        )

        arancione_alerts = source.fetch(*CALA_6_ARANCIONE)
        flood = [a for a in arancione_alerts if a.hazard == "flood" and a.level == 3]
        assert flood, (
            f"Cala-6 ist Idrogeo/Idraulico ARANCIONE -- erwartet flood level=3, "
            f"erhalten: {arancione_alerts}"
        )


def test_stufen_abbildung_rossa_liefert_level_4_flood(monkeypatch):
    """Stufen-Abbildung (Implementation Details Punkt 6): ROSSA -> Level 4.
    GIVEN Sard-A im 'tomorrow'-Datensatz des Unwettertag-Bulletins ist
    Idrogeo ELEVATA/ALLERTA ROSSA (Temporali dort NESSUNA -- reiner
    Hochwasser/Erdrutsch-Fall auf hoechster Stufe), WHEN DpcSource.fetch()
    fuer einen Punkt in Sard-A laeuft, THEN liefert es eine flood-Warnung
    mit level=4."""
    from services.official_alerts.dpc import DpcSource
    import services.official_alerts.dpc as dpc_module

    payload = _read_fixture_bytes("unwettertag_20260118_1515.zip")
    _reset_dpc_module_caches(dpc_module)
    # 'tomorrow' des 18.01.-Bulletins = Bezugstag 19.01.
    _set_now(monkeypatch, dpc_module, datetime(2026, 1, 19, 5, 0, tzinfo=timezone.utc))
    with _serve_bytes(payload) as url:
        monkeypatch.setattr(dpc_module, "DPC_ZIP_URL", url)
        alerts = DpcSource().fetch(*SARD_A_FLOOD_ROSSA)

    flood = [a for a in alerts if a.hazard == "flood" and a.level == 4]
    assert flood, f"Sard-A ist Idrogeo ROSSA -- erwartet flood level=4, erhalten: {alerts}"


def test_stufen_abbildung_arancione_ohne_temporali_liefert_nur_flood(monkeypatch):
    """Stufen-Abbildung: Sard-E ist im 'tomorrow'-Datensatz Idrogeo
    ARANCIONE bei Temporali=NESSUNA -- ein reiner Hochwasser/Erdrutsch-Fall
    OHNE begleitende Gewitterwarnung derselben Zone. Grenzt die Idrogeo/
    Idraulico->flood-Abbildung sauber von der Temporali->thunderstorm-
    Abbildung ab (Implementation Details Punkt 7)."""
    from services.official_alerts.dpc import DpcSource
    import services.official_alerts.dpc as dpc_module

    payload = _read_fixture_bytes("unwettertag_20260118_1515.zip")
    _reset_dpc_module_caches(dpc_module)
    _set_now(monkeypatch, dpc_module, datetime(2026, 1, 19, 5, 0, tzinfo=timezone.utc))
    with _serve_bytes(payload) as url:
        monkeypatch.setattr(dpc_module, "DPC_ZIP_URL", url)
        alerts = DpcSource().fetch(*SARD_E_FLOOD_ARANCIONE)

    assert any(a.hazard == "flood" and a.level == 3 for a in alerts), (
        f"Sard-E ist Idrogeo ARANCIONE -- erwartet flood level=3, erhalten: {alerts}"
    )
    assert not any(a.hazard == "thunderstorm" for a in alerts), (
        f"Sard-E hat Temporali=NESSUNA -- es darf KEINE thunderstorm-Warnung "
        f"entstehen, erhalten: {alerts}"
    )


# ---------------------------------------------------------------------------
# AC-4: Herkunftsangabe
# ---------------------------------------------------------------------------

def test_ac4_source_label_nennt_protezione_civile_nicht_meteoalarm(monkeypatch):
    """AC-4 (ADR-0034): GIVEN eine DPC-Warnung, WHEN die Herkunftsangabe
    ueber official_alert_source_label() aufgeloest wird, THEN nennt sie die
    italienische Zivilschutzbehoerde (Protezione Civile), nicht
    MeteoAlarm."""
    from services.official_alerts.dpc import DpcSource
    from output.renderers.alert.official_alerts import official_alert_source_label
    import services.official_alerts.dpc as dpc_module

    payload = _read_fixture_bytes("ruhetag_20260730_1511.zip")
    _reset_dpc_module_caches(dpc_module)
    _set_now(monkeypatch, dpc_module, datetime(2026, 7, 31, 4, 57, tzinfo=timezone.utc))
    with _serve_bytes(payload) as url:
        monkeypatch.setattr(dpc_module, "DPC_ZIP_URL", url)
        alerts = DpcSource().fetch(*KHW_TREN_A)

    assert alerts, "Vorbedingung: Fixture muss eine Warnung liefern (s. AC-2)"
    label = official_alert_source_label(alerts[0].source)
    assert "protezione civile" in label.lower(), (
        f"Herkunftsangabe muss die italienische Zivilschutzbehoerde nennen, "
        f"war {label!r}"
    )
    assert "meteoalarm" not in label.lower(), (
        f"Herkunftsangabe darf NICHT 'MeteoAlarm' sein, war {label!r}"
    )


# ---------------------------------------------------------------------------
# AC-5: Fail-soft (defektes Zip, unbekanntes Freitext-Muster, unbekannter Code)
# ---------------------------------------------------------------------------

def test_ac5a_kaputtes_zip_liefert_leere_liste_kein_crash(monkeypatch):
    """AC-5: GIVEN eine kaputte/unlesbare Zip-Antwort (echter lokaler
    HTTP-Server, kein Mock der HTTP-Bibliothek), WHEN fetch() laeuft, THEN
    wirft es KEINE Exception und liefert []."""
    from services.official_alerts.dpc import DpcSource
    import services.official_alerts.dpc as dpc_module

    _reset_dpc_module_caches(dpc_module)
    _set_now(monkeypatch, dpc_module, datetime(2026, 7, 31, 4, 57, tzinfo=timezone.utc))
    with _serve_bytes(b"das ist kein gueltiges Zip-Archiv") as url:
        monkeypatch.setattr(dpc_module, "DPC_ZIP_URL", url)
        alerts = DpcSource().fetch(*KHW_TREN_A)

    assert alerts == [], f"Kaputtes Zip muss fail-soft [] liefern, erhalten: {alerts}"


def test_ac5b_unbekanntes_stufen_freitextmuster_liefert_keine_warnung(monkeypatch):
    """AC-5: GIVEN ein Bulletin, dessen Freitext-Stufe fuer eine reale Zone
    (Abru-A) vom bekannten Muster '<Kritikalitaet> / ALLERTA <FARBE>'
    abweicht ('Formato sconosciuto / STATO IMPREVISTO', synthetische
    Fail-soft-Fixture, s. tests/fixtures/dpc/README.md), WHEN fetch() fuer
    einen Punkt in dieser Zone laeuft, THEN wirft es KEINE Exception und
    behauptet KEINE Warnung fuer das betroffene Feld."""
    from services.official_alerts.dpc import DpcSource
    import services.official_alerts.dpc as dpc_module

    payload = _read_fixture_bytes("synthetic_unknown_stufe_pattern.zip")
    _reset_dpc_module_caches(dpc_module)
    _set_now(monkeypatch, dpc_module, datetime(2026, 1, 15, 14, 0, tzinfo=timezone.utc))
    with _serve_bytes(payload) as url:
        monkeypatch.setattr(dpc_module, "DPC_ZIP_URL", url)
        alerts = DpcSource().fetch(*ABRU_A_QUIET)

    assert alerts == [], (
        f"Unbekanntes Freitext-Muster darf keine erfundene Warnung erzeugen, "
        f"erhalten: {alerts}"
    )


def test_ac5c_unbekannter_zonencode_wird_geloggt_kein_crash(monkeypatch, caplog):
    """AC-5: GIVEN ein Bulletin mit einem Zonencode ('Xyz-9'), der in
    dpc_zones.json nicht existiert (neben der realen, ungewarnten Zone
    Abru-A im selben Datensatz -- synthetische Fail-soft-Fixture), WHEN
    fetch() fuer einen Punkt in der REALEN Zone laeuft, THEN wirft es KEINE
    Exception, liefert [] (Abru-A selbst ist NESSUNA), UND der unbekannte
    Zonencode erscheint im Diagnose-Log statt kommentarlos zu
    verschwinden."""
    from services.official_alerts.dpc import DpcSource
    import services.official_alerts.dpc as dpc_module

    payload = _read_fixture_bytes("synthetic_unknown_zone_code.zip")
    _reset_dpc_module_caches(dpc_module)
    _set_now(monkeypatch, dpc_module, datetime(2026, 1, 15, 14, 0, tzinfo=timezone.utc))
    with caplog.at_level(logging.WARNING):
        with _serve_bytes(payload) as url:
            monkeypatch.setattr(dpc_module, "DPC_ZIP_URL", url)
            alerts = DpcSource().fetch(*ABRU_A_QUIET)

    assert alerts == [], f"Abru-A ist NESSUNA, erwartet [], erhalten: {alerts}"
    assert "xyz-9" in caplog.text.lower(), (
        f"Unbekannter Zonencode 'Xyz-9' muss im Diagnose-Log erscheinen, "
        f"Log-Text: {caplog.text!r}"
    )


# ---------------------------------------------------------------------------
# AC-6: Gewitter-Ueberschneidung DPC/MeteoAlarm -> genau EIN Eintrag
# ---------------------------------------------------------------------------

class _MeteoAlarmLikeSourceForCollapseTest:
    """Echte, minimale Testdoppel-Quelle (kein Mock/Patch) -- erfuellt das
    OfficialAlertSource-Protocol strukturell. Meldet fuer JEDEN Punkt eine
    thunderstorm-Warnung auf niedrigerer Stufe als DPC im Unwettertag-
    Bulletin (Cala-6 dort Temporali ARANCIONE=3)."""

    @property
    def name(self) -> str:
        return "test-meteoalarm-double"

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float):
        from services.official_alerts.models import OfficialAlert
        return [OfficialAlert(
            source="meteoalarm", hazard="thunderstorm", level=2,
            label="Testdoppel Gewitter GELB",
        )]


def test_ac6_gewitter_ueberschneidung_kollabiert_auf_hoehere_stufe(monkeypatch):
    """AC-6: GIVEN DPC UND MeteoAlarm melden fuer denselben Punkt eine
    Gewitterwarnung (DPC ARANCIONE=3 aus dem Unwettertag-Bulletin,
    Testdoppel GELB=2), WHEN get_official_alerts_with_status() ueber die
    ECHTE Zwei-Pass-Partitionierung (base.py, unveraendert seit
    #1086/#1245) laeuft, THEN erscheint GENAU EIN thunderstorm-Eintrag --
    der mit der hoeheren Stufe (DPC, level=3)."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_with_status, register_official_alert_source
    from services.official_alerts.dpc import DpcSource
    import services.official_alerts.dpc as dpc_module

    payload = _read_fixture_bytes("unwettertag_20260118_1515.zip")
    _reset_dpc_module_caches(dpc_module)
    _set_now(monkeypatch, dpc_module, datetime(2026, 1, 18, 16, 0, tzinfo=timezone.utc))

    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        with _serve_bytes(payload) as url:
            monkeypatch.setattr(dpc_module, "DPC_ZIP_URL", url)
            register_official_alert_source(_MeteoAlarmLikeSourceForCollapseTest())
            register_official_alert_source(DpcSource())

            alerts, _unavailable = get_official_alerts_with_status(*CALA_6_ARANCIONE)
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)

    thunder = [a for a in alerts if a.hazard == "thunderstorm"]
    assert len(thunder) == 1, (
        f"Beide Quellen melden Gewitter fuer denselben Punkt -- erwartet "
        f"GENAU EINEN Eintrag, erhalten {len(thunder)}: {thunder}"
    )
    assert thunder[0].level == 3, (
        f"Die hoehere Stufe (DPC ARANCIONE) muss gewinnen, war "
        f"level={thunder[0].level}"
    )


def test_ac6_reale_paket_registrierungsreihenfolge_meteoalarm_vor_dpc(monkeypatch):
    """AC-6-Voraussetzung (Adversary F001): der obige Kollaps-Test baut sich
    eine EIGENE, isolierte Registry und beweist damit nur den Tie-Break-
    Mechanismus in base.py, NICHT die tatsaechliche Registrierungsreihenfolge
    in services/official_alerts/__init__.py. Bei Stufengleichstand (z.B.
    beide Temporali level=2) gewinnt in der Zwei-Pass-Partitionierung
    (base.py Pass 1: 'bei Gleichstand die ZUERST gesammelte Quelle') die
    zuerst REGISTRIERTE Quelle -- deshalb muss MeteoAlarmSource() in
    __init__.py VOR DpcSource() stehen. Vertauscht man die beiden Zeilen,
    bricht AC-6 exakt bei Stufengleichstand, waehrend KEIN anderer Test in
    dieser Datei das bemerkt (Mutationsprobe des Adversary).

    GIVEN das echte Paket services.official_alerts wird frisch geladen
    (kein nachgebautes Registry-Doppel), WHEN base._REGISTERED_SOURCES nach
    dem Reload ausgelesen wird, THEN steht 'meteoalarm' VOR 'dpc'."""
    import importlib

    import services.official_alerts as oa_package
    import services.official_alerts.base as oa_base

    backup = list(oa_base._REGISTERED_SOURCES)
    try:
        oa_base._REGISTERED_SOURCES.clear()
        importlib.reload(oa_package)  # fuehrt die ECHTEN __init__.py-Registrierungszeilen erneut aus

        names = [s.name for s in oa_base._REGISTERED_SOURCES]
        # Seit Issue #1445 S3 heisst die registrierte Quelle "meteoalarm_feed"
        # (MeteoAlarmFeedSource, country-unabhaengiges .name-Property) -- die
        # alte MeteoAlarmSource ("meteoalarm") wird nicht mehr registriert.
        assert "meteoalarm_feed" in names and "dpc" in names, (
            f"Nach frischem Paket-Reload muessen beide Quellen registriert "
            f"sein, erhalten: {names}"
        )
        assert names.index("meteoalarm_feed") < names.index("dpc"), (
            "MeteoAlarmSource muss in __init__.py VOR DpcSource registriert "
            "werden -- AC-6 verlangt bei GLEICHER Warnstufe (Stufengleichstand) "
            "den Sieg der zuerst registrierten Quelle (Zwei-Pass-Partitionierung, "
            f"base.py Pass 1). Registrierte Reihenfolge: {names}"
        )
    finally:
        # NUR die Registry zuruecksetzen (keinen zweiten reload()) -- ein
        # erneuter reload() wuerde die __init__.py-Registrierungszeilen ein
        # weiteres Mal ausfuehren und die soeben wiederhergestellte Liste mit
        # Dubletten ueberladen.
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


# ---------------------------------------------------------------------------
# AC-7: unavailable bleibt True bei MeteoAlarm-Ausfall trotz erfolgreichem DPC
# ---------------------------------------------------------------------------

class _AlwaysFailingMeteoAlarmDouble:
    """Echte Testdoppel-Quelle (kein Mock): covers=True, fetch() wirft --
    simuliert einen MeteoAlarm-Ausfall (analog _AllCoveringFailSource in
    test_official_alerts_unavailable_hint.py)."""

    @property
    def name(self) -> str:
        return "test-meteoalarm-fail-double"

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float):
        raise RuntimeError("simulierter MeteoAlarm-Ausfall (AC-7)")


def test_ac7_unavailable_bleibt_true_wenn_meteoalarm_ausfaellt_dpc_liefert(monkeypatch):
    """AC-7: GIVEN MeteoAlarm faellt fuer einen italienischen Punkt aus
    (Testdoppel wirft), DPC liefert aber erfolgreich (Unwettertag-Bulletin,
    Cala-6), WHEN get_official_alerts_with_status() laeuft, THEN bleibt
    unavailable=True bestehen -- DPC nimmt den Hinweis 'amtliche Warnungen
    nicht abrufbar' NICHT zurueck (deckt Hitze-/Wind-/Regenwarnungen
    strukturell nicht ab)."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_with_status, register_official_alert_source
    from services.official_alerts.dpc import DpcSource
    import services.official_alerts.dpc as dpc_module

    payload = _read_fixture_bytes("unwettertag_20260118_1515.zip")
    _reset_dpc_module_caches(dpc_module)
    _set_now(monkeypatch, dpc_module, datetime(2026, 1, 18, 16, 0, tzinfo=timezone.utc))

    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        with _serve_bytes(payload) as url:
            monkeypatch.setattr(dpc_module, "DPC_ZIP_URL", url)
            register_official_alert_source(_AlwaysFailingMeteoAlarmDouble())
            register_official_alert_source(DpcSource())

            alerts, unavailable = get_official_alerts_with_status(*CALA_6_ARANCIONE)
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)

    assert unavailable is True, (
        "MeteoAlarm-Ausfall + erfolgreiche DPC-Antwort muss unavailable=True "
        "belassen (DPC ersetzt Hitze-/Wind-/Regenwarnungen nicht, s. AC-7)"
    )
    assert any(a.hazard in ("flood", "thunderstorm") for a in alerts), (
        f"DPC muss trotzdem seine eigenen Warnungen liefern, erhalten: {alerts}"
    )
