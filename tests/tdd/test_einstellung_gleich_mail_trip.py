"""Pruefkatalog Trip -- Issue #3047 Phase 1, Arbeitspaket A („Einstellung = Mail").

SPEC: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md
(AC-2, AC-3, AC-4, AC-8 Trip, AC-9, AC-10 Trip, AC-11 Trip, AC-12 Trip,
AC-15, AC-17).

Jeder Fall nimmt ein rohes Trip-JSON im Persistenzformat (Array in
Katalogfolge, eingestellte Position allein in ``order``), schickt es durch den
echten Loader, die Kaskade, den Renderer und den Versandweg
(``NotificationService.send_trip_report``) und liest die Mail aus der
Transport-Mitschrift -- HTML-Teil, Klartext-Teil bzw. Kompakttext. Das Soll
stammt aus dem rohen JSON und dem statischen Register
(``tests/helpers/einstellung_gleich_mail_trip.py``), nie aus ``resolve_*``.
Kein ``Mock()``/``patch()``/``MagicMock``; einzige Naht ist der Transport.

Die Faelle stehen in ``tests/fixtures/einstellung_gleich_mail/fallliste_trip.json``
(Status ``gruen``/``rot_erwartet``/``ausnahme``/``offen_feature``). Ein Fall
``rot_erwartet`` laeuft hier als ``xfail(strict=True)`` -- der RED-Nachweis
aus Nutzersicht steht in ``docs/artifacts/feat-3047/red_paket_a_trip.txt``
(Lauf mit ``--runxfail``). Die Behebungspakete setzen den Status auf
``gruen``; damit faellt das ``xfail`` automatisch weg.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest
from freezegun import freeze_time

from services.day_comparison import DayComparison
from tests.helpers.einstellung_gleich_mail_orte import katalogtext
from tests.helpers.einstellung_gleich_mail_trip import (
    html_ausblick, html_tabellen, html_text, klartext_ausblick,
    klartext_tabellen, soll_ausblick, soll_ausblickformen, soll_grundauswahl,
    soll_stundenformen, soll_stundenspalten,
)
from tests.helpers.transport_mitschrift import aufzeichner_installieren
from tests.tdd._einstellung_gleich_mail_trip_fixtures import (
    AUSBLICK_TAGE, BASIS_KATALOG, STAGE_NAME, eml_aus_mitschrift, mail_sendung, mail_teile,
    metrik_eintraege, render_trip_mit_ausblick, trip_json,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "einstellung_gleich_mail"
_FALLLISTE = json.loads((FIXTURES / "fallliste_trip.json").read_text(encoding="utf-8"))


def _faelle(testname: str) -> list:
    """Die Faelle der Fallliste fuer ``testname``; ``rot_erwartet`` -> xfail."""
    params = []
    for f in _FALLLISTE["faelle"]:
        if f["test"] != testname or f["status"] == "offen_feature":
            continue
        marks = []
        if f["status"] == "rot_erwartet":
            marks.append(pytest.mark.xfail(strict=True, reason=f"#3047 RED {f['befund']}"))
        params.append(pytest.param(f, id=f["id"], marks=marks))
    assert params, f"Fallliste ohne Faelle fuer {testname}"
    return params


def _variante(fall: dict) -> str:
    """ID-Schema ``trip-<thema>--<variante>--<format>``."""
    return fall["id"].split("--")[1]


# ---------------------------------------------------------------------------
# Muster der Dimensionen (Spec §3)
# ---------------------------------------------------------------------------

KATALOG = list(BASIS_KATALOG)
MUSTER = {
    "katalog": KATALOG,
    "umkehrung": KATALOG[::-1],
    # AC-2: Boeen vor Temperatur vor Niederschlag vor Wind.
    "gemischt": ["gust", "temperature", "precipitation", "wind", "cloud_total",
                 "uv_index", "wind_direction"],
}
#: Grundauswahl-Folge fuer Faelle mit eigener Liste: weder Katalog noch eines
#: der Listenmuster -- so beweist jede Listenfolge, dass sie selbst wirkt.
GLOBAL_ANDERS = ["precipitation", "uv_index", "wind", "temperature", "cloud_total",
                 "gust", "wind_direction"]
OHNE_BEI_TEILMENGE = ("wind", "uv_index")
EINFACH = {"roh": set(), "gemischt": {"cloud_total", "gust", "uv_index"},
           "einfach": set(KATALOG)}

for _name, _folge in MUSTER.items():
    assert sorted(_folge) == sorted(KATALOG), _name
    assert _name == "katalog" or _folge != KATALOG, f"Muster {_name} gleicht der Katalogfolge"
assert GLOBAL_ANDERS not in MUSTER.values()


def _formate(einfach: set[str]) -> dict[str, bool]:
    return {m: m in einfach for m in KATALOG}


def paarfall_json(liste: str, werte: dict) -> dict:
    """Rohes Trip-JSON zu einem Paarfall (Werte der vier Dimensionen)."""
    a, r, d = werte["auswahl_muster"], werte["reihenfolge"], werte["darstellung"]
    einfach, folge = EINFACH[d], MUSTER[r]
    if a == "nie_eingestellt":
        data = trip_json(folge, einfach=einfach, outlook_metric_formats=_formate(einfach))
    else:
        if a == "bewusst_leer":
            listenfolge: list[str] = []
        elif a == "alles":
            listenfolge = list(folge)
        else:
            listenfolge = [m for m in folge if m not in OHNE_BEI_TEILMENGE]
        if liste == "trip_ausblick":
            data = trip_json(GLOBAL_ANDERS, einfach=einfach, outlook_metrics=listenfolge,
                             outlook_metric_formats=_formate(einfach))
        else:
            layout = metrik_eintraege(listenfolge, einfach=einfach) if listenfolge else []
            data = trip_json(GLOBAL_ANDERS, einfach=einfach, email_layout=layout)
    if werte["format"] == "kompakt":
        data["report_config"]["email_format"] = "compact"
    return data


# ---------------------------------------------------------------------------
# Senden + Lesen
# ---------------------------------------------------------------------------


def _senden(monkeypatch, data: dict, fmt: str, **kw) -> tuple:
    """(HTML oder None, Klartext/Kompakttext, Mitschrift) einer Mail."""
    data = copy.deepcopy(data)
    if fmt == "kompakt":
        data["report_config"]["email_format"] = "compact"
    mitschrift, _trip, _uid = render_trip_mit_ausblick(monkeypatch, data, **kw)
    html, text = mail_teile(mitschrift)
    if fmt == "kompakt":
        assert html is None and mail_sendung(mitschrift)["mail_format"] == "compact", (
            "Kompaktformat muss eine reine Klartext-Mail ohne HTML-Teil sein")
    else:
        assert html, "Vollformat ohne HTML-Teil"
    return html, text, mitschrift


def _stundentabellen(html, text, fmt: str, art: str):
    return html_tabellen(html)[art] if fmt == "html" else klartext_tabellen(text)[art]


def _ausblick(html, text, fmt: str):
    return html_ausblick(html) if fmt == "html" else klartext_ausblick(text, AUSBLICK_TAGE)


def _pruefe_spalten(tabellen, soll: list[str], wo: str) -> None:
    if not soll:
        assert all(t.spalten == [] for t in tabellen), (
            f"{wo}: bewusst leere Auswahl, aber Spalten {[t.spalten for t in tabellen]}")
        return
    assert tabellen, f"{wo}: Tabelle fehlt, Soll {soll}"
    for t in tabellen:
        assert t.spalten == soll, f"{wo}: Spaltenfolge {t.spalten} != Soll {soll}"


def _pruefe_formen(ist: dict, soll: dict, wo: str) -> None:
    abweichung = {m: (ist.get(m), f) for m, f in soll.items()
                  if f is not None and ist.get(m) != f}
    assert not abweichung, f"{wo}: Darstellung (Ist, Soll) weicht ab: {abweichung}"


def _pruefe_kompakt_ohne_tabellen(text: str, wo: str) -> None:
    tabs = klartext_tabellen(text)
    assert tabs == {"etappe": [], "nacht": []}, f"{wo}: Kompaktformat mit Stundentabelle"


# ---------------------------------------------------------------------------
# Paarweise Faelle (Spec §3) -- je Liste
# ---------------------------------------------------------------------------


def _paar_tabelle(monkeypatch, fall: dict, art: str) -> None:
    data = paarfall_json(fall["liste"], fall["werte"])
    fmt = fall["format"]
    html, text, _ = _senden(monkeypatch, data, fmt)
    wo = f"{fall['id']} ({art}, {fmt})"
    if fmt == "kompakt":
        _pruefe_kompakt_ohne_tabellen(text, wo)
        return
    tabellen = _stundentabellen(html, text, fmt, art)
    soll = soll_stundenspalten(data)
    if fall["pruefung"] != "darstellung":
        _pruefe_spalten(tabellen, soll, wo)
        return
    # Darstellung: nur Menge + Form je Spalte -- die Folge prueft der
    # Schwesterfall derselben Zeile (eine Aussage je Fall).
    teil = "html" if fmt == "html" else "klartext"
    assert tabellen, f"{wo}: Tabelle fehlt"
    for t in tabellen:
        assert set(t.spalten) == set(soll), f"{wo}: Auswahl {t.spalten} != {soll}"
        _pruefe_formen(t.formen(), soll_stundenformen(data, teil), wo)


@pytest.mark.parametrize("fall", _faelle("test_paarweise_stundentabelle"))
def test_paarweise_stundentabelle(monkeypatch, fall):
    """Etappen-Stundentabelle: Auswahl, Reihenfolge exakt, Roh/Einfach je
    Spalte -- paarweise ueber Auswahl-Muster, Reihenfolge, Darstellung, Format."""
    _paar_tabelle(monkeypatch, fall, "etappe")


@pytest.mark.parametrize("fall", _faelle("test_paarweise_nachttabelle"))
def test_paarweise_nachttabelle(monkeypatch, fall):
    """Nacht-Stundentabelle am Ziel: dieselbe E-Mail-Liste wie die Etappe."""
    _paar_tabelle(monkeypatch, fall, "nacht")


@pytest.mark.parametrize("fall", _faelle("test_paarweise_ausblick"))
def test_paarweise_ausblick(monkeypatch, fall):
    """3-Tages-Ausblick in HTML, Klartext und Kompaktformat."""
    data = paarfall_json(fall["liste"], fall["werte"])
    fmt = fall["format"]
    html, text, _ = _senden(monkeypatch, data, fmt)
    wo = f"{fall['id']} (ausblick, {fmt})"
    tab = _ausblick(html, text, fmt)
    soll = soll_ausblick(data)
    if soll is None:
        assert tab is None, f"{wo}: bewusst leer, Ausblick erscheint trotzdem: {tab.spalten}"
        return
    assert tab is not None, f"{wo}: Ausblick fehlt, Soll {soll}"
    if fall["pruefung"] == "darstellung":
        assert set(tab.spalten) == set(soll), f"{wo}: Auswahl {tab.spalten} != {soll}"
        _pruefe_formen(tab.formen(), soll_ausblickformen(data, soll), wo)
        return
    assert tab.spalten == soll, f"{wo}: Spaltenfolge {tab.spalten} != Soll {soll}"


# ---------------------------------------------------------------------------
# AC-2 / AC-3 / AC-15 -- Stunden- und Nachttabelle
# ---------------------------------------------------------------------------

_AC2 = {
    "boeen_temp_regen_wind": ["gust", "temperature", "precipitation", "wind"],
    "umkehrung": KATALOG[::-1],
    "teilmenge_zwei_ab": [m for m in MUSTER["gemischt"] if m not in ("uv_index", "cloud_total")],
}


@pytest.mark.parametrize("fall", _faelle("test_ac2_stundentabelle_folge"))
def test_ac2_stundentabelle_folge(monkeypatch, fall):
    """AC-2: gespeicherte E-Mail-Folge (ungleich Katalog) steht genau so in
    der Etappentabelle, jede Spalte einmal, keine nicht angehakte."""
    folge = _AC2[_variante(fall)]
    data = trip_json(GLOBAL_ANDERS, email_layout=metrik_eintraege(folge))
    html, text, _ = _senden(monkeypatch, data, fall["format"])
    soll = soll_stundenspalten(data)
    assert soll == folge, f"Orakel-Vorbedingung: {soll} != {folge}"
    tabellen = _stundentabellen(html, text, fall["format"], "etappe")
    _pruefe_spalten(tabellen, folge, fall["id"])
    for t in tabellen:
        assert len(set(t.spalten)) == len(t.spalten), f"Spalte doppelt: {t.spalten}"


@pytest.mark.parametrize("fall", _faelle("test_ac3_nachttabelle_folge"))
def test_ac3_nachttabelle_folge(monkeypatch, fall):
    """AC-3: Nachttabelle zeigt genau Wind, Temperatur, Boeen in dieser Folge."""
    folge = ["wind", "temperature", "gust"]
    data = trip_json(GLOBAL_ANDERS, email_layout=metrik_eintraege(folge))
    html, text, _ = _senden(monkeypatch, data, fall["format"])
    _pruefe_spalten(_stundentabellen(html, text, fall["format"], "nacht"), folge, fall["id"])


@pytest.mark.parametrize("fall", _faelle("test_ac15_nacht_darstellung_wie_etappe"))
def test_ac15_nacht_darstellung_wie_etappe(monkeypatch, fall):
    """AC-3/AC-15: jede Spalte der Nachttabelle zeigt dieselbe Roh/Einfach-
    Form wie in der Etappentabelle derselben Mail und wie eingestellt
    (Windrichtung und Bewoelkung auf Roh, Boeen-Ampel auf Einfach)."""
    folge = ["wind_direction", "temperature", "cloud_total", "uv_index"]
    data = trip_json(folge, einfach={"uv_index"})
    fmt = fall["format"]
    html, text, _ = _senden(monkeypatch, data, fmt)
    etappe = _stundentabellen(html, text, fmt, "etappe")
    nacht = _stundentabellen(html, text, fmt, "nacht")
    assert etappe and nacht, "Vorbedingung: Etappen- und Nachttabelle vorhanden"
    teil = "html" if fmt == "html" else "klartext"
    soll = soll_stundenformen(data, teil)
    _pruefe_formen(etappe[0].formen(), soll, f"{fall['id']} Etappe")
    _pruefe_formen(nacht[0].formen(), etappe[0].formen(), f"{fall['id']} Nacht gegen Etappe")


# ---------------------------------------------------------------------------
# AC-4 -- Ausblick
# ---------------------------------------------------------------------------

_AC4_GRUND = ["gust", "temperature", "thunder", "precipitation", "wind"]


@pytest.mark.parametrize("fall", _faelle("test_ac4_ausblick_gespeicherte_folge"))
def test_ac4_ausblick_gespeicherte_folge(monkeypatch, fall):
    """AC-4: gespeicherter Ausblick Wind, Temperatur, Niederschlag; Boeen und
    Gewitter stehen nur in der Grundauswahl und erscheinen nicht."""
    folge = ["wind", "temperature", "precipitation"]
    data = trip_json(_AC4_GRUND, outlook_metrics=folge)
    html, text, _ = _senden(monkeypatch, data, fall["format"])
    tab = _ausblick(html, text, fall["format"])
    assert tab is not None and tab.spalten == folge, (
        f"{fall['id']}: Ausblick {tab and tab.spalten} != {folge}")


@pytest.mark.parametrize("fall", _faelle("test_ac4_ausblick_nie_eingestellt"))
def test_ac4_ausblick_nie_eingestellt(monkeypatch, fall):
    """AC-4/T1: nie eingestellter Ausblick zeigt die ganze Grundauswahl in der
    EINGESTELLTEN Folge der Trip-Metriken (wie der Reiter), nicht in
    Katalog-/Array-Folge."""
    data = trip_json(_AC4_GRUND)
    soll = soll_grundauswahl(data)
    assert soll == _AC4_GRUND, f"Orakel-Vorbedingung: {soll}"
    katalog = [m["metric_id"] for m in data["display_config"]["metrics"] if m["enabled"]]
    assert katalog != soll, "Vorbedingung: Katalogfolge muss von der eingestellten abweichen"
    html, text, _ = _senden(monkeypatch, data, fall["format"])
    tab = _ausblick(html, text, fall["format"])
    assert tab is not None, f"{fall['id']}: Ausblick fehlt"
    assert tab.spalten == soll, (
        f"{fall['id']}: Ausblick {tab.spalten} != eingestellte Folge {soll} "
        f"(Katalogfolge waere {katalog})")


@pytest.mark.parametrize("fall", _faelle("test_ac4_ausblick_bewusst_leer"))
def test_ac4_ausblick_bewusst_leer(monkeypatch, fall):
    """AC-4: bewusst leere Ausblick-Auswahl laesst den Block entfallen."""
    data = trip_json(_AC4_GRUND, outlook_metrics=[])
    html, text, _ = _senden(monkeypatch, data, fall["format"])
    tab = _ausblick(html, text, fall["format"])
    assert tab is None, f"{fall['id']}: Ausblick trotz leerer Auswahl: {tab.spalten}"


@pytest.mark.parametrize("fall", _faelle("test_ausblick_ausgeschaltet"))
def test_ausblick_ausgeschaltet(monkeypatch, fall):
    """Spec §2 Punkt 5: ``show_outlook`` aus -> kein Ausblick, obwohl
    Tageszeilen vorliegen; Gegenprobe mit ``show_outlook`` an."""
    data = trip_json(_AC4_GRUND, outlook_metrics=["wind"])
    html, text, _ = _senden(monkeypatch, data, fall["format"])
    assert _ausblick(html, text, fall["format"]) is not None, "Gegenprobe: Ausblick an"
    data["report_config"]["show_outlook"] = False
    html, text, _ = _senden(monkeypatch, data, fall["format"])
    tab = _ausblick(html, text, fall["format"])
    if fall["status"] == "ausnahme":
        # #722: render_compact ignoriert die Baustein-Schalter (compact.py,
        # Docstring) -- gewollte, in der Fallliste benannte Abweichung.
        assert tab is not None and tab.spalten == ["wind"], tab
        return
    assert tab is None, f"{fall['id']}: Ausblick trotz show_outlook=false: {tab.spalten}"


#: Variante -> (abgeschalteter Bericht, Schalter am Metrik-Eintrag).
_BERICHT_AUS = {"morgen_aus": ("morning", "morning_enabled"),
                "abend_aus": ("evening", "evening_enabled")}


@pytest.mark.parametrize("fall", _faelle("test_ein_aus_metrik_je_bericht"))
def test_ein_aus_metrik_je_bericht(monkeypatch, fall):
    """Spec §2 Punkt 5 (#3047 H4, Nachpruefung Punkt 6): Boeen sind am
    gespeicherten Metrik-Eintrag fuer EINEN Bericht ausgeschaltet
    (``morning_enabled``/``evening_enabled`` = false). Die Mail dieses
    Berichts zeigt Boeen in keiner Liste (Etappe, Nacht, Ausblick); die Mail
    des anderen Berichts ist unberuehrt und zeigt Boeen in gespeicherter Folge."""
    aus_bericht, schalter = _BERICHT_AUS[_variante(fall)]
    folge = ["gust", "temperature", "wind"]
    data = trip_json(folge, outlook_metrics=["gust", "temperature"])
    for eintrag in data["display_config"]["metrics"]:
        if eintrag["metric_id"] == "gust":
            eintrag[schalter] = False
    fmt = fall["format"]
    for bericht in ("morning", "evening"):
        html, text, _ = _senden(monkeypatch, data, fmt, report_type=bericht)
        aus = bericht == aus_bericht
        soll = [m for m in folge if not (aus and m == "gust")]
        wo = f"{fall['id']} ({bericht})"
        for art in ("etappe", "nacht"):
            _pruefe_spalten(_stundentabellen(html, text, fmt, art), soll, f"{wo} {art}")
        tab = _ausblick(html, text, fmt)
        soll_ausblick_folge = ["temperature"] if aus else ["gust", "temperature"]
        assert tab is not None and tab.spalten == soll_ausblick_folge, (
            f"{wo}: Ausblick {tab and tab.spalten} != {soll_ausblick_folge}")


#: Variante -> (eingeschalteter Bericht, Schalter am Metrik-Eintrag).
_BERICHT_AN = {"morgen_an": ("morning", "morning_enabled"),
               "abend_an": ("evening", "evening_enabled")}


@pytest.mark.parametrize("fall", _faelle("test_ein_metrik_nur_je_bericht_eingeschaltet"))
def test_ein_metrik_nur_je_bericht_eingeschaltet(monkeypatch, fall):
    """#3047 N3 (Altbestand ``morning_enabled``/``evening_enabled`` je Metrik,
    positiver Zweig): Boeen sind global AUS (``enabled: false``), aber fuer
    EINEN Bericht ausdruecklich eingeschaltet (``morning_enabled`` bzw.
    ``evening_enabled`` = true). Die Mail dieses Berichts zeigt Boeen an der
    gespeicherten Position in Etappen-, Nachttabelle und Ausblick; die Mail
    des anderen Berichts zeigt sie in keiner Liste."""
    an_bericht, schalter = _BERICHT_AN[_variante(fall)]
    folge = ["gust", "temperature", "wind"]
    data = trip_json(folge, outlook_metrics=["gust", "temperature"])
    for eintrag in data["display_config"]["metrics"]:
        if eintrag["metric_id"] == "gust":
            eintrag["enabled"] = False
            eintrag[schalter] = True
    fmt = fall["format"]
    for bericht in ("morning", "evening"):
        html, text, _ = _senden(monkeypatch, data, fmt, report_type=bericht)
        an = bericht == an_bericht
        soll = folge if an else [m for m in folge if m != "gust"]
        wo = f"{fall['id']} ({bericht})"
        for art in ("etappe", "nacht"):
            _pruefe_spalten(_stundentabellen(html, text, fmt, art), soll, f"{wo} {art}")
        tab = _ausblick(html, text, fmt)
        soll_ausblick_folge = ["gust", "temperature"] if an else ["temperature"]
        assert tab is not None and tab.spalten == soll_ausblick_folge, (
            f"{wo}: Ausblick {tab and tab.spalten} != {soll_ausblick_folge}")


_ANDERER_BERICHT = {"morning": "evening", "evening": "morning"}


@pytest.mark.parametrize("fall", _faelle("test_f007_ausblick_zellen_je_bericht"))
def test_f007_ausblick_zellen_je_bericht(monkeypatch, fall):
    """#3047 F007 (vierte Pruefung): Boeen sind global AUS, aber fuer EINEN
    Bericht ein (``enabled: false``, ``<bericht>_enabled: true``);
    Niederschlag ist global EIN, aber fuer denselben Bericht aus
    (``<bericht>_enabled: false``). Die Ausblick-Zeilen entstehen ueber den
    Zeilenbau des Zeitplaners. Der Ausblick dieses Berichts zeigt Boeen und
    Temperatur, der des anderen Berichts Niederschlag und Temperatur -- und
    zwar mit den WERTEN der jeweiligen Groesse: jede Zelle gleicht der Zelle
    derselben Groesse in einer Referenz-Mail ohne Bericht-Schalter (eine
    Spalte mit fremdem Wert -- Kopf aus dem einen, Zeile aus dem anderen
    Bericht -- faellt so auf)."""
    bericht = {"morgen": "morning", "abend": "evening"}[_variante(fall)]
    folge = ["gust", "precipitation", "temperature"]
    data = trip_json(folge, outlook_metrics=folge)
    for eintrag in data["display_config"]["metrics"]:
        if eintrag["metric_id"] == "gust":
            eintrag["enabled"] = False
            eintrag[f"{bericht}_enabled"] = True
        elif eintrag["metric_id"] == "precipitation":
            eintrag[f"{bericht}_enabled"] = False
    fmt = fall["format"]
    for rt, soll in ((bericht, ["gust", "temperature"]),
                     (_ANDERER_BERICHT[bericht], ["precipitation", "temperature"])):
        wo = f"{fall['id']} ({rt})"
        rh, rtext, _ = _senden(monkeypatch, trip_json(folge, outlook_metrics=folge), fmt,
                               report_type=rt)
        ref = _ausblick(rh, rtext, fmt)
        assert ref is not None and ref.spalten == folge, f"{wo}: Referenz {ref and ref.spalten}"
        html, text, _ = _senden(monkeypatch, data, fmt, report_type=rt)
        tab = _ausblick(html, text, fmt)
        assert tab is not None and tab.spalten == soll, f"{wo}: Ausblick {tab and tab.spalten}"
        for m in soll:
            assert tab.spalte(m) == ref.spalte(m), (
                f"{wo}: Ausblick-Zellen {m} {tab.spalte(m)} != Referenz {ref.spalte(m)}")


# ---------------------------------------------------------------------------
# AC-8 -- Roh/Einfach
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fall", _faelle("test_ac8_stunden_roh_einfach"))
def test_ac8_stunden_roh_einfach(monkeypatch, fall):
    """AC-8: Windrichtung Roh -> Zahl, Bewoelkung Einfach -> Symbol (ohne
    Wind, damit #435 nicht greift)."""
    folge = ["wind_direction", "cloud_total", "temperature"]
    data = trip_json(folge, einfach={"cloud_total"})
    html, text, _ = _senden(monkeypatch, data, fall["format"])
    tab = _stundentabellen(html, text, fall["format"], "etappe")[0]
    assert tab.spalten == folge
    assert tab.formen() == {"wind_direction": "zahl", "cloud_total": "einfach",
                            "temperature": "zahl"}, tab.zellen[:1]


@pytest.mark.parametrize("fall", _faelle("test_ac8_einfach_ohne_einfachform_zeigt_zahl"))
def test_ac8_einfach_ohne_einfachform_zeigt_zahl(monkeypatch, fall):
    """AC-8: auf Einfach gestellt, aber ohne Einfach-Form (UV, Temperatur) ->
    weiterhin die Zahl."""
    folge = ["uv_index", "temperature"]
    data = trip_json(folge, einfach={"uv_index", "temperature"})
    html, text, _ = _senden(monkeypatch, data, fall["format"])
    tab = _stundentabellen(html, text, fall["format"], "etappe")[0]
    assert tab.formen() == {"uv_index": "zahl", "temperature": "zahl"}, tab.zellen[:1]


@pytest.mark.parametrize("fall", _faelle("test_ac8_windrichtung_einfach_verschmilzt_mit_wind"))
def test_ac8_windrichtung_einfach_verschmilzt_mit_wind(monkeypatch, fall):
    """Ausnahme #435: Windrichtung auf Einfach (Skala) steht als Himmels-
    richtung in der Wind-Zelle, nicht als eigene Spalte."""
    data = trip_json(["wind", "wind_direction", "temperature"], einfach={"wind_direction"})
    html, text, _ = _senden(monkeypatch, data, fall["format"])
    tab = _stundentabellen(html, text, fall["format"], "etappe")[0]
    assert tab.spalten == ["wind", "temperature"], tab.spalten
    assert tab.spalte("wind")[0].split()[-1] in {"N", "NE", "E", "SE", "S", "SW", "W", "NW"}


_KOMPASS = {"N", "NE", "E", "SE", "S", "SW", "W", "NW"}


@pytest.mark.parametrize("fall", _faelle("test_f004_wind_einfach_mit_richtung_einfach"))
def test_f004_wind_einfach_mit_richtung_einfach(monkeypatch, fall):
    """#3047 F004 (vierte Pruefung, Kanal-Paritaet): Wind UND Windrichtung auf
    Einfach. Die Windrichtung verschmilzt in die Wind-Zelle (#435); der
    Klartext zeigt "20 W", die HTML-Zelle den Ampelpunkt (#814) UND dieselbe
    Himmelsrichtung -- je Zeile dieselbe Richtung wie der Klartext, in
    Etappen- und Nachttabelle."""
    from tests.helpers.einstellung_gleich_mail_trip import zellform

    data = trip_json(["wind", "wind_direction", "temperature"],
                     einfach={"wind", "wind_direction"})
    html, text, _ = _senden(monkeypatch, data, "html")
    art = "nacht" if fall["liste"] == "trip_nachttabelle" else "etappe"
    klar = klartext_tabellen(text)[art]
    assert klar and klar[0].spalten == ["wind", "temperature"], klar
    richtungen = [z.split()[-1] if z.split() else "" for z in klar[0].spalte("wind")]
    assert richtungen and set(richtungen) <= _KOMPASS, f"Klartext ohne Richtung: {richtungen}"
    if fall["format"] == "klartext":
        return
    tabellen = html_tabellen(html)[art]
    assert tabellen, f"{fall['id']}: HTML-Tabelle fehlt"
    for tab in tabellen:
        assert tab.spalten == ["wind", "temperature"], tab.spalten
        zellen = tab.spalte("wind")
        ist = [z.split()[-1] if z.split() else "" for z in zellen]
        assert ist == richtungen, f"{fall['id']}: HTML-Richtung {ist} != Klartext {richtungen}"
        j = tab.spalten.index("wind")
        formen = {zellform(z[j], f[j]) for z, f in zip(tab.zellen, tab.fragmente)}
        assert formen == {"einfach"}, f"{fall['id']}: Wind-Zelle ohne Ampelpunkt: {tab.zellen[:1]}"


@pytest.mark.parametrize("fall", _faelle("test_ac8_ampel_groesse_einfach"))
def test_ac8_ampel_groesse_einfach(monkeypatch, fall):
    """#814: Boeen auf Einfach -> HTML Ampelpunkt (Einfach-Form), Klartext
    die Zahl (gewollte Ausnahme)."""
    data = trip_json(["gust", "temperature"], einfach={"gust"})
    html, text, _ = _senden(monkeypatch, data, fall["format"])
    tab = _stundentabellen(html, text, fall["format"], "etappe")[0]
    erwartet = "einfach" if fall["format"] == "html" else "zahl"
    assert tab.formen()["gust"] == erwartet, tab.zellen[:1]


@pytest.mark.parametrize("fall", _faelle("test_ac8_ausblick_roh_einfach"))
def test_ac8_ausblick_roh_einfach(monkeypatch, fall):
    """AC-8: Ausblick -- Windrichtung und Boeen Einfach, Niederschlag und
    Bewoelkung Roh, je Zelle gegen ``outlook_metric_formats``."""
    folge = ["wind_direction", "precipitation", "gust", "cloud_total"]
    fmts = {"wind_direction": True, "gust": True, "precipitation": False, "cloud_total": False}
    # #3047 N7: zusaetzlich die Umkehrung (jede Groesse einmal Roh, einmal
    # Einfach) -- so faengt der Fall auch eine je Groesse fest verdrahtete Form,
    # insbesondere im Kompakt-Ausblick.
    for zuordnung in (fmts, {m: not v for m, v in fmts.items()}):
        data = trip_json(folge, outlook_metrics=folge, outlook_metric_formats=zuordnung)
        html, text, _ = _senden(monkeypatch, data, fall["format"])
        tab = _ausblick(html, text, fall["format"])
        assert tab is not None and tab.spalten == folge
        soll = {m: "einfach" if zuordnung[m] else "zahl" for m in folge}
        assert tab.formen() == soll, (zuordnung, tab.zellen[:1])


@pytest.mark.parametrize("fall", _faelle("test_ac8_ausblick_ohne_einfachform"))
def test_ac8_ausblick_ohne_einfachform(monkeypatch, fall):
    """Ausnahme #814 AC-5 / Spec §2 Punkt 3: Sicht und Temperatur zeigen trotz
    Einfach die Zahl (Temperatur als Spanne Tief/Hoch), Gewitter zeigt schon
    roh das Stufenwort."""
    folge = ["visibility", "temperature", "thunder"]
    data = trip_json(folge, outlook_metrics=folge,
                     outlook_metric_formats={m: True for m in folge})
    html, text, _ = _senden(monkeypatch, data, fall["format"])
    tab = _ausblick(html, text, fall["format"])
    assert tab is not None and tab.spalten == folge
    formen = tab.formen()
    assert formen["visibility"] == "zahl" and formen["temperature"] == "zahl", tab.zellen[:1]
    assert "/" in tab.spalte("temperature")[0], "Temperatur als Spanne Tief/Hoch"
    assert formen["thunder"] == "einfach", tab.zellen[:1]


# ---------------------------------------------------------------------------
# AC-9 -- Zusatzbloecke
# ---------------------------------------------------------------------------

_VORTAG = dict(wind_delta_kmh=15.0, gust_delta_kmh=20.0, precip_delta_mm=6.0)
_SCHALTER = {
    "nachtblock": ("display_config", "show_night_block"),
    "etappenkennzahlen": ("report_config", "show_stage_stats"),
    "vortag": ("report_config", "show_yesterday_comparison"),
}


def _zeilen(text: str) -> list[str]:
    return [z for z in text.splitlines() if z.strip() and not z.startswith("Generated:")]


@pytest.mark.parametrize("fall", _faelle("test_ac9_zusatzblock_aus"))
def test_ac9_zusatzblock_aus(monkeypatch, fall):
    """AC-9: je ein Schalter aus -> genau dieser Block fehlt in HTML und
    Klartext, alle uebrigen Klartext-Zeilen bleiben unveraendert."""
    variante, fmt = _variante(fall), fall["format"]
    data = trip_json(["wind", "temperature", "precipitation"], outlook_metrics=["wind"])
    kw = {"day_comparison": DayComparison(**_VORTAG)}
    html_an, text_an, _ = _senden(monkeypatch, data, fmt, **kw)
    teil, schluessel = _SCHALTER[variante]
    data[teil][schluessel] = False
    html_aus, text_aus, _ = _senden(monkeypatch, data, fmt, **kw)
    weg = [z for z in _zeilen(text_an) if z not in _zeilen(text_aus)]
    neu = [z for z in _zeilen(text_aus) if z not in _zeilen(text_an)]
    assert weg, f"{fall['id']}: Schalter ohne Wirkung im Klartext"
    assert not neu, f"{fall['id']}: Schalter veraendert andere Zeilen: {neu}"
    if variante == "nachtblock":
        assert not klartext_tabellen(text_aus)["nacht"] and klartext_tabellen(text_an)["nacht"]
        assert not html_tabellen(html_aus)["nacht"] and html_tabellen(html_an)["nacht"]
        return
    marke = "12.0 km" if variante == "etappenkennzahlen" else weg[0].split(":")[-1].strip()
    assert any(marke in z for z in weg), f"{fall['id']}: entfernt wurde {weg}"
    ziel_an, ziel_aus = ((html_text(html_an), html_text(html_aus)) if fmt == "html"
                         else (text_an, text_aus))
    assert marke in ziel_an and marke not in ziel_aus, (
        f"{fall['id']}: Block {marke!r} an={marke in ziel_an} aus={marke in ziel_aus}")


@pytest.mark.parametrize("fall", _faelle("test_ac9_email_format_kompakt"))
def test_ac9_email_format_kompakt(monkeypatch, fall):
    """AC-9: ``email_format=compact`` -> nur Klartext ohne HTML-Teil, ASCII,
    Ausblick bleibt, Stundentabellen entfallen."""
    data = trip_json(["wind", "temperature"], outlook_metrics=["temperature", "wind"])
    _html, text, _ = _senden(monkeypatch, data, "kompakt")
    assert text.isascii(), "Kompaktformat muss ASCII sein"
    _pruefe_kompakt_ohne_tabellen(text, fall["id"])
    tab = klartext_ausblick(text, AUSBLICK_TAGE)
    assert tab is not None and tab.spalten == ["temperature", "wind"]


# ---------------------------------------------------------------------------
# AC-10 -- Grundauswahl-Kopplung
# ---------------------------------------------------------------------------


def _listen_spalten(html, text, fall) -> list:
    """Gelesene Spalten der Liste des Falls (je Tabelle eine Liste)."""
    fmt, liste = fall["format"], fall["liste"]
    if liste == "trip_ausblick":
        tab = _ausblick(html, text, fmt)
        return [tab.spalten] if tab else []
    art = "etappe" if liste == "trip_stundentabelle" else "nacht"
    return [t.spalten for t in _stundentabellen(html, text, fmt, art)]


@pytest.mark.parametrize("fall", _faelle("test_ac10_abgewaehlt_erscheint_nirgends"))
def test_ac10_abgewaehlt_erscheint_nirgends(monkeypatch, fall):
    """AC-10: UV ist in der Grundauswahl abgewaehlt, steht aber gespeichert in
    der E-Mail-Liste und im Ausblick -> UV erscheint in keiner Liste, die
    uebrigen in gespeicherter Folge."""
    liste_folge = ["uv_index", "gust", "temperature", "wind"]
    layout = metrik_eintraege(liste_folge)
    data = trip_json(["wind", "gust", "temperature"], email_layout=layout,
                     outlook_metrics=liste_folge)
    html, text, _ = _senden(monkeypatch, data, fall["format"])
    gelesen = _listen_spalten(html, text, fall)
    assert gelesen, f"{fall['id']}: Liste fehlt"
    for spalten in gelesen:
        assert spalten == ["gust", "temperature", "wind"], f"{fall['id']}: {spalten}"


@pytest.mark.parametrize("fall", _faelle("test_ac10_neue_metrik_hinten_angehaengt"))
def test_ac10_neue_metrik_hinten_angehaengt(monkeypatch, fall):
    """AC-10 (Mail-Seite): UV neu in die Grundauswahl aufgenommen und -- wie
    der Editor es beim Einschalten ablegt -- hinten an die bearbeitete
    E-Mail-Liste und den bearbeiteten Ausblick angehaengt -> UV steht in jeder
    Liste am Ende, die bestehende Folge bleibt. (Dass der Editor eine global
    eingeschaltete Metrik in eine bestehende Kanal-Liste schreibt, ist Befund
    T3 und steht als ``offen_feature`` in der Fallliste.)"""
    bisher = ["gust", "temperature", "wind"]
    neu = bisher + ["uv_index"]
    data = trip_json(neu, email_layout=metrik_eintraege(neu), outlook_metrics=neu)
    html, text, _ = _senden(monkeypatch, data, fall["format"])
    gelesen = _listen_spalten(html, text, fall)
    assert gelesen, f"{fall['id']}: Liste fehlt"
    for spalten in gelesen:
        assert spalten == neu, f"{fall['id']}: {spalten} != {neu}"


@pytest.mark.parametrize("fall", _faelle("test_ac10_leerer_schnitt_rueckfall_grundauswahl"))
def test_ac10_leerer_schnitt_rueckfall_grundauswahl(monkeypatch, fall):
    """AC-10: die gespeicherte Liste enthaelt nur Groessen, die in der
    Grundauswahl abgewaehlt sind -> nach dem Schnitt bliebe nichts; Soll ist
    der dokumentierte Rueckfall auf die volle Grundauswahl (in Katalogfolge
    eingestellt, damit Befund T1 diesen Fall nicht beruehrt), kein
    verschwindender Block."""
    grund = ["temperature", "wind", "gust"]
    data = trip_json(grund, email_layout=metrik_eintraege(["uv_index"]),
                     outlook_metrics=["uv_index"])
    html, text, _ = _senden(monkeypatch, data, fall["format"])
    gelesen = _listen_spalten(html, text, fall)
    assert gelesen, f"{fall['id']}: Liste fehlt"
    for spalten in gelesen:
        assert spalten == grund, f"{fall['id']}: {spalten} != Grundauswahl {grund}"


@pytest.mark.parametrize("fall", _faelle("test_n1_totalschnitt_reine_fremdliste"))
def test_n1_totalschnitt_reine_fremdliste(monkeypatch, fall):
    """#3047 N1 (AC-10, Totalschnitt != bewusst leer): die gespeicherte
    E-Mail-Liste bzw. Ausblick-Liste ist NICHT leer, nennt aber ausschliesslich
    Groessen ausserhalb der Grundauswahl (UV, Bewoelkung) und keinen einzigen
    Grundauswahl-Eintrag -- auch keinen ausgeschalteten. Soll: die volle
    Grundauswahl in ihrer eingestellten Folge (nicht Katalogfolge), kein
    verschwindender Block, in HTML, Klartext und (Ausblick) Kompakt."""
    grund = ["gust", "temperature", "wind"]
    fremd = ["uv_index", "cloud_total"]
    data = trip_json(grund, email_layout=metrik_eintraege(fremd, katalog=tuple(fremd)),
                     outlook_metrics=list(fremd))
    assert grund != [m for m in KATALOG if m in grund], "Vorbedingung: Folge != Katalog"
    html, text, _ = _senden(monkeypatch, data, fall["format"])
    gelesen = _listen_spalten(html, text, fall)
    assert gelesen, f"{fall['id']}: Liste fehlt (Totalschnitt darf den Block nicht leeren)"
    for spalten in gelesen:
        assert spalten == grund, f"{fall['id']}: {spalten} != Grundauswahl {grund}"


# ---------------------------------------------------------------------------
# AC-11 -- Altbestand (Golden)
# ---------------------------------------------------------------------------

_GOLDEN_ZEIT = "2026-07-20 16:00:00"
_GOLDEN_SCHREIBEN = os.environ.get("EINSTELLUNG_GLEICH_MAIL_GOLDEN_SCHREIBEN") == "1"


def _altbestand_mail(monkeypatch) -> tuple[str, str]:
    data = json.loads((FIXTURES / "trip_altbestand.json").read_text(encoding="utf-8"))
    for feld in ("outlook_metric_formats", "channel_layouts", "hourly_metrics", "outlook_metrics"):
        assert feld not in data["display_config"], f"Altbestand darf {feld} nicht tragen"
    with freeze_time(_GOLDEN_ZEIT):
        mitschrift, _trip, _uid = render_trip_mit_ausblick(monkeypatch, data)
    return mail_teile(mitschrift)


@pytest.mark.parametrize("fall", _faelle("test_ac11_altbestand_golden"))
def test_ac11_altbestand_golden(monkeypatch, fall):
    """AC-11: ein Alt-Bestand ohne ``outlook_metric_formats``,
    ``channel_layouts``, ``hourly_metrics``, ``outlook_metrics`` rendert
    zeichengleich zum eingefrorenen Golden (Ist-Stand vor den Behebungen).

    Die Behebungen AC-15 (Nachttabelle Klartext mit ``format_modes``) und
    AC-17 (Klartext-Festtexte „Time"/„… Report" ueber den Katalog) werden den
    Klartext-Golden ausdruecklich und einzeln aendern -- jede dieser
    Golden-Aenderungen wird im Behebungspaket benannt freigegeben, nie
    pauschal neu eingefroren. Der Altbestand traegt durchweg ``order = 0``
    (stabile Folge = Array-Folge), damit Befund T1 den Golden nicht beruehrt.
    """
    html, text = _altbestand_mail(monkeypatch)
    teil, endung = (html, "html") if fall["format"] == "html" else (text, "txt")
    pfad = FIXTURES / f"trip_altbestand_golden.{endung}"
    if _GOLDEN_SCHREIBEN:
        pfad.write_text(teil, encoding="utf-8")
        pytest.fail(f"Golden geschrieben: {pfad} -- Lauf ohne Schalter wiederholen")
    assert teil == pfad.read_text(encoding="utf-8"), (
        f"{fall['id']}: Mail weicht vom Golden {pfad.name} ab")


def _amtliche_gewitterwarnung():
    from datetime import datetime, timezone

    from services.official_alerts.models import OfficialAlert

    return OfficialAlert(
        source="meteofrance_vigilance", hazard="thunderstorm", level=3,
        label="Gewitter", region_label="Pruefregion 3047",
        valid_from=datetime(2026, 7, 20, 6, 0, tzinfo=timezone.utc),
        valid_to=datetime(2026, 7, 20, 20, 0, tzinfo=timezone.utc),
    )


def _wv6_positionen(html, text, fmt: str) -> dict[str, int]:
    """Position von Warnung, Kopf-Einzeiler (Tageslage), Metriken-Ueberblick
    und erster Stundentabelle im gelesenen Mail-Teil; -1 = nicht gefunden.
    Im Klartext zusaetzlich ``kopf_ende`` = erste Leerzeile (Ende des Kopfs)."""
    import re

    from i18n import t

    if fmt == "html":
        body = html[html.find("<body"):]
        tabelle = re.search(r'<table[^>]*data-table="resp"', body)
        return {"warnung": body.find('class="wb'),
                "einzeiler": body.find(t("mail.tageslage.eyebrow", "de")),
                "ueberblick": body.find(t("mail.pille.ueberschrift", "de")),
                "tabelle": tabelle.start() if tabelle else -1}
    zeilen = text.splitlines()

    def _zeile(praefix: str) -> int:
        return next((i for i, z in enumerate(zeilen) if z.startswith(praefix)), -1)

    return {"warnung": _zeile(f"━━ {t('mail.warnungen.ueberschrift', 'de')}"),
            # Der Kopf-Einzeiler (``compact_summary``) beginnt mit dem Etappennamen.
            "einzeiler": _zeile(f"{STAGE_NAME}: "),
            "ueberblick": _zeile(f"━━ {t('mail.pille.ueberschrift', 'de')}"),
            "tabelle": _zeile("━━ Segment"),
            "kopf_ende": zeilen.index("") if "" in zeilen else -1}


@pytest.mark.parametrize("fall", _faelle("test_wv6_amtliche_warnung_zuerst"))
def test_wv6_amtliche_warnung_zuerst(monkeypatch, fall):
    """WV6 (Konzept ``einstellungen_neu.md``): amtliche Warnungen stehen in der
    E-Mail immer zuerst, fest und nicht verschiebbar -- direkt nach dem Kopf,
    vor jedem Inhalt (Kopf-Einzeiler/Tageslage, Metriken-Ueberblick und
    Stundentabelle), unabhaengig von der gespeicherten Metrik-Folge (hier
    Boeen, Temperatur, Niederschlag, Wind)."""
    data = trip_json(["gust", "temperature", "precipitation", "wind"])
    html, text, _ = _senden(monkeypatch, data, fall["format"],
                            official_alerts=[_amtliche_gewitterwarnung()])
    pos = _wv6_positionen(html, text, fall["format"])
    warnung, ueberblick = pos["warnung"], pos["ueberblick"]
    assert warnung >= 0, f"{fall['id']}: amtliche Warnung fehlt in der Mail"
    assert pos["tabelle"] > warnung, (
        f"{fall['id']}: Warnung (Pos. {warnung}) nicht vor der ersten "
        f"Stundentabelle (Pos. {pos['tabelle']})")
    if _variante(fall) == "direkt_nach_kopf":
        assert pos["einzeiler"] >= 0, f"{fall['id']}: Kopf-Einzeiler fehlt in der Mail"
        assert pos["einzeiler"] > warnung, (
            f"{fall['id']}: Warnung (Pos. {warnung}) steht hinter dem "
            f"Kopf-Einzeiler (Pos. {pos['einzeiler']})")
        if fall["format"] == "klartext":
            assert warnung == pos["kopf_ende"] + 1, (
                f"{fall['id']}: Warnung (Zeile {warnung}) folgt nicht direkt "
                f"auf den Kopf (Leerzeile {pos['kopf_ende']})")
    if _variante(fall) == "vor_ueberblick":
        assert ueberblick > warnung, (
            f"{fall['id']}: Warnung (Pos. {warnung}) steht hinter dem "
            f"Metriken-Ueberblick (Pos. {ueberblick})")


#: Register-Standardfolge (``trip_default_rank``) als STUNDENSPALTEN, von Hand
#: aus ``editor_standard.json`` (Liste ``trip_tabellen``, Zustand
#: ``altbestand_ohne_metrics``) uebernommen; Tagestief/-hoch sind
#: Nachtfenster-/Tageswerte ohne Stundenspalte (#1484) und fehlen hier.
_REGISTER_STANDARD_STUNDENSPALTEN = [
    "temperature", "wind", "gust", "precipitation", "thunder", "freezing_level",
    "visibility",
]


@pytest.mark.parametrize("fall", _faelle("test_n1_altbestand_ohne_metrics"))
def test_n1_altbestand_ohne_metrics(monkeypatch, fall):
    """N1 (#3047, frueher Ausnahme #3048) -- behoben.

    Ein Trip-Altbestand, dessen ``display_config`` gar kein ``metrics`` traegt
    (Fall A), zeigt in Etappen- UND Nachttabelle (HTML und Klartext) genau den
    Register-Standard ``_REGISTER_STANDARD_STUNDENSPALTEN`` in Register-Folge
    -- dieselbe Liste, die der Editor fuer diesen Trip zeigt. Der Rueckfall
    sitzt am Lese-Pfad (``loader._parse_display_config``); ein
    ``metrics: []`` ist ebenfalls Altbestand
    (``test_n1_leere_liste_altbestand_standard``); bewusst leer heisst alle
    Eintraege aus (``test_n1_bewusst_leer_alle_aus``)."""
    data = trip_json(["temperature"])
    del data["display_config"]["metrics"]
    html, text, _ = _senden(monkeypatch, data, fall["format"])
    art = "etappe" if fall["liste"] == "trip_stundentabelle" else "nacht"
    _pruefe_spalten(_stundentabellen(html, text, fall["format"], art),
                    _REGISTER_STANDARD_STUNDENSPALTEN, fall["id"])


#: Eingaben aus ``editor_standard.json`` (dieselbe Datei liest die
#: Frontend-Seite): so sieht der Editor diese Zustaende -- Mail und Editor
#: muessen dieselbe Folge zeigen.
_EDITOR_STANDARD = json.loads((FIXTURES / "editor_standard.json").read_text(encoding="utf-8"))


def _editor_zustand(zustand_id: str) -> dict:
    return next(z for z in _EDITOR_STANDARD["listen"]["trip_tabellen"]["zustaende"]
                if z["id"] == zustand_id)


@pytest.mark.parametrize("fall", _faelle("test_n1_leere_liste_altbestand_standard"))
def test_n1_leere_liste_altbestand_standard(monkeypatch, fall):
    """#3047 H5 (#1394 Fall A): ``metrics: []`` ist Altbestand, KEINE bewusste
    Leerauswahl -- Etappen- und Nachttabelle zeigen wie beim fehlenden
    Schluessel den Register-Standard, denselben, den der Editor fuer ``[]``
    zeigt (``editor_standard.json``, Zustand ``altbestand_leere_liste``)."""
    data = trip_json(["temperature"])
    data["display_config"]["metrics"] = copy.deepcopy(
        _editor_zustand("altbestand_leere_liste")["eingabe"]["display_config"]["metrics"])
    assert data["display_config"]["metrics"] == []
    html, text, _ = _senden(monkeypatch, data, fall["format"])
    art = "etappe" if fall["liste"] == "trip_stundentabelle" else "nacht"
    _pruefe_spalten(_stundentabellen(html, text, fall["format"], art),
                    _REGISTER_STANDARD_STUNDENSPALTEN, fall["id"])


@pytest.mark.parametrize("fall", _faelle("test_n1_bewusst_leer_alle_aus"))
def test_n1_bewusst_leer_alle_aus(monkeypatch, fall):
    """#3047 H5 (#1394 Fall B): bewusst leer heisst alle Eintraege
    ``enabled:false`` (so speichert der Editor eine Leerauswahl) -- Etappen-
    und Nachttabelle entfallen (J3: auch kein Zeit/Risiko-Geruest in HTML
    oder Klartext), kein Standard-Rueckfall; der Editor
    zeigt fuer dieselbe Eingabe nichts aktiv (``editor_standard.json``,
    Zustand ``bewusst_leer_alle_aus``, ``erwartet: []``)."""
    zustand = _editor_zustand("bewusst_leer_alle_aus")
    assert zustand["erwartet"] == [], "Editor-Soll fuer bewusst leer muss leer sein"
    data = trip_json(["temperature"])
    data["display_config"]["metrics"] = copy.deepcopy(
        zustand["eingabe"]["display_config"]["metrics"])
    html, text, _ = _senden(monkeypatch, data, fall["format"])
    art = "etappe" if fall["liste"] == "trip_stundentabelle" else "nacht"
    tabellen = _stundentabellen(html, text, fall["format"], art)
    # #3047 J3: ohne Metrikspalte entfaellt die Tabelle GANZ -- kein Geruest
    # aus Zeit/Risiko, in HTML wie im Klartext (Format-Paritaet).
    assert tabellen == [], (
        f"{fall['id']}: bewusst leer, aber Stundentabelle mit Koepfen "
        f"{[t.labels for t in tabellen]}")
    _pruefe_spalten(tabellen, zustand["erwartet"], fall["id"])


def _bewusst_leer_json(outlook) -> dict:
    """Grundauswahl wie der Editor eine Leerauswahl speichert (alle aus)."""
    zustand = _editor_zustand("bewusst_leer_alle_aus")
    data = trip_json(["temperature"]) if outlook is None else trip_json(
        ["temperature"], outlook_metrics=outlook)
    data["display_config"]["metrics"] = copy.deepcopy(
        zustand["eingabe"]["display_config"]["metrics"])
    return data


#: Variante -> gespeicherte Ausblick-Auswahl (None = nie eingestellt).
_J3_AUSBLICK = {"nie_eingestellt": None, "gespeichert": ["wind", "temperature"]}


@pytest.mark.parametrize("fall", _faelle("test_n1_bewusst_leer_kein_ausblick"))
def test_n1_bewusst_leer_kein_ausblick(monkeypatch, fall):
    """#3047 J3 (AC-4, Konzept §5 Punkt 8): Grundauswahl bewusst leer (alle
    Eintraege ``enabled:false``) -> die Ausblick-Liste nimmt nur aus den
    Metriken oben, ist also leer -> der Ausblick entfaellt in HTML, Klartext
    und Kompakt; kein Rueckfall auf feste Spalten, auch nicht bei einer
    gespeicherten Ausblick-Auswahl."""
    data = _bewusst_leer_json(_J3_AUSBLICK[_variante(fall)])
    assert soll_ausblick(data) is None, "Orakel-Vorbedingung: Ausblick entfaellt"
    html, text, _ = _senden(monkeypatch, data, fall["format"])
    tab = _ausblick(html, text, fall["format"])
    assert tab is None, f"{fall['id']}: Ausblick trotz leerer Grundauswahl: {tab.spalten}"
    for zeile in text.splitlines():
        assert not zeile.startswith(AUSBLICK_TAGE), (
            f"{fall['id']}: Ausblick-Zeile trotz leerer Grundauswahl: {zeile!r}")


def _katalog_kopf(schluessel: str, lang: str) -> str:
    """Fester Teil eines Katalogtexts vor dem ersten Platzhalter (Soll aus den
    Katalogdateien, nicht ueber ``t()``)."""
    return katalogtext(schluessel, lang).split("{")[0].strip()


@pytest.mark.parametrize("fall", _faelle("test_n7_bewusst_leer_ohne_leere_ueberschriften"))
def test_n7_bewusst_leer_ohne_leere_ueberschriften(monkeypatch, fall):
    """#3047 N7 (Konzept §5.8, AC-4/AC-9): Grundauswahl bewusst leer (alle
    Eintraege ``enabled: false``) im Vollformat -- Etappen- und Nachttabelle
    entfallen GANZ, samt Ueberschrift: kein "Segment 1"/"SEG 1" und kein
    "Nacht am Ziel"/"Night at destination" (samt Ankunftszeile) ohne Tabelle
    darunter, in HTML und Klartext, DE und EN."""
    lang = fall.get("sprache", "de")
    data = _bewusst_leer_json(None)
    fmt = fall["format"]
    mitschrift, _trip, _uid = render_trip_mit_ausblick(monkeypatch, data, language=lang)
    html, text = mail_teile(mitschrift)
    gelesen = html_text(html) if fmt == "html" else text
    if fall["liste"] == "trip_nachttabelle":
        verboten = [_katalog_kopf("mail.nacht.am_ziel", lang),
                    _katalog_kopf("mail.nacht.ankunft", lang)]
    else:
        verboten = ["SEG 1" if fmt == "html" else "Segment 1"]
    gefunden = [v for v in verboten if v in gelesen]
    assert not gefunden, f"{fall['id']}: leere Ueberschrift(en) ohne Tabelle: {gefunden}"
    assert STAGE_NAME in gelesen, f"{fall['id']}: Vorbedingung Kopf der Mail fehlt"


def _ueberblick_kopf(gelesen: str, lang: str) -> bool:
    """Steht die Ueberschrift des Metriken-Ueberblicks (Katalogtext, Kompakt
    in ASCII-Umschrift) im gelesenen Mail-Teil?"""
    kopf = katalogtext("mail.pille.ueberschrift", lang)
    ascii_kopf = kopf.replace("Ü", "Ue").replace("ü", "ue")
    return kopf in gelesen or ascii_kopf in gelesen


@pytest.mark.parametrize("fall", _faelle("test_f008b_ueberblick_ohne_inhalt_entfaellt"))
def test_f008b_ueberblick_ohne_inhalt_entfaellt(monkeypatch, fall):
    """#3047 F008b (vierte Pruefung): gewaehlt ist allein eine Groesse ohne
    Ueberblick-Kachel (Nacht-Tiefsttemperatur). Der Metriken-Ueberblick hat
    dann keinen Inhalt -- seine Ueberschrift entfaellt mit, in HTML, Klartext
    und Kompakt, DE und EN. Gegenprobe: mit Temperatur steht sie da."""
    lang = fall.get("sprache", "de")
    fmt = fall["format"]

    def gelesen(folge):
        data = trip_json(folge)
        if fmt == "kompakt":
            data["report_config"]["email_format"] = "compact"
        mitschrift, _trip, _uid = render_trip_mit_ausblick(monkeypatch, data, language=lang)
        html, text = mail_teile(mitschrift)
        return html_text(html) if fmt == "html" else text

    assert _ueberblick_kopf(gelesen(["temperature", "temperature_night"]), lang), (
        f"{fall['id']}: Vorbedingung -- Ueberblick-Ueberschrift mit Temperatur fehlt")
    leer = gelesen(["temperature_night"])
    assert STAGE_NAME in leer, f"{fall['id']}: Vorbedingung Kopf der Mail fehlt"
    assert not _ueberblick_kopf(leer, lang), (
        f"{fall['id']}: Ueberblick-Ueberschrift ohne Inhalt")


#: Register-Standard im 3-Tages-Ausblick (von Hand): die ausblickfaehigen
#: Groessen des Standardsatzes in Register-Folge; Tagestief/-hoch haben keine
#: Ausblick-Spalte (keine Tagesauswertung im Compare-Katalog).
_REGISTER_STANDARD_AUSBLICK = [
    "temperature", "wind", "gust", "precipitation", "thunder", "freezing_level",
    "visibility",
]


@pytest.mark.parametrize("fall", _faelle("test_n1_altbestand_ausblick_standardsatz"))
def test_n1_altbestand_ausblick_standardsatz(monkeypatch, fall):
    """#3047 J2 (AC-19/AC-20, #1394 Fall A): Trip-Altbestand ohne ``metrics``
    bzw. mit ``metrics: []`` und nie eingestelltem Ausblick -- der Ausblick
    zeigt in HTML, Klartext und Kompakt den Register-Standardsatz, soweit
    ausblickfaehig, in Register-Folge (Grundauswahl = Standardsatz), nicht die
    alten sieben festen Spalten."""
    data = trip_json(["temperature"])
    if "leere_liste" in fall["id"]:
        data["display_config"]["metrics"] = []
    else:
        del data["display_config"]["metrics"]
    assert "outlook_metrics" not in data["display_config"], "Vorbedingung: nie eingestellt"
    html, text, _ = _senden(monkeypatch, data, fall["format"])
    tab = _ausblick(html, text, fall["format"])
    assert tab is not None, f"{fall['id']}: Ausblick fehlt"
    assert tab.spalten == _REGISTER_STANDARD_AUSBLICK, (
        f"{fall['id']}: Ausblick {tab.spalten} != Register-Standard {_REGISTER_STANDARD_AUSBLICK}")


def _p7_faelle() -> list:
    """Faelle ``offen_feature`` von Punkt 7 -- belegt rot, bis #3065 Phase 2
    die Abwahl persistiert (dann ``xfail(strict)`` laut)."""
    return [pytest.param(f, id=f["id"], marks=[pytest.mark.xfail(
                strict=True, reason="#3065 Phase 2: Abwahl nicht persistiert")])
            for f in _FALLLISTE["faelle"]
            if f["test"] == "test_p7_global_nachtraeglich_in_gespeicherter_liste"]


@pytest.mark.parametrize("fall", _p7_faelle())
def test_p7_global_nachtraeglich_in_gespeicherter_liste(monkeypatch, fall):
    """Konzept §5 Punkt 6 / Nachpruefung Punkt 7: eine Metrik, die NACH dem
    Speichern einer eigenen Liste global eingeschaltet wird (UV-Index), steht
    in allen Listen -- hier in der gespeicherten E-Mail-Stundentabelle bzw. im
    gespeicherten Ausblick, die sie noch gar nicht kennen (kein Eintrag, keine
    Abwahl)."""
    alt = ["temperature", "wind", "gust"]
    if fall["liste"] == "trip_ausblick":
        data = trip_json(alt + ["uv_index"], outlook_metrics=["wind", "temperature"])
        tab = _ausblick(*_senden(monkeypatch, data, fall["format"])[:2], fall["format"])
        spalten = tab.spalten if tab else []
    else:
        layout = metrik_eintraege(alt, katalog=tuple(alt))
        data = trip_json(alt + ["uv_index"], email_layout=layout)
        html, text, _ = _senden(monkeypatch, data, fall["format"])
        spalten = _stundentabellen(html, text, fall["format"], "etappe")[0].spalten
    assert "uv_index" in spalten, f"{fall['id']}: global nachtraeglich aufgenommen, fehlt in {spalten}"


# ---------------------------------------------------------------------------
# AC-12 -- zwei Nutzer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fall", _faelle("test_ac12_zwei_nutzer_je_eigene_folge"))
def test_ac12_zwei_nutzer_je_eigene_folge(monkeypatch, fall):
    """AC-12: zwei frische Profile, je eigene Folge (Wind, Temperatur bzw.
    Temperatur, Wind) und eigener Empfaenger; EIN Aufzeichner -- jede Mail
    geht an ihren Nutzer und traegt nur dessen Folge."""
    mitschrift = aufzeichner_installieren(monkeypatch)
    folgen = {}
    for folge in (["wind", "temperature"], ["temperature", "wind"]):
        data = trip_json(folge, email_layout=metrik_eintraege(folge), outlook_metrics=folge)
        _m, _trip, uid = render_trip_mit_ausblick(monkeypatch, data, mitschrift=mitschrift)
        assert uid != "default"
        folgen[f"{uid}@example.invalid"] = folge
    sendungen = mitschrift.sendungen("email")
    assert sorted(s["empfaenger"] for s in sendungen) == sorted(folgen), sendungen
    for s in sendungen:
        soll = folgen[s["empfaenger"]]
        html, text = s["body"], s["plain_text_body"]
        if fall["liste"] == "trip_ausblick":
            tab = _ausblick(html, text, fall["format"])
            gelesen = [tab.spalten] if tab else []
        else:
            gelesen = [t.spalten for t in _stundentabellen(html, text, fall["format"], "etappe")]
        assert gelesen and all(sp == soll for sp in gelesen), (
            f"{fall['id']}: Mail an {s['empfaenger']} zeigt {gelesen}, Soll {soll}")


# ---------------------------------------------------------------------------
# AC-17 -- Sprache der Klartext-Festtexte
# ---------------------------------------------------------------------------


def _kopf_und_erste_spalte(text: str) -> tuple[str, str]:
    zeilen = text.splitlines()
    tab = klartext_tabellen(text)["etappe"][0]
    return zeilen[1], tab.labels[0]


@pytest.mark.parametrize("fall", _faelle("test_ac17_klartext_festtexte_in_nutzersprache"))
def test_ac17_klartext_festtexte_in_nutzersprache(monkeypatch, fall):
    """AC-17/T5: deutscher Klartext ohne fest englische Woerter in Kopfzeile
    („… Report") und Zeitspalte („Time"); Deutsch und Englisch unterscheiden
    sich dort; die Spaltenkuerzel (Protokoll-Token) bleiben gleich."""
    data = trip_json(["wind", "temperature"])
    ergebnis = {}
    for sprache in ("de", "en"):
        _html, text, _ = _senden(monkeypatch, data, "klartext", language=sprache)
        ergebnis[sprache] = (_kopf_und_erste_spalte(text), klartext_tabellen(text)["etappe"][0])
    (kopf_de, zeit_de), tab_de = ergebnis["de"]
    (kopf_en, zeit_en), tab_en = ergebnis["en"]
    assert tab_de.spalten == tab_en.spalten == ["wind", "temperature"]
    assert tab_de.labels[1:] == tab_en.labels[1:], "Spaltenkuerzel duerfen nicht uebersetzt werden"
    assert "Report" not in kopf_de, f"deutsche Kopfzeile fest englisch: {kopf_de!r}"
    assert zeit_de != "Time", f"deutsche Zeitspalte fest englisch: {zeit_de!r}"
    assert zeit_de != zeit_en, f"Zeitspalte in DE und EN gleich: {zeit_de!r}"


@pytest.mark.parametrize("fall", _faelle("test_ac17_html_tabellenkopf_in_nutzersprache"))
def test_ac17_html_tabellenkopf_in_nutzersprache(monkeypatch, fall):
    """AC-17/T5 (HTML): die Struktur-Koepfe der Etappentabelle (Zeit vorn,
    Risiko hinten) folgen der Nutzersprache -- Deutsch „Zeit"/„Risiko",
    Englisch „Time"/„Risk"; die Spaltenkuerzel dazwischen bleiben gleich."""
    data = trip_json(["wind", "temperature"])
    koepfe = {}
    for sprache in ("de", "en"):
        html, _text, _ = _senden(monkeypatch, data, "html", language=sprache)
        tab = html_tabellen(html)["etappe"][0]
        assert tab.spalten == ["wind", "temperature"], f"{fall['id']} {sprache}: {tab.spalten}"
        koepfe[sprache] = tab.labels
    de, en = koepfe["de"], koepfe["en"]
    assert (de[0], de[-1]) == ("Zeit", "Risiko"), f"deutscher Tabellenkopf: {de!r}"
    assert (en[0], en[-1]) == ("Time", "Risk"), f"englischer Tabellenkopf: {en!r}"
    assert de[1:-1] == en[1:-1], "Spaltenkuerzel duerfen nicht uebersetzt werden"


# ---------------------------------------------------------------------------
# Angebot fuer Paket C (Validatoren per --eml)
# ---------------------------------------------------------------------------


def test_eml_aus_kette_ist_multipart_mit_beiden_teilen(monkeypatch):
    """``eml_aus_mitschrift`` liefert eine echte MIME-Mail (HTML + Klartext,
    Marker-Header) aus derselben Kette -- Vorbedingung fuer Paket C."""
    import email
    from email import policy

    data = trip_json(["gust", "temperature"], outlook_metrics=["temperature"])
    mitschrift, _trip, uid = render_trip_mit_ausblick(monkeypatch, data)
    msg = email.message_from_bytes(eml_aus_mitschrift(mitschrift), policy=policy.default)
    assert msg["X-GZ-Mail-Type"] == "trip-briefing" and msg["X-GZ-Format"] == "full"
    assert msg["To"] == f"{uid}@example.invalid"
    html = msg.get_body(("html",)).get_content()
    text = msg.get_body(("plain",)).get_content()
    assert html_tabellen(html)["etappe"][0].spalten == ["gust", "temperature"]
    assert klartext_tabellen(text)["etappe"][0].spalten == ["gust", "temperature"]
