"""KUERZEL/CODES-Legende und Telegram-Aktionsknoepfe aus dem Katalog (Issue #2751).

ADR-0104 Nr. 5: die Kurzform-Legende CODES bleibt byte-gleich englisch, KUERZEL
byte-gleich deutsch; die Aktionsknoepfe folgen der Nutzersprache (Telegram
Normalstil), ``callback_data`` bleibt sprachneutral. Echte Funktionen, echter
Katalog, echte ``user.json`` -- kein Mock.
"""
from __future__ import annotations

import json

from i18n import resolve_user_lang
from output.tokens import builder
from output.tokens import hazard_symbols as hz
from services import trip_command_processor as tcp

#: Golden vor #2751 (byte-gleich).
_KNOEPFE_DE = {"inline_keyboard": [
    [{"text": "📋 Übersicht", "callback_data": "act_overview"},
     {"text": "⏸ Pause", "callback_data": "act_pause"}],
    [{"text": "⏭ Überspringen", "callback_data": "act_skip"},
     {"text": "📊 Spalten", "callback_data": "act_columns"}],
    [{"text": "❓ Hilfe", "callback_data": "act_help"}],
]}


def _konto(tmp_path, uid: str, lang: str) -> str:
    ordner = tmp_path / "users" / uid
    ordner.mkdir(parents=True)
    (ordner / "user.json").write_text(json.dumps({"language": lang}), encoding="utf-8")
    return resolve_user_lang(uid, data_dir=tmp_path)


def _texte(markup: dict) -> list[str]:
    return [k["text"] for reihe in markup["inline_keyboard"] for k in reihe]


def _callbacks(markup: dict) -> list[str]:
    return [k["callback_data"] for reihe in markup["inline_keyboard"] for k in reihe]


def test_aktionsknoepfe_folgen_der_kontosprache(tmp_path):
    en = tcp.actions_bubble_buttons(_konto(tmp_path, "knopf-en", "en"))
    de = tcp.actions_bubble_buttons(_konto(tmp_path, "knopf-de", "de"))
    assert _texte(en) == ["📋 Overview", "⏸ Pause", "⏭ Skip", "📊 Columns", "❓ Help"]
    assert de == _KNOEPFE_DE
    assert _callbacks(en) == _callbacks(de)


def test_aktionsknoepfe_konstante_bleibt_deutsch_byte_gleich():
    assert tcp.ACTIONS_BUBBLE_BUTTONS == _KNOEPFE_DE


def test_kuerzel_legende_deutsch_und_codes_englisch_unveraendert():
    de = tcp.codes_text(False).split("\n")
    en = tcp.codes_text(True).split("\n")
    assert de[0] == "Kürzel"
    assert [z.split(":")[0] for z in de[1:]] == ["Wetter", "Weitere", "Format",
                                                "Warnungen nach !"]
    assert [z.split(":")[0] for z in en] == ["Weather", "More", "Format", "Alerts after !"]
    assert "Höchststufe" in de[2] and "über der Schwelle ab 5 Uhr" in de[3]
    assert "top level" in en[1] and "over limit from 5h" in en[2]


def test_bausteine_format_und_warnarten_byte_gleich():
    assert builder.BAUSTEIN_BEDEUTUNG_DE == {
        "Z:": "Brandzonen", "MAX": "Höchststufe", "M:": "Massive",
        "VR:": "Météo-France-Risiko Regen", "VT:": "Météo-France-Risiko Gewitter",
        "X?": "keine Warndaten"}
    assert builder.BAUSTEIN_BEDEUTUNG_EN == {
        "Z:": "fire zones", "MAX": "top level", "M:": "massifs",
        "VR:": "MF rain risk", "VT:": "MF storm risk", "X?": "no data"}
    assert builder.FORMAT_BEDEUTUNG_DE == {
        "E4": "Etappe 4", "23@5": "über der Schwelle ab 5 Uhr", "(24@7)": "Spitze",
        "D13/27": "Tiefst/Höchst", "+HL": "Hagel", "-": "nichts", "?": "keine Daten"}
    assert builder.FORMAT_BEDEUTUNG_EN == {
        "E4": "stage 4", "23@5": "over limit from 5h", "(24@7)": "peak",
        "D13/27": "min/max", "+HL": "hail", "-": "none", "?": "no data"}
    assert hz.HAZARD_BEDEUTUNG_DE["black_ice"] == "Glätte"
    assert hz.HAZARD_BEDEUTUNG_DE["extreme_cold"] == "Kälte"
    assert hz.HAZARD_BEDEUTUNG_EN == {
        "thunderstorm": "storm", "flood": "flood", "rain": "heavy rain",
        "wind_gust": "wind", "snow": "snow", "avalanche": "avalanche",
        "avalanche_bulletin": "avalanche level", "black_ice": "ice",
        "extreme_heat": "heat", "extreme_cold": "cold", "wildfire_risk": "fire",
        "access_ban": "closure"}
    assert list(hz.HAZARD_BEDEUTUNG_DE) == list(hz.HAZARD_SMS_SYMBOLS)
    assert hz.STUFE_BEDEUTUNG_DE == {"L": "niedrig", "M": "mittel", "H": "hoch"}
    assert hz.STUFE_BEDEUTUNG_EN == {"L": "low", "M": "mid", "H": "high"}
