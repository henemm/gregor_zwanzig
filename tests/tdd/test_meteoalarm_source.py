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
import os
import threading
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


def test_ac5b_kaputtes_index_json_liefert_leere_liste(monkeypatch):
    """AC-5b: GIVEN eine echte HTTP-Antwort (lokaler Test-Server) mit
    strukturell kaputtem JSON-Koerper, WHEN fetch() den Index-Call macht,
    THEN liefert fetch() [] ohne Exception."""
    from services.official_alerts import meteoalarm

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


def test_leerer_index_204_ist_kein_fehler(monkeypatch, caplog):
    """GIVEN eine echte HTTP-Antwort (lokaler Test-Server) mit Status 204
    und leerem Koerper (regulaerer "keine Warnung"-Fall bei MeteoAlarm),
    WHEN ``_get_cached_index()`` diese verarbeitet, THEN liefert es ein
    leeres, aber gueltiges Ergebnis OHNE Exception, cached es als ERFOLG
    (300s-TTL, kein Failure-Cache) und loggt KEIN WARNING."""
    from services.official_alerts import meteoalarm

    server = http.server.HTTPServer(("127.0.0.1", 0), _EmptyBody204Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv("GZ_METEOALARM_APIKEY", "dummy-test-token-204")
        monkeypatch.setattr(
            meteoalarm, "METEOALARM_BASE_URL",
            f"http://127.0.0.1:{server.server_port}",
        )
        meteoalarm._index_cache.pop("IT", None)

        with caplog.at_level("WARNING", logger="meteoalarm"):
            data = meteoalarm._get_cached_index("IT")

        assert data == {"features": []}, (
            f"204/leerer Body muss als leeres, gueltiges Ergebnis behandelt "
            f"werden, erhalten: {data}"
        )
        assert not any(
            "fehlgeschlagen" in rec.message for rec in caplog.records
        ), "204/leerer Body ist der reguläre Fall, kein WARNING-Log erlaubt"

        cache_entry = meteoalarm._index_cache["IT"]
        assert cache_entry["ttl"] == meteoalarm.CACHE_TTL, (
            f"204/leerer Body muss als ERFOLG gecacht werden (300s-TTL), "
            f"nicht als Fehlschlag (60s), erhalten ttl={cache_entry['ttl']}"
        )

        # Zweiter Aufruf innerhalb der TTL darf keinen erneuten HTTP-Call
        # ausloesen -- Server abschalten und pruefen, dass der Cache-Treffer
        # trotzdem klappt (kein ConnectionError).
        server.shutdown()
        thread.join(timeout=2)
        data_cached = meteoalarm._get_cached_index("IT")
        assert data_cached == {"features": []}
    finally:
        meteoalarm._index_cache.pop("IT", None)
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
