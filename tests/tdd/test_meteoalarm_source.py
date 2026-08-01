"""TDD RED/GREEN — Issue #1086: MeteoAlarmSource (amtliche Warnungen AT/IT, Slice 2).

SPEC: docs/specs/modules/issue_1086_meteoalarm_source.md (Rev 2, nach
Adversary-Befund BROKEN F001/F002)
Kontext: docs/context/feat-1086-meteoalarm-source.md
AC-1 bis AC-7

Rev 2 (Adversary-Korrektur): der Cross-Source-Kollaps laeuft NICHT mehr ueber
eine geteilte ``normalize_gemeinde_name()``-Funktion + normalisierte
``dedup_id`` (das kollabierte im Orts-Vergleich faelschlich VERSCHIEDENE Orte
mit aehnlichem Namen, F002 CRITICAL, und crashte ``GeoSphereWarnSource`` bei
``region_label=None``, F001 HIGH). Der Kollaps sitzt jetzt ausschliesslich in
``get_official_alerts_for_location()`` (``base.py``) -- pro EINZELNEM Punkt,
vor jeder ortsuebergreifenden Kombination. ``dedup_id`` bleibt bei beiden
Quellen ``None``. AC-6/AC-7 sichern das gegen Regression bzw. den urspruenglich
gefundenen Adversary-Fall ab.

Diese Tests schlagen ABSICHTLICH fehl, solange ``services.official_alerts.
meteoalarm`` noch nicht existiert -> ModuleNotFoundError/ImportError beim
jeweils ersten Import innerhalb der Testfunktion (= korrektes RED). Ausnahme
AC-6: reiner Regressions-Waechter fuer die BESTEHENDE FR-Dedup-Logik
(``dedupe_official_alerts`` wird durch diese Spec NICHT veraendert) --
dieser Test ist bewusst schon JETZT gruen und bleibt es nach der
Implementierung (kein neues Verhalten, sondern ein Nicht-Regressions-Beweis).

KEINE Mocks (CLAUDE.md-Projektkonvention "KEINE MOCKED TESTS!"):
- AC-1/AC-2-Live-Tests rufen die echte MeteoAlarm-EDR-API
  (``https://api.meteoalarm.org/edr/v1``) inkl. echtem CAP-XML-Nachladen auf,
  kein Mock, kein Patch. Marker ``@pytest.mark.live`` (Default-Testlauf
  schliesst diese Marker aus, siehe pyproject.toml ``addopts``).
- AC-3/AC-4 rufen die reine Mapping-Funktion ``_extract_alerts_from_cap``
  direkt mit versionierten, echten bzw. aus der CAP-Doku abgeleiteten
  Fixture-Dateien auf (kein Netzwerk-Mock, nur Testdaten).
- AC-5b nutzt einen ECHTEN lokalen HTTP-Server (``http.server``), der ein
  kaputtes JSON liefert -- kein Mock der HTTP-Bibliothek, sondern ein echter
  Socket-Roundtrip mit absichtlich defektem Inhalt (analog dem
  Graubuenden-404-Testmuster aus ``test_issue_1085_geosphere_warn.py``, dort
  gegen die echte Fremd-API, hier lokal, weil ein kaputtes JSON bei der
  echten API nicht reproduzierbar provoziert werden kann).
- AC-5a/AC-5d entfernen die ENV-Variable temporaer (kein Mock).
"""
from __future__ import annotations

import http.server
import json
import os
import threading
import urllib.parse
from pathlib import Path

import pytest

from services.official_alerts.models import OfficialAlert

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "meteoalarm"

# Reale Koordinaten aus Spec/Kontext-Dokument.
VILLACH = (46.61, 13.85)  # Oesterreich, GeoSphere UND MeteoAlarm decken ab (Dedup-Fall)
SOUTH_TYROL_BOZEN = (46.4983, 11.3548)  # Italien (Suedtirol), nur MeteoAlarm

_ALLOWED_HAZARDS = {
    "wind_gust", "snow", "thunderstorm", "extreme_heat",
    "extreme_cold", "wildfire_risk", "rain",
}


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _meteoalarm_index_cache_isolation(monkeypatch):
    """Issue #1397 S1c: der Index-Cache-Schluessel enthaelt jetzt einen
    Zeitslot (``f"{country}:{slot}:p{n}"``, s. ``_current_slot_end``) --
    Tests koennen ihn nicht mehr vorab hardcoden, und da ALLE Tests eines
    Laufs typischerweise im SELBEN 30-Minuten-Slot laufen, wuerde ohne
    Reset ein Cache-Eintrag aus Test A in Test B durchschlagen (Cache-
    Pollution). Autouse: leert ``_index_cache`` VOR und NACH jedem Test.

    Setzt zugleich ``_SLEEP_FN`` auf ein No-Op (Standard fuer alle Tests
    dieser Datei, s. Projekt-Testpolitik "kein echtes time.sleep() im
    Test") -- einzelne Tests, die die tatsaechliche Wartezeit pruefen
    wollen, ueberschreiben ``_SLEEP_FN``/``_WALL_CLOCK_FN`` selbst per
    ``monkeypatch`` (wirkt NACH dieser Fixture, da im selben Testlauf)."""
    from services.official_alerts import meteoalarm

    def _clear_module_caches() -> None:
        meteoalarm._index_cache.clear()
        # S1c macht Nachlade-Abrufe fuer Features aus einem (jetzt moeglichen)
        # Teilergebnis erreichbar, die vorher wegen des sofortigen ``None``
        # nie ausgefuehrt wurden -- ohne Reset wuerde ein Geometrie-/CAP-
        # Cache-Treffer aus einem FRUEHEREN Test einen erwarteten echten
        # Nachlade-Abruf in einem SPAETEREN Test verdecken.
        meteoalarm._geometry_cache.clear()
        meteoalarm._cap_cache.clear()

    _clear_module_caches()
    monkeypatch.setattr(meteoalarm, "_SLEEP_FN", lambda _seconds: None)
    yield
    _clear_module_caches()


# ---------------------------------------------------------------------------
# AC-1: Live-Punkt Suedtirol -> struktureller Vertrag / echte Warnung
# ---------------------------------------------------------------------------

@pytest.mark.live
def test_ac1_live_suedtirol_struktureller_vertrag_oder_echte_warnung():
    """AC-1: GIVEN ein Punkt in Suedtirol, WHEN MeteoAlarmSource.fetch() live
    aufgerufen wird, THEN liefert das Ergebnis entweder mind. einen
    OfficialAlert mit source='meteoalarm' und korrektem hazard/level (falls
    zum Testzeitpunkt eine Warnung aktiv ist), ODER -- falls keine Warnung
    vorliegt -- der strukturelle Vertrag wird ueber die aufgezeichnete
    CAP-Fixture nachgewiesen (tolerant laut AC-1, Warnlage ist tagesabhaengig)."""
    from services.official_alerts.meteoalarm import MeteoAlarmSource, _extract_alerts_from_cap

    if not os.environ.get("GZ_METEOALARM_APIKEY"):
        pytest.skip("GZ_METEOALARM_APIKEY nicht konfiguriert (.env)")

    source = MeteoAlarmSource()
    alerts = source.fetch(*SOUTH_TYROL_BOZEN)

    assert isinstance(alerts, list)

    if alerts:
        for alert in alerts:
            assert alert.source == "meteoalarm"
            assert alert.level in (2, 3, 4)
            assert alert.hazard in _ALLOWED_HAZARDS, (
                f"hazard {alert.hazard!r} nicht im dokumentierten Mapping-Vokabular"
            )
            assert alert.label and isinstance(alert.label, str)
            assert alert.region_label, "region_label muss aus areaDesc befuellt sein"
    else:
        # Keine aktive Warnung zum Testzeitpunkt: struktureller Vertrag ueber
        # eine echte, aufgezeichnete CAP-Struktur (Villach-Hitze-Fixture).
        cap_text = _read_fixture("cap_villach_heat.xml")
        synth_alerts = _extract_alerts_from_cap(cap_text)
        assert len(synth_alerts) == 1, (
            "Mapping-Funktion muss aus der aufgezeichneten CAP-Struktur genau "
            "einen OfficialAlert bilden (deutscher <info>-Block)"
        )
        assert synth_alerts[0].source == "meteoalarm"
        assert synth_alerts[0].hazard == "extreme_heat"
        assert synth_alerts[0].level == 2
        assert synth_alerts[0].region_label == "Villach (Stadt)"


# ---------------------------------------------------------------------------
# AC-2: Cross-Source-Dedup AT (Villach) -- Kern (Punkt-Kollaps) + Live
#
# Rev 2 (Adversary-Korrektur F002): der Kollaps sitzt in
# get_official_alerts_for_location(), nicht mehr in einem normalisierten
# Namens-Schluessel. Zwei kontrollierte Test-Quellen (reale Objekte, die das
# OfficialAlertSource-Protocol strukturell erfuellen -- kein Mock des
# Codes-under-test) werden ueber die echte Registry registriert.
# ---------------------------------------------------------------------------

class _FixedGeoSphereLikeSource:
    """Reale Test-Quelle (kein Mock): liefert einen festen Hitze-Alert mit
    GeoSphere-typischem Label, konfigurierbarer Stufe."""

    name = "fixed_geosphere_like_test_source"

    def __init__(self, level: int = 2) -> None:
        self._level = level

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        return [
            OfficialAlert(
                source="geosphere_warn", hazard="extreme_heat", level=self._level,
                label="Hitze", region_label="Villach",
            )
        ]


class _FixedMeteoAlarmLikeSource:
    """Reale Test-Quelle (kein Mock): liefert einen festen Hitze-Alert mit
    MeteoAlarm-typischem (abweichendem) Label, konfigurierbarer Stufe."""

    name = "fixed_meteoalarm_like_test_source"

    def __init__(self, level: int = 2) -> None:
        self._level = level

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        return [
            OfficialAlert(
                source="meteoalarm", hazard="extreme_heat", level=self._level,
                label="Hitzewarnung", region_label="Villach (Stadt)",
            )
        ]


def test_ac2_kern_punkt_kollaps_geosphere_und_meteoalarm_gleiche_stufe():
    """AC-2 (Kern, Rev 2): GIVEN eine GeoSphere-artige (level=2) UND eine
    MeteoAlarm-artige (level=2) Test-Quelle fuer denselben Punkt, beide mit
    hazard='extreme_heat', WHEN get_official_alerts_for_location() aufgerufen
    wird, THEN liefert das Ergebnis genau EINEN extreme_heat-Alert mit dem
    Label der ZUERST registrierten Quelle (Tie-Break bei gleicher Stufe)."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_for_location, register_official_alert_source

    backup_sources = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        register_official_alert_source(_FixedGeoSphereLikeSource(level=2))
        register_official_alert_source(_FixedMeteoAlarmLikeSource(level=2))

        alerts = get_official_alerts_for_location(*VILLACH)

        heat_alerts = [a for a in alerts if a.hazard == "extreme_heat"]
        assert len(heat_alerts) == 1, (
            f"Gleiche Gefahr, gleicher Punkt, zwei Quellen muessen zu EINEM "
            f"Alert kollabieren, erhalten {len(heat_alerts)}"
        )
        assert heat_alerts[0].region_label == "Villach", (
            "Bei gleicher Stufe muss die ZUERST registrierte Quelle "
            f"(GeoSphere-artig) der Repraesentant bleiben, war "
            f"region_label={heat_alerts[0].region_label!r}"
        )
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup_sources)


def test_ac2_kern_punkt_kollaps_hoehere_stufe_gewinnt():
    """AC-2 (Kern-Variante, Rev 2): GIVEN dieselbe Konstellation, aber die
    MeteoAlarm-artige Quelle meldet eine HOEHERE Stufe (level=3), WHEN
    get_official_alerts_for_location() aufgerufen wird, THEN gewinnt die
    hoehere Stufe -- Repraesentant ist der MeteoAlarm-artige Alert."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_for_location, register_official_alert_source

    backup_sources = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        register_official_alert_source(_FixedGeoSphereLikeSource(level=2))
        register_official_alert_source(_FixedMeteoAlarmLikeSource(level=3))

        alerts = get_official_alerts_for_location(*VILLACH)

        heat_alerts = [a for a in alerts if a.hazard == "extreme_heat"]
        assert len(heat_alerts) == 1
        assert heat_alerts[0].level == 3, (
            f"Hoehere Stufe muss gewinnen, erhalten level={heat_alerts[0].level}"
        )
        assert heat_alerts[0].region_label == "Villach (Stadt)", (
            "Bei hoeherer Stufe muss die MeteoAlarm-artige Quelle der "
            f"Repraesentant sein, war region_label={heat_alerts[0].region_label!r}"
        )
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup_sources)


@pytest.mark.live
def test_ac2_live_villach_dedup_meteoalarm_und_geosphere():
    """AC-2 Live: GIVEN Villach (echter AT-Punkt), WHEN GeoSphereWarnSource
    UND MeteoAlarmSource live abgefragt werden UND dedupe_official_alerts()
    auf das kombinierte Ergebnis angewendet wird, THEN erscheint jede Gefahr,
    die von BEIDEN Quellen gemeldet wird, danach genau einmal."""
    from output.renderers.alert.official_alerts import dedupe_official_alerts
    from services.official_alerts.geosphere_warn import GeoSphereWarnSource
    from services.official_alerts.meteoalarm import MeteoAlarmSource

    if not os.environ.get("GZ_METEOALARM_APIKEY"):
        pytest.skip("GZ_METEOALARM_APIKEY nicht konfiguriert (.env)")

    geosphere_alerts = GeoSphereWarnSource().fetch(*VILLACH)
    meteoalarm_alerts = MeteoAlarmSource().fetch(*VILLACH)

    raw_by_hazard: dict[str, list[OfficialAlert]] = {}
    for a in geosphere_alerts + meteoalarm_alerts:
        raw_by_hazard.setdefault(a.hazard, []).append(a)

    tagged = [(a, []) for a in geosphere_alerts] + [(a, []) for a in meteoalarm_alerts]
    deduped = dedupe_official_alerts(tagged)

    deduped_by_hazard: dict[str, list[OfficialAlert]] = {}
    for a, _seg in deduped:
        deduped_by_hazard.setdefault(a.hazard, []).append(a)

    overlapping_hazards = 0
    for hazard, raws in raw_by_hazard.items():
        sources = {a.source for a in raws}
        if {"geosphere_warn", "meteoalarm"} <= sources:
            overlapping_hazards += 1
            assert len(deduped_by_hazard[hazard]) == 1, (
                f"Gefahr {hazard!r} von BEIDEN Quellen gemeldet, muss nach "
                f"dedupe_official_alerts() genau 1 Eintrag ergeben, war "
                f"{len(deduped_by_hazard[hazard])}"
            )
    # Kein hartes Bestehen auf ueberlappende Gefahren -- Warnlage ist
    # tagesabhaengig (AC-1-Toleranzprinzip gilt analog).


# ---------------------------------------------------------------------------
# AC-3: Level-1 (gruen) wird gefiltert
# ---------------------------------------------------------------------------

def test_ac3_gruene_stufe_level1_wird_gefiltert():
    """AC-3: GIVEN eine aufgezeichnete/synthetische CAP-Fixture mit
    awareness_level='1; green; Minor', WHEN die Mapping-Funktion diese
    verarbeitet, THEN wird KEIN OfficialAlert zurueckgegeben."""
    from services.official_alerts.meteoalarm import _extract_alerts_from_cap

    cap_text = _read_fixture("cap_green_level1.xml")
    alerts = _extract_alerts_from_cap(cap_text)

    assert alerts == [], (
        f"Level-1 (gruen) muss gefiltert werden (analog Vigilance/GeoSphere), "
        f"erhalten: {alerts}"
    )


# ---------------------------------------------------------------------------
# AC-4: Unbekannter awareness_type (Lawine) wird uebersprungen, kein Crash
# ---------------------------------------------------------------------------

def test_ac4_lawine_uebersprungen_hitze_bleibt_erhalten():
    """AC-4: GIVEN eine synthetische CAP-Fixture mit ZWEI Warnungen fuer
    denselben Punkt (awareness_type=9 Lawine, keine App-Kategorie UND
    awareness_type=5 Hitze), WHEN die Mapping-Funktion die Antwort
    verarbeitet, THEN wird die Lawinen-Warnung uebersprungen (kein Eintrag,
    kein Crash) und die Hitze-Warnung erscheint unveraendert."""
    from services.official_alerts.meteoalarm import _extract_alerts_from_cap

    cap_text = _read_fixture("cap_avalanche_plus_heat.xml")
    alerts = _extract_alerts_from_cap(cap_text)

    assert len(alerts) == 1, (
        f"Lawinen-Warnung (awareness_type=9) muss uebersprungen werden, "
        f"erwartet genau 1 Alert (Hitze), erhalten {len(alerts)}"
    )
    assert alerts[0].hazard == "extreme_heat"
    assert alerts[0].level == 2


# ---------------------------------------------------------------------------
# AC-5: Fail-soft (fehlende ENV / kaputtes Index-JSON / kaputtes CAP-XML) +
# Fehler-Isolation gegenueber anderen Quellen
# ---------------------------------------------------------------------------

def test_ac5a_fehlende_env_liefert_leere_liste():
    """AC-5a: GIVEN GZ_METEOALARM_APIKEY ist nicht gesetzt, WHEN fetch()
    aufgerufen wird, THEN liefert fetch() [] ohne Exception (analog
    vigilance.py test_ac2_fail_soft_ohne_apikey)."""
    from services.official_alerts.meteoalarm import MeteoAlarmSource

    backup = os.environ.pop("GZ_METEOALARM_APIKEY", None)
    try:
        source = MeteoAlarmSource()
        assert source.covers(*VILLACH) is True
        alerts = source.fetch(*VILLACH)
        assert alerts == [], "fetch() muss bei fehlender ENV [] liefern, kein Crash"
    finally:
        if backup is not None:
            os.environ["GZ_METEOALARM_APIKEY"] = backup


class _BrokenJSONHandler(http.server.BaseHTTPRequestHandler):
    """Echter lokaler HTTP-Server (kein Mock der HTTP-Bibliothek): liefert
    fuer JEDEN Pfad denselben absichtlich kaputten JSON-Koerper."""

    def do_GET(self):  # noqa: N802 - stdlib-Signatur
        body = b'{"type": "FeatureCollection", "features": [BROKEN'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):  # Testlauf-Output nicht zumuellen
        pass


def test_ac5b_kaputtes_index_json_liefert_leere_liste(monkeypatch, tmp_path):
    """AC-5b: GIVEN eine echte HTTP-Antwort (lokaler Test-Server) mit
    strukturell kaputtem JSON-Koerper, WHEN fetch() den Index-Call macht,
    THEN liefert fetch() [] ohne Exception."""
    from services.official_alerts import meteoalarm

    # WARN_CALLS_PATH-Umlenkung erfolgt global via conftest-Autouse-Fixture
    # ``_isolate_warn_calls_path`` (Issue #1348) — kein Per-Test-Monkeypatch nötig.
    server = http.server.HTTPServer(("127.0.0.1", 0), _BrokenJSONHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv("GZ_METEOALARM_APIKEY", "dummy-test-token-red-phase")
        monkeypatch.setattr(
            meteoalarm, "METEOALARM_BASE_URL",
            f"http://127.0.0.1:{server.server_port}",
        )

        source = meteoalarm.MeteoAlarmSource()
        alerts = source.fetch(*VILLACH)
        assert alerts == [], (
            f"Kaputtes Index-JSON muss fail-soft [] liefern, kein Crash, "
            f"erhalten: {alerts}"
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_ac5c_kaputtes_cap_xml_wird_uebersprungen_kein_crash():
    """AC-5c: GIVEN eine absichtlich strukturell kaputte CAP-XML-Fixture,
    WHEN die Mapping-Funktion diese verarbeitet, THEN wird die betroffene
    Warnung uebersprungen -- die Funktion wirft NICHT."""
    from services.official_alerts.meteoalarm import _extract_alerts_from_cap

    cap_text = _read_fixture("cap_broken.xml")
    alerts = _extract_alerts_from_cap(cap_text)

    assert alerts == [], (
        f"Kaputtes CAP-XML darf keinen Alert liefern und nicht crashen, "
        f"erhalten: {alerts}"
    )


def test_ac5d_meteoalarm_fehlschlag_leert_andere_quelle_nicht():
    """AC-5d: GIVEN die Registry mit einer synthetischen AT-Quelle UND
    MeteoAlarmSource (fehlende ENV, garantierter Fehlschlag), WHEN
    get_official_alerts_for_location() fuer einen AT-Punkt aufgerufen wird,
    THEN bleibt das Ergebnis der anderen Quelle vollstaendig erhalten
    (Fehler-Isolation der Registry, #1034, bleibt mit MeteoAlarmSource intakt).

    Nutzt eine minimale, handgeschriebene Quelle (kein Mock/Patch, sondern
    eine reale Objektimplementierung des OfficialAlertSource-Protocols mit
    festem Rueckgabewert), um den Test unabhaengig von der tatsaechlichen
    Live-Warnlage der echten GeoSphere-API deterministisch zu halten."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_for_location, register_official_alert_source
    from services.official_alerts.meteoalarm import MeteoAlarmSource

    class _FixedAtSource:
        name = "fixed_at_test_source"

        def covers(self, lat: float, lon: float) -> bool:
            return True

        def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
            return [
                OfficialAlert(
                    source="fixed_at_test_source", hazard="extreme_heat",
                    level=2, label="Testwarnung", region_label="Villach",
                )
            ]

    backup_env = os.environ.pop("GZ_METEOALARM_APIKEY", None)
    backup_sources = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        register_official_alert_source(_FixedAtSource())
        register_official_alert_source(MeteoAlarmSource())

        alerts = get_official_alerts_for_location(*VILLACH)

        assert isinstance(alerts, list)
        assert any(a.source == "fixed_at_test_source" for a in alerts), (
            "MeteoAlarm-Fehlschlag (fehlende ENV) darf das Ergebnis der "
            "anderen registrierten Quelle nicht leeren"
        )
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup_sources)
        if backup_env is not None:
            os.environ["GZ_METEOALARM_APIKEY"] = backup_env


class _EmptyBody204Handler(http.server.BaseHTTPRequestHandler):
    """Echter lokaler HTTP-Server (kein Mock der HTTP-Bibliothek): liefert
    fuer JEDEN Pfad HTTP 204 (No Content) mit leerem Koerper -- so antwortet
    ``api.meteoalarm.org`` real, wenn ein Land aktuell keine Warnungen hat."""

    def do_GET(self):  # noqa: N802 - stdlib-Signatur
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *_args):  # Testlauf-Output nicht zumuellen
        pass


def test_leerer_index_204_ist_kein_fehler(monkeypatch, caplog, tmp_path):
    """GIVEN eine echte HTTP-Antwort (lokaler Test-Server) mit Status 204
    und leerem Koerper (regulaerer "keine Warnung"-Fall bei MeteoAlarm),
    WHEN ``_get_cached_index()`` diese verarbeitet, THEN liefert es ein
    leeres, aber gueltiges Ergebnis OHNE Exception, cached es als ERFOLG
    (Issue #1397 S1c: ``INDEX_PAGE_SUCCESS_TTL``, kein Failure-Cache) und
    loggt KEIN WARNING."""
    from services.official_alerts import meteoalarm

    # WARN_CALLS_PATH-Umlenkung erfolgt global via conftest-Autouse-Fixture
    # ``_isolate_warn_calls_path`` (Issue #1348) — kein Per-Test-Monkeypatch nötig.
    server = http.server.HTTPServer(("127.0.0.1", 0), _EmptyBody204Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv("GZ_METEOALARM_APIKEY", "dummy-test-token-204")
        monkeypatch.setattr(
            meteoalarm, "METEOALARM_BASE_URL",
            f"http://127.0.0.1:{server.server_port}",
        )

        with caplog.at_level("WARNING", logger="meteoalarm"):
            data = meteoalarm._get_cached_index("IT")

        assert data == {"features": []}, (
            f"204/leerer Body muss als leeres, gueltiges Ergebnis behandelt "
            f"werden, erhalten: {data}"
        )
        assert not any(
            "fehlgeschlagen" in rec.message for rec in caplog.records
        ), "204/leerer Body ist der reguläre Fall, kein WARNING-Log erlaubt"

        # Issue #1397 S1c: Cache-Schluessel enthaelt zusaetzlich den
        # Zeitslot ("{country}:{slot}:p{n}") -- Tests kennen ihn nicht im
        # Voraus, s. ``_index_cache_entries_for()``.
        entries = meteoalarm._index_cache_entries_for("IT", 1)
        assert len(entries) == 1, f"genau EIN Cache-Eintrag fuer IT-Seite-1 erwartet, war {entries}"
        cache_entry = entries[0]
        assert cache_entry["ttl"] == meteoalarm.INDEX_PAGE_SUCCESS_TTL, (
            f"204/leerer Body muss als ERFOLG gecacht werden "
            f"(INDEX_PAGE_SUCCESS_TTL), nicht als Fehlschlag, erhalten ttl={cache_entry['ttl']}"
        )

        # Zweiter Aufruf innerhalb der TTL darf keinen erneuten HTTP-Call
        # ausloesen -- Server abschalten und pruefen, dass der Cache-Treffer
        # trotzdem klappt (kein ConnectionError).
        server.shutdown()
        thread.join(timeout=2)
        data_cached = meteoalarm._get_cached_index("IT")
        assert data_cached == {"features": []}
    finally:
        try:
            server.shutdown()
        except Exception:
            pass
        thread.join(timeout=2)


# ---------------------------------------------------------------------------
# AC-6: FR-Dedup-Regression -- dedupe_official_alerts() bleibt fuer
# Frankreich-Quellen unveraendert (REGRESSIONS-WAECHTER, bewusst schon jetzt
# gruen: die AT-Dedup-Aenderung wirkt laut Spec ausschliesslich auf
# GeoSphereWarnSource/MeteoAlarmSource-Objekte -- kein neues Verhalten fuer
# FR, daher kein RED-Zustand fuer diesen einen Test).
# ---------------------------------------------------------------------------

def test_ac6_fr_dedup_regression_unveraendert():
    """AC-6: GIVEN die real genutzten FR-Testfaelle aus #1035/#1036/#1037
    (Vigilance-Region-Dedup + Massiv-Sperre-dedup_id-Eskalation), WHEN
    dedupe_official_alerts() darauf angewendet wird, THEN ist das Ergebnis
    byte-/wertidentisch zum Stand vor dieser Spec -- keine neue Kollision,
    keine veraenderte Gruppierung."""
    from output.renderers.alert.official_alerts import dedupe_official_alerts

    # Fall 1 (#1035-Muster): gleiche region_label+hazard, zwei Stufen ->
    # kollabiert auf die hoechste Stufe (region-Namespace, kein dedup_id).
    heat_low = OfficialAlert(
        source="meteofrance_vigilance", hazard="extreme_heat", level=2,
        label="Hitzewarnung Haute-Corse", region_label="Haute-Corse",
    )
    heat_high = OfficialAlert(
        source="meteofrance_vigilance", hazard="extreme_heat", level=4,
        label="Hitzewarnung Haute-Corse", region_label="Haute-Corse",
    )

    # Fall 2 (#1036/#1037-Muster, F001): Massiv-Sperre mit stabiler dedup_id,
    # Label traegt die Stufe im Text -- muss trotzdem ueber dedup_id kollabieren.
    massif_low = OfficialAlert(
        source="massif_closure", hazard="access_ban", level=3,
        label="Zugang eingeschraenkt — Massif de l'Esterel", region_label=None,
        dedup_id="ESTEREL-MASSIF-ID",
    )
    massif_high = OfficialAlert(
        source="massif_closure", hazard="access_ban", level=4,
        label="Zugang gesperrt — Massif de l'Esterel", region_label=None,
        dedup_id="ESTEREL-MASSIF-ID",
    )

    # Nicht-Regressions-Waechter: verschiedene hazards / verschiedene Regionen
    # duerfen NICHT kollabieren (#1218 AC-5).
    thunder = OfficialAlert(
        source="meteofrance_vigilance", hazard="thunderstorm", level=3,
        label="Gewitter Haute-Corse", region_label="Haute-Corse",
    )
    heat_other_region = OfficialAlert(
        source="meteofrance_vigilance", hazard="extreme_heat", level=3,
        label="Hitzewarnung Corse-du-Sud", region_label="Corse-du-Sud",
    )

    tagged = [
        (heat_low, ["1"]), (heat_high, ["2"]),
        (massif_low, ["1"]), (massif_high, ["2"]),
        (thunder, ["1"]),
        (heat_other_region, ["1"]),
    ]
    deduped = dedupe_official_alerts(tagged)

    assert len(deduped) == 4, (
        f"Erwartet 4 Gruppen (Hitze-Haute-Corse, Massiv-Esterel, Gewitter, "
        f"Hitze-Corse-du-Sud), erhalten {len(deduped)}: "
        f"{[(a.hazard, a.region_label, a.dedup_id) for a, _ in deduped]}"
    )

    by_key = {(a.hazard, a.region_label or a.dedup_id): (a, segs) for a, segs in deduped}

    heat_repr, heat_segs = by_key[("extreme_heat", "Haute-Corse")]
    assert heat_repr.level == 4, "Hitze-Haute-Corse muss auf die hoechste Stufe (4) kollabieren"
    assert sorted(heat_segs) == ["1", "2"], "Segment-Union muss beide Etappen enthalten"

    massif_repr, _massif_segs = by_key[("access_ban", "ESTEREL-MASSIF-ID")]
    assert massif_repr.level == 4
    assert massif_repr.label == "Zugang gesperrt — Massif de l'Esterel", (
        "Massiv-Sperre muss auf die hoechste Stufe (4, 'gesperrt') kollabieren"
    )

    assert ("thunderstorm", "Haute-Corse") in by_key, "Gewitter darf nicht mit Hitze kollabieren"
    assert ("extreme_heat", "Corse-du-Sud") in by_key, "Andere Region darf nicht kollabieren"


# ---------------------------------------------------------------------------
# AC-6 (Adversary-Befund F003): Regressions-Waechter fuer den ECHTEN
# Registry-Pfad mit FR-artigen Quellen -- nicht nur dedupe_official_alerts()
# mit vorgefertigten Listen. Der Punkt-Kollaps in
# get_official_alerts_for_location() ist bewusst GENERISCH (ein Punkt + eine
# Gefahrenart -> ein Alert). Fuer FR ist das faktisch folgenlos, weil
# Vigilance/MeteoForets/MassifClosure an einem Punkt NIE denselben hazard
# liefern -- dieser Test belegt genau das ueber die echte Registry.
# ---------------------------------------------------------------------------

class _FixedVigilanceLikeSource:
    """Reale Test-Quelle (kein Mock): FR-Vigilance-artig, hazard=thunderstorm."""

    name = "fixed_vigilance_like_test_source"

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        return [
            OfficialAlert(
                source="meteofrance_vigilance", hazard="thunderstorm", level=3,
                label="Gewitter Haute-Corse", region_label="Haute-Corse",
            )
        ]


class _FixedMeteoForetsLikeSource:
    """Reale Test-Quelle (kein Mock): FR-MeteoForets-artig, hazard=wildfire_risk."""

    name = "fixed_meteo_forets_like_test_source"

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        return [
            OfficialAlert(
                source="meteo_forets", hazard="wildfire_risk", level=2,
                label="Waldbrandgefahr Haute-Corse", region_label="Haute-Corse",
            )
        ]


class _FixedMassifClosureLikeSource:
    """Reale Test-Quelle (kein Mock): FR-MassifClosure-artig, hazard=access_ban."""

    name = "fixed_massif_closure_like_test_source"

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        return [
            OfficialAlert(
                source="massif_closure", hazard="access_ban", level=3,
                label="Zugang eingeschraenkt — Massif de l'Esterel", region_label=None,
                dedup_id="ESTEREL-MASSIF-ID",
            )
        ]


class _FixedVigilanceLikeSourceLowLevel:
    """Reale Test-Quelle (kein Mock): identischer hazard wie
    _FixedVigilanceLikeSource, aber niedrigere Stufe -- fuer den zweiten
    Assert-Block (bewusster generischer Kollaps bei GLEICHEM hazard)."""

    name = "fixed_vigilance_like_test_source_low"

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        return [
            OfficialAlert(
                source="meteofrance_vigilance", hazard="thunderstorm", level=1,
                label="Gewitter (schwach) Haute-Corse", region_label="Haute-Corse",
            )
        ]


HAUTE_CORSE = (42.3, 9.15)  # Punkt in Frankreich (Korsika), analog Spec-Kontext


def test_ac6_registry_pfad_fr_quellen_kein_kollaps():
    """AC-6 (Adversary-Korrektur F003, Kern): GIVEN drei FR-artige
    Test-Quellen (Vigilance/MeteoForets/MassifClosure), die fuer DENSELBEN
    Punkt Alerts mit DREI VERSCHIEDENEN hazard-Werten liefern (analog dem
    realen FR-Muster: Vigilance/MeteoForets/MassifClosure teilen nie einen
    hazard), WHEN get_official_alerts_for_location() -- der ECHTE
    Registry-Pfad, nicht nur dedupe_official_alerts() mit vorgefertigten
    Listen -- aufgerufen wird, THEN bleiben ALLE drei Alerts erhalten
    (kein Kollaps, weil verschiedene hazards), Reihenfolge/Werte
    unveraendert."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_for_location, register_official_alert_source

    backup_sources = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        register_official_alert_source(_FixedVigilanceLikeSource())
        register_official_alert_source(_FixedMeteoForetsLikeSource())
        register_official_alert_source(_FixedMassifClosureLikeSource())

        alerts = get_official_alerts_for_location(*HAUTE_CORSE)

        assert len(alerts) == 3, (
            f"Drei verschiedene hazards an einem Punkt duerfen NICHT "
            f"kollabieren, erwartet 3 Alerts, erhalten {len(alerts)}: "
            f"{[(a.hazard, a.level, a.label) for a in alerts]}"
        )
        hazards_in_order = [a.hazard for a in alerts]
        assert hazards_in_order == ["thunderstorm", "wildfire_risk", "access_ban"], (
            f"Reihenfolge muss dem ersten Auftreten (=Registrierungsreihenfolge) "
            f"entsprechen, erhalten {hazards_in_order}"
        )

        by_hazard = {a.hazard: a for a in alerts}
        assert by_hazard["thunderstorm"].level == 3
        assert by_hazard["thunderstorm"].label == "Gewitter Haute-Corse"
        assert by_hazard["wildfire_risk"].level == 2
        assert by_hazard["wildfire_risk"].label == "Waldbrandgefahr Haute-Corse"
        assert by_hazard["access_ban"].level == 3
        assert by_hazard["access_ban"].label == "Zugang eingeschraenkt — Massif de l'Esterel"
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup_sources)

    # Zweiter Assert-Block: die generische Invariante als GEWOLLT
    # dokumentieren -- zwei Test-Quellen mit GLEICHEM hazard an einem Punkt
    # (verschiedene level) -> genau EIN Alert, hoechste Stufe, Label der
    # ZUERST registrierten Quelle. Belegt: der Kollaps ist bewusst generisch
    # und korrekt, nicht AT-spezifisch (Spec-Praezisierung AC-6, Adversary F003).
    backup_sources = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        # Reihenfolge bewusst so gewaehlt, dass die ZUERST registrierte
        # Quelle auch die hoechste Stufe traegt (level=3 vor level=1): so
        # bestaetigt der Test beide Teile der dokumentierten Invariante
        # gleichzeitig -- "hoechste Stufe gewinnt" UND "Label der zuerst
        # registrierten Quelle" -- konsistent mit der Kollaps-Logik in
        # base.py (ein SPAETER registrierter Alert ersetzt den bisherigen
        # Repraesentanten nur bei STRIKT hoeherer Stufe, s. AC-2-Tests).
        register_official_alert_source(_FixedVigilanceLikeSource())
        register_official_alert_source(_FixedVigilanceLikeSourceLowLevel())

        alerts = get_official_alerts_for_location(*HAUTE_CORSE)

        thunder_alerts = [a for a in alerts if a.hazard == "thunderstorm"]
        assert len(thunder_alerts) == 1, (
            f"Gleicher hazard, gleicher Punkt, zwei Quellen muessen generisch "
            f"zu EINEM Alert kollabieren -- das ist die gewollte Invariante, "
            f"nicht AT-spezifisch, erhalten {len(thunder_alerts)}"
        )
        assert thunder_alerts[0].level == 3, (
            f"Hoechste Stufe muss gewinnen, erhalten level={thunder_alerts[0].level}"
        )
        assert thunder_alerts[0].label == "Gewitter Haute-Corse", (
            "Bei niedrigerer Stufe des SPAETER registrierten Kandidaten "
            "bleibt der ZUERST registrierte Alert (samt Label) "
            f"Repraesentant, war label={thunder_alerts[0].label!r}"
        )
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup_sources)


# ---------------------------------------------------------------------------
# AC-7 (Adversary-Regression F002, CRITICAL): zwei VERSCHIEDENE Orte mit
# aehnlichem Warngebiets-/Gemeindenamen duerfen NICHT ueber
# dedupe_official_alerts() im Mehr-Orte-Fall des Orts-Vergleichs verschmelzen.
# ---------------------------------------------------------------------------

def test_ac7_zwei_verschiedene_orte_aehnlicher_name_kollabieren_nicht():
    """AC-7: GIVEN zwei OfficialAlert-Objekte unterschiedlicher region_label
    ('Villach (Stadt)' level=2 fuer Ort A, 'Villach Land' level=4 fuer Ort B),
    dieselbe Gefahr, getaggt mit zwei verschiedenen loc_ids, WHEN
    dedupe_official_alerts() auf die kombinierte Mehr-Orte-Liste (wie im
    Orts-Vergleich, compare_official_alert.py::_detect) angewendet wird,
    THEN liefert das Ergebnis ZWEI Eintraege mit je korrekter Stufe/Label --
    keine ortsuebergreifende Verschmelzung, weder durch region_label
    (unterschiedliche Strings) noch durch dedup_id (beide None, Rev-2-Fix).
    Reproduziert den vom Adversary gefundenen Fall auch fuer reines
    GeoSphere, ganz ohne MeteoAlarm."""
    from output.renderers.alert.official_alerts import dedupe_official_alerts

    ort_a_alert = OfficialAlert(
        source="geosphere_warn", hazard="extreme_heat", level=2,
        label="Hitze", region_label="Villach (Stadt)",
    )
    ort_b_alert = OfficialAlert(
        source="geosphere_warn", hazard="extreme_heat", level=4,
        label="Hitze", region_label="Villach Land",
    )
    assert ort_a_alert.dedup_id is None and ort_b_alert.dedup_id is None, (
        "Rev-2-Fix: keine normalisierte dedup_id mehr aus Gemeindenamen"
    )

    loc_id_a, loc_id_b = "loc-a-villach-stadt", "loc-b-villach-land"
    tagged = [(ort_a_alert, [loc_id_a]), (ort_b_alert, [loc_id_b])]
    deduped = dedupe_official_alerts(tagged)

    assert len(deduped) == 2, (
        f"Zwei VERSCHIEDENE Orte mit aehnlichem Namen duerfen nicht "
        f"kollabieren, erwartet 2 Eintraege, erhalten {len(deduped)}: "
        f"{[(a.region_label, a.level) for a, _ in deduped]}"
    )

    by_region = {a.region_label: (a, segs) for a, segs in deduped}
    a_repr, a_segs = by_region["Villach (Stadt)"]
    b_repr, b_segs = by_region["Villach Land"]

    assert a_repr.level == 2, "Ort A muss seine eigene Stufe (2) behalten"
    assert a_segs == [loc_id_a], "Ort A darf nur seine eigene loc_id tragen"
    assert b_repr.level == 4, "Ort B muss seine eigene Stufe (4) behalten"
    assert b_segs == [loc_id_b], "Ort B darf nur seine eigene loc_id tragen"

    # Der State-Key-Pfad aus compare_official_alert.py::_detect/_record_state
    # (f"official_alert:{alert.region_label}:{alert.hazard}") muss fuer beide
    # Orte VERSCHIEDENE Keys ergeben -- sonst wuerde der State eines Ortes den
    # des anderen ueberschreiben, selbst wenn dedupe_official_alerts() bereits
    # korrekt getrennt haette.
    key_a = f"official_alert:{a_repr.region_label}:{a_repr.hazard}"
    key_b = f"official_alert:{b_repr.region_label}:{b_repr.hazard}"
    assert key_a != key_b, (
        f"State-Keys muessen fuer verschiedene Orte verschieden sein, "
        f"waren beide {key_a!r}"
    )


# ---------------------------------------------------------------------------
# Issue #1348 (Scheibe 2a von #1337) — Warn-Dienst-Verbrauch senken +
# 429-bewusster Rückzug. Die folgenden Tests sind in der RED-Phase ABSICHTLICH
# rot: heute ist ``meteoalarm.CACHE_TTL == 300.0`` und der 429-Pfad läuft über
# ``raise_for_status()`` -> generischer ``except`` -> 60s-Failure-Cache (kein
# Retry-After-Backoff). SPEC: docs/specs/modules/warn_service_consumption.md
# AC-1, AC-4, AC-6, AC-10.
# ---------------------------------------------------------------------------

def test_ttl_ist_dreissig_minuten():
    """AC-1: GIVEN das MeteoAlarm-Modul, WHEN es importiert wird, THEN beträgt
    die Erfolgs-TTL 1800.0 Sekunden (30 Minuten, warngerecht länger als der
    15-Minuten-Scheduler-Takt) und die Failure-TTL bleibt bei 60.0 Sekunden.

    RED heute: ``CACHE_TTL == 300.0`` -> die erste Assertion schlägt fehl."""
    from services.official_alerts import meteoalarm

    assert meteoalarm.CACHE_TTL == 1800.0, (
        f"Erfolgs-TTL muss auf 1800.0s (30 min) angehoben sein, war {meteoalarm.CACHE_TTL}"
    )
    assert meteoalarm.FAILURE_CACHE_TTL == 60.0, (
        f"Failure-TTL bleibt unverändert bei 60.0s, war {meteoalarm.FAILURE_CACHE_TTL}"
    )


class _Http429RetryAfterHandler(http.server.BaseHTTPRequestHandler):
    """Echter lokaler HTTP-Server (kein Mock der HTTP-Bibliothek): liefert für
    JEDEN Pfad HTTP 429 mit ``Retry-After: 120`` — so verhält sich
    ``api.meteoalarm.org`` real, wenn das Tages-Kontingent erschöpft ist."""

    def do_GET(self):  # noqa: N802 - stdlib-Signatur
        body = b'{"detail": "rate limited"}'
        self.send_response(429)
        self.send_header("Retry-After", "120")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):  # Testlauf-Output nicht zumuellen
        pass


def test_429_lokaler_server_retry_after_respektiert(monkeypatch, caplog, tmp_path):
    """AC-4/AC-6 (End-zu-Ende über den echten ``meteoalarm``-Pfad): GIVEN ein
    echter lokaler HTTP-Server, der auf JEDEN Versuch 429 + ``Retry-After:
    120`` liefert (kein ``x-ratelimit-reset``, also erschoepft die S1b-
    Wiederholung ihre Versuche), WHEN ``_get_cached_index()`` den Index-Call
    macht, THEN liefert Seite 1 (== der gesamte Index, ohne sie ist
    ``total_pages`` unbekannt) ``None`` -- der Cache-Eintrag traegt den
    Backoff ``max(120, INDEX_PAGE_SUCCESS_TTL)`` (S1c: die Index-Seiten-TTL
    ist laenger als die generische ``CACHE_TTL``) UND ein WARNING-Log nennt
    explizit "429"."""
    from services.official_alerts import meteoalarm

    # WARN_CALLS_PATH-Umlenkung erfolgt global via conftest-Autouse-Fixture
    # ``_isolate_warn_calls_path`` (Issue #1348) — kein Per-Test-Monkeypatch nötig.
    server = http.server.HTTPServer(("127.0.0.1", 0), _Http429RetryAfterHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv("GZ_METEOALARM_APIKEY", "dummy-test-token-429")
        monkeypatch.setattr(
            meteoalarm, "METEOALARM_BASE_URL",
            f"http://127.0.0.1:{server.server_port}",
        )

        with caplog.at_level("WARNING", logger="meteoalarm"):
            data = meteoalarm._get_cached_index("AT")

        assert data is None, (
            f"429 ist kein Erfolg — _get_cached_index() muss None liefern, war {data!r}"
        )

        entries = meteoalarm._index_cache_entries_for("AT", 1)
        assert len(entries) == 1, f"genau EIN Cache-Eintrag fuer AT-Seite-1 erwartet, war {entries}"
        cache_entry = entries[0]
        expected_backoff = max(120.0, meteoalarm.INDEX_PAGE_SUCCESS_TTL)
        assert cache_entry["ttl"] == expected_backoff, (
            f"429 mit Retry-After:120 muss Backoff max(120, INDEX_PAGE_SUCCESS_TTL)="
            f"{expected_backoff} als Cache-TTL setzen, war {cache_entry['ttl']}"
        )
        # Konkreter Wert (Gegenprobe zur symbolischen Zusicherung oben):
        # Issue #1397 S1 hob INDEX_PAGE_SUCCESS_TTL von 2700s (45 min, passend
        # zum alten 30-Minuten-Raster) auf 5400s (90 min) an -- die Seiten-TTL
        # muss laenger sein als ein Zeitslot, und der Slot ist jetzt 60 statt
        # 30 Minuten breit. Geprueftes Verhalten unveraendert: der 429-Rueckzug
        # ist nie kuerzer als die Erfolgs-TTL der Index-Seiten.
        assert cache_entry["ttl"] == 5400.0

        warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
        assert any("429" in m for m in warnings), (
            f"429 muss LAUT geloggt werden (Text enthält '429'), Records: {warnings}"
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)


# ---------------------------------------------------------------------------
# Issue #1397 -- Scheibe S1: vollstaendiges Seiten-Blaettern, eingefrorenes
# Zeitfenster, supersededAt-Filter, Feature-Dedup, bbox-Vorfilter, stabile
# OBJECTID-/alertId-Cache-Schluessel. Fixtures unter tests/fixtures/meteoalarm/
# index_multipage_p{1,2,3}.json / index_objectid_reuse.json /
# index_bbox_prefilter.json sind ECHTE, aufgezeichnete API-Antworten
# (api.meteoalarm.org, Land IT, 2026-07-27), auf wenige Features gekuerzt --
# geometry-/hubLink-hrefs zeigen ueber den Platzhalter "TESTSERVER" auf den
# lokalen Test-Server dieser Datei (kein Mock, echter Socket-Roundtrip).
# ---------------------------------------------------------------------------

def _load_index_fixture(name: str, port: int) -> dict:
    text = _read_fixture(name).replace("TESTSERVER", f"127.0.0.1:{port}")
    return json.loads(text)


def _make_paging_handler(pages: dict, geometry_bodies: dict, cap_bodies: dict, calls: list):
    """Baut eine http.server-Handler-Klasse (echter lokaler Server, kein Mock):
    ``pages[(country, page)]`` liefert Index-Seiten (Body oder HTTP-Status),
    ``/geometry/*``- und ``/cap/*``-Pfade werden in ``calls`` protokolliert --
    das ist der Nachweis, ob ein Nachlade-Abruf ueberhaupt stattfand."""

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib-Signatur
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            if parsed.path.startswith("/collections/warnings/locations/"):
                country = parsed.path.rsplit("/", 1)[-1]
                page_num = int(qs.get("page", ["1"])[0])
                entry = pages.get((country, page_num), {"body": {"features": []}})
                status = entry.get("status", 200)
                self.send_response(status)
                if "retry_after" in entry:
                    self.send_header("Retry-After", str(entry["retry_after"]))
                if status != 200:
                    self.end_headers()
                    return
                body = json.dumps(entry["body"]).encode("utf-8")
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            calls.append(parsed.path)
            if parsed.path.startswith("/geometry/"):
                body = json.dumps({"geometry": geometry_bodies.get(parsed.path, {})}).encode()
                content_type = "application/json"
            else:
                body = cap_bodies.get(parsed.path, "").encode("utf-8")
                content_type = "application/xml"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):  # Testlauf-Output nicht zumuellen
            pass

    return _Handler


def _run_server(handler_cls):
    server = http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_treffer_auf_seite_3_von_3_wird_gefunden(monkeypatch):
    """GIVEN ein Index mit 3 Seiten (echte, aufgezeichnete Daten -- Issue
    #1445 S1: ueber den AT-Pfad abgerufen, da MeteoAlarmSource IT nicht mehr
    bedient, die Feature-Verarbeitung selbst ist laenderunabhaengig),
    dessen einzige NICHT ueberholte Warnung auf Seite 3 liegt (Seite 1+2
    bestehen aus ueberholten Fassungen), WHEN fetch() aufgerufen wird, THEN
    wird die Warnung gefunden -- vor Issue #1397 (nur Seite 1 abgerufen)
    waere das Ergebnis leer geblieben (Nachweis: Bericht an den Product
    Owner)."""
    from services.official_alerts import meteoalarm

    calls: list[str] = []
    pages: dict = {}
    # Exakte Flaeche (geometry-Link-Antwort) -- eng um den Zielpunkt herum,
    # unabhaengig von der (weiten) Index-bbox.
    trentino_geometry = {
        "type": "Polygon",
        "coordinates": [[[7.5, 45.0], [7.5, 45.5], [8.5, 45.5], [8.5, 45.0], [7.5, 45.0]]],
    }
    handler_cls = _make_paging_handler(
        pages=pages,
        geometry_bodies={"/geometry/trentino": trentino_geometry},
        cap_bodies={"/cap/trentino": _read_fixture("cap_villach_heat.xml")},
        calls=calls,
    )
    server, thread = _run_server(handler_cls)
    try:
        pages[("AT", 1)] = {"body": _load_index_fixture("index_multipage_p1.json", server.server_port)}
        pages[("AT", 2)] = {"body": _load_index_fixture("index_multipage_p2.json", server.server_port)}
        pages[("AT", 3)] = {"body": _load_index_fixture("index_multipage_p3.json", server.server_port)}

        monkeypatch.setenv("GZ_METEOALARM_APIKEY", "dummy-test-token-paging")
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{server.server_port}")
        for key in ("AT:p1", "AT:p2", "AT:p3"):
            meteoalarm._index_cache.pop(key, None)

        # Zielpunkt: Mittelpunkt der bbox des Seite-3-Treffer-Features
        # (echte, aufgezeichnete Region -- direkter fetch()-Aufruf prueft
        # nicht covers(), die Koordinate muss dafuer nicht in Oesterreich
        # liegen).
        alerts = meteoalarm.MeteoAlarmSource().fetch(45.263, 7.917)

        assert any(a.hazard == "extreme_heat" for a in alerts), (
            f"Treffer-Feature auf Seite 3 muss gefunden werden, erhalten: {alerts}"
        )
        assert "/geometry/should-not-be-called-p1-0" not in calls, (
            "ueberholte Features (Seite 1) duerfen keinen Flaechen-Abruf ausloesen"
        )
        assert "/geometry/should-not-be-called-p2-0" not in calls, (
            "ueberholte Features (Seite 2) duerfen keinen Flaechen-Abruf ausloesen"
        )
        assert "/cap/trentino" in calls, "Treffer-CAP muss abgerufen worden sein"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        for key in ("AT:p1", "AT:p2", "AT:p3"):
            meteoalarm._index_cache.pop(key, None)


def test_fehlschlag_seite_2_von_2_liefert_teilergebnis_mit_unavailable(monkeypatch):
    """Issue #1397 Scheibe S1c (inhaltliche Kurskorrektur gegenueber S1):
    GIVEN ein AT-Index mit 2 Seiten, dessen Seite 1 einen ECHTEN Treffer
    traegt (reale Geometrie/CAP, Punkt-in-Flaeche-Match) und dessen Seite 2
    mit HTTP 500 fehlschlaegt, WHEN get_official_alerts_with_status() ueber
    die echte Registry aufgerufen wird, THEN meldet es unavailable=True UND
    liefert TROTZDEM den Treffer von Seite 1 -- ein GEKENNZEICHNETES
    Teilergebnis ist besser als gar keines (PO-Entscheid: verboten ist das
    STILLE Teilergebnis aus S1, nicht das gekennzeichnete aus S1c). Issue
    #1445 S1: der Testpunkt muss innerhalb der AT-Bbox liegen, sonst
    ueberspringt covers() die Quelle bereits vor fetch()."""
    from datetime import datetime, timezone

    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_with_status
    from services.official_alerts import meteoalarm

    calls: list[str] = []
    pages: dict = {}
    # Innerhalb der AT-INCA-Bbox (46.3-49.1 lat, 9.5-17.2 lon).
    tirol_geometry = {
        "type": "Polygon",
        "coordinates": [[[10.5, 46.5], [10.5, 47.0], [11.5, 47.0], [11.5, 46.5], [10.5, 46.5]]],
    }
    handler_cls = _make_paging_handler(
        pages=pages,
        geometry_bodies={"/geometry/tirol-partial": tirol_geometry},
        cap_bodies={"/cap/tirol-partial": _read_fixture("cap_villach_heat.xml")},
        calls=calls,
    )
    server, thread = _run_server(handler_cls)
    backup_sources = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        treffer_feature = _minimal_feature(
            "AT", "PARTIAL-RESULT-TEST", "partial-alert", base_url,
            "/geometry/tirol-partial", "/cap/tirol-partial",
        )
        pages[("AT", 1)] = {"body": {"metadata": {"total_pages": 2}, "features": [treffer_feature]}}
        pages[("AT", 2)] = {"status": 500}

        monkeypatch.setenv("GZ_METEOALARM_APIKEY", "dummy-test-token-partial")
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", base_url)
        oa_base._REGISTERED_SOURCES.append(meteoalarm.MeteoAlarmSource())

        # cap_villach_heat.xml traegt einen festen, aufgezeichneten Zeitraum
        # (onset/expires 2026-07-15) -- ``now`` MUSS in dieses Fenster fallen,
        # sonst filtert filter_alerts_to_window() den Treffer unabhaengig vom
        # hier getesteten Verhalten weg.
        fixture_now = datetime(2026, 7, 15, 10, 0, 0, tzinfo=timezone.utc)
        alerts, unavailable = get_official_alerts_with_status(46.75, 11.0, now=fixture_now)

        assert unavailable is True, "Fehlschlag auf Seite 2 von 2 muss als unavailable gemeldet werden"
        assert any(a.hazard == "extreme_heat" for a in alerts), (
            f"Treffer von Seite 1 muss TROTZ Fehlschlag auf Seite 2 erscheinen (gekennzeichnetes "
            f"Teilergebnis), erhalten: {alerts}"
        )
        assert "/cap/tirol-partial" in calls, "Nachlade-Abruf fuer den Seite-1-Treffer muss stattfinden"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup_sources)


def test_is_superseded_gesetzt_leer_fehlend():
    """Direkter Unit-Test von ``_is_superseded()`` (Adversary-Korrektur
    F003): gesetzter Zeitstempel/gesetzte ID -> True; ``None``/leerer
    String/fehlendes Feld/fehlendes ``properties`` -> False."""
    from services.official_alerts.meteoalarm import _is_superseded

    assert _is_superseded({"properties": {"supersededAt": "2026-07-26T10:00:00Z"}}) is True
    assert _is_superseded({"properties": {"supersededByAlertId": "some-id"}}) is True
    assert _is_superseded({"properties": {"supersededAt": None, "supersededByAlertId": None}}) is False
    assert _is_superseded({"properties": {"supersededAt": ""}}) is False
    assert _is_superseded({"properties": {}}) is False
    assert _is_superseded({}) is False


def test_ueberholte_features_werden_uebersprungen_ohne_nachladen(monkeypatch):
    """GIVEN EIN als ueberholt markiertes Feature (echtes, aufgezeichnetes
    supersededAt), dessen bbox den Testpunkt ABDECKT und dessen geometry-/
    CAP-Link einen ECHTEN Treffer liefern WUERDE (Adversary-Korrektur F003:
    isoliert vom bbox-Vorfilter -- der urspruengliche Test bewies nichts,
    weil sein Testpunkt ohnehin ausserhalb jeder bbox lag), WHEN fetch()
    aufgerufen wird, THEN wird WEDER Flaeche noch CAP nachgeladen und kein
    Alert erscheint -- der Filter greift VOR jedem Nachlade-Abruf.

    Mutationstest-Nachweis (im Entwickler-Bericht): ``_is_superseded``
    neutralisiert (immer ``False``) -> dieser Test wird ROT, weil dann sowohl
    ein Flaechen-/CAP-Abruf stattfindet als auch ein Alert erscheint."""
    from services.official_alerts import meteoalarm

    calls: list[str] = []
    pages: dict = {}
    geometry = {
        "type": "Polygon",
        "coordinates": [[[8.0, 43.9], [8.0, 44.5], [9.5, 44.5], [9.5, 43.9], [8.0, 43.9]]],
    }
    handler_cls = _make_paging_handler(
        pages=pages,
        geometry_bodies={"/geometry/superseded-isolation": geometry},
        cap_bodies={"/cap/superseded-isolation": _read_fixture("cap_villach_heat.xml")},
        calls=calls,
    )
    server, thread = _run_server(handler_cls)
    try:
        pages[("IT", 1)] = {"body": _load_index_fixture("index_superseded_isolation.json", server.server_port)}
        pages[("AT", 1)] = {"body": {"features": []}}

        monkeypatch.setenv("GZ_METEOALARM_APIKEY", "dummy-test-token-superseded")
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{server.server_port}")
        for key in ("AT:p1", "IT:p1"):
            meteoalarm._index_cache.pop(key, None)

        # Testpunkt liegt INNERHALB der bbox des ueberholten Features
        # (44.2, 8.7) -- ohne den supersededAt-Filter waere hier ein echter
        # Treffer faellig (Flaechen- + CAP-Abruf + extreme_heat-Alert).
        alerts = meteoalarm.MeteoAlarmSource().fetch(44.2, 8.7)

        assert alerts == [], f"Ueberholte Features duerfen keine Alerts liefern, erhalten: {alerts}"
        assert calls == [], f"Ueberholte Features duerfen keinen Nachlade-Abruf ausloesen, erhalten: {calls}"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        for key in ("AT:p1", "IT:p1"):
            meteoalarm._index_cache.pop(key, None)


def test_bbox_vorfilter_ueberspringt_treffer_ausserhalb_laedt_kantenfall(monkeypatch):
    """GIVEN eine Index-Seite mit zwei Features -- eines, dessen bbox den
    Testpunkt NICHT enthaelt, und eines, dessen bbox den Punkt EXAKT auf der
    Kante traegt -- WHEN fetch() diese verarbeitet, THEN wird fuer das erste
    Feature KEIN Flaechen-Abruf ausgeloest, fuer den Kantenfall SEHR WOHL
    (Issue #1397: die bbox-Pruefung ist bewusst eine Obermenge, kein
    striktes Ray-Casting -- sonst wuerde derselbe Kanten-Verlust entstehen,
    den der Fix beheben soll)."""
    from services.official_alerts import meteoalarm

    calls: list[str] = []
    pages: dict = {}
    handler_cls = _make_paging_handler(pages=pages, geometry_bodies={}, cap_bodies={}, calls=calls)
    server, thread = _run_server(handler_cls)
    try:
        # Issue #1445 S1: ueber den AT-Pfad abgerufen (direkter fetch()-Aufruf
        # prueft nicht covers(), die Koordinate muss dafuer nicht in
        # Oesterreich liegen -- die bbox-Vorfilterlogik ist laenderunabhaengig).
        pages[("AT", 1)] = {"body": _load_index_fixture("index_bbox_prefilter.json", server.server_port)}

        monkeypatch.setenv("GZ_METEOALARM_APIKEY", "dummy-test-token-bbox")
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{server.server_port}")
        meteoalarm._index_cache.pop("AT:p1", None)

        # Testpunkt liegt exakt auf minLon/maxLat der "edge"-bbox (10.0/45.0).
        meteoalarm.MeteoAlarmSource().fetch(45.0, 10.0)

        assert "/geometry/bbox-miss" not in calls, "bbox ohne Ueberlappung darf keinen Flaechen-Abruf ausloesen"
        assert "/geometry/bbox-edge" in calls, "Kantenfall muss trotzdem nachgeladen werden (Obermenge)"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        meteoalarm._index_cache.pop("AT:p1", None)


def test_gleiches_objectid_wird_nur_einmal_geladen(monkeypatch):
    """GIVEN zwei Index-Features mit DEMSELBEN OBJECTID (= dieselbe Flaeche),
    aber unterschiedlichem ``alertId`` und unterschiedlicher, echt
    aufgezeichneter presigned-URL fuer den geometry-Link, WHEN fetch() beide
    verarbeitet, THEN wird die Flaeche NUR EINMAL nachgeladen -- der Cache
    schluesselt auf ``OBJECTID``, nicht auf die (pro Antwort rotierende)
    presigned URL (Issue #1397, behebt das unbegrenzt wachsende Speicherleck
    im dauerhaft laufenden FastAPI-Prozess)."""
    from services.official_alerts import meteoalarm

    calls: list[str] = []
    pages: dict = {}
    rect = {"type": "Polygon", "coordinates": [[[7.0, 43.5], [7.0, 45.0], [10.5, 45.0], [10.5, 43.5], [7.0, 43.5]]]}
    handler_cls = _make_paging_handler(
        pages=pages,
        geometry_bodies={"/geometry/reuse-via-href-a": rect},
        cap_bodies={
            "/cap/reuse-a": _read_fixture("cap_villach_heat.xml"),
            "/cap/reuse-b": _read_fixture("cap_villach_heat.xml"),
        },
        calls=calls,
    )
    server, thread = _run_server(handler_cls)
    try:
        # Issue #1445 S1: ueber den AT-Pfad abgerufen (direkter fetch()-Aufruf
        # prueft nicht covers(), die OBJECTID-Dedup-Logik ist
        # laenderunabhaengig).
        pages[("AT", 1)] = {"body": _load_index_fixture("index_objectid_reuse.json", server.server_port)}

        monkeypatch.setenv("GZ_METEOALARM_APIKEY", "dummy-test-token-objectid")
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{server.server_port}")
        meteoalarm._index_cache.pop("AT:p1", None)
        meteoalarm._geometry_cache.clear()

        alerts = meteoalarm.MeteoAlarmSource().fetch(44.2, 8.7)

        geometry_calls = [c for c in calls if c.startswith("/geometry/")]
        assert len(geometry_calls) == 1, (
            f"Gleiches OBJECTID darf nur EINMAL nachgeladen werden, erhalten: {geometry_calls}"
        )
        assert len(alerts) == 2, f"Beide Features (verschiedene alertId) muessen je einen Alert liefern, erhalten: {alerts}"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        meteoalarm._geometry_cache.clear()
        meteoalarm._index_cache.pop("AT:p1", None)


# ---------------------------------------------------------------------------
# Fix-Loop (Adversary-Verdict BROKEN) -- F001/F002: Obergrenze/Ausfall statt
# stillem Kappen bzw. Wurf. Direkter Unit-Test der reinen Ermittlungsfunktion
# ``_resolve_total_pages()`` (belegter Fall des Pruefers: total_pages=999999).
# ---------------------------------------------------------------------------

def test_resolve_total_pages_grenzfaelle():
    """F001: fehlende Metadata/``total_pages`` -> 1 Seite (Bestandsverhalten,
    z.B. 204-Fall). F001 (Kern): ``total_pages`` ueber ``_MAX_INDEX_PAGES``
    -> ``None`` (Ausfall) -- NICHT stumm auf die Obergrenze gekappt (das WAERE
    der behobene Bug: erhaltener Fall des Pruefers ``total_pages=999999``
    fuehrte vor der Korrektur zu 50 geladenen Seiten UND einer Rueckgabe
    ungleich ``None``). F002: nicht als positive Ganzzahl lesbares
    ``total_pages`` -> ``None``, kein Wurf."""
    from services.official_alerts.meteoalarm import _MAX_INDEX_PAGES, _resolve_total_pages

    assert _resolve_total_pages(None) == 1
    assert _resolve_total_pages({}) == 1
    assert _resolve_total_pages({"total_pages": _MAX_INDEX_PAGES}) == _MAX_INDEX_PAGES
    assert _resolve_total_pages({"total_pages": _MAX_INDEX_PAGES + 1}) is None, (
        "ueber der Obergrenze gemeldete Seiten muessen als Ausfall gelten, nicht stumm gekappt werden"
    )
    assert _resolve_total_pages({"total_pages": 999999}) is None, "belegter Adversary-Fall F001"
    assert _resolve_total_pages({"total_pages": "viele"}) is None, "F002: nicht parsebar -> Ausfall, kein Wurf"
    assert _resolve_total_pages({"total_pages": 0}) is None
    assert _resolve_total_pages({"total_pages": -3}) is None


def _minimal_feature(country: str, object_id: str, alert_id: str, base_url: str,
                      geometry_path: str, cap_path: str) -> dict:
    """Minimales, aber schema-konformes Feature fuer gezielte Fix-Loop-Tests
    (F002/F004) -- ohne bbox-``geometry`` (fail-open, s. ``_bbox_may_contain``),
    damit ausschliesslich das jeweils getestete Verhalten wirkt."""
    return {
        "links": [{"rel": "geometry", "href": f"{base_url}{geometry_path}"}],
        "properties": {
            "OBJECTID": object_id, "alertId": alert_id, "countryCode": country,
            "indexArea": 0, "indexInfo": 0, "hubLink": f"{base_url}{cap_path}",
            "supersededAt": None, "supersededByAlertId": None,
        },
    }


def _assert_at_malformed_index_faelt_soft_ohne_wurf(monkeypatch, at_body) -> None:
    """Gemeinsamer Kern fuer alle drei F002-Malformationsvarianten (Wert-,
    Metadata- und Ganz-Antwort-Typ-Fehler). Issue #1445 S1: MeteoAlarmSource
    deckt nur noch AT ab, ein zweites Land zur Isolationsprobe ("AT kaputt,
    IT liefert trotzdem") steht nicht mehr zur Verfuegung -- der eigentliche
    Kern-Nachweis bleibt aber direkt pruefbar: ``fetch()`` darf bei kaputter
    AT-Seite-1-Antwort NICHT werfen und muss fail-soft ``[]`` liefern (kein
    Teilergebnis, kein Crash, Modul-Docstring Zeile 11-13)."""
    from services.official_alerts import meteoalarm

    pages: dict = {}
    handler_cls = _make_paging_handler(pages=pages, geometry_bodies={}, cap_bodies={}, calls=[])
    server, thread = _run_server(handler_cls)
    try:
        pages[("AT", 1)] = {"body": at_body}

        monkeypatch.setenv("GZ_METEOALARM_APIKEY", "dummy-test-token-broken-total-pages")
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{server.server_port}")
        meteoalarm._index_cache.pop("AT:p1", None)

        alerts = meteoalarm.MeteoAlarmSource().fetch(*VILLACH)

        assert alerts == [], (
            f"kaputte AT-Seite-1-Antwort darf fetch() weder werfen noch ein "
            f"Teilergebnis entlocken, erhalten: {alerts}"
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)
        meteoalarm._index_cache.pop("AT:p1", None)


def test_kaputtes_total_pages_bricht_fail_soft_schleife_nicht_ab(monkeypatch):
    """F002 (Wert-Malformation): ein nicht-numerisches ``total_pages`` darf
    ``fetch()`` NICHT crashen lassen. Vor der Korrektur wirft ``int("viele")``
    und reisst die Verarbeitung ab -- direkter Nachweis auf Methodenebene."""
    _assert_at_malformed_index_faelt_soft_ohne_wurf(
        monkeypatch, {"metadata": {"total_pages": "viele"}, "features": []}
    )


def test_kaputte_metadata_als_string_bricht_fail_soft_schleife_nicht_ab(monkeypatch):
    """F002 Runde 2 (Typ-Malformation): ``metadata`` selbst ist kein Objekt
    (z.B. ein String), nicht nur ``total_pages`` unlesbar. Belegter
    Adversary-Fall: ``{"metadata": "kaputt", "features": []}`` liess
    ``metadata.get("total_pages")`` mit ``AttributeError`` werfen -- ``fetch()``
    darf NICHT werfen.

    Mutationstest-Nachweis (im Entwickler-Bericht): die ``isinstance``-Pruefung
    in ``_resolve_total_pages()`` entfernt -> dieser Test wird ROT
    (``AttributeError`` statt Ergebnis)."""
    _assert_at_malformed_index_faelt_soft_ohne_wurf(
        monkeypatch, {"metadata": "kaputt", "features": []}
    )


def test_kaputte_seiten_antwort_als_string_bricht_fail_soft_schleife_nicht_ab(monkeypatch):
    """F002 Runde 3: nicht nur ``metadata`` kann falsch typisiert sein,
    sondern die GANZE Seiten-Antwort (z.B. ``"kaputt"`` statt eines Objekts).
    Belegter Adversary-Fall (sinngemaess, hier als String statt JSON-Liste
    reproduziert -- ``json.dumps("kaputt")`` liefert ein valides JSON, dessen
    oberste Ebene trotzdem kein Objekt ist): ``fetch()`` darf NICHT werfen.

    Mutationstest-Nachweis (im Entwickler-Bericht): die ``isinstance``-Pruefung
    in ``_parse()`` entfernt -> dieser Test wird ROT (``AttributeError``)."""
    _assert_at_malformed_index_faelt_soft_ohne_wurf(monkeypatch, "kaputt")


def _assert_broken_total_pages_marks_unavailable(monkeypatch, at_body: dict) -> None:
    """Adversary F001 (S1c-Runde, KRITISCH): Seite 1 kommt HTTP-sauber und
    als valides JSON-Objekt durch -- fuer ``cached_fetch()`` ist das ein
    ERFOLG, es markiert NICHTS. Erst ``_resolve_total_pages()`` entscheidet
    eine Ebene hoeher, dass der Index trotzdem unbrauchbar ist.
    ``get_official_alerts_with_status()`` MUSS das ueber ``unavailable=True``
    sichtbar machen -- sonst wird ein kompletter Ausfall als "alles ruhig"
    ausgeliefert (genau die Fehlerart, gegen die Issue #1397 laeuft). Issue
    #1445 S1: der Testpunkt muss innerhalb der AT-Bbox liegen, sonst
    ueberspringt covers() die Quelle bereits vor fetch()."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_with_status, meteoalarm

    pages: dict = {}
    handler_cls = _make_paging_handler(pages=pages, geometry_bodies={}, cap_bodies={}, calls=[])
    server, thread = _run_server(handler_cls)
    backup_sources = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        pages[("AT", 1)] = {"body": at_body}

        monkeypatch.setenv("GZ_METEOALARM_APIKEY", "dummy-test-token-f001-total-pages")
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{server.server_port}")
        oa_base._REGISTERED_SOURCES.append(meteoalarm.MeteoAlarmSource())

        _alerts, unavailable = get_official_alerts_with_status(*VILLACH)

        assert unavailable is True, (
            "unbrauchbares total_pages muss als unavailable gemeldet werden -- sonst wird ein "
            "kompletter Ausfall stillschweigend als 'alles ruhig' ausgeliefert"
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup_sources)


def test_total_pages_ausserhalb_bereich_markiert_unavailable(monkeypatch):
    """Adversary F001 (KRITISCH): ``total_pages`` ausserhalb 1..
    ``_MAX_INDEX_PAGES`` (belegter Fall: 999999) darf NICHT als stiller
    Ausfall durchgehen -- ``unavailable`` muss ``True`` sein."""
    _assert_broken_total_pages_marks_unavailable(
        monkeypatch, {"metadata": {"total_pages": 999999}, "features": []}
    )


def test_total_pages_nicht_numerisch_markiert_unavailable(monkeypatch):
    """Adversary F001 (KRITISCH): nicht-numerisches ``total_pages`` darf
    NICHT als stiller Ausfall durchgehen -- ``unavailable`` muss ``True``
    sein.

    Mutationstest-Nachweis (im Entwickler-Bericht): das
    ``warn_egress.mark_fetch_incomplete()`` vor dem ``return None`` in
    ``_get_cached_index()`` entfernt -> dieser Test wird ROT (``unavailable``
    faellt auf ``False`` zurueck)."""
    _assert_broken_total_pages_marks_unavailable(
        monkeypatch, {"metadata": {"total_pages": "viele"}, "features": []}
    )


def _assert_malformed_top_level_page_yields_unavailable_no_partial(monkeypatch, at_pages: dict) -> None:
    """Gemeinsamer Kern: AT liefert ueber ``at_pages`` (Seite -> Koerper)
    mindestens eine strukturell falsch typisierte Seiten-Antwort (Liste/Zahl
    statt Objekt) -- egal ob Seite 1 oder eine Folgeseite. Direkter
    ``fetch()``-Aufruf darf NICHT werfen und muss KEIN Teilergebnis liefern
    (das ist der eigentliche Mutationsnachweis: eine fehlende Validierung
    wirft hier direkt, statt fail-soft [] zu liefern); zusaetzlich meldet
    ``get_official_alerts_with_status()`` ueber die Registry ``unavailable=True``.
    Issue #1445 S1: der Testpunkt muss innerhalb der AT-Bbox liegen, sonst
    ueberspringt covers() die Quelle bereits vor fetch() im Registry-Teil."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_with_status, meteoalarm

    calls: list[str] = []
    pages: dict = {}
    handler_cls = _make_paging_handler(pages=pages, geometry_bodies={}, cap_bodies={}, calls=calls)
    server, thread = _run_server(handler_cls)
    backup_sources = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        for page_num, body in at_pages.items():
            pages[("AT", page_num)] = {"body": body}

        monkeypatch.setenv("GZ_METEOALARM_APIKEY", "dummy-test-token-malformed-toplevel")
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{server.server_port}")
        for page_num in at_pages:
            meteoalarm._index_cache.pop(f"AT:p{page_num}", None)

        direct_alerts = meteoalarm.MeteoAlarmSource().fetch(*VILLACH)
        assert direct_alerts == [], (
            f"direkter fetch()-Aufruf darf bei kaputter Seiten-Antwort kein Teilergebnis liefern, "
            f"erhalten: {direct_alerts}"
        )

        oa_base._REGISTERED_SOURCES.append(meteoalarm.MeteoAlarmSource())
        alerts, unavailable = get_official_alerts_with_status(*VILLACH)

        assert unavailable is True, "strukturell falsch typisierte Seiten-Antwort muss als unavailable gelten"
        assert alerts == [], f"kein Teilergebnis aus bereits erfolgreichen Seiten erlaubt, erhalten: {alerts}"
        assert calls == [], "bei verworfenem Index darf kein Nachlade-Abruf stattfinden"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup_sources)
        for page_num in at_pages:
            meteoalarm._index_cache.pop(f"AT:p{page_num}", None)


def test_seite_1_als_json_liste_ergibt_unavailable_kein_wurf(monkeypatch):
    """F002 Runde 3: Seite 1 liefert eine JSON-Liste statt eines Objekts.
    Muss wie jede andere kaputte Seite behandelt werden -- Ausfall, kein
    Wurf, kein Teilergebnis."""
    _assert_malformed_top_level_page_yields_unavailable_no_partial(monkeypatch, {1: [1, 2, 3]})


def test_folgeseite_als_zahl_ergibt_unavailable_kein_teilergebnis(monkeypatch):
    """F002 Runde 3: Seite 1 ist gueltig -- Seite 2 liefert eine blanke Zahl
    statt eines Objekts. Das bereits erfolgreich abgerufene Seite-1-Ergebnis
    darf NICHT als Teilergebnis erscheinen (Kern des #1397-Bugs: die
    fehlende/kaputte Seite koennte genau die gesuchte Warnung tragen)."""
    _assert_malformed_top_level_page_yields_unavailable_no_partial(
        monkeypatch, {1: {"metadata": {"total_pages": 2}, "features": []}, 2: 42}
    )


def test_geometry_cache_schluesselt_je_land_bei_gleicher_objectid():
    """F004: OBJECTID ist NICHT nachweislich laenderuebergreifend eindeutig
    -- zwei Features mit IDENTISCHER OBJECTID, aber unterschiedlichem
    ``countryCode``, muessen UNABHAENGIG voneinander nachgeladen werden
    (Cache-Schluessel enthaelt ``countryCode``, sonst wuerde das zweite Land
    die Flaeche des ersten aus dem Cache serviert bekommen). Issue #1445 S1:
    ``MeteoAlarmSource.fetch()`` durchlaeuft nur noch AT, der Laender-Praefix
    in ``_fetch_geometry_link()`` selbst ist davon unabhaengig (er liest
    ``countryCode`` direkt aus den Feature-``properties``) -- direkter
    Nachweis an der Funktion statt ueber die (jetzt einlaendrige)
    ``fetch()``-Schleife."""
    from services.official_alerts import meteoalarm

    calls: list[str] = []
    # Beide Flaechen decken denselben Testpunkt ab -- es geht hier NICHT um
    # geografische Plausibilitaet, sondern ausschliesslich darum, dass beide
    # Cache-Eintraege unabhaengig getroffen werden.
    geo_at = {"type": "Polygon", "coordinates": [[[8.5, 45.5], [8.5, 46.5], [9.5, 46.5], [9.5, 45.5], [8.5, 45.5]]]}
    geo_it = {"type": "Polygon", "coordinates": [[[8.5, 45.5], [8.5, 46.5], [9.5, 46.5], [9.5, 45.5], [8.5, 45.5]]]}
    handler_cls = _make_paging_handler(
        pages={},
        geometry_bodies={"/geometry/shared-oid-at": geo_at, "/geometry/shared-oid-it": geo_it},
        cap_bodies={}, calls=calls,
    )
    server, thread = _run_server(handler_cls)
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        shared_oid = "SHARED-OBJECTID-COLLISION-TEST"
        at_feature = _minimal_feature("AT", shared_oid, "at-alert", base_url, "/geometry/shared-oid-at", "/cap/shared-at")
        it_feature = _minimal_feature("IT", shared_oid, "it-alert", base_url, "/geometry/shared-oid-it", "/cap/shared-it")
        meteoalarm._geometry_cache.clear()

        geo_result_at = meteoalarm._fetch_geometry_link(at_feature)
        geo_result_it = meteoalarm._fetch_geometry_link(it_feature)

        assert "/geometry/shared-oid-at" in calls and "/geometry/shared-oid-it" in calls, (
            f"beide Laender muessen ihre eigene Flaeche nachladen trotz gleicher OBJECTID, erhalten: {calls}"
        )
        assert geo_result_at == geo_at, "AT muss seine EIGENE Flaeche zurueckbekommen, nicht die von IT"
        assert geo_result_it == geo_it, "IT muss seine EIGENE Flaeche zurueckbekommen, nicht die von AT"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        meteoalarm._geometry_cache.clear()


# ---------------------------------------------------------------------------
# Issue #1397 Scheibe S1b -- in Produktion gemessene Kurzzeit-Ratenbremse auf
# Index-Seiten (~1 Anfrage/4s, HTTP 429 ohne Retry-After, aber mit
# x-ratelimit-reset als Unix-Sekunden). Vor S1b liess ein 429 auf JEDER
# Folgeseite den GESAMTEN Index ausfallen -- selbst Seite 1 kam nicht mehr
# an. Diese Tests belegen die Wiederholung (echter lokaler Server, kein
# Mock) UND dass ein DAUERHAFTES 429 weiterhin ein echter Ausfall bleibt.
# ---------------------------------------------------------------------------

def _make_flaky_index_handler(pages: dict, page_hits: dict):
    """Wie ``_make_paging_handler``, aber ``pages[(country, page)]`` ist eine
    LISTE von Antworten -- die n-te Anfrage an dieselbe Seite bekommt den
    n-ten Eintrag (der letzte Eintrag wiederholt sich bei weiteren
    Anfragen). ``page_hits`` zaehlt die Treffer je Seite mit -- der Beweis,
    WIE OFT tatsaechlich wiederholt wurde."""

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib-Signatur
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            country = parsed.path.rsplit("/", 1)[-1]
            page_num = int(qs.get("page", ["1"])[0])
            key = (country, page_num)
            hit = page_hits.get(key, 0)
            page_hits[key] = hit + 1
            entries = pages.get(key) or [{"body": {"features": []}}]
            entry = entries[min(hit, len(entries) - 1)]
            status = entry.get("status", 200)
            self.send_response(status)
            for header_name, header_value in entry.get("headers", {}).items():
                self.send_header(header_name, header_value)
            if status != 200:
                self.end_headers()
                return
            body = json.dumps(entry["body"]).encode("utf-8")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):  # Testlauf-Output nicht zumuellen
            pass

    return _Handler


def test_429_auf_folgeseite_wird_wiederholt_index_bleibt_vollstaendig(monkeypatch):
    """S1b: GIVEN Seite 2 antwortet beim ERSTEN Versuch mit HTTP 429 +
    ``x-ratelimit-reset`` (echter lokaler Server), WHEN
    ``_get_cached_index()`` blaettert, THEN wird die Seite wiederholt statt
    sofort als Ausfall zu gelten -- der Index enthaelt BEIDE Seiten, kein
    Ausfall (Produktions-Vorfall aus dem Auftrag: vorher fiel dabei der
    GESAMTE Index aus, obwohl Seite 1 laengst da war)."""
    from services.official_alerts import meteoalarm

    pages: dict = {}
    page_hits: dict = {}
    handler_cls = _make_flaky_index_handler(pages, page_hits)
    server, thread = _run_server(handler_cls)
    sleeps: list[float] = []
    try:
        pages[("AT", 1)] = [
            {"body": {"metadata": {"total_pages": 2}, "features": [{"properties": {"alertId": "p1"}}]}}
        ]
        pages[("AT", 2)] = [
            {"status": 429, "headers": {"x-ratelimit-reset": "1000"}},
            {"body": {"features": [{"properties": {"alertId": "p2"}}]}},
        ]

        monkeypatch.setenv("GZ_METEOALARM_APIKEY", "dummy-test-token-flaky")
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{server.server_port}")
        monkeypatch.setattr(meteoalarm, "_SLEEP_FN", sleeps.append)
        monkeypatch.setattr(meteoalarm, "_WALL_CLOCK_FN", lambda: 1000.0)
        for key in ("AT:p1", "AT:p2"):
            meteoalarm._index_cache.pop(key, None)

        index = meteoalarm._get_cached_index("AT")

        assert index is not None, "429 auf einer Folgeseite darf NICHT sofort zum Ausfall fuehren"
        alert_ids = {f["properties"]["alertId"] for f in index["features"]}
        assert alert_ids == {"p1", "p2"}, f"Index muss BEIDE Seiten enthalten, erhalten: {alert_ids}"
        assert page_hits[("AT", 2)] == 2, (
            f"Seite 2 muss GENAU EINMAL wiederholt worden sein, Treffer: {page_hits[('AT', 2)]}"
        )
        # Zwei Pausen: die vorbeugende Pause VOR Seite 2 (Seite 1 lieferte
        # keinen x-ratelimit-reset -> fester Standardabstand) und die
        # 429-Wiederholungspause INNERHALB von cached_fetch (Reset == Fake-
        # Uhr -> 0.0, kein reales Warten).
        assert sleeps == [meteoalarm._PAGE_THROTTLE_DEFAULT_SECONDS, 0.0], (
            f"erwartete Pausenfolge [Standardabstand, 0.0], war {sleeps!r}"
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)
        for key in ("AT:p1", "AT:p2"):
            meteoalarm._index_cache.pop(key, None)


def test_429_dauerhaft_auf_folgeseite_liefert_teilergebnis_mit_fehlschlag_markierung(monkeypatch):
    """DARF IN DER VERSUCHSZAHL NICHT AUFGEWEICHT WERDEN: haelt Seite 2
    DURCHGEHEND (ueber alle Wiederholungsversuche) bei 429, WHEN
    ``_get_cached_index()`` blaettert, THEN wird NICHT endlos wiederholt
    (Versuche bleiben auf ``max_attempts`` gedeckelt). Seit Issue #1397
    Scheibe S1c ist das Ergebnis ein GEKENNZEICHNETES Teilergebnis (Seite 1
    kommt durch) statt eines stillen ``None`` -- nachgewiesen ueber
    ``warn_egress.observe_fetch_failure()``, demselben Mechanismus, den
    ``get_official_alerts_with_status()`` fuer ``unavailable=True`` nutzt."""
    from services.official_alerts import meteoalarm, warn_egress

    pages: dict = {}
    page_hits: dict = {}
    handler_cls = _make_flaky_index_handler(pages, page_hits)
    server, thread = _run_server(handler_cls)
    try:
        pages[("AT", 1)] = [
            {"body": {"metadata": {"total_pages": 2}, "features": [{"properties": {"alertId": "p1"}}]}}
        ]
        # Einziger Eintrag wiederholt sich bei JEDER weiteren Anfrage (s.
        # ``_make_flaky_index_handler``) -- simuliert eine durchgehende Sperre.
        pages[("AT", 2)] = [{"status": 429, "headers": {"x-ratelimit-reset": "1000"}}]

        monkeypatch.setenv("GZ_METEOALARM_APIKEY", "dummy-test-token-flaky-persistent")
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{server.server_port}")
        monkeypatch.setattr(meteoalarm, "_WALL_CLOCK_FN", lambda: 1000.0)

        with warn_egress.observe_fetch_failure() as fetch_status:
            index = meteoalarm._get_cached_index("AT")
        expected_attempts = meteoalarm._rate_limit_retry_policy().max_attempts

        assert index == {"features": [{"properties": {"alertId": "p1"}}]}, (
            f"Seite 1 muss als gekennzeichnetes Teilergebnis durchkommen, war {index!r}"
        )
        assert fetch_status["failed"] is True, (
            "eine echt fehlgeschlagene Folgeseite muss den Fetch als real fehlgeschlagen "
            "markieren (Basis fuer unavailable=True) -- unabhaengig vom Zeitbudget"
        )
        assert page_hits[("AT", 2)] == expected_attempts, (
            f"Nach Erschoepfung der Versuche darf NICHT weiter wiederholt werden -- erwartet "
            f"{expected_attempts} Treffer, war {page_hits[('AT', 2)]}"
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_throttle_before_next_page_derives_wait_from_last_reset(monkeypatch):
    """S1b: GIVEN der letzte bekannte ``x-ratelimit-reset``, WHEN
    ``_throttle_before_next_page()`` die vorbeugende Pause berechnet, THEN
    wird sie aus ``reset - jetzt`` abgeleitet (gedeckelt), faellt ohne
    bekannten Reset-Zeitpunkt auf den festen Standardabstand zurueck UND
    deckelt einen absurd weit in der Zukunft liegenden Reset-Zeitpunkt."""
    from services.official_alerts import meteoalarm

    sleeps: list[float] = []
    monkeypatch.setattr(meteoalarm, "_SLEEP_FN", sleeps.append)
    monkeypatch.setattr(meteoalarm, "_WALL_CLOCK_FN", lambda: 998.0)

    meteoalarm._throttle_before_next_page(1000.0)
    assert sleeps == [2.0], f"Pause muss aus reset(1000) - jetzt(998) = 2.0s abgeleitet werden, war {sleeps!r}"

    sleeps.clear()
    meteoalarm._throttle_before_next_page(None)
    assert sleeps == [meteoalarm._PAGE_THROTTLE_DEFAULT_SECONDS], (
        f"ohne bekannten Reset-Zeitpunkt muss der feste Standardabstand gelten, war {sleeps!r}"
    )

    sleeps.clear()
    monkeypatch.setattr(meteoalarm, "_WALL_CLOCK_FN", lambda: 0.0)
    meteoalarm._throttle_before_next_page(999999.0)  # absurd weit in der Zukunft
    assert sleeps == [meteoalarm._PAGE_THROTTLE_MAX_SECONDS], (
        f"Pause vor der naechsten Seite muss gedeckelt werden, war {sleeps!r}"
    )


# ---------------------------------------------------------------------------
# Issue #1397 Scheibe S1c -- schrittweises Blaettern ueber mehrere Aufrufe
# hinweg statt "alles in einem Aufruf": Zeitfenster auf einen 30-Minuten-
# Rasterpunkt gerundet, Cache-Schluessel traegt den Zeitslot, Zeitbudget je
# Aufruf, unvollstaendig -> gekennzeichnetes Teilergebnis (nicht mehr
# stilles ``None``).
# ---------------------------------------------------------------------------

class _SteppingClock:
    """Deterministische Fake-Uhr (kein echtes Warten): gibt den aktuellen
    Wert zurueck und ruecht danach um ``step`` weiter -- steuert, wann das
    Zeitbudget als erschoepft gilt, ohne dass ein Test real warten muss."""

    def __init__(self, start: float, step: float) -> None:
        self.value = start
        self.step = step

    def __call__(self) -> float:
        current = self.value
        self.value += self.step
        return current


def test_budget_erschoepft_liefert_teilergebnis_zweiter_aufruf_vervollstaendigt(monkeypatch):
    """S1c Kern-Nachweis: GIVEN ein AT-Index mit 4 Seiten UND eine Fake-Uhr,
    die das Zeitbudget (20s) bereits nach Seite 2 erschoepft, WHEN
    ``_get_cached_index()`` EINMAL aufgerufen wird, THEN liefert er NUR die
    Treffer der Seiten 1+2 UND markiert den Fetch als real fehlgeschlagen
    (Basis fuer ``unavailable=True``) -- Seiten 3+4 werden NICHT angefragt.
    WHEN ein ZWEITER Aufruf im SELBEN Zeitslot mit ausreichendem Budget
    folgt, THEN kommen die Seiten 1+2 aus dem Cache (kein erneuter
    Netzwerk-Call) UND die Seiten 3+4 werden nachgeladen -- das Ergebnis ist
    VOLLSTAENDIG und NICHT mehr als fehlgeschlagen markiert."""
    from services.official_alerts import meteoalarm, warn_egress

    pages: dict = {}
    page_hits: dict = {}
    handler_cls = _make_flaky_index_handler(pages, page_hits)
    server, thread = _run_server(handler_cls)
    try:
        pages[("AT", 1)] = [
            {"body": {"metadata": {"total_pages": 4}, "features": [{"properties": {"alertId": "p1"}}]}}
        ]
        pages[("AT", 2)] = [{"body": {"features": [{"properties": {"alertId": "p2"}}]}}]
        pages[("AT", 3)] = [{"body": {"features": [{"properties": {"alertId": "p3"}}]}}]
        pages[("AT", 4)] = [{"body": {"features": [{"properties": {"alertId": "p4"}}]}}]

        monkeypatch.setenv("GZ_METEOALARM_APIKEY", "dummy-test-token-budget")
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{server.server_port}")

        # Erster Aufruf: die Fake-Uhr schreitet so schnell voran, dass das
        # Budget (20s) bereits VOR Seite 3 erschoepft ist.
        monkeypatch.setattr(meteoalarm, "_WALL_CLOCK_FN", _SteppingClock(start=0.0, step=10.0))
        with warn_egress.observe_fetch_failure() as first_status:
            first_index = meteoalarm._get_cached_index("AT")

        first_ids = {f["properties"]["alertId"] for f in first_index["features"]}
        assert first_ids == {"p1", "p2"}, (
            f"erster Aufruf muss NUR die vor Budget-Erschoepfung geholten Seiten liefern, war {first_ids}"
        )
        assert first_status["failed"] is True, (
            "erschoepftes Budget muss den Fetch als real fehlgeschlagen markieren (unavailable=True)"
        )
        assert page_hits.get(("AT", 3), 0) == 0 and page_hits.get(("AT", 4), 0) == 0, (
            "Seiten 3+4 duerfen beim ersten (budget-begrenzten) Aufruf NICHT angefragt werden"
        )

        # Zweiter Aufruf, SELBER Zeitslot (real verstreichen nur Millisekunden
        # zwischen den beiden Aufrufen), ausreichend Budget (konstante
        # Fake-Uhr): Seiten 1+2 kommen aus dem Cache, Seiten 3+4 werden
        # nachgeladen -- das Ergebnis ist vollstaendig.
        monkeypatch.setattr(meteoalarm, "_WALL_CLOCK_FN", _SteppingClock(start=0.0, step=0.0))
        with warn_egress.observe_fetch_failure() as second_status:
            second_index = meteoalarm._get_cached_index("AT")

        second_ids = {f["properties"]["alertId"] for f in second_index["features"]}
        assert second_ids == {"p1", "p2", "p3", "p4"}, (
            f"zweiter Aufruf muss den Satz vervollstaendigen, war {second_ids}"
        )
        assert second_status["failed"] is False, (
            "ein vollstaendiger Index darf NICHT mehr als fehlgeschlagen markiert werden"
        )
        assert page_hits[("AT", 1)] == 1, (
            f"Seite 1 muss beim zweiten Aufruf aus dem Cache kommen (kein erneuter Call), "
            f"Treffer: {page_hits[('AT', 1)]}"
        )
        assert page_hits[("AT", 2)] == 1, (
            f"Seite 2 muss beim zweiten Aufruf aus dem Cache kommen (kein erneuter Call), "
            f"Treffer: {page_hits[('AT', 2)]}"
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_slot_helfer_runden_auf_raster():
    """``_current_slot_end()`` rundet auf die aktuelle Rasterzelle AB (nicht
    auf zur naechsten), ``_slot_key()`` bildet daraus einen kompakten,
    sortierbaren Schluessel-Teil.

    Issue #1397 S1: Rasterbreite 30 -> 60 Minuten. Die frueher geprueften
    Halbstunden-Grenzen (10:41 -> 10:30) sind damit hinfaellig -- ersetzende
    Aussage: JEDE Minute einer Stunde faellt auf denselben Slot (die volle
    Stunde), denn die Rueckschau haengt jetzt am kumulierten Bestand und
    nicht mehr an der Auffrischungs-Rasterbreite."""
    from datetime import datetime, timezone

    from services.official_alerts import meteoalarm

    assert meteoalarm._current_slot_end(datetime(2026, 7, 27, 10, 17, 3, tzinfo=timezone.utc)) == \
        datetime(2026, 7, 27, 10, 0, 0, tzinfo=timezone.utc)
    assert meteoalarm._current_slot_end(datetime(2026, 7, 27, 10, 41, 59, tzinfo=timezone.utc)) == \
        datetime(2026, 7, 27, 10, 0, 0, tzinfo=timezone.utc)
    assert meteoalarm._current_slot_end(datetime(2026, 7, 27, 10, 0, 0, tzinfo=timezone.utc)) == \
        datetime(2026, 7, 27, 10, 0, 0, tzinfo=timezone.utc)
    assert meteoalarm._current_slot_end(datetime(2026, 7, 27, 11, 0, 0, tzinfo=timezone.utc)) == \
        datetime(2026, 7, 27, 11, 0, 0, tzinfo=timezone.utc)
    assert meteoalarm._slot_key(datetime(2026, 7, 27, 10, 0, 0, tzinfo=timezone.utc)) == "20260727T1000Z"


def test_prune_stale_slot_entries_entfernt_nur_fremde_slots_desselben_landes():
    """S1c: GIVEN Cache-Eintraege aus einem FREMDEN und dem AKTUELLEN
    Zeitslot desselben Landes sowie ein ANDERES Land, WHEN
    ``_prune_stale_slot_entries()`` aufgerufen wird, THEN werden NUR die
    fremden Slot-Eintraege DIESES Landes entfernt -- der Cache waechst bei
    einem Slot-Wechsel nicht unbegrenzt weiter, andere Laender/der aktuelle
    Slot bleiben unberuehrt (keine Vermischung alter/neuer Seiten)."""
    from services.official_alerts import meteoalarm

    meteoalarm._index_cache.update({
        "AT:20260101T0000Z:p1": {"data": "alt"},
        "AT:20260101T0000Z:p2": {"data": "alt"},
        "AT:20260727T1000Z:p1": {"data": "aktuell"},
        "IT:20260101T0000Z:p1": {"data": "anderes-land-bleibt"},
    })

    meteoalarm._prune_stale_slot_entries("AT", "20260727T1000Z")

    assert set(meteoalarm._index_cache.keys()) == {"AT:20260727T1000Z:p1", "IT:20260101T0000Z:p1"}, (
        f"nur fremde AT-Slots duerfen entfernt werden, verbleibend: {list(meteoalarm._index_cache.keys())}"
    )


def test_prune_stale_slot_entries_laesst_bestand_und_fortschrittsmarke_stehen():
    """Adversary F002 (Fix-Loop 1): GIVEN neben Seiten-Cache-Eintraegen liegt
    der kumulierte Bestand samt Fortschrittsmarke unter dem reservierten
    Schluessel ``AT:bestand`` im selben Dict, WHEN der Aufraeumlauf beim
    Slot-Wechsel laeuft, THEN bleiben Bestand UND Fortschrittsmarke
    unveraendert erhalten -- sonst faellt der Dienst bei jedem Slot-Wechsel
    auf Kaltstart zurueck und verliert alle bereits gesehenen Warnungen
    (genau die Kopplung, die Issue #1397 S1 aufgeloest hat)."""
    from services.official_alerts import meteoalarm

    bestand = meteoalarm._country_store("AT")
    bestand["features"]["schluessel-einer-warnung"] = {"feature": {"x": 1}, "seen_at": 123.0}
    bestand["last_complete"] = "marke-bleibt"
    meteoalarm._index_cache.update({
        "AT:20260101T0000Z:p1": {"data": "alt"},
        "AT:20260727T1000Z:p1": {"data": "aktuell"},
    })

    meteoalarm._prune_stale_slot_entries("AT", "20260727T1000Z")

    assert "AT:bestand" in meteoalarm._index_cache, (
        f"der kumulierte Bestand darf beim Slot-Aufraeumen NIE mitgeloescht werden, "
        f"verbleibend: {list(meteoalarm._index_cache.keys())}"
    )
    danach = meteoalarm._country_store("AT")
    assert danach["features"] == {"schluessel-einer-warnung": {"feature": {"x": 1}, "seen_at": 123.0}}, (
        f"gesehene Warnungen muessen den Slot-Wechsel ueberleben, erhalten: {danach['features']}"
    )
    assert danach["last_complete"] == "marke-bleibt", (
        "die Fortschrittsmarke ueberlebt den Slot-Wechsel -- sonst waere jeder "
        "Zyklus wieder ein Kaltstart-Breitband-Abruf"
    )


# ---------------------------------------------------------------------------
# Tageskontingent-Fund (Issue #1397 S1c-Nachbesserung, Produktion 2026-07-27
# 10:37 UTC): eigene Tagesbudget-Schranke (MeteoAlarmBudgetGate) VOR jedem
# echten Index-Seiten-Abruf -- verhindert, dass wir ein Tageskontingent
# selbst leerfeuern, bevor das echte Limit gemessen ist (#1329-Falle).
# ---------------------------------------------------------------------------

def test_budget_erschoepft_blockiert_index_abruf_komplett(monkeypatch):
    """GIVEN das Tagesbudget ist bereits ausgeschoepft (Zaehler direkt
    vorbereitet, kein Mock der Gate-Klasse), WHEN ``_get_cached_index()``
    aufgerufen wird, THEN wird KEIN einziger echter Netzwerk-Call ausgeloest
    (Server bekommt null Treffer auf Seite 1) UND der Fetch gilt als real
    fehlgeschlagen."""
    from services.official_alerts import meteoalarm, warn_egress

    pages: dict = {}
    page_hits: dict = {}
    handler_cls = _make_flaky_index_handler(pages, page_hits)
    server, thread = _run_server(handler_cls)
    try:
        pages[("AT", 1)] = [{"body": {"features": []}}]

        gate = meteoalarm._meteoalarm_budget_gate()
        for _ in range(gate.daily_budget):
            gate.record_call()

        monkeypatch.setenv("GZ_METEOALARM_APIKEY", "dummy-test-token-budget-exhausted")
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{server.server_port}")

        with warn_egress.observe_fetch_failure() as fetch_status:
            index = meteoalarm._get_cached_index("AT")

        assert index is None, f"erschoepftes Budget muss Seite 1 blockieren -> None, war {index!r}"
        assert fetch_status["failed"] is True
        assert page_hits.get(("AT", 1), 0) == 0, (
            f"KEIN echter Netzwerk-Call darf stattfinden, Treffer: {page_hits.get(('AT', 1), 0)}"
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_budget_erschoepft_waehrend_blaetterns_liefert_teilergebnis(monkeypatch):
    """GIVEN das Tagesbudget reicht fuer GENAU EINEN weiteren Abruf (Seite
    1), WHEN ``_get_cached_index()`` blaettert, THEN liefert es Seite 1 als
    Teilergebnis zurueck UND markiert den Fetch als real fehlgeschlagen --
    Seite 2 wird gar nicht erst angefragt (kein Netzwerk-Call verschwendet).
    Nutzt denselben Fail-soft-Pfad wie ein echter HTTP-Fehlschlag (S1c)."""
    from services.official_alerts import meteoalarm, warn_egress

    pages: dict = {}
    page_hits: dict = {}
    handler_cls = _make_flaky_index_handler(pages, page_hits)
    server, thread = _run_server(handler_cls)
    try:
        pages[("AT", 1)] = [
            {"body": {"metadata": {"total_pages": 2}, "features": [{"properties": {"alertId": "p1"}}]}}
        ]
        pages[("AT", 2)] = [{"body": {"features": [{"properties": {"alertId": "p2"}}]}}]

        gate = meteoalarm._meteoalarm_budget_gate()
        for _ in range(gate.daily_budget - 1):  # genau EIN Aufruf uebrig
            gate.record_call()

        monkeypatch.setenv("GZ_METEOALARM_APIKEY", "dummy-test-token-budget-midway")
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{server.server_port}")

        with warn_egress.observe_fetch_failure() as fetch_status:
            index = meteoalarm._get_cached_index("AT")

        ids = {f["properties"]["alertId"] for f in index["features"]}
        assert ids == {"p1"}, f"NUR Seite 1 darf im Teilergebnis stehen, war {ids}"
        assert fetch_status["failed"] is True
        assert page_hits.get(("AT", 2), 0) == 0, (
            f"Seite 2 darf beim erschoepften Budget NICHT angefragt werden, Treffer: "
            f"{page_hits.get(('AT', 2), 0)}"
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_budget_gate_betrifft_nur_index_seiten_nicht_geometrie_cap(monkeypatch):
    """Team-Lead-Vorgabe: die Budget-Schranke gilt NUR fuer Index-Seiten --
    ein bereits (fast) ausgeschoepftes Tagesbudget darf den Nachlade-Abruf
    (Geometrie/CAP) fuer ein bereits gefundenes Feature NICHT blockieren."""
    from services.official_alerts import meteoalarm

    calls: list[str] = []
    pages: dict = {}
    trentino_geometry = {
        "type": "Polygon",
        "coordinates": [[[7.5, 45.0], [7.5, 45.5], [8.5, 45.5], [8.5, 45.0], [7.5, 45.0]]],
    }
    handler_cls = _make_paging_handler(
        pages=pages,
        geometry_bodies={"/geometry/budget-ok": trentino_geometry},
        cap_bodies={"/cap/budget-ok": _read_fixture("cap_villach_heat.xml")},
        calls=calls,
    )
    server, thread = _run_server(handler_cls)
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        treffer_feature = _minimal_feature(
            "AT", "BUDGET-GATE-TEST", "budget-alert", base_url,
            "/geometry/budget-ok", "/cap/budget-ok",
        )
        pages[("AT", 1)] = {"body": {"metadata": {"total_pages": 1}, "features": [treffer_feature]}}

        gate = meteoalarm._meteoalarm_budget_gate()
        for _ in range(gate.daily_budget - 1):  # genau ein Index-Aufruf (Seite 1) uebrig
            gate.record_call()

        monkeypatch.setenv("GZ_METEOALARM_APIKEY", "dummy-test-token-budget-geometry")
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", base_url)

        alerts = meteoalarm.MeteoAlarmSource().fetch(45.263, 7.917)

        assert any(a.hazard == "extreme_heat" for a in alerts), (
            f"Geometrie-/CAP-Nachladen darf durch das Index-Budget NICHT blockiert werden, "
            f"erhalten: {alerts}"
        )
        assert "/cap/budget-ok" in calls
    finally:
        server.shutdown()
        thread.join(timeout=2)


# ---------------------------------------------------------------------------
# Fensterlaenge (Issue #1397 S1c-Nachbesserung, mit S1 vom 2026-07-30
# neu gefasst): das Publikations-Abfragefenster ist konfigurierbar; ohne ENV
# gilt beim KALTSTART DEFAULT_INDEX_WINDOW_HOURS (23h), im Dauerbetrieb der
# Abstand zur letzten vollstaendigen Auffrischung plus Ueberlappung.
# ---------------------------------------------------------------------------

def test_index_window_hours_default_and_env_override(monkeypatch):
    """GIVEN keine ENV gesetzt, WHEN ``_index_window_hours()`` aufgerufen
    wird, THEN liefert es ``DEFAULT_INDEX_WINDOW_HOURS``. Ein gueltiger
    ``GZ_METEOALARM_WINDOW_HOURS``-Wert ueberschreibt ihn; ein unlesbarer
    oder nicht-positiver Wert faellt fail-soft auf den Default zurueck.

    Issue #1397 S1: der Default ist von 3.0 auf 23.0 gestiegen UND hat eine
    engere Bedeutung -- er ist die Breite des KALTSTART-Fensters (Rueckschau-
    Tiefe nach einem Neustart), nicht mehr die Breite JEDES Zyklus. Im
    Dauerbetrieb bestimmt ``_index_query_window()`` die Breite aus dem
    Abstand zur letzten vollstaendigen Auffrischung. Fail-soft-Verhalten der
    ENV-Auswertung (die eigentliche Aussage dieses Tests) unveraendert."""
    from services.official_alerts import meteoalarm

    monkeypatch.delenv("GZ_METEOALARM_WINDOW_HOURS", raising=False)
    assert meteoalarm.DEFAULT_INDEX_WINDOW_HOURS == 23.0
    assert meteoalarm._index_window_hours() == 23.0

    monkeypatch.setenv("GZ_METEOALARM_WINDOW_HOURS", "6")
    assert meteoalarm._index_window_hours() == 6.0

    monkeypatch.setenv("GZ_METEOALARM_WINDOW_HOURS", "nicht-lesbar")
    assert meteoalarm._index_window_hours() == 23.0, "unlesbarer ENV-Wert faellt auf Default zurueck"

    monkeypatch.setenv("GZ_METEOALARM_WINDOW_HOURS", "0")
    assert meteoalarm._index_window_hours() == 23.0, "0 ist kein gueltiges Fenster -> Default"

    monkeypatch.setenv("GZ_METEOALARM_WINDOW_HOURS", "-3")
    assert meteoalarm._index_window_hours() == 23.0, "negativer Wert -> Default"


def _make_window_capturing_handler(captured: list):
    """Echter lokaler Server (kein Mock): zeichnet den ANGEFRAGTEN Pfad
    (inkl. ``datetime``-Query) auf, statt eine feste Fixture zu spielen --
    Beweis dafuer, welches Fenster tatsaechlich gesendet wurde."""

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib-Signatur
            captured.append(self.path)
            body = json.dumps({"features": []}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):  # Testlauf-Output nicht zumuellen
            pass

    return _Handler


def _extract_query_window(path: str) -> "tuple":
    from datetime import datetime as _dt

    qs = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
    start_str, end_str = qs["datetime"][0].split("/")
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return _dt.strptime(start_str, fmt), _dt.strptime(end_str, fmt)


def test_kaltstart_fenster_ist_dreiundzwanzig_stunden(monkeypatch):
    """Issue #1397 S1 (ersetzt ``..._default_ist_drei_stunden``): OHNE ENV und
    OHNE vorherigen Zyklus (Kaltstart -- genau die Lage nach einem Neustart)
    muss die tatsaechlich an die API gesendete ``datetime``-Query 23 Stunden
    umfassen, damit die Rueckschau sofort steht. Die alte Aussage ("genau 3h
    in JEDEM Zyklus") ist hinfaellig: das schmale Fenster gilt jetzt nur noch
    fuer die Auffrischung eines bereits gefuellten Bestands."""
    from datetime import timedelta

    from services.official_alerts import meteoalarm

    captured: list[str] = []
    handler_cls = _make_window_capturing_handler(captured)
    server, thread = _run_server(handler_cls)
    try:
        monkeypatch.delenv("GZ_METEOALARM_WINDOW_HOURS", raising=False)
        monkeypatch.setenv("GZ_METEOALARM_APIKEY", "dummy-test-token-window-default")
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{server.server_port}")

        meteoalarm._get_cached_index("AT")

        assert len(captured) == 1
        start_dt, end_dt = _extract_query_window(captured[0])
        assert end_dt - start_dt == timedelta(hours=23), (
            f"Kaltstart-Fenster muss 23h betragen, war {end_dt - start_dt}"
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_index_window_hours_env_override_aendert_gesendete_query(monkeypatch):
    """S1c-Nachbesserung: GIVEN ``GZ_METEOALARM_WINDOW_HOURS=1``, WHEN
    ``_get_cached_index()`` den Index-Call baut, THEN liegt der angefragte
    Start-Zeitpunkt GENAU 1h vor dem (auf den Slot gerundeten) Ende --
    ohne Deploy nachziehbar, sobald das echte Limit bekannt ist."""
    from datetime import timedelta

    from services.official_alerts import meteoalarm

    captured: list[str] = []
    handler_cls = _make_window_capturing_handler(captured)
    server, thread = _run_server(handler_cls)
    try:
        monkeypatch.setenv("GZ_METEOALARM_WINDOW_HOURS", "1")
        monkeypatch.setenv("GZ_METEOALARM_APIKEY", "dummy-test-token-window-override")
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{server.server_port}")

        meteoalarm._get_cached_index("AT")

        assert len(captured) == 1
        start_dt, end_dt = _extract_query_window(captured[0])
        assert end_dt - start_dt == timedelta(hours=1), (
            f"ENV-Override muss die gesendete Fensterlaenge auf 1h aendern, war {end_dt - start_dt}"
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)


# ---------------------------------------------------------------------------
# Adversary-Fund (Runde 2, 2026-07-27): der beobachtete Tageskontingent-
# Reset muss aus dem echten meteoalarm-Pfad (_get_cached_index -> on_response
# -> _capture_reset) tatsaechlich im Budget-Gate persistiert werden, nicht
# nur in einem isolierten Unit-Test der Gate-Klasse.
# ---------------------------------------------------------------------------

def test_beobachteter_daily_reset_sperrt_budget_ueber_echten_pfad(monkeypatch):
    """GIVEN ein echter lokaler Server antwortet mit einem Tageskontingent-
    429 (x-ratelimit-reset 86.399s in der Zukunft, belegte Messung), WHEN
    ``_get_cached_index()`` diese Antwort verarbeitet, THEN persistiert der
    ECHTE meteoalarm-Pfad (``_capture_reset`` -> ``record_observed_reset``)
    diesen Reset-Zeitpunkt im Budget-Gate -- das Budget bleibt bis dahin
    GESPERRT, obwohl der eigene Zaehlerstand (1 Versuch, keine Wiederholung
    bei Tageskontingent) weit unter dem 200er-Budget liegt."""
    from datetime import datetime, timezone

    from services.official_alerts import meteoalarm

    pages: dict = {}
    page_hits: dict = {}
    handler_cls = _make_flaky_index_handler(pages, page_hits)
    server, thread = _run_server(handler_cls)
    try:
        # 1000.0 (Fake-Uhr) + 86399s = 87399.0 -- exakt die belegte Messung.
        pages[("AT", 1)] = [{"status": 429, "headers": {"x-ratelimit-reset": "87399"}}]

        monkeypatch.setenv("GZ_METEOALARM_APIKEY", "dummy-test-token-observed-reset")
        monkeypatch.setattr(meteoalarm, "METEOALARM_BASE_URL", f"http://127.0.0.1:{server.server_port}")
        monkeypatch.setattr(meteoalarm, "_WALL_CLOCK_FN", lambda: 1000.0)

        index = meteoalarm._get_cached_index("AT")

        assert index is None, "Tageskontingent-429 auf Seite 1 -> kein Index"
        assert page_hits[("AT", 1)] == 1, (
            f"Tageskontingent darf NICHT wiederholt werden, Treffer: {page_hits[('AT', 1)]}"
        )

        gate = meteoalarm._meteoalarm_budget_gate()
        before_reset = datetime.fromtimestamp(1000.0 + 43200, tz=timezone.utc)  # 12h spaeter
        after_reset = datetime.fromtimestamp(87400.0, tz=timezone.utc)  # kurz NACH dem Reset

        assert gate.allow(now=before_reset) is False, (
            "das Budget muss bis zum ECHTEN, ueber den meteoalarm-Pfad beobachteten "
            "Reset-Zeitpunkt gesperrt bleiben -- auch mit nur 1 verbrauchtem Aufruf"
        )
        assert gate.allow(now=after_reset) is True, (
            "nach dem beobachteten Reset-Zeitpunkt muss das Budget wieder oeffnen"
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)


# ---------------------------------------------------------------------------
# Issue #1397 Scheibe S2b: MeteoAlarmSource.covers() nimmt franzoesische
# Départements aus (INCA-Bbox reicht ~100km in die Provence). Verlaesslich
# erst seit Issue #1400 -- die gefaehrlichste Stelle dieses Auftrags: ein
# Fehler hier wuerde MeteoAlarm komplett fuer Oesterreich/Italien abschalten.
# ---------------------------------------------------------------------------

def test_covers_schliesst_franzoesische_orte_in_der_provence_aus():
    """GIVEN Fréjus und Saint-Tropez (Var, 83) liegen geografisch INNERHALB
    der INCA-Bbox (Grobgatter Oesterreich reicht bis lon 9,5, diese Orte
    liegen bei lon ~6,6-6,7), WHEN ``covers()`` aufgerufen wird, THEN
    liefert es False -- MeteoAlarm ist fuer Frankreich nicht zustaendig
    (Issue #1397 S2b: sonst kippt ein einzelner franzoesischer Vergleichs-Ort
    den 'unavailable'-Hinweis fuer den gesamten Ortsvergleich)."""
    from services.official_alerts.meteoalarm import MeteoAlarmSource

    source = MeteoAlarmSource()
    frejus = (43.4332, 6.7370)
    saint_tropez = (43.2677, 6.6407)
    assert source.covers(*frejus) is False, "Fréjus (FR, Var) darf nicht abgedeckt sein"
    assert source.covers(*saint_tropez) is False, "Saint-Tropez (FR, Var) darf nicht abgedeckt sein"


def test_covers_deckt_oesterreich_und_italien_weiterhin_ab():
    """KRITISCHSTER Test dieses Auftrags (Team-Lead-Warnung), Issue #1445 S1
    umformuliert: GIVEN echte oesterreichische und italienische Orte, WHEN
    ``covers()`` BEIDER aktiven Quellen (``MeteoAlarmSource`` fuer AT-Index,
    ``MeteoAlarmFeedSource`` fuer IT-Feed) geprueft wird, THEN deckt
    MINDESTENS EINE der beiden Quellen jeden Ort ab -- das ist die fachlich
    zaehlende Eigenschaft, seit Italien nicht mehr ueber den AT-Index laeuft,
    sondern ueber eine eigene Quelle (kein Ort verliert Abdeckung gegenueber
    dem alten Einzel-Quellen-Stand). Die franzoesische Ausnahme aus S2b darf
    NIEMALS Oesterreich/Italien mit-treffen -- ein Fehler hier wuerde
    MeteoAlarm faktisch komplett abschalten (dedup_id-kritischer
    Regressionswaechter)."""
    from services.official_alerts.meteoalarm import MeteoAlarmSource
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    at_source = MeteoAlarmSource()
    it_source = MeteoAlarmFeedSource("IT")
    toblach = (46.7333, 12.2167)       # Suedtirol/Italien -> IT-Feed
    bozen = (46.4983, 11.3548)         # Suedtirol/Italien -> IT-Feed
    zillertal = (47.2333, 11.8500)     # Oesterreich (Tirol) -> AT-Index
    innsbruck = (47.2692, 11.4041)     # Oesterreich -> AT-Index
    milan = (45.4642, 9.1900)          # Italien (Festland, DPC-Bbox) -> IT-Feed

    for lat, lon, ort in (
        (toblach[0], toblach[1], "Toblach"),
        (bozen[0], bozen[1], "Bozen"),
        (zillertal[0], zillertal[1], "Zillertal"),
        (innsbruck[0], innsbruck[1], "Innsbruck"),
        (milan[0], milan[1], "Mailand"),
    ):
        assert at_source.covers(lat, lon) or it_source.covers(lat, lon), (
            f"{ort} MUSS von mindestens einer der beiden Quellen abgedeckt "
            f"sein (AT-Index ODER IT-Feed) -- die franzoesische Ausnahme "
            f"(#1397 S2b) darf Oesterreich/Italien nicht treffen"
        )

    # Gegenprobe (PO-Auftrag Fix-Runde 1): Fréjus muss nach der uebernommenen
    # franzoesischen Ausnahme in BEIDEN Quellen als nicht abgedeckt gelten.
    frejus = (43.4330, 6.7370)
    assert at_source.covers(*frejus) is False, "Fréjus darf ueber den AT-Index nicht abgedeckt sein"
    assert it_source.covers(*frejus) is False, "Fréjus darf ueber den IT-Feed nicht abgedeckt sein"


# ERWARTUNG GEDREHT (SPEC: docs/specs/modules/fix_1397_s4_it_grenze.md,
# 2026-08-01). Dieser Test hiess ``test_covers_bekannte_grenze_bayern_
# slowenien_schweiz_ungarn_bleibt_abgedeckt`` und verlangte, dass Slowenien und
# die Schweiz WEITERHIN von der italienischen Quelle abgedeckt sind -- als
# Waechter ueber eine damals bewusst NICHT behobene Grobgatter-Grenze. Warum
# die alte Erwartung faellt: ihre Begruendung ("folgenlos, da der exakte
# Zonen-Filter nach dem Abruf laeuft") war falsch. Genau dieser Filter findet
# fuer solche Punkte keine Zone und meldet ueber ``mark_fetch_incomplete()``
# "nicht abrufbar" (Prod 2026-08-01: 39 Punkte EINER Tour, fortlaufend,
# irrefuehrender Betriebszustand #1434). S4 stellt die IT-Zustaendigkeit auf
# die echte Zonen-Geometrie um; SI/CH sind damit korrekt nicht mehr abgedeckt.

def test_covers_nachbarlaender_ausserhalb_italiens_sind_nicht_it_abgedeckt():
    """Issue #1397 S4: Punkte in Slowenien und der Schweiz liegen zwar in der
    groben DPC-Radar-Bbox, aber in keiner der 187 italienischen Warnzonen --
    die italienische Quelle ist fuer sie NICHT zustaendig und schweigt, statt
    einen Ausfall zu melden, den es nicht gibt. Bayern bleibt ueber den
    unveraenderten AT-Weg abgedeckt (Invariante 2 der S4-Spec)."""
    from services.official_alerts.meteoalarm import MeteoAlarmSource
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    it_source = MeteoAlarmFeedSource("IT")
    assert MeteoAlarmSource().covers(48.1351, 11.5820) is True, (
        "Bayern (Muenchen) bleibt ueber den AT-Weg abgedeckt -- S4 aendert "
        "nichts an der INCA-Bbox (Invariante 2)"
    )
    for lat, lon, ort in (
        (46.0569, 14.5058, "Ljubljana"),   # Slowenien, in der DPC-Bbox
        (47.3769, 8.5417, "Zuerich"),      # Schweiz, in der DPC-Bbox
    ):
        assert it_source.covers(lat, lon) is False, (
            f"{ort} liegt ausserhalb Italiens und in keiner der 187 Warnzonen -- "
            f"die italienische Quelle darf sich dafuer nicht zustaendig halten"
        )


# ---------------------------------------------------------------------------
# Issue #1427 S1: awareness_type 12 (flooding) und 13 (rain-flood) muessen
# auf die neue Gefahrenart "flood" abbilden (heute: 12 faelschlich "rain",
# 13 unabgebildet -> None). Fixtures sind ECHTE, unveraenderte Aufzeichnungen
# vom oeffentlichen Feed https://feeds.meteoalarm.org/api/v1/warnings/
# feeds-romania (2026-07-31), s. tests/fixtures/meteoalarm/
# README_flood_type12_13.md. Beide tragen awareness_level=1 (gruen) -- der
# volle _extract_alerts_from_cap()-Pfad filtert level<2 vor jeder
# Nutzeranzeige, ein Nachweis DURCH den Level-Filter ist mit diesen Fixtures
# strukturell nicht moeglich (Spec Test Plan, "Verbleibende Einschraenkung").
# Der Nachweis sitzt deshalb an der Abbildungsstelle selbst: die echten
# Modul-Funktionen _find_parameter()/_leading_int() lesen den rohen
# awareness_type-Wert aus der aufgezeichneten CAP-XML, _TYPE_HAZARD_MAP
# (die echte Zuordnungstabelle des Moduls) bildet ihn ab.
# ---------------------------------------------------------------------------

def test_awareness_type_12_flooding_mappt_auf_flood_nicht_rain():
    """S1/AC-1: GIVEN die echte, aufgezeichnete MeteoAlarm-Warnung vom
    awareness_type 12 ('flooding', RO/Alba, 2026-07-31), WHEN die echte
    Gefahren-Zuordnung des Moduls (_TYPE_HAZARD_MAP ueber _leading_int()) auf
    den aus der CAP-XML gelesenen awareness_type-Rohwert angewendet wird,
    THEN ergibt sich hazard == 'flood' -- heute (RED) liefert die Abbildung
    faelschlich 'rain'."""
    import xml.etree.ElementTree as ET

    from services.official_alerts.meteoalarm import (
        _TYPE_HAZARD_MAP,
        _find_parameter,
        _leading_int,
        _local_tag,
    )

    cap_text = _read_fixture("cap_flooding_type12_ro.xml")
    root = ET.fromstring(cap_text)
    info = next(child for child in root if _local_tag(child) == "info")
    type_raw = _find_parameter(info, "awareness_type")

    assert type_raw == "12; flooding", (
        f"Fixture muss den echten awareness_type-Rohwert '12; flooding' "
        f"tragen, gelesen: {type_raw!r}"
    )

    hazard = _TYPE_HAZARD_MAP.get(_leading_int(type_raw))

    assert hazard == "flood", (
        f"awareness_type 12 (flooding) muss auf hazard 'flood' abbilden "
        f"(bisherige Fehlabbildung: 'rain'), erhalten: {hazard!r}"
    )


def test_awareness_type_13_rainflood_mappt_auf_flood_nicht_unabgebildet():
    """S1/AC-1: GIVEN die echte, aufgezeichnete MeteoAlarm-Warnung vom
    awareness_type 13 ('rain-flood', RO/Alba, 2026-07-31), WHEN dieselbe
    echte Gefahren-Zuordnung des Moduls angewendet wird, THEN ergibt sich
    hazard == 'flood' -- heute (RED) ist Typ 13 in _TYPE_HAZARD_MAP gar nicht
    enthalten (Ergebnis None, die Warnung faellt komplett weg)."""
    import xml.etree.ElementTree as ET

    from services.official_alerts.meteoalarm import (
        _TYPE_HAZARD_MAP,
        _find_parameter,
        _leading_int,
        _local_tag,
    )

    cap_text = _read_fixture("cap_rainflood_type13_ro.xml")
    root = ET.fromstring(cap_text)
    info = next(child for child in root if _local_tag(child) == "info")
    type_raw = _find_parameter(info, "awareness_type")

    assert type_raw == "13; rain-flood", (
        f"Fixture muss den echten awareness_type-Rohwert '13; rain-flood' "
        f"tragen, gelesen: {type_raw!r}"
    )

    hazard = _TYPE_HAZARD_MAP.get(_leading_int(type_raw))

    assert hazard == "flood", (
        f"awareness_type 13 (rain-flood) muss auf hazard 'flood' abbilden "
        f"(heute unabgebildet, faellt ganz weg), erhalten: {hazard!r}"
    )
