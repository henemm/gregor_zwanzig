"""#3156: Renderer-Nachzug Roh/Einfach aus EINER Quelle (``zwei_formen_stellen``).

SPEC: docs/specs/modules/feat_3156_renderer_nachzug_roh_einfach.md (AC-1..AC-9),
uebergeordnet docs/specs/modules/feat_3122_was_steht_wo.md (Teil A Nr. 4,
AC-5, AC-6, AC-11), ADR-0124 Nr. 5.

Kern-Schicht ueber den ECHTEN Versandweg (Trip: ``NotificationService``,
Orte: ``send_one_compare_preset``); einzige Naehte sind Wetter und Transport
(Muster der #3122-Tests). Kein ``Mock()``/``patch()``. Das Soll steht von Hand
im Test.

Zwei Arten von Tests:
* Verhaltenstests (AC-1, Trip-Telegram, AC-3, AC-4, AC-5, AC-6): rot bis zum
  Nachzug.
* Regressionswaechter (AC-2, AC-7, AC-8): Golden-Dateien unter
  ``tests/fixtures/renderer_nachzug_3156/``, ERZEUGT aus dem Stand VOR dem
  Nachzug (Commit der RED-Phase). Sie sind bewusst schon jetzt gruen und
  muessen es nach dem Nachzug bleiben. Neu erzeugen nur mit
  ``GOLDEN_3156_SCHREIBEN=1`` und nur, wenn eine Spec die Ausgabe aendert.
"""
from __future__ import annotations

import copy
import os
import re
from pathlib import Path

import pytest

from app.metric_catalog import get_all_metrics, get_metric
from tests.helpers.einstellung_gleich_mail_orte import html_vergleichszellen
from tests.helpers.einstellung_gleich_mail_trip import klartext_tabellen
from tests.tdd._einstellung_gleich_mail_trip_fixtures import BASIS_KATALOG, mail_teile
from tests.tdd.test_einstellung_gleich_mail_orte_tabelle import (  # noqa: F401  (Fixture)
    AN, ORTSNAMEN, mit, preset, senden as orte_senden, tg_bloecke,
)
from tests.tdd.test_einstellung_gleich_mail_trip_tabelle import (
    _tg_kurz, senden as trip_senden, tabelle, telegram_tabelle, trip, zeile,
)

ALLE_IDS = [m.id for m in get_all_metrics()]
GOLDEN_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "renderer_nachzug_3156"
PUNKT = "border-radius:50%"


def _wortstufe(pct: float) -> str:
    from services.weather_metrics import format_rain_probability_scale

    return format_rain_probability_scale(pct, lang="de")


#: Alle vier Wortstufen der Regenwahrscheinlichkeit (DE).
WORTSTUFEN = {_wortstufe(p) for p in (0, 30, 60, 90)}


# ---------------------------------------------------------------------------
# Golden-Hilfen (Regressionswaechter)
# ---------------------------------------------------------------------------

_WOCHENTAG = r"\b(Mo|Di|Mi|Do|Fr|Sa|So|Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Sonntag)\b"


def _normal(text: str | None, uid: str) -> str:
    """Fluechtige Teile (Nutzerkennung, Erstellzeit, Datum relativ zu heute,
    Wochentag) ersetzen -- der Rest muss zeichengleich bleiben."""
    if text is None:
        return "<FEHLT>"
    t = text.replace(uid, "<UID>")
    t = re.sub(r"Erstellt: [^\n<]*", "Erstellt: <ZEIT>", t)
    t = re.sub(r"\d{4}-\d{2}-\d{2}(T[\d:.]+Z?)?", "<DATUM>", t)
    t = re.sub(r"\d{2}\.\d{2}\.\d{4}", "<DATUM>", t)
    t = re.sub(r"\b\d{2}\.\d{2}\.(?!\d)", "<TT.MM.>", t)
    # Versand-/Erstellzeit (Uhrzeit des Testlaufs) in Kopf und Fuss.
    t = re.sub(r"\b\d{2}:\d{2}( \((CET|CEST|UTC)\)| (CET|CEST|UTC)\b)", r"<UHR>\1", t)
    t = re.sub(_WOCHENTAG, "<WT>", t)
    return re.sub(r"(gesendet <WT> · )\d{2}:\d{2}", r"\1<UHR>", t)


def _golden(name: str, ist: str) -> None:
    pfad = GOLDEN_DIR / f"{name}.txt"
    if os.environ.get("GOLDEN_3156_SCHREIBEN") == "1":
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        pfad.write_text(ist, encoding="utf-8")
    assert pfad.exists(), f"Golden fehlt: {pfad} (Stand vor dem Nachzug)"
    soll = pfad.read_text(encoding="utf-8")
    assert ist == soll, f"Ausgabe {name} weicht vom Stand vor dem Nachzug ab"


def _trip_ausgaben(monkeypatch, data: dict, report_type: str = "evening") -> dict[str, str]:
    from tests.tdd._einstellung_gleich_mail_trip_fixtures import render_trip_mit_ausblick

    mitschrift, _trip, uid = render_trip_mit_ausblick(monkeypatch, data, report_type=report_type)
    html, plain = mail_teile(mitschrift)
    aus = {"html": _normal(html, uid), "plain": _normal(plain, uid)}
    for kanal in ("telegram", "sms", "premium_sms"):
        aus[kanal] = "\n=====\n".join(
            _normal(s["body"], uid) for s in mitschrift.sendungen(kanal))
    return aus


def _orte_ausgaben(mit_, p: dict) -> dict[str, str]:  # noqa: F811
    aus = orte_senden(mit_, p, slot="evening")
    uid = aus["uid"]
    return {k: _normal(aus[k], uid) for k in ("html", "plain", "telegram", "sms", "premium_sms")}


# ---------------------------------------------------------------------------
# Trip: AC-1 (Nur-Text), AC-2 (HTML unveraendert), Trip-Telegram
# ---------------------------------------------------------------------------

def _trip_regen(monkeypatch, *, email: str = "raw", telegram: str = "raw"):
    folge = list(BASIS_KATALOG) + ["rain_probability"]
    data = trip(tabelle([zeile("rain_probability", email=email, telegram=telegram),
                         zeile("temperature")], outlook_reports=[]), folge=folge)
    mitschrift = trip_senden(monkeypatch, data, "evening", mit_ausblick=False)
    html, plain = mail_teile(mitschrift)
    return mitschrift, html, plain


def _regen_zellen_text(plain: str) -> list[str]:
    tabs = klartext_tabellen(plain)["etappe"]
    assert tabs, "Vorbedingung: Etappentabelle im Klartext"
    return tabs[0].spalte("rain_probability")


def test_ac1_trip_nur_text_regenwahrscheinlichkeit_einfach_ist_wortstufe(monkeypatch):
    """AC-1: Trip, Regenwahrscheinlichkeit E-Mail Einfach -> die Nur-Text-Mail
    zeigt in der Etappentabelle die Wortstufe (Regenwahrscheinlichkeits-Skala,
    dieselbe wie im Orte-Vergleich), keine Zahl."""
    _m, _html, plain = _trip_regen(monkeypatch, email="simplified")
    zellen = _regen_zellen_text(plain)
    assert zellen, "Vorbedingung: Spalte Regenwahrscheinlichkeit im Klartext"
    assert not any(re.match(r"\d", z) for z in zellen), f"Zahl statt Wortstufe: {zellen}"
    # Seed: 60 % in jeder Stunde -> eine Wortstufe aus der Skala.
    assert set(zellen) == {_wortstufe(60)}, zellen


def test_ac1_trip_nur_text_regenwahrscheinlichkeit_roh_ist_zahl(monkeypatch):
    """AC-1 (Gegenprobe): Roh -> die Zahl (Waechter, schon heute gruen)."""
    _m, _html, plain = _trip_regen(monkeypatch, email="raw")
    zellen = _regen_zellen_text(plain)
    assert zellen and all(re.fullmatch(r"\d+", z) for z in zellen), zellen


def test_trip_telegram_regenwahrscheinlichkeit_einfach_ist_wortstufe(monkeypatch):
    """PO-Briefing-Zusatz: Trip-Telegram Regenwahrscheinlichkeit Einfach ->
    Wortstufe in Kurzuebersicht und Segmenttabelle; die E-Mail (Roh) bleibt
    dabei unveraendert."""
    m, html, plain = _trip_regen(monkeypatch, telegram="simplified")
    kurz = _tg_kurz(m, "PR")
    assert re.fullmatch(r"[^\d@]+@\d\d", kurz), f"Kurzuebersicht PR: {kurz!r}"
    assert kurz.split("@")[0] == _wortstufe(60), kurz
    koepfe, zeilen = telegram_tabelle(m)
    spalte = [z[koepfe.index("PR")] for z in zeilen]
    assert not any(re.match(r"\d", z) for z in spalte), f"Segmenttabelle PR: {spalte}"

    m_roh, html_roh, plain_roh = _trip_regen(monkeypatch, telegram="raw")
    assert re.fullmatch(r"\d+@\d\d", _tg_kurz(m_roh, "PR")), _tg_kurz(m_roh, "PR")
    assert _regen_zellen_text(plain) == _regen_zellen_text(plain_roh), "Telegram aendert Mail"


def test_ac2_trip_html_regenwahrscheinlichkeit_einfach_unveraendert(monkeypatch):
    """AC-2 (Regressionswaechter, Golden vor dem Nachzug): HTML-Trip-Mail mit
    Regenwahrscheinlichkeit Einfach zeigt den Ampelpunkt und bleibt
    zeichengleich."""
    folge = list(BASIS_KATALOG) + ["rain_probability"]
    data = trip(tabelle([zeile("rain_probability", email="simplified"), zeile("temperature")],
                        outlook_reports=["evening"]), folge=folge)
    aus = _trip_ausgaben(monkeypatch, data)
    assert PUNKT in aus["html"].replace(" ", "")
    _golden("ac2_trip_html_regen_einfach", aus["html"])


# ---------------------------------------------------------------------------
# Orte: AC-3 (HTML-Ampelpunkt), AC-6 (Telegram/Klartext ueber channel_layouts)
# ---------------------------------------------------------------------------

def _orte_regen(mit_, fmt: str) -> dict:  # noqa: F811
    zeilen = [{"metric_id": "rain_probability", "places": AN, "formats": {"email": fmt}},
              {"metric_id": "temperature", "places": AN}]
    return orte_senden(mit_, preset(zeilen), slot="evening")


def test_ac3_orte_html_regenwahrscheinlichkeit_einfach_ampelpunkt(mit):  # noqa: F811
    """AC-3: Orte-HTML-Uebersicht, Regenwahrscheinlichkeit Einfach -> Ampelpunkt
    statt Wortstufe (wie Wind/Boeen/Niederschlag), kein Text daneben."""
    zellen = html_vergleichszellen(_orte_regen(mit, "simplified")["html"])["rain_probability"]
    for text, roh_html in zellen:
        assert PUNKT in roh_html.replace(" ", ""), f"kein Ampelpunkt: {roh_html}"
        assert text not in WORTSTUFEN, f"Wortstufe statt Ampelpunkt: {text!r}"


def test_ac3_orte_html_regenwahrscheinlichkeit_roh_ist_zahl(mit):  # noqa: F811
    """AC-3 (Gegenprobe): Roh -> Zahl, kein Ampelpunkt (Waechter)."""
    zellen = html_vergleichszellen(_orte_regen(mit, "raw")["html"])["rain_probability"]
    for text, roh_html in zellen:
        assert re.match(r"\d", text) and PUNKT not in roh_html.replace(" ", ""), zellen


ORTE_GRUND = [("temperature", "max"), ("rain_probability", "max"), ("thunder", "max")]


def _orte_kanal_layout(mit_, einfach: bool) -> dict:  # noqa: F811
    """Altform ``channel_layouts`` (ohne Tabelle): Regenwahrscheinlichkeit und
    Gewitter in Telegram und E-Mail mit ``use_friendly_format``."""
    p = preset(grund=ORTE_GRUND)
    del p["display_config"]["placements"]
    eintraege = [{"metric_id": "temperature"},
                 {"metric_id": "rain_probability", "use_friendly_format": einfach},
                 {"metric_id": "thunder", "use_friendly_format": einfach}]
    p["display_config"]["channel_layouts"] = {
        "telegram": copy.deepcopy(eintraege), "email": copy.deepcopy(eintraege)}
    return orte_senden(mit_, p, slot="evening")


def _tg_zelle(tg: str, ort: str, label: str) -> str:
    for z in tg_bloecke(tg)[ort]:
        for c in z.split(" · "):
            if c.startswith(label + " "):
                return c[len(label) + 1:]
    raise AssertionError(f"keine Zelle {label!r} fuer {ort}: {tg}")


def test_ac6_orte_telegram_regenwahrscheinlichkeit_einfach_wirkt(mit):  # noqa: F811
    """AC-6: Orte-Telegram (Altform channel_layouts) mit Regenwahrscheinlichkeit
    Einfach zeigt die Wortstufe statt der Zahl -- die Telegram-Stelle hat laut
    Quelle zwei Formen (heute verworfen, weil ``format_modes`` nur Roh kennt)."""
    aus = _orte_kanal_layout(mit, True)
    for ort in ORTSNAMEN:
        wert = _tg_zelle(aus["telegram"], ort, "Regenwahrscheinlichkeit")
        assert not re.match(r"\d", wert), f"{ort}: Zahl statt Einfach: {wert!r}"
        assert wert.split("@")[0] in WORTSTUFEN, wert


def test_ac6_orte_klartext_regenwahrscheinlichkeit_einfach_wirkt(mit):  # noqa: F811
    """AC-6: Orte-Klartext-Uebersicht (Altform channel_layouts, E-Mail) mit
    Regenwahrscheinlichkeit Einfach -> Wortstufe."""
    aus = _orte_kanal_layout(mit, True)
    werte = re.findall(r"^   Regenwahrscheinlichkeit: (.*)$", aus["plain"], re.M)
    assert werte, aus["plain"][:600]
    assert all(w in WORTSTUFEN for w in werte), werte


def test_ac6_orte_gewitter_einfach_bleibt_stufenwort(mit):  # noqa: F811
    """AC-6: Gewitter auf Einfach zeigt in Telegram wie bisher das Stufenwort
    (Gewitter hat dort laut Quelle nur eine Form) -- gleich wie Roh."""
    einfach = _orte_kanal_layout(mit, True)
    roh = _orte_kanal_layout(mit, False)
    for ort in ORTSNAMEN:
        assert (_tg_zelle(einfach["telegram"], ort, "Gewitter")
                == _tg_zelle(roh["telegram"], ort, "Gewitter")), ort


# ---------------------------------------------------------------------------
# AC-4 / Test 9: jede Faehigkeitsabfrage im Renderpfad folgt der Quelle
# ---------------------------------------------------------------------------

SOLL_AMPEL = {"wind", "gust", "precipitation", "rain_probability"}


def _ampel_aus_quelle() -> set[str]:
    from app.metric_catalog import zwei_formen_stellen

    return {m.id for m in get_all_metrics()
            if "email" in zwei_formen_stellen(m.id) and m.display_thresholds}


def test_ac4_ampelmenge_im_katalog_abgeleitet_aus_quelle():
    """Test 9: der Katalog fuehrt EINE Ampel-Menge, abgeleitet aus der
    E-Mail-Stelle der Quelle plus Schwellen (Gewitter ohne Schwellen: eigener
    Zweig)."""
    from app import metric_catalog

    assert _ampel_aus_quelle() == SOLL_AMPEL
    assert set(metric_catalog.AMPEL_METRIC_IDS) == SOLL_AMPEL


def test_ac4_renderer_ampellisten_sind_die_katalog_menge():
    """Test 9: Orte-HTML (``_FRIENDLY_AMPEL_METRIC_IDS``) und Trip-HTML/Alarm
    (``_AMPEL_CAPABLE_METRIC_IDS``) nennen dieselbe Menge wie die Quelle."""
    from output.renderers.email.compare_html import _FRIENDLY_AMPEL_METRIC_IDS
    from output.renderers.email.helpers import _AMPEL_CAPABLE_METRIC_IDS

    assert set(_FRIENDLY_AMPEL_METRIC_IDS) == SOLL_AMPEL, "Orte-HTML-Ampelliste weicht ab"
    assert set(_AMPEL_CAPABLE_METRIC_IDS) == SOLL_AMPEL


def test_ac4_regenwahrscheinlichkeit_hat_im_katalog_zwei_formen():
    """Die Regenwahrscheinlichkeit hat laut Quelle an der E-Mail-Stelle zwei
    Formen -- ``format_modes`` kennt Einfach; Standard bleibt Roh."""
    m = get_metric("rain_probability")
    assert "simplified" in m.format_modes, m.format_modes
    assert m.default_format_mode == "raw"


@pytest.mark.parametrize("metric_id", ALLE_IDS)
def test_ac4_format_modes_folgt_email_stelle(metric_id):
    """Zwei ``format_modes`` genau dort, wo die Quelle an der E-Mail-Stelle
    zwei Formen nennt (keine benannte Differenz mehr)."""
    from app.metric_catalog import zwei_formen_stellen

    assert (len(get_metric(metric_id).format_modes) > 1) == ("email" in zwei_formen_stellen(metric_id))


@pytest.mark.parametrize("metric_id", ALLE_IDS)
def test_ac4_ausblick_faehigkeit_folgt_quelle(metric_id):
    from app.metric_catalog import (
        OUTLOOK_FRIENDLY_CAPABLE, outlook_friendly_capable, zwei_formen_stellen,
    )

    soll = "outlook" in zwei_formen_stellen(metric_id)
    assert outlook_friendly_capable(metric_id) is soll
    assert (metric_id in OUTLOOK_FRIENDLY_CAPABLE) is soll


def test_ac4_stundenverlauf_formate_nur_wo_quelle_zwei_formen_nennt():
    """Orte-Stundenverlauf: gespeichertes Einfach fuer Sonnenstunden und
    Windrichtung wird verworfen (dort nur eine Form); Wind bleibt."""
    from output.renderers.compare_outlook_metric_ids import resolve_hourly_metric_formats

    aus = resolve_hourly_metric_formats(
        {"sunshine": True, "wind_direction": True, "wind": True, "rain_probability": False})
    assert aus == {"wind": True, "rain_probability": False}, aus


def _kanalzeilen(kanal: str, kennung: str) -> set[bool]:
    from output.renderers.compare_metric_ids import resolve_channel_layout_rows

    rows = resolve_channel_layout_rows(
        None, {kanal: [{"metric_id": kennung, "use_friendly_format": True}]}, kanal)
    assert rows, f"Vorbedingung: Zeilen fuer {kennung}"
    return {einfach for _rid, einfach in rows}


@pytest.mark.parametrize("kanal,kennung,soll", [
    ("telegram", "rain_probability", True),
    ("email", "rain_probability", True),
    ("telegram", "thunder", False),
    ("email", "thunder", True),
    ("telegram", "gust", True),
    ("telegram", "temperature", False),
])
def test_ac4_kanal_einfach_folgt_quelle_je_stelle(kanal, kennung, soll):
    """Orte-Telegram/Klartext (``channel_layouts``): Einfach wirkt genau an den
    Stellen, die die Quelle fuer diese Metrik nennt."""
    assert _kanalzeilen(kanal, kennung) == {soll}


# ---------------------------------------------------------------------------
# AC-5: Sonnenstunden/Windrichtung im Orte-Stundenverlauf (Altform-Schalter)
# ---------------------------------------------------------------------------

def test_ac5_stundenverlauf_sonne_windrichtung_einfach_gleich_roh(mit):  # noqa: F811
    """AC-5 (Ausgabe, Waechter): gespeichertes Einfach fuer Sonnenstunden und
    Windrichtung im Stundenverlauf aendert die Mail nicht gegenueber Roh."""
    grund = [("temperature", "max"), ("sunshine", "sum"), ("wind_direction", "avg")]

    def lauf(wert: bool) -> dict:
        p = preset(grund=grund)
        p["display_config"]["hourly_metric_formats"] = {"sunshine": wert, "wind_direction": wert}
        return _orte_ausgaben(mit, p)

    einfach, roh = lauf(True), lauf(False)
    assert einfach["html"] == roh["html"]
    assert einfach["plain"] == roh["plain"]


# ---------------------------------------------------------------------------
# AC-7 / AC-8: Altbestand und SMS zeichengleich (Golden vor dem Nachzug)
# ---------------------------------------------------------------------------

def test_ac7_trip_altbestand_ohne_einfach_zeichengleich(monkeypatch):
    """AC-7 (Regressionswaechter): Trip ohne Tabelle und ohne gespeichertes
    Format (Altbestand, Regenwahrscheinlichkeit dabei) -- jede Ausgabe
    zeichengleich zum Stand vor dem Nachzug."""
    from tests.tdd._einstellung_gleich_mail_trip_fixtures import trip_json
    from tests.tdd.test_einstellung_gleich_mail_trip_tabelle import ALLE_KANAELE

    folge = list(BASIS_KATALOG) + ["rain_probability"]
    data = trip_json(folge, report_config=dict(ALLE_KANAELE))
    aus = _trip_ausgaben(monkeypatch, data)
    for kanal, text in aus.items():
        _golden(f"ac7_trip_altbestand_{kanal}", text)


def test_ac7_trip_altbestand_ampel_altform_nur_text_bleibt_zahl(monkeypatch):
    """AC-7 / Known Limitation: Altbestand mit ``use_friendly_format`` (HTML-
    Ampel) fuer die Regenwahrscheinlichkeit -- die Nur-Text-Mail bleibt bei
    der Zahl (Nur-Text folgt erst mit der Migration B6)."""
    from tests.tdd._einstellung_gleich_mail_trip_fixtures import trip_json
    from tests.tdd.test_einstellung_gleich_mail_trip_tabelle import ALLE_KANAELE

    folge = list(BASIS_KATALOG) + ["rain_probability"]
    data = trip_json(folge, einfach={"rain_probability", "wind", "gust", "precipitation"},
                     report_config=dict(ALLE_KANAELE))
    aus = _trip_ausgaben(monkeypatch, data)
    for kanal, text in aus.items():
        _golden(f"ac7_trip_altbestand_ampel_{kanal}", text)


def test_ac7_orte_altbestand_ohne_einfach_zeichengleich(mit):  # noqa: F811
    """AC-7 (Regressionswaechter): Orte-Abo mit Tabelle ohne gespeichertes
    Format -- jede Ausgabe zeichengleich zum Stand vor dem Nachzug."""
    aus = _orte_ausgaben(mit, preset())
    for kanal, text in aus.items():
        _golden(f"ac7_orte_altbestand_{kanal}", text)


def test_ac8_sms_mit_gespeichertem_format_zeichengleich(monkeypatch):
    """AC-8 (Regressionswaechter): gespeichertes Einfach an E-Mail/Telegram
    und ein (wirkungsloses) SMS-Format -- SMS und Premium-SMS zeichengleich."""
    folge = list(BASIS_KATALOG) + ["rain_probability"]
    data = trip(tabelle([zeile("rain_probability", email="simplified", telegram="simplified",
                               sms="simplified"),
                         zeile("gust", email="simplified", sms="simplified"),
                         zeile("temperature")], outlook_reports=[]), folge=folge)
    aus = _trip_ausgaben(monkeypatch, data)
    _golden("ac8_trip_sms", aus["sms"])
    _golden("ac8_trip_premium_sms", aus["premium_sms"])
