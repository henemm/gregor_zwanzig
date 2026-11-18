"""#3122 B1b-Trip: jede Trip-Ausgabe liest die Tabelle "Was steht wo".

SPEC: docs/specs/modules/feat_3122_was_steht_wo.md (Teil A Nr. 3, 6, 7;
AC-1, AC-2, AC-4, AC-5, AC-8, AC-10, AC-19; ADR-0124 Nr. 11)

Ein Abo mit gespeicherter Tabelle ``display_config.placements`` muss in JEDER
Trip-Ausgabe wirken: HTML-Mail, Nur-Text-Mail, Kompakt-Mail, Telegram, SMS,
Premium-SMS und im 3-Tages-Ausblick dieser Ausgaben; die Alarm-Darstellung
folgt der Stelle E-Mail bzw. Telegram.

Kern-Schicht ueber den ECHTEN Versandweg (``NotificationService``), Einzige
Naht ist der Transport (``tests/helpers/transport_mitschrift.py``). Das Soll
steht von Hand im Test (Tabelle -> erwartete Spalten), nie aus einer
``resolve_*``-Produktfunktion. Kein ``Mock()``/``patch()``. Katalogfaelle:
``tests/fixtures/einstellung_gleich_mail/fallliste_trip.json`` (IDs
``T-3122-B1B-*``).
"""
from __future__ import annotations

import copy
import re
from typing import Optional

import pytest

from app.metric_catalog import get_metric
from tests.helpers.einstellung_gleich_mail_trip import (
    html_ausblick, html_tabellen, klartext_ausblick, klartext_tabellen,
)
from tests.tdd._einstellung_gleich_mail_trip_fixtures import (
    AUSBLICK_TAGE, BASIS_KATALOG, mail_teile, render_trip_mit_ausblick, trip_json,
)

REPORT_TYPES = ("morning", "evening")
_FEHLT = object()

#: Alle vier Kanaele an (das frische Profil hat Mail, Telegram, SMS, Premium-SMS).
ALLE_KANAELE = {"send_email": True, "send_sms": True, "send_telegram": True,
                "send_premium_sms": True}

#: Telegram-Kuerzel (Kopf der Segment-Tabelle) -- von Hand, Register.
TG = {"temperature": "T", "wind": "W", "gust": "G", "wind_direction": "WD",
      "precipitation": "R", "cloud_total": "CT", "uv_index": "UV", "humidity": "HU"}
#: SMS-Kuerzel (Anfang eines Tokens) -- von Hand, ``docs/reference/sms_format.md``.
SMS = {"temperature": ("D", "N"), "wind": ("W",), "gust": ("G",),
       "wind_direction": ("WD",), "precipitation": ("R",), "cloud_total": ("CT",),
       "uv_index": ("UV",), "humidity": ("H", "HU")}


# ---------------------------------------------------------------------------
# Bausteine
# ---------------------------------------------------------------------------

def zeile(mid: str, *, aus: tuple[str, ...] = (), **formate: str) -> dict:
    """Eine gespeicherte Zeile: ``aus`` = bewusst abgewaehlte Stellen,
    ``formate`` = Roh/Einfach je Stelle (``email="simplified"``)."""
    z: dict = {"metric_id": mid}
    if aus:
        z["places"] = {s: False for s in aus}
    if formate:
        z["formats"] = dict(formate)
    return z


def tabelle(zeilen: list[dict], outlook_reports=_FEHLT) -> dict:
    out: dict = {"version": 1, "rows": zeilen}
    if outlook_reports is not _FEHLT:
        out["outlook_reports"] = outlook_reports
    return out


def trip(placements: dict, *, folge: Optional[list[str]] = None,
         report_config: Optional[dict] = None, display: Optional[dict] = None) -> dict:
    """Trip-JSON mit Grundauswahl ``folge`` (Standard: Basis-Satz) und Tabelle."""
    dc = {"placements": copy.deepcopy(placements)}
    dc.update(display or {})
    return trip_json(list(BASIS_KATALOG) if folge is None else folge, display=dc,
                     report_config={**ALLE_KANAELE, **(report_config or {})})


def senden(monkeypatch, data: dict, report_type: str, **kw):
    mit, _trip, _uid = render_trip_mit_ausblick(monkeypatch, data, report_type=report_type, **kw)
    return mit


def etappe_spalten_html(html: str, *, leer_erlaubt: bool = False) -> list[str]:
    """Metrik-Spalten der Etappentabelle; ``leer_erlaubt``: ohne Metrik darf
    die Tabelle ganz fehlen (dann ``[]``)."""
    tabs = html_tabellen(html)["etappe"]
    if not tabs and leer_erlaubt:
        return []
    assert tabs, "Vorbedingung: Etappentabelle im HTML-Teil"
    return tabs[0].spalten


def etappe_spalten_klartext(text: str, *, leer_erlaubt: bool = False) -> list[str]:
    tabs = klartext_tabellen(text)["etappe"]
    if not tabs and leer_erlaubt:
        return []
    assert tabs, "Vorbedingung: Etappentabelle im Klartext"
    return tabs[0].spalten


def ausblick_html(html: str) -> Optional[list[str]]:
    tab = html_ausblick(html)
    return None if tab is None else tab.spalten


def ausblick_text(text: str) -> Optional[list[str]]:
    """Ausblick-Spalten im Klartext/Kompakt; ``None`` = Block fehlt ganz --
    auch die Ueberschrift "Naechste Etappen" (sonst bliebe ein leerer Block
    ohne Spalten unbemerkt)."""
    tab = klartext_ausblick(text, AUSBLICK_TAGE)
    if tab is None:
        assert not re.search(r"N(ä|ae)chste Etappen", text), "Ausblick-Kopf ohne Zeilen"
        return None
    return tab.spalten


def telegram_bubbles(mit) -> list[str]:
    return [s["body"] for s in mit.sendungen("telegram")]


def telegram_tabelle(mit) -> Optional[tuple[list[str], list[list[str]]]]:
    for b in telegram_bubbles(mit):
        if "<pre>" in b:
            zeilen = b.split("<pre>")[1].split("</pre>")[0].strip().splitlines()
            return zeilen[0].split()[1:], [z.split()[1:] for z in zeilen[1:]]
    return None


def telegram_koepfe(mit) -> list[str]:
    tab = telegram_tabelle(mit)
    return [] if tab is None else tab[0]


def telegram_ausblick(mit) -> Optional[str]:
    """Die Ausblick-Bubble (Titel ``Ausblick``) oder None."""
    for b in telegram_bubbles(mit):
        if b.splitlines() and b.splitlines()[0] in ("Ausblick", "Outlook"):
            return b
    return None


def ausblick_label(mid: str) -> str:
    return get_metric(mid).col_label


def sms_text(mit, kanal: str = "sms") -> str:
    sendungen = mit.sendungen(kanal)
    assert len(sendungen) == 1, f"Vorbedingung: genau eine {kanal}: {mit!r}"
    return sendungen[0]["body"]


def sms_kuerzel(text: str) -> list[str]:
    """Kuerzel der Metrik-Tokens in Folge (``E1: D15/15 W- R2.0@4`` -> D, W, R)."""
    rumpf = text.split(":", 1)[1] if ":" in text else text
    out = []
    for token in rumpf.split():
        m = re.match(r"([A-Z]+)", token)
        if m:
            out.append(m.group(1))
    return out


def sms_folge(text: str, mids: list[str]) -> list[str]:
    """Metriken (aus ``mids``), deren Kuerzel in der SMS stehen, in SMS-Folge."""
    kuerzel = sms_kuerzel(text)
    treffer = []
    for k in kuerzel:
        for mid in mids:
            if k in SMS[mid] and mid not in treffer:
                treffer.append(mid)
    return treffer


# ---------------------------------------------------------------------------
# AC-1: je Stelle genau die angehakten Metriken in der einen Reihenfolge
# ---------------------------------------------------------------------------

#: Eine Reihenfolge fuer alle Stellen, je Metrik andere Haken.
AC1_TABELLE = tabelle([
    zeile("gust", email="raw", telegram="raw"),
    zeile("temperature", aus=("sms",)),
    zeile("precipitation", aus=("telegram",), email="raw"),
    zeile("wind", aus=("email",)),
    zeile("cloud_total", email="raw", telegram="raw"),
    zeile("wind_direction", aus=("telegram",), email="raw"),
    zeile("uv_index", aus=("sms",)),
], outlook_reports=["morning", "evening"])

AC1_EMAIL = ["gust", "temperature", "precipitation", "cloud_total", "wind_direction", "uv_index"]
AC1_TELEGRAM = ["gust", "temperature", "wind", "cloud_total", "uv_index"]
AC1_SMS = ["gust", "precipitation", "wind", "cloud_total", "wind_direction"]


@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_ac1_stundentabelle_html_und_klartext_folgen_email_spalte(monkeypatch, report_type):
    """AC-1: HTML- und Nur-Text-Mail zeigen in der Stundentabelle genau die in
    der E-Mail-Spalte angehakten Metriken in der Reihenfolge der Tabelle."""
    html, plain = mail_teile(senden(monkeypatch, trip(AC1_TABELLE), report_type))
    assert etappe_spalten_html(html) == AC1_EMAIL
    assert etappe_spalten_klartext(plain) == AC1_EMAIL


@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_ac1_ausblick_folgt_tabelle_in_allen_mailformen(monkeypatch, report_type):
    """AC-1/AC-4: der Ausblick zeigt die an der Stelle Ausblick angehakten
    Metriken, die auch in der E-Mail stehen (Wind ist aus der E-Mail
    abgewaehlt), in der Reihenfolge der Tabelle -- HTML, Nur-Text, Kompakt."""
    soll = ["gust", "temperature", "precipitation", "cloud_total", "wind_direction", "uv_index"]
    html, plain = mail_teile(senden(monkeypatch, trip(AC1_TABELLE), report_type))
    assert ausblick_html(html) == soll
    assert ausblick_text(plain) == soll
    _, kompakt = mail_teile(senden(monkeypatch, trip(
        AC1_TABELLE, report_config={"email_format": "compact"}), report_type))
    assert ausblick_text(kompakt) == soll


@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_ac1_kompakt_metriken_ueberblick_ohne_abgewaehlte_email_metrik(monkeypatch, report_type):
    """AC-1 (Kompakt, soweit sie Metriken zeigt): der Metriken-Ueberblick der
    Kompakt-Mail folgt der E-Mail-Spalte -- Wind (abgewaehlt) fehlt, Boeen
    (angehakt) stehen da."""
    _, kompakt = mail_teile(senden(monkeypatch, trip(
        AC1_TABELLE, report_config={"email_format": "compact"}), report_type))
    assert "Boeen" in kompakt or "Böen" in kompakt, kompakt[:900]
    assert not re.search(r"^\s*!*\s*Wind max", kompakt, re.MULTILINE), kompakt[:900]


@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_ac1_telegram_und_sms_folgen_ihrer_spalte(monkeypatch, report_type):
    """AC-1: Telegram-Tabelle und SMS je mit ihrer Spalte, dieselbe Reihenfolge;
    die Premium-SMS hat denselben Text wie die SMS."""
    mit = senden(monkeypatch, trip(AC1_TABELLE), report_type)
    assert telegram_koepfe(mit) == [TG[m] for m in AC1_TELEGRAM]
    sms = sms_text(mit)
    assert sms_folge(sms, list(BASIS_KATALOG)) == AC1_SMS, sms
    assert sms_text(mit, "premium_sms") == sms


# ---------------------------------------------------------------------------
# AC-2: Zeile ausserhalb der Grundauswahl wirkt nirgends
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_ac2_zeile_ausserhalb_grundauswahl_erscheint_nirgends(monkeypatch, report_type):
    """AC-2: eine Zeile fuer Luftfeuchte (nicht in der Grundauswahl), ueberall
    angehakt und vorn, erscheint in keiner Ausgabe -- auch nicht im Ausblick."""
    data = trip(tabelle([zeile("humidity"), zeile("gust"), zeile("temperature")],
                        outlook_reports=["morning", "evening"]))
    mit = senden(monkeypatch, data, report_type)
    html, plain = mail_teile(mit)
    assert etappe_spalten_html(html)[:2] == ["gust", "temperature"], "Vorbedingung"
    for spalten in (etappe_spalten_html(html), etappe_spalten_klartext(plain),
                    ausblick_html(html), ausblick_text(plain)):
        assert spalten is not None and "humidity" not in spalten, spalten
    assert TG["humidity"] not in telegram_koepfe(mit)
    assert "Humidity" not in (telegram_ausblick(mit) or "")
    assert not {"H", "HU"} & set(sms_kuerzel(sms_text(mit))), sms_text(mit)


# ---------------------------------------------------------------------------
# AC-4: ohne E-Mail-Haken fehlt die Metrik in Tabelle und Ausblick
# ---------------------------------------------------------------------------

def _ac4_trip(email_an: bool) -> dict:
    return trip(tabelle([
        zeile("gust", aus=() if email_an else ("email",)),
        zeile("temperature"), zeile("wind"),
    ], outlook_reports=["evening"]))


def test_ac4_ohne_email_haken_fehlt_metrik_in_tabelle_und_ausblick_mail_und_telegram(monkeypatch):
    """AC-4: Boeen ohne E-Mail-Haken (Ausblick-Haken gespeichert) fehlen in
    der Stundentabelle UND im Ausblick der HTML-, Nur-Text-Mail und von
    Telegram; nach Wiederanhaken stehen sie wieder da wie zuvor."""
    mit = senden(monkeypatch, _ac4_trip(True), "evening")
    html_an, plain_an = mail_teile(mit)
    assert "gust" in etappe_spalten_html(html_an), "Vorbedingung: angehakt sichtbar"
    assert "gust" in ausblick_html(html_an) and "gust" in ausblick_text(plain_an)
    assert ausblick_label("gust") + ":" in telegram_ausblick(mit)

    mit = senden(monkeypatch, _ac4_trip(False), "evening")
    html, plain = mail_teile(mit)
    assert "gust" not in etappe_spalten_html(html)
    assert "gust" not in etappe_spalten_klartext(plain)
    assert ausblick_html(html) is not None and "gust" not in ausblick_html(html)
    assert "gust" not in ausblick_text(plain)
    tg = telegram_ausblick(mit)
    assert tg is not None and ausblick_label("gust") + ":" not in tg, tg
    assert TG["gust"] in telegram_koepfe(mit), "Telegram-Haken bleibt unberuehrt"

    mit = senden(monkeypatch, _ac4_trip(True), "evening")
    html_wieder, plain_wieder = mail_teile(mit)
    assert ausblick_html(html_wieder) == ausblick_html(html_an)
    assert etappe_spalten_html(html_wieder) == etappe_spalten_html(html_an)


# ---------------------------------------------------------------------------
# AC-5: Roh/Einfach je Stelle, Umschalten an einer Stelle aendert keine andere
# ---------------------------------------------------------------------------

def _gust_zellen_html(html: str) -> list[str]:
    tab = html_tabellen(html)["etappe"][0]
    j = tab.spalten.index("gust")
    return [f[j] for f in tab.fragmente]


def _gust_zellen_text(plain: str) -> list[str]:
    return klartext_tabellen(plain)["etappe"][0].spalte("gust")


def _tg_spalte(mit, kuerzel: str) -> list[str]:
    koepfe, zeilen = telegram_tabelle(mit)
    i = koepfe.index(kuerzel)
    return [z[i] for z in zeilen]


def _ac5(monkeypatch, email: str, telegram: str):
    data = trip(tabelle([zeile("gust", email=email, telegram=telegram),
                         zeile("temperature")], outlook_reports=[]))
    mit = senden(monkeypatch, data, "evening", mit_ausblick=False)
    html, plain = mail_teile(mit)
    return mit, html, plain


def test_ac5_boeen_telegram_roh_email_einfach(monkeypatch):
    """AC-5: Boeen Telegram Roh, E-Mail Einfach -> Telegram die Zahl, HTML-Mail
    der Ampelpunkt; Umschalten der E-Mail aendert Telegram nicht, Umschalten
    von Telegram aendert die HTML-Mail nicht."""
    mit, html, _plain = _ac5(monkeypatch, "simplified", "raw")
    assert all(re.fullmatch(r"\d+", z) for z in _tg_spalte(mit, "G")), _tg_spalte(mit, "G")
    assert all("border-radius:50%" in z.replace(" ", "") for z in _gust_zellen_html(html))

    mit_roh, html_roh, _ = _ac5(monkeypatch, "raw", "raw")
    assert not any("border-radius:50%" in z.replace(" ", "") for z in _gust_zellen_html(html_roh))
    assert _tg_spalte(mit_roh, "G") == _tg_spalte(mit, "G"), "E-Mail-Umschalten aendert Telegram"

    _mit_tg, html_tg, _ = _ac5(monkeypatch, "simplified", "simplified")
    assert _gust_zellen_html(html_tg) == _gust_zellen_html(html), "Telegram-Umschalten aendert Mail"


def test_ac5_boeen_nur_text_mail_einfach_ist_wortstufe(monkeypatch):
    """AC-5 (Nur-Text): Boeen E-Mail Einfach -> Wortstufe statt Zahl; Roh -> Zahl."""
    _mit, _html, plain = _ac5(monkeypatch, "simplified", "raw")
    assert not any(re.fullmatch(r"\d+", z) for z in _gust_zellen_text(plain)), _gust_zellen_text(plain)
    _mit, _html, plain_roh = _ac5(monkeypatch, "raw", "raw")
    assert all(re.fullmatch(r"\d+", z) for z in _gust_zellen_text(plain_roh)), plain_roh[:400]


def _tg_kurz(mit, kuerzel: str) -> str:
    """Wert der Zeile ``kuerzel`` in der Telegram-Kurzuebersicht."""
    for b in telegram_bubbles(mit):
        zeilen = b.splitlines()
        if zeilen and zeilen[0] in ("Kurzübersicht", "Summary"):
            for z in zeilen[1:]:
                if z.startswith(kuerzel + " "):
                    return z[len(kuerzel) + 1:]
    raise AssertionError(f"keine Zeile {kuerzel!r}: {telegram_bubbles(mit)}")


def test_ac5_boeen_telegram_einfach_ist_wortstufe(monkeypatch):
    """AC-5: Boeen Telegram Einfach -> Wortstufe statt Zahl (Kurzuebersicht),
    Telegram Roh -> Zahl; die E-Mail (Roh) bleibt dabei gleich."""
    mit, html, _plain = _ac5(monkeypatch, "raw", "simplified")
    assert re.fullmatch(r"[^\d@]+@\d\d", _tg_kurz(mit, "G")), _tg_kurz(mit, "G")
    mit_roh, html_roh, _ = _ac5(monkeypatch, "raw", "raw")
    assert re.fullmatch(r"\d+@\d\d", _tg_kurz(mit_roh, "G")), _tg_kurz(mit_roh, "G")
    assert _gust_zellen_html(html) == _gust_zellen_html(html_roh)


def test_ac5_tabellen_format_schlaegt_altschreibweise_der_grundauswahl(monkeypatch):
    """AC-5: mit Tabelle gilt allein deren Format. Steht im Grundauswahl-
    Eintrag der Boeen noch die Alt-Schreibweise ``format_mode: raw`` mit
    ``use_friendly_format: true`` (dort: Ampelpunkt), zeigt die HTML-Mail bei
    E-Mail Roh in der Tabelle keinen Ampelpunkt."""
    from tests.tdd._einstellung_gleich_mail_trip_fixtures import metrik_eintraege

    eintraege = metrik_eintraege(list(BASIS_KATALOG))
    for e in eintraege:
        if e["metric_id"] == "gust":
            e.update(format_mode="raw", use_friendly_format=True)
    data = trip(tabelle([zeile("gust", email="raw"), zeile("temperature")], outlook_reports=[]),
                display={"metrics": eintraege})
    html, _plain = mail_teile(senden(monkeypatch, data, "evening", mit_ausblick=False))
    zellen = _gust_zellen_html(html)
    assert zellen and not any("border-radius:50%" in z.replace(" ", "") for z in zellen), zellen[:1]


def _regenwahrscheinlichkeit(monkeypatch, email: str) -> tuple[str, str]:
    folge = list(BASIS_KATALOG) + ["rain_probability"]
    data = trip(tabelle([zeile("rain_probability", email=email), zeile("temperature")],
                        outlook_reports=[]), folge=folge)
    return mail_teile(senden(monkeypatch, data, "evening", mit_ausblick=False))


def test_ac5_regenwahrscheinlichkeit_html_einfach_ampelpunkt(monkeypatch):
    """AC-5 (HTML): Regenwahrscheinlichkeit E-Mail Einfach -> Ampelpunkt, Roh -> ohne."""
    html, _ = _regenwahrscheinlichkeit(monkeypatch, "simplified")
    tab = html_tabellen(html)["etappe"][0]
    j = tab.spalten.index("rain_probability")
    assert all("border-radius:50%" in f[j].replace(" ", "") for f in tab.fragmente)
    html_roh, _ = _regenwahrscheinlichkeit(monkeypatch, "raw")
    tab = html_tabellen(html_roh)["etappe"][0]
    assert not any("border-radius:50%" in f[j].replace(" ", "") for f in tab.fragmente)


@pytest.mark.xfail(strict=True, reason="#3122: Nur-Text-Mail kennt fuer die Regenwahrscheinlichkeit keine Wortstufe (Renderer-Nachzug, eigene Scheibe)")
def test_ac5_regenwahrscheinlichkeit_nur_text_einfach_ist_wortstufe(monkeypatch):
    """AC-5 (offen_feature): Regenwahrscheinlichkeit Einfach -> Wortstufe im Klartext."""
    _html, plain = _regenwahrscheinlichkeit(monkeypatch, "simplified")
    zellen = klartext_tabellen(plain)["etappe"][0].spalte("rain_probability")
    assert not any(re.match(r"\d", z) for z in zellen), zellen


def test_ac5_ausblick_format_folgt_stelle_ausblick(monkeypatch):
    """AC-5 (Ausblick): Boeen im Ausblick Einfach -> Wortstufe im Ausblick der
    Nur-Text-Mail, Roh -> Zahl; die E-Mail-Stundentabelle bleibt gleich."""
    def lauf(fmt):
        data = trip(tabelle([zeile("gust", email="raw", outlook=fmt), zeile("temperature")],
                            outlook_reports=["evening"]))
        _html, plain = mail_teile(senden(monkeypatch, data, "evening"))
        return klartext_ausblick(plain, AUSBLICK_TAGE).spalte("gust"), _gust_zellen_text(plain)

    einfach, stunden_e = lauf("simplified")
    roh, stunden_r = lauf("raw")
    assert all(re.match(r"\d", z) for z in roh), roh
    assert not any(re.match(r"\d", z) for z in einfach), einfach
    assert stunden_e == stunden_r


# ---------------------------------------------------------------------------
# AC-8 (neuer Eingang): outlook_reports steuert den Ausblick in allen Ausgaben
# ---------------------------------------------------------------------------

def _ausblick_ueberall(monkeypatch, data_voll: dict, data_kompakt: dict, rt: str) -> dict:
    mit = senden(monkeypatch, data_voll, rt)
    html, plain = mail_teile(mit)
    _, kompakt = mail_teile(senden(monkeypatch, data_kompakt, rt))
    return {"html": ausblick_html(html), "klartext": ausblick_text(plain),
            "kompakt": ausblick_text(kompakt), "telegram": telegram_ausblick(mit)}


def _ausblick_trip(reports, report_config: Optional[dict] = None) -> tuple[dict, dict]:
    t = tabelle([zeile("gust"), zeile("temperature"), zeile("wind")], outlook_reports=reports)
    rc = report_config or {}
    return trip(t, report_config=rc), trip(t, report_config={**rc, "email_format": "compact"})


def test_ac8_ausblick_nur_abends(monkeypatch):
    """AC-8: ``outlook_reports: ["evening"]`` -> abends in HTML, Nur-Text,
    Kompakt und Telegram vorhanden, morgens in keiner dieser Ausgaben (auch
    wenn Ausblick-Zeilen vorliegen)."""
    voll, kompakt = _ausblick_trip(["evening"])
    abends = _ausblick_ueberall(monkeypatch, voll, kompakt, "evening")
    assert all(v is not None for v in abends.values()), abends
    morgens = _ausblick_ueberall(monkeypatch, voll, kompakt, "morning")
    assert all(v is None for v in morgens.values()), morgens


@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_ac8_ausblick_leer_nirgends(monkeypatch, report_type):
    """AC-8: ``outlook_reports: []`` -> in keiner Ausgabe, morgens wie abends."""
    voll, kompakt = _ausblick_trip([])
    werte = _ausblick_ueberall(monkeypatch, voll, kompakt, report_type)
    assert all(v is None for v in werte.values()), werte


def test_ac8_tabelle_ersetzt_alte_ausblick_schalter(monkeypatch):
    """Spec Nr. 6: mit Tabelle steuert allein ``outlook_reports`` -- die
    Altschalter ``show_outlook: false`` und ``multi_day_trend_reports``
    wirken nicht mehr; der Ausblick steht morgens (laut Tabelle)."""
    voll, kompakt = _ausblick_trip(["morning"], report_config={
        "show_outlook": False, "multi_day_trend_reports": ["evening"]})
    morgens = _ausblick_ueberall(monkeypatch, voll, kompakt, "morning")
    assert all(v is not None for v in morgens.values()), morgens


def test_ac8_zeitplaner_baut_ausblick_nach_tabelle():
    """Der Zeitplaner entscheidet ueber ``resolve_report_render_options``, ob er
    die Ausblick-Daten baut: mit Tabelle nach ``outlook_reports`` (nicht nach
    ``multi_day_trend_reports``), ``show_outlook`` wirkt nicht."""
    from app.loader import load_trip
    from services.report_config_resolver import resolve_report_render_options
    from tests.tdd._einstellung_gleich_mail_trip_fixtures import frisches_profil

    voll, _ = _ausblick_trip(["morning"], report_config={
        "show_outlook": False, "multi_day_trend_reports": ["evening"]})
    t = load_trip(copy.deepcopy(voll), user_id=frisches_profil())
    morgens = resolve_report_render_options(t.report_config, t.display_config, "morning")
    abends = resolve_report_render_options(t.report_config, t.display_config, "evening")
    assert morgens.show_multi_day_trend is True and abends.show_multi_day_trend is False
    assert morgens.show_outlook is True


def test_ac9_vorbelegung_nur_morgen_briefing_eingeschaltet(monkeypatch):
    """Spec Nr. 6 (Vorbelegung): ohne ``outlook_reports`` und nur mit dem
    Morgen-Briefing eingeschaltet steht der Ausblick morgens -- die
    eingeschalteten Briefings des Abos erreichen den Resolver."""
    t = tabelle([zeile("gust"), zeile("temperature")])
    mit = senden(monkeypatch, trip(t, report_config={"evening_enabled": False}), "morning")
    html, _plain = mail_teile(mit)
    assert ausblick_html(html) is not None
    assert telegram_ausblick(mit) is not None


# ---------------------------------------------------------------------------
# AC-10: Spalte leer / Grundauswahl leer -- kein Rueckfall
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_ac10_email_spalte_leer_keine_metrik_kein_ausblick(monkeypatch, report_type):
    """AC-10: alle E-Mail-Haken entfernt -> keine Metrik in der Stundentabelle
    von HTML- und Nur-Text-Mail, der Ausblick entfaellt als Block (auch in
    Telegram, er haengt an der E-Mail); Telegram und SMS fallen nicht zurueck,
    sie zeigen ihre eigene Spalte."""
    t = tabelle([zeile(m, aus=("email",)) for m in BASIS_KATALOG],
                outlook_reports=["morning", "evening"])
    mit = senden(monkeypatch, trip(t), report_type)
    html, plain = mail_teile(mit)
    assert etappe_spalten_html(html, leer_erlaubt=True) == []
    assert etappe_spalten_klartext(plain, leer_erlaubt=True) == []
    assert ausblick_html(html) is None and ausblick_text(plain) is None
    assert telegram_ausblick(mit) is None
    assert telegram_koepfe(mit), "Telegram behaelt seine eigene Spalte"


@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_ac10_grundauswahl_bewusst_leer_keine_metrik_nirgends(monkeypatch, report_type):
    """AC-10: Grundauswahl bewusst leer (alle Eintraege aus) mit Tabelle ->
    nirgends eine Metrik, kein Ausblick, kein Rueckfall auf einen Standardsatz."""
    t = tabelle([zeile("gust"), zeile("temperature")], outlook_reports=["morning", "evening"])
    mit = senden(monkeypatch, trip(t, folge=[]), report_type)
    html, plain = mail_teile(mit)
    assert etappe_spalten_html(html, leer_erlaubt=True) == []
    assert etappe_spalten_klartext(plain, leer_erlaubt=True) == []
    assert ausblick_html(html) is None and ausblick_text(plain) is None
    assert telegram_koepfe(mit) == [] and telegram_ausblick(mit) is None
    assert not set(sms_kuerzel(sms_text(mit))) & {k for ks in SMS.values() for k in ks}, sms_text(mit)


# ---------------------------------------------------------------------------
# AC-19 (Trip-Teil): Alarm haengt nicht an der Tabelle, Darstellung folgt der Stelle
# ---------------------------------------------------------------------------

def _alarm_trip(uid: str, gust_email: dict, gust_telegram: Optional[str] = None):
    """Trip mit Boeen in der Grundauswahl und gespeicherter Tabelle, in der die
    Boeen in der E-Mail-Spalte abgewaehlt sind."""
    import uuid
    from datetime import datetime

    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    from app.trip import Stage, Trip, Waypoint

    tid = f"trip-3122-{uuid.uuid4().hex[:6]}"
    formate = dict(gust_email)
    if gust_telegram:
        formate["telegram"] = gust_telegram
    stage = Stage(id="T1", name="Tag 1", date=datetime(2026, 5, 1).date(),
                  waypoints=[Waypoint(id="G1", name="Start", lat=47.0, lon=11.0,
                                      elevation_m=1000.0)])
    return Trip(
        id=tid, name="Alarm-Trip", stages=[stage], official_warnings=None, corridors=[],
        display_config=UnifiedWeatherDisplayConfig(
            trip_id=tid, metrics=[MetricConfig(metric_id="gust", enabled=True),
                                  MetricConfig(metric_id="temperature", enabled=True)],
            placements=tabelle([{"metric_id": "gust", "places": {"email": False},
                                 "formats": formate}, zeile("temperature")]),
        ),
    )


def _alarm_senden(monkeypatch, gust_email: dict, gust_telegram: Optional[str] = None):
    from services.notification_service import NotificationService
    from tests.helpers.sms_empfaenger import mit_profil_kanaele
    from tests.helpers.transport_mitschrift import aufzeichner_installieren
    from tests.tdd.test_alert_hour_rows import _load, _segment_data, _settings, _user, _wc

    fx = _load("boeen_neun_stunden.json")
    mit = aufzeichner_installieren(monkeypatch)
    settings = _settings()
    uid = mit_profil_kanaele(_user("3122"), settings)
    NotificationService(settings, uid).send_deviation_alert(
        trip=_alarm_trip(uid, gust_email, gust_telegram),
        weather=[_segment_data(fx, fx["fresh"])], changes=[_wc(fx["change"])],
        effective_channels={"email", "telegram"},
        anchor_weather=[_segment_data(fx, fx["anchor"])],
    )
    return mit


def _alarm_zeilen_html(html: str) -> list[str]:
    return [z for z in re.findall(r"<tr\b.*?</tr>", html, re.DOTALL)
            if re.search(r">\s*\d{2}:\d{2}\s*<", z)]


def test_ac19_alarm_nennt_boeen_trotz_abwahl_in_email_spalte(monkeypatch):
    """AC-19: Boeen in der E-Mail-Spalte abgewaehlt, Boeen-Alarm loest aus ->
    die Alarm-Mail nennt die Boeen (die Tabelle steuert keine Alarme)."""
    from services.trip_alert import TripAlertService
    from tests.helpers.alert_log_fixtures import gust_alert_trip, settings_email_only, weather
    import dataclasses
    import uuid

    t = gust_alert_trip(f"t3122-{uuid.uuid4().hex[:6]}")
    t = dataclasses.replace(t, display_config=dataclasses.replace(
        t.display_config,
        placements=tabelle([{"metric_id": "gust", "places": {"email": False}}])))
    mails: list = []
    svc = TripAlertService(settings=settings_email_only(),
                           user_id=f"alarm-3122-{uuid.uuid4().hex[:6]}",
                           mail_sink=lambda subject, body: mails.append((subject, body)))
    assert svc.check_and_send_alerts(t, [weather(1, gust_max_kmh=10.0)],
                                     fresh_weather=[weather(1, gust_max_kmh=90.0)])
    assert len(mails) == 1 and re.search(r"Böen|Boeen", mails[0][1]), mails


@pytest.mark.parametrize("fmt,punkt", [("simplified", True), ("raw", False)])
def test_ac19_alarm_mail_darstellung_folgt_stelle_email_auch_abgewaehlt(monkeypatch, fmt, punkt):
    """AC-19 / ADR-0124 Nr. 11: Roh/Einfach der Alarm-Mail folgt der Stelle
    E-Mail aus der Tabelle -- auch fuer die dort abgewaehlten Boeen (ihr
    gespeichertes Format der Stelle). Einfach = Ampelpunkt, Roh = Zahl."""
    mit = _alarm_senden(monkeypatch, {"email": fmt}, "raw")
    mails = mit.sendungen("email")
    assert len(mails) == 1, mit
    zeilen = _alarm_zeilen_html(mails[0]["body"])
    assert zeilen, "Vorbedingung: Stundenzeilen in der Alarm-Mail"
    hat_punkt = ["border-radius:50%" in z.replace(" ", "") for z in zeilen]
    assert all(hat_punkt) if punkt else not any(hat_punkt), zeilen[:2]


@pytest.mark.parametrize("email,telegram", [("simplified", "raw"), ("raw", "simplified")])
def test_ac19_alarm_telegram_darstellung_folgt_stelle_telegram(monkeypatch, email, telegram):
    """ADR-0124 Nr. 11: das Alarm-Telegram folgt dem Format der Stelle
    Telegram (Roh = Zahl, Einfach = Wortstufe), unabhaengig vom Format der
    E-Mail."""
    from tests.tdd.test_alert_hour_rows import _rows

    mit = _alarm_senden(monkeypatch, {"email": email}, telegram)
    tg = mit.sendungen("telegram")
    assert len(tg) == 1, mit
    zeilen = _rows(tg[0]["body"])
    assert zeilen, tg[0]["body"]
    zahlen = [bool(re.fullmatch(r"\d+ → \d+", rest)) for _t, rest in zeilen]
    assert all(zahlen) if telegram == "raw" else not any(zahlen), zeilen


# ---------------------------------------------------------------------------
# Nacht-/Tagesgroessen: gesperrte E-Mail-Stelle ("keine eigene Spalte") heisst
# nicht "fehlt in der Mail" (Entscheidung Fix-Loop B1b-Trip)
# ---------------------------------------------------------------------------

#: Nachttief am Ziel 4 Grad (Nacht 20-06 Uhr), tagsueber 15 Grad -- Nachttief
#: und Gehzeit-Minimum unterscheiden sich (die Basis-Fixtur ist konstant 15).
NACHT_TIEF = 4.0


def _nennt_nachttief(zeile: str) -> bool:
    """``E1: 4–15°C, ...`` bzw. ``E1: 4°C, ...`` (nicht ``ab 4:00``)."""
    return bool(re.search(rf"(?<![\d.]){int(NACHT_TIEF)}(?:–-?\d+)?°C", zeile))


def _kalte_nacht():
    import dataclasses

    from tests.tdd._einstellung_gleich_mail_trip_fixtures import night_weather

    nw = night_weather()
    kalt = [dataclasses.replace(dp, t2m_c=NACHT_TIEF)
            if dp.ts.astimezone(_tz()).hour >= 20 or dp.ts.astimezone(_tz()).hour <= 6 else dp
            for dp in nw.data]
    return dataclasses.replace(nw, data=kalt)


def _tz():
    from tests.tdd._einstellung_gleich_mail_trip_fixtures import TZ

    return TZ


def _zusammenfassung(data: dict, report_type: str = "evening") -> str:
    """Kurz-Zusammenfassung der Trip-Mail (Klartext und HTML) ueber den echten
    Formatter, mit kalter Nacht; ``E1: ...``-Zeile des Klartexts."""
    from app.loader import load_trip
    from output.renderers.trip_report import TripReportFormatter
    from tests.tdd._einstellung_gleich_mail_trip_fixtures import (
        STAGE_NAME, frisches_profil, segment,
    )

    t = load_trip(copy.deepcopy(data), user_id=frisches_profil())
    bericht = TripReportFormatter().format_email(
        [segment()], trip_name="Nacht", report_type=report_type,
        display_config=t.display_config, report_config=t.report_config,
        night_weather=_kalte_nacht(), stage_name=STAGE_NAME, tz=_tz(), trip=t,
    )
    zeilen = [z for z in bericht.email_plain.splitlines() if z.startswith(f"{STAGE_NAME}: ")]
    assert zeilen, bericht.email_plain[:800]
    return zeilen[0]


def _mit_tabelle_aus_altbestand(alt: dict) -> dict:
    from app.loader import load_trip
    from services.placements import placements_from_legacy
    from tests.tdd._einstellung_gleich_mail_trip_fixtures import frisches_profil

    t = load_trip(copy.deepcopy(alt), user_id=frisches_profil())
    neu = copy.deepcopy(alt)
    neu["display_config"]["placements"] = placements_from_legacy(
        t.display_config, "trip", report_config=t.report_config).placements
    return neu


@pytest.mark.parametrize("folge", [
    ["temperature", "wind", "gust"],          # Nachttief abgeleitet aus Temperatur
    ["temperature_night", "wind", "gust"],    # nur die Nachtgroesse gewaehlt
], ids=["mit_temperatur", "nur_nachtgroesse"])
def test_nachttief_in_kurzzusammenfassung_wie_ohne_tabelle(folge):
    """Abend-Kurz-Zusammenfassung: das Abo mit (umgerechneter) Tabelle nennt
    das Nachttief wie dasselbe Abo ohne Tabelle -- die Nachtgroesse hat in der
    Stundentabelle keine Spalte, gehoert aber weiter zur Mail."""
    alt = trip_json(folge, report_config=ALLE_KANAELE)
    ohne = _zusammenfassung(alt)
    assert _nennt_nachttief(ohne), f"Vorbedingung: Nachttief im Bestand: {ohne}"
    assert _zusammenfassung(_mit_tabelle_aus_altbestand(alt)) == ohne


def test_nachttief_bleibt_auch_bei_abgewaehlter_tabellenzeile():
    """Die Nachtgroesse ist an der Stelle E-Mail nicht abwaehlbar: auch eine
    gespeicherte Abwahl in der E-Mail-Spalte entfernt sie nicht aus der Mail."""
    data = trip(tabelle([zeile("temperature_night", aus=("email",)), zeile("wind")]),
                folge=["temperature_night", "wind", "gust"])
    satz = _zusammenfassung(data)
    assert _nennt_nachttief(satz), satz


#: Kanal-Eintrag mit eigenen Horizonten und einer Format-Schreibweise, die die
#: View-Model-Zeile nicht unterscheidet (``format_mode: raw`` bei
#: ``use_friendly_format: true`` -- HTML-Ampelpunkt an, Wert roh).
_EIGENE_HORIZONTE = {
    "metrics": [{"metric_id": m, "enabled": True, "bucket": "primary", "order": i}
                for i, m in enumerate(["temperature", "wind", "gust", "precipitation"])],
    "channel_layouts": {"email": [
        {"metric_id": "gust", "bucket": "primary", "order": 0, "format_mode": "raw",
         "use_friendly_format": True, "horizons": {"today": True, "tomorrow": False}},
        {"metric_id": "temperature", "bucket": "primary", "order": 1,
         "horizons": {"today": False, "tomorrow": True}},
    ]},
}


def test_bestand_ohne_tabelle_mail_eintraege_gleich_bisheriger_kaskade():
    """Unveraendertheit (Abos ohne ``placements``): fuer jede Kombination aus
    Kanal-Ebenen, Briefing-Typ und Grundauswahl liefert der Mail-Adapter aus
    den E-Mail-Zeilen des View-Models dieselben Eintraege (samt ``horizons``,
    ``use_friendly_format``) wie die bisherige Kaskade -- Orakel ist die
    wortgleiche Kopie ``alt_trip_metrics_for_channel`` (Stand vor #3057)."""
    import dataclasses

    from app.loader import _parse_display_config
    from output.renderers.email.helpers import channel_metric_configs
    from services.channel_list_resolver import resolve_channel_lists
    from tests.helpers.kanal_liste_orakel import alt_trip_metrics_for_channel
    from tests.tdd.test_3057_channel_list_resolver import _trip_kombinationen

    faelle = list(_trip_kombinationen()) + [("eigene_horizonte", _EIGENE_HORIZONTE)]
    fehler = []
    for name, roh in faelle:
        dc = _parse_display_config(copy.deepcopy(roh))
        for rt in REPORT_TYPES:
            vm = resolve_channel_lists(dc, "trip", rt)
            neu = channel_metric_configs(vm.email, dc, "email", rt)
            alt = [dataclasses.replace(mc, enabled=True)
                   for mc in alt_trip_metrics_for_channel(dc, "email", rt)]
            if neu != alt:
                fehler.append(f"{name}/{rt}")
    assert len(faelle) > 50 and not fehler, f"{len(fehler)} Abweichungen: {fehler[:5]}"


def test_alarm_format_loest_keinen_ausblick_auf(caplog):
    """Der Alarm-Pfad braucht nur die Kanal-Zeilen: er loest den 3-Tages-
    Ausblick nicht mit auf und meldet darum auch dessen Rueckfall-Warnung
    (#1848 A3, unaufloesbare Ausblick-Liste) nicht."""
    import logging

    from app.loader import _parse_display_config
    from services.channel_list_resolver import resolve_channel_lists
    from services.notification_service import _alert_format_modes, _alert_indicator_keys

    dc = _parse_display_config({
        "metrics": [{"metric_id": "gust", "enabled": True}],
        "outlook_metrics": ["humidity"],
    })
    with caplog.at_level(logging.WARNING):
        resolve_channel_lists(dc, "trip", "evening")
    assert any("#1848 A3" in r.getMessage() for r in caplog.records), "Vorbedingung"
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        modi = _alert_format_modes(dc)
        _alert_indicator_keys(dc)
    assert "gust" in modi["email"]
    assert not any("#1848 A3" in r.getMessage() for r in caplog.records), caplog.text
