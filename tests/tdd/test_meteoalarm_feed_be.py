"""TDD RED -- MeteoAlarm Belgien aus dem kontingentfreien Feed (Issue #1442, S3c).

SPEC: docs/specs/modules/feat_1442_s3c_meteoalarm_be.md ("## Acceptance Criteria", AC-1 bis AC-16;
Test Plan Test 1-16). AC-16 / Test 16 (live): eigene Datei ``test_meteoalarm_feed_be_live.py``.

AC -> Testfunktion:

- AC-1  (Test 1)  ``test_ac1_feedpfad_und_kein_neuer_egress_host``
- AC-2  (Test 2)  ``test_ac2_belgische_orte_sind_zustaendig``, ``test_ac2_ausserhalb_schweigt_folgenlos``
- AC-3  (Test 3)  ``test_ac3_arlon_und_benannte_orte_abgedeckt``, ``test_ac3_landgitter_luecken_hoechstens_0_1_prozent``
- AC-4  (Test 4)  ``test_ac4_nuts2_only_trifft_nur_die_provinz``, ``test_ac4_echte_kuesten_und_nebelwarnungen_verwirft_der_mapper``
- AC-5  (Test 5)  ``test_ac5_emma_id_warnungen_bruessel_und_kueste``
- AC-6  (Test 6)  ``test_ac6_brabant_tabelle_bruessel_leuven_wavre``
- AC-7  (Test 7)  ``test_ac7_doppelkennung_genau_einmal``, ``test_ac7_ueberlappende_zonen_genau_einmal``
- AC-8  (Test 8)  ``test_ac8_echtes_gruenes_update_erzeugt_nichts``, ``test_ac8_update_ersetzt_vorgaenger_genau_einmal``,
                  ``test_ac8_cancel_nimmt_warnung_zurueck``
- AC-9  (Test 9)  ``test_ac9_unbekannter_nuts2_code_kein_ausfall_aber_drift``
- AC-10 (Test 10) ``test_ac10_feed_ohne_kennung_meldet_nicht_abrufbar``, ``test_ac10_ausfall_meldet_nicht_abrufbar``,
                  ``test_ac10_einzelner_kaputter_eintrag_faerbt_nicht_ein``
- AC-11 (Test 11) ``test_ac11_text_aus_de_de_sonst_en_gb``
- AC-12 (Test 12) ``test_ac12_nuts2_wird_nur_fuer_belgien_uebersetzt`` (Golden Master, darf GRUEN sein),
                  ``test_ac12_bestehende_laenderpfade_unveraendert`` (Golden Master, darf GRUEN sein;
                  zusaetzlich laufen die Feedtests aller anderen Laender unveraendert)
- AC-13 (Test 13) ``test_ac13_registrierung_be_nach_gb_vor_dpc``, ``test_ac13_maastricht_keine_doppelwarnung``
- AC-14 (Test 14) ``test_ac14_zonendatei_zehn_zonen``, ``test_ac14_tabelle_und_feed_zonen_stehen_in_der_datei``,
                  ``test_ac14_readme_und_data_sources_dokumentieren_belgien`` (# doc-compliance-test)
- AC-15 (Test 15) ``test_ac15_warnung_erreicht_dieselben_kanaele_wie_at``

RED-Ursachen (fachlich): ``_FEED_PATHS``/``_zone_mappers`` kennen BE nicht, der Konstruktor-``country`` faellt
in den IT-Zweig, ``_BE_NUTS2_TO_EMMA`` und die Zonendatei ``meteoalarm_zones_BE.geojson.json`` fehlen,
Belgien ist nicht registriert, die Doku fehlt.

Kein Mock-Theater, kein Netz: der Modul-Cache wird mit der ECHTEN aufgezeichneten Probe vorbelegt,
``fetch()`` laeuft ueber den echten Cache-Treffer-Zweig von ``warn_egress.cached_fetch()``.

Fixture ``tests/fixtures/meteoalarm_feed/feed_belgium_sample.json``: sechs reale, unveraenderte Eintraege
aus dem Vollabruf vom 2026-10-31 (beide Kennungsarten, ein ``Update``) plus SYNTHETISCHE Eintraege
(Kennung ``.SYNTH-*``, aus einem echten Eintrag abgeleitet; Herkunft: README dort). Alle echten Eintraege sind
Nebel (Typ 4) oder Kueste (Typ 7) -- beide verwirft der geteilte Mapper bewusst (#1430), keine echte Warnung
ist also auswertbar (``test_ac4_echte_kuesten_und_nebelwarnungen_verwirft_der_mapper``). Die SYNTH-Ableitungen
der echten Kuestenwarnung 1618968 tragen deshalb den unterstuetzten Typ ``1; wind``.

Testorte folgen der Spec-Tabelle ("Der Developer verifiziert und justiert sie in der Umsetzung").
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
_ZONEN_DATEI = _DATA / "meteoalarm_zones_BE.geojson.json"

# ── Punkte (lat, lon) ─────────────────────────────────────────────────────────────────────────
BRUESSEL = (50.85, 4.35)        # BE004
LEUVEN = (50.88, 4.70)          # BE004
WAVRE = (50.72, 4.61)           # BE004
OSTENDE = (51.23, 2.92)         # BE801 (Wasser) + Land
KNOKKE = (51.35, 3.29)          # BE801 + Land
KUESTE_5KM = (51.28, 2.80)      # BE801
EUPEN = (50.63, 6.08)           # BE008
BASTOGNE = (50.00, 5.72)        # BE001
BOUILLON = (49.79, 5.07)        # BE001
VIRTON = (49.57, 5.53)          # BE001
ARLON = (49.68, 5.81)           # roh in keiner Zone, nur aufgeweitet in BE001 (Pflichtort, AC-3)
GENT = (51.05, 3.72)            # BE003
NAMUR = (50.47, 4.87)           # BE006
MECHELEN = (51.03, 4.48)        # Grenze BE002/BE004 (Ueberlappung durch die Aufweitung)
NORDSEE_30KM = (51.60, 2.60)    # bewusst ohne Zustaendigkeit
AACHEN = (50.78, 6.08)
LILLE = (50.63, 3.06)
LUXEMBURG_STADT = (49.61, 6.13)
MAASTRICHT = (50.85, 5.69)      # Grenzfall NL/BE
AMSTERDAM = (52.37, 4.90)

# Referenzzeitpunkte (UTC). SYNTH-Eintraege gelten 29.10. 00:00Z - 01.11. 22:59Z.
_NOW = datetime(2026, 10, 31, 9, 0, tzinfo=timezone.utc)
# Echte Kuestenwarnung 1618968 (BE23) gilt 26.10. 01:00Z - 04:00Z.
_NOW_ECHT = datetime(2026, 10, 26, 2, 0, tzinfo=timezone.utc)
_DATEI = "feed_belgium_sample.json"
_PFAD = "/api/v1/warnings/feeds-belgium"

# Spec Implementation Details Punkt 3 (Namensabgleich Feed-areaDesc gegen geocodes.json bestaetigt).
_TABELLE = {
    "BE21": "BE002", "BE22": "BE007", "BE23": "BE003", "BE25": "BE009", "BE32": "BE005",
    "BE33": "BE008", "BE34": "BE001", "BE35": "BE006", "BE10": "BE004", "BE24": "BE004",
    "BE31": "BE004",
}
_ZONEN = {
    "BE001": "Luxembourg", "BE002": "Antwerpen", "BE003": "Oost Vlaanderen", "BE004": "Brabant",
    "BE005": "Hainaut", "BE006": "Namur", "BE007": "Limburg", "BE008": "Liege",
    "BE009": "West Vlaanderen", "BE801": None,
}


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
    meteoalarm_feed._drift_checked.clear()
    yield
    geosphere_warn._cache.clear()
    meteoalarm_feed._cache.clear()
    meteoalarm_feed._drift_checked.clear()


def _feed() -> dict:
    return json.loads((_FIXTURES / _DATEI).read_text(encoding="utf-8"))


def _eintrag(feed: dict, suffix: str) -> dict:
    treffer = [w for w in feed["warnings"] if w["alert"]["identifier"].endswith(suffix)]
    assert len(treffer) == 1, f"Fixture-Eintrag *{suffix} nicht eindeutig"
    return treffer[0]["alert"]


def _teil(*suffixe: str) -> dict:
    """Teil-Feed aus der Fixture: nur die benannten Eintraege (Suffix der Kennung), in Fixture-Reihenfolge."""
    feed = _feed()
    gewaehlt = {id(_eintrag(feed, s)) for s in suffixe}
    return {"warnings": [w for w in feed["warnings"] if id(w["alert"]) in gewaehlt]}


def _zeitraum(feed: dict, suffix: str) -> "tuple[datetime, datetime]":
    info = _eintrag(feed, suffix)["info"][0]
    return (datetime.fromisoformat(info["onset"]).astimezone(timezone.utc),
            datetime.fromisoformat(info["expires"]).astimezone(timezone.utc))


def _feed_vorbelegen(land: str, daten: "dict | None") -> None:
    from services.official_alerts import meteoalarm_feed, warn_egress

    meteoalarm_feed._cache[land] = {
        "data": daten,
        "fetched_at": time.monotonic(),
        "ttl": warn_egress.WARN_SUCCESS_TTL if daten is not None else warn_egress.WARN_FAILURE_TTL,
    }


def _quelle(land: str = "BE"):
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    return MeteoAlarmFeedSource(land)


def _abruf(punkt, feed, now=_NOW):
    """Registry-Abruf nur ueber die belgische Quelle (Feed-Cache vorbelegt)."""
    from services.official_alerts import get_official_alerts_with_status

    _feed_vorbelegen("BE", feed)
    with _nur_quellen(_quelle()):
        return get_official_alerts_with_status(*punkt, now=now)


def _direkt(punkt, feed) -> "tuple[list, dict]":
    """``fetch()`` der Quelle DIREKT (ohne Registry-Kollaps #1086), mit Ausfall-Beobachtung."""
    from services.official_alerts import warn_egress

    _feed_vorbelegen("BE", feed)
    with warn_egress.observe_fetch_failure() as status:
        ergebnis = list(_quelle().fetch(*punkt))
    return ergebnis, dict(status)


def _quellen_in_registry(land: str) -> list:
    import services.official_alerts.base as oa_base
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    return [s for s in oa_base._REGISTERED_SOURCES
            if isinstance(s, MeteoAlarmFeedSource) and getattr(s, "country", None) == land]


_BRABANT = [("bruessel", BRUESSEL), ("leuven", LEUVEN), ("wavre", WAVRE)]
_KUESTE = [("ostende", OSTENDE), ("knokke", KNOKKE), ("kueste_5km", KUESTE_5KM)]


# ───────────────────────────── AC-1 (Test 1) ─────────────────────────────────

def test_ac1_feedpfad_und_kein_neuer_egress_host():
    """AC-1: GIVEN die Konfiguration der Landesquelle BE, WHEN der Feed-Pfad abgefragt wird, THEN
    ``/api/v1/warnings/feeds-belgium`` auf dem bereits gefuehrten Host (kein neuer Egress-Host)."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    assert meteoalarm_feed._FEED_PATHS.get("BE") == _PFAD
    assert meteoalarm_feed.FEED_BASE_URL == "https://feeds.meteoalarm.org"
    inventar = (_REPO_ROOT / "internal" / "egress" / "inventory.go").read_text(encoding="utf-8")
    assert "feeds.meteoalarm.org" in inventar


# ───────────────────────────── AC-2 (Test 2) ─────────────────────────────────

@pytest.mark.parametrize("name,punkt", [
    ("bruessel", BRUESSEL), ("leuven", LEUVEN), ("wavre", WAVRE), ("ostende", OSTENDE),
    ("knokke", KNOKKE), ("kueste_5km", KUESTE_5KM), ("eupen", EUPEN), ("bastogne", BASTOGNE),
    ("bouillon", BOUILLON), ("virton", VIRTON), ("arlon", ARLON), ("gent", GENT),
])
def test_ac2_belgische_orte_sind_zustaendig(name, punkt):
    """AC-2: GIVEN ein Wanderpunkt in Belgien (Kueste, Brabant, Ostkantone, Sueden), WHEN die
    Zustaendigkeit geprueft wird, THEN ist die belgische Quelle zustaendig (rein lokal, ohne Netz)."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle().covers(*punkt) is True


@pytest.mark.parametrize("name,punkt", [("nordsee_30km", NORDSEE_30KM), ("amsterdam", AMSTERDAM)])
def test_ac2_ausserhalb_schweigt_folgenlos(name, punkt):
    """AC-2: GIVEN ein Punkt weit in der Nordsee bzw. weit ausserhalb, WHEN abgefragt wird, THEN
    schweigt die Quelle: ``covers`` False, keine Warnung, kein Ausfallhinweis -- auch bei ausgefallenem
    Feed; ein direkter ``fetch()`` meldet ``not_covered``."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle().covers(*BRUESSEL) is True, "Positivkontrolle: Quelle existiert"
    assert _quelle().covers(*punkt) is False
    for feed in (_feed(), None):
        alerts, unavailable = _abruf(punkt, feed)
        assert alerts == [] and unavailable is False
        direkt, status = _direkt(punkt, feed)
        assert direkt == []
        assert status["not_covered"] is True, status
        assert status["failed"] is False, status


@pytest.mark.parametrize("name,punkt", [
    ("aachen", AACHEN), ("lille", LILLE), ("luxemburg_stadt", LUXEMBURG_STADT),
])
def test_ac2_nachbarstaedte_liefern_keine_belgische_warnung(name, punkt):
    """AC-2: GIVEN eine Stadt jenseits der Grenze (darf nur im Randstreifen der Aufweitung wahr sein),
    WHEN abgefragt wird, THEN keine belgische Warnung und kein Ausfallhinweis."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle().covers(*BRUESSEL) is True, "Positivkontrolle: Quelle existiert"
    alerts, unavailable = _abruf(punkt, _feed())
    assert alerts == [] and unavailable is False, alerts


@pytest.mark.parametrize("name,punkt,zone,nuts2,fremd_nuts2", [
    ("aachen", AACHEN, "BE008", "BE33", "BE23"),   # Liege
    ("lille", LILLE, "BE009", "BE25", "BE23"),     # West-Vlaanderen
])
def test_known_limitation_randueberlappung_nachbarstadt_erhaelt_warnung_der_grenzprovinz(
        name, punkt, zone, nuts2, fremd_nuts2):
    """KNOWN LIMITATION (Spec "Known Limitations", Adversary-Finding F001; bewusst in Kauf genommen,
    Spec Implementation Details Punkt 7 "lieber eine Warnung zu viel"): durch die 0,1°-Aufweitung liegt
    eine Stadt jenseits der Grenze im Randstreifen der angrenzenden Provinzzone. GIVEN eine (SYNTH)
    Wind-Warnung fuer genau diese Provinz, WHEN fuer die Nachbarstadt abgerufen wird, THEN erhaelt sie
    die belgische Warnung genau EINMAL und keinen Ausfallhinweis; eine Warnung einer anderen Provinz
    bleibt dort stumm (Kontrolle). Aendert sich die Aufweitung, faellt dieser Test bewusst auf."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    assert _quelle().covers(*punkt) is True, f"Kontrolle: {name} liegt im Randstreifen"
    zonen = set(meteoalarm_feed._zone_mappers["BE"].regions_at(*punkt))
    assert zonen == {zone}, f"Kontrolle: {name} muss genau in {zone} liegen: {zonen}"
    assert _TABELLE[nuts2] == zone

    def _feed_fuer(code: str) -> dict:
        feed = _teil("SYNTH-BE23")
        for info in _eintrag(feed, "SYNTH-BE23")["info"]:
            info["area"][0]["geocode"] = [{"valueName": "NUTS2", "value": code}]
        return feed

    feed = _feed_fuer(nuts2)
    alerts, unavailable = _abruf(punkt, feed)
    assert len(alerts) == 1 and unavailable is False, (alerts, unavailable)
    direkt, status = _direkt(punkt, feed)
    assert len(direkt) == 1 and status["failed"] is False, (direkt, status)

    kontrolle, unavailable = _abruf(punkt, _feed_fuer(fremd_nuts2))
    assert kontrolle == [] and unavailable is False, kontrolle


# ───────────────────────────── AC-3 (Test 3) ─────────────────────────────────

def test_ac3_arlon_und_benannte_orte_abgedeckt():
    """AC-3: GIVEN die eingecheckte Zonengeometrie (um 0,1 Grad aufgeweitet), WHEN Arlon (roh in
    keiner Zone) und die benannten Orte geprueft werden, THEN liegt jeder in mindestens einer Zone;
    Arlon ausdruecklich in BE001."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    mapper = meteoalarm_feed._zone_mappers["BE"]
    assert "BE001" in mapper.regions_at(*ARLON), mapper.regions_at(*ARLON)
    for name, punkt in [("bruessel", BRUESSEL), ("leuven", LEUVEN), ("wavre", WAVRE), ("eupen", EUPEN),
                        ("bastogne", BASTOGNE), ("bouillon", BOUILLON), ("virton", VIRTON),
                        ("gent", GENT), ("namur", NAMUR)]:
        assert mapper.regions_at(*punkt), f"{name} {punkt} liegt in keiner Zone"
    for name, punkt in _KUESTE:
        assert mapper.regions_at(*punkt), f"{name} {punkt} liegt in keiner Zone"


# Grober, bewusst NACH INNEN gezogener Umriss des belgischen Landgebiets (lon, lat). Er ist kein
# amtlicher Umriss (die Landmaske liegt nicht im Repo, GISCO ist nicht nutzbar, Spec Punkt 7), sondern
# eine Test-Stichprobe: gefragt ist, ob INNERHALB des Landes Luecken zwischen den Zonen klaffen.
_LAND_UMRISS = [
    (2.70, 51.10), (3.30, 51.33), (3.60, 51.28), (3.85, 51.22), (4.20, 51.35), (4.40, 51.40),
    (4.75, 51.42), (5.05, 51.45), (5.50, 51.25), (5.70, 51.05), (5.75, 50.80), (6.00, 50.75),
    (6.20, 50.60), (6.20, 50.45), (6.10, 50.15), (5.90, 50.05), (5.80, 49.80), (5.70, 49.60),
    (5.50, 49.55), (5.25, 49.65), (5.00, 49.80), (4.85, 49.95), (4.70, 50.10), (4.45, 50.15),
    (4.20, 50.25), (3.95, 50.35), (3.65, 50.45), (3.40, 50.50), (3.20, 50.70), (2.90, 50.74),
    (2.70, 50.80),
]


def _im_umriss(lat: float, lon: float) -> bool:
    drin = False
    n = len(_LAND_UMRISS)
    for i in range(n):
        x1, y1 = _LAND_UMRISS[i]
        x2, y2 = _LAND_UMRISS[(i + 1) % n]
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            drin = not drin
    return drin


def test_ac3_landgitter_luecken_hoechstens_0_1_prozent():
    """AC-3: GIVEN ein Gitter von 0,01 Grad ueber das belgische Landgebiet (Test-Umriss, nach innen
    gezogen), WHEN jeder Punkt gegen die Zonendatei geprueft wird, THEN liegen hoechstens 0,1 % der
    Punkte in keiner Zone (Spec Punkt 7: Messwert 0,03 % mit 0,1 Grad Aufweitung)."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    mapper = meteoalarm_feed._zone_mappers["BE"]
    gesamt = luecken = 0
    for i in range(0, 220):
        lat = 49.5 + i * 0.01
        for j in range(0, 380):
            lon = 2.6 + j * 0.01
            if not _im_umriss(lat, lon):
                continue
            gesamt += 1
            if not mapper.regions_at(lat, lon):
                luecken += 1
    assert gesamt > 20000, f"Gitter zu klein: {gesamt}"
    assert luecken / gesamt <= 0.001, f"{luecken} von {gesamt} Landpunkten ohne Zone ({luecken / gesamt:.3%})"


# ───────────────────────────── AC-4 (Test 4) ─────────────────────────────────

def test_ac4_nuts2_only_trifft_nur_die_provinz():
    """AC-4: GIVEN eine aus der ECHTEN BE23-Warnung 1618968 abgeleitete Warnung (``SYNTH-BE23``: nur
    ``NUTS2 = BE23``, Oost-Vlaanderen, Typ Wind statt des verworfenen Kuesten-Typs), WHEN fuer Gent
    abgerufen wird, THEN erscheint sie mit Stufe, Ereignisart und Zeitraum; fuer Namur, Eupen und Virton
    (andere Provinzen) erscheint sie nicht, ohne Ausfallhinweis."""
    _assert_pruefling_aus_diesem_baum()
    suffix = "SYNTH-BE23"
    feed = _teil(suffix)
    eintrag = _eintrag(feed, suffix)
    echt = _eintrag(_feed(), "20261024195121.1618968")
    assert [g["valueName"] for i in echt["info"] for a in i["area"] for g in a["geocode"]] == ["NUTS2"] * 4
    assert [g["valueName"] for i in eintrag["info"] for a in i["area"] for g in a["geocode"]] == ["NUTS2"] * 4
    assert {g["value"] for i in eintrag["info"] for a in i["area"] for g in a["geocode"]} == {"BE23"}
    von, bis = _zeitraum(feed, suffix)
    assert von <= _NOW < bis, "Kontrolle: Warnung ist zum Referenzzeitpunkt gueltig"

    assert _quelle().covers(*GENT) is True
    alerts, unavailable = _abruf(GENT, feed)
    assert len(alerts) == 1, alerts
    assert alerts[0].level == 2 and alerts[0].source == "meteoalarm"
    assert alerts[0].hazard == "wind_gust"
    assert alerts[0].label and alerts[0].region_label
    assert (alerts[0].valid_from, alerts[0].valid_to) == (von, bis)
    assert unavailable is False
    for name, punkt in [("namur", NAMUR), ("eupen", EUPEN), ("virton", VIRTON)]:
        assert _quelle().covers(*punkt) is True
        fremd, unavailable = _abruf(punkt, feed)
        assert fremd == [] and unavailable is False, (name, fremd)


@pytest.mark.parametrize("suffix,punkt,now", [
    ("20261024195121.1618968", GENT, _NOW_ECHT),      # echte Kuestenwarnung, NUTS2 BE23
    ("20261024195121.1618969", (51.22, 4.40), _NOW_ECHT),  # echte Kuestenwarnung, NUTS2 BE21 (Antwerpen)
    ("20261031060158.1619001", GENT, _NOW),           # echte Nebelwarnung, NUTS2 BE23
    ("20261031060158.1618999", OSTENDE, _NOW),        # echte Nebelwarnung, EMMA_ID BE801
    ("20261031060158.1619004", BRUESSEL, _NOW),       # echte Nebelwarnung, EMMA_ID BE004
])
def test_ac4_echte_kuesten_und_nebelwarnungen_verwirft_der_mapper(suffix, punkt, now):
    """AC-4 (#1430): GIVEN eine ECHTE belgische Kuesten- (Typ 7) bzw. Nebelwarnung (Typ 4) aus der Probe,
    WHEN fuer einen Ort in ihrer Zone abgerufen wird, THEN erscheint sie nicht (Typ bewusst nicht
    unterstuetzt) und es entsteht kein Ausfallhinweis. Gegenprobe: derselbe Eintrag mit Typ Wind erscheint
    dort -- die Zone wird also getroffen, verworfen wird allein wegen des Typs."""
    _assert_pruefling_aus_diesem_baum()
    feed = _teil(suffix)
    eintrag = _eintrag(feed, suffix)
    assert ".SYNTH-" not in eintrag["identifier"], "muss die echte Probe sein"
    typen = {p["value"] for i in eintrag["info"] for p in i["parameter"] if p["valueName"] == "awareness_type"}
    assert typen in ({"7; coastalevent"}, {"4; Fog"}), typen
    von, bis = _zeitraum(feed, suffix)
    assert von <= now < bis, "Kontrolle: Warnung ist zum Referenzzeitpunkt gueltig"
    assert _quelle().covers(*punkt) is True
    alerts, unavailable = _abruf(punkt, feed, now)
    assert alerts == [] and unavailable is False, (suffix, alerts, unavailable)

    for info in eintrag["info"]:
        for p in info["parameter"]:
            if p["valueName"] == "awareness_type":
                p["value"] = "1; wind"
    gegenprobe, unavailable = _abruf(punkt, feed, now)
    assert len(gegenprobe) == 1 and gegenprobe[0].level == 2 and unavailable is False, (suffix, gegenprobe)


# ───────────────────────────── AC-5 (Test 5) ─────────────────────────────────

@pytest.mark.parametrize("name,punkt", _BRABANT)
def test_ac5_emma_id_warnungen_bruessel_und_kueste_brabant(name, punkt):
    """AC-5: GIVEN eine Warnung mit ``EMMA_ID = BE004`` (orange), WHEN fuer Bruessel, Leuven bzw. Wavre
    abgerufen wird, THEN erscheint sie mit Stufe, Ereignisart und Zeitraum."""
    _assert_pruefling_aus_diesem_baum()
    feed = _teil("SYNTH-BE004-ORANGE")
    von, bis = _zeitraum(feed, "SYNTH-BE004-ORANGE")
    assert _quelle().covers(*punkt) is True
    alerts, unavailable = _abruf(punkt, feed)
    assert len(alerts) == 1 and alerts[0].level == 3, alerts
    assert alerts[0].label and alerts[0].hazard
    assert (alerts[0].valid_from, alerts[0].valid_to) == (von, bis)
    assert unavailable is False


@pytest.mark.parametrize("name,punkt", _KUESTE)
def test_ac5_emma_id_warnungen_kueste(name, punkt):
    """AC-5: GIVEN eine Warnung mit ``EMMA_ID = BE801`` (Kuestenstreifen), WHEN fuer Ostende, Knokke
    bzw. die Kueste abgerufen wird, THEN erscheint sie; Gent (nicht an der Kueste) bekommt sie nicht."""
    _assert_pruefling_aus_diesem_baum()
    feed = _teil("SYNTH-BE801")
    assert _quelle().covers(*punkt) is True
    alerts, unavailable = _abruf(punkt, feed)
    assert len(alerts) == 1 and alerts[0].level == 2, alerts
    assert unavailable is False
    assert _abruf(BRUESSEL, feed)[0] == []


# ───────────────────────────── AC-6 (Test 6) ─────────────────────────────────

@pytest.mark.parametrize("suffix", ["SYNTH-BE24", "SYNTH-BE10", "SYNTH-BE31"])
@pytest.mark.parametrize("name,punkt", _BRABANT)
def test_ac6_brabant_tabelle_bruessel_leuven_wavre(name, punkt, suffix):
    """AC-6: GIVEN eine Warnung mit ``NUTS2`` BE24, BE10 bzw. BE31 (alle -> EMMA BE004), WHEN fuer
    Bruessel, Leuven bzw. Wavre abgerufen wird, THEN erscheint sie dort -- nicht aber in Gent."""
    _assert_pruefling_aus_diesem_baum()
    feed = _teil(suffix)
    alerts, unavailable = _abruf(punkt, feed)
    assert len(alerts) == 1 and unavailable is False, (suffix, alerts)
    gent, unavailable = _abruf(GENT, feed)
    assert gent == [] and unavailable is False, gent


# ───────────────────────────── AC-7 (Test 7) ─────────────────────────────────

def test_ac7_doppelkennung_genau_einmal():
    """AC-7: GIVEN eine Warnung traegt ``NUTS2 = BE10`` UND ``EMMA_ID = BE004`` (beide -> BE004), WHEN
    fuer Bruessel abgerufen wird, THEN genau einmal -- auch direkt an der Quelle."""
    _assert_pruefling_aus_diesem_baum()
    feed = _teil("SYNTH-BE10-UND-BE004")
    alerts, unavailable = _abruf(BRUESSEL, feed)
    assert len(alerts) == 1 and unavailable is False, alerts
    direkt, status = _direkt(BRUESSEL, feed)
    assert len(direkt) == 1 and status["failed"] is False, (direkt, status)


def test_ac7_ueberlappende_zonen_genau_einmal():
    """AC-7: GIVEN ein Punkt liegt durch die Aufweitung in zwei Zonen (Mechelen: BE002 und BE004) und
    eine Warnung traegt beide Provinzen (``NUTS2`` BE21 und BE24), WHEN abgerufen wird, THEN erscheint
    sie genau einmal -- auch direkt an der Quelle."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    zonen = set(meteoalarm_feed._zone_mappers["BE"].regions_at(*MECHELEN))
    assert {"BE002", "BE004"} <= zonen, f"Kontrolle: Mechelen muss in beiden Zonen liegen: {zonen}"
    feed = _teil("SYNTH-BE24")
    for info in _eintrag(feed, "SYNTH-BE24")["info"]:
        info["area"][0]["geocode"].append({"valueName": "NUTS2", "value": "BE21"})
    alerts, unavailable = _abruf(MECHELEN, feed)
    assert len(alerts) == 1 and unavailable is False, alerts
    direkt, _status = _direkt(MECHELEN, feed)
    assert len(direkt) == 1, f"jede Warnung genau EINMAL erwartet, erhalten {direkt}"


# ───────────────────────────── AC-8 (Test 8) ─────────────────────────────────

def test_ac8_echtes_gruenes_update_erzeugt_nichts():
    """AC-8: GIVEN die Probe fuehrt ein ECHTES ``Update`` (BE004, Stufe gruen, Vorgaenger nicht mehr im
    Feed), WHEN fuer Bruessel abgerufen wird, THEN entsteht keine Warnung und kein Ausfallhinweis."""
    _assert_pruefling_aus_diesem_baum()
    echt = _eintrag(_feed(), "20261031070505.1619011")
    assert echt["msgType"] == "Update" and ".SYNTH-" not in echt["identifier"]
    assert _quelle().covers(*BRUESSEL) is True, "Positivkontrolle: Quelle ist zustaendig"
    alerts, unavailable = _abruf(BRUESSEL, _teil("20261031070505.1619011"))
    assert alerts == [] and unavailable is False, alerts


def test_ac8_update_ersetzt_vorgaenger_genau_einmal():
    """AC-8: GIVEN eine gelbe Warnung und ihr oranges ``Update`` (``references`` auf die gelbe) stehen
    beide im Feed, WHEN fuer Gent abgerufen wird, THEN erscheint nur die aktualisierte Fassung, genau
    einmal -- auch direkt an der Quelle."""
    _assert_pruefling_aus_diesem_baum()
    feed = _teil("SYNTH-UPD-ALT-BE23", "SYNTH-UPD-NEU-BE23")
    kontrolle, _ = _abruf(GENT, _teil("SYNTH-UPD-ALT-BE23"))
    assert [a.level for a in kontrolle] == [2], "Kontrolle: ohne Update ist die gelbe Fassung aktiv"
    assert _quelle().covers(*GENT) is True
    alerts, unavailable = _abruf(GENT, feed)
    assert [a.level for a in alerts] == [3], f"nur das Update erwartet: {alerts}"
    assert unavailable is False
    direkt, _status = _direkt(GENT, feed)
    assert [a.level for a in direkt] == [3], f"ersetzte Fassung darf nicht zusaetzlich kommen: {direkt}"


def test_ac8_cancel_nimmt_warnung_zurueck():
    """AC-8: GIVEN eine Warnung und ihr CAP-konformer Rueckzug (``msgType`` Cancel, ohne ``info``,
    ``references`` auf sie), WHEN fuer Gent abgerufen wird, THEN erscheint die aufgehobene Warnung nicht
    als aktiv, ohne Ausfallhinweis."""
    _assert_pruefling_aus_diesem_baum()
    assert "info" not in _eintrag(_feed(), "SYNTH-CANCEL-BE23")
    kontrolle, _ = _abruf(GENT, _teil("SYNTH-CANCEL-ALT-BE23"))
    assert len(kontrolle) == 1, f"Kontrolle: ohne Rueckzug ist die Warnung aktiv: {kontrolle}"
    alerts, unavailable = _abruf(GENT, _teil("SYNTH-CANCEL-ALT-BE23", "SYNTH-CANCEL-BE23"))
    assert alerts == [], f"aufgehobene Warnung darf nicht erscheinen: {alerts}"
    assert unavailable is False


# ───────────────────────────── AC-9 (Test 9) ─────────────────────────────────

def test_ac9_unbekannter_nuts2_code_kein_ausfall_aber_drift(tmp_path, monkeypatch):
    """AC-9: GIVEN eine Warnung traegt einen NUTS2-Code, der nicht in der Tabelle steht (BE99), WHEN fuer
    belgische Punkte abgerufen wird, THEN kein Ausfallhinweis, der Ort mit eigener Warnung (Gent) behaelt
    sie, und der Code steht als ``unknown_zone`` (``meteoalarm_feed:BE``) im Journal -- und NUR er: die
    in der Tabelle bekannten Codes (BE10/BE24/BE31 ...) loesen keinen Drift aus."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import warn_egress

    journal = tmp_path / "warn.jsonl"
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH_OVERRIDE", journal)
    feed = _feed()
    assert _quelle().covers(*GENT) is True
    gent, unavailable = _abruf(GENT, feed)
    assert gent and unavailable is False, (gent, unavailable)
    bruessel, unavailable = _abruf(BRUESSEL, feed)
    assert bruessel and unavailable is False, (bruessel, unavailable)
    zeilen = [json.loads(z) for z in journal.read_text(encoding="utf-8").splitlines()]
    drift = {z.get("zone_code") for z in zeilen
             if z.get("service") == "meteoalarm_feed:BE" and z.get("drift") == "unknown_zone"}
    assert drift == {"BE99"}, zeilen


# ───────────────────────────── AC-10 (Test 10) ───────────────────────────────

def test_ac10_feed_ohne_kennung_meldet_nicht_abrufbar():
    """AC-10: GIVEN der Feed enthaelt keinen einzigen Eintrag mit auswertbarer Kennung, WHEN fuer einen
    belgischen Punkt abgerufen wird, THEN ``unavailable=True`` statt einer scheinbar ruhigen Lage."""
    _assert_pruefling_aus_diesem_baum()
    feed = _teil("SYNTH-BE23", "SYNTH-BE801")
    for w in feed["warnings"]:
        for info in w["alert"]["info"]:
            for area in info["area"]:
                area["geocode"] = []
    assert _quelle().covers(*GENT) is True
    alerts, unavailable = _abruf(GENT, feed)
    assert alerts == [] and unavailable is True


def test_ac10_ausfall_meldet_nicht_abrufbar():
    """AC-10: GIVEN der Feed-Abruf ist gescheitert, WHEN fuer einen belgischen Punkt abgerufen wird,
    THEN ``unavailable=True`` statt einer scheinbar warnungsfreien Lage."""
    _assert_pruefling_aus_diesem_baum()
    assert _quelle().covers(*GENT) is True
    alerts, unavailable = _abruf(GENT, None)
    assert alerts == [] and unavailable is True


def test_ac10_einzelner_kaputter_eintrag_faerbt_nicht_ein():
    """AC-10: GIVEN ein einzelner Eintrag ohne awareness-Parameter (Zone BE22) steht VOR lesbaren
    Eintraegen, WHEN fuer Gent (gewarnt) und Namur (ruhig) abgerufen wird, THEN behaelt Gent seine
    Warnung, Namur bleibt ruhig, und kein Ort wird als Ausfall gemeldet."""
    _assert_pruefling_aus_diesem_baum()
    kaputt = _teil("SYNTH-BE99")["warnings"][0]
    kaputt["alert"]["identifier"] += "-KAPUTT"
    for info in kaputt["alert"]["info"]:
        info["parameter"] = []
        info["area"][0]["geocode"] = [{"valueName": "NUTS2", "value": "BE22"}]
    feed = {"warnings": [kaputt] + _teil("SYNTH-BE23")["warnings"]}
    gent, unavailable = _abruf(GENT, feed)
    assert len(gent) == 1 and unavailable is False, (gent, unavailable)
    namur, unavailable = _abruf(NAMUR, feed)
    assert namur == [] and unavailable is False, (namur, unavailable)


# ───────────────────────────── AC-11 (Test 11) ───────────────────────────────

def test_ac11_text_aus_de_de_sonst_en_gb():
    """AC-11: GIVEN der Eintrag fuehrt ``nl-BE``, ``fr-BE``, ``en-GB`` und ``de-DE``, WHEN die Warnung
    ausgegeben wird, THEN stammt der Text aus ``de-DE``; fehlt ``de-DE``, aus ``en-GB`` -- nie leer."""
    _assert_pruefling_aus_diesem_baum()
    feed = _teil("SYNTH-BE23")
    eintrag = _eintrag(feed, "SYNTH-BE23")
    sprachen = {i["language"]: i for i in eintrag["info"]}
    assert set(sprachen) == {"nl-BE", "fr-BE", "en-GB", "de-DE"}
    assert len({sprachen[s]["event"] for s in sprachen}) == 4, "Kontrolle: Texte je Sprache verschieden"
    direkt, _status = _direkt(GENT, feed)
    assert [a.label for a in direkt] == [sprachen["de-DE"]["event"]], direkt

    eintrag["info"] = [i for i in eintrag["info"] if i["language"] != "de-DE"]
    direkt, _status = _direkt(GENT, feed)
    assert [a.label for a in direkt] == [sprachen["en-GB"]["event"]], direkt
    assert direkt[0].label


# ───────────────────────────── AC-12 (Test 12) ───────────────────────────────

@pytest.mark.parametrize("land,punkt", [
    ("NL", AMSTERDAM), ("PL", (52.23, 21.01)), ("PT", (38.72, -9.14)),
    ("FI", (60.17, 24.94)), ("ES", (40.42, -3.70)),
])
def test_ac12_nuts2_wird_nur_fuer_belgien_uebersetzt(land, punkt):
    """AC-12 (Golden Master, darf schon jetzt GRUEN sein): GIVEN der Feed eines ANDEREN Zonenlands traegt
    einen Eintrag mit ``NUTS2 = BE23`` und sonst keine Kennung, WHEN abgerufen wird, THEN wird der Code
    NICHT ueber die Belgien-Tabelle uebersetzt: der Eintrag bleibt ohne auswertbare Kennung
    (``unavailable=True``, wie vor S3c) statt als "andere Zone" zu gelten."""
    _assert_pruefling_aus_diesem_baum()
    feed = _teil("SYNTH-BE23")
    for info in _eintrag(feed, "SYNTH-BE23")["info"]:
        info["area"][0]["geocode"] = [{"valueName": "NUTS2", "value": "BE23"}]
    _feed_vorbelegen(land, feed)
    quelle = _quelle(land)
    assert quelle.covers(*punkt) is True, f"{land}-Quelle muss hier zustaendig sein"
    from services.official_alerts import get_official_alerts_with_status

    with _nur_quellen(quelle):
        alerts, unavailable = get_official_alerts_with_status(*punkt, now=_NOW)
    assert alerts == [] and unavailable is True, (land, alerts, unavailable)


def test_ac12_bestehende_laenderpfade_unveraendert():
    """AC-12 (Golden Master, darf schon jetzt GRUEN sein): Feedpfade und Geocode-Arten aller
    bisherigen Laender bleiben unveraendert."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    erwartet = {"IT": "italy", "AT": "austria", "DE": "germany", "CH": "switzerland", "NO": "norway",
                "SE": "sweden", "FI": "finland", "ES": "spain", "PT": "portugal",
                "NL": "netherlands", "PL": "poland", "GB": "united-kingdom"}
    for land, name in erwartet.items():
        assert meteoalarm_feed._FEED_PATHS[land] == f"/api/v1/warnings/feeds-{name}", land
    assert meteoalarm_feed._GEOCODE_NAME["DE"] == "WARNCELLID"
    for land in ("IT", "AT", "FI", "ES", "PT", "NL", "PL"):
        assert meteoalarm_feed._GEOCODE_NAME[land] == "EMMA_ID", land


# ───────────────────────────── AC-13 (Test 13) ───────────────────────────────

def test_ac13_registrierung_be_nach_gb_vor_dpc():
    """AC-13: in der ECHTEN Registry steht je genau EINE BE-Quelle in der Reihenfolge NL < PL < GB < BE
    < ``DpcSource`` (Gewitter-Tie-Break, #1427 S2)."""
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
    assert pos("NL") < pos("PL") < pos("GB") < pos("BE") < dpc[0]


def test_ac13_maastricht_keine_doppelwarnung():
    """AC-13: GIVEN Maastricht (Grenzfall: durch die Aufweitung kann ``covers()`` fuer NL UND BE wahr
    sein), die NL-Quelle fuehrt dort eine Warnung (NL012, SYNTH) und der belgische Feed keine fuer
    BE007/BE008, WHEN mit beiden Quellen abgerufen wird, THEN erscheint genau diese eine Warnung, und
    die belgische Quelle liefert dort weder Warnung noch Ausfallhinweis."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import get_official_alerts_with_status, warn_egress

    nl_feed = json.loads((_FIXTURES / "feed_netherlands_sample.json").read_text(encoding="utf-8"))
    nl_now = datetime(2026, 10, 31, 9, 0, tzinfo=timezone.utc)
    assert _quelle("NL").covers(*MAASTRICHT) is True
    _feed_vorbelegen("NL", nl_feed)
    _feed_vorbelegen("BE", _teil("SYNTH-BE23"))
    with _nur_quellen(_quelle("NL"), _quelle("BE")):
        alerts, unavailable = get_official_alerts_with_status(*MAASTRICHT, now=nl_now)
    assert len(alerts) == 1 and unavailable is False, alerts
    with warn_egress.observe_fetch_failure() as status:
        aus_be = list(_quelle("BE").fetch(*MAASTRICHT))
    assert aus_be == [] and status["failed"] is False, (aus_be, status)


# ───────────────────────────── AC-14 (Test 14) ───────────────────────────────

def test_ac14_zonendatei_zehn_zonen():
    """AC-14: GIVEN die Datenhaltung der belgischen Zonen, WHEN die Datei geprueft wird, THEN enthaelt
    ``meteoalarm_zones_BE.geojson.json`` genau BE001-BE009 und BE801 mit ``properties.id``/``name``, ist
    kleiner als 400 KB, und der ``RegionMapper`` laedt alle Zonen."""
    from services.official_alerts.region_mapper import RegionMapper

    assert _ZONEN_DATEI.is_file(), f"Zonendatei fehlt: {_ZONEN_DATEI}"
    assert _ZONEN_DATEI.stat().st_size < 400 * 1024, _ZONEN_DATEI.stat().st_size
    features = json.loads(_ZONEN_DATEI.read_text(encoding="utf-8"))["features"]
    ids = [f["properties"].get("id", "") for f in features]
    assert sorted(ids) == sorted(_ZONEN), ids
    assert all(f["properties"].get("name") for f in features)
    namen = {f["properties"]["id"]: f["properties"]["name"] for f in features}
    for zone, name in _ZONEN.items():
        if name is not None:
            assert namen[zone] == name, (zone, namen[zone])
    assert {rid for rid, _geo, _box in RegionMapper(_ZONEN_DATEI)._loaded()} == set(ids)


def test_ac14_tabelle_und_feed_zonen_stehen_in_der_datei():
    """AC-14: GIVEN die Zuordnungstabelle NUTS2 -> EMMA und die Probe, WHEN sie gegen die Zonendatei
    geprueft werden, THEN entspricht die Tabelle der Spec, jeder Tabellenwert und jede aus der Probe
    uebersetzte Zonen-ID (ausser dem bewusst unbekannten BE99) steht in der Datei."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    assert meteoalarm_feed._BE_NUTS2_TO_EMMA == _TABELLE
    assert _ZONEN_DATEI.is_file(), f"Zonendatei fehlt: {_ZONEN_DATEI}"
    ids = {f["properties"]["id"] for f in json.loads(_ZONEN_DATEI.read_text(encoding="utf-8"))["features"]}
    assert set(_TABELLE.values()) <= ids
    kennungen = {(g["valueName"], g["value"]) for w in _feed()["warnings"]
                 for i in w["alert"].get("info") or [] for a in i["area"] for g in a["geocode"]}
    uebersetzt = {_TABELLE.get(v, v) if n == "NUTS2" else v for n, v in kennungen} - {"BE99"}
    assert uebersetzt <= ids, f"Feed-Zonen ohne Geometrie: {sorted(uebersetzt - ids)}"


def test_ac14_readme_und_data_sources_dokumentieren_belgien():  # doc-compliance-test
    """AC-14: GIVEN die Dokumentation, WHEN sie geprueft wird, THEN steht im Abschnitt BE von
    ``data/README.md`` Herkunft/sha256, Aufweitung 0,1 Grad, Zuordnungstabelle und der Verzicht auf
    GISCO mit Lizenzbegruendung; ``docs/specs/data_sources.md`` fuehrt BE im Lizenzantrag und den
    GISCO-Vermerk. Es wird keine GISCO-Geometrie eingecheckt."""
    readme = (_DATA / "README.md").read_text(encoding="utf-8")
    treffer = re.search(r"^#+ .*(Belgien|\bBE\b).*$", readme, re.MULTILINE)
    assert treffer, "Abschnitt BE in data/README.md fehlt"
    abschnitt = readme[treffer.start():]
    naechster = re.search(r"^## ", abschnitt[3:], re.MULTILINE)
    if naechster:
        abschnitt = abschnitt[:naechster.start() + 3]
    for pflicht in ("0c8fe7b9af4f86c72f1c28bb9cea02f673fee6d45d02681713e6ad3ebd615dd0", "0,1",
                    "NUTS2", "BE004", "GISCO", "nicht-kommerziell"):
        assert pflicht in abschnitt, f"README-Abschnitt BE nennt {pflicht!r} nicht"
    quellen = (_REPO_ROOT / "docs" / "specs" / "data_sources.md").read_text(encoding="utf-8")
    assert "GISCO" in quellen and re.search(r"BE\b|Belgien", quellen)
    assert not list(_DATA.glob("*gisco*")) and not list(_DATA.glob("*nuts*"))


# ───────────────────────────── AC-15 (Test 15) ───────────────────────────────

@pytest.mark.parametrize("art", ["route", "vergleich"])
def test_ac15_warnung_erreicht_dieselben_kanaele_wie_at(art, premium_nutzer):  # noqa: F811
    """AC-15: GIVEN eine orange BE-Warnung (EMMA BE004, Bruessel) und eine orange AT-Warnung (Hitze Wien),
    UND ein Trip bzw. Ortsvergleich mit Empfaengern auf allen vier Kanaelen, WHEN die geteilte
    Alarm-Kanal-Aufloesung laeuft, THEN erreicht die Warnung dieselbe Kanalmenge wie die AT-Warnung."""
    _assert_pruefling_aus_diesem_baum()
    _feed_vorbelegen("BE", _feed())
    _feed_vorbelegen("AT", _feed_at())
    _zamg_gemeinde(*WIEN, 90101, "Wien")

    at_orange = [a for a in _quelle("AT").fetch(*WIEN) if a.level == 3]
    assert at_orange, "Kontrolle: orange AT-Warnung (Wien) aus der AT-Stichprobe"
    assert _quelle().covers(*BRUESSEL) is True
    orange = [a for a in _quelle().fetch(*BRUESSEL) if a.level == 3]
    assert orange, "orange BE-Warnung muss aus dem Feed entstehen"

    abo = _abo(art)
    k_be = _kanaele_fuer(orange[0], abo, premium_nutzer)
    k_at = _kanaele_fuer(at_orange[0], abo, premium_nutzer)
    assert k_be == k_at == _ALL_CHANNELS, (k_be, k_at)
