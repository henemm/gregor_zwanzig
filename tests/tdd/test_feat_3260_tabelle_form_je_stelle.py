"""#3260 Schritt 1, Scheibe B: Form je Stelle -- jede Zelle der Tabelle "Roh/Einfach".

SPEC: docs/specs/modules/feat_3260_s1b_form_je_stelle.md (AC-1..AC-5),
Tabelle: docs/specs/modules/feat_3122_was_steht_wo.md Teil A Nr. 4, ADR-0127.

Kern-Schicht ueber den ECHTEN Versandweg mit ``display_config.placements``
(Trip: ``NotificationService``, Orte: ``send_one_compare_preset``); einzige
Naehte sind Wetter und Transport (Geruest der #3122-Tests). Kein
``Mock()``/``patch()``.

Die Erwartung (``SOLL``) ist von Hand aus der freigegebenen Tabelle
abgeschrieben und importiert nichts aus Katalog oder Renderer (ADR-0127 Nr. 5):
Wortstufen, Symbole, Himmelsrichtungen und Ampelgrenzen stehen hier als
Literale. Die Parser lesen nur Beschriftungen.

Bekannte Reste ausserhalb des Tests (Spec Nr. 6): Trip-Klartext der Altform
ohne ``placements`` (B6/#3237). Sonnenstunden folgen dem Wert: Stundenwert
(Trip-Stundentabelle, Trip-Telegram) Symbol, Tageswert (Orte-Uebersicht,
Orte-Telegram, Ausblick) Wortstufe (Spec Known Limitations, T7).
"""
from __future__ import annotations

import re
from typing import Optional

import pytest

from tests.helpers.einstellung_gleich_mail_orte import (
    ORTSNAMEN, kennungen, klartext_ausblick as orte_klartext_ausblick,
    klartext_vergleichswerte,
)
from tests.helpers.einstellung_gleich_mail_trip import (
    _html_tabelle, html_ausblick, html_tabellen, klartext_ausblick, klartext_tabellen,
)
from tests.tdd._einstellung_gleich_mail_trip_fixtures import AUSBLICK_TAGE, mail_teile
from tests.tdd.test_3097_stundenverlauf_darstellung import html_stunden, klartext_stunden
from tests.tdd.test_einstellung_gleich_mail_orte_tabelle import (  # noqa: F401  (Fixture)
    AN, mit, preset, senden as orte_senden, tg_ausblick_zellen, tg_bloecke,
)
from tests.tdd.test_einstellung_gleich_mail_trip_tabelle import (
    _tg_kurz, senden as trip_senden, tabelle, telegram_ausblick, trip, zeile,
)

# ---------------------------------------------------------------------------
# Erkennung der Form (von Hand, keine Produktliste)
# ---------------------------------------------------------------------------

#: Wortstufen DE (Klartext) und ihre ASCII-Faltung (Kompakt-Mail).
WORTE = {
    # Wind/Boeen
    "schwach", "mäßig", "maessig", "stark", "sehr stark",
    # Niederschlag (Stunde und Tag)
    "trocken", "leicht",
    # Regenwahrscheinlichkeit
    "unwahrscheinlich", "möglich", "moeglich", "wahrscheinlich", "sehr wahrscheinlich",
    # Sonnenstunden (Tageswert)
    "trübe", "truebe", "wechselhaft", "freundlich", "sonnig",
    # Gewitter
    "kein", "mittel", "hoch",
    # Bewoelkung, ASCII-Wortstufe (neu mit #3260)
    "klar", "heiter", "wolkig", "stark bewölkt", "stark bewoelkt", "bedeckt",
}
#: Symbole: Wolken-Skala und Wetter-Symbol der Stunde.
SYMBOLE = {"☀️", "🌤️", "⛅", "🌥️", "☁️", "🌧️", "🌦️", "⛈️", "🌨️", "🌫️", "🌙", "☀"}
KOMPASS = {"N", "NE", "E", "SE", "S", "SW", "W", "NW", "NO", "O", "SO"}
PLATZHALTER = {"", "-", "–", "·", "?"}
_ZAHL = re.compile(r"^-?\d+(?:[.,]\d+)?(?:/-?\d+(?:[.,]\d+)?)?\s*(?:°C|°|%|km/h|mm|h)?$")
_PUNKT = re.compile(r"border-radius:\s*50%;\s*background:\s*(#[0-9a-fA-F]{6})")
#: Ampel-Fuellfarben (Mail-Palette), von Hand.
FARBE = {"#15803d": "green", "#d69500": "yellow", "#d4530a": "orange", "#a8104a": "red"}
_EMOJI_NAME = re.compile(r":[a-z_]+:")


def _gewitter_kern(text: str) -> str:
    """``⚡mittel@4 · CAPE`` / ``Tmittel@4`` / ``mittel @13 · Hagel: ja`` -> ``mittel``."""
    kern = re.sub(r"\s*@\d+$", "", text.split(" · ")[0].strip())
    for vorsatz in ("⚡", "T"):
        if kern.startswith(vorsatz) and kern[len(vorsatz):] in WORTE | PLATZHALTER:
            kern = kern[len(vorsatz):]
    return kern


def form_von(text: str, fragment: Optional[str] = None) -> Optional[str]:
    """``zahl | wort | symbol | ampelpunkt | kompass`` oder ``None`` (kein Wert)."""
    if fragment and _PUNKT.search(fragment):
        rest = text.strip()
        assert rest in PLATZHALTER or rest in KOMPASS, f"Ampelpunkt mit Text {rest!r}"
        return "ampelpunkt"
    t = re.sub(r"@\d+$", "", text.strip())
    kern = _gewitter_kern(t)
    if t in PLATZHALTER or kern in PLATZHALTER:
        return None
    if kern in WORTE:
        return "wort"
    if t in SYMBOLE:
        return "symbol"
    if t in KOMPASS:
        return "kompass"
    if _ZAHL.match(t):
        return "zahl"
    raise AssertionError(f"unbekannte Zellform: {text!r}")


def _ohne_kompass(text: str) -> tuple[str, Optional[str]]:
    """Wind-Zelle mit verschmolzener Windrichtung (``mäßig S``)."""
    teile = text.rsplit(" ", 1)
    if len(teile) == 2 and teile[1] in KOMPASS and teile[0] not in ("", "sehr"):
        return teile[0], teile[1]
    if text.strip() in KOMPASS:
        return "", text.strip()
    return text, None


# ---------------------------------------------------------------------------
# SOLL: freigegebene Tabelle (feat_3122 Teil A Nr. 4, Spec #3260 S1b Nr. 1)
# ---------------------------------------------------------------------------

GESPERRT = "gesperrt"
OHNE_WERT = "ohne Wert"  # Fixtur liefert an dieser Stelle keinen Wert
A4 = ("zahl", "ampelpunkt")   # Wind/Boeen/Niederschlag/Regen-W., HTML
W4 = ("zahl", "wort")         # dieselben, Text/ASCII/Telegram
WOLKE = ("zahl", "symbol")
RICHTUNG = ("zahl", "kompass")
TEMP = ("zahl", "zahl")
GEW_WORT = ("wort", "wort")


def _zeile(ampel, wolke, sonne, richtung, gewitter) -> dict:
    return {"wind": ampel, "gust": ampel, "precipitation": ampel, "rain_probability": ampel,
            "cloud_total": wolke, "sunshine": sonne, "wind_direction": richtung,
            "thunder": gewitter, "temperature": TEMP}


#: (Flaeche, Stelle, Ausgabe) -> {Metrik: (Form Roh, Form Einfach)}
SOLL: dict[tuple[str, str, str], dict] = {
    ("trip", "email", "html"): _zeile(A4, WOLKE, WOLKE, RICHTUNG, ("wort", "ampelpunkt")),
    ("trip", "email", "text"): _zeile(W4, WOLKE, WOLKE, RICHTUNG, GEW_WORT),
    ("trip", "telegram", "text"): _zeile(W4, WOLKE, WOLKE, RICHTUNG, GEW_WORT),
    ("trip", "outlook", "html"): _zeile(A4, WOLKE, W4, RICHTUNG, GEW_WORT),
    ("trip", "outlook", "text"): _zeile(W4, WOLKE, W4, RICHTUNG, GEW_WORT),
    ("trip", "outlook", "telegram"): _zeile(W4, WOLKE, W4, RICHTUNG, GEW_WORT),
    ("trip", "outlook", "ascii"): _zeile(W4, ("zahl", "wort"), W4, RICHTUNG, GEW_WORT),
    ("orte", "email", "html"): _zeile(A4, WOLKE, W4, OHNE_WERT, ("wort", "ampelpunkt")),
    ("orte", "email", "text"): _zeile(W4, WOLKE, W4, OHNE_WERT, GEW_WORT),
    ("orte", "telegram", "text"): _zeile(W4, WOLKE, W4, OHNE_WERT, GEW_WORT),
    ("orte", "hourly", "html"): _zeile(A4, WOLKE, GESPERRT, ("kompass", "kompass"), GEW_WORT),
    ("orte", "hourly", "text"): _zeile(W4, WOLKE, GESPERRT, ("kompass", "kompass"), GEW_WORT),
    ("orte", "outlook", "html"): _zeile(A4, WOLKE, W4, RICHTUNG, GEW_WORT),
    ("orte", "outlook", "text"): _zeile(W4, WOLKE, W4, RICHTUNG, GEW_WORT),
    ("orte", "outlook", "telegram"): _zeile(W4, WOLKE, W4, RICHTUNG, GEW_WORT),
}

#: Metrikgruppen je Lauf (Telegram-Breite: hoechstens fuenf Groessen je Lauf).
GRUPPEN = (
    ("wind", "gust", "precipitation", "rain_probability", "wind_direction"),
    ("cloud_total", "sunshine", "thunder", "temperature"),
)
#: Orte-Grundauswahl (Auswertung je Metrik), von Hand.
ORTE_AGG = {"temperature": "max", "wind": "max", "gust": "max", "wind_direction": "avg",
            "precipitation": "sum", "rain_probability": "max", "cloud_total": "avg",
            "sunshine": "sum", "thunder": "max"}
FMT = {"roh": "raw", "einfach": "simplified"}

# ---------------------------------------------------------------------------
# Lesen je Stelle: {Metrik: [(Text, rohes Fragment oder None)]}
# ---------------------------------------------------------------------------

#: Telegram-Kurzuebersicht (Trip) und Zellbeschriftung (Orte), von Hand.
TRIP_TG = {"temperature": "T", "wind": "W", "gust": "G", "wind_direction": "WD",
           "precipitation": "R", "rain_probability": "PR", "cloud_total": "CT",
           "sunshine": "SU", "thunder": "TH"}
ORTE_TG = {"temperature": "Temp max", "wind": "Wind", "gust": "Böen",
           "wind_direction": "Windrichtung", "precipitation": "Regen",
           "rain_probability": "Regenwahrscheinlichkeit", "cloud_total": "Wolken",
           "sunshine": "Sonne", "thunder": "Gewitter"}

Zellen = dict[str, list[tuple[str, Optional[str]]]]


def _richtung_abtrennen(zellen: Zellen) -> Zellen:
    """Eine mit der Windrichtung verschmolzene Wind-Zelle (``mäßig S``,
    Ampelpunkt + ``S``) traegt die Windrichtung als eigene Zelle."""
    aus: Zellen = {mid: list(z) for mid, z in zellen.items() if mid != "wind"}
    for text, frag in zellen.get("wind", []):
        rest, richtung = _ohne_kompass(text)
        if richtung:
            aus.setdefault("wind_direction", []).append((richtung, None))
        aus.setdefault("wind", []).append((rest, frag))
    return aus


def _aus_tabelle(tab) -> Zellen:
    return {mid: [(z[j], tab.fragmente[i][j] if tab.fragmente else None)
                  for i, z in enumerate(tab.zellen)]
            for j, mid in enumerate(tab.spalten)}


def _paare(paare) -> Zellen:
    aus: Zellen = {}
    for kopf, wert in paare:
        aus.setdefault(kennungen([kopf])[0], []).append((wert, None))
    return aus


def _tg_ausblick_paare(bubble: str) -> Zellen:
    paare = re.findall(r"(\S+): (.+?)(?=\s{2,}|$)", "\n".join(
        z for z in bubble.splitlines()[1:]), re.M)
    return _paare(paare)


def _trip_lesen(mit_, kompakt: Optional[str]) -> dict[tuple[str, str], Zellen]:
    html, plain = mail_teile(mit_)
    tg = {}
    for mid, kurz in TRIP_TG.items():
        try:
            tg[mid] = [(_tg_kurz(mit_, kurz), None)]
        except AssertionError:
            pass
    aus = {("email", "html"): _aus_tabelle(html_tabellen(html)["etappe"][0]),
           ("email", "text"): _aus_tabelle(klartext_tabellen(plain)["etappe"][0]),
           ("telegram", "text"): tg,
           ("outlook", "html"): _aus_tabelle(html_ausblick(html)),
           ("outlook", "text"): _aus_tabelle(klartext_ausblick(plain, AUSBLICK_TAGE)),
           ("outlook", "telegram"): _tg_ausblick_paare(telegram_ausblick(mit_))}
    if kompakt is not None:
        aus[("outlook", "ascii")] = _aus_tabelle(klartext_ausblick(kompakt, AUSBLICK_TAGE))
    return {k: _richtung_abtrennen(v) for k, v in aus.items()}


def orte_ausblick_html(html: str) -> list:
    """Alle Ausblick-Tabellen (Kopf ``Tag``) mit rohen Fragmenten, je Ort eine."""
    return [_html_tabelle(m.group(0), "ausblick")
            for m in re.finditer(r"<table\b[^>]*>.*?</table>", html, re.DOTALL)
            if "<thead>" in m.group(0) and re.search(r"<th\b[^>]*>\s*Tag\s*</th>", m.group(0))]


def _orte_tg(tg: str) -> Zellen:
    aus: Zellen = {}
    for block in tg_bloecke(tg).values():
        kopf = next((i for i, z in enumerate(block) if z == "3-Tages-Ausblick"), len(block))
        for z in block[:kopf]:
            for c in z.split(" · "):
                treffer = [m for m, n in ORTE_TG.items() if c.startswith(n + " ")]
                if treffer:
                    mid = max(treffer, key=lambda m: len(ORTE_TG[m]))
                    aus.setdefault(mid, []).append((c[len(ORTE_TG[mid]) + 1:], None))
    return aus


def _stunden(tabellen, html: bool) -> Zellen:
    aus: Zellen = {}
    for tab in tabellen:
        for mid, zellen in tab.items():
            aus.setdefault(mid, []).extend(z if html else (z, None) for z in zellen)
    return aus


def _orte_lesen(aus_: dict) -> dict[tuple[str, str], Zellen]:
    html, plain = aus_["html"], aus_["plain"]
    uebersicht: Zellen = {}
    for mid, zellen in _vergleich_html(html).items():
        uebersicht[mid] = zellen
    text: Zellen = {}
    for werte in klartext_vergleichswerte(plain).values():
        for mid, wert in werte.items():
            text.setdefault(mid, []).append((wert, None))
    ausblick_html: Zellen = {}
    for tab in orte_ausblick_html(html):
        for mid, zellen in _aus_tabelle(tab).items():
            ausblick_html.setdefault(mid, []).extend(zellen)
    ausblick_text: Zellen = {}
    for paare in orte_klartext_ausblick(plain).values():
        for mid, zellen in _paare(paare).items():
            ausblick_text.setdefault(mid, []).extend(zellen)
    ausblick_tg: Zellen = {}
    for block in tg_bloecke(aus_["telegram"]).values():
        for mid, zellen in _paare((tg_ausblick_zellen(block) or {}).items()).items():
            ausblick_tg.setdefault(mid, []).extend(zellen)
    gelesen = {("email", "html"): uebersicht, ("email", "text"): text,
               ("telegram", "text"): _orte_tg(aus_["telegram"]),
               ("hourly", "html"): _stunden(html_stunden(html), True),
               ("hourly", "text"): _stunden(klartext_stunden(plain), False),
               ("outlook", "html"): ausblick_html, ("outlook", "text"): ausblick_text,
               ("outlook", "telegram"): ausblick_tg}
    return {k: _richtung_abtrennen(v) for k, v in gelesen.items()}


def _vergleich_html(html: str) -> Zellen:
    from tests.helpers.einstellung_gleich_mail_orte import html_vergleichszellen

    return {mid: [(t, f) for t, f in zellen] for mid, zellen in html_vergleichszellen(html).items()}


# ---------------------------------------------------------------------------
# Laeufe (je Flaeche x Gruppe x Roh/Einfach einmal, modulweit zwischengespeichert)
# ---------------------------------------------------------------------------

_CACHE: dict = {}


def _trip_lauf(monkeypatch, gruppe: tuple[str, ...], fmt: str) -> dict:
    schluessel = ("trip", gruppe, fmt)
    if schluessel not in _CACHE:
        zeilen = [zeile(m, email=fmt, telegram=fmt, outlook=fmt) for m in gruppe]
        folge = list(gruppe) if "temperature" in gruppe else ["temperature", *gruppe]
        voll = trip_senden(monkeypatch, trip(tabelle(zeilen, outlook_reports=["evening"]),
                                             folge=folge), "evening")
        kompakt = trip_senden(monkeypatch, trip(tabelle(zeilen, outlook_reports=["evening"]),
                                                folge=folge,
                                                report_config={"email_format": "compact"}),
                              "evening")
        _CACHE[schluessel] = _trip_lesen(voll, mail_teile(kompakt)[1])
    return _CACHE[schluessel]


def _orte_zeilen(gruppe, fmt: str) -> list[dict]:
    return [{"metric_id": m, "places": AN,
             "formats": {"email": fmt, "telegram": fmt, "hourly": fmt, "outlook": fmt}}
            for m in gruppe]


def _orte_lauf(mit_, gruppe: tuple[str, ...], fmt: str) -> dict:
    schluessel = ("orte", gruppe, fmt)
    if schluessel not in _CACHE:
        grund = [(m, ORTE_AGG[m]) for m in gruppe]
        p = preset(_orte_zeilen(gruppe, fmt), grund=grund)
        _CACHE[schluessel] = _orte_lesen(orte_senden(mit_, p, slot="evening"))
    return _CACHE[schluessel]


def _faelle():
    for (flaeche, stelle, ausgabe), zeilen in SOLL.items():
        for modus in ("roh", "einfach"):
            for gruppe in GRUPPEN:
                yield pytest.param(flaeche, stelle, ausgabe, modus, gruppe,
                                   id=f"{flaeche}-{stelle}-{ausgabe}-{modus}-{gruppe[0]}")


def _pruefe(zellen: Zellen, soll: dict, gruppe, modus: str, ort: str) -> list[str]:
    fehler = []
    for mid in gruppe:
        erwartet = soll[mid]
        if erwartet == GESPERRT:
            if mid in zellen:
                fehler.append(f"{ort} {mid}: gesperrt, steht aber da: {zellen[mid][:2]}")
            continue
        if erwartet == OHNE_WERT:
            formen = {form_von(t, f) for t, f in zellen.get(mid, [])}
            if formen - {None}:
                fehler.append(f"{ort} {mid}: Fixtur ohne Wert erwartet, Formen {formen}")
            continue
        soll_form = erwartet[0 if modus == "roh" else 1]
        if mid not in zellen:
            fehler.append(f"{ort} {mid}: fehlt (Soll {soll_form})")
            continue
        formen = {form_von(t, f) for t, f in zellen[mid]} - {None}
        if formen != {soll_form}:
            beispiele = [t if not f else f"{t}<{'PUNKT' if _PUNKT.search(f) else ''}>"
                         for t, f in zellen[mid][:3]]
            fehler.append(f"{ort} {mid}: Soll {soll_form}, Ist {sorted(formen)} {beispiele}")
    return fehler


# ---------------------------------------------------------------------------
# AC-3: jede Zelle der Tabelle
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(("flaeche", "stelle", "ausgabe", "modus", "gruppe"), list(_faelle()))
def test_ac3_jede_zelle_der_tabelle_hat_die_freigegebene_form(
        monkeypatch, mit, flaeche, stelle, ausgabe, modus, gruppe):  # noqa: F811
    """AC-3: Metrikgruppe x Stelle x Roh/Einfach x Ausgabeart x Trip/Orte
    rendert die von Hand hinterlegte Form; gesperrt = Metrik fehlt dort."""
    if flaeche == "trip":
        gelesen = _trip_lauf(monkeypatch, gruppe, FMT[modus])
    else:
        gelesen = _orte_lauf(mit, gruppe, FMT[modus])
    fehler = _pruefe(gelesen[(stelle, ausgabe)], SOLL[(flaeche, stelle, ausgabe)],
                     gruppe, modus, f"{flaeche}/{stelle}/{ausgabe}/{modus}")
    assert not fehler, "\n".join(fehler)


def test_ac3_verfaelschte_form_macht_den_vergleich_rot():
    """AC-3 (Gegenprobe des Vergleichs): eine einzige verfaelschte Zelle an
    beliebiger Stelle wird gemeldet -- der Vergleich prueft wirklich."""
    soll = SOLL[("orte", "outlook", "html")]
    gruppe = ("wind", "cloud_total")
    echt = {"wind": [("", '<span style="border-radius:50%;background:#d69500;"></span>')],
            "cloud_total": [("⛅", None)]}
    assert _pruefe(echt, soll, gruppe, "einfach", "x") == []
    for verfaelscht in ({**echt, "wind": [("stark", None)]},
                        {**echt, "cloud_total": [("wolkig", None)]},
                        {**echt, "cloud_total": [("70 %", None)]}):
        assert _pruefe(verfaelscht, soll, gruppe, "einfach", "x"), verfaelscht


# ---------------------------------------------------------------------------
# AC-1: Orte-Stundenverlauf, Niederschlag und Regen-W. auf Einfach
# ---------------------------------------------------------------------------

#: Ampelgrenzen (gelb, orange, rot) der Vorlagen, von Hand (ampel_templates).
GRENZEN = {
    "allgemein": {"precipitation": (1, 5, 15), "rain_probability": (30, 60, 80)},
    "radtour": {"precipitation": (0.5, 2, 5), "rain_probability": (30, 50, 70)},
}


def _band(wert: float, grenzen: tuple[float, float, float]) -> str:
    gelb, orange, rot = grenzen
    if wert >= rot:
        return "red"
    if wert >= orange:
        return "orange"
    if wert >= gelb:
        return "yellow"
    return "green"


def _zahl(text: str) -> float:
    return 0.0 if text.strip() in ("·", "") else float(re.match(r"-?[\d.]+", text).group(0))


def _stunden_preset(fmt: str, vorlage: str) -> dict:
    grund = [("temperature", "max"), ("precipitation", "sum"), ("rain_probability", "max")]
    zeilen = [{"metric_id": m, "places": AN, "formats": {"email": "raw", "hourly": fmt}}
              for m, _ in grund]
    p = preset(zeilen, grund=grund)
    p["display_config"]["ampel"] = {"template": vorlage}
    return p


@pytest.mark.parametrize("vorlage", ["allgemein", "radtour"])
def test_ac1_orte_stundenverlauf_regen_einfach_ampelpunkt_in_abo_farbe(mit, vorlage):  # noqa: F811
    """AC-1: jede Stundenzelle von Niederschlag und Regenwahrscheinlichkeit
    zeigt im HTML einen Ampelpunkt in der Farbe der Abo-Ampel (Vorlage des
    Abos, Grenzen von Hand) und kein Wort; der Klartext zeigt die Wortstufe."""
    einfach = orte_senden(mit, _stunden_preset("simplified", vorlage), slot="evening")
    roh = orte_senden(mit, _stunden_preset("raw", vorlage), slot="evening")
    farben_gesehen = set()
    for tab_e, tab_r in zip(html_stunden(einfach["html"]), html_stunden(roh["html"])):
        for mid in ("precipitation", "rain_probability"):
            assert tab_e[mid], f"Vorbedingung: Spalte {mid}"
            for (text, frag), (roh_text, _f) in zip(tab_e[mid], tab_r[mid]):
                punkt = _PUNKT.search(frag)
                assert punkt and text.strip() == "", f"{mid}: kein reiner Ampelpunkt: {text!r}"
                soll = _band(_zahl(roh_text), GRENZEN[vorlage][mid])
                assert FARBE[punkt.group(1).lower()] == soll, (
                    f"{vorlage} {mid} {roh_text!r}: Farbe {punkt.group(1)} statt {soll}")
                farben_gesehen.add(soll)
    assert len(farben_gesehen) >= 2, f"Fixtur deckt nur {farben_gesehen} ab"
    for tab in klartext_stunden(einfach["plain"]):
        for mid in ("precipitation", "rain_probability"):
            assert tab[mid] and all(z in WORTE for z in tab[mid]), f"Klartext {mid}: {tab[mid]}"


# ---------------------------------------------------------------------------
# AC-2: Ausblick HTML Ampelpunkt, Text/Kompakt/Telegram Wortstufe
# ---------------------------------------------------------------------------

AMPEL_VIER = ("wind", "gust", "precipitation", "rain_probability")


def test_ac2_trip_ausblick_html_ampelpunkt_sonst_wortstufe(monkeypatch):
    """AC-2 (Trip): Wind, Boeen, Niederschlag, Regen-W. im Ausblick auf
    Einfach -> HTML Ampelpunkt ohne Wort; Nur-Text, Kompakt, Telegram Wort."""
    gelesen = _trip_lauf(monkeypatch, GRUPPEN[0], "simplified")
    for mid in AMPEL_VIER:
        for text, frag in gelesen[("outlook", "html")][mid]:
            assert _PUNKT.search(frag or "") and text.strip() == "", f"HTML {mid}: {text!r}"
        for ausgabe in ("text", "ascii", "telegram"):
            werte = [t for t, _ in gelesen[("outlook", ausgabe)][mid]]
            assert werte and all(w in WORTE for w in werte), f"{ausgabe} {mid}: {werte}"


def test_ac2_orte_ausblick_html_ampelpunkt_sonst_wortstufe(mit):  # noqa: F811
    """AC-2 (Orte): HTML-Ausblick Ampelpunkt, Nur-Text und Telegram Wort."""
    gelesen = _orte_lauf(mit, GRUPPEN[0], "simplified")
    for mid in AMPEL_VIER:
        zellen = gelesen[("outlook", "html")][mid]
        assert len(zellen) >= len(ORTSNAMEN), f"Vorbedingung: {mid} je Ort"
        for text, frag in zellen:
            assert _PUNKT.search(frag or "") and text.strip() == "", f"HTML {mid}: {text!r}"
        for ausgabe in ("text", "telegram"):
            werte = [t for t, _ in gelesen[("outlook", ausgabe)][mid]]
            assert werte and all(w in WORTE for w in werte), f"{ausgabe} {mid}: {werte}"


# ---------------------------------------------------------------------------
# AC-4: Kompakt-Mail ohne Emoji-Kurznamen
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("sprache,wort", [("de", "wolkig"), ("en", "partly cloudy")])
def test_ac4_kompakt_bewoelkung_einfach_ohne_emoji_kurzname(monkeypatch, sprache, wort):
    """AC-4: Kompakt-Mail, Bewoelkung im Ausblick auf Einfach -> keine
    Zeichenfolge ``:name:``; stattdessen die Wortstufe (70 % = wolkig, DE/EN)."""
    zeilen = [zeile("cloud_total", email="simplified", outlook="simplified"),
              zeile("temperature")]
    data = trip(tabelle(zeilen, outlook_reports=["evening"]),
                folge=["temperature", "cloud_total"], report_config={"email_format": "compact"})
    from tests.tdd._einstellung_gleich_mail_trip_fixtures import render_trip_mit_ausblick

    mit_, _t, _u = render_trip_mit_ausblick(monkeypatch, data, report_type="evening",
                                            language=sprache)
    kompakt = mail_teile(mit_)[1]
    assert not _EMOJI_NAME.search(kompakt), _EMOJI_NAME.findall(kompakt)
    tab = klartext_ausblick(kompakt, AUSBLICK_TAGE)
    assert tab is not None, kompakt
    assert set(tab.spalte("cloud_total")) == {wort}, tab.spalte("cloud_total")


# ---------------------------------------------------------------------------
# AC-5: zwei Nutzer, nur A mit Niederschlag auf Einfach
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("reihenfolge", ["a_zuerst", "b_zuerst"])
def test_ac5_zwei_nutzer_nur_a_sieht_den_ampelpunkt(mit, reihenfolge):  # noqa: F811
    """AC-5: zwei Nutzer mit je einem Orte-Abo; nur A stellt Niederschlag im
    Stundenverlauf und Ausblick auf Einfach. Nur A's Mail zeigt den Punkt,
    jede Mail geht an den eigenen Nutzer und traegt keine fremde Kennung."""
    from tests.tdd._compare_kette_fixtures import nutzer_anlegen

    uid_a, uid_b = nutzer_anlegen(), nutzer_anlegen()
    assert uid_a != uid_b and "default" not in (uid_a, uid_b)
    grund = [("temperature", "max"), ("precipitation", "sum")]

    def abo(fmt: str) -> dict:
        zeilen = [{"metric_id": m, "places": AN,
                   "formats": {"email": "raw", "hourly": fmt, "outlook": fmt}} for m, _ in grund]
        return preset(zeilen, grund=grund)

    auftraege = [(uid_a, "simplified"), (uid_b, "raw")]
    if reihenfolge == "b_zuerst":
        auftraege.reverse()
    mails = {uid: orte_senden(mit, abo(fmt), slot="evening", uid=uid) for uid, fmt in auftraege}

    def punkte(html: str) -> int:
        stunden = sum(1 for tab in html_stunden(html) for _t, f in tab["precipitation"]
                      if _PUNKT.search(f))
        ausblick = sum(1 for tab in orte_ausblick_html(html)
                       for _t, f in _aus_tabelle(tab)["precipitation"] if _PUNKT.search(f or ""))
        return stunden + ausblick

    assert punkte(mails[uid_a]["html"]) > 0, "Nutzer A: kein Ampelpunkt"
    assert punkte(mails[uid_b]["html"]) == 0, "Nutzer B sieht A's Einfach-Form"
    assert mails[uid_a]["uid"] == uid_a and mails[uid_b]["uid"] == uid_b
    for eigen, fremd in ((uid_a, uid_b), (uid_b, uid_a)):
        for teil in ("html", "plain", "telegram"):
            assert fremd not in mails[eigen][teil], f"{teil} von {eigen} nennt {fremd}"

