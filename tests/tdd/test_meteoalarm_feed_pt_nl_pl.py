"""TDD RED -- MeteoAlarm Portugal, Niederlande, Polen aus dem kontingentfreien Feed (Issue #1442, S3a).

SPEC: docs/specs/modules/feat_1442_s3a_meteoalarm_pt_nl_pl.md ("## Acceptance Criteria", AC-1 bis
AC-14; Test Plan Test 1-16). AC-14 / Test 16 (live): eigene Datei ``test_meteoalarm_feed_pt_nl_pl_live.py``.

AC -> Testfunktion:

- AC-1  (Test 1)  ``test_ac1_gewarnter_ort_bekommt_warnung_mit_stufe_art_zeitraum``,
                  ``test_ac1_echte_pl_nebelwarnung_zakopane_wird_verworfen``
- AC-2  (Test 2)  ``test_ac2_ruhige_lage_ist_keine_warnung_ohne_ausfall``
- AC-3  (Test 3)  ``test_ac3_feed_ausfall_meldet_nicht_abrufbar``
- AC-4  (Test 4)  ``test_ac4_land_kueste_und_rand_sind_zustaendig``,
                  ``test_ac4_ausserhalb_schweigt_folgenlos``
- AC-5  (Test 5)  ``test_ac5_kuestenort_land_und_seezone_je_einmal``,
                  ``test_ac5_nur_seezone_gewarnt_erscheint``
- AC-6  (Test 6)  ``test_ac6_nl_gruenstufen_erzeugen_nichts_gelb_erscheint``
- AC-7  (Test 7)  ``test_ac7_echte_update_proben_je_einmal_ohne_vorgaenger``,
                  ``test_ac7_update_ersetzt_vorgaenger_genau_einmal``,
                  ``test_ac7_cancel_nimmt_warnung_zurueck``
- AC-8  (Test 8)  ``test_ac8_text_stammt_aus_en_gb``
- AC-9  (Test 9)  ``test_ac9_andersfoermiger_eintrag_faerbt_nicht_ein``
- AC-10 (Test 10) ``test_ac10_grenzpaare_genau_eine_warnung_nachbar_still``
- AC-11 (Test 11/12) ``test_ac11_unbekannte_zone_meldet_drift``,
                  ``test_ac11_zonendatei_deckt_feed_zonen_vollstaendig``
- AC-12 (Test 13/14) ``test_ac12_registrierung_pt_nl_pl_nach_es_vor_dpc_ohne_be``,
                  ``test_ac12_bestehende_laenderpfade_unveraendert`` (Golden Master, darf GRUEN sein;
                  zusaetzlich laufen die IT-/AT-/DE-/CH-/NO-/SE-/FI-/ES-Testdateien unveraendert)
- AC-13 (Test 15) ``test_ac13_warnung_erreicht_dieselben_kanaele_wie_at``

RED-Ursachen (fachlich): ``_FEED_PATHS``/``_zone_mappers`` kennen PT/NL/PL nicht, der Konstruktor-
``country`` faellt in den IT-Zweig, die Zonendateien und die Registrierung fehlen. AC-7 (synthetisch:
``Update`` mit noch vorhandenem Vorgaenger, ``Cancel`` ohne ``info``) bleibt auch nach der reinen
Registrierung ROT, weil der Zonenweg (``_alerts_for_zone``) ``references`` nicht auswertet -- das ist
die in Spec Punkt 7 vorgesehene gemeinsame Ergaenzung (wirkt auch fuer FI/ES). Die echten Proben
zeigen den Fehler NICHT (kein ``Update`` hat seinen Vorgaenger noch im Feed, belegt in
``test_ac7_echte_update_proben_je_einmal_ohne_vorgaenger``); das AC verlangt das Verhalten trotzdem.
Jeder Test, der sonst zufaellig gruen waere (leere Liste bei nicht zustaendiger Quelle), traegt eine
Positivkontrolle (``covers(...) is True``).

Kein Mock-Theater, kein Netz: der Modul-Cache wird mit der ECHTEN aufgezeichneten Probe vorbelegt,
``fetch()`` laeuft ueber den echten Cache-Treffer-Zweig von ``warn_egress.cached_fetch()``.

Fixtures ``tests/fixtures/meteoalarm_feed/feed_{portugal,netherlands,poland}_sample.json``: reale,
unveraenderte Eintraege aus den Vollabrufen vom 2026-10-30 plus SYNTHETISCHE Eintraege (Kennung
``.SYNTH-*``, aus einem echten Eintrag desselben Landes abgeleitet; Herkunft: README.md dort). Am
Aufzeichnungstag waren das portugiesische Festland und die Niederlande (nur Stufe gruen) ohne
auswertbare Warnung.

Zonen-Erwartungen folgen dem ES-Rezept der Zonendateien (Spec Punkt 2, ``data/README.md``):
Landzonen um 0,05 Grad aufgeweitet, Seezonen (``NL8xx``, ``PL8xx``) unveraendert. Die Kuestenpunkte
der Spec-Tabelle liegen dabei nur in der Landzone (Den Helder Stadt, Danzig Stadt, Terschelling
Inselmitte); fuer Land+See dienen die Haefen Den Helder (52.96, 4.78) und Danzig-Neufahrwasser
(54.42, 18.68), fuer "nur See" West-Terschelling (53.36, 5.22) -- gemessen gegen geocodes.json.
"""
from __future__ import annotations

import json
import re
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

# ── Punkte (lat, lon) ─────────────────────────────────────────────────────────────────────────
# Portugal
LISSABON = (38.72, -9.14)          # PT016 (+PT020 aufgeweitet), SYNTH orange
PORTO = (41.15, -8.61)             # PT009, SYNTH gelb
FARO = (37.02, -7.93)              # PT021, SYNTH Alert + Update (orange)
CABO_DA_ROCA = (38.78, -9.50)      # PT016, Kueste
ELVAS = (38.88, -7.16)             # PT018, Grenze, SYNTH gelb
BADAJOZ = (38.88, -6.97)           # ES, ausserhalb aller PT-Zonen
COIMBRA = (40.21, -8.43)           # PT013, ruhig
NAZARE = (39.60, -9.07)            # PT015, SYNTH Alert + Cancel
FUNCHAL = (32.65, -16.91)          # PT023 + PT024, echte gelbe Madeira-Updates
# Niederlande
AMSTERDAM = (52.37, 4.90)          # NL011, echte Gruenstufen + SYNTH gelb
MAASTRICHT = (50.85, 5.69)         # NL012
DEN_HELDER = (52.96, 4.76)         # NL011 (+NL019), Stadt
DEN_HELDER_HAFEN = (52.96, 4.78)   # NL011 + NL019 (Land) + NL806 Waddenzee (See)
TERSCHELLING = (53.40, 5.35)       # NL019
WEST_TERSCHELLING = (53.36, 5.22)  # NL019 + NL806; nur NL806 gewarnt
VENLO = (51.37, 6.17)              # NL012, Grenze DE, SYNTH gelb
KALDENKIRCHEN = (51.31, 6.20)      # DE, im 0,05-Streifen von NL012
BAARLE_NASSAU = (51.44, 4.93)      # NL013, Grenze BE, SYNTH orange
UTRECHT = (52.09, 5.12)            # NL015, nur echte Gruenstufen -> ruhig
# Polen
WARSCHAU = (52.23, 21.01)          # PL1465, SYNTH gelb
KRAKAU = (50.06, 19.94)            # PL1261 (+PL1206), SYNTH orange
ZAKOPANE = (49.30, 19.95)          # PL1217, ECHTE gelbe NEBEL-Warnung (2544112) -> verworfen (#1430)
DANZIG = (54.35, 18.65)            # PL2261, Stadt
DANZIG_HAFEN = (54.42, 18.68)      # PL2261 (Land) + PL805 Coastal Zone East (See) (+PL801 Altzone)
HEL = (54.61, 18.80)               # PL2211 + PL801
SLUBICE = (52.35, 14.56)           # PL0805, Grenze DE, SYNTH gelb
FRANKFURT_ODER = (52.35, 14.55)    # DE, im 0,05-Streifen von PL0805
POSEN = (52.41, 16.93)             # PL3064, ruhig
LUBLIN = (51.25, 22.57)            # PL0663, SYNTH Alert + Update (orange)
BIALYSTOK = (53.13, 23.16)         # PL2061, SYNTH Alert + Cancel
# ausserhalb
MADRID = (40.42, -3.70)
PARIS = (48.86, 2.35)
BERLIN = (52.52, 13.40)
PRAG = (50.08, 14.44)
VILNIUS = (54.69, 25.28)

# Referenzzeitpunkte (UTC): SYNTH-Eintraege gelten 30.10. 00:00Z - 01.11. 23:59Z.
# PT: echte Madeira-Updates 31.10. 21:00Z - 01.11. 09:00Z. PL: echte 2544112 bis 30.10. 09:00Z.
_NOW = {
    "PT": datetime(2026, 10, 31, 22, 0, tzinfo=timezone.utc),
    "NL": datetime(2026, 10, 31, 9, 0, tzinfo=timezone.utc),
    "PL": datetime(2026, 10, 30, 6, 0, tzinfo=timezone.utc),
}
_DATEI = {"PT": "feed_portugal_sample.json", "NL": "feed_netherlands_sample.json",
          "PL": "feed_poland_sample.json"}
_PFAD = {"PT": "/api/v1/warnings/feeds-portugal", "NL": "/api/v1/warnings/feeds-netherlands",
         "PL": "/api/v1/warnings/feeds-poland"}
_ZONEN_ANZAHL = {"PT": 25, "NL": 20, "PL": 385}  # Features je Land in geocodes.json (sha256 0c8fe7b9...)


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
    return json.loads((_FIXTURES / _DATEI[land]).read_text(encoding="utf-8"))


def _nur_echte(feed: dict) -> dict:
    return {"warnings": [w for w in feed["warnings"] if ".SYNTH-" not in w["alert"]["identifier"]]}


def _eintrag(feed: dict, suffix: str) -> dict:
    treffer = [w for w in feed["warnings"] if w["alert"]["identifier"].endswith(suffix)]
    assert len(treffer) == 1, f"Fixture-Eintrag *{suffix} nicht eindeutig"
    return treffer[0]["alert"]


def _zeitraum(feed: dict, suffix: str) -> "tuple[datetime, datetime]":
    info = _eintrag(feed, suffix)["info"][0]
    von = datetime.fromisoformat(info["onset"]).astimezone(timezone.utc)
    bis = datetime.fromisoformat(info["expires"]).astimezone(timezone.utc)
    return von, bis


def _info(alert: dict, sprache: str) -> dict:
    return next(i for i in alert["info"] if i["language"].startswith(sprache))


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


def _abruf(land: str, punkt, feed="__fixture__"):
    """Registry-Abruf nur ueber die Quelle dieses Landes (Feed-Cache vorbelegt)."""
    from services.official_alerts import get_official_alerts_with_status

    _feed_vorbelegen(land, _feed(land) if feed == "__fixture__" else feed)
    with _nur_quellen(_quelle(land)):
        return get_official_alerts_with_status(*punkt, now=_NOW[land])


def _direkt(land: str, punkt, feed="__fixture__") -> "tuple[list, dict]":
    """``fetch()`` der Quelle DIREKT (ohne Registry-Kollaps #1086), mit Ausfall-Beobachtung."""
    from services.official_alerts import warn_egress

    _feed_vorbelegen(land, _feed(land) if feed == "__fixture__" else feed)
    with warn_egress.observe_fetch_failure() as status:
        ergebnis = list(_quelle(land).fetch(*punkt))
    return ergebnis, dict(status)


def _quellen_in_registry(land: str) -> list:
    import services.official_alerts.base as oa_base
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    return [s for s in oa_base._REGISTERED_SOURCES
            if isinstance(s, MeteoAlarmFeedSource) and getattr(s, "country", None) == land]


def _zonendatei(land: str) -> Path:
    return _DATA / f"meteoalarm_zones_{land}.geojson.json"


# ───────────────────────────── AC-1 (Test 1) ─────────────────────────────────

@pytest.mark.parametrize("land,name,punkt,suffix,stufe", [
    ("PT", "lissabon", LISSABON, ".SYNTH-PT016", 3),
    ("PT", "porto", PORTO, ".SYNTH-PT009", 2),
    ("NL", "amsterdam", AMSTERDAM, ".SYNTH-NL011", 2),
    ("PL", "warschau", WARSCHAU, ".SYNTH-PL1465", 2),
    ("PL", "krakau", KRAKAU, ".SYNTH-PL1261", 3),
])
def test_ac1_gewarnter_ort_bekommt_warnung_mit_stufe_art_zeitraum(land, name, punkt, suffix, stufe):
    """AC-1: GIVEN ein Ort in PT/NL/PL in einem Gebiet mit aktiver Warnung, WHEN die amtlichen
    Warnungen abgerufen werden, THEN erscheint genau diese Warnung mit Stufe, Ereignisart und
    Gueltigkeitszeitraum."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    assert meteoalarm_feed._FEED_PATHS.get(land) == _PFAD[land], f"Feedpfad {land} fehlt"
    assert _quelle(land).covers(*punkt) is True, f"{land}-Quelle muss hier zustaendig sein"
    alerts, unavailable = _abruf(land, punkt)

    assert len(alerts) == 1, f"genau 1 Warnung erwartet, erhalten {alerts}"
    a = alerts[0]
    von, bis = _zeitraum(_feed(land), suffix)
    assert a.level == stufe and a.source == "meteoalarm", a
    assert a.label, "Ereignisbezeichnung darf nicht leer sein"
    assert a.hazard, "Gefahrenart darf nicht leer sein"
    assert (a.valid_from, a.valid_to) == (von, bis), (a, von, bis)
    assert a.region_label, "Gebietsbezeichnung darf nicht leer sein"
    assert unavailable is False


def test_ac1_echte_pl_nebelwarnung_zakopane_wird_verworfen():
    """AC-1 (Negativpruefung auf ECHTEN Daten, Korrektur Phase 6): GIVEN die echte, unveraenderte
    IMGW-Warnung ``2544112.PL1217`` (Zakopane, gelb, ``awareness_type`` 4 Nebel) ist zum
    Referenzzeitpunkt gueltig, WHEN fuer Zakopane abgerufen wird, THEN entsteht KEINE Warnung (Nebel
    verwirft der geteilte Mapper bewusst, #1430) und KEIN Ausfallhinweis -- auch direkt an der Quelle."""
    _assert_pruefling_aus_diesem_baum()
    eintrag = _eintrag(_feed("PL"), "2544112.PL1217")
    assert ".SYNTH-" not in eintrag["identifier"], "muss die echte Probe sein"
    for info in eintrag["info"]:
        params = {p["valueName"]: p["value"] for p in info["parameter"]}
        assert params["awareness_type"].startswith("4;"), params
        assert params["awareness_level"].startswith("2;"), params
    von, bis = _zeitraum(_feed("PL"), "2544112.PL1217")
    assert von <= _NOW["PL"] < bis, "Kontrolle: Nebelwarnung ist zum Referenzzeitpunkt gueltig"
    assert _quelle("PL").covers(*ZAKOPANE) is True
    alerts, unavailable = _abruf("PL", ZAKOPANE)
    assert alerts == [] and unavailable is False, alerts
    direkt, status = _direkt("PL", ZAKOPANE)
    assert direkt == [] and status["failed"] is False, (direkt, status)


# ───────────────────────────── AC-2 (Test 2) ─────────────────────────────────

@pytest.mark.parametrize("land,name,punkt", [
    ("PT", "coimbra", COIMBRA), ("NL", "utrecht", UTRECHT), ("PL", "posen", POSEN),
])
def test_ac2_ruhige_lage_ist_keine_warnung_ohne_ausfall(land, name, punkt):
    """AC-2: GIVEN ein Ort in PT/NL/PL ohne aktive Warnung (gesunder Feed), WHEN abgerufen wird,
    THEN leere Liste UND ``unavailable=False`` (nicht "nicht abrufbar")."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle(land).covers(*punkt) is True
    alerts, unavailable = _abruf(land, punkt)
    assert alerts == []
    assert unavailable is False


# ───────────────────────────── AC-3 (Test 3) ─────────────────────────────────

@pytest.mark.parametrize("land,punkt", [("PT", LISSABON), ("NL", AMSTERDAM), ("PL", WARSCHAU)])
def test_ac3_feed_ausfall_meldet_nicht_abrufbar(land, punkt):
    """AC-3: GIVEN der Feed-Abruf ist gescheitert, WHEN Warnungen fuer einen Ort in PT/NL/PL ermittelt
    werden, THEN ``unavailable=True`` statt einer scheinbar warnungsfreien Lage."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle(land).covers(*punkt) is True
    alerts, unavailable = _abruf(land, punkt, feed=None)
    assert alerts == []
    assert unavailable is True


# ───────────────────────────── AC-4 (Test 4) ─────────────────────────────────

@pytest.mark.parametrize("land,name,punkt", [
    ("PT", "lissabon", LISSABON), ("PT", "porto", PORTO), ("PT", "faro", FARO),
    ("PT", "cabo_da_roca", CABO_DA_ROCA), ("PT", "elvas", ELVAS), ("PT", "funchal", FUNCHAL),
    ("NL", "amsterdam", AMSTERDAM), ("NL", "maastricht", MAASTRICHT), ("NL", "den_helder", DEN_HELDER),
    ("NL", "terschelling", TERSCHELLING), ("NL", "venlo", VENLO), ("NL", "baarle_nassau", BAARLE_NASSAU),
    ("PL", "warschau", WARSCHAU), ("PL", "krakau", KRAKAU), ("PL", "zakopane", ZAKOPANE),
    ("PL", "danzig", DANZIG), ("PL", "hel", HEL), ("PL", "slubice", SLUBICE),
])
def test_ac4_land_kueste_und_rand_sind_zustaendig(land, name, punkt):
    """AC-4: GIVEN ein Ort in PT/NL/PL, auch an Kueste und Landesrand, WHEN die Zustaendigkeit
    geprueft wird, THEN ist die Landesquelle zustaendig (rein lokal, ohne Netz)."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle(land).covers(*punkt) is True


@pytest.mark.parametrize("land", ["PT", "NL", "PL"])
@pytest.mark.parametrize("name,punkt", [
    ("madrid", MADRID), ("paris", PARIS), ("berlin", BERLIN), ("prag", PRAG), ("vilnius", VILNIUS),
])
def test_ac4_ausserhalb_schweigt_folgenlos(land, name, punkt):
    """AC-4: GIVEN ein Ort ausserhalb aller Zonen von PT/NL/PL, WHEN abgefragt wird, THEN schweigt
    die Quelle: ``covers`` False, keine Warnung, kein Ausfallhinweis -- auch bei ausgefallenem Feed;
    ein direkter ``fetch()`` meldet ``not_covered`` statt eines Ausfalls."""
    _assert_pruefling_aus_diesem_baum()
    positiv = {"PT": LISSABON, "NL": AMSTERDAM, "PL": WARSCHAU}[land]
    assert _quelle(land).covers(*positiv) is True, "Positivkontrolle: Quelle existiert"
    assert _quelle(land).covers(*punkt) is False
    for feed in ("__fixture__", None):
        alerts, unavailable = _abruf(land, punkt, feed=feed)
        assert alerts == [] and unavailable is False
        direkt, status = _direkt(land, punkt, feed=feed)
        assert direkt == []
        assert status["not_covered"] is True, status
        assert status["failed"] is False, status


# ───────────────────────────── AC-5 (Test 5) ─────────────────────────────────

@pytest.mark.parametrize("land,name,punkt,gebiete", [
    ("NL", "den_helder_hafen", DEN_HELDER_HAFEN, {"Noord-Holland", "Waddenzee"}),
    ("PL", "danzig_hafen", DANZIG_HAFEN, {"Gdańsk", "Coastal Zone East"}),
])
def test_ac5_kuestenort_land_und_seezone_je_einmal(land, name, punkt, gebiete):
    """AC-5: GIVEN ein Kuestenort in einer Land- und einer Seezone mit je einer aktiven Warnung, WHEN
    abgerufen wird, THEN erscheinen beide, jede genau einmal -- auch direkt an der Quelle (ohne den
    Registry-Kollaps #1086, der ein Doppel verdecken wuerde)."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle(land).covers(*punkt) is True
    alerts, unavailable = _abruf(land, punkt)
    assert {a.region_label for a in alerts} == gebiete, alerts
    assert len(alerts) == 2 and unavailable is False, alerts
    direkt, status = _direkt(land, punkt)
    assert len(direkt) == 2, f"Land + See je EINMAL erwartet, erhalten {direkt}"
    assert {a.region_label for a in direkt} == gebiete
    assert status["failed"] is False


def test_ac5_nur_seezone_gewarnt_erscheint():
    """AC-5: GIVEN nur die Seezone (NL806 Waddenzee) ist gewarnt, die Landzone (NL019) nicht, WHEN
    ein Kuestenort darin abgefragt wird (West-Terschelling), THEN erscheint die Seewarnung."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle("NL").covers(*WEST_TERSCHELLING) is True
    alerts, unavailable = _abruf("NL", WEST_TERSCHELLING)
    assert [a.region_label for a in alerts] == ["Waddenzee"], alerts
    assert unavailable is False


# ───────────────────────────── AC-6 (Test 6) ─────────────────────────────────

def test_ac6_nl_gruenstufen_erzeugen_nichts_gelb_erscheint():
    """AC-6: GIVEN die echte NL-Probe fuehrt nur Stufe gruen (auch fuer Amsterdam/NL011), WHEN fuer
    Amsterdam abgerufen wird, THEN entsteht kein ``OfficialAlert`` -- damit weder Alarm noch
    Briefing-Zeile, die beide nur ``OfficialAlert`` konsumieren; mit der zusaetzlichen gelben
    Warnung erscheint genau diese, die Gruenstufen weiterhin nicht."""
    _assert_pruefling_aus_diesem_baum()
    echt = _nur_echte(_feed("NL"))
    stufen = {p["value"].split(";")[0] for w in echt["warnings"] for i in w["alert"]["info"]
              for p in i["parameter"] if p["valueName"] == "awareness_level"}
    assert stufen == {"1"}, f"echte NL-Probe soll nur gruen fuehren: {stufen}"
    nl011 = [w for w in echt["warnings"]
             if any(g["value"] == "NL011" for a in w["alert"]["info"][0]["area"] for g in a["geocode"])]
    assert len(nl011) >= 3, "Probe muss echte Gruenstufen fuer Amsterdam tragen"

    assert _quelle("NL").covers(*AMSTERDAM) is True
    alerts, unavailable = _abruf("NL", AMSTERDAM, feed=echt)
    assert alerts == [] and unavailable is False, alerts

    alerts, unavailable = _abruf("NL", AMSTERDAM)
    assert len(alerts) == 1 and alerts[0].level == 2, alerts
    assert unavailable is False


# ───────────────────────────── AC-7 (Test 7) ─────────────────────────────────

def test_ac7_echte_update_proben_je_einmal_ohne_vorgaenger():
    """AC-7 (Befund an echten Proben, Spec Punkt 7): die echten ``Update``-Eintraege (PT Madeira,
    NL, PL) haben ihren Vorgaenger NICHT mehr im Feed; Funchal (PT023 + PT024, je ein echtes
    Update) bekommt jede der beiden Warnungen genau einmal."""
    _assert_pruefling_aus_diesem_baum()
    for land in ("PT", "NL", "PL"):
        echt = _nur_echte(_feed(land))["warnings"]
        ids = {w["alert"]["identifier"] for w in echt}
        updates = [w["alert"] for w in echt if w["alert"].get("msgType") == "Update"]
        assert updates, f"echte {land}-Probe soll Updates enthalten"
        for u in updates:
            refs = {r.split(",")[1] for r in u["references"].split() if len(r.split(",")) >= 2}
            assert not refs & ids, (land, u["identifier"])

    assert _quelle("PT").covers(*FUNCHAL) is True
    direkt, status = _direkt("PT", FUNCHAL)
    assert sorted(a.region_label for a in direkt) == [
        "Madeira - Costa Sul", "Madeira - Regiões Montanhosas"
    ], direkt
    assert status["failed"] is False


@pytest.mark.parametrize("land,name,punkt,neu", [
    ("PT", "faro", FARO, ".SYNTH-PT021-UPDATE"),
    ("PL", "lublin", LUBLIN, ".SYNTH-PL0663-UPDATE"),
])
def test_ac7_update_ersetzt_vorgaenger_genau_einmal(land, name, punkt, neu):
    """AC-7: GIVEN eine gelbe Warnung und ihr orangefarbenes ``Update`` (``references`` auf die gelbe)
    stehen beide im Feed, WHEN abgerufen wird, THEN erscheint nur die aktualisierte Fassung, genau
    einmal -- auch direkt an der Quelle. ROT bis zur gemeinsamen Zonenweg-Ergaenzung."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle(land).covers(*punkt) is True
    von, bis = _zeitraum(_feed(land), neu)
    alerts, unavailable = _abruf(land, punkt)
    assert len(alerts) == 1 and alerts[0].level == 3, f"nur das Update erwartet: {alerts}"
    assert (alerts[0].valid_from, alerts[0].valid_to) == (von, bis)
    assert unavailable is False
    direkt, _status = _direkt(land, punkt)
    assert [a.level for a in direkt] == [3], f"ersetzte Fassung darf nicht zusaetzlich kommen: {direkt}"


@pytest.mark.parametrize("land,name,punkt", [("PT", "nazare", NAZARE), ("PL", "bialystok", BIALYSTOK)])
def test_ac7_cancel_nimmt_warnung_zurueck(land, name, punkt):
    """AC-7: GIVEN eine Warnung und ihr CAP-konformer Rueckzug (``msgType`` Cancel, ohne ``info``,
    ``references`` auf sie), WHEN abgerufen wird, THEN erscheint die aufgehobene Warnung nicht als
    aktiv, ohne Ausfallhinweis. ROT bis zur gemeinsamen Zonenweg-Ergaenzung."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle(land).covers(*punkt) is True
    ohne_cancel = {"warnings": [w for w in _feed(land)["warnings"]
                                if w["alert"].get("msgType") != "Cancel"]}
    kontrolle, _ = _abruf(land, punkt, feed=ohne_cancel)
    assert len(kontrolle) == 1, f"Kontrolle: ohne Rueckzug ist die Warnung aktiv: {kontrolle}"
    alerts, unavailable = _abruf(land, punkt)
    assert alerts == [], f"aufgehobene Warnung darf nicht erscheinen: {alerts}"
    assert unavailable is False


def test_ac7_cancel_mit_info_ist_nie_aktive_warnung():
    """AC-7 (Adversary F001): GIVEN ein ``Cancel`` MIT vollstaendigem ``info[]`` (gelb, Wind, Zone
    PT013 Coimbra, zum Referenzzeitpunkt gueltig), dessen Vorgaenger NICHT im Feed steht, WHEN fuer
    Coimbra abgerufen wird, THEN erscheint der Rueckzug nicht als aktive Warnung -- weder ueber die
    Registry noch direkt an der Quelle. Positivkontrolle: derselbe Eintrag als ``Alert`` ergibt
    genau eine Warnung (der Rueckzug faellt also nicht aus anderem Grund heraus)."""
    _assert_pruefling_aus_diesem_baum()
    feed = _feed("PT")
    cancel = _eintrag(feed, ".SYNTH-PT013-CANCEL-MIT-INFO")
    assert cancel["msgType"] == "Cancel" and cancel["info"], "Fixture: Cancel MIT info"
    ids = {w["alert"]["identifier"] for w in feed["warnings"]}
    assert not {r.split(",")[1] for r in cancel["references"].split()} & ids, "Vorgaenger nicht im Feed"
    assert _quelle("PT").covers(*COIMBRA) is True

    als_alert = {"warnings": [dict(w, alert=dict(w["alert"], msgType="Alert"))
                              if w["alert"] is cancel else w for w in feed["warnings"]]}
    kontrolle, _ = _abruf("PT", COIMBRA, feed=als_alert)
    assert len(kontrolle) == 1 and kontrolle[0].level == 2, kontrolle

    alerts, unavailable = _abruf("PT", COIMBRA)
    assert alerts == [] and unavailable is False, f"Rueckzug darf nicht aktiv sein: {alerts}"
    direkt, status = _direkt("PT", COIMBRA)
    assert direkt == [] and status["failed"] is False, (direkt, status)


# ───────────────────────────── AC-8 (Test 8) ─────────────────────────────────

@pytest.mark.parametrize("land,punkt,suffix,landessprache", [
    ("PT", FUNCHAL, "MD-10-1166", "pt-PT"),
    ("NL", AMSTERDAM, ".SYNTH-NL011", "nl-NL"),
    ("PL", WARSCHAU, ".SYNTH-PL1465", "pl-PL"),
])
def test_ac8_text_stammt_aus_en_gb(land, punkt, suffix, landessprache):
    """AC-8: GIVEN ein Eintrag mit Landessprache und ``en-GB`` (PT: echter Eintrag; NL/PL:
    synthetisch, die echte PL-Probe traegt keine auswertbare Warnart), WHEN die Warnung ausgegeben
    wird, THEN ist ihr Text vorhanden und stammt aus ``en-GB``."""
    _assert_pruefling_aus_diesem_baum()
    eintrag = _eintrag(_feed(land), suffix)
    assert {i["language"] for i in eintrag["info"]} == {landessprache, "en-GB"}
    en, lokal = _info(eintrag, "en"), _info(eintrag, landessprache[:2])
    assert en["event"] != lokal["event"]
    assert _quelle(land).covers(*punkt) is True
    direkt, _status = _direkt(land, punkt)
    labels = {a.label for a in direkt}
    assert en["event"] in labels, f"en-GB-Text erwartet: {en['event']!r} in {labels}"
    assert lokal["event"] not in labels


# ───────────────────────────── AC-9 (Test 9) ─────────────────────────────────

@pytest.mark.parametrize("name,punkt", [("lissabon", LISSABON), ("porto", PORTO)])
def test_ac9_andersfoermiger_eintrag_faerbt_nicht_ein(name, punkt):
    """AC-9: GIVEN der PT-Feed beginnt mit einem andersfoermigen Eintrag (``.SYNTH-KAPUTT``: keine
    awareness-Parameter, unlesbarer Beginn, Zone PT010), WHEN ein Ort mit korrekter Warnung abgefragt
    wird, THEN bekommt er seine Warnung und keinen Ausfallhinweis."""
    _assert_pruefling_aus_diesem_baum()
    feed = _feed("PT")
    assert feed["warnings"][0]["alert"]["identifier"].endswith(".SYNTH-KAPUTT")
    assert _quelle("PT").covers(*punkt) is True
    alerts, unavailable = _abruf("PT", punkt, feed=feed)
    assert len(alerts) == 1, alerts
    assert unavailable is False


# ───────────────────────────── AC-10 (Test 10) ───────────────────────────────

@pytest.mark.parametrize("land,eigen,suffix,nachbar,nachbar_punkt", [
    ("PT", ELVAS, ".SYNTH-PT018", "ES", BADAJOZ),
    ("NL", VENLO, ".SYNTH-NL012", "DE", KALDENKIRCHEN),
    ("NL", BAARLE_NASSAU, ".SYNTH-NL013", None, None),
    ("PL", SLUBICE, ".SYNTH-PL0805", "DE", FRANKFURT_ODER),
])
def test_ac10_grenzpaare_genau_eine_warnung_nachbar_still(land, eigen, suffix, nachbar, nachbar_punkt):
    """AC-10: GIVEN ein Grenzort und nur das eigene Land fuehrt dort eine Warnung (Nachbarfeed gesund,
    ohne Warnung dort), WHEN mit beiden Landesquellen abgerufen wird, THEN erscheint genau diese
    Warnung einmal, und die Quelle des Nachbarlands liefert weder Warnung noch Ausfallhinweis --
    weder am Grenzort noch am Nachbarort jenseits der Grenze. Belgien ist nicht registriert."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import get_official_alerts_with_status, warn_egress

    assert _quelle(land).covers(*eigen) is True
    von, bis = _zeitraum(_feed(land), suffix)
    quellen = [_quelle(land)] + ([_quelle(nachbar)] if nachbar else [])
    _feed_vorbelegen(land, _feed(land))
    if nachbar:
        _feed_vorbelegen(nachbar, {"warnings": []})

    with _nur_quellen(*quellen):
        alerts, unavailable = get_official_alerts_with_status(*eigen, now=_NOW[land])
    assert len(alerts) == 1 and (alerts[0].valid_from, alerts[0].valid_to) == (von, bis), alerts
    assert unavailable is False
    assert len(list(_quelle(land).fetch(*eigen))) == 1, "Quelle direkt: genau EINE Warnung"
    if not nachbar:
        assert not _quellen_in_registry("BE"), "Belgien darf nicht registriert sein"
        return

    for punkt in (eigen, nachbar_punkt):
        with warn_egress.observe_fetch_failure() as status:
            aus_nachbar = list(_quelle(nachbar).fetch(*punkt))
        assert aus_nachbar == [] and status["failed"] is False, (nachbar, punkt, aus_nachbar, status)
    with _nur_quellen(*quellen):
        alerts, unavailable = get_official_alerts_with_status(*nachbar_punkt, now=_NOW[land])
    assert len(alerts) <= 1, f"kein Doppel-Chip am Nachbarort: {alerts}"
    assert all((a.valid_from, a.valid_to) == (von, bis) for a in alerts), alerts
    assert unavailable is False


# ───────────────────────────── AC-11 (Test 11/12) ────────────────────────────

@pytest.mark.parametrize("land,punkt,suffix,fremd", [
    ("PT", LISSABON, ".SYNTH-PT016", "PT999"),
    ("NL", AMSTERDAM, ".SYNTH-NL011", "NL999"),
    ("PL", WARSCHAU, ".SYNTH-PL1465", "PL9999"),
])
def test_ac11_unbekannte_zone_meldet_drift(land, punkt, suffix, fremd, tmp_path, monkeypatch):
    """AC-11: GIVEN der Feed nennt eine Zone, die in der eingecheckten Datei fehlt, WHEN ein Ort
    abgefragt wird, THEN steht sie als ``unknown_zone`` im Warn-Journal (``meteoalarm_feed:<Land>``),
    und der Ort in bekannter Zone bekommt seine Warnung ohne Ausfallhinweis."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import warn_egress

    journal = tmp_path / "warn.jsonl"
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH_OVERRIDE", journal)
    feed = _feed(land)
    for info in _eintrag(feed, suffix)["info"]:
        info["area"].append({"areaDesc": "unbekannt", "geocode": [{"valueName": "EMMA_ID", "value": fremd}]})
    assert _quelle(land).covers(*punkt) is True
    alerts, unavailable = _abruf(land, punkt, feed=feed)
    assert len(alerts) == 1 and unavailable is False, (alerts, unavailable)
    zeilen = [json.loads(z) for z in journal.read_text(encoding="utf-8").splitlines()]
    assert any(z.get("service") == f"meteoalarm_feed:{land}" and z.get("zone_code") == fremd
               and z.get("drift") == "unknown_zone" for z in zeilen), zeilen


@pytest.mark.parametrize("land", ["PT", "NL", "PL"])
def test_ac11_zonendatei_deckt_feed_zonen_vollstaendig(land):
    """AC-11 (Test 12): GIVEN die eingecheckte Zonendatei des Landes, WHEN sie gegen die Feed-Probe
    geprueft wird, THEN ist sie nicht leer, traegt alle ``EMMA_ID``-Zonen des Landes aus
    ``geocodes.json`` unter ``properties.id``, jede Zonen-ID der Probe ist enthalten (1:1), und der
    ``RegionMapper`` laedt alle Zonen."""
    from services.official_alerts.region_mapper import RegionMapper

    datei = _zonendatei(land)
    assert datei.is_file(), f"Zonendatei fehlt: {datei}"
    features = json.loads(datei.read_text(encoding="utf-8"))["features"]
    ids = [f["properties"].get("id", "") for f in features]
    assert len(ids) == len(set(ids)) == _ZONEN_ANZAHL[land], len(ids)
    assert all(re.fullmatch(rf"{land}\d{{3,4}}", i) for i in ids), ids
    feed_zonen = {g["value"] for w in _feed(land)["warnings"] for i in w["alert"].get("info") or []
                  for a in i["area"] for g in a["geocode"]}
    assert feed_zonen <= set(ids), f"Feed-Zonen ohne Geometrie: {sorted(feed_zonen - set(ids))}"
    geladen = {rid for rid, _geo, _box in RegionMapper(datei)._loaded()}
    assert geladen == set(ids)


# ───────────────────────────── AC-12 (Test 13/14) ────────────────────────────

def test_ac12_registrierung_pt_nl_pl_nach_es_vor_dpc_ohne_be():
    """AC-12 (Test 13): in der ECHTEN Registry steht je genau EINE PT-, NL-, PL-Quelle in der
    Reihenfolge ES < PT < NL < PL < ``DpcSource`` (Gewitter-Tie-Break, #1427 S2); Belgien ist weder
    registriert noch als Feedpfad gefuehrt."""
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
    assert pos("FI") < pos("ES") < pos("PT") < pos("NL") < pos("PL") < dpc[0]
    assert not _quellen_in_registry("BE")
    assert "BE" not in meteoalarm_feed._FEED_PATHS


def test_ac12_bestehende_laenderpfade_unveraendert():
    """AC-12 (Test 14, Golden Master, darf schon jetzt GRUEN sein): Feedpfade und Geocode-Arten aller
    bisherigen Laender bleiben unveraendert."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    erwartet = {"IT": "italy", "AT": "austria", "DE": "germany", "CH": "switzerland",
                "NO": "norway", "SE": "sweden", "FI": "finland", "ES": "spain"}
    for land, name in erwartet.items():
        assert meteoalarm_feed._FEED_PATHS[land] == f"/api/v1/warnings/feeds-{name}", land
    assert meteoalarm_feed._GEOCODE_NAME["DE"] == "WARNCELLID"
    assert meteoalarm_feed._GEOCODE_NAME["FI"] == meteoalarm_feed._GEOCODE_NAME["ES"] == "EMMA_ID"


# ───────────────────────────── AC-13 (Test 15) ───────────────────────────────

@pytest.mark.parametrize("art", ["route", "vergleich"])
@pytest.mark.parametrize("land,punkt", [("PT", LISSABON), ("NL", BAARLE_NASSAU), ("PL", KRAKAU)])
def test_ac13_warnung_erreicht_dieselben_kanaele_wie_at(land, punkt, art, premium_nutzer):  # noqa: F811
    """AC-13: GIVEN eine orange Warnung aus PT/NL/PL und eine orange AT-Warnung (Hitze Wien), UND ein
    Trip bzw. Ortsvergleich mit Empfaengern auf allen vier Kanaelen, WHEN die geteilte Alarm-Kanal-
    Aufloesung laeuft, THEN erreicht die Warnung dieselbe Kanalmenge wie die AT-Warnung -- alle vier."""
    _assert_pruefling_aus_diesem_baum()
    _feed_vorbelegen(land, _feed(land))
    _feed_vorbelegen("AT", _feed_at())
    _zamg_gemeinde(*WIEN, 90101, "Wien")

    at_orange = [a for a in _quelle("AT").fetch(*WIEN) if a.level == 3]
    assert at_orange, "Kontrolle: orange AT-Warnung (Wien) aus der AT-Stichprobe"
    orange = [a for a in _quelle(land).fetch(*punkt) if a.level == 3]
    assert orange, f"orange {land}-Warnung muss aus dem Feed entstehen"

    abo = _abo(art)
    k_land = _kanaele_fuer(orange[0], abo, premium_nutzer)
    k_at = _kanaele_fuer(at_orange[0], abo, premium_nutzer)
    assert k_land == k_at == _ALL_CHANNELS, (k_land, k_at)
