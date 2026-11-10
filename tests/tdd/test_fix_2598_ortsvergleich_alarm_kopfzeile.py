"""Ortsvergleich-Alarm: Ortsname einmal, kein "km 0–0" (Issue #2598).

SPEC:    docs/specs/modules/fix_2598_ortsvergleich_alarm_kopfzeile.md (AC-1 bis AC-11)
KONTEXT: docs/context/fix-2598-ortsvergleich-alarm-kopfzeile.md

Heute (gemessen gegen origin/main 4fd66fa74) sieht ein Ortsvergleich-Alarm so aus:

    Betreff   [Ort Eins] Ort Eins · ↑ Böen: 30 km/h→60 km/h
    Telegram  <b>Ort Eins · Ort Eins · ↑ Böen</b>
              km 0–0 · stärkste Stunde 14:00
    Radar     [Ort Eins] km 0–0 · Regen in 30 Min
              Wo & wann: km 0–0 · ab 14:30

Geprueft wird ausschliesslich, was den Nutzer erreicht: echte
`WeatherChange`-/`NowcastResult`-Objekte durch die echten Projektionen
(`to_multi_point_alert_message`, `to_multi_location_onset_alert_message`) und
die echten Renderer (`render_subject`, `render_telegram`, `render_email`,
`render_sms`). Telegram-Kurzform und Premium-SMS senden den Text von
`render_sms(..., location_positions=...)` (`notification_service.py`
`_dispatch_alert_message`), die Vorschau ruft dieselben Bausteine
(`compare_alert_preview_service.py`) und wird hier zusaetzlich echt aufgerufen.
Kein Mock, kein Patch.

Trip-Alarme setzen `location_label` nie; ihre Ausgabe ist als feste Referenz
aus dem Stand VOR dem Fix im Test hinterlegt (AC-9).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.ampel import resolve_ampel

UTC = timezone.utc
TZ = ZoneInfo("UTC")
EINS = "Ort Eins"
ZWEI = "Ort Zwei"
POSITIONEN = {EINS: 1, ZWEI: 2}
KM_NULL = "km 0–0"
_UHR = r"\d\d:\d\d"
# Kurzform (SMS, Premium-SMS, Telegram-Kurzform) schreibt die Stunde ohne
# fuehrende Null (`R@3:46`, Bestandsformat, sms_format.md); vor 10 Uhr waere
# `_UHR` dort rot, unabhaengig vom Fix.
_SMS_UHR = r"\d{1,2}:\d\d"


# ---------------------------------------------------------------------------
# Echte Domaenen-Objekte
# ---------------------------------------------------------------------------

def _loc(name: str):
    from app.user import SavedLocation

    return SavedLocation(id=name.lower().replace(" ", "-"), name=name,
                         lat=None, lon=None, elevation_m=20)


def _boeen(old: float = 30.0, new: float = 60.0):
    from app.models import ChangeSeverity, WeatherChange

    return WeatherChange(
        metric="gust_max_kmh", old_value=old, new_value=new, delta=new - old,
        threshold=20.0, severity=ChangeSeverity.MODERATE, direction="increase",
        occurred_at=datetime(2026, 7, 1, 14, 0, tzinfo=UTC),
    )


def _wind():
    from app.models import ChangeSeverity, WeatherChange

    return WeatherChange(
        metric="wind_max_kmh", old_value=1.0, new_value=8.0, delta=7.0,
        threshold=2.0, severity=ChangeSeverity.MODERATE, direction="increase",
        occurred_at=datetime(2026, 7, 1, 15, 0, tzinfo=UTC),
    )


def _gewitter_beginn_frueher(segment_id=None):
    """Beginn-Verschiebung: Gewitter-Beginn 12:00 → 10:00 UTC (2 h früher)."""
    from app.models import ChangeSeverity, WeatherChange

    alt = datetime(2026, 7, 1, 12, 0, tzinfo=UTC).timestamp()
    neu = datetime(2026, 7, 1, 10, 0, tzinfo=UTC).timestamp()
    return WeatherChange(
        metric="thunder_onset_utc", old_value=alt, new_value=neu, delta=neu - alt,
        threshold=3600.0, severity=ChangeSeverity.MODERATE, direction="decrease",
        segment_id=segment_id,
    )


def _aenderung(groups):
    """Ortsvergleich-Änderungsalarm über die echte Projektion."""
    from output.renderers.alert.project import to_multi_point_alert_message

    return to_multi_point_alert_message(
        [(name, changes, _loc(name)) for name, changes in groups],
        tz=TZ, stand_at="10:00", ampel=resolve_ampel(None),
    )


def _nowcast():
    from services.radar_service import NowcastResult

    return NowcastResult(onset_minutes=30, intensity_label="leichter Regen",
                         source="Radar (AROME-FR)", is_convective=False)


def _radar(names):
    """Ortsvergleich-Radar-Alarm über die echte Projektion."""
    from output.renderers.alert.project import to_multi_location_onset_alert_message

    return to_multi_location_onset_alert_message(
        [(name, _loc(name), _nowcast()) for name in names],
        tz=TZ, stand_at="10:00", ampel=resolve_ampel(None),
    )


FAELLE = {
    "1 Ort, 1 Metrik": lambda: _aenderung([(EINS, [_boeen()])]),
    "1 Ort, 2 Metriken": lambda: _aenderung([(EINS, [_boeen(), _wind()])]),
    "2 Orte": lambda: _aenderung([(EINS, [_boeen()]), (ZWEI, [_boeen(40.0, 70.0)])]),
    "1 Ort, nur Beginn": lambda: _aenderung([(EINS, [_gewitter_beginn_frueher()])]),
    "1 Ort, Böen + Beginn": lambda: _aenderung([(EINS, [_boeen(), _gewitter_beginn_frueher()])]),
    "2 Orte, nur Beginn": lambda: _aenderung([
        (EINS, [_gewitter_beginn_frueher()]), (ZWEI, [_gewitter_beginn_frueher()]),
    ]),
    # Adversary F001: Bündel OHNE über-Schwelle-Ereignis -> eigener
    # Betreff-/Kopf-Zweig "N Änderungen seit dem Briefing".
    "2 Orte unter Schwelle": lambda: _aenderung([
        (EINS, [_boeen(30.0, 35.0)]), (ZWEI, [_boeen(30.0, 36.0)]),
    ]),
    "1 Ort, 2 unter Schwelle": lambda: _aenderung([
        (EINS, [_boeen(30.0, 35.0), _boeen(30.0, 36.0)]),
    ]),
    "Radar 1 Ort": lambda: _radar([EINS]),
    "Radar 2 Orte": lambda: _radar([EINS, ZWEI]),
}


def _sichtbar(html: str) -> str:
    from bs4 import BeautifulSoup

    return BeautifulSoup(html, "html.parser").get_text("\n")


def _kanaele(msg, lang: str) -> dict[str, str]:
    """Jeder Text, der aus dieser Nachricht einen Nutzer erreicht."""
    from output.renderers.alert.render import (
        render_email, render_sms, render_subject, render_telegram,
    )

    html, plain = render_email(msg, lang=lang)
    return {
        "Betreff": render_subject(msg, lang=lang),
        "Mail (Text)": plain,
        "Mail (HTML)": _sichtbar(html),
        "Telegram": render_telegram(msg, lang=lang),
        "SMS/Premium-SMS/Telegram-Kurzform": render_sms(msg, location_positions=POSITIONEN),
        "SMS ohne Ortsnummern (Vorschau/Validator)": render_sms(msg),
    }


def _kopf(telegram: str) -> str:
    return telegram.splitlines()[0]


# Derselbe Ortsname (oder dieselbe Ortsliste) zweimal hintereinander, nur durch
# Leerraum, Trenner oder Klammern getrennt: "Ort Eins · Ort Eins",
# "[Ort Eins] Ort Eins", "Ort Eins Ort Eins:".
_DOPPELT = re.compile(
    r"(Ort Eins, Ort Zwei|Ort Eins|Ort Zwei)[\s·:\[\]()<>/b]*\1(?![\w])"
)


def _assert_kein_befund(text: str, wo: str) -> None:
    assert KM_NULL not in text, f"{wo}: '{KM_NULL}' statt Ortsname:\n{text}"
    treffer = _DOPPELT.search(text)
    assert treffer is None, (
        f"{wo}: Ortsname doppelt hintereinander ({treffer.group(0)!r}):\n{text}"
    )


# ---------------------------------------------------------------------------
# AC-1 — 1 Ort, 1 Metrik
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang,betreff,kopf,zeile", [
    ("de", "[Ort Eins] ↑ Böen: 30 km/h→60 km/h", "<b>Ort Eins · ↑ Böen</b>",
     "Ort Eins · stärkste Stunde 14:00"),
    ("en", "[Ort Eins] ↑ Gusts: 30 km/h→60 km/h", "<b>Ort Eins · ↑ Gusts</b>",
     "Ort Eins · peak hour 14:00"),
])
def test_ac1_ein_ort_eine_metrik_nennt_den_namen_einmal(lang, betreff, kopf, zeile):
    """AC-1: Given ein Ortsvergleich-Änderungsalarm für genau "Ort Eins" mit
    Böen 30 → 60 km/h / When Betreff, Telegram und Mail gerendert werden /
    Then Betreff `[Ort Eins] ↑ Böen: …`, Telegram-Kopf `<b>Ort Eins · ↑ Böen</b>`,
    Ereigniszeile `Ort Eins · stärkste Stunde 14:00`, nie `km 0–0`.

    RED heute: Betreff `[Ort Eins] Ort Eins · ↑ Böen…`, Kopf
    `<b>Ort Eins · Ort Eins · ↑ Böen</b>`, Zeile `km 0–0 · stärkste Stunde 14:00`.
    """
    msg = FAELLE["1 Ort, 1 Metrik"]()
    k = _kanaele(msg, lang)

    assert k["Betreff"] == betreff
    assert _kopf(k["Telegram"]) == kopf
    assert zeile in k["Telegram"].splitlines(), k["Telegram"]
    wo = "Wo & wann" if lang == "de" else "Where & when"
    assert f"{wo}: {zeile}" in k["Mail (Text)"].splitlines()
    for kanal, text in k.items():
        _assert_kein_befund(text, kanal)


# ---------------------------------------------------------------------------
# AC-2 — 1 Ort, mehrere Metriken
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang,betreff_anfang,kopf", [
    ("de", "[Ort Eins] ↑ 2 über Schwelle: ", "<b>Ort Eins · 2 über Schwelle</b>"),
    ("en", "[Ort Eins] ↑ 2 over threshold: ", "<b>Ort Eins · 2 over threshold</b>"),
])
def test_ac2_ein_ort_mehrere_metriken_nennt_den_namen_einmal(lang, betreff_anfang, kopf):
    """AC-2: Given ein Ort mit zwei geänderten Metriken / When Betreff und
    Telegram-Kopf gerendert werden / Then steht der Ortsname genau einmal.

    RED heute: `[Ort Eins] Ort Eins · ↑ 2 über Schwelle…`,
    `<b>Ort Eins · Ort Eins · 2 über Schwelle</b>`.
    """
    k = _kanaele(FAELLE["1 Ort, 2 Metriken"](), lang)

    assert k["Betreff"].startswith(betreff_anfang), k["Betreff"]
    assert k["Betreff"].count(EINS) == 1, k["Betreff"]
    assert _kopf(k["Telegram"]) == kopf


# ---------------------------------------------------------------------------
# AC-3 — 2 Orte gebündelt (Betreff, Vorschau-Telegram)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang,betreff_anfang,kopf", [
    ("de", "[Ort Eins, Ort Zwei] ↑ 2 über Schwelle: ",
     "<b>Ort Eins, Ort Zwei · 2 über Schwelle</b>"),
    ("en", "[Ort Eins, Ort Zwei] ↑ 2 over threshold: ",
     "<b>Ort Eins, Ort Zwei · 2 over threshold</b>"),
])
def test_ac3_zwei_orte_nennen_die_namensliste_einmal(lang, betreff_anfang, kopf):
    """AC-3: Given ein gebündelter Alarm für zwei Orte / When Betreff und
    Telegram (Bündel, wie in der Vorschau) gerendert werden / Then erscheint
    `Ort Eins, Ort Zwei` genau einmal.

    RED heute: `[Ort Eins, Ort Zwei] Ort Eins, Ort Zwei · …` und
    `<b>Ort Eins, Ort Zwei · Ort Eins, Ort Zwei · 2 über Schwelle</b>`.
    """
    k = _kanaele(FAELLE["2 Orte"](), lang)

    assert k["Betreff"].startswith(betreff_anfang), k["Betreff"]
    assert k["Betreff"].count("Ort Eins, Ort Zwei") == 1, k["Betreff"]
    assert _kopf(k["Telegram"]) == kopf


@pytest.mark.parametrize("fall,namen", [
    ("2 Orte unter Schwelle", "Ort Eins, Ort Zwei"),
    ("1 Ort, 2 unter Schwelle", "Ort Eins"),
])
@pytest.mark.parametrize("lang,kern", [
    ("de", "2 Änderungen seit dem Briefing"),
    ("en", "2 changes since the briefing"),
])
def test_ac3_buendel_unter_schwelle_nennt_die_namen_einmal(fall, namen, lang, kern):
    """AC-3 (Adversary F001): Given ein Bündel ohne über-Schwelle-Ereignis
    (Zweig "N Änderungen seit dem Briefing") / When Betreff und Telegram
    gerendert werden / Then steht die Namensliste genau einmal, kein `km 0–0`.

    Vor dem Fix: `[Ort Eins, Ort Zwei] Ort Eins, Ort Zwei · 2 Änderungen …`."""
    k = _kanaele(FAELLE[fall](), lang)

    assert k["Betreff"] == f"[{namen}] {kern}"
    assert _kopf(k["Telegram"]) == f"<b>{namen} · {kern}</b>"
    for kanal in ("Betreff", "Telegram"):
        assert KM_NULL not in k[kanal], k[kanal]


# ---------------------------------------------------------------------------
# AC-4 — 1 Ort, Beginn-Verschiebung
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang,betreff,beginn_zeile", [
    ("de", "[Ort Eins] Gewitter-Beginn 10:00 (2 h früher)",
     "Gewitter-Beginn: 12:00 → 10:00 (2 h früher · Ort Eins)"),
    ("en", "[Ort Eins] Thunder onset 10:00 (2 h earlier)",
     "Thunder onset: 12:00 → 10:00 (2 h earlier · Ort Eins)"),
])
def test_ac4_nur_beginn_verschiebung_nennt_den_ort_statt_km(lang, betreff, beginn_zeile):
    """AC-4: Given ein Ort, bei dem sich nur der Gewitter-Beginn um zwei
    Stunden nach vorn verschoben hat / When Betreff, Telegram und Mail
    gerendert werden / Then kein `km 0–0` im Betreff und die Beginn-Zeile
    lautet `…-Beginn: 12:00 → 10:00 (2 h früher · Ort Eins)`.

    RED heute: Betreff `[Ort Eins] km 0–0 · Gewitter-Beginn 10:00 (2 h früher)`,
    Zeile `(2 h früher · km 0–0)`.
    """
    k = _kanaele(FAELLE["1 Ort, nur Beginn"](), lang)

    assert k["Betreff"] == betreff
    assert beginn_zeile in k["Telegram"].splitlines(), k["Telegram"]
    assert beginn_zeile in k["Mail (Text)"].splitlines(), k["Mail (Text)"]


@pytest.mark.parametrize("lang,beginn_zeile,ereignis_zeile", [
    ("de", "Gewitter-Beginn: 12:00 → 10:00 (2 h früher · Ort Eins)",
     "Ort Eins · stärkste Stunde 14:00"),
    ("en", "Thunder onset: 12:00 → 10:00 (2 h earlier · Ort Eins)",
     "Ort Eins · peak hour 14:00"),
])
def test_ac4_beginn_verschiebung_neben_aenderung_nennt_den_ort(lang, beginn_zeile, ereignis_zeile):
    """AC-4 (gemischter Fall): Böen-Änderung UND Beginn-Verschiebung am selben
    Ort — beide Zeilen nennen den Ort, keine `km 0–0`.

    RED heute: `km 0–0 · stärkste Stunde 14:00` und `(2 h früher · km 0–0)`.
    """
    k = _kanaele(FAELLE["1 Ort, Böen + Beginn"](), lang)

    zeilen = k["Telegram"].splitlines()
    assert ereignis_zeile in zeilen, k["Telegram"]
    assert beginn_zeile in zeilen, k["Telegram"]
    assert beginn_zeile in k["Mail (Text)"].splitlines(), k["Mail (Text)"]


@pytest.mark.parametrize("lang,label,frueher", [
    ("de", "Gewitter-Beginn", "2 h früher"),
    ("en", "Thunder onset", "2 h earlier"),
])
def test_ac4_zwei_orte_beginn_zeile_nennt_den_eigenen_ort(lang, label, frueher):
    """AC-4 (Adversary F002): Given zwei Orte mit Beginn-Verschiebung / When
    Telegram und Mail (Text und HTML) gerendert werden / Then nennt jede
    Beginn-Zeile ihren EIGENEN Ort -- das per-Ereignis-Label geht dem
    nachrichtenweiten Sammelnamen vor, der in keiner Ereigniszeile steht."""
    k = _kanaele(FAELLE["2 Orte, nur Beginn"](), lang)
    erwartet = [f"{label}: 12:00 → 10:00 ({frueher} · {name})" for name in (EINS, ZWEI)]

    for kanal in ("Telegram", "Mail (Text)"):
        zeilen = [z for z in k[kanal].splitlines() if z.startswith(f"{label}:")]
        assert zeilen == erwartet, k[kanal]
    html_zeilen = [z for z in k["Mail (HTML)"].splitlines() if z.startswith(label)]
    assert html_zeilen == [f"{label} · {EINS}", f"{label} · {ZWEI}"], k["Mail (HTML)"]
    for kanal in ("Telegram", "Mail (Text)", "Mail (HTML)"):
        ereignis = [z for z in k[kanal].splitlines() if z.startswith(label)]
        assert all("Ort Eins, Ort Zwei" not in z for z in ereignis), k[kanal]


# ---------------------------------------------------------------------------
# AC-5 — Radar, 1 Ort
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang,betreff,kopf,wo", [
    ("de", "[Ort Eins] Regen in 30 Min", "<b>Ort Eins · Regen in 30 Min</b>",
     rf"Wo & wann: Ort Eins · ab {_UHR}"),
    ("en", "[Ort Eins] Rain in 30 min", "<b>Ort Eins · Rain in 30 min</b>",
     rf"Where & when: Ort Eins · from {_UHR}"),
])
def test_ac5_radar_ein_ort_nennt_den_ort_statt_km(lang, betreff, kopf, wo):
    """AC-5: Given ein Ortsvergleich-Radar-Alarm (Regen in 30 Min) für genau
    einen Ort / When Betreff, Telegram und Mail gerendert werden / Then
    `[Ort Eins] Regen in 30 Min`, `<b>Ort Eins · Regen in 30 Min</b>`,
    `Wo & wann: Ort Eins · ab HH:MM`.

    Die Uhrzeit haengt an der Echtzeit (Projektion rechnet "jetzt + 30 Min"),
    deshalb steht sie als Muster da.

    RED heute: `[Ort Eins] km 0–0 · Regen in 30 Min`,
    `<b>Ort Eins · km 0–0 · Regen in 30 Min</b>`, `Wo & wann: km 0–0 · ab …`.
    """
    msg = FAELLE["Radar 1 Ort"]()
    k = _kanaele(msg, lang)

    assert k["Betreff"] == betreff
    assert _kopf(k["Telegram"]) == kopf
    assert any(re.fullmatch(wo, z) for z in k["Mail (Text)"].splitlines()), k["Mail (Text)"]
    # Kurznachricht bleibt, wie sie ist: Name einmal, Kuerzel unveraendert.
    assert re.fullmatch(rf"Ort Eins: R@{_SMS_UHR}", k["SMS/Premium-SMS/Telegram-Kurzform"])


def test_ac5_radar_ein_ort_haelt_die_invariante_1041():
    """AC-5 / Spec Punkt 3: das per-Event-`location_label` bleibt bei genau einem
    Ort `None` (Invariante #1041 AC-5); der Ort ist nur nachrichtenweit gesetzt
    und dient dem Renderer als Kennzeichen "Punkt-Kontext".

    RED heute: `msg.location_label` ist `None`.
    """
    msg = FAELLE["Radar 1 Ort"]()

    assert all(e.location_label is None for e in msg.events)
    assert msg.location_label == EINS


# ---------------------------------------------------------------------------
# AC-6 — Radar, 2 Orte bleibt wie seit #1767
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang,betreff,kopf,zeile", [
    ("de", "[Ort Eins, Ort Zwei] Regen-Alarm: 2 Orte", "<b>Regen-Alarm: 2 Orte</b>",
     rf"Ort Eins · Regen in 30 Min: ab {_UHR} · leichter Regen"),
    ("en", "[Ort Eins, Ort Zwei] Rain alert: 2 locations", "<b>Rain alert: 2 locations</b>",
     rf"Ort Eins · Rain in 30 min: from {_UHR} · light rain"),
])
def test_ac6_radar_zwei_orte_bleibt_wie_seit_1767(lang, betreff, kopf, zeile):
    """AC-6 (Invariante, heute gruen): der Mehrort-Radar behaelt seinen Kopf
    ohne Namens-Join, seine Ortszeilen und seine Kurznachricht."""
    k = _kanaele(FAELLE["Radar 2 Orte"](), lang)

    assert k["Betreff"] == betreff
    assert _kopf(k["Telegram"]) == kopf
    assert any(re.fullmatch(zeile, z) for z in k["Telegram"].splitlines()), k["Telegram"]
    assert re.fullmatch(rf"1:R@{_SMS_UHR} 2:R@{_SMS_UHR}", k["SMS/Premium-SMS/Telegram-Kurzform"])
    assert re.fullmatch(rf"Ort Eins:R@{_SMS_UHR} Ort Zwei:R@{_SMS_UHR}",
                        k["SMS ohne Ortsnummern (Vorschau/Validator)"])


# ---------------------------------------------------------------------------
# AC-7 / AC-10 — kein Fall, kein Kanal, keine Sprache mit Befund
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("fall", list(FAELLE))
def test_ac7_kein_kanal_zeigt_km_null_oder_doppelten_namen(fall, lang):
    """AC-7/AC-10: Given jeder Ortsvergleich-Alarm (Änderung, Beginn, Radar;
    1 und 2 Orte) in DE und EN / When er in jedem Kanal gerendert wird /
    Then enthält keine Ausgabe `km 0–0` und keine nennt denselben Ortsnamen
    zweimal hintereinander."""
    k = _kanaele(FAELLE[fall](), lang)

    for kanal, text in k.items():
        _assert_kein_befund(text, f"{fall} / {lang} / {kanal}")


# Protokoll-Token der Kurznachricht (SMS, Premium-SMS, Telegram-Kurzform) -- der
# Fix nimmt nur Ortsteile weg und darf an ihnen nichts aendern (AC-10).
_KURZNACHRICHT_VORHER = {
    "1 Ort, 1 Metrik": r"\+G60@14",
    "1 Ort, 2 Metriken": r"\+W8@15 \+G60@14",
    "2 Orte": r"2:\+G70@14 1:\+G60@14",
    "1 Ort, nur Beginn": r"Ort Eins: TH10:00 2 h früher",
    "1 Ort, Böen + Beginn": r"\+G60@14 TH10:00 2 h früher",
    "Radar 1 Ort": rf"Ort Eins: R@{_SMS_UHR}",
    "Radar 2 Orte": rf"1:R@{_SMS_UHR} 2:R@{_SMS_UHR}",
}


@pytest.mark.parametrize("fall", list(_KURZNACHRICHT_VORHER))
def test_ac10_kurznachricht_mit_ortsnummern_bleibt_unveraendert(fall):
    """AC-10 (Invariante, heute gruen): die tatsaechlich versandte
    Kurznachricht (mit Ortsnummern) behaelt Wortlaut und Kuerzel."""
    from output.renderers.alert.render import render_sms

    sms = render_sms(FAELLE[fall](), location_positions=POSITIONEN)
    assert re.fullmatch(_KURZNACHRICHT_VORHER[fall], sms), sms


# ---------------------------------------------------------------------------
# AC-8 — SMS-Kopf ohne Ortsnummern (Vorschau/Validator-Render)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fall", ["1 Ort, 1 Metrik", "1 Ort, 2 Metriken", "1 Ort, Böen + Beginn"])
def test_ac8_sms_ohne_ortsnummern_nennt_den_ort_einmal(fall):
    """AC-8: Given der SMS-Kopf-Zweig ohne `location_positions` / When
    `render_sms` aufgerufen wird / Then steht der Ortsname im Kopf genau einmal.

    RED heute: `Ort Eins Ort Eins: G30->60@14`.
    """
    from output.renderers.alert.render import render_sms

    sms = render_sms(FAELLE[fall]())
    assert sms.count(EINS) == 1, sms
    assert sms.startswith(f"{EINS}: "), sms


# ---------------------------------------------------------------------------
# AC-7 — die echte Alarm-Vorschau des Ortsvergleichs
# ---------------------------------------------------------------------------

_VORSCHAU_ORTE = [("loc-2598-a", EINS), ("loc-2598-b", ZWEI)]
_VORSCHAU_PRESET = "cp-2598-alarm"


def _vorschau_seed(user_id: str) -> None:
    from app.loader import get_data_dir, save_location
    from app.user import SavedLocation

    from tests.helpers.compare_briefings import write_compare_briefings

    for loc_id, name in _VORSCHAU_ORTE:
        save_location(SavedLocation(id=loc_id, name=name, lat=None, lon=None,
                                    elevation_m=20), user_id=user_id)
    write_compare_briefings(get_data_dir(user_id), [{
        "id": _VORSCHAU_PRESET, "name": "Vergleich 2598", "user_id": user_id,
        "location_ids": [loc_id for loc_id, _ in _VORSCHAU_ORTE],
        "schedule": "daily", "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "forecast_hours": 48, "alert_cooldown_minutes": 60,
        "empfaenger": ["a@example.invalid"], "created_at": "2026-07-01T00:00:00Z",
    }])


def _vorschau_aenderung(loc_ids, *, beginn: bool = False) -> dict:
    if beginn:
        alt = datetime(2026, 7, 1, 12, 0, tzinfo=UTC).timestamp()
        neu = datetime(2026, 7, 1, 10, 0, tzinfo=UTC).timestamp()
        return {"changes": [{
            "location_id": lid, "metric": "thunder_onset_utc", "old_value": alt,
            "new_value": neu, "delta": neu - alt, "threshold": 3600.0,
            "severity": "moderate", "direction": "decrease",
        } for lid in loc_ids]}
    return {"changes": [{
        "location_id": lid, "metric": "gust_max_kmh", "old_value": 30.0 + i,
        "new_value": 60.0 + i, "delta": 30.0, "threshold": 20.0,
        "severity": "moderate", "direction": "increase",
    } for i, lid in enumerate(loc_ids)]}


def _vorschau_radar(loc_ids) -> dict:
    return {"onsets": [{
        "location_id": lid, "onset_minutes": 30, "intensity_label": "leichter Regen",
        "source": "radar", "is_convective": False,
    } for lid in loc_ids]}


_VORSCHAU_FAELLE = {
    "Änderung 1 Ort": lambda: _vorschau_aenderung(["loc-2598-a"]),
    "Änderung 2 Orte": lambda: _vorschau_aenderung(["loc-2598-a", "loc-2598-b"]),
    "Beginn 1 Ort": lambda: _vorschau_aenderung(["loc-2598-a"], beginn=True),
    "Radar 1 Ort": lambda: _vorschau_radar(["loc-2598-a"]),
    "Radar 2 Orte": lambda: _vorschau_radar(["loc-2598-a", "loc-2598-b"]),
}


@pytest.mark.parametrize("fall", list(_VORSCHAU_FAELLE))
def test_ac7_alarm_vorschau_zeigt_weder_km_null_noch_doppelten_namen(env, fall):  # noqa: F811
    """AC-7 (Vorschau): Given ein Ortsvergleich dieses Nutzers / When seine
    Alarm-Vorschau abgerufen wird / Then zeigt kein Kanal `km 0–0` oder einen
    doppelten Ortsnamen.

    RED heute: Änderung 1 Ort -> `[Ort Eins] Ort Eins · …`; Radar 1 Ort ->
    `[Ort Eins] km 0–0 · Regen in 30 Min`."""
    from services.compare_alert_preview_service import render_compare_alert_preview

    user_id = env
    _vorschau_seed(user_id)
    got = render_compare_alert_preview(
        _VORSCHAU_PRESET, user_id=user_id, body=_VORSCHAU_FAELLE[fall](),
    )

    texte = {
        "subject": got["subject"], "email_plain": got["email_plain"],
        "email_html": _sichtbar(got["email_html"]), "sms": got["sms"],
        "telegram": got["telegram"],
    }
    for i, blase in enumerate(got["telegram_bubbles"]):
        texte[f"telegram_blase_{i}"] = blase
    for kanal, text in texte.items():
        _assert_kein_befund(text, f"Vorschau {fall} / {kanal}")


# ---------------------------------------------------------------------------
# AC-9 — Trip-Alarme byte-identisch zum Stand vor dem Fix
# ---------------------------------------------------------------------------

# Aufgenommen am 2026-11-09 gegen origin/main 4fd66fa74 (Stand VOR dem Fix) mit
# den Projektionen aus tests/tdd/test_alert_location_vocabulary.py.
TRIP_REFERENZ = {
    ('trip_delta', 'de'): {
        'subject': '[KHW 403] Segment 3 · ↑ Böen: 50 km/h→80 km/h',
        'telegram': '<b>KHW 403 · Segment 3 · ↑ Böen</b>\nBöen · Schwelle 20 km/h · 50 km/h ↑ 80 km/h · Änderung über\nSegment 3 · stärkste Stunde 16:00\nStand: heute 10:00 · verglichen mit dem letzten Briefing',
        'email_plain': 'Böen 50 km/h → 80 km/h seit dem Briefing\n\n↑ Änderung über deiner Alarm-Schwelle (20 km/h)\n\nBöen · km/h: 50 km/h ↑ 80 km/h\nÄnderung 30 km/h: über Alarm-Schwelle 20 km/h ✗\nWo & wann: Segment 3 · stärkste Stunde 16:00\n\nStand: heute 10:00 · verglichen mit dem letzten Briefing\n\nAbweichungs-Alarm · Open-Meteo',
        'sms': 'Seg 3: G50->80@16',
    },
    ('trip_delta_multi', 'de'): {
        'subject': '[KHW 403] Segment 3–4 · ↑ 2 über Schwelle: Böen 80 km/h, Böen 80 km/h',
        'telegram': '<b>KHW 403 · Segment 3–4 · 2 über Schwelle</b>\nBöen Segment 3 · stärkste Stunde 16:00 50→80 km/h · Böen Segment 4 · stärkste Stunde 16:00 50→80 km/h\nStand: heute 10:00 · verglichen mit dem letzten Briefing',
        'email_plain': '2 Werte über der Alarm-Schwelle\n\n↑ 2 über Schwelle\n\nBöen · Segment 3 · stärkste Stunde 16:00 · Änderung 30 · Schwelle 20: 50 ↑ 80 km/h über\nBöen · Segment 4 · stärkste Stunde 16:00 · Änderung 30 · Schwelle 20: 50 ↑ 80 km/h über\n\nStand: heute 10:00 · verglichen mit dem letzten Briefing · Segment 3–4\n\nAbweichungs-Alarm · Open-Meteo',
        'sms': 'Seg 3-4: G50->80@16 G50->80@16',
    },
    ('trip_delta_onset', 'de'): {
        'subject': '[KHW 403] Segment 3 · ↑ Böen: 50 km/h→80 km/h',
        'telegram': '<b>KHW 403 · Segment 3 · ↑ Böen</b>\nBöen · Schwelle 20 km/h · 50 km/h ↑ 80 km/h · Änderung über\nSegment 3 · stärkste Stunde 16:00\nGewitter-Beginn: 14:00 → 12:00 (2 h früher · Segment 3)\nStand: heute 10:00 · verglichen mit dem letzten Briefing',
        'email_plain': 'Böen 50 km/h → 80 km/h seit dem Briefing\n\n↑ Änderung über deiner Alarm-Schwelle (20 km/h)\n\nBöen · km/h: 50 km/h ↑ 80 km/h\nÄnderung 30 km/h: über Alarm-Schwelle 20 km/h ✗\nWo & wann: Segment 3 · stärkste Stunde 16:00\n\nGewitter-Beginn: 14:00 → 12:00 (2 h früher · Segment 3)\n\nStand: heute 10:00 · verglichen mit dem letzten Briefing\n\nAbweichungs-Alarm · Open-Meteo',
        'sms': 'Seg 3: G50->80@16 TH12:00 2 h früher',
    },
    ('trip_radar', 'de'): {
        'subject': '[KHW 403] Segment 3 · Gewitter in 8 Min',
        'telegram': '<b>KHW 403 · Segment 3 · Gewitter in 8 Min</b>\n14:08 · kraeftiger Regen · Radar (GeoSphere INCA)',
        'email_plain': 'Gewitter in 8 Min\n\nRadar-Nowcast\n\nWo & wann: Segment 3 · ab 14:08\nIntensität: kraeftiger Regen\nQuelle: Radar (GeoSphere INCA)\nBriefing: nicht angekuendigt\n\nStand: heute 10:00\nCooldown: Du erhältst diese Warnung höchstens einmal in 60 Min. Bei Meldungen aus anderen Quellen (amtliche Warnung/Radar) greift dieser Cooldown nicht.\n\nRegen-/Gewitter-Alarm · Radar (GeoSphere INCA)',
        'sms': 'Seg 3: TH@14:08',
    },
    ('trip_delta', 'en'): {
        'subject': '[KHW 403] Segment 3 · ↑ Gusts: 50 km/h→80 km/h',
        'telegram': '<b>KHW 403 · Segment 3 · ↑ Gusts</b>\nGusts · Threshold 20 km/h · 50 km/h ↑ 80 km/h · Change above\nSegment 3 · peak hour 16:00\nAs of today 10:00 · compared with the last briefing',
        'email_plain': 'Gusts 50 km/h → 80 km/h since the briefing\n\n↑ Change above your alert threshold (20 km/h)\n\nGusts · km/h: 50 km/h ↑ 80 km/h\nChange 30 km/h: above alert threshold 20 km/h ✗\nWhere & when: Segment 3 · peak hour 16:00\n\nAs of today 10:00 · compared with the last briefing\n\nDeviation alert · Open-Meteo',
        'sms': 'Seg 3: G50->80@16',
    },
    ('trip_delta_multi', 'en'): {
        'subject': '[KHW 403] Segment 3–4 · ↑ 2 over threshold: Gusts 80 km/h, Gusts 80 km/h',
        'telegram': '<b>KHW 403 · Segment 3–4 · 2 over threshold</b>\nGusts Segment 3 · peak hour 16:00 50→80 km/h · Gusts Segment 4 · peak hour 16:00 50→80 km/h\nAs of today 10:00 · compared with the last briefing',
        'email_plain': '2 values above the alert threshold\n\n↑ 2 over threshold\n\nGusts · Segment 3 · peak hour 16:00 · Change 30 · Threshold 20: 50 ↑ 80 km/h above\nGusts · Segment 4 · peak hour 16:00 · Change 30 · Threshold 20: 50 ↑ 80 km/h above\n\nAs of today 10:00 · compared with the last briefing · Segment 3–4\n\nDeviation alert · Open-Meteo',
        'sms': 'Seg 3-4: G50->80@16 G50->80@16',
    },
    ('trip_delta_onset', 'en'): {
        'subject': '[KHW 403] Segment 3 · ↑ Gusts: 50 km/h→80 km/h',
        'telegram': '<b>KHW 403 · Segment 3 · ↑ Gusts</b>\nGusts · Threshold 20 km/h · 50 km/h ↑ 80 km/h · Change above\nSegment 3 · peak hour 16:00\nThunder onset: 14:00 → 12:00 (2 h earlier · Segment 3)\nAs of today 10:00 · compared with the last briefing',
        'email_plain': 'Gusts 50 km/h → 80 km/h since the briefing\n\n↑ Change above your alert threshold (20 km/h)\n\nGusts · km/h: 50 km/h ↑ 80 km/h\nChange 30 km/h: above alert threshold 20 km/h ✗\nWhere & when: Segment 3 · peak hour 16:00\n\nThunder onset: 14:00 → 12:00 (2 h earlier · Segment 3)\n\nAs of today 10:00 · compared with the last briefing\n\nDeviation alert · Open-Meteo',
        'sms': 'Seg 3: G50->80@16 TH12:00 2 h früher',
    },
    ('trip_radar', 'en'): {
        'subject': '[KHW 403] Segment 3 · Thunderstorm in 8 min',
        'telegram': '<b>KHW 403 · Segment 3 · Thunderstorm in 8 min</b>\n14:08 · kraeftiger Regen · Radar (GeoSphere INCA)',
        'email_plain': 'Thunderstorm in 8 min\n\nRadar nowcast\n\nWhere & when: Segment 3 · from 14:08\nIntensity: kraeftiger Regen\nSource: Radar (GeoSphere INCA)\nBriefing: nicht angekuendigt\n\nAs of today 10:00\nCooldown: you receive this alert at most once in 60 Min. Alerts from other sources (official warning/radar) are not affected by this cooldown.\n\nRain/thunderstorm alert (radar) · Radar (GeoSphere INCA)',
        'sms': 'Seg 3: TH@14:08',
    },
}


def _trip_nachricht(fall: str):
    from output.renderers.alert.project import to_alert_message

    from tests.tdd.test_alert_location_vocabulary import (
        TRIP_NAME, TRIP_TZ, _change, _delta_message, _onset_message, _segment,
    )

    if fall == "trip_delta":
        return _delta_message([("3", 10.0, 14.0)])
    if fall == "trip_delta_multi":
        return _delta_message([("3", 10.0, 14.0), ("4", 14.0, 19.0)])
    if fall == "trip_delta_onset":
        return to_alert_message(
            [_change("3"), _gewitter_beginn_frueher("3")], [_segment("3", 10.0, 14.0)],
            TRIP_NAME, tz=TRIP_TZ, stand_at="10:00", ampel=resolve_ampel(None),
        )
    return _onset_message(segment_id="3", km_from=10.0, km_to=14.0)


@pytest.mark.parametrize("fall,lang", list(TRIP_REFERENZ))
def test_ac9_trip_alarme_bleiben_byte_identisch(fall, lang):
    """AC-9 (Invariante, heute gruen): Trip-Alarme (Änderung, Mehr-Etappen,
    Beginn-Verschiebung, Radar) sind nach dem Fix byte-identisch."""
    from output.renderers.alert.render import (
        render_email, render_sms, render_subject, render_telegram,
    )

    msg = _trip_nachricht(fall)
    got = {
        "subject": render_subject(msg, lang=lang),
        "telegram": render_telegram(msg, lang=lang),
        "email_plain": render_email(msg, lang=lang)[1],
        "sms": render_sms(msg),
    }
    assert got == TRIP_REFERENZ[(fall, lang)]


# Fixture `env` (isolierter Daten-Root, echte Nutzerkennung) fuer die Vorschau.
from tests.helpers.vorschau_umgebung import env  # noqa: E402,F401
