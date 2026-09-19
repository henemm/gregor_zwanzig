"""TDD RED -- MeteoAlarm Deutschland: DWD-Warnungen aus dem kontingentfreien
Feed (Issue #1681).

SPEC: docs/specs/modules/feat_1681_meteoalarm_de.md ("## Acceptance Criteria",
AC-1 bis AC-11; Test Plan Test 1-10)
KONTEXT: docs/context/feat-1681-meteoalarm-de.md (Abschnitt Analysis)

AC -> Testfunktion (AC-9 Drift-Waechter: eigene Datei
``tests/tdd/test_dwd_warnzellen_drift.py``):

- AC-1  (Test 1)  ``test_ac1_garmisch_aktive_gelbe_gewitterwarnung_erscheint_mit_stufe_art_zeitraum``,
                  ``test_ac1_feedpfad_und_zonenaufloesung_deutschland``
- AC-2  (Test 2)  ``test_ac2_deutscher_punkt_ohne_warnung_liefert_leere_liste_ohne_ausfallhinweis``
- AC-3  (Test 3)  ``test_ac3_de_feed_ausfall_meldet_nicht_abrufbar_nur_de_quelle``,
                  ``test_ac3_de_feed_ausfall_bayerische_alpen_echte_registry_meldet_nicht_abrufbar``
- AC-4  (Test 4)  ``test_ac4_auslaendische_punkte_covers_und_fetch_konsistent_nicht_zustaendig``
- AC-5  (Test 5)  ``test_ac5_allclear_alert_wird_im_geteilten_umsetzer_verworfen``,
                  ``test_ac5_starnberg_nur_aufhebung_erscheint_nicht_als_aktive_warnung``,
                  ``test_ac5_landsberg_aufhebung_verdraengt_nicht_die_aktive_gelbe_warnung``
- AC-6  (Test 6)  ``test_ac6_allclear_filter_veraendert_it_at_ergebnisse_nicht`` (darf schon
                  jetzt GRUEN sein -- Regressions-Golden-Master, s. unten); zusaetzlich laufen
                  ``test_meteoalarm_feed_italien.py``/``test_meteoalarm_feed_oesterreich.py``
                  unveraendert.
- AC-7  (Test 7)  ``test_ac7_kuestenzellen_nicht_in_der_geometrie``,
                  ``test_ac7_kuestenpunkt_bekommt_kreiswarnung_aber_nie_die_seezelle``
- AC-8            ``test_ac8_quellenvermerk_dwd_bkg_woertlich`` (``# doc-compliance-test``)
- AC-10 (Test 9)  ``test_ac10_de_warnung_erreicht_dieselben_kanaele_wie_at_und_it``
- AC-11 (Test 10) ``test_ac11_grenzraum_garmisch_warnung_genau_einmal_unabhaengig_von_reihenfolge``

RED-Ursachen (bewusst, fachlich): ``MeteoAlarmFeedSource("DE")`` laesst sich heute
zwar konstruieren (``Literal`` ist nur ein Typhinweis), faellt aber in den
italienischen Zweig -- ``covers()`` ist fuer JEDEN deutschen Punkt ``False``,
``fetch()`` meldet ``point_unmapped``. ``_FEED_PATHS["DE"]``,
``_zone_for_point_de`` und ``data/dwd_warngebiete_kreise.json`` existieren nicht,
die Registry kennt keine deutsche Quelle, und der geteilte Umsetzer mappt
``responseType: ["AllClear"]`` als aktive Warnung. Jeder Test, der sonst schon
vor der Implementierung "zufaellig" gruen waere (leere Liste bei nicht
zustaendiger Quelle), traegt eine Positivkontrolle (``covers(...) is True`` bzw.
``_zone_for_point_de``), damit er nur mit echter DE-Funktionalitaet besteht.

Kein Mock-Theater, kein Netz (Kern-Schicht, ohne Marker, laeuft mit
``--disable-socket``): Muster ``tests/tdd/test_official_alerts_unavailable_hint.py``
-- die Modul-Caches werden mit ECHTEN Eintraegen vorbelegt, ``fetch()`` laeuft
ueber den echten Cache-Treffer-Zweig von ``warn_egress.cached_fetch()``:

- Feed: ``meteoalarm_feed._cache[<Land>] = {"data": <aufgezeichneter Feed>, ...}``
  (Cache-Schluessel = Laendercode, Spec ADR-0074).
- Ausfall (AC-3): ``{"data": None, ...}`` -- der Treffer-Zweig meldet ihn ueber
  ``_record_fetch_failure()`` exakt wie einen echten gescheiterten Abruf.
- ZAMG "nicht zustaendig" (404, AC-3/AC-11): ``geosphere_warn._cache[...] =
  {"data": {}, "ttl": WARN_NOT_COVERED_TTL}`` -- exakt der Wert, den
  ``cached_fetch(not_covered_statuses={404})`` bei einem echten 404 ablegt.

Die IT/AT-Feed-Tests verwenden lokale HTTP-Server und tragen daher den
``live``-Marker; hier genuegt der Cache-Weg, damit die Datei im
deterministischen Kern (und damit in der CI-Ampel) laeuft.

Aufgezeichnete Fixture: ``tests/fixtures/meteoalarm_feed/feed_germany_sample.json``
-- 7 reale, unveraenderte Eintraege aus dem Vollabruf vom 2026-09-19
(Herkunft, Auswahl und Ray-Cast-Pruefpunkte: README.md im selben Verzeichnis).
"""
from __future__ import annotations

import json
import shutil
import time
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "meteoalarm_feed"
_DATA_DIR = _REPO_ROOT / "src" / "services" / "official_alerts" / "data"
_GEOMETRIE = _DATA_DIR / "dwd_warngebiete_kreise.json"

# Ray-Cast-verifiziert gegen dwd:Warngebiete_Kreise (2026-09-19, s. README).
GARMISCH = (47.4921, 11.0958)      # 109180000 Kreis Garmisch-Partenkirchen
LENGGRIES = (47.6800, 11.5760)     # 109173000 Kreis Bad Toelz-Wolfratshausen (noerdl. 47,5 -> ohne DPC-Bbox)
STARNBERG = (47.9990, 11.3400)     # 109188000 Kreis Starnberg (nur Aufhebung in der Fixture)
LANDSBERG = (48.0480, 10.8830)     # 109181000 Kreis Landsberg am Lech
PEINE = (52.32, 10.23)             # 103157000 Kreis Peine (kein Eintrag in der Fixture)
CUXHAVEN = (53.8615, 8.6944)       # 903352002 Kreis Cuxhaven - Kueste
FREILASSING = (47.8406, 12.9767)   # 109172000 Kreis Berchtesgadener Land
WEIL_AM_RHEIN = (47.5947, 7.6206)  # 108336000 Kreis Loerrach
# Ausserhalb Deutschlands -- im Kreis-Layer ohne Treffer.
INNSBRUCK = (47.2692, 11.4041)
SALZBURG = (47.8095, 13.0550)
BASEL = (47.5596, 7.5886)
# Referenzpunkte der Schwesterlaender (wie in den IT/AT-Tests).
WIEN = (48.2082, 16.3738)          # ZAMG gemeindenr 90101 -> AT901
ROM = (41.9028, 12.4964)           # DPC-Geometrie -> IT012 (Lazio)

# 17:40 MESZ am Unwettertag: Eintraege #108 (orange Starkregen), #211 (gelbes
# Gewitter) aktiv, Aufhebung #216 (expires 17:47 MESZ) noch nicht abgelaufen.
TEST_NOW_BAYERN = datetime(2026, 9, 16, 15, 40, tzinfo=timezone.utc)
# Aufzeichnungstag: #244 (Windboeen Kueste Kreise) aktiv, #246 (Seezelle) ohne expires.
TEST_NOW_KUESTE = datetime(2026, 9, 19, 14, 50, tzinfo=timezone.utc)

# Eintrag #211 (GEWITTER, gelb) -- 17:25-18:30 MESZ.
GEWITTER_211_VON = datetime(2026, 9, 16, 15, 25, tzinfo=timezone.utc)
GEWITTER_211_BIS = datetime(2026, 9, 16, 16, 30, tzinfo=timezone.utc)
# Eintrag #108 (STARKREGEN, orange) -- 14:00-23:00 MESZ.
REGEN_108_VON = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
REGEN_108_BIS = datetime(2026, 9, 16, 21, 0, tzinfo=timezone.utc)
# Eintrag #141 (STARKES GEWITTER, orange, Landsberg) -- 14:00-15:00 MESZ.
GEWITTER_141_VON = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
# Eintrag #216 (AUFHEBUNG STARKES GEWITTER, orange) -- 16:57-17:47 MESZ.
AUFHEBUNG_216_VON = datetime(2026, 9, 16, 14, 57, tzinfo=timezone.utc)
AUFHEBUNG_216_BIS = datetime(2026, 9, 16, 15, 47, tzinfo=timezone.utc)

_ALL_CHANNELS = {"email", "telegram", "sms", "premium_sms"}


# ───────────────────────────── Helfer ────────────────────────────────────────

def _assert_pruefling_aus_diesem_baum() -> None:
    """#1409: der importierte Pruefling MUSS aus dem Baum DIESER Testdatei
    stammen -- sonst misst der Test aus einem Worktree die Hauptrepo-Kopie."""
    from services.official_alerts import meteoalarm_feed

    modul = Path(meteoalarm_feed.__file__).resolve()
    assert str(modul).startswith(str(_REPO_ROOT)), (
        f"Pruefling {modul} liegt ausserhalb von {_REPO_ROOT}"
    )


@pytest.fixture(autouse=True)
def _caches_leeren():
    """Frischer ZAMG- und Feed-Cache je Test -- mehrere Tests belegen
    DIESELBEN Schluessel ("DE", Garmisch) mit unterschiedlichen Zustaenden."""
    from services.official_alerts import geosphere_warn, meteoalarm_feed

    geosphere_warn._cache.clear()
    meteoalarm_feed._cache.clear()
    yield
    geosphere_warn._cache.clear()
    meteoalarm_feed._cache.clear()


def _feed_de() -> dict:
    return json.loads((_FIXTURES / "feed_germany_sample.json").read_text(encoding="utf-8"))


def _feed_at() -> dict:
    return json.loads((_FIXTURES / "feed_austria_sample.json").read_text(encoding="utf-8"))


def _feed_it() -> dict:
    return json.loads((_FIXTURES / "feed_italy_sample.json").read_text(encoding="utf-8"))


def _alert_nach_identifier(feed: dict, suffix: str) -> dict:
    treffer = [w["alert"] for w in feed["warnings"] if w["alert"]["identifier"].endswith(suffix)]
    assert len(treffer) == 1, f"Fixture-Eintrag *{suffix} nicht eindeutig: {len(treffer)}"
    return treffer[0]


def _feed_vorbelegen(land: str, daten: "dict | None") -> None:
    """Echter Cache-Eintrag in der Form, die ``warn_egress._store_entry()``
    bzw. der Fehlschlag-Zweig von ``cached_fetch()`` ablegt."""
    from services.official_alerts import meteoalarm_feed, warn_egress

    meteoalarm_feed._cache[land] = {
        "data": daten,
        "fetched_at": time.monotonic(),
        "ttl": warn_egress.WARN_SUCCESS_TTL if daten is not None else warn_egress.WARN_FAILURE_TTL,
    }


def _zamg_nicht_zustaendig(lat: float, lon: float) -> None:
    """ZAMG-404 so, wie ``cached_fetch(not_covered_statuses={404})`` ihn ablegt."""
    from services.official_alerts import geosphere_warn, warn_egress

    geosphere_warn._cache[geosphere_warn._round_coord(lat, lon)] = {
        "data": {}, "fetched_at": time.monotonic(), "ttl": warn_egress.WARN_NOT_COVERED_TTL,
    }


def _zamg_gemeinde(lat: float, lon: float, gemeindenr: int, name: str) -> None:
    """ZAMG-Erfolgsantwort in der live verifizierten Form (s. AT-Tests)."""
    from services.official_alerts import geosphere_warn, warn_egress

    geosphere_warn._cache[geosphere_warn._round_coord(lat, lon)] = {
        "data": {
            "type": "Feature",
            "properties": {
                "location": {"type": "Municipal",
                             "properties": {"gemeindenr": gemeindenr, "name": name}},
                "warnings": [],
            },
        },
        "fetched_at": time.monotonic(),
        "ttl": warn_egress.WARN_SUCCESS_TTL,
    }


@contextmanager
def _nur_quellen(*quellen):
    """Registry fuer die Testdauer auf genau diese Quellen setzen, danach
    den Originalbestand wiederherstellen (Muster der AT-Tests)."""
    import services.official_alerts.base as oa_base

    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    oa_base._REGISTERED_SOURCES.extend(quellen)
    try:
        yield
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


def _de_quellen_in_registry() -> list:
    import services.official_alerts.base as oa_base
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    return [s for s in oa_base._REGISTERED_SOURCES
            if isinstance(s, MeteoAlarmFeedSource) and getattr(s, "country", None) == "DE"]


def _warncellids_in(obj) -> "list[str]":
    """Alle Werte eines Schluessels ``WARNCELLID`` irgendwo in einer
    JSON-Struktur -- formatunabhaengig (die Geometriedatei darf GeoJSON oder
    das ``dpc_zones.json``-Muster verwenden)."""
    gefunden: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "WARNCELLID":
                gefunden.append(str(value))
            else:
                gefunden.extend(_warncellids_in(value))
    elif isinstance(obj, list):
        for item in obj:
            gefunden.extend(_warncellids_in(item))
    return gefunden


# ─────────────── AC-1 Grundlagen: Feedpfad + Zonenaufloesung ─────────────────

def test_ac1_feedpfad_und_zonenaufloesung_deutschland():
    """AC-1 (Infrastruktur): GIVEN die deutsche Quelle, WHEN Feedpfad und
    Punkt->Warnzelle abgefragt werden, THEN zeigt der Pfad auf
    ``feeds-germany`` UND ``_zone_for_point_de`` liefert fuer Garmisch die
    WARNCELLID des Landkreises (``109180000``), fuer Innsbruck ``None``."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    assert meteoalarm_feed._FEED_PATHS["DE"] == "/api/v1/warnings/feeds-germany"
    assert str(meteoalarm_feed._zone_for_point_de(*GARMISCH)) == "109180000"
    assert str(meteoalarm_feed._zone_for_point_de(*LANDSBERG)) == "109181000"
    assert meteoalarm_feed._zone_for_point_de(*INNSBRUCK) is None


# ───────────────────────────── AC-1 (Test 1) ─────────────────────────────────

def test_ac1_garmisch_aktive_gelbe_gewitterwarnung_erscheint_mit_stufe_art_zeitraum():
    """AC-1: GIVEN ein Punkt im Landkreis Garmisch-Partenkirchen UND der
    aufgezeichnete DE-Feed fuehrt fuer ``109180000`` eine aktive gelbe
    Gewitterwarnung (#211, 17:25-18:30 MESZ), WHEN die amtlichen Warnungen
    ermittelt werden, THEN erscheint genau diese Warnung mit Stufe, Art und
    Zeitraum -- daneben die ebenfalls aktive orange Starkregenwarnung (#108)."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import get_official_alerts_with_status
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    _feed_vorbelegen("DE", _feed_de())
    de = MeteoAlarmFeedSource("DE")
    assert de.covers(*GARMISCH) is True, "die deutsche Quelle muss fuer Garmisch zustaendig sein"

    with _nur_quellen(de):
        alerts, unavailable = get_official_alerts_with_status(*GARMISCH, now=TEST_NOW_BAYERN)

    gewitter = [a for a in alerts if a.hazard == "thunderstorm"]
    assert len(gewitter) == 1, f"genau EINE Gewitterwarnung erwartet, erhalten {alerts}"
    g = gewitter[0]
    assert g.level == 2
    assert g.source == "meteoalarm"
    assert g.label, "Ereignisbezeichnung darf nicht leer sein"
    assert g.valid_from == GEWITTER_211_VON and g.valid_to == GEWITTER_211_BIS, g
    assert any(
        a.hazard == "rain" and a.level == 3
        and a.valid_from == REGEN_108_VON and a.valid_to == REGEN_108_BIS
        for a in alerts
    ), f"die orange Starkregenwarnung #108 fehlt: {alerts}"
    assert unavailable is False


# ───────────────────────────── AC-2 (Test 2) ─────────────────────────────────

def test_ac2_deutscher_punkt_ohne_warnung_liefert_leere_liste_ohne_ausfallhinweis():
    """AC-2: GIVEN ein Punkt in Deutschland (Peine, ``103157000``), dessen
    Warngebiet im aufgezeichneten Feed keinen Eintrag traegt, WHEN die
    amtlichen Warnungen ermittelt werden, THEN leere Liste UND
    ``unavailable=False`` -- und zwar weil die deutsche Quelle zustaendig ist
    und erfolgreich "keine Warnung" sagt, nicht weil sie schweigt."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import get_official_alerts_with_status, meteoalarm_feed
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    _feed_vorbelegen("DE", _feed_de())
    de = MeteoAlarmFeedSource("DE")
    assert de.covers(*PEINE) is True, "Peine liegt in Deutschland -- die DE-Quelle ist zustaendig"
    assert str(meteoalarm_feed._zone_for_point_de(*PEINE)) == "103157000"

    with _nur_quellen(de):
        alerts, unavailable = get_official_alerts_with_status(*PEINE, now=TEST_NOW_BAYERN)

    assert alerts == []
    assert unavailable is False


# ───────────────────────────── AC-3 (Test 3) ─────────────────────────────────

def test_ac3_de_feed_ausfall_meldet_nicht_abrufbar_nur_de_quelle():
    """AC-3 (Grundfall): GIVEN der DE-Feed-Abruf ist fehlgeschlagen
    (gecachter Fehlschlag), WHEN die Warnungen fuer Garmisch ermittelt werden
    und nur die deutsche Quelle registriert ist, THEN ``unavailable=True``."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import get_official_alerts_with_status
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    _feed_vorbelegen("DE", None)
    with _nur_quellen(MeteoAlarmFeedSource("DE")):
        alerts, unavailable = get_official_alerts_with_status(*GARMISCH, now=TEST_NOW_BAYERN)

    assert unavailable is True, (
        f"ein DE-Feed-Ausfall muss 'nicht abrufbar' melden. alerts={alerts}"
    )


@pytest.mark.parametrize("punkt", [GARMISCH, LENGGRIES], ids=["garmisch", "lenggries"])
def test_ac3_de_feed_ausfall_bayerische_alpen_echte_registry_meldet_nicht_abrufbar(punkt):
    """AC-3 (Suedbayern-Kompensationsluecke): GIVEN der DE-Feed ist
    ausgefallen UND fuer den Punkt antworten die oesterreichischen Quellen
    regulaer "nicht zustaendig" (ZAMG 404 -> GeoSphereWarnSource leer,
    MeteoAlarmFeedSource("AT") Fall 1), WHEN die Warnungen ueber die ECHTE
    Registry (alle registrierten Quellen, echte Reihenfolge) ermittelt werden,
    THEN ``unavailable=True`` -- eine "nicht zustaendig"-Antwort darf den
    Ausfall der einzig wirklich zustaendigen deutschen Quelle nicht
    kompensieren.

    Gemessene Zustaendigkeit (``covers()`` der echten Registry, 2026-09-19):
    - Lenggries (47,68 N): GeoSphereWarnSource + MeteoAlarmFeedSource("AT")
      (reine INCA-Bbox) -- der in der Spec benannte Fall.
    - Garmisch (47,49 N): ZUSAETZLICH ``DpcSource`` -- die italienische
      Radar-Bbox reicht bis 47,5 N; ``DpcSource.fetch`` findet keine DPC-Zone
      und liefert ohne Netzabruf erfolgreich ``[]``. Damit maskieren am
      Kanon-Punkt der Spec DREI "nicht zustaendig"-Antworten den DE-Ausfall
      (GeoSphere-404, AT Fall 1, DPC ohne Zone). Der ``base.py``-Fix muss
      deshalb JEDE Quelle, die fuer den Punkt fachlich "nicht zustaendig"
      antwortet, aus der ``covering``-Bilanz nehmen -- nicht nur den AT-Zweig.
      Kein Netz: DPC bricht vor dem Bulletin-Abruf ab (``_zone_at`` ist None)."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import get_official_alerts_with_status

    de_quellen = _de_quellen_in_registry()
    assert len(de_quellen) == 1, (
        f"MeteoAlarmFeedSource('DE') muss genau einmal registriert sein, gefunden {len(de_quellen)}"
    )
    _zamg_nicht_zustaendig(*punkt)
    _feed_vorbelegen("DE", None)

    alerts, unavailable = get_official_alerts_with_status(*punkt, now=TEST_NOW_BAYERN)

    assert unavailable is True, (
        f"DE-Ausfall in den Bayerischen Alpen wird von 'nicht zustaendig'-Antworten "
        f"(AT/GeoSphere/DPC) ueberdeckt. alerts={alerts}, unavailable={unavailable}"
    )


# ───────────────────────────── AC-4 (Test 4) ─────────────────────────────────

@pytest.mark.parametrize(
    "ausland, kontrolle, kontroll_zelle",
    [
        (INNSBRUCK, GARMISCH, "109180000"),
        (SALZBURG, FREILASSING, "109172000"),
        (BASEL, WEIL_AM_RHEIN, "108336000"),
    ],
    ids=["innsbruck", "salzburg", "basel"],
)
def test_ac4_auslaendische_punkte_covers_und_fetch_konsistent_nicht_zustaendig(
    ausland, kontrolle, kontroll_zelle,
):
    """AC-4: GIVEN ein Punkt ausserhalb Deutschlands (Innsbruck, Salzburg,
    Basel), WHEN ``covers()`` UND ``fetch()`` der deutschen Quelle aufgerufen
    werden, THEN beide sagen konsistent "nicht zustaendig": ``covers`` False,
    ``fetch`` leer OHNE Fehlschlag-Markierung (kein ``mark_fetch_incomplete``).
    Positivkontrolle im selben Test: der deutsche Nachbarpunkt jenseits der
    Grenze ist zustaendig und wird seiner Warnzelle zugeordnet -- sonst waere
    "nicht zustaendig" nur leeres Schweigen."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed, warn_egress
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    _feed_vorbelegen("DE", _feed_de())
    de = MeteoAlarmFeedSource("DE")

    assert de.covers(*kontrolle) is True
    assert str(meteoalarm_feed._zone_for_point_de(*kontrolle)) == kontroll_zelle

    assert meteoalarm_feed._zone_for_point_de(*ausland) is None
    assert de.covers(*ausland) is False
    with warn_egress.observe_fetch_failure() as status:
        ergebnis = de.fetch(*ausland)
    assert ergebnis == []
    assert status["failed"] is False, (
        "ein nicht zustaendiger Auslandspunkt darf keinen deutschen Ausfallhinweis ausloesen"
    )


# ───────────────────────────── AC-5 (Test 5) ─────────────────────────────────

def test_ac5_allclear_alert_wird_im_geteilten_umsetzer_verworfen():
    """AC-5 (geteilter Umsetzer IT/AT/DE): GIVEN der echte Aufhebungs-Eintrag
    #216 (``responseType: ["AllClear"]``) und der echte aktive Eintrag #211
    (``["Prepare"]``), WHEN beide durch ``_info_entries_from_alert`` +
    ``_group_and_map_info_entries`` laufen, THEN liefert die Aufhebung KEINE
    Warnung, der aktive Eintrag weiterhin seine."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts.meteoalarm import _group_and_map_info_entries
    from services.official_alerts.meteoalarm_feed import _info_entries_from_alert

    feed = _feed_de()
    aufhebung = _alert_nach_identifier(feed, "031ad672-42fe-411f-b4d6-5b11785c051e.MUL")
    aktiv = _alert_nach_identifier(feed, "239d17e8-4827-4990-973a-8fdd25c4c2b2.MUL")
    assert all(i.get("responseType") == ["AllClear"] for i in aufhebung["info"]), "Fixture-Vorbedingung"

    assert _group_and_map_info_entries(_info_entries_from_alert(aufhebung)) == [], (
        "eine amtlich aufgehobene Warnung darf nicht als aktive Warnung gemappt werden"
    )
    assert _group_and_map_info_entries(_info_entries_from_alert(aktiv)), (
        "Kontrolle: der aktive Eintrag #211 muss weiterhin gemappt werden"
    )


def test_ac5_starnberg_nur_aufhebung_erscheint_nicht_als_aktive_warnung():
    """AC-5: GIVEN fuer Starnberg (``109188000``) fuehrt die Fixture
    ausschliesslich die Aufhebung #216 mit zum Testzeitpunkt noch
    ZUKUENFTIGEM ``expires`` (17:47 MESZ > 17:40 MESZ), WHEN die Warnungen
    ermittelt werden, THEN erscheint sie NICHT als aktive Warnung -- bei
    zustaendiger, erfolgreich antwortender deutscher Quelle."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import get_official_alerts_with_status
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    feed = _feed_de()
    starnberg_eintraege = [
        w["alert"] for w in feed["warnings"]
        if "109188000" in {g["value"] for i in w["alert"]["info"] for ar in i["area"] for g in ar["geocode"]}
    ]
    assert len(starnberg_eintraege) == 1, "Fixture-Vorbedingung: nur die Aufhebung fuer Starnberg"
    assert TEST_NOW_BAYERN < AUFHEBUNG_216_BIS, "Fixture-Vorbedingung: expires liegt in der Zukunft"

    _feed_vorbelegen("DE", feed)
    de = MeteoAlarmFeedSource("DE")
    assert de.covers(*STARNBERG) is True

    with _nur_quellen(de):
        alerts, unavailable = get_official_alerts_with_status(*STARNBERG, now=TEST_NOW_BAYERN)

    assert alerts == [], f"aufgehobene Warnung erscheint als aktiv: {alerts}"
    assert unavailable is False


def test_ac5_landsberg_aufhebung_verdraengt_nicht_die_aktive_gelbe_warnung():
    """AC-5 (Mischlage): GIVEN Landsberg (``109181000``) hat zum
    Testzeitpunkt die aktive gelbe Gewitterwarnung #211 UND die noch nicht
    abgelaufene Aufhebung #216 (orange Gewitter), WHEN die Warnungen
    ermittelt werden, THEN bleibt genau die gelbe aktiv -- die aufgehobene
    orange erscheint nicht (sie gewaenne sonst den Stufenvergleich)."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import get_official_alerts_with_status
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    _feed_vorbelegen("DE", _feed_de())
    de = MeteoAlarmFeedSource("DE")
    assert de.covers(*LANDSBERG) is True

    with _nur_quellen(de):
        alerts, unavailable = get_official_alerts_with_status(*LANDSBERG, now=TEST_NOW_BAYERN)

    gewitter = [a for a in alerts if a.hazard == "thunderstorm"]
    assert [(a.level, a.valid_from, a.valid_to) for a in gewitter] == [
        (2, GEWITTER_211_VON, GEWITTER_211_BIS)
    ], f"erwartet nur #211 gelb, erhalten {alerts}"
    assert unavailable is False


# ───────────────────────────── AC-6 (Test 6) ─────────────────────────────────

# Golden Master, erzeugt 2026-09-19 mit dem UNVERAENDERTEN Umsetzer
# (``_group_and_map_info_entries(_info_entries_from_alert(alert))`` je Eintrag
# der IT/AT-Stichproben): (hazard, level, valid_from, valid_to, region_label).
_GOLDEN_IT_AT = {
    "feed_italy_sample.json": {
        "2.49.0.0.380.3.IT.260731115902.089": [("extreme_heat", 3, "2026-07-31T11:00:00+02:00", "2026-08-02T01:59:00+02:00", "Lazio")],
        "2.49.0.0.380.3.IT.260726112159.099": [("thunderstorm", 3, "2026-07-26T10:00:00+02:00", "2026-07-26T19:59:00+02:00", "Lazio")],
        "2.49.0.0.380.3.IT.260726112159.105": [("wind_gust", 3, "2026-07-26T14:00:00+02:00", "2026-07-26T19:59:00+02:00", "Lazio")],
        "2.49.0.0.380.3.IT.260731115902.047": [("thunderstorm", 2, "2026-07-31T14:00:00+02:00", "2026-07-31T19:59:00+02:00", "Valle d'Aosta")],
        "2.49.0.0.380.3.IT.260726112159.001": [],
        "2.49.0.0.380.3.IT.260731115902.048": [("rain", 2, "2026-07-31T10:00:00+02:00", "2026-08-01T01:59:00+02:00", "Piemonte")],
        "2.49.0.0.380.3.IT.260731115902.058": [("extreme_heat", 3, "2026-07-31T11:00:00+02:00", "2026-08-02T01:59:00+02:00", "Lombardia")],
        "2.49.0.0.380.3.IT.260731115902.060": [("thunderstorm", 2, "2026-07-31T11:00:00+02:00", "2026-08-01T01:59:00+02:00", "Trentino Alto Adige")],
        "2.49.0.0.380.3.IT.260729113318.097": [("thunderstorm", 2, "2026-07-29T11:00:00+02:00", "2026-07-30T01:59:00+02:00", "Sicilia")],
        "2.49.0.0.380.3.IT.260731115902.080": [("extreme_heat", 4, "2026-08-02T02:00:00+02:00", "2026-08-02T23:59:00+02:00", "Basilicata")],
    },
    "feed_austria_sample.json": {
        "2.49.0.0.40.0.AT.-20260731095118_d1_707": [("extreme_heat", 2, "2026-08-01T00:00:00+02:00", "2026-08-01T23:59:59+02:00", "Lienz")],
        "2.49.0.0.40.0.AT.20260726094324.4824_2_707": [("thunderstorm", 2, "2026-07-26T12:00:00+02:00", "2026-07-26T20:00:00+02:00", "Lienz")],
        "2.49.0.0.40.0.AT.-20260726034825_ATNT_505": [("thunderstorm", 2, "2026-07-26T03:48:24+02:00", "2026-07-26T04:48:24+02:00", "Tamsweg")],
        "2.49.0.0.40.0.AT.-20260731095118_d1_901": [("extreme_heat", 3, "2026-08-01T00:00:00+02:00", "2026-08-01T23:59:59+02:00", "Wien Innere Stadt")],
        "2.49.0.0.40.0.AT.20260727081958.4825_2_304": [("wind_gust", 2, "2026-07-27T08:00:00+02:00", "2026-07-27T18:00:00+02:00", "Wiener Neustadt (Stadt)")],
        "2.49.0.0.40.0.AT.-20260731095116_d1_601": [("extreme_heat", 3, "2026-08-01T00:00:00+02:00", "2026-08-01T23:59:59+02:00", "Graz (Stadt)")],
    },
}
# Aequivalenz-Aufzeichnungen: Anzahl gemappter Warnungen je (hazard, level).
_GOLDEN_AEQUIVALENZ = {
    "feed_italy_equivalence.json": {("extreme_heat", 3): 7, ("extreme_heat", 4): 8, ("rain", 2): 2, ("thunderstorm", 2): 16},
    "feed_austria_equivalence.json": {("extreme_heat", 2): 25, ("extreme_heat", 3): 29, ("thunderstorm", 2): 33, ("wind_gust", 2): 3},
}


def test_ac6_allclear_filter_veraendert_it_at_ergebnisse_nicht():
    """AC-6 (Regression, darf schon VOR der Implementierung gruen sein): GIVEN
    die aufgezeichneten IT/AT-Feeds (Stichproben + Aequivalenz-Aufzeichnungen),
    WHEN sie nach Einbau des AllClear-Filters durch den geteilten Umsetzer
    laufen, THEN ist jedes Ergebnis identisch zum vor der Aenderung
    festgehaltenen Golden Master.

    Keine Tautologie: IT/AT tragen ``responseType`` ``["Monitor"]`` bzw.
    ``None`` -- ein zu breit gebauter Filter (z. B. "alles ausser Prepare
    verwerfen") macht diesen Test rot."""
    import collections

    from services.official_alerts.meteoalarm import _group_and_map_info_entries
    from services.official_alerts.meteoalarm_feed import _info_entries_from_alert

    for datei, erwartet in _GOLDEN_IT_AT.items():
        feed = json.loads((_FIXTURES / datei).read_text(encoding="utf-8"))
        ist = {}
        for w in feed["warnings"]:
            alert = w["alert"]
            ist[alert["identifier"]] = [
                (a.hazard, a.level,
                 a.valid_from.isoformat() if a.valid_from else None,
                 a.valid_to.isoformat() if a.valid_to else None,
                 a.region_label)
                for a in _group_and_map_info_entries(_info_entries_from_alert(alert))
            ]
        assert ist == erwartet, f"{datei}: Ergebnis weicht vom Golden Master ab"

    for datei, erwartet in _GOLDEN_AEQUIVALENZ.items():
        feed = json.loads((_FIXTURES / datei).read_text(encoding="utf-8"))
        zaehler: collections.Counter = collections.Counter()
        for w in feed["warnings"]:
            for a in _group_and_map_info_entries(_info_entries_from_alert(w.get("alert") or {})):
                zaehler[(a.hazard, a.level)] += 1
        assert dict(zaehler) == erwartet, f"{datei}: Ergebnis weicht vom Golden Master ab"


# ───────────────────────────── AC-7 (Test 7) ─────────────────────────────────

def test_ac7_kuestenzellen_nicht_in_der_geometrie():
    """AC-7: GIVEN die eingecheckte DWD-Kreisgeometrie, WHEN ihre
    WARNCELLIDs gelesen werden, THEN enthaelt sie die Landkreise (u. a.
    Garmisch, die Kuesten-KREISzelle Cuxhaven) aber KEINE einzige
    Kuesten-/Seezelle ``501...`` -- die Fixture-Seezelle ohne ``expires``
    kann daher keinem Punkt zugeordnet werden."""
    feed = _feed_de()
    seezellen = {
        str(g["value"])
        for w in feed["warnings"] for i in w["alert"]["info"]
        if i.get("expires") is None
        for ar in i["area"] for g in ar["geocode"] if g["valueName"] == "WARNCELLID"
    }
    assert seezellen and all(z.startswith("501") for z in seezellen), (
        f"Fixture-Vorbedingung: Eintraege ohne expires tragen nur 501-Zellen, gefunden {seezellen}"
    )

    assert _GEOMETRIE.exists(), f"Geometriedatei fehlt: {_GEOMETRIE}"
    zellen = set(_warncellids_in(json.loads(_GEOMETRIE.read_text(encoding="utf-8"))))
    assert len(zellen) >= 400, f"erwartet ~402 Kreisflaechen, gefunden {len(zellen)}"
    assert {"109180000", "903352002", "103157000"} <= zellen
    assert not {z for z in zellen if z.startswith("501")}, "Kuestenzellen duerfen nicht enthalten sein"
    assert not (seezellen & zellen)


def test_ac7_kuestenpunkt_bekommt_kreiswarnung_aber_nie_die_seezelle():
    """AC-7 (Wirkung am Punkt): GIVEN ein Wanderpunkt an der Kueste
    (Cuxhaven, Kreiszelle ``903352002``) UND der Feed fuehrt dort am
    Aufzeichnungstag die Kreis-Windwarnung #244 sowie die Seezellen-Warnung
    #246 (``501000004``, ohne ``expires``), WHEN die Warnungen ermittelt
    werden, THEN wird der Punkt seiner Kreiszelle zugeordnet (nie einer
    ``501``-Zelle), die Kreis-Warnung erscheint, die Seezellen-Warnung nicht."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import get_official_alerts_with_status, meteoalarm_feed
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    zone = meteoalarm_feed._zone_for_point_de(*CUXHAVEN)
    assert str(zone) == "903352002", f"Cuxhaven muss der Kreis-Kuestenzelle zugeordnet sein, war {zone}"

    _feed_vorbelegen("DE", _feed_de())
    with _nur_quellen(MeteoAlarmFeedSource("DE")):
        alerts, unavailable = get_official_alerts_with_status(*CUXHAVEN, now=TEST_NOW_KUESTE)

    assert any(a.hazard == "wind_gust" and a.level == 2 for a in alerts), (
        f"Kontrolle: die Kreis-Windwarnung #244 muss erscheinen, erhalten {alerts}"
    )
    assert not any("Elbe von Hamburg bis Cuxhaven" in (a.region_label or "") for a in alerts)
    assert all(a.valid_to is not None for a in alerts), (
        f"keine Warnung ohne Ablaufzeit (Seezelle) darf am Wanderpunkt erscheinen: {alerts}"
    )
    assert unavailable is False


# ───────────────────────────── AC-8 ──────────────────────────────────────────

_QUELLENVERMERK = (
    "Warngebiete: Deutscher Wetterdienst (DWD), CC BY 4.0; Copyright GeoBasis-DE / BKG "
    "(http://www.bkg.bund.de) 2019 (Daten modifiziert)"
)


def test_ac8_quellenvermerk_dwd_bkg_woertlich():
    # doc-compliance-test
    """AC-8: GIVEN die eingecheckte Quellenangabe fuer die deutschen
    Warngebiete (``src/services/official_alerts/data/README.md`` neben
    ``dwd_warngebiete_kreise.json``), WHEN sie eingesehen wird, THEN traegt
    sie den zweiteiligen Quellenvermerk WOERTLICH (Jahr 2019 laut
    Layer-Abstract, nicht das 2021 aus dem Feed-``LICENSE``-Feld)."""
    readme = _DATA_DIR / "README.md"
    assert readme.exists(), f"Quellenangabe fehlt: {readme}"
    text = readme.read_text(encoding="utf-8")
    assert "dwd_warngebiete_kreise.json" in text, "README muss die Geometriedatei benennen"
    assert _QUELLENVERMERK in text, "Quellenvermerk nicht woertlich enthalten"


# ───────────────────────────── AC-10 (Test 9) ────────────────────────────────

@pytest.fixture()
def premium_nutzer():
    """Echter Nutzer mit Tier ``premium`` (``user.json`` ueber
    ``app.loader.get_data_dir``, Vorbild ``test_alert_channel_resolution_parity.py``)
    -- sonst entfernen die Tier-Gates SMS/Premium-SMS fail-closed."""
    from app.loader import get_data_dir

    user_id = f"tdd-meteoalarm-de-{uuid.uuid4().hex[:8]}"
    pfad = get_data_dir(user_id)
    if pfad.exists():
        shutil.rmtree(pfad)
    pfad.mkdir(parents=True, exist_ok=True)
    (pfad / "user.json").write_text(json.dumps({"id": user_id, "tier": "premium"}))
    yield user_id
    if pfad.exists():
        shutil.rmtree(pfad)


_SCHWELLEN = {"sms": "MODERATE", "premium_sms": "MODERATE"}


def _abo(art: str):
    """Trip (``kind="route"``) bzw. Ortsvergleichs-Preset (``kind="vergleich"``)
    mit Empfaengern auf allen vier Kanaelen und identischen Kanal-Schwellen."""
    alle = {"email": True, "telegram": True, "sms": True, "premium_sms": True}
    if art == "vergleich":
        return {
            "id": "cmp-de", "name": "cmp-de", "user_id": "unused",
            "location_ids": ["loc-1"], "schedule": "daily", "weekday": 4,
            "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
            "empfaenger": [], "created_at": "2026-09-19T00:00:00Z",
            "send_telegram": True, "send_sms": True, "send_premium_sms": True,
            "alert_channels": dict(alle), "alert_channel_thresholds": dict(_SCHWELLEN),
        }
    from app.trip import Stage, Trip, Waypoint

    stage = Stage(
        id="S1", name="Etappe 1", date=date.today() + timedelta(days=1),
        waypoints=[
            Waypoint(id="W1", name="Garmisch", lat=GARMISCH[0], lon=GARMISCH[1],
                     elevation_m=700, arrival_calculated="08:00"),
            Waypoint(id="W2", name="Mittenwald", lat=47.4428, lon=11.2616,
                     elevation_m=900, arrival_calculated="12:00"),
        ],
    )
    return Trip(id="trip-de", name="Trip DE", stages=[stage],
                alert_channels=dict(alle), alert_channel_thresholds=dict(_SCHWELLEN))


def _kanaele_fuer(alert, abo, user_id: str) -> set:
    """Die geteilte Alarm-Kanal-Aufloesung, so wie sie ``trip_alert.py``
    (amtlicher Alarm) und ``compare_official_alert.py`` am Versand aufrufen:
    ``effective_alert_channels`` -> Dringlichkeit aus der amtlichen Stufe ->
    ``split_by_threshold`` -> tatsaechlich erlaubte Kanaele."""
    from services import alert_channel_threshold, alert_urgency
    from services.alert_channels import effective_alert_channels

    effective = effective_alert_channels(abo, None, user_id)
    dringlichkeit = alert_urgency.highest_urgency(alert_urgency.urgency_from_official_level(alert.level))
    schwellen = abo.get("alert_channel_thresholds") if isinstance(abo, dict) else abo.alert_channel_thresholds
    erlaubt, _unterdrueckt = alert_channel_threshold.split_by_threshold(effective, dringlichkeit, schwellen)
    return erlaubt


@pytest.mark.parametrize("art", ["route", "vergleich"])
def test_ac10_de_warnung_erreicht_dieselben_kanaele_wie_at_und_it(art, premium_nutzer):
    """AC-10: GIVEN orange amtliche Warnungen -- aus dem aufgezeichneten
    DE-Feed ueber ``MeteoAlarmFeedSource("DE")`` umgesetzt (Starkregen #108
    Garmisch, Gewitter #141 Landsberg), aus dem AT-Feed (Hitze Wien, AT901)
    und aus dem IT-Feed (Gewitter Rom, IT012) -- UND ein Trip bzw.
    Ortsvergleich mit Empfaengern auf allen vier Kanaelen, WHEN die geteilte
    Alarm-Kanal-Aufloesung fuer jede Warnung laeuft, THEN erreicht die
    DE-Warnung exakt dieselbe Kanalmenge wie die AT-/IT-Warnung gleicher
    Stufe (beim Gewitter auch gleicher Art), und diese Menge umfasst alle
    vier Kanaele.

    Die Paritaet selbst ist eine Invariante (die Aufloesung sieht weder Land
    noch Quelle); der RED-Grund ist die fehlende DE-Seite: ohne
    DE-Funktionalitaet entsteht aus dem Feed gar keine deutsche Warnung."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    _feed_vorbelegen("DE", _feed_de())
    _feed_vorbelegen("AT", _feed_at())
    _feed_vorbelegen("IT", _feed_it())
    _zamg_gemeinde(*WIEN, 90101, "Wien")

    at_orange = [a for a in MeteoAlarmFeedSource("AT").fetch(*WIEN) if a.level == 3]
    it_gewitter = [a for a in MeteoAlarmFeedSource("IT").fetch(*ROM)
                   if a.level == 3 and a.hazard == "thunderstorm"]
    assert at_orange, "Kontrolle: orange AT-Warnung (Wien) aus der AT-Stichprobe"
    assert it_gewitter, "Kontrolle: orange IT-Gewitterwarnung (Rom) aus der IT-Stichprobe"

    de = MeteoAlarmFeedSource("DE")
    de_regen = [a for a in de.fetch(*GARMISCH)
                if a.level == 3 and a.hazard == "rain" and a.valid_from == REGEN_108_VON]
    de_gewitter = [a for a in de.fetch(*LANDSBERG)
                   if a.level == 3 and a.hazard == "thunderstorm" and a.valid_from == GEWITTER_141_VON]
    assert de_regen, "orange DE-Starkregenwarnung #108 (Garmisch) muss aus dem Feed entstehen"
    assert de_gewitter, "orange DE-Gewitterwarnung #141 (Landsberg) muss aus dem Feed entstehen"

    abo = _abo(art)
    k_de_regen = _kanaele_fuer(de_regen[0], abo, premium_nutzer)
    k_at = _kanaele_fuer(at_orange[0], abo, premium_nutzer)
    k_de_gewitter = _kanaele_fuer(de_gewitter[0], abo, premium_nutzer)
    k_it = _kanaele_fuer(it_gewitter[0], abo, premium_nutzer)

    assert k_de_regen == k_at == _ALL_CHANNELS, (k_de_regen, k_at)
    assert k_de_gewitter == k_it == _ALL_CHANNELS, (k_de_gewitter, k_it)


# ───────────────────────────── AC-11 (Test 10) ───────────────────────────────

@pytest.mark.parametrize("reihenfolge", ["registriert", "umgekehrt"])
def test_ac11_grenzraum_garmisch_warnung_genau_einmal_unabhaengig_von_reihenfolge(reihenfolge):
    """AC-11: GIVEN Garmisch (Bayerische Alpen), fuer dessen Warnzelle der
    DE-Feed die aktive gelbe Gewitterwarnung #211 fuehrt, UND die
    oesterreichischen Quellen antworten regulaer "nicht zustaendig" (ZAMG
    404), WHEN die Warnungen ueber die ECHTE Registry ermittelt werden --
    einmal in der Registrierungsreihenfolge, einmal vollstaendig umgekehrt --
    THEN erscheint #211 genau einmal, mit deutscher Herkunft (Kreis
    Garmisch-Partenkirchen), und ``unavailable=False``."""
    _assert_pruefling_aus_diesem_baum()
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_with_status

    assert len(_de_quellen_in_registry()) == 1, "MeteoAlarmFeedSource('DE') muss registriert sein"
    _zamg_nicht_zustaendig(*GARMISCH)
    _feed_vorbelegen("DE", _feed_de())

    quellen = list(oa_base._REGISTERED_SOURCES)
    if reihenfolge == "umgekehrt":
        quellen = list(reversed(quellen))
    with _nur_quellen(*quellen):
        alerts, unavailable = get_official_alerts_with_status(*GARMISCH, now=TEST_NOW_BAYERN)

    treffer = [a for a in alerts
               if a.hazard == "thunderstorm" and a.level == 2
               and a.valid_from == GEWITTER_211_VON and a.valid_to == GEWITTER_211_BIS]
    assert len(treffer) == 1, f"#211 muss genau einmal erscheinen, erhalten {alerts}"
    assert treffer[0].source == "meteoalarm"
    assert treffer[0].region_label == "Kreis Garmisch-Partenkirchen", treffer[0]
    assert unavailable is False


# ─────────── Fix-Runde Adversary: F003 Enklave, F002 Suedtirol ───────────────

BADEN_BADEN = (48.7606, 8.2398)  # 108211000 Stadt Baden-Baden -- Loch im Kreis Rastatt
RASTATT = (48.8580, 8.2030)      # 108216000 Kreis Rastatt, ausserhalb des Lochs
BOZEN = (46.4983, 11.3548)       # Suedtirol: GeoSphere-Bbox ja, ZAMG 404; IT-Feed zustaendig


@pytest.mark.parametrize("reihenfolge", ["datei", "umgekehrt"])
def test_f003_enklave_baden_baden_gehoert_nicht_zum_umschliessenden_kreis_rastatt(monkeypatch, reihenfolge):
    """F003 (Adversary, Even-Odd): GIVEN die echte DWD-Kreisgeometrie, in der
    der Kreis Rastatt die Stadt Baden-Baden als Innenring (Loch) umschliesst,
    WHEN ein Punkt in Baden-Baden bzw. im Kreis Rastatt ausserhalb des Lochs
    zugeordnet wird -- in Dateireihenfolge UND in umgekehrter Reihenfolge der
    Kreise --, THEN liefert Baden-Baden ``108211000`` und Rastatt
    ``108216000``. Die Zuordnung darf nicht von der Reihenfolge abhaengen: in
    Dateireihenfolge steht Baden-Baden zufaellig VOR Rastatt und verdeckt
    einen Fehler im Lochtest; erst umgekehrt wird der Innenring wirksam
    geprueft. Echte Geometrie, nur die Liste wird umsortiert."""
    from services.official_alerts import dwd_zones

    if reihenfolge == "umgekehrt":
        monkeypatch.setattr(dwd_zones, "_ZONES", list(reversed(dwd_zones._ZONES)))
    assert dwd_zones.warncell_at(*BADEN_BADEN) == "108211000"
    assert dwd_zones.warncell_at(*RASTATT) == "108216000"


@pytest.mark.parametrize("it_feed_ok, erwartet", [(False, True), (True, False)],
                         ids=["it_ausfall", "it_ok"])
def test_f002_suedtirol_zamg_404_kompensiert_it_ausfall_nicht(it_feed_ok, erwartet):
    """F002 (Tech-Lead-Entscheid, gleiches Prinzip wie AC-3): GIVEN Bozen,
    registriert nur GeoSphereWarnSource + MeteoAlarmFeedSource("IT"), ZAMG
    antwortet "nicht zustaendig" (404), WHEN der IT-Feed ausgefallen ist, THEN
    ``unavailable=True`` -- die nicht zustaendige ZAMG kompensiert den Ausfall
    der einzig zustaendigen italienischen Quelle nicht. Kontrolle: IT-Feed ok
    -> ``unavailable=False``."""
    from services.official_alerts import get_official_alerts_with_status
    from services.official_alerts.geosphere_warn import GeoSphereWarnSource
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    geo, it = GeoSphereWarnSource(), MeteoAlarmFeedSource("IT")
    assert geo.covers(*BOZEN) is True and it.covers(*BOZEN) is True, "Vorbedingung: beide Vorfilter sagen zustaendig"
    _zamg_nicht_zustaendig(*BOZEN)
    _feed_vorbelegen("IT", _feed_it() if it_feed_ok else None)

    with _nur_quellen(geo, it):
        _alerts, unavailable = get_official_alerts_with_status(*BOZEN, now=TEST_NOW_BAYERN)

    assert unavailable is erwartet
