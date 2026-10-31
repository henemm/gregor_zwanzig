"""TDD RED -- MeteoAlarm Vereinigtes Koenigreich aus dem kontingentfreien Feed (Issue #1442, S3b).

SPEC: docs/specs/modules/feat_1442_s3b_meteoalarm_uk.md ("## Acceptance Criteria", AC-1 bis AC-10;
Test Plan Test 1-11). AC-10 / Test 11 (live): eigene Datei ``test_meteoalarm_feed_uk_live.py``.

AC -> Testfunktion:

- AC-1  (Test 1)  ``test_ac1_feedpfad_gb``
- AC-2  (Test 2)  ``test_ac2_uk_orte_sind_zustaendig``, ``test_ac2_ausserhalb_schweigt_folgenlos``
- AC-3  (Test 3)  ``test_ac3_gewarnter_ort_bekommt_warnung_mit_stufe_art_zeitraum``,
                  ``test_ac3_ort_ausserhalb_der_polygone_ist_ruhig_ohne_ausfall``,
                  ``test_ac3_nebelwarnung_wird_verworfen``
- AC-4  (Test 4)  ``test_ac4_cancel_nimmt_warnung_zurueck``,
                  ``test_ac4_update_ersetzt_vorgaenger_genau_einmal``
- AC-5  (Test 5)  ``test_ac5_unlesbares_polygon_meldet_nicht_abrufbar``
- AC-6  (Test 6)  ``test_ac6_text_stammt_aus_en_gb``
- AC-7  (Test 7/10) ``test_ac7_registrierung_gb_nach_pl_vor_dpc``,
                  ``test_ac7_bestehende_laenderpfade_unveraendert`` (Golden Master, darf GRUEN sein)
- AC-8  (Test 8)  ``test_ac8_umrissdatei_und_readme``
- AC-9  (Test 9)  ``test_ac9_warnung_erreicht_dieselben_kanaele_wie_at``

RED-Ursachen (fachlich): ``_FEED_PATHS`` kennt ``GB`` nicht, ``_POLYGON_COUNTRIES`` auch nicht (der
Konstruktor faellt in den Zonen-/IT-Zweig), die Umrissdatei und die Registrierung fehlen. Jeder
Test, der sonst zufaellig gruen waere (leere Liste bei nicht zustaendiger Quelle), traegt eine
Positivkontrolle (``covers(...) is True``).

Kein Mock-Theater, kein Netz: der Modul-Cache wird mit dem ECHTEN aufgezeichneten Feed vorbelegt,
``fetch()`` laeuft ueber den echten Cache-Treffer-Zweig von ``warn_egress.cached_fetch()``.

Fixture ``tests/fixtures/meteoalarm_feed/feed_uk_sample.json``: der echte Vollabruf vom 2026-10-31
(4 Eintraege, unveraendert) plus drei SYNTHETISCHE Eintraege (``.SYNTH-*``, Herkunft: README.md dort).
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Geteilte Helfer aus der S1-Testdatei (eine Quelle, kein Duplikat). ``premium_nutzer`` ist ein
# pytest-Fixture und muss im Namensraum dieser Datei stehen.
from tests.tdd.test_meteoalarm_feed_ch import (  # noqa: F401
    WIEN, _ALL_CHANNELS, _abo, _feed_at, _kanaele_fuer, _nur_quellen, _zamg_gemeinde,
    premium_nutzer,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "meteoalarm_feed"
_DATA = _REPO_ROOT / "src" / "services" / "official_alerts" / "data"

# ── Punkte (lat, lon); Treffer per Ray-Cast gegen die Aufzeichnung 2026-10-31 geprueft ────────
LONDON = (51.51, -0.13)
EDINBURGH = (55.95, -3.19)
LERWICK = (60.15, -1.15)           # Shetland: Nordschottland-Wind (v3)
STORNOWAY = (58.21, -6.39)         # Hebriden: Nordschottland-Wind (v3)
INVERNESS = (57.48, -4.22)         # Nordschottland-Wind (v3)
BELFAST = (54.60, -5.93)
CARDIFF = (51.48, -3.18)
HOLYHEAD = (53.31, -4.63)          # Irische-See-Wind (v1)
PENZANCE = (50.12, -5.54)          # Irische-See-Wind (v1)
OXFORD = (51.75, -1.26)            # nur Nebel (cd0a7b87) -> verworfen
MANCHESTER = (53.48, -2.24)        # in keinem Warn-Polygon
PARIS = (48.86, 2.35)
DUBLIN = (53.35, -6.26)            # Irland: ausserhalb des Scopes

NOW_IRISCHE_SEE = datetime(2026, 10, 26, 22, 0, tzinfo=timezone.utc)   # v1: 26.10. 18:00 - 27.10. 03:00Z
NOW_NORD = datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc)          # v3: 27.10. 03:00 - 18:00Z
NOW_NEBEL = datetime(2026, 10, 31, 7, 0, tzinfo=timezone.utc)          # fb133494: 31.10. 04:11 - 10:00Z

_PFAD = "/api/v1/warnings/feeds-united-kingdom"
_V1 = "61bc9a69.v1.0.W"
_V3 = "011bc9b4.v3.0.W"


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


def _feed() -> dict:
    return json.loads((_FIXTURES / "feed_uk_sample.json").read_text(encoding="utf-8"))


def _real_und_synth(*synth: str) -> dict:
    """Die vier echten Eintraege plus nur die genannten ``.SYNTH-*``-Eintraege."""
    kopie = _feed()
    kopie["warnings"] = [
        w for w in kopie["warnings"]
        if ".SYNTH-" not in w["alert"]["identifier"]
        or any(w["alert"]["identifier"].endswith(f".SYNTH-{s}") for s in synth)
    ]
    return kopie


def _eintrag(feed: dict, suffix: str) -> dict:
    treffer = [w for w in feed["warnings"] if w["alert"]["identifier"].endswith(suffix)]
    assert len(treffer) == 1, f"Fixture-Eintrag *{suffix} nicht eindeutig"
    return treffer[0]["alert"]


def _zeitraum(feed: dict, suffix: str) -> "tuple[datetime, datetime]":
    info = _eintrag(feed, suffix)["info"][0]
    von = datetime.fromisoformat(info["onset"]).astimezone(timezone.utc)
    bis = datetime.fromisoformat(info["expires"]).astimezone(timezone.utc)
    return von, bis


def _feed_vorbelegen(daten: "dict | None") -> None:
    from services.official_alerts import meteoalarm_feed, warn_egress

    meteoalarm_feed._cache["GB"] = {
        "data": daten,
        "fetched_at": time.monotonic(),
        "ttl": warn_egress.WARN_SUCCESS_TTL if daten is not None else warn_egress.WARN_FAILURE_TTL,
    }


def _quelle():
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    return MeteoAlarmFeedSource("GB")


def _abruf(punkt, now, feed="__standard__"):
    """Registry-Abruf nur ueber die GB-Quelle (Feed-Cache vorbelegt). Standard: echte Eintraege."""
    from services.official_alerts import get_official_alerts_with_status

    _feed_vorbelegen(_real_und_synth() if feed == "__standard__" else feed)
    with _nur_quellen(_quelle()):
        return get_official_alerts_with_status(*punkt, now=now)


def _quellen_in_registry(land: str) -> list:
    import services.official_alerts.base as oa_base
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    return [s for s in oa_base._REGISTERED_SOURCES
            if isinstance(s, MeteoAlarmFeedSource) and getattr(s, "country", None) == land]


# ───────────────────────────── AC-1 (Test 1) ─────────────────────────────────

def test_ac1_feedpfad_gb():
    """AC-1: GIVEN die Landesquelle ``GB``, WHEN der Feedpfad abgefragt wird, THEN
    ``/api/v1/warnings/feeds-united-kingdom`` -- Host unveraendert (``feeds.meteoalarm.org``)."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    assert meteoalarm_feed._FEED_PATHS["GB"] == _PFAD
    assert "GB" in meteoalarm_feed._POLYGON_COUNTRIES
    # Kein neuer Egress-Host: der Feed-Host ist im Python-Guard bereits bekannt (Verhalten, kein Quelltext).
    from app.egress_guard import INVENTORY

    assert "feeds.meteoalarm.org" in INVENTORY


# ───────────────────────────── AC-2 (Test 2) ─────────────────────────────────

@pytest.mark.parametrize("name,punkt", [
    ("london", LONDON), ("edinburgh", EDINBURGH), ("lerwick", LERWICK),
    ("stornoway", STORNOWAY), ("belfast", BELFAST), ("cardiff", CARDIFF),
])
def test_ac2_uk_orte_sind_zustaendig(name, punkt):
    """AC-2: GIVEN ein Punkt in England/Schottland/Wales/Nordirland (auch Shetland, Hebriden,
    Belfast), WHEN die Zustaendigkeit geprueft wird, THEN ist die UK-Quelle zustaendig -- ohne
    vorbelegten Feed, allein ueber den lokalen Umriss."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle().covers(*punkt) is True, name


@pytest.mark.parametrize("name,punkt", [("paris", PARIS), ("dublin", DUBLIN)])
def test_ac2_ausserhalb_schweigt_folgenlos(name, punkt):
    """AC-2: GIVEN Paris oder Dublin-Mitte (Irland nicht im Scope), WHEN die Warnungen abgerufen
    werden, THEN keine Warnung und kein Ausfallhinweis. Positivkontrolle: London ist zustaendig."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle().covers(*LONDON) is True, "Kontrolle: Quelle ist fuer UK zustaendig"
    assert _quelle().covers(*punkt) is False, name
    alerts, unavailable = _abruf(punkt, NOW_NORD)
    assert alerts == [] and unavailable is False


# ───────────────────────────── AC-3 (Test 3) ─────────────────────────────────

@pytest.mark.parametrize("name,punkt,now,suffix,hazard,level", [
    ("inverness", INVERNESS, NOW_NORD, _V3, "wind_gust", 2),
    ("lerwick", LERWICK, NOW_NORD, _V3, "wind_gust", 2),
    ("stornoway", STORNOWAY, NOW_NORD, _V3, "wind_gust", 2),
    ("holyhead", HOLYHEAD, NOW_IRISCHE_SEE, _V1, "wind_gust", 2),
    ("penzance", PENZANCE, NOW_IRISCHE_SEE, _V1, "wind_gust", 2),
])
def test_ac3_gewarnter_ort_bekommt_warnung_mit_stufe_art_zeitraum(
        name, punkt, now, suffix, hazard, level):
    """AC-3: GIVEN ein Punkt im Polygon einer aktiven UK-Warnung (echter Feed), WHEN die amtlichen
    Warnungen ermittelt werden, THEN genau diese Warnung mit Stufe, Ereignisart und Zeitraum."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle().covers(*punkt) is True, name
    alerts, unavailable = _abruf(punkt, now)

    assert len(alerts) == 1, f"genau EINE Warnung erwartet, erhalten {alerts}"
    a = alerts[0]
    von, bis = _zeitraum(_feed(), suffix)
    assert a.level == level and a.hazard == hazard and a.source == "meteoalarm"
    assert a.label, "Ereignisbezeichnung darf nicht leer sein"
    assert a.region_label, "Gebietsbezeichnung darf nicht leer sein"
    assert a.valid_from == von and a.valid_to == bis, (a, von, bis)
    assert unavailable is False


def test_ac3_ort_ausserhalb_der_polygone_ist_ruhig_ohne_ausfall():
    """AC-3: GIVEN Manchester liegt in keinem Warn-Polygon, WHEN abgerufen wird, THEN leere Liste
    und ``unavailable=False`` (nicht "nicht abrufbar"). Positivkontrolle: Quelle ist zustaendig."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle().covers(*MANCHESTER) is True
    alerts, unavailable = _abruf(MANCHESTER, NOW_NORD)
    assert alerts == [] and unavailable is False


def test_ac3_nebelwarnung_wird_verworfen():
    """AC-3 (Abgrenzung): Oxford liegt im Polygon einer echten gelben NEBEL-Warnung; der geteilte
    Mapper verwirft Nebel bewusst -- keine Warnung, kein Ausfall. Positivkontrolle: Zustaendigkeit."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle().covers(*OXFORD) is True
    alerts, unavailable = _abruf(OXFORD, NOW_NEBEL)
    assert alerts == [] and unavailable is False


# ───────────────────────────── AC-4 (Test 4) ─────────────────────────────────

def test_ac4_cancel_nimmt_warnung_zurueck():
    """AC-4: GIVEN die Irische-See-Windwarnung und ein ``Cancel`` (ohne ``info``), das sie per
    ``references`` aufhebt, WHEN abgerufen wird, THEN nicht aktiv. Kontrolle: ohne Cancel ist sie da."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle().covers(*HOLYHEAD) is True
    alerts, _ = _abruf(HOLYHEAD, NOW_IRISCHE_SEE, feed=_real_und_synth())
    assert len(alerts) == 1, f"Kontrolle: ohne Cancel genau eine Warnung, erhalten {alerts}"

    alerts, unavailable = _abruf(HOLYHEAD, NOW_IRISCHE_SEE, feed=_real_und_synth("CANCEL"))
    assert alerts == [], f"Cancel muss die Warnung zurueckgenommen haben: {alerts}"
    assert unavailable is False


def test_ac4_update_ersetzt_vorgaenger_genau_einmal():
    """AC-4: GIVEN die gelbe Nordschottland-Warnung (v3) und ein ``Update`` (orange), das sie per
    ``references`` ersetzt UND die Vorgaengerin noch im Feed steht, WHEN abgerufen wird, THEN genau
    EINE Warnung, orange -- die ersetzte Fassung erscheint nicht zusaetzlich."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle().covers(*INVERNESS) is True
    alerts, unavailable = _abruf(INVERNESS, NOW_NORD, feed=_real_und_synth("UPDATE"))
    assert len(alerts) == 1, f"genau eine Warnung erwartet: {alerts}"
    assert alerts[0].level == 3
    assert unavailable is False


# ───────────────────────────── AC-5 (Test 5) ─────────────────────────────────

def _alle_polygone_unlesbar(feed: dict) -> dict:
    """Jedes Gebiet jedes Eintrags bekommt ein unlesbares Polygon (Muster: Nordics AC-3)."""
    for w in feed["warnings"]:
        for info in w["alert"].get("info") or []:
            ar = info.get("area") or []
            for area in (ar if isinstance(ar, list) else [ar]):
                area["polygon"] = ["nicht,lesbar x,y"]
    return feed


def test_ac5_feed_ohne_lesbares_polygon_meldet_nicht_abrufbar():
    """AC-5: GIVEN der UK-Feed enthaelt KEINEN einzigen Eintrag mit lesbarem Polygon, WHEN die
    Warnungen fuer einen UK-Punkt abgerufen werden, THEN ``alerts == []`` und ``unavailable=True``
    (``mark_fetch_incomplete``) statt warnungsfrei -- geteilte Polygonregel wie CH/NO/SE.
    Kontrolle: ohne kaputte Polygone ist Manchester ruhig und verfuegbar."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle().covers(*MANCHESTER) is True
    _, unavailable_ohne = _abruf(MANCHESTER, NOW_NORD, feed=_real_und_synth())
    assert unavailable_ohne is False

    alerts, unavailable = _abruf(MANCHESTER, NOW_NORD,
                                 feed=_alle_polygone_unlesbar(_real_und_synth()))
    assert alerts == []
    assert unavailable is True


def test_ac5_einzelner_kaputter_eintrag_faerbt_nicht_jeden_ort_als_ausfall():
    """AC-5 (Gegenrichtung, wie S2): GIVEN EIN Eintrag mit unlesbarem Polygon (``SYNTH-KAPUTT``)
    unter lesbaren Eintraegen, WHEN abgerufen wird, THEN behaelt ein gewarnter Punkt seine Warnung
    und ein ruhiger Punkt bleibt ruhig -- beide ``unavailable=False``."""
    _assert_pruefling_aus_diesem_baum()
    feed = _real_und_synth("KAPUTT")
    assert any(w["alert"]["identifier"].endswith(".SYNTH-KAPUTT") for w in feed["warnings"]), \
        "Aufbau: der kaputte Eintrag muss im Feed stehen"

    alerts, unavailable = _abruf(INVERNESS, NOW_NORD, feed=feed)
    assert len(alerts) == 1, f"Inverness muss seine Warnung behalten: {alerts}"
    assert unavailable is False

    alerts, unavailable = _abruf(MANCHESTER, NOW_NORD, feed=_real_und_synth("KAPUTT"))
    assert alerts == []
    assert unavailable is False


# ───────────────────────────── AC-6 (Test 6) ─────────────────────────────────

def test_ac6_text_stammt_aus_en_gb():
    """AC-6: GIVEN der UK-Feed fuehrt nur ``en-GB`` (kein ``de``), WHEN die Warnung ausgegeben wird,
    THEN ist ihr Text vorhanden und stammt aus ``en-GB``."""
    _assert_pruefling_aus_diesem_baum()
    info = _eintrag(_feed(), _V3)["info"]
    assert [i["language"] for i in info] == ["en-GB"], "Aufbau: nur en-GB im Feed"
    alerts, _ = _abruf(INVERNESS, NOW_NORD)
    assert len(alerts) == 1
    assert alerts[0].label == info[0]["event"] and alerts[0].label


# ───────────────────────────── AC-7 (Test 7/10) ──────────────────────────────

def test_ac7_registrierung_gb_nach_pl_vor_dpc():
    """AC-7: in der ECHTEN Registry steht je genau EINE GB-Quelle, in der Reihenfolge PL < GB <
    ``DpcSource`` (Gewitter-Tie-Break, #1427 S2); Belgien (S3c) folgt nach GB."""
    _assert_pruefling_aus_diesem_baum()
    import services.official_alerts.base as oa_base
    from services.official_alerts import meteoalarm_feed
    from services.official_alerts.dpc import DpcSource

    echte = list(oa_base._REGISTERED_SOURCES)

    def pos(land):
        idx = [i for i, s in enumerate(echte) if s in _quellen_in_registry(land)]
        assert len(idx) == 1, (land, idx)
        return idx[0]

    dpc = [i for i, s in enumerate(echte) if isinstance(s, DpcSource)]
    assert len(dpc) == 1
    assert pos("PL") < pos("GB") < dpc[0]
    # S3c: Belgien steht inzwischen NACH GB und VOR ``DpcSource`` (Reihenfolge: test_meteoalarm_feed_be.py).
    assert pos("GB") < pos("BE") < dpc[0]
    assert "BE" in meteoalarm_feed._FEED_PATHS


def test_ac7_bestehende_laenderpfade_unveraendert():
    """AC-7 (Golden Master, darf schon jetzt GRUEN sein): Feedpfade aller bisherigen Laender
    bleiben unveraendert."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    erwartet = {"IT": "italy", "AT": "austria", "DE": "germany", "CH": "switzerland",
                "NO": "norway", "SE": "sweden", "FI": "finland", "ES": "spain",
                "PT": "portugal", "NL": "netherlands", "PL": "poland"}
    for land, name in erwartet.items():
        assert meteoalarm_feed._FEED_PATHS[land] == f"/api/v1/warnings/feeds-{name}", land
    assert meteoalarm_feed._GEOCODE_NAME["DE"] == "WARNCELLID"


# ───────────────────────────── AC-8 (Test 8) ─────────────────────────────────

def test_ac8_umrissdatei_und_readme():
    """AC-8: GIVEN die Datenhaltung, THEN liegt ``meteoalarm_outlines_uk.geojson.json`` mit
    ``properties.id == "GB"`` im Datenordner, und ``data/README.md`` dokumentiert Herkunft, Lizenz
    und die bewusst nicht abgedeckten Kanalinseln/Isle of Man."""  # doc-compliance-test (README)
    _assert_pruefling_aus_diesem_baum()
    datei = _DATA / "meteoalarm_outlines_uk.geojson.json"
    assert datei.is_file() and datei.stat().st_size > 0
    geo = json.loads(datei.read_text(encoding="utf-8"))
    ids = {f["properties"]["id"] for f in geo["features"]}
    assert ids == {"GB"}, ids

    readme = (_DATA / "README.md").read_text(encoding="utf-8")  # doc-compliance-test
    for stichwort in ("meteoalarm_outlines_uk", "Natural Earth", "GBR", "Isle of Man"):
        assert stichwort in readme, f"README ohne UK-Abschnitt: {stichwort}"


# ───────────────────────────── AC-9 (Test 9) ─────────────────────────────────

@pytest.mark.parametrize("art", ["route", "vergleich"])
def test_ac9_warnung_erreicht_dieselben_kanaele_wie_at(art, premium_nutzer):  # noqa: F811
    """AC-9: GIVEN eine orange UK-Warnung (Update-Fassung, Feed ueber die echte Quelle) und eine
    orange AT-Warnung (Hitze Wien), UND ein Trip bzw. Ortsvergleich mit Empfaengern auf allen vier
    Kanaelen, WHEN die geteilte Alarm-Kanal-Aufloesung laeuft, THEN erreicht die UK-Warnung dieselbe
    Kanalmenge wie die AT-Warnung -- alle vier."""
    _assert_pruefling_aus_diesem_baum()
    _feed_vorbelegen(_real_und_synth("UPDATE"))
    from services.official_alerts import meteoalarm_feed  # noqa: F401
    _feed_vorbelegen_at = _feed_at()
    from services.official_alerts import meteoalarm_feed as mf, warn_egress
    mf._cache["AT"] = {"data": _feed_vorbelegen_at, "fetched_at": time.monotonic(),
                       "ttl": warn_egress.WARN_SUCCESS_TTL}
    _zamg_gemeinde(*WIEN, 90101, "Wien")

    at_orange = [a for a in mf.MeteoAlarmFeedSource("AT").fetch(*WIEN) if a.level == 3]
    assert at_orange, "Kontrolle: orange AT-Warnung (Wien) aus der AT-Stichprobe"
    uk_orange = [a for a in _quelle().fetch(*INVERNESS) if a.level == 3]
    assert uk_orange, "orange UK-Warnung muss aus dem Feed entstehen"

    abo = _abo(art)
    k_uk = _kanaele_fuer(uk_orange[0], abo, premium_nutzer)
    k_at = _kanaele_fuer(at_orange[0], abo, premium_nutzer)
    assert k_uk == k_at == _ALL_CHANNELS, (k_uk, k_at)
