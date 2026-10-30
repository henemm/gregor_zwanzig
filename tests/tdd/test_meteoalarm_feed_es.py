"""TDD RED -- MeteoAlarm Spanien (AEMET) aus dem kontingentfreien Feed (Issue #1442, Scheibe S3).

SPEC: docs/specs/modules/feat_1442_s3_meteoalarm_spanien.md ("## Acceptance Criteria", AC-1 bis
AC-17; Test Plan Test 1-16). Ablage in ``tests/tdd/`` wie S1/S2 (die Spec nennt ``tests/``).

AC -> Testfunktion (AC-16 / Test 16 Live: eigene Datei ``test_meteoalarm_feed_es_live.py``):

- AC-1  (Test 1)  ``test_ac1_gr221_punkte_bekommen_tramontana_warnung``
- AC-2  (Test 2)  ``test_ac2_kuestenpunkt_land_und_seezone_je_einmal``
- AC-3  (Test 3)  ``test_ac3_punkt_auf_see_trifft_nur_seezone``
- AC-4  (Test 4)  ``test_ac4_ausserhalb_spaniens_schweigt_folgenlos``
- AC-5  (Test 5)  ``test_ac5_feed_ausfall_meldet_nicht_abrufbar``
- AC-6  (Test 6)  ``test_ac6_ruhige_lage_ist_keine_warnung_ohne_ausfall``
- AC-7  (Test 7)  ``test_ac7_unbekannte_zone_im_feed_meldet_drift``
- AC-8  (Test 8)  ``test_ac8_text_stammt_aus_en_gb``
- AC-9  (Test 9)  ``test_ac9_registrierung_es_nach_fi_vor_dpc``
- AC-10 (Test 10) ``test_ac10_grenzstreifen_fr_genau_eine_es_warnung``,
                  ``test_ac10_fr_jenseits_des_streifens_nicht_zustaendig``
- AC-11 (Test 11) ``test_ac11_bestehende_laenderpfade_unveraendert`` (Regressions-Golden-Master, darf
                  schon jetzt GRUEN sein; zusaetzlich laufen die FI-/NO-/SE-/CH-/IT-/AT-/DE-
                  Testdateien unveraendert)
- AC-12 (Test 12) ``test_ac12_fi_und_es_laufen_ueber_denselben_zonenweg``
- AC-13 (Test 13) ``test_ac13_auszug_traegt_id_im_muster_und_mapper_laedt_alle``
- AC-14 (Test 14) ``test_ac14_auszug_vollstaendig_und_klein``
- AC-15 (Test 15) ``test_ac15_es_warnung_erreicht_dieselben_kanaele_wie_at``
- AC-17           ``test_ac17_doku_fuehrt_es_in_readme_und_lizenzantrag``  (# doc-compliance-test)

RED-Ursachen (bewusst, fachlich): ``_FEED_PATHS`` kennt kein ES, ``covers()`` und ``fetch()`` fallen
fuer ES in den falschen Zweig; die Zonendatei ``meteoalarm_zones_ES.geojson.json`` und die Registrierung
fehlen. Jeder Test, der sonst "zufaellig" gruen waere (leere Liste bei nicht zustaendiger Quelle),
traegt eine Positivkontrolle (``covers(...) is True``).

Kein Mock-Theater, kein Netz (Kern-Schicht, laeuft mit ``--disable-socket``): der Modul-Cache wird mit
der ECHTEN aufgezeichneten Probe vorbelegt, ``fetch()`` laeuft ueber den echten Cache-Treffer-Zweig
von ``warn_egress.cached_fetch()``.

Fixture ``tests/fixtures/meteoalarm_feed/feed_spain_sample.json``: reale, unveraenderte Eintraege aus
dem Vollabruf vom 2026-10-30 plus SYNTHETISCHE Eintraege (Kennung ``.SYNTH-*``; Herkunft und Auswahl:
README.md im selben Verzeichnis). Der Spanien-Feed fuehrte am Aufzeichnungstag fuer Mallorca nur eine
echte gelbe Warnung (``ES115``); die GR221-/Kuesten-/Grenz-Warnungen sind aus echten Eintraegen
abgeleitet.
"""
from __future__ import annotations

import json
import re
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
_DATA = _REPO_ROOT / "src" / "services" / "official_alerts" / "data"
_ZONEN_ES = _DATA / "meteoalarm_zones_ES.geojson.json"

# ── Punkte ────────────────────────────────────────────────────────────────────────────────────
SOLLER = (39.766, 2.715)          # ES114 Sierra Tramontana (GR221)
LLUC = (39.822, 2.887)            # ES114
SA_CALOBRA = (39.850, 2.800)      # ES114
SA_DRAGONERA = (39.587, 2.319)    # nur Seezone ES874 (Rohumriss); Land ES117 0,035 Grad entfernt
PORT_ANDRATX = (39.545, 2.388)    # nur Seezone ES874; Land ES117 0,043 Grad entfernt
SEE_VOR_DRAGONERA = (39.50, 2.15)  # ca. 0,1 Grad auf See, ausserhalb der 0,05-Aufweitung
ALCUDIA = (39.853, 3.121)         # ES115 Norte y nordeste de Mallorca (echte gelbe Warnung)
MADRID = (40.42, -3.70)           # ES219, im Fixture nur gruen -> keine aktive Warnung
MENORCA = (40.00, 3.84)           # ES119, keine Warnung im Fixture

PERPIGNAN = (42.70, 2.90)         # FR, klar ausserhalb
TANGER = (35.76, -5.80)           # MA, klar ausserhalb
TOULOUSE = (43.60, 1.44)          # FR, jenseits des Aufweitungsstreifens
HENDAYE = (43.37, -1.78)          # FR im Streifen (ES233)
BOURG_MADAME = (42.43, 1.95)      # FR im Streifen (ES182)

# Referenzzeitpunkt (UTC): in der Gueltigkeit der ES115-Warnung (30.10. 23:00Z - 31.10. 10:59Z) und
# der SYNTH-Eintraege (31.10. 00:00Z - 23:59Z), nach dem Versand aller Eintraege.
NOW_ES = datetime(2026, 10, 31, 9, 0, tzinfo=timezone.utc)

_PFAD_ES = "/api/v1/warnings/feeds-spain"


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
    return json.loads((_FIXTURES / "feed_spain_sample.json").read_text(encoding="utf-8"))


def _infos(alert: dict) -> list:
    info = alert["info"]
    return info if isinstance(info, list) else [info]


def _eintrag(feed: dict, suffix: str) -> dict:
    treffer = [w for w in feed["warnings"] if w["alert"]["identifier"].endswith(suffix)]
    assert len(treffer) == 1, f"Fixture-Eintrag *{suffix} nicht eindeutig"
    return treffer[0]["alert"]


def _zeitraum(feed: dict, suffix: str) -> "tuple[datetime, datetime]":
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


def _quelle(land: str = "ES"):
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    return MeteoAlarmFeedSource(land)


def _abruf(punkt, now=NOW_ES, feed="__fixture__"):
    """Registry-Abruf nur ueber die ES-Quelle (Feed-Cache vorbelegt)."""
    from services.official_alerts import get_official_alerts_with_status

    _feed_vorbelegen("ES", _feed() if feed == "__fixture__" else feed)
    with _nur_quellen(_quelle("ES")):
        return get_official_alerts_with_status(*punkt, now=now)


def _quellen_in_registry(land: str) -> list:
    import services.official_alerts.base as oa_base
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    return [s for s in oa_base._REGISTERED_SOURCES
            if isinstance(s, MeteoAlarmFeedSource) and getattr(s, "country", None) == land]


# ───────────────────────────── AC-1 (Test 1) ─────────────────────────────────

@pytest.mark.parametrize("name,punkt", [("soller", SOLLER), ("lluc", LLUC), ("sa_calobra", SA_CALOBRA)])
def test_ac1_gr221_punkte_bekommen_tramontana_warnung(name, punkt):
    """AC-1: GIVEN ein GR221-Punkt und eine aktive Warnung fuer ``ES114``, WHEN die amtlichen
    Warnungen abgerufen werden, THEN erscheint genau diese Warnung mit Stufe, Art und Zeitraum."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    assert meteoalarm_feed._FEED_PATHS["ES"] == _PFAD_ES
    assert _quelle().covers(*punkt) is True, "ES-Quelle muss hier zustaendig sein"
    alerts, unavailable = _abruf(punkt)

    assert len(alerts) == 1, f"genau EINE Warnung erwartet, erhalten {alerts}"
    a = alerts[0]
    von, bis = _zeitraum(_feed(), ".SYNTH-ES114")
    assert a.level == 3 and a.source == "meteoalarm"
    assert a.label, "Ereignisbezeichnung darf nicht leer sein"
    assert a.hazard, "Gefahrenart darf nicht leer sein"
    assert a.valid_from == von and a.valid_to == bis, (a, von, bis)
    assert a.region_label, "Gebietsbezeichnung darf nicht leer sein"
    assert unavailable is False


# ───────────────────────────── AC-2 (Test 2) ─────────────────────────────────

@pytest.mark.parametrize("name,punkt", [("sa_dragonera", SA_DRAGONERA), ("port_andratx", PORT_ANDRATX)])
def test_ac2_kuestenpunkt_land_und_seezone_je_einmal(name, punkt):
    """AC-2: GIVEN ein Kuestenpunkt im Suedwesten Mallorcas und Warnungen fuer Landzone ``ES117``
    (Regen) UND Seezone ``ES874`` (Wind), WHEN abgerufen wird, THEN liefert die Quelle beide, jede
    genau einmal. Ohne die 0,05-Aufweitung der Landzonen kaeme nur die Seewarnung."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle().covers(*punkt) is True
    alerts, unavailable = _abruf(punkt)

    assert len(alerts) == 2, f"Land- UND Seewarnung erwartet, erhalten {alerts}"
    assert len({(a.hazard, a.valid_from, a.valid_to, a.region_label) for a in alerts}) == 2
    assert all(a.level == 2 and a.source == "meteoalarm" for a in alerts)
    assert unavailable is False


# ───────────────────────────── AC-3 (Test 3) ─────────────────────────────────

def test_ac3_punkt_auf_see_trifft_nur_seezone():
    """AC-3: GIVEN Landzonen um 0,05 Grad aufgeweitet und Seezonen unveraendert, WHEN ein Punkt knapp
    auf See ausserhalb der Aufweitung abgefragt wird, THEN trifft er nur die Seezone: die Seewarnung
    (Wind) erscheint, die Landwarnung ``ES117`` (Regen) nicht."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle().covers(*SEE_VOR_DRAGONERA) is True
    alerts, unavailable = _abruf(SEE_VOR_DRAGONERA)
    assert len(alerts) == 1, f"nur die Seewarnung erwartet, erhalten {alerts}"
    land_alerts, _ = _abruf(SA_DRAGONERA)
    assert {a.hazard for a in alerts} < {a.hazard for a in land_alerts}, (
        "die Land-Warnung (Regen) darf auf See nicht erscheinen"
    )
    assert unavailable is False


# ───────────────────────────── AC-4 (Test 4) ─────────────────────────────────

@pytest.mark.parametrize("name,punkt", [("perpignan", PERPIGNAN), ("tanger", TANGER)])
def test_ac4_ausserhalb_spaniens_schweigt_folgenlos(name, punkt):
    """AC-4: GIVEN ein Punkt ausserhalb Spaniens, WHEN die Zustaendigkeit geprueft wird, THEN
    schweigt die ES-Quelle: ``covers`` False, keine Warnung, KEIN Ausfallhinweis -- selbst bei
    ausgefallenem Feed (``mark_not_covered``)."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle().covers(*SOLLER) is True, "Positivkontrolle: ES-Quelle existiert und deckt Mallorca"
    assert _quelle().covers(*punkt) is False
    alerts, unavailable = _abruf(punkt)
    assert alerts == [] and unavailable is False
    alerts, unavailable = _abruf(punkt, feed=None)
    assert alerts == [] and unavailable is False


# ───────────────────────────── AC-5 (Test 5) ─────────────────────────────────

def test_ac5_feed_ausfall_meldet_nicht_abrufbar():
    """AC-5: GIVEN der Feed-Abruf ist gescheitert, WHEN Warnungen fuer einen Punkt auf Mallorca
    ermittelt werden, THEN ``unavailable=True`` statt einer scheinbar warnungsfreien Lage."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle().covers(*SOLLER) is True
    alerts, unavailable = _abruf(SOLLER, feed=None)
    assert alerts == []
    assert unavailable is True


# ───────────────────────────── AC-6 (Test 6) ─────────────────────────────────

@pytest.mark.parametrize("name,punkt", [("madrid", MADRID), ("menorca", MENORCA)])
def test_ac6_ruhige_lage_ist_keine_warnung_ohne_ausfall(name, punkt):
    """AC-6: GIVEN ein Punkt in Spanien ohne aktive Warnung (Feed fuehrt nur gruen), WHEN abgerufen
    wird, THEN leere Liste UND ``unavailable=False``."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle().covers(*punkt) is True
    alerts, unavailable = _abruf(punkt)
    assert alerts == []
    assert unavailable is False


# ───────────────────────────── AC-7 (Test 7) ─────────────────────────────────

def test_ac7_unbekannte_zone_im_feed_meldet_drift(tmp_path, monkeypatch):
    """AC-7: GIVEN der Feed nennt eine Zone, die in der eingecheckten Datei fehlt (``ES999``), WHEN
    ein Punkt abgefragt wird, THEN steht sie als ``unknown_zone`` im Warn-Journal (Service
    ``meteoalarm_feed:ES``), der Ort bekommt keinen Ausfallhinweis, bekannte Warnungen bleiben."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import warn_egress

    journal = tmp_path / "warn.jsonl"
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH_OVERRIDE", journal)
    feed = _feed()
    for info in _infos(_eintrag(feed, ".SYNTH-ES114")):
        info["area"].append({"areaDesc": "Zona inexistente",
                             "geocode": [{"valueName": "EMMA_ID", "value": "ES999"}]})
    assert _quelle().covers(*SOLLER) is True
    alerts, unavailable = _abruf(SOLLER, feed=feed)
    assert len(alerts) == 1 and unavailable is False, (alerts, unavailable)
    zeilen = [json.loads(z) for z in journal.read_text(encoding="utf-8").splitlines()]
    assert any(z.get("service") == "meteoalarm_feed:ES" and z.get("zone_code") == "ES999"
               and z.get("drift") == "unknown_zone" for z in zeilen), zeilen


# ───────────────────────────── AC-8 (Test 8) ─────────────────────────────────

def test_ac8_text_stammt_aus_en_gb():
    """AC-8: GIVEN ein echter Feed-Eintrag mit ``es-ES`` und ``en-GB`` (ES115, Alcudia), WHEN die
    Warnung ausgegeben wird, THEN ist der Text vorhanden und stammt aus ``en-GB``."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle().covers(*ALCUDIA) is True
    alerts, unavailable = _abruf(ALCUDIA)
    assert len(alerts) == 1, alerts
    echt = next(w["alert"] for w in _feed()["warnings"] if w["alert"]["identifier"].endswith("2PRP1311154648"))
    info = {i["language"]: i for i in _infos(echt)}
    assert set(info) == {"es-ES", "en-GB"}
    assert info["es-ES"]["event"] != info["en-GB"]["event"]
    assert alerts[0].label and alerts[0].label == info["en-GB"]["event"]
    assert unavailable is False


# ───────────────────────────── AC-9 (Test 9) ─────────────────────────────────

def test_ac9_registrierung_es_nach_fi_vor_dpc():
    """AC-9: in der ECHTEN Registry steht genau EINE ES-Quelle, nach FI und vor ``DpcSource``
    (Gewitter-Tie-Break "zuerst registriert gewinnt", #1427 S2)."""
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
    assert pos("FI") < pos("ES") < dpc[0]


# ───────────────────────────── AC-10 (Test 10) ───────────────────────────────

@pytest.mark.parametrize("name,punkt", [("hendaye", HENDAYE), ("bourg_madame", BOURG_MADAME)])
def test_ac10_grenzstreifen_fr_genau_eine_es_warnung(name, punkt):
    """AC-10: GIVEN ein Punkt in Frankreich im 0,05-Streifen an der Pyrenaeen-Grenze, WHEN abgerufen
    wird, THEN erscheint jede ES-Warnung genau einmal (kein Doppel-Chip innerhalb der ES-Quelle).
    Der Quellen-Kollaps mit ``VigilanceSource`` (#1086) bleibt unveraendert und ist hier nicht Thema."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle().covers(*punkt) is True
    alerts, unavailable = _abruf(punkt)
    assert len(alerts) == 1, f"genau EINE ES-Warnung erwartet: {alerts}"
    assert alerts[0].level == 2 and unavailable is False


def test_ac10_fr_jenseits_des_streifens_nicht_zustaendig():
    """AC-10: ein Punkt in Frankreich jenseits des Aufweitungsstreifens (Toulouse) bekommt keine ES-
    Warnung und keinen Ausfallhinweis."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle().covers(*SOLLER) is True, "Positivkontrolle"
    assert _quelle().covers(*TOULOUSE) is False
    alerts, unavailable = _abruf(TOULOUSE, feed=None)
    assert alerts == [] and unavailable is False


# ───────────────────────────── AC-11 (Test 11) ───────────────────────────────

def test_ac11_bestehende_laenderpfade_unveraendert():
    """AC-11 (Regression, darf schon jetzt GRUEN sein): Feedpfade/Geocode-Namen aller bisherigen
    Laender bleiben unveraendert."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    erwartet = {"IT": "italy", "AT": "austria", "DE": "germany", "CH": "switzerland",
                "NO": "norway", "SE": "sweden", "FI": "finland"}
    for land, name in erwartet.items():
        assert meteoalarm_feed._FEED_PATHS[land] == f"/api/v1/warnings/feeds-{name}", land
    assert meteoalarm_feed._GEOCODE_NAME["DE"] == "WARNCELLID"
    assert meteoalarm_feed._GEOCODE_NAME["FI"] == "EMMA_ID"
    assert len(_quellen_in_registry("FI")) == 1


# ───────────────────────────── AC-12 (Test 12) ───────────────────────────────

def test_ac12_fi_und_es_laufen_ueber_denselben_zonenweg():
    """AC-12: GIVEN der Zonenweg fuer Finnland und Spanien, WHEN der Code geprueft wird, THEN laufen
    beide ueber ``_fetch_zones(country, ...)`` -- es gibt keine kopierte ``_fetch_es`` (und die alte
    laenderspezifische ``_fetch_fi`` ist aufgegangen)."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    assert hasattr(MeteoAlarmFeedSource, "_fetch_zones"), "verallgemeinerter Zonenweg fehlt"
    assert not hasattr(MeteoAlarmFeedSource, "_fetch_es"), "kopierte ES-Abrufroutine verboten"
    assert not hasattr(MeteoAlarmFeedSource, "_fetch_fi"), "FI-Sonderweg muss im Zonenweg aufgehen"
    assert set(meteoalarm_feed._zone_mappers) >= {"FI", "ES"}
    # Verhalten: beide Laender liefern ueber dieselbe Quelle Zonen-Treffer.
    assert _quelle("ES").covers(*SOLLER) is True
    assert _quelle("FI").covers(60.17, 24.94) is True


# ───────────────────────────── AC-13 (Test 13) ───────────────────────────────

def test_ac13_auszug_traegt_id_im_muster_und_mapper_laedt_alle():
    """AC-13: GIVEN der eingecheckte ES-Auszug, WHEN der Zonenweg ihn laedt, THEN traegt jede Zone
    ihre Kennung unter ``properties.id`` (``ES`` + 3 Ziffern), ``code`` fehlt, und der
    ``RegionMapper`` laedt alle Zonen."""
    from services.region_mapper import RegionMapper

    assert _ZONEN_ES.is_file(), f"Zonendatei fehlt: {_ZONEN_ES}"
    daten = json.loads(_ZONEN_ES.read_text(encoding="utf-8"))
    features = daten["features"]
    assert features, "Auszug leer"
    for f in features:
        props = f["properties"]
        assert re.fullmatch(r"ES\d{3}", props.get("id", "")), props
        assert "code" not in props, props
    geladen = {rid for rid, _geo, _box in RegionMapper(_ZONEN_ES)._loaded()}
    assert geladen == {f["properties"]["id"] for f in features}


# ───────────────────────────── AC-14 (Test 14) ───────────────────────────────

def test_ac14_auszug_vollstaendig_und_klein():
    """AC-14: GIVEN der ES-Auszug, WHEN Groesse und Inhalt geprueft werden, THEN genau 233 Zonen
    inkl. Kanaren (``ES120``-``ES132``), jede Fixture-Feed-Zone ist enthalten, Datei <= 400 KB."""
    assert _ZONEN_ES.is_file(), f"Zonendatei fehlt: {_ZONEN_ES}"
    assert _ZONEN_ES.stat().st_size <= 400 * 1024, _ZONEN_ES.stat().st_size
    ids = [f["properties"]["id"] for f in json.loads(_ZONEN_ES.read_text(encoding="utf-8"))["features"]]
    assert len(ids) == len(set(ids)) == 233, len(ids)
    assert {f"ES{n}" for n in range(120, 133)} <= set(ids), "Kanaren fehlen"
    assert any(i.startswith("ES87") for i in ids), "Ceuta/Melilla-Kuestenzonen fehlen"
    feed_zonen = set()
    for w in _feed()["warnings"]:
        for info in _infos(w["alert"]):
            for area in info["area"]:
                geo = area["geocode"]
                feed_zonen |= {g["value"] for g in (geo if isinstance(geo, list) else [geo])}
    assert feed_zonen <= set(ids), f"Feed-Zonen ohne Geometrie: {sorted(feed_zonen - set(ids))}"


# ───────────────────────────── AC-15 (Test 15) ───────────────────────────────

@pytest.mark.parametrize("art", ["route", "vergleich"])
def test_ac15_es_warnung_erreicht_dieselben_kanaele_wie_at(art, premium_nutzer):  # noqa: F811
    """AC-15: GIVEN eine orange ES-Warnung (Tramontana, Soller) und eine orange AT-Warnung (Hitze
    Wien), UND ein Trip bzw. Ortsvergleich mit Empfaengern auf allen vier Kanaelen, WHEN die
    geteilte Alarm-Kanal-Aufloesung laeuft, THEN erreicht die ES-Warnung dieselbe Kanalmenge wie die
    AT-Warnung -- alle vier."""
    _assert_pruefling_aus_diesem_baum()
    _feed_vorbelegen("ES", _feed())
    _feed_vorbelegen("AT", _feed_at())
    _zamg_gemeinde(*WIEN, 90101, "Wien")

    at_orange = [a for a in _quelle("AT").fetch(*WIEN) if a.level == 3]
    assert at_orange, "Kontrolle: orange AT-Warnung (Wien) aus der AT-Stichprobe"
    es_orange = [a for a in _quelle("ES").fetch(*SOLLER) if a.level == 3]
    assert es_orange, "orange ES-Warnung muss aus dem Feed entstehen"

    abo = _abo(art)
    k_es = _kanaele_fuer(es_orange[0], abo, premium_nutzer)
    k_at = _kanaele_fuer(at_orange[0], abo, premium_nutzer)
    assert k_es == k_at == _ALL_CHANNELS, (k_es, k_at)


# ───────────────────────────── AC-17 (Doku) ──────────────────────────────────

def test_ac17_doku_fuehrt_es_in_readme_und_lizenzantrag():  # doc-compliance-test
    """AC-17 (Dokumentationspflicht, kein Verhaltensnachweis): ES-Abschnitt im Daten-README
    (Herkunft, sha256, Skript-Parameter) und Spanien im bestehenden Lizenz-Antrag zusammen mit FI."""
    readme = (_DATA / "README.md").read_text(encoding="utf-8")
    assert "meteoalarm_zones_ES" in readme, "ES-Abschnitt im data/README.md fehlt"
    assert "0c8fe7b9" in readme and "simplify" in readme
    quellen = (_REPO_ROOT / "docs" / "specs" / "data_sources.md").read_text(encoding="utf-8")
    assert re.search(r"(?i)spanien|\bES\b", quellen) and "meteoalarm_zones_ES" in quellen, (
        "Spanien im Lizenz-Antrag (docs/specs/data_sources.md) fehlt"
    )
