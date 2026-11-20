"""#3133: Premium-SMS-Befehlsantworten seitenweise, je Nachricht hoechstens 153 Zeichen.

SPEC: docs/specs/modules/fix_3133_premium_antwort_laenge.md (AC-1 bis AC-16)

Messpunkt ist der ECHTE Premium-SMS-Eingang: Garmin-Nachricht ins seven.io-
Journal -> ``InboundSmsReader.poll_and_process`` -> Kommandoverarbeiter ->
``send_command_reply_premium_sms`` -> Kanal-Ausgang (Aufzeichner ``mit``).
Ersetzt sind nur die Aussengrenzen (Journal-GET, Lern-POST, vier Kanal-
Ausgaenge) -- Vorbild ``test_3100_premium_sms_fallliste.py``.

Festgelegte Schnittstellen (aus der Spec):
* ``services.premium_sms_pages.paginate(zeilen, page, *, verweis_fn, limit=153) -> str``
* ``TripCommandProcessor._format_drilldown_kurzform(..., channel=...)``:
  ``premium_sms`` -> 153, sonst unveraendert 160 (AC-13)
* Kuerzungskennzeichen des zentralen Sicherheitsnetzes: ``~`` als letztes Zeichen (AC-11)

ROT vor der Umsetzung: Premium-HILFE (456), Vergleichs-HILFE (158), KUERZEL/CODES
(761) und unbekannter Befehl (~190) gehen ungekuerzt raus; ``paginate`` existiert
nicht; die Drilldown-Kurzform kennt nur 160.
"""
from __future__ import annotations

import copy
import itertools
import json
import re
from datetime import datetime, timedelta, timezone

import pytest

from app.loader import get_data_dir, load_all_trips, save_trip
from app.metric_catalog import get_metric
from app.models import TripReportConfig
from app.trip import Stage, Trip, Waypoint
from services.trip_command_processor import (
    InboundMessage, TripCommandProcessor, codes_text, hilfe_kurzform, hilfe_langform,
)
from services.weather_extractor import DrilldownPoint, DrilldownResult
from tests.tdd._compare_kette_fixtures import nutzer_anlegen, orte_anlegen, preset_ablegen
from tests.tdd._einstellung_auslieferung_fixtures import frisches_profil, premium_rueckadresse
from tests.tdd._gsm7_charset import assert_gsm7_clean

# ruff: noqa: F811  (mit = geteilte Fixture als Testparameter)
from tests.tdd.test_3047_runde7_orte_kanaele import mit, preset  # noqa: F401  (Fixture)
from tests.tdd.test_premium_sms_kommandopfad import (
    INNSBRUCK, _garmin, _Journal, _LernEndpunkt, _poll,
)
from utils.ascii_fold import fold_ascii
from utils.timezone import tz_for_coords

GRENZE = 153
MAX_SEITEN = 20
NUMMERN = ("4917000313301", "4917000313302")
_MSG_ID = itertools.count(3133000)

#: Befehlswort und Verweis je Nutzersprache (AC-6).
WORT = {
    ("hilfe", "de"): "HILFE", ("hilfe", "en"): "HELP",
    ("kuerzel", "de"): "KUERZEL", ("kuerzel", "en"): "CODES",
}
VERWEIS = {"de": "mehr: {wort} {n}", "en": "more: {wort} {n}"}
BEREICH = {"de": "HILFE: Seiten 1-{n}", "en": "HELP: pages 1-{n}"}


# ---------------------------------------------------------------------------
# Aufbau
# ---------------------------------------------------------------------------

def _sprache(uid: str, lang: str) -> None:
    pf = get_data_dir(uid) / "user.json"
    u = json.loads(pf.read_text())
    u["language"] = lang
    pf.write_text(json.dumps(u))


def _trip(uid: str, *, name: str | None = None, etappen: int = 3, suffix: str = "") -> Trip:
    zone = tz_for_coords(*INNSBRUCK)
    heute = datetime.now(timezone.utc).astimezone(zone).date()
    trip_id = f"p3133-{uid[-6:]}{suffix}"
    stages = [
        Stage(id=f"T{i}", name=f"Etappe {i}", date=heute + timedelta(days=i - 1),
              waypoints=[
                  Waypoint(id=f"G{i}a", name="Start", lat=INNSBRUCK[0], lon=INNSBRUCK[1],
                           elevation_m=600),
                  Waypoint(id=f"G{i}b", name="Ziel", lat=INNSBRUCK[0] + 0.02,
                           lon=INNSBRUCK[1] + 0.02, elevation_m=900)])
        for i in range(etappen)
    ]
    trip = Trip(
        id=trip_id, name=name or f"Premium {uid[-6:]}{suffix}", stages=stages,
        report_config=TripReportConfig(trip_id=trip_id, send_email=True, send_sms=True,
                                       send_premium_sms=True, send_telegram=True),
    )
    save_trip(trip, uid)
    return next(t for t in load_all_trips(uid) if t.id == trip_id)


def _nutzer(lang: str = "de", **trip_kw) -> str:
    uid = frisches_profil()
    _sprache(uid, lang)
    _trip(uid, **trip_kw)
    return uid


def _eingang(monkeypatch, auftraege: list[tuple[str, str, str]]) -> None:
    """Ein Journal-Poll mit je einer Garmin-Nachricht ``(uid, nummer, befehl)``."""
    msgs = [_garmin(next(_MSG_ID), nummer, befehl) for _u, nummer, befehl in auftraege]
    _poll(monkeypatch, journal=_Journal([msgs]),
          lernen=_LernEndpunkt(nummer_zu_user={n: u for u, n, _b in auftraege}))


def _premium_fuer(mit, uid: str) -> list[str]:
    ziel = premium_rueckadresse(uid)
    return [s["body"] for s in mit.sendungen("premium_sms") if s["empfaenger"] == ziel]


def _antwort(monkeypatch, mit, uid: str, befehl: str) -> str:
    """Genau EINE Premium-SMS an diesen Nutzer, sonst nichts (eine Anfrage = eine Sendung)."""
    mit.leeren()
    _eingang(monkeypatch, [(uid, NUMMERN[0], befehl)])
    assert mit.kanaele == ["premium_sms"], f"nur Premium-SMS erwartet: {mit!r}"
    texte = _premium_fuer(mit, uid)
    assert len(texte) == 1, f"{befehl!r}: genau eine Sendung erwartet: {mit!r}"
    return texte[0]


def _pruefe_laenge(text: str, kontext: str) -> None:
    assert len(text) <= GRENZE, f"{kontext}: {len(text)} > {GRENZE} Zeichen: {text!r}"
    assert text == fold_ascii(text), f"{kontext}: nicht gefaltet: {text!r}"


def _alle_seiten(monkeypatch, mit, uid: str, befehl: str, lang: str,
                 praefix: str = "") -> list[str]:
    """Seite 1 per ``<befehl>``, dann je Verweis die naechste Seite, bis keiner mehr kommt."""
    wort_key = {"HILFE": "hilfe", "HELP": "hilfe", "KUERZEL": "kuerzel",
                "CODES": "kuerzel"}[befehl.upper()]
    wort = WORT[(wort_key, lang)]
    seiten = [_antwort(monkeypatch, mit, uid, f"{praefix}{befehl}")]
    while len(seiten) < MAX_SEITEN:
        verweis = VERWEIS[lang].format(wort=wort, n=len(seiten) + 1)
        if not seiten[-1].endswith(verweis):
            break
        seiten.append(_antwort(monkeypatch, mit, uid, f"{praefix}{befehl} {len(seiten) + 1}"))
    for i, s in enumerate(seiten, 1):
        _pruefe_laenge(s, f"{befehl} Seite {i}")
    assert len(seiten) < MAX_SEITEN, "Seitenkette endet nicht"
    return seiten


def _hilfe_zeilen(kind: str) -> list[str]:
    """Jeder Befehlseintrag der bisherigen Kurzform-HELP (ohne Kopfzeile)."""
    return [fold_ascii(z) for z in hilfe_kurzform(kind).split("\n")[1:]]


def _codes_eintraege() -> list[str]:
    """Jeder Kuerzel-Eintrag der bisherigen CODES-Antwort, ohne Gruppenkopf."""
    eintraege = []
    for zeile in codes_text(True).split("\n"):
        _kopf, _sep, rest = zeile.partition(": ")
        for teil in re.split(r", |\. ", rest):
            teil = teil.strip().rstrip(".")
            if teil:
                eintraege.append(fold_ascii(teil))
    return eintraege


def _pruefe_vollstaendig(seiten: list[str], eintraege: list[str], kontext: str) -> None:
    fehlend = [e for e in eintraege if not any(e in s for s in seiten)]
    assert not fehlend, f"{kontext}: Eintraege fehlen oder sind zerschnitten: {fehlend!r}\n{seiten!r}"


# ---------------------------------------------------------------------------
# Einheit: paginate
# ---------------------------------------------------------------------------

def _paginate():
    from services.premium_sms_pages import paginate

    return paginate


def _verweis(n: int) -> str:
    return f"mehr: HILFE {n}"


def _alle_einheit_seiten(zeilen: list[str], limit: int = GRENZE) -> list[str]:
    paginate = _paginate()
    seiten = [paginate(zeilen, 1, verweis_fn=_verweis, limit=limit)]
    while seiten[-1].endswith(_verweis(len(seiten) + 1)) and len(seiten) < MAX_SEITEN:
        seiten.append(paginate(zeilen, len(seiten) + 1, verweis_fn=_verweis, limit=limit))
    return seiten


def test_paginate_ganze_eintraege_verweis_im_budget():
    zeilen = [f"BEFEHL{i:02d} - wirkung nummer {i}" for i in range(20)]
    seiten = _alle_einheit_seiten(zeilen)
    assert len(seiten) > 1, seiten
    for i, s in enumerate(seiten, 1):
        assert len(s) <= GRENZE, (i, len(s), s)
    for i, s in enumerate(seiten[:-1], 1):
        assert s.endswith(_verweis(i + 1)), (i, s)
    assert "mehr:" not in seiten[-1], seiten[-1]
    for z in zeilen:
        assert sum(z in s for s in seiten) == 1, (z, seiten)


def test_paginate_einzelzeile_ueber_limit_wird_hart_gekuerzt():
    seiten = _alle_einheit_seiten(["X" * 400, "kurz"])
    assert all(len(s) <= GRENZE for s in seiten), seiten
    assert any("kurz" in s for s in seiten), seiten


def test_paginate_faltet_vor_dem_messen():
    zeilen = ["Größe ändern – überall ß"] * 12
    seiten = _alle_einheit_seiten(zeilen)
    for s in seiten:
        assert s == fold_ascii(s) and len(s) <= GRENZE, s


def test_paginate_genau_passend_eine_seite_ohne_verweis():
    zeilen = ["A" * 76, "B" * 76]  # 76 + 1 + 76 = 153
    seite = _paginate()(zeilen, 1, verweis_fn=_verweis, limit=GRENZE)
    assert seite == "A" * 76 + "\n" + "B" * 76, seite


# ---------------------------------------------------------------------------
# AC-1 / AC-2 / AC-5 / AC-6: Trip-HILFE alle Seiten
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang,befehl", [("de", "HILFE"), ("en", "HELP")])
def test_ac1_ac2_hilfe_seiten_vollstaendig_und_kurz(monkeypatch, mit, lang, befehl):
    uid = _nutzer(lang)
    seiten = _alle_seiten(monkeypatch, mit, uid, befehl, lang)
    assert len(seiten) >= 2, f"HILFE muss geseitet sein: {seiten!r}"
    _pruefe_vollstaendig(seiten, _hilfe_zeilen("route"), f"{befehl} ({lang})")


@pytest.mark.parametrize("lang,befehl", [("de", "HILFE"), ("en", "HELP")])
def test_ac5_ac6_verweis_nur_bis_zur_vorletzten_seite(monkeypatch, mit, lang, befehl):
    uid = _nutzer(lang)
    seiten = _alle_seiten(monkeypatch, mit, uid, befehl, lang)
    assert len(seiten) >= 2, seiten
    wort = WORT[("hilfe", lang)]
    assert seiten[0].endswith(VERWEIS[lang].format(wort=wort, n=2)), seiten[0]
    for i, s in enumerate(seiten[:-1], 1):
        assert s.endswith(VERWEIS[lang].format(wort=wort, n=i + 1)), (i, s)
    assert "mehr:" not in seiten[-1] and "more:" not in seiten[-1], seiten[-1]


# ---------------------------------------------------------------------------
# AC-3: Orts-Vergleich
# ---------------------------------------------------------------------------

def test_ac3_vergleichshilfe_seiten(monkeypatch, mit):
    uid = nutzer_anlegen("premium")
    orte_anlegen(uid)
    p = preset()
    preset_ablegen(uid, copy.deepcopy(p))
    seiten = _alle_seiten(monkeypatch, mit, uid, "HILFE", "de", praefix=f"{p['name']} ")
    assert len(seiten) >= 2, f"Vergleichs-HILFE (158 Zeichen) muss geseitet sein: {seiten!r}"
    _pruefe_vollstaendig(seiten, _hilfe_zeilen("vergleich"), "Vergleichs-HILFE")
    # Vergleichsseiten tragen keine Trip-Befehle (RESTDAY o.ae.).
    assert not any("RESTDAY" in s for s in seiten), seiten


# ---------------------------------------------------------------------------
# AC-4 / AC-6: KUERZEL / CODES
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang,befehl", [("de", "KUERZEL"), ("en", "CODES")])
def test_ac4_codes_seiten_vollstaendig(monkeypatch, mit, lang, befehl):
    uid = _nutzer(lang)
    seiten = _alle_seiten(monkeypatch, mit, uid, befehl, lang)
    assert len(seiten) >= 5, seiten
    assert seiten[0].endswith(VERWEIS[lang].format(wort=WORT[("kuerzel", lang)], n=2)), seiten[0]
    _pruefe_vollstaendig(seiten, _codes_eintraege(), befehl)


# ---------------------------------------------------------------------------
# AC-7 / AC-8: ungueltige Seitenzahl
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("arg", ["abc", "0", "-1"])
def test_ac7_ungueltige_seite_ist_seite_eins(monkeypatch, mit, arg):
    uid = _nutzer("de")
    seite1 = _antwort(monkeypatch, mit, uid, "HILFE")
    _pruefe_laenge(seite1, "HILFE")
    assert _antwort(monkeypatch, mit, uid, f"HILFE {arg}") == seite1


@pytest.mark.parametrize("lang,befehl", [("de", "HILFE"), ("en", "HELP")])
def test_ac8_seite_ueber_n_nennt_bereich(monkeypatch, mit, lang, befehl):
    uid = _nutzer(lang)
    n = len(_alle_seiten(monkeypatch, mit, uid, befehl, lang))
    assert n >= 2
    text = _antwort(monkeypatch, mit, uid, f"{befehl} 99")
    assert text == BEREICH[lang].format(n=n), text


# ---------------------------------------------------------------------------
# AC-9: Telegram und E-Mail unveraendert (Regressionswaechter)
# ---------------------------------------------------------------------------

def _process(uid: str, body: str, channel: str, englisch: bool) -> str:
    return TripCommandProcessor().process(InboundMessage(
        trip_name="", body=body, sender="x", channel=channel,
        received_at=datetime.now(timezone.utc), user_id=uid, englisch=englisch,
    )).confirmation_body


@pytest.mark.parametrize("body", ["HELP", "HELP 2"])
def test_ac9_telegram_help_unveraendert(body):
    uid = _nutzer("de")
    assert _process(uid, body, "telegram", True) == hilfe_kurzform("route")


@pytest.mark.parametrize("body", ["CODES", "CODES 2"])
def test_ac9_telegram_codes_unveraendert(body):
    uid = _nutzer("de")
    assert _process(uid, body, "telegram", True) == codes_text(True)


@pytest.mark.parametrize("body", ["HILFE", "HILFE 2"])
def test_ac9_email_hilfe_unveraendert(body):
    uid = _nutzer("de")
    assert _process(uid, body, "email", False) == hilfe_langform("route", lang="de")


def test_ac9_telegram_unbekannter_befehl_unveraendert():
    uid = _nutzer("de")
    text = _process(uid, "FOOBAR", "telegram", True)
    assert "Commands: TODAY, TOMORROW, NOW, STORMS" in text, text
    assert "more:" not in text and "mehr:" not in text, text


# ---------------------------------------------------------------------------
# AC-10: unbekannter Befehl auf Premium
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang,wort", [("de", "HILFE"), ("en", "HELP")])
def test_ac10_unbekannter_befehl_premium_kurz_mit_verweis(monkeypatch, mit, lang, wort):
    uid = _nutzer(lang)
    text = _antwort(monkeypatch, mit, uid, "FOOBAR")
    _pruefe_laenge(text, "unbekannter Befehl")
    assert re.search(rf"\b{wort}\b", text), text
    assert not text.endswith("~"), f"eigene Fassung, nicht vom Sicherheitsnetz gekuerzt: {text!r}"
    assert "mehr:" not in text and "more:" not in text, text


# ---------------------------------------------------------------------------
# AC-11 / AC-12: zentrales Sicherheitsnetz
# ---------------------------------------------------------------------------

def test_ac11_langer_trip_name_wird_gekuerzt_mit_kennzeichen(monkeypatch, mit):
    """Sehr langer Trip-Name (zwei Trips, der aktive wird gewaehlt) -> die
    STATUS-Antwort ueberschreitet 153 und muss gekuerzt und gekennzeichnet werden."""
    uid = frisches_profil()
    for k in ("a", "b"):
        _trip(uid, name=f"Sehr langer Trip-Name {k.upper()} " + "Hoehenweg " * 8, suffix=k)
    text = _antwort(monkeypatch, mit, uid, "STATUS")
    _pruefe_laenge(text, "Rueckfrage")
    assert text.endswith("~"), f"Kuerzungskennzeichen fehlt: {text!r}"


def test_ac11_langer_status_wird_gekuerzt(monkeypatch, mit):
    uid = _nutzer("de", etappen=25)
    text = _antwort(monkeypatch, mit, uid, "STATUS")
    _pruefe_laenge(text, "STATUS")
    assert text.endswith("~"), f"Kuerzungskennzeichen fehlt: {text!r}"


def test_ac12_umlaute_werden_gefaltet(monkeypatch, mit):
    uid = _nutzer("de", name="Großglockner Höhenweg – Süd")
    text = _antwort(monkeypatch, mit, uid, "STATUS")
    _pruefe_laenge(text, "STATUS mit Umlauten")
    assert_gsm7_clean(text, context="Premium-STATUS (AC-12)")


# ---------------------------------------------------------------------------
# AC-13: Drilldown-Grenze kanalabhaengig
# ---------------------------------------------------------------------------

def _drilldown(n: int) -> DrilldownResult:
    tz = tz_for_coords(*INNSBRUCK)
    start = datetime(2026, 9, 10, 0, tzinfo=tz)
    return DrilldownResult(
        trip_id="p3133", metric="wind10m_kmh",
        points=[DrilldownPoint(ts=start + timedelta(hours=i), value=10.0 + i) for i in range(n)],
        available=True,
    )


def test_ac13_drilldown_premium_153_sms_160():
    tz = tz_for_coords(*INNSBRUCK)
    wind = get_metric("wind")
    proz = TripCommandProcessor()
    # Eingabe suchen, deren SMS-Kurzform zwischen 154 und 160 Zeichen landet.
    fall = None
    for n in range(10, 30):
        sms = proz._format_drilldown_kurzform(_drilldown(n), wind, tz, channel="sms")
        if 153 < len(sms) <= 160:
            fall = n
            break
    assert fall is not None, "Testaufbau: kein Fall mit SMS-Laenge 154..160 gefunden"
    sms = proz._format_drilldown_kurzform(_drilldown(fall), wind, tz, channel="sms")
    premium = proz._format_drilldown_kurzform(_drilldown(fall), wind, tz, channel="premium_sms")
    assert sms == proz._format_drilldown_kurzform(_drilldown(fall), wind, tz), "SMS unveraendert"
    assert len(premium) <= GRENZE, (len(premium), premium)
    assert "not shown" in premium, f"ganze Gruppen weg, Luecke benannt: {premium!r}"


# ---------------------------------------------------------------------------
# AC-14 / AC-15 / AC-16
# ---------------------------------------------------------------------------

def _antwort_zaehler(uid: str) -> int:
    from services import sms_daily_limit as sdl

    now = datetime.now(timezone.utc)
    return sdl._zaehlerwert(sdl._tagesstand(sdl._load(sdl._path(uid)), sdl._today(now)),
                            "premium_sms_reply")


def test_ac14_jede_seite_ein_kontingentplatz(monkeypatch, mit):
    uid = _nutzer("de")
    seite1 = _antwort(monkeypatch, mit, uid, "HILFE")
    vorher = _antwort_zaehler(uid)
    seite2 = _antwort(monkeypatch, mit, uid, "HILFE 2")
    assert _antwort_zaehler(uid) == vorher + 1
    assert seite2 != seite1, "HILFE 2 liefert Seite 2"
    _pruefe_laenge(seite2, "HILFE 2")


def test_ac15_zwei_nutzer_je_eigene_seite(monkeypatch, mit):
    a, b = _nutzer("de"), _nutzer("en")
    mit.leeren()
    _eingang(monkeypatch, [(a, NUMMERN[0], "HILFE 2"), (b, NUMMERN[1], "HELP 2")])
    assert len(mit.sendungen("premium_sms")) == 2, mit
    ta, tb = _premium_fuer(mit, a), _premium_fuer(mit, b)
    assert len(ta) == 1 and len(tb) == 1, mit
    _pruefe_laenge(ta[0], "Nutzer A")
    _pruefe_laenge(tb[0], "Nutzer B")
    empf = {s["empfaenger"] for s in mit.sendungen("premium_sms")}
    assert empf == {premium_rueckadresse(a), premium_rueckadresse(b)}, empf
    assert "mehr: HILFE 3" in ta[0] or "mehr:" not in ta[0], ta
    assert "mehr:" not in tb[0], f"englischer Nutzer bekommt englischen Verweis: {tb!r}"


def test_ac16_ziellos_mit_seitenzahl(monkeypatch, mit):
    referenz = _nutzer("de")
    seite2 = _antwort(monkeypatch, mit, referenz, "HILFE 2")
    uid = frisches_profil()
    _trip(uid, suffix="a")
    _trip(uid, suffix="b")
    text = _antwort(monkeypatch, mit, uid, "HILFE 2")
    _pruefe_laenge(text, "HILFE 2 ziellos")
    assert text == seite2, (text, seite2)
