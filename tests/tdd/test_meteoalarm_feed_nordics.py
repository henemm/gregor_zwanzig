"""TDD RED -- MeteoAlarm Skandinavien: Norwegen, Schweden, Finnland aus dem kontingentfreien
Feed (Issue #1442, Scheibe S2).

SPEC: docs/specs/modules/feat_1442_s2_meteoalarm_nordics.md ("## Acceptance Criteria", AC-1 bis
AC-13; Test Plan Test 1-14)

AC -> Testfunktion (AC-13 / Test 14 Live: eigene Datei ``test_meteoalarm_feed_nordics_live.py``):

- AC-1  (Test 1)  ``test_ac1_feedpfade_und_registrierung_no_se``,
                  ``test_ac1_punkt_im_gewarnten_gebiet_liefert_warnung_mit_stufe_art_zeitraum``
- AC-2  (Test 2)  ``test_ac2_punkt_ohne_treffer_polygon_leer_ohne_ausfallhinweis``,
                  ``test_ac2_leerer_feed_ist_keine_warnung_ohne_ausfall``
- AC-3  (Test 3)  ``test_ac3_feed_ausfall_meldet_nicht_abrufbar``,
                  ``test_ac3_feed_ohne_verwertbaren_eintrag_meldet_nicht_abrufbar``
- AC-4  (Test 4)  ``test_ac4_rand_und_kuestenpunkte_sind_zustaendig``,
                  ``test_ac4_nachbarland_punkte_nicht_zustaendig_ohne_ausfallhinweis``,
                  ``test_ac4_fallback_punkt_im_gecachten_feed_polygon_ist_zustaendig``
- AC-5  (Test 5)  ``test_ac5_cancel_nimmt_die_warnung_zurueck``,
                  ``test_ac5_update_ersetzt_die_vorgaengerwarnung_genau_einmal``
- AC-6  (Test 6)  ``test_ac6_hoehenband_wird_ignoriert``, ``test_loch_im_polygon_ist_keine_warnung``
- AC-7  (Test 7)  ``test_ac7_text_stammt_aus_en_gb_nicht_aus_landessprache``
- AC-8  (Test 8)  ``test_ac8_andersfoermiger_eintrag_faerbt_andere_orte_nicht_als_ausfall``
- AC-9  (Test 9)  ``test_ac9_grenzpunkt_norwegen_schweden_keine_doppelte_warnung``
- AC-10 (Test 13) ``test_ac10_bestehende_laenderpfade_unveraendert`` (Regressions-Golden-Master;
                  darf schon jetzt GRUEN sein -- zusaetzlich laufen die S1-CH- und IT/AT/DE-
                  Testdateien unveraendert)
- AC-11 (Test 10) ``test_ac11_warnung_erreicht_dieselben_kanaele_wie_at``
- AC-12 (Test 11/12) Abschnitt "Teil B Finnland" (``test_ac12_*``): fallen mit der Registrierung weg,
                  wenn die FI-Zonengeometrie nicht belegbar zugeordnet werden kann (AC-12, 2. Satz)
- AC-13 (Test 14) Live-Datei.

RED-Ursachen (bewusst, fachlich): ``_FEED_PATHS`` kennt weder NO noch SE noch FI, ``covers()`` und
``fetch()`` fallen fuer diese Laender in den italienischen/Geocode-Zweig bzw. melden
``point_unmapped``; die Registrierungen fehlen. Jeder Test, der sonst "zufaellig" gruen waere (leere
Liste bei nicht zustaendiger Quelle), traegt eine Positivkontrolle (``covers(...) is True``).

Kein Mock-Theater, kein Netz (Kern-Schicht, laeuft mit ``--disable-socket``): der Modul-Cache wird
mit dem ECHTEN aufgezeichneten Feed vorbelegt, ``fetch()`` laeuft ueber den echten Cache-Treffer-
Zweig von ``warn_egress.cached_fetch()``.

Fixtures (``tests/fixtures/meteoalarm_feed/``): ``feed_norway_sample.json``,
``feed_sweden_sample.json``, ``feed_finland_sample.json`` -- reale, unveraenderte Eintraege aus dem
Vollabruf vom 2026-10-30 plus SYNTHETISCHE Eintraege (Kennung ``.SYNTH-*``; Herkunft und Auswahl:
README.md im selben Verzeichnis). Die Schweden-Aufzeichnung fuehrte am Aufzeichnungstag nur
gruene (Stufe-1-) Eintraege -- die aktiven Schweden-Warnungen sind deshalb synthetisch aus echten
Eintraegen abgeleitet.
"""
from __future__ import annotations

import copy
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Geteilte Helfer aus der S1-Testdatei (eine Quelle, kein Duplikat): Registry-Isolation, Nutzer-
# und Abo-Fixtures, Kanal-Aufloesung. ``premium_nutzer`` ist ein pytest-Fixture und muss im
# Namensraum dieser Datei stehen.
from tests.tdd.test_meteoalarm_feed_ch import (  # noqa: F401
    WIEN, _ALL_CHANNELS, _abo, _feed_at, _kanaele_fuer, _nur_quellen, _zamg_gemeinde,
    premium_nutzer,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "meteoalarm_feed"

# ── Punkte (per Ray-Cast gegen die aufgezeichneten Feeds 2026-10-30 geprueft) ────────────────
OSLO = (59.91, 10.75)             # NO: Flomfare gelb (Ostland, 2 Ringe)
ORANGE_NO = (58.8, 9.4)           # NO: Flomfare ORANGE (Ostland), ausserhalb des gelben Polygons
BERGEN = (60.39, 5.32)            # NO: Hoeh vannstand gelb + SYNTH-UPDATE (orange)
STAVANGER = (58.97, 5.73)         # NO: Hoeh vannstand gelb
BODOE = (67.28, 14.40)            # NO: Kuling gelb
LOFOTEN = (68.20, 13.60)          # NO: Kuling gelb (Skomvær-Melbu), Hoehenband 0-900 m; SYNTH-CANCEL
TROMSOE = (69.65, 18.96)          # NO: im Fixture ohne Treffer-Polygon
LOCH_AUSSEN = (61.85, 9.10)       # NO: synthetisches Lochgebiet, Aussenring
LOCH_INNEN = (62.00, 9.40)        # NO: synthetisches Lochgebiet, Innenring (= Loch)

STOCKHOLM = (59.33, 18.07)        # SE: SYNTH-GUL (Wind gelb)
KARLSTAD = (59.38, 13.50)         # SE: SYNTH-ORANGE (Wind orange)
MALMOE = (55.60, 13.00)           # SE: im Fixture nur gruen (AllClear) -> keine aktive Warnung
SE_GRENZE = (59.00, 12.50)        # SE: im SYNTH-ORANGE-Polygon, knapp an der Landesgrenze zu NO

HALDEN = (59.12, 11.39)           # NO-Grenzstadt zu SE

VAASA = (63.10, 21.62)            # FI029 Pohjanmaa
TURKU = (60.45, 22.27)            # FI032 Varsinais-Suomi
MARIEHAMN = (60.10, 19.94)        # FI043 Ahvenanmaa
HANKO_SEE = (59.70, 23.00)        # FI806 Suomenlahden länsiosa (Seegebiet vor Hanko)
HELSINKI = (60.17, 24.94)

# Referenzzeitpunkte (UTC) -- innerhalb der Gueltigkeit der jeweiligen Fixture-Eintraege.
NOW_NO_OSLO = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)      # Flomfare 24./25.-26.10.
NOW_NO_LOFOTEN = datetime(2026, 10, 25, 20, 0, tzinfo=timezone.utc)   # Kuling 25.10. 18:00-02:00
NOW_NO_BERGEN = datetime(2026, 10, 26, 8, 0, tzinfo=timezone.utc)     # Hoeh vannstand 26.10. 06-12
NOW_SE = datetime(2026, 10, 25, 9, 0, tzinfo=timezone.utc)            # SYNTH-GUL/-ORANGE 25.10.
NOW_FI_LAND1 = datetime(2026, 10, 27, 20, 0, tzinfo=timezone.utc)     # FI032/FI029 (Update)
NOW_FI_LAND2 = datetime(2026, 10, 27, 23, 0, tzinfo=timezone.utc)     # FI043/FI029 (Alert)
NOW_FI_SEE = datetime(2026, 10, 26, 1, 0, tzinfo=timezone.utc)        # FI806 Sturmwarnung

_FEEDS = {"NO": "feed_norway_sample.json", "SE": "feed_sweden_sample.json",
          "FI": "feed_finland_sample.json"}
_PFADE = {"NO": "/api/v1/warnings/feeds-norway", "SE": "/api/v1/warnings/feeds-sweden",
          "FI": "/api/v1/warnings/feeds-finland"}


# ───────────────────────────── Helfer ────────────────────────────────────────

def _assert_pruefling_aus_diesem_baum() -> None:
    """#1409: der importierte Pruefling MUSS aus dem Baum DIESER Testdatei stammen."""
    from services.official_alerts import meteoalarm_feed

    modul = Path(meteoalarm_feed.__file__).resolve()
    assert str(modul).startswith(str(_REPO_ROOT)), (
        f"Pruefling {modul} liegt ausserhalb von {_REPO_ROOT}"
    )


@pytest.fixture(autouse=True)
def _caches_leeren():
    from services.official_alerts import geosphere_warn, meteoalarm_feed

    geosphere_warn._cache.clear()
    meteoalarm_feed._cache.clear()
    yield
    geosphere_warn._cache.clear()
    meteoalarm_feed._cache.clear()


def _feed(land: str) -> dict:
    return json.loads((_FIXTURES / _FEEDS[land]).read_text(encoding="utf-8"))


def _ohne_eintrag(feed: dict, suffix: str) -> dict:
    """Kopie des Feeds ohne den Eintrag, dessen Kennung auf ``suffix`` endet."""
    kopie = copy.deepcopy(feed)
    vorher = len(kopie["warnings"])
    kopie["warnings"] = [w for w in kopie["warnings"] if not w["alert"]["identifier"].endswith(suffix)]
    assert len(kopie["warnings"]) == vorher - 1, f"Fixture-Eintrag *{suffix} nicht eindeutig"
    return kopie


def _eintrag(feed: dict, suffix: str) -> dict:
    treffer = [w for w in feed["warnings"] if w["alert"]["identifier"].endswith(suffix)]
    assert len(treffer) == 1, f"Fixture-Eintrag *{suffix} nicht eindeutig"
    return treffer[0]["alert"]


def _infos(alert: dict) -> list:
    info = alert["info"]
    return info if isinstance(info, list) else [info]


def _zeitraum(feed: dict, suffix: str) -> "tuple[datetime, datetime]":
    """Gueltigkeit (onset, expires) des Eintrags laut Fixture -- UTC."""
    info = _infos(_eintrag(feed, suffix))[0]
    von = datetime.fromisoformat(info["onset"].replace("Z", "+00:00")).astimezone(timezone.utc)
    bis = datetime.fromisoformat(info["expires"].replace("Z", "+00:00")).astimezone(timezone.utc)
    return von, bis


def _feed_vorbelegen(land: str, daten: "dict | None") -> None:
    from services.official_alerts import meteoalarm_feed, warn_egress

    meteoalarm_feed._cache[land] = {
        "data": daten,
        "fetched_at": time.monotonic(),
        "ttl": warn_egress.WARN_SUCCESS_TTL if daten is not None else warn_egress.WARN_FAILURE_TTL,
    }


def _quelle(land: str):
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    return MeteoAlarmFeedSource(land)


def _abruf(land: str, punkt, now, feed="__fixture__"):
    """Registry-Abruf nur ueber die Quelle des Landes (Feed-Cache vorbelegt)."""
    from services.official_alerts import get_official_alerts_with_status

    _feed_vorbelegen(land, _feed(land) if feed == "__fixture__" else feed)
    with _nur_quellen(_quelle(land)):
        return get_official_alerts_with_status(*punkt, now=now)


def _quellen_in_registry(land: str) -> list:
    import services.official_alerts.base as oa_base
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    return [s for s in oa_base._REGISTERED_SOURCES
            if isinstance(s, MeteoAlarmFeedSource) and getattr(s, "country", None) == land]


# ───────────────────────────── AC-1 (Test 1) ─────────────────────────────────

def test_ac1_feedpfade_und_registrierung_no_se():
    """AC-1 (Infrastruktur): GIVEN die Quellen NO/SE, WHEN Feedpfad und Registry abgefragt werden,
    THEN zeigen die Pfade auf ``feeds-norway``/``feeds-sweden`` UND je genau EINE
    ``MeteoAlarmFeedSource`` ist registriert."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    for land in ("NO", "SE"):
        assert meteoalarm_feed._FEED_PATHS[land] == _PFADE[land]
        assert len(_quellen_in_registry(land)) == 1, f"MeteoAlarmFeedSource('{land}') nicht registriert"


@pytest.mark.parametrize("land,name,punkt,now,suffix,hazard,level,label", [
    ("NO", "oslo", OSLO, NOW_NO_OSLO, "261025105157.584959", "flood", 2,
     None),
    ("NO", "orange", ORANGE_NO, NOW_NO_OSLO, "261025105157.584960", "flood", 3, None),
    ("NO", "stavanger", STAVANGER, NOW_NO_BERGEN, "073333.057", None, 2, None),
    ("NO", "bodoe", BODOE, NOW_NO_LOFOTEN, "072757.041", "wind_gust", 2, None),
    ("SE", "stockholm", STOCKHOLM, NOW_SE, "110179.SYNTH-GUL", "wind_gust", 2, None),
    ("SE", "karlstad", KARLSTAD, NOW_SE, "110147.SYNTH-ORANGE", "wind_gust", 3, None),
])
def test_ac1_punkt_im_gewarnten_gebiet_liefert_warnung_mit_stufe_art_zeitraum(
        land, name, punkt, now, suffix, hazard, level, label):
    """AC-1: GIVEN ein Punkt in einem Gebiet mit aktiver Warnung (aufgezeichnet bzw. aus einem
    echten Eintrag abgeleitet), WHEN die amtlichen Warnungen ermittelt werden, THEN erscheint genau
    diese Warnung mit Stufe, Ereignisart und Gueltigkeitszeitraum, ohne Ausfallhinweis.

    Wichtig fuer die Umsetzung: ``areaDesc`` unterscheidet sich zwischen den Sprachbloecken (NO:
    "Skomvær"/"Skomvaer", SE: schwedisch/englisch). Die Gruppierung im CAP-Mapper darf deshalb NICHT
    am Gebietstext haengen, sonst kaeme dieselbe Warnung je Sprache einmal -- "genau EINE" faengt das."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle(land).covers(*punkt) is True, f"{land}-Quelle muss hier zustaendig sein"
    alerts, unavailable = _abruf(land, punkt, now)

    assert len(alerts) == 1, f"genau EINE Warnung erwartet, erhalten {alerts}"
    a = alerts[0]
    von, bis = _zeitraum(_feed(land), suffix)
    assert a.level == level and a.source == "meteoalarm"
    if hazard:
        assert a.hazard == hazard, a
    assert a.label, "Ereignisbezeichnung darf nicht leer sein"
    assert a.valid_from == von and a.valid_to == bis, (a, von, bis)
    assert a.region_label, "Gebietsbezeichnung darf nicht leer sein"
    assert unavailable is False


# ───────────────────────────── AC-2 (Test 2) ─────────────────────────────────

@pytest.mark.parametrize("land,punkt,now", [
    ("NO", TROMSOE, NOW_NO_OSLO),
    ("SE", MALMOE, NOW_SE),
])
def test_ac2_punkt_ohne_treffer_polygon_leer_ohne_ausfallhinweis(land, punkt, now):
    """AC-2: GIVEN ein Punkt im Land ohne aktive Warnung, WHEN die Warnungen ermittelt werden, THEN
    leere Liste UND ``unavailable=False`` -- weil die Quelle zustaendig ist und erfolgreich "keine
    Warnung" sagt, nicht weil sie schweigt."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle(land).covers(*punkt) is True
    alerts, unavailable = _abruf(land, punkt, now)
    assert alerts == []
    assert unavailable is False


@pytest.mark.parametrize("land,punkt", [("NO", OSLO), ("SE", STOCKHOLM)])
def test_ac2_leerer_feed_ist_keine_warnung_ohne_ausfall(land, punkt):
    """AC-2: ein erfolgreich abgerufener, aber leerer Feed ist "keine Warnung", kein Ausfall."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle(land).covers(*punkt) is True
    alerts, unavailable = _abruf(land, punkt, NOW_SE, feed={"warnings": []})
    assert alerts == []
    assert unavailable is False


# ───────────────────────────── AC-3 (Test 3) ─────────────────────────────────

@pytest.mark.parametrize("land,punkt", [("NO", OSLO), ("SE", STOCKHOLM)])
def test_ac3_feed_ausfall_meldet_nicht_abrufbar(land, punkt):
    """AC-3: GIVEN der Feed-Abruf ist gescheitert, WHEN die Warnungen fuer einen Punkt im Land
    ermittelt werden, THEN ``unavailable=True`` statt einer scheinbar warnungsfreien Lage."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle(land).covers(*punkt) is True
    alerts, unavailable = _abruf(land, punkt, NOW_SE, feed=None)
    assert alerts == []
    assert unavailable is True


def _alle_areas(feed: dict):
    for w in feed["warnings"]:
        for info in _infos(w["alert"]) if w["alert"].get("info") else []:
            ar = info.get("area") or []
            yield from (ar if isinstance(ar, list) else [ar])


def _ohne_info(feed: dict) -> None:
    for w in feed["warnings"]:
        w["alert"].pop("info", None)


def _polygon_umbenennen(feed: dict) -> None:
    for area in _alle_areas(feed):
        area["flaeche"] = area.pop("polygon", None)


def _polygone_unlesbar(feed: dict) -> None:
    for area in _alle_areas(feed):
        area["polygon"] = ["nicht,lesbar x,y"]


@pytest.mark.parametrize("land,punkt", [("NO", OSLO), ("SE", STOCKHOLM)])
@pytest.mark.parametrize("verderben", [_ohne_info, _polygon_umbenennen, _polygone_unlesbar])
def test_ac3_feed_ohne_verwertbaren_eintrag_meldet_nicht_abrufbar(land, punkt, verderben):
    """AC-3: ein Feed ohne einen einzigen verwertbaren Eintrag ist ein Ausfall, kein Freispruch."""
    _assert_pruefling_aus_diesem_baum()
    feed = _feed(land)
    verderben(feed)
    assert _quelle(land).covers(*punkt) is True
    alerts, unavailable = _abruf(land, punkt, NOW_SE, feed=feed)
    assert alerts == []
    assert unavailable is True


# ───────────────────────────── AC-4 (Test 4) ─────────────────────────────────

NO_RAND_PUNKTE = {
    "Kirkenes": (69.73, 30.05), "Tromsoe": TROMSOE, "Svolvaer": (68.23, 14.57), "Oslo": OSLO,
    "Bergen": BERGEN, "Stavanger": STAVANGER, "Kristiansand": (58.15, 8.00),
    "Trondheim": (63.43, 10.40), "Bodoe": BODOE, "Hammerfest": (70.66, 23.68),
    "Halden": HALDEN, "Lindesnes": (58.00, 7.05), "Roeros": (62.57, 11.38), "Alta": (69.97, 23.27),
}
SE_RAND_PUNKTE = {
    "Kiruna": (67.86, 20.23), "Malmoe": MALMOE, "Haparanda": (65.83, 24.14), "Stockholm": STOCKHOLM,
    "Goeteborg": (57.70, 11.97), "Ystad": (55.43, 13.82), "Kalmar": (56.66, 16.36),
    "Visby": (57.64, 18.30), "Karesuando": (68.44, 22.48), "Stroemstad": (58.94, 11.17),
    "Treriksroeset": (69.06, 20.55), "Are": (63.40, 13.08), "Lulea": (65.58, 22.15),
    "Trelleborg": (55.38, 13.16),
}
NACHBAR_PUNKTE = {
    "Kopenhagen": (55.68, 12.57), "Flensburg": (54.78, 9.44), "Tallinn": (59.44, 24.75),
    "Murmansk": (68.97, 33.08), "Berlin": (52.52, 13.40), "Wien": WIEN,
}


@pytest.mark.parametrize("land,punkte", [("NO", NO_RAND_PUNKTE), ("SE", SE_RAND_PUNKTE)])
def test_ac4_rand_und_kuestenpunkte_sind_zustaendig(land, punkte):
    """AC-4 (Messung): GIVEN >=12 Rand-/Kuestenpunkte des Landes, WHEN die Zustaendigkeit geprueft
    wird, THEN ist die Landesquelle ueberall zustaendig -- ein Falsch-Nein waere stilles Schweigen."""
    _assert_pruefling_aus_diesem_baum()
    assert len(punkte) >= 12
    quelle = _quelle(land)
    daneben = [n for n, p in punkte.items() if quelle.covers(*p) is not True]
    assert daneben == [], f"{land}-Quelle nicht zustaendig fuer: {daneben}"


@pytest.mark.parametrize("land", ["NO", "SE"])
def test_ac4_nachbarland_punkte_nicht_zustaendig_ohne_ausfallhinweis(land):
    """AC-4: GIVEN Punkte in Nachbarlaendern, WHEN die Quelle gefragt wird, THEN ist sie nicht
    zustaendig und schweigt folgenlos: keine Warnung, KEIN Ausfallhinweis -- auch bei defektem
    Feed (die Quelle darf gar nicht erst abrufen)."""
    _assert_pruefling_aus_diesem_baum()
    # Positivkontrolle: dieselbe Quelle ist im eigenen Land zustaendig.
    assert _quelle(land).covers(*(OSLO if land == "NO" else STOCKHOLM)) is True
    quelle = _quelle(land)
    for name, punkt in NACHBAR_PUNKTE.items():
        assert quelle.covers(*punkt) is False, f"{land}-Quelle darf {name} nicht beanspruchen"
        alerts, unavailable = _abruf(land, punkt, NOW_SE, feed=None)
        assert alerts == [] and unavailable is False, (name, alerts, unavailable)


def test_ac4_fallback_punkt_im_gecachten_feed_polygon_ist_zustaendig():
    """AC-4 (Spec Impl. 3): GIVEN ein Feed-Polygon weit draussen auf See (synthetisch, ausserhalb
    jedes Landesumrisses), WHEN der Feed gecacht ist, THEN ist die Quelle fuer einen Punkt darin
    zustaendig und liefert die Warnung; ohne diesen Eintrag ist derselbe Punkt NICHT zustaendig."""
    _assert_pruefling_aus_diesem_baum()
    see_punkt = (75.0, 5.0)  # Norwegische See nordwestlich von Spitzbergen-Naehe, weit vor der Kueste
    feed = _feed("NO")
    eintrag = copy.deepcopy(_eintrag_komplett(feed, "261025105157.584959"))
    eintrag["alert"]["identifier"] += ".SYNTH-SEE"
    for info in _infos(eintrag["alert"]):
        info["area"] = [{"areaDesc": "Synthetische Hochsee",
                         "polygon": ["74.5,4.0 74.5,6.0 75.5,6.0 75.5,4.0 74.5,4.0"]}]
    feed["warnings"].append(eintrag)

    _feed_vorbelegen("NO", _feed("NO"))
    assert _quelle("NO").covers(*see_punkt) is False, "Kontrolle: ohne Feed-Polygon nicht zustaendig"
    _feed_vorbelegen("NO", feed)
    assert _quelle("NO").covers(*see_punkt) is True
    alerts, unavailable = _abruf("NO", see_punkt, NOW_NO_OSLO, feed=feed)
    assert len(alerts) == 1 and unavailable is False


def _eintrag_komplett(feed: dict, suffix: str) -> dict:
    treffer = [w for w in feed["warnings"] if w["alert"]["identifier"].endswith(suffix)]
    assert len(treffer) == 1
    return treffer[0]


# ───────────────────────────── AC-5 (Test 5) ─────────────────────────────────

def test_ac5_cancel_nimmt_die_warnung_zurueck():
    """AC-5: GIVEN eine Kuling-Warnung (Lofoten) und ein ``Cancel``, der sie per ``references``
    aufhebt, WHEN die Warnungen ermittelt werden, THEN erscheint sie nicht als aktiv. Kontrolle:
    ohne den Cancel ist sie da."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle("NO").covers(*LOFOTEN) is True
    ohne_cancel = _ohne_eintrag(_feed("NO"), ".SYNTH-CANCEL")
    alerts, _ = _abruf("NO", LOFOTEN, NOW_NO_LOFOTEN, feed=ohne_cancel)
    assert len(alerts) == 1, f"Kontrolle: ohne Cancel genau eine Warnung, erhalten {alerts}"

    alerts, unavailable = _abruf("NO", LOFOTEN, NOW_NO_LOFOTEN)
    assert alerts == [], f"Cancel muss die Warnung zurueckgenommen haben: {alerts}"
    assert unavailable is False


def test_ac5_update_ersetzt_die_vorgaengerwarnung_genau_einmal():
    """AC-5: GIVEN eine gelbe Hoehenwasser-Warnung (Bergen) und ein ``Update`` (orange), das sie
    per ``references`` ersetzt, WHEN die Warnungen ermittelt werden, THEN erscheint genau EINE
    Warnung, orange -- die gelbe Vorgaengerin ist ersetzt, nicht zusaetzlich da."""
    _assert_pruefling_aus_diesem_baum()
    alerts, unavailable = _abruf("NO", BERGEN, NOW_NO_BERGEN)
    assert len(alerts) == 1, f"genau eine Warnung erwartet: {alerts}"
    assert alerts[0].level == 3
    assert unavailable is False


# ───────────────────────────── AC-6 (Test 6) ─────────────────────────────────

def test_ac6_hoehenband_wird_ignoriert():
    """AC-6: GIVEN eine Warnung mit Hoehenband (``altitude`` 0 / ``ceiling`` 900 m, aufgezeichnet),
    WHEN ein Punkt im Gebiet abgefragt wird, THEN wird sie ausgegeben -- unabhaengig von der Hoehe
    des Punkts (bewusst wie IT/AT/DE/CH)."""
    _assert_pruefling_aus_diesem_baum()
    feed = _feed("NO")
    bandgebiete = [a for a in _alle_areas(feed) if a.get("ceiling") is not None
                   and a.get("areaDesc") == "Skomvær - Melbu"]
    assert bandgebiete, "Aufbau: Fixture muss das Hoehenband-Gebiet tragen"
    alerts, _ = _abruf("NO", LOFOTEN, NOW_NO_LOFOTEN, feed=_ohne_eintrag(feed, ".SYNTH-CANCEL"))
    assert len(alerts) == 1


def test_loch_im_polygon_ist_keine_warnung():
    """Mehrfachring (Spec Impl. 2): Punkt im Aussenring -> Warnung; Punkt im Innenring (Loch) -> keine."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle("NO").covers(*LOCH_AUSSEN) is True
    aussen, _ = _abruf("NO", LOCH_AUSSEN, NOW_NO_OSLO)
    assert len(aussen) == 1, f"Aussenring muss warnen: {aussen}"
    innen, unavailable = _abruf("NO", LOCH_INNEN, NOW_NO_OSLO)
    assert innen == [] and unavailable is False


# ───────────────────────────── AC-7 (Test 7) ─────────────────────────────────

@pytest.mark.parametrize("land,punkt,now,suffix,landessprache", [
    ("NO", OSLO, NOW_NO_OSLO, "261025105157.584959", "no"),
    ("SE", STOCKHOLM, NOW_SE, "110179.SYNTH-GUL", "sv-SE"),
])
def test_ac7_text_stammt_aus_en_gb_nicht_aus_landessprache(land, punkt, now, suffix, landessprache):
    """AC-7: GIVEN Feed-Texte in Landessprache und ``en-GB`` (kein ``de``), WHEN die Warnung
    ausgegeben wird, THEN ist ihr Text vorhanden und stammt aus ``en-GB``."""
    _assert_pruefling_aus_diesem_baum()
    infos = _infos(_eintrag(_feed(land), suffix))
    sprachen = {i["language"]: i for i in infos}
    assert set(sprachen) == {landessprache, "en-GB"}, "Aufbau: keine de-Sprache im Fixture"
    erwartet = sprachen["en-GB"]["event"]
    assert erwartet, "Aufbau: en-GB-Text fehlt"
    if landessprache != "sv-SE":  # SMHI nennt "Wind" in beiden Sprachen -- dort nur Vorhandensein
        assert erwartet != sprachen[landessprache]["event"], (
            "Aufbau: en-GB- und Landessprachen-Text muessen unterscheidbar sein")

    alerts, _ = _abruf(land, punkt, now)
    assert len(alerts) == 1
    assert alerts[0].label == erwartet, (alerts[0].label, erwartet)


# ───────────────────────────── AC-8 (Test 8) ─────────────────────────────────

@pytest.mark.parametrize("land,punkt,now", [
    ("NO", OSLO, NOW_NO_OSLO),
])
def test_ac8_andersfoermiger_eintrag_faerbt_andere_orte_nicht_als_ausfall(land, punkt, now):
    """AC-8: GIVEN ein Eintrag (``.SYNTH-KAPUTT``, steht an erster Stelle) mit unlesbarem Polygon,
    WHEN ein Punkt mit korrekter Warnung abgefragt wird, THEN erhaelt er seine Warnung und KEINEN
    Ausfallhinweis."""
    _assert_pruefling_aus_diesem_baum()
    feed = _feed(land)
    assert feed["warnings"][0]["alert"]["identifier"].endswith(".SYNTH-KAPUTT")
    assert _quelle(land).covers(*punkt) is True
    alerts, unavailable = _abruf(land, punkt, now)
    assert len(alerts) == 1 and alerts[0].level == 2, alerts
    assert unavailable is False


def test_ac8_eintrag_ohne_info_und_nicht_objekt_faerbt_nicht_als_ausfall():
    """AC-8: ein Eintrag ohne ``info`` und ein Nicht-Objekt im Feed duerfen den gesunden Rest nicht
    zum Ausfall machen."""
    _assert_pruefling_aus_diesem_baum()
    feed = _feed("NO")
    ohne_info = copy.deepcopy(feed["warnings"][1])
    ohne_info["alert"]["identifier"] += ".SYNTH-OHNE-INFO"
    ohne_info["alert"].pop("info")
    feed["warnings"] = [ohne_info, "kein-objekt"] + feed["warnings"]
    alerts, unavailable = _abruf("NO", OSLO, NOW_NO_OSLO, feed=feed)
    assert len(alerts) == 1 and unavailable is False


# ───────────────────────────── AC-9 (Test 9) ─────────────────────────────────

def test_ac9_grenzpunkt_norwegen_schweden_keine_doppelte_warnung():
    """AC-9: GIVEN beide Landesquellen sind registriert, WHEN ein Punkt an der NO/SE-Grenze
    abgefragt wird, in dessen Polygon nur Schweden warnt, THEN erscheint genau diese Warnung
    EINMAL -- ohne Doppel-Chip, auch wenn beide Quellen zustaendig sind."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import get_official_alerts_with_status

    for land in ("NO", "SE"):
        _feed_vorbelegen(land, _feed(land))
    assert _quelle("SE").covers(*SE_GRENZE) is True
    with _nur_quellen(_quelle("NO"), _quelle("SE")):
        alerts, unavailable = get_official_alerts_with_status(*SE_GRENZE, now=NOW_SE)
        halden, halden_unavailable = get_official_alerts_with_status(*HALDEN, now=NOW_SE)

    assert len(alerts) == 1, f"genau EINE Warnung ohne Doppel erwartet: {alerts}"
    assert alerts[0].level == 3 and unavailable is False
    # Grenzstadt auf norwegischer Seite: nichts aus dem schwedischen Polygon, nichts doppelt.
    identitaeten = [(a.hazard, a.level, a.valid_from, a.region_label) for a in halden]
    assert len(identitaeten) == len(set(identitaeten)) and halden_unavailable is False


# ───────────────────────────── AC-10 (Test 13) ───────────────────────────────

def test_ac10_bestehende_laenderpfade_unveraendert():
    """AC-10 (Regression, darf schon jetzt GRUEN sein): IT/AT/DE/CH-Pfade und -Geocode-Namen bleiben
    unveraendert, die CH-Quelle bleibt registriert."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    assert meteoalarm_feed._FEED_PATHS["IT"] == "/api/v1/warnings/feeds-italy"
    assert meteoalarm_feed._FEED_PATHS["AT"] == "/api/v1/warnings/feeds-austria"
    assert meteoalarm_feed._FEED_PATHS["DE"] == "/api/v1/warnings/feeds-germany"
    assert meteoalarm_feed._FEED_PATHS["CH"] == "/api/v1/warnings/feeds-switzerland"
    assert meteoalarm_feed._GEOCODE_NAME["DE"] == "WARNCELLID"
    assert len(_quellen_in_registry("CH")) == 1


def test_ac10_registrierungsreihenfolge_ch_no_se_vor_dpc():
    """AC-10/Spec Impl. 8: in der ECHTEN Registry stehen CH, NO, SE (in dieser Reihenfolge) VOR
    ``DpcSource`` (Gewitter-Tie-Break "zuerst registriert gewinnt", #1427 S2)."""
    _assert_pruefling_aus_diesem_baum()
    import services.official_alerts.base as oa_base
    from services.official_alerts.dpc import DpcSource

    echte = list(oa_base._REGISTERED_SOURCES)

    def pos(land):
        idx = [i for i, s in enumerate(echte) if s in _quellen_in_registry(land)]
        assert len(idx) == 1, (land, idx)
        return idx[0]

    dpc = [i for i, s in enumerate(echte) if isinstance(s, DpcSource)]
    assert len(dpc) == 1
    assert pos("CH") < pos("NO") < pos("SE") < dpc[0]


# ───────────────────────────── AC-11 (Test 10) ───────────────────────────────

@pytest.mark.parametrize("art", ["route", "vergleich"])
@pytest.mark.parametrize("land,punkt,now", [
    ("NO", BERGEN, NOW_NO_BERGEN),
    ("SE", KARLSTAD, NOW_SE),
])
def test_ac11_warnung_erreicht_dieselben_kanaele_wie_at(land, punkt, now, art, premium_nutzer):
    """AC-11: GIVEN eine orange Warnung aus NO bzw. SE (Feed ueber die echte Quelle) und eine
    orange AT-Warnung (Hitze Wien), UND ein Trip bzw. Ortsvergleich mit Empfaengern auf allen vier
    Kanaelen, WHEN die geteilte Alarm-Kanal-Aufloesung laeuft, THEN erreicht die Nord-Warnung
    dieselbe Kanalmenge wie die AT-Warnung -- alle vier."""
    _assert_pruefling_aus_diesem_baum()
    _feed_vorbelegen(land, _feed(land))
    _feed_vorbelegen("AT", _feed_at())
    _zamg_gemeinde(*WIEN, 90101, "Wien")

    at_orange = [a for a in _quelle("AT").fetch(*WIEN) if a.level == 3]
    assert at_orange, "Kontrolle: orange AT-Warnung (Wien) aus der AT-Stichprobe"
    nord_orange = [a for a in _quelle(land).fetch(*punkt) if a.level == 3]
    assert nord_orange, f"orange {land}-Warnung muss aus dem Feed entstehen"

    abo = _abo(art)
    k_nord = _kanaele_fuer(nord_orange[0], abo, premium_nutzer)
    k_at = _kanaele_fuer(at_orange[0], abo, premium_nutzer)
    assert k_nord == k_at == _ALL_CHANNELS, (k_nord, k_at)


# ═══════════════════════════ Teil B: Finnland (AC-12) ═════════════════════════
# Faellt als Block weg, wenn die FI-Zonengeometrie nicht belegbar zugeordnet werden kann
# (AC-12, zweiter Satz: FI wird dann NICHT registriert und als offen gemeldet).

FI_RAND_PUNKTE = {
    "Helsinki": HELSINKI, "Utsjoki": (69.91, 27.03), "Mariehamn": MARIEHAMN, "Hanko": (59.82, 22.96),
    "Turku": TURKU, "Vaasa": VAASA, "Oulu": (65.01, 25.47), "Rovaniemi": (66.50, 25.73),
    "Kemi": (65.74, 24.56), "Kotka": (60.47, 26.95), "Imatra": (61.17, 28.77),
    "Lappeenranta": (61.06, 28.19), "Tornio": (65.85, 24.15), "Inari": (68.90, 27.00),
}


def test_ac12_fi_feedpfad_und_registrierung():
    """AC-12 (Infrastruktur): Pfad auf ``feeds-finland`` UND genau EINE FI-Quelle registriert,
    in der Reihenfolge CH, NO, SE, FI vor ``DpcSource``."""
    _assert_pruefling_aus_diesem_baum()
    import services.official_alerts.base as oa_base
    from services.official_alerts import meteoalarm_feed
    from services.official_alerts.dpc import DpcSource

    assert meteoalarm_feed._FEED_PATHS["FI"] == _PFADE["FI"]
    echte = list(oa_base._REGISTERED_SOURCES)

    def pos(land):
        idx = [i for i, s in enumerate(echte) if s in _quellen_in_registry(land)]
        assert len(idx) == 1, (land, idx)
        return idx[0]

    dpc = [i for i, s in enumerate(echte) if isinstance(s, DpcSource)]
    assert pos("NO") < pos("SE") < pos("FI") < dpc[0]


@pytest.mark.parametrize("name,punkt,now", [
    ("vaasa_fi029", VAASA, NOW_FI_LAND1),
    ("turku_fi032", TURKU, NOW_FI_LAND1),
    ("mariehamn_fi043", MARIEHAMN, NOW_FI_LAND2),
])
def test_ac12_fi_land_punkt_in_warnzone_liefert_warnung(name, punkt, now):
    """AC-12 (Test 11): GIVEN ein Punkt in Pohjanmaa/Varsinais-Suomi/Ahvenanmaa und eine aktive
    Windwarnung fuer ``FI029``/``FI032``/``FI043``, WHEN die Warnungen abgerufen werden, THEN
    erscheint sie; ein Punkt in einer anderen Zone (Helsinki) bekommt sie nicht."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle("FI").covers(*punkt) is True
    alerts, unavailable = _abruf("FI", punkt, now)
    assert len(alerts) == 1, f"genau eine Warnung erwartet: {alerts}"
    assert alerts[0].hazard == "wind_gust" and alerts[0].level == 2 and unavailable is False

    fremd, fremd_unavailable = _abruf("FI", HELSINKI, now)
    assert fremd == [] and fremd_unavailable is False


def test_ac12_fi_seegebiet_punkt_liefert_warnung():
    """AC-12 (Test 12): GIVEN ein Punkt im Seegebiet ``FI806`` (Suomenlahden länsiosa) und eine
    aktive Sturmwarnung, WHEN die Warnungen abgerufen werden, THEN erscheint sie."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle("FI").covers(*HANKO_SEE) is True
    alerts, unavailable = _abruf("FI", HANKO_SEE, NOW_FI_SEE)
    assert len(alerts) == 1 and alerts[0].level == 2, alerts
    assert unavailable is False


def test_ac12_fi_rand_punkte_zustaendig_nachbarn_nicht():
    """AC-4 fuer Finnland: >=12 Rand-/Kuestenpunkte zustaendig; Nachbarland-Punkte (Kopenhagen,
    Flensburg, Murmansk, Stockholm, Oslo) nicht und ohne Ausfallhinweis."""
    _assert_pruefling_aus_diesem_baum()
    quelle = _quelle("FI")
    assert len(FI_RAND_PUNKTE) >= 12
    daneben = [n for n, p in FI_RAND_PUNKTE.items() if quelle.covers(*p) is not True]
    assert daneben == [], f"FI-Quelle nicht zustaendig fuer: {daneben}"
    nachbarn = dict(NACHBAR_PUNKTE, Stockholm=STOCKHOLM, Oslo=OSLO)
    nachbarn.pop("Tallinn")  # Tallinn liegt ~80 km suedlich von Helsinki -- Seeumriss ist grosszuegig
    for name, punkt in nachbarn.items():
        assert quelle.covers(*punkt) is False, f"FI-Quelle darf {name} nicht beanspruchen"
        alerts, unavailable = _abruf("FI", punkt, NOW_FI_SEE, feed=None)
        assert alerts == [] and unavailable is False, name


def test_ac12_fi_ausfall_und_ruhige_lage():
    """AC-2/AC-3 fuer Finnland: Helsinki ohne Warnung -> leer, kein Ausfall; Feed-Ausfall -> Ausfall."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle("FI").covers(*HELSINKI) is True
    ruhig, unavailable = _abruf("FI", HELSINKI, NOW_FI_LAND1)
    assert ruhig == [] and unavailable is False
    leer, ausfall = _abruf("FI", HELSINKI, NOW_FI_LAND1, feed=None)
    assert leer == [] and ausfall is True


def test_ac12_fi_text_aus_en_gb():
    """AC-7 fuer Finnland: Feed traegt ``fi-FI``/``sv-SE``/``en-GB`` -- der Text kommt aus ``en-GB``."""
    _assert_pruefling_aus_diesem_baum()
    alerts, _ = _abruf("FI", VAASA, NOW_FI_LAND1)
    assert len(alerts) == 1
    info = {i["language"]: i for i in _infos(_feed("FI")["warnings"][4]["alert"])}
    assert set(info) == {"fi-FI", "sv-SE", "en-GB"}
    assert alerts[0].label == info["en-GB"]["event"]
