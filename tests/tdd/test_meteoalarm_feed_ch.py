"""TDD RED -- MeteoAlarm Schweiz: MeteoSchweiz-Warnungen aus dem kontingentfreien
Feed (Issue #1442, Scheibe S1).

SPEC: docs/specs/modules/feat_1442_s1_meteoalarm_ch.md ("## Acceptance Criteria",
AC-1 bis AC-11; Test Plan Test 1-12)

AC -> Testfunktion (AC-11 / Test 12 Live: eigene Datei ``test_meteoalarm_feed_ch_live.py``):

- AC-1  (Test 1)  ``test_ac1_feedpfad_und_registrierung``,
                  ``test_ac1_punkt_in_gewarnter_gemeinde_liefert_warnung_mit_stufe_art_zeitraum``
- AC-2  (Test 2)  ``test_ac2_schweizer_punkt_ohne_treffer_polygon_leer_ohne_ausfallhinweis``
- AC-3  (Test 3)  ``test_ac3_ch_feed_ausfall_meldet_nicht_abrufbar``
- AC-4  (Test 4)  ``test_ac4_schweizer_rand_und_grenzpunkte_sind_zustaendig``,
                  ``test_ac4_nachbarland_punkte_nicht_zustaendig_ohne_ausfallhinweis``,
                  ``test_ac4_fallback_punkt_ausserhalb_slf_aber_im_feed_polygon_ist_zustaendig``
- AC-5  (Test 5/6) ``test_ac5_cancel_nimmt_die_warnung_zurueck``,
                  ``test_ac5_update_ersetzt_die_vorgaengerwarnung_genau_einmal``,
                  ``test_ac5_aufgezeichnete_allclear_update_erscheint_nicht_als_warnung``
- AC-6  (Test 7)  ``test_ac6_hoehenband_wird_ignoriert``
- AC-7  (Test 8)  ``test_ac7_feedwarnung_und_slf_lawine_getrennt_registrierungsreihenfolge``
- AC-8  (Test 9)  ``test_ac8_ch_warnung_erreicht_dieselben_kanaele_wie_at``
- AC-9  (Test 10) ``test_ac9_andersfoermiger_eintrag_faerbt_andere_orte_nicht_als_ausfall``
- AC-10 (Test 11) ``test_ac10_bestehende_laenderpfade_unveraendert`` (darf schon jetzt GRUEN
                  sein -- Regressions-Golden-Master; zusaetzlich laufen die IT/AT/DE-Testdateien
                  unveraendert).
- Mehrfachring/Loch (Spec Impl. Details 1): ``test_loch_im_polygon_ist_keine_warnung``

RED-Ursachen (bewusst, fachlich): ``MeteoAlarmFeedSource("CH")`` laesst sich heute zwar
konstruieren (``Literal`` ist nur ein Typhinweis), faellt aber in den italienischen Zweig --
``covers()`` ist fuer JEDEN Schweizer Punkt ``False`` bzw. ``fetch()`` meldet
``point_unmapped``. ``_FEED_PATHS["CH"]`` und die Registrierung fehlen, ``references`` (Cancel/
Update) werden nirgends ausgewertet. Jeder Test, der sonst "zufaellig" gruen waere (leere Liste
bei nicht zustaendiger Quelle), traegt eine Positivkontrolle (``covers(...) is True``).

Kein Mock-Theater, kein Netz (Kern-Schicht, laeuft mit ``--disable-socket``): wie
``test_meteoalarm_feed_deutschland.py`` wird der Modul-Cache mit dem ECHTEN aufgezeichneten Feed
vorbelegt, ``fetch()`` laeuft ueber den echten Cache-Treffer-Zweig von
``warn_egress.cached_fetch()``.

Fixture: ``tests/fixtures/meteoalarm_feed/feed_switzerland_sample.json`` -- 8 reale, unveraenderte
Eintraege aus dem Vollabruf vom 2026-10-29 (131 Eintraege) plus 4 SYNTHETISCHE Eintraege
(Kennung ``.SYNTH-*``): Cancel, Update (Stufe orange), Loch-Gebiet, unlesbares Polygon.
Herkunft und Auswahl: README.md im selben Verzeichnis.
"""
from __future__ import annotations

import copy
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

# Punkte (Gemeinde-/Warnregion laut Fixture, per Ray-Cast gegen den Vollabruf 2026-10-29 geprueft)
ZUERICH = (47.3769, 8.5417)       # Thalwil-Wetzikon: gelber Wind
BERN = (46.9481, 7.4474)          # Bern-Sense: gelber Wind
LUZERN = (47.0502, 8.3093)        # Luzern-Alpnach: gelber Wind; SLF-Region CH-2112 (bewertet)
INTERLAKEN = (46.6863, 7.8632)    # Brienz-Interlaken: gelber Wind + SYNTH-Update (orange)
BASEL = (47.5596, 7.5886)         # Basel: gelber Wind + echtes AllClear-Update (gruen)
SARGANS = (47.0490, 9.4420)       # Sarganserland: gelber Wind + SYNTH-Cancel
MENDRISIO = (45.9376, 9.0221)     # Mendrisiotto: Bodenfrost 0-600 m; AUSSERHALB der SLF-Regionen
LUGANO = (46.0037, 8.9511)        # Luganese: im Fixture bewusst OHNE Polygon
LOCH_AUSSEN = (46.57, 8.25)       # synthetisches Lochgebiet: im Aussenring
LOCH_INNEN = (46.60, 8.30)        # synthetisches Lochgebiet: im Innenring (= Loch)

CH_RAND_PUNKTE = {
    "Zuerich": ZUERICH, "Bern": BERN, "Lugano": LUGANO, "Davos": (46.8027, 9.8360),
    "Chiasso": (45.8324, 9.0295), "Basel": BASEL, "Genf": (46.2044, 6.1432),
    "Schaffhausen": (47.6960, 8.6340), "Muestair": (46.6280, 10.4540),
    "Samnaun": (46.9480, 10.3680), "Sargans": SARGANS, "Brig": (46.3150, 7.9880),
    "Disentis": (46.7020, 8.8510), "Porrentruy": (47.4150, 7.0750),
    "St-Gingolph": (46.3935, 6.8085),
}
NACHBAR_PUNKTE = {
    "Konstanz": (47.6779, 9.1732), "Bregenz": (47.5031, 9.7471), "Como": (45.8081, 9.0852),
    "Chamonix": (45.9237, 6.8694), "Loerrach": (47.6140, 7.6610),
    "Feldkirch": (47.2397, 9.5981), "Mulhouse": (47.7508, 7.3359),
}
WIEN = (48.2082, 16.3738)         # ZAMG gemeindenr 90101 -> AT901

# Wind-Warnungen: onset 05:00Z, expires 19:00Z am 25.10. (Basel 02:00-17:00Z).
TEST_NOW_WIND = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
WIND_VON = datetime(2026, 10, 25, 5, 0, tzinfo=timezone.utc)
WIND_BIS = datetime(2026, 10, 25, 19, 0, tzinfo=timezone.utc)
# Bodenfrost Mendrisiotto: onset 28.10. 23:00Z, expires 29.10. 07:00Z.
TEST_NOW_FROST = datetime(2026, 10, 29, 2, 0, tzinfo=timezone.utc)

_ALL_CHANNELS = {"email", "telegram", "sms", "premium_sms"}


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


def _feed_ch() -> dict:
    return json.loads((_FIXTURES / "feed_switzerland_sample.json").read_text(encoding="utf-8"))


def _feed_at() -> dict:
    return json.loads((_FIXTURES / "feed_austria_sample.json").read_text(encoding="utf-8"))


def _ohne_eintrag(feed: dict, suffix: str) -> dict:
    """Kopie des Feeds ohne den Eintrag, dessen Kennung auf ``suffix`` endet."""
    kopie = copy.deepcopy(feed)
    vorher = len(kopie["warnings"])
    kopie["warnings"] = [w for w in kopie["warnings"] if not w["alert"]["identifier"].endswith(suffix)]
    assert len(kopie["warnings"]) == vorher - 1, f"Fixture-Eintrag *{suffix} nicht eindeutig"
    return kopie


def _feed_vorbelegen(land: str, daten: "dict | None") -> None:
    from services.official_alerts import meteoalarm_feed, warn_egress

    meteoalarm_feed._cache[land] = {
        "data": daten,
        "fetched_at": time.monotonic(),
        "ttl": warn_egress.WARN_SUCCESS_TTL if daten is not None else warn_egress.WARN_FAILURE_TTL,
    }


def _zamg_gemeinde(lat: float, lon: float, gemeindenr: int, name: str) -> None:
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
    import services.official_alerts.base as oa_base

    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    oa_base._REGISTERED_SOURCES.extend(quellen)
    try:
        yield
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


def _ch_quellen_in_registry() -> list:
    import services.official_alerts.base as oa_base
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    return [s for s in oa_base._REGISTERED_SOURCES
            if isinstance(s, MeteoAlarmFeedSource) and getattr(s, "country", None) == "CH"]


def _abruf(punkt, now=TEST_NOW_WIND, feed="__fixture__"):
    """Registry-Abruf nur ueber die CH-Quelle (Feed-Cache vorbelegt)."""
    from services.official_alerts import get_official_alerts_with_status
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    _feed_vorbelegen("CH", _feed_ch() if feed == "__fixture__" else feed)
    ch = MeteoAlarmFeedSource("CH")
    with _nur_quellen(ch):
        return get_official_alerts_with_status(*punkt, now=now)


# ───────────────────────────── AC-1 (Test 1) ─────────────────────────────────

def test_ac1_feedpfad_und_registrierung():
    """AC-1 (Infrastruktur): GIVEN die Schweizer Quelle, WHEN Feedpfad und Registry
    abgefragt werden, THEN zeigt der Pfad auf ``feeds-switzerland`` UND genau EINE
    ``MeteoAlarmFeedSource("CH")`` ist registriert."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    assert meteoalarm_feed._FEED_PATHS["CH"] == "/api/v1/warnings/feeds-switzerland"
    assert len(_ch_quellen_in_registry()) == 1, "MeteoAlarmFeedSource('CH') muss registriert sein"


@pytest.mark.parametrize("name,punkt,label", [
    ("zuerich", ZUERICH, "Thalwil-Wetzikon"),
    ("bern", BERN, "Bern-Sense"),
])
def test_ac1_punkt_in_gewarnter_gemeinde_liefert_warnung_mit_stufe_art_zeitraum(name, punkt, label):
    """AC-1: GIVEN ein Punkt in einer Warnregion mit aktiver gelber Windwarnung (aufgezeichnet),
    WHEN die amtlichen Warnungen ermittelt werden, THEN erscheint genau diese Warnung mit Stufe 2,
    Ereignisart Wind und Zeitraum 25.10. 05:00-19:00 UTC, ohne Ausfallhinweis."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    assert MeteoAlarmFeedSource("CH").covers(*punkt) is True, "CH-Quelle muss hier zustaendig sein"
    alerts, unavailable = _abruf(punkt)

    assert len(alerts) == 1, f"genau EINE Warnung erwartet, erhalten {alerts}"
    a = alerts[0]
    assert a.hazard == "wind_gust" and a.level == 2 and a.source == "meteoalarm"
    assert a.label, "Ereignisbezeichnung darf nicht leer sein"
    assert a.valid_from == WIND_VON and a.valid_to == WIND_BIS, a
    assert a.region_label == label, a
    assert unavailable is False


# ───────────────────────────── AC-2 (Test 2) ─────────────────────────────────

def test_ac2_schweizer_punkt_ohne_treffer_polygon_leer_ohne_ausfallhinweis():
    """AC-2: GIVEN Lugano (Luganese, im Fixture ohne Polygon), WHEN die Warnungen ermittelt
    werden, THEN leere Liste UND ``unavailable=False`` -- weil die CH-Quelle zustaendig ist und
    erfolgreich "keine Warnung" sagt, nicht weil sie schweigt."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    assert MeteoAlarmFeedSource("CH").covers(*LUGANO) is True
    alerts, unavailable = _abruf(LUGANO, now=TEST_NOW_WIND)
    assert alerts == []
    assert unavailable is False


# ───────────────────────────── AC-3 (Test 3) ─────────────────────────────────

def test_ac3_ch_feed_ausfall_meldet_nicht_abrufbar():
    """AC-3: GIVEN der CH-Feed-Abruf ist gescheitert, WHEN die Warnungen fuer einen Punkt in der
    Schweiz ermittelt werden, THEN ``unavailable=True`` statt einer scheinbar warnungsfreien Lage."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    assert MeteoAlarmFeedSource("CH").covers(*ZUERICH) is True
    alerts, unavailable = _abruf(ZUERICH, feed=None)
    assert alerts == []
    assert unavailable is True


# ───────────────────────────── AC-4 (Test 4) ─────────────────────────────────

def test_ac4_schweizer_rand_und_grenzpunkte_sind_zustaendig():
    """AC-4: GIVEN 15 Schweizer Rand-/Grenzpunkte, WHEN ``covers()`` laeuft (Feed im Cache),
    THEN ist die CH-Quelle fuer JEDEN zustaendig."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    _feed_vorbelegen("CH", _feed_ch())
    ch = MeteoAlarmFeedSource("CH")
    assert len(CH_RAND_PUNKTE) >= 15
    nicht_zustaendig = [n for n, p in CH_RAND_PUNKTE.items() if ch.covers(*p) is not True]
    assert nicht_zustaendig == [], f"CH-Quelle fuer Schweizer Punkte nicht zustaendig: {nicht_zustaendig}"


def test_ac4_nachbarland_punkte_nicht_zustaendig_ohne_ausfallhinweis():
    """AC-4: GIVEN Punkte in Nachbarlaendern, WHEN ``covers()`` und die Registry-Abfrage laufen,
    THEN ist die CH-Quelle ``False``, loest keinen Ausfallhinweis aus und liefert keine Warnung.
    Positivkontrolle: derselbe Aufbau ist fuer Zuerich zustaendig (sonst vakuum-gruen)."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    _feed_vorbelegen("CH", _feed_ch())
    ch = MeteoAlarmFeedSource("CH")
    assert ch.covers(*ZUERICH) is True, "Positivkontrolle"
    for name, punkt in NACHBAR_PUNKTE.items():
        assert ch.covers(*punkt) is False, f"{name}: CH-Quelle darf hier nicht zustaendig sein"
        alerts, unavailable = _abruf(punkt)
        assert alerts == [], f"{name}: {alerts}"
        assert unavailable is False, f"{name}: Ausland darf keinen Ausfallhinweis ausloesen"


def test_ac4_fallback_punkt_ausserhalb_slf_aber_im_feed_polygon_ist_zustaendig():
    """AC-4 (Fallback, Impl. Details 3): GIVEN Mendrisiotto -- ausserhalb der SLF-Regionspolygone,
    aber im aufgezeichneten Feed-Polygon --, WHEN ``covers()`` laeuft, THEN ist die Quelle
    zustaendig (Feed im Cache); OHNE gecachten Feed gilt der Punkt als nicht zustaendig und es
    gibt keinen Netzabruf (Kern-Schicht ``--disable-socket``)."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource
    from services.official_alerts.slf import SlfSource

    assert SlfSource().covers(*MENDRISIO) is False, "Voraussetzung: Punkt liegt ausserhalb der SLF-Regionen"
    ch = MeteoAlarmFeedSource("CH")
    assert ch.covers(*MENDRISIO) is False, "ohne gecachten Feed kein Netz, nicht zustaendig"
    _feed_vorbelegen("CH", _feed_ch())
    assert ch.covers(*MENDRISIO) is True


# ───────────────────────────── AC-5 (Test 5/6) ───────────────────────────────

def test_ac5_cancel_nimmt_die_warnung_zurueck():
    """AC-5: GIVEN eine aktive Windwarnung Sarganserland UND ein Cancel (``references`` auf sie),
    WHEN die Warnungen ermittelt werden, THEN erscheint sie nicht als aktiv. Gegenprobe: ohne
    den Cancel-Eintrag erscheint sie."""
    _assert_pruefling_aus_diesem_baum()
    ohne_cancel = _ohne_eintrag(_feed_ch(), ".SYNTH-CANCEL")
    alerts, _ = _abruf(SARGANS, feed=ohne_cancel)
    assert len(alerts) == 1 and alerts[0].level == 2, f"Gegenprobe (ohne Cancel): {alerts}"

    alerts, unavailable = _abruf(SARGANS)
    assert alerts == [], f"aufgehobene Warnung darf nicht aktiv sein: {alerts}"
    assert unavailable is False


def test_ac5_update_ersetzt_die_vorgaengerwarnung_genau_einmal():
    """AC-5: GIVEN Brienz-Interlaken fuehrt die gelbe Windwarnung UND ein Update (orange,
    ``references`` auf die gelbe), WHEN die Warnungen ermittelt werden, THEN genau EINE Warnung
    im Update-Stand (Stufe 3). Gegenprobe: ohne das Update bleibt es die gelbe (Stufe 2)."""
    _assert_pruefling_aus_diesem_baum()
    ohne_update = _ohne_eintrag(_feed_ch(), ".SYNTH-UPDATE")
    alerts, _ = _abruf(INTERLAKEN, feed=ohne_update)
    assert [a.level for a in alerts] == [2], f"Gegenprobe (ohne Update): {alerts}"

    alerts, unavailable = _abruf(INTERLAKEN)
    assert [a.level for a in alerts] == [3], f"genau eine Warnung im Update-Stand erwartet: {alerts}"
    assert alerts[0].hazard == "wind_gust"
    assert unavailable is False


def test_ac5_aufgezeichnete_allclear_update_erscheint_nicht_als_warnung():
    """AC-5 (echte Aufzeichnung): GIVEN Basel fuehrt die gelbe Windwarnung UND ein aufgezeichnetes
    Update ``responseType: AllClear`` (gruen, Stufe 1, anderes Vorgaenger-Alert), WHEN die
    Warnungen ermittelt werden, THEN genau die gelbe Windwarnung -- das Gruen-Update erscheint
    nicht als Warnung."""
    _assert_pruefling_aus_diesem_baum()
    alerts, unavailable = _abruf(BASEL)
    assert len(alerts) == 1, f"nur die gelbe Warnung erwartet: {alerts}"
    assert alerts[0].level == 2 and alerts[0].region_label == "Basel"
    assert unavailable is False


# ───────────────────────────── AC-6 (Test 7) ─────────────────────────────────

def test_ac6_hoehenband_wird_ignoriert():
    """AC-6: GIVEN die aufgezeichnete Bodenfrost-Warnung Mendrisiotto gilt amtlich nur fuer das
    Hoehenband 0-600 m (``altitude``/``ceiling``), WHEN ein Punkt in der Region abgefragt wird,
    THEN wird die Warnung ausgegeben -- unabhaengig von der Hoehe (bewusst wie IT/AT/DE)."""
    _assert_pruefling_aus_diesem_baum()
    frost = [w["alert"] for w in _feed_ch()["warnings"]
             if any(i.get("event") == "Bodenfrost" for i in w["alert"].get("info") or [])]
    assert frost, "Fixture muss die Bodenfrost-Warnung enthalten"
    area = frost[0]["info"][0]["area"][0]
    assert area["areaDesc"] == "Mendrisiotto" and area["ceiling"] == 600.0 and area["altitude"] == 0.0

    alerts, unavailable = _abruf(MENDRISIO, now=TEST_NOW_FROST)
    assert len(alerts) == 1, f"Bodenfrost-Warnung erwartet: {alerts}"
    assert alerts[0].hazard == "extreme_cold" and alerts[0].level == 2
    assert unavailable is False


# ───────────────────────────── Mehrfachring / Loch ───────────────────────────

def test_loch_im_polygon_ist_keine_warnung():
    """Spec Impl. Details 1: GIVEN ein (synthetisches) Gebiet aus Aussenring und Innenring (Loch),
    WHEN ein Punkt im Aussenring, aber ausserhalb des Lochs liegt, THEN erscheint die Warnung;
    liegt er im Loch, erscheint keine."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    ch = MeteoAlarmFeedSource("CH")
    _feed_vorbelegen("CH", _feed_ch())
    assert ch.covers(*LOCH_AUSSEN) is True and ch.covers(*LOCH_INNEN) is True

    aussen, unavailable = _abruf(LOCH_AUSSEN)
    assert any(a.region_label == "Synthetisch Lochgebiet" for a in aussen), aussen
    assert unavailable is False
    innen, unavailable = _abruf(LOCH_INNEN)
    assert not any(a.region_label == "Synthetisch Lochgebiet" for a in innen), f"Punkt im Loch: {innen}"
    assert unavailable is False


# ───────────────────────────── AC-7 (Test 8) ─────────────────────────────────

def test_ac7_feedwarnung_und_slf_lawine_getrennt_registrierungsreihenfolge():
    """AC-7: GIVEN Luzern (Feed-Windwarnung UND bewertete SLF-Region CH-2112), WHEN die Warnungen
    ueber die Registry ermittelt werden, THEN erscheinen Wind (meteoalarm) und Lawine
    (``avalanche_bulletin``) je genau einmal und getrennt, Wind vor Lawine; und in der ECHTEN
    Registry steht die CH-Feedquelle vor der SLF-Quelle."""
    _assert_pruefling_aus_diesem_baum()
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_with_status
    from services.official_alerts.slf import SlfSource
    from tests.helpers.slf_support import (
        WINTER_MORGEN, FakeClock, SlfFixtureTransport, make_slf_source,
    )

    echte = list(oa_base._REGISTERED_SOURCES)
    ch_idx = [i for i, s in enumerate(echte) if s in _ch_quellen_in_registry()]
    slf_idx = [i for i, s in enumerate(echte) if isinstance(s, SlfSource)]
    assert len(ch_idx) == 1 and len(slf_idx) == 1, (ch_idx, slf_idx)
    assert ch_idx[0] < slf_idx[0], "Registrierungsreihenfolge: CH-Feed VOR SLF"

    _feed_vorbelegen("CH", _feed_ch())
    clock = FakeClock(datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc))
    slf = make_slf_source(SlfFixtureTransport(WINTER_MORGEN), clock)
    # Reihenfolge wie in der echten Registry: echte CH-Quelle, dann SLF mit Fixture-Transport.
    with _nur_quellen(_ch_quellen_in_registry()[0], slf):
        alerts, unavailable = get_official_alerts_with_status(*LUZERN, now=TEST_NOW_WIND)

    wind = [a for a in alerts if a.hazard == "wind_gust"]
    lawine = [a for a in alerts if a.hazard == "avalanche_bulletin"]
    assert len(wind) == 1 and len(lawine) == 1, f"je eine Gefahrenart erwartet: {alerts}"
    assert alerts.index(wind[0]) < alerts.index(lawine[0]), "Reihenfolge folgt der Registrierung"
    assert unavailable is False


# ───────────────────────────── AC-8 (Test 9) ─────────────────────────────────

_SCHWELLEN = {"sms": "MODERATE", "premium_sms": "MODERATE"}


@pytest.fixture()
def premium_nutzer():
    """Echter Nutzer mit Tier ``premium`` -- sonst entfernen die Tier-Gates SMS/Premium-SMS."""
    from app.loader import get_data_dir

    user_id = f"tdd-meteoalarm-ch-{uuid.uuid4().hex[:8]}"
    pfad = get_data_dir(user_id)
    if pfad.exists():
        shutil.rmtree(pfad)
    pfad.mkdir(parents=True, exist_ok=True)
    (pfad / "user.json").write_text(json.dumps({"id": user_id, "tier": "premium"}))
    yield user_id
    if pfad.exists():
        shutil.rmtree(pfad)


def _abo(art: str):
    alle = {"email": True, "telegram": True, "sms": True, "premium_sms": True}
    if art == "vergleich":
        return {
            "id": "cmp-ch", "name": "cmp-ch", "user_id": "unused",
            "location_ids": ["loc-1"], "schedule": "daily", "weekday": 4,
            "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
            "empfaenger": [], "created_at": "2026-10-29T00:00:00Z",
            "send_telegram": True, "send_sms": True, "send_premium_sms": True,
            "alert_channels": dict(alle), "alert_channel_thresholds": dict(_SCHWELLEN),
        }
    from app.trip import Stage, Trip, Waypoint

    stage = Stage(
        id="S1", name="Etappe 1", date=date.today() + timedelta(days=1),
        waypoints=[
            Waypoint(id="W1", name="Interlaken", lat=INTERLAKEN[0], lon=INTERLAKEN[1],
                     elevation_m=570, arrival_calculated="08:00"),
            Waypoint(id="W2", name="Grindelwald", lat=46.6244, lon=8.0413,
                     elevation_m=1034, arrival_calculated="12:00"),
        ],
    )
    return Trip(id="trip-ch", name="Trip CH", stages=[stage],
                alert_channels=dict(alle), alert_channel_thresholds=dict(_SCHWELLEN))


def _kanaele_fuer(alert, abo, user_id: str) -> set:
    """Die geteilte Alarm-Kanal-Aufloesung, wie ``trip_alert.py`` und
    ``compare_official_alert.py`` sie am Versand aufrufen."""
    from services import alert_channel_threshold, alert_urgency
    from services.alert_channels import effective_alert_channels

    effective = effective_alert_channels(abo, None, user_id)
    dringlichkeit = alert_urgency.highest_urgency(alert_urgency.urgency_from_official_level(alert.level))
    schwellen = abo.get("alert_channel_thresholds") if isinstance(abo, dict) else abo.alert_channel_thresholds
    erlaubt, _unterdrueckt = alert_channel_threshold.split_by_threshold(effective, dringlichkeit, schwellen)
    return erlaubt


@pytest.mark.parametrize("art", ["route", "vergleich"])
def test_ac8_ch_warnung_erreicht_dieselben_kanaele_wie_at(art, premium_nutzer):
    """AC-8: GIVEN eine orange CH-Warnung (aus dem Feed ueber ``MeteoAlarmFeedSource("CH")``,
    Brienz-Interlaken Update-Stand) und eine orange AT-Warnung (Hitze Wien), UND ein Trip bzw.
    Ortsvergleich mit Empfaengern auf allen vier Kanaelen, WHEN die geteilte Alarm-Kanal-Aufloesung
    laeuft, THEN erreicht die CH-Warnung dieselbe Kanalmenge wie die AT-Warnung -- alle vier."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    _feed_vorbelegen("CH", _feed_ch())
    _feed_vorbelegen("AT", _feed_at())
    _zamg_gemeinde(*WIEN, 90101, "Wien")

    at_orange = [a for a in MeteoAlarmFeedSource("AT").fetch(*WIEN) if a.level == 3]
    assert at_orange, "Kontrolle: orange AT-Warnung (Wien) aus der AT-Stichprobe"

    ch_orange = [a for a in MeteoAlarmFeedSource("CH").fetch(*INTERLAKEN) if a.level == 3]
    assert ch_orange, "orange CH-Warnung (Update-Stand) muss aus dem Feed entstehen"

    abo = _abo(art)
    k_ch = _kanaele_fuer(ch_orange[0], abo, premium_nutzer)
    k_at = _kanaele_fuer(at_orange[0], abo, premium_nutzer)
    assert k_ch == k_at == _ALL_CHANNELS, (k_ch, k_at)


# ───────────────────────────── AC-9 (Test 10) ────────────────────────────────

@pytest.mark.parametrize("name,punkt", [("zuerich", ZUERICH), ("bern", BERN)])
def test_ac9_andersfoermiger_eintrag_faerbt_andere_orte_nicht_als_ausfall(name, punkt):
    """AC-9: GIVEN ein Eintrag (``.SYNTH-KAPUTT``, steht an erster Stelle des Feeds) mit unlesbarem
    Polygon, WHEN ein Punkt mit korrekter Warnung abgefragt wird, THEN erhaelt er seine Warnung
    und KEINEN Ausfallhinweis."""
    _assert_pruefling_aus_diesem_baum()
    feed = _feed_ch()
    assert feed["warnings"][0]["alert"]["identifier"].endswith(".SYNTH-KAPUTT"), "Fixture-Aufbau"
    alerts, unavailable = _abruf(punkt, feed=feed)
    assert len(alerts) == 1 and alerts[0].level == 2, f"{name}: {alerts}"
    assert unavailable is False


# ───────────────────────────── AC-10 (Test 11) ───────────────────────────────

def test_ac10_bestehende_laenderpfade_unveraendert():
    """AC-10 (Regression, darf schon jetzt GRUEN sein): IT/AT/DE-Pfade und -Geocode-Namen
    bleiben unveraendert, die DE-Quelle bleibt registriert."""
    _assert_pruefling_aus_diesem_baum()
    from services.official_alerts import meteoalarm_feed

    assert meteoalarm_feed._FEED_PATHS["IT"] == "/api/v1/warnings/feeds-italy"
    assert meteoalarm_feed._FEED_PATHS["AT"] == "/api/v1/warnings/feeds-austria"
    assert meteoalarm_feed._FEED_PATHS["DE"] == "/api/v1/warnings/feeds-germany"
    assert meteoalarm_feed._GEOCODE_NAME["DE"] == "WARNCELLID"
