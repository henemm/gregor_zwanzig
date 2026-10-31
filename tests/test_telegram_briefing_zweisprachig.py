"""Telegram-Briefing zweisprachig de/en (Issue #2669, i18n P7, Epic #2644).

SPEC: docs/specs/modules/i18n_p7_telegram_2669.md (AC-1, AC-3..AC-6, AC-8..AC-10,
AC-12). Echter Renderer ``render_telegram_bubbles`` auf der Golden-Fixture,
echter Katalog, echte ``user.json`` je Nutzer -- kein Mock.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest

from app import loader
from i18n import resolve_user_lang, t, tn
from output.renderers.narrow import _outlook_lines, render_telegram_incomplete_hint
from services.trip_command_processor import ACTIONS_BUBBLE_BUTTONS
from tests.helpers.telegram_briefing_fixture import (
    BUBBLE_SEP, build_bubbles, build_texts, golden_path,
)

MESSAGES = Path(__file__).resolve().parents[1] / "src" / "i18n" / "messages"


def _katalog(lang: str) -> dict[str, str]:
    return json.loads((MESSAGES / lang / "telegram.json").read_text(encoding="utf-8"))


def _golden_de() -> list[str]:
    return golden_path("de").read_text(encoding="utf-8")[:-1].split(BUBBLE_SEP)


def _bubble(texts: list[str], kopf: str) -> str:
    treffer = [b for b in texts if b.split("\n", 1)[0] == kopf]
    assert len(treffer) == 1, (kopf, texts)
    return treffer[0]


def _warn_index(texts: list[str]) -> int:
    return next(i for i, b in enumerate(texts) if b.startswith("<b>"))


# --- AC-1 ------------------------------------------------------------------

def test_ac1_englische_ueberschriften_fusszeile_vortag_und_praefix():
    texts = build_texts(lang="en")
    for key in ("telegram.kopf.zusammenfassung", "telegram.kopf.ausblick",
                "telegram.kopf.aktionen"):
        _bubble(texts, t(key, "en"))
    # Prosa-Zeilen werden bei 56 Zeichen am Wort umbrochen (_TG_PROSE_WIDTH)
    ueber = _bubble(texts, t("telegram.kopf.zusammenfassung", "en")).replace("\n", " ")
    fuss = " · ".join([
        t("telegram.fuss.luftmasse", "en", wort="leicht"),
        t("telegram.fuss.sicht", "en", wort=t("telegram.fuss.sicht_gut", "en")),
        t("telegram.fuss.nullgradgrenze", "en", hoehe=2800),
    ])
    assert fuss == "Air mass leicht · Visibility good · Freezing level 2800 m"
    assert fuss in ueber
    vortag = t("telegram.vortag.zeile", "en", liste=", ".join([
        f"{t('telegram.vortag.label_boeen', 'en')} +12.0km/h",
        f"{t('telegram.vortag.label_regen', 'en')} +3.5mm",
        f"{t('telegram.vortag.label_gewitter', 'en')} +1.0",
    ]))
    assert vortag == "vs. yesterday: Gusts +12.0km/h, Rain +3.5mm, Thunderstorm +1.0"
    assert vortag in ueber
    assert texts[_warn_index(texts)].startswith("<b>Official warning · ")
    assert t("telegram.segment.ziel", "en") + " · 8.4–14.2 km" in "\n".join(texts)


def _deutsche_fragmente() -> set[str]:
    de, en = _katalog("de"), _katalog("en")
    frags: set[str] = set()
    for key, wert in de.items():
        for teil in re.split(r"\{[a-z_]+\}", wert):
            teil = teil.strip(" :—⚠️.")
            if len(teil) >= 3 and teil not in en[key]:
                frags.add(teil)
    return frags


def test_ac1_kein_deutsches_katalogwort_in_den_englischen_bubbles():
    texts = build_texts(lang="en")
    # Die Warnungs-Bubble ist bis auf das Praefix P6-Rahmen (AC-5).
    del texts[_warn_index(texts)]
    frags = _deutsche_fragmente()
    assert frags, "Katalog telegram.* ist leer"
    joined = "\n".join(texts)
    assert [f for f in sorted(frags) if f in joined] == []


# --- AC-3 / AC-12 -----------------------------------------------------------

def test_ac3_kuerzel_zahlen_und_tabellen_identisch_zu_deutsch():
    de, en = build_texts(lang="de"), build_texts(lang="en")
    assert len(de) == len(en)
    ue_de = _bubble(de, "Kurzübersicht").split("\n")
    ue_en = _bubble(en, "Summary").split("\n")
    # Metrik-Zeilen {Kuerzel} {Min}-{Max}@{Stunde} bis zur Leerzeile
    ende = ue_de.index("")
    assert ue_de[1:ende] == ue_en[1:ende]
    assert any(re.fullmatch(r"\S+ [\d.]+-[\d.]+@\d\d", z) for z in ue_en[1:ende])
    for b_de, b_en in zip(de, en):
        if "<pre>" in b_de:
            assert b_de.split("<pre>", 1)[1] == b_en.split("<pre>", 1)[1]


def test_ac3_ac12_aktionen_buttons_unveraendert():
    for lang in ("de", "en"):
        letzte = build_bubbles(lang=lang)[-1]
        assert letzte.text == t("telegram.kopf.aktionen", lang)
        assert letzte.reply_markup == ACTIONS_BUBBLE_BUTTONS


# --- AC-4 -------------------------------------------------------------------

@pytest.mark.parametrize("n, soll", [
    (1, "⚠️ Briefing incomplete — 1 part of the briefing did not arrive. "
        "Please request the briefing again shortly."),
    (3, "⚠️ Briefing incomplete — 3 parts of the briefing did not arrive. "
        "Please request the briefing again shortly."),
])
def test_ac4_hinweis_unvollstaendig_englisch_plural(n, soll):
    assert render_telegram_incomplete_hint(n, lang="en") == soll
    assert tn("telegram.hinweis.unvollstaendig", n, "en") == soll


@pytest.mark.parametrize("n, soll", [
    (1, "⚠️ Briefing unvollständig — 1 Teil des Briefings ist nicht angekommen. "
        "Bitte fordere das Briefing gleich noch einmal an."),
    (3, "⚠️ Briefing unvollständig — 3 Teile des Briefings sind nicht angekommen. "
        "Bitte fordere das Briefing gleich noch einmal an."),
])
def test_ac4_hinweis_unvollstaendig_deutsch_byte_gleich(n, soll):
    assert render_telegram_incomplete_hint(n) == soll
    assert render_telegram_incomplete_hint(n, lang="de") == soll


# --- AC-5 -------------------------------------------------------------------

def test_ac5_warnung_praefix_englisch_eigennamen_unveraendert():
    texts = build_texts(lang="en")
    warn = texts[_warn_index(texts)]
    assert warn.startswith(f"<b>{t('telegram.warnung.praefix', 'en')} · ")
    assert "ORANGE" in warn
    assert "MeteoAlarm" in warn
    de_warn = _golden_de()[_warn_index(_golden_de())]
    # Eigennamen unveraendert: Umfang (Segment-Bezug) und Behoerde (letzte Zeile);
    # den Rahmen dazwischen uebersetzt P6 (#2668).
    assert warn.split(" · ")[1] == de_warn.split(" · ")[1]
    assert warn.splitlines()[-1] == de_warn.splitlines()[-1]


def test_ac5_englischer_rahmen_aus_p6():
    texts = build_texts(lang="en")
    warn = texts[_warn_index(texts)]
    assert f"{t('warnung.kopf.warnstufe', 'en')} {t('warnung.stufe.orange', 'en')} (2/3)" in warn
    assert t("warnung.gefahr.thunderstorm", "en") in warn


# --- AC-6 -------------------------------------------------------------------

def test_ac6_kein_zustand_zwischen_aufrufen():
    erst_en = build_texts(lang="en")
    dann_de = build_texts(lang="de")
    wieder_en = build_texts(lang="en")
    assert dann_de == _golden_de()
    assert wieder_en == erst_en
    assert erst_en != dann_de


# --- AC-8 -------------------------------------------------------------------

def _stage(d: date) -> dict:
    return {"weekday": "XX", "date": d, "temp_lo": 5.0, "temp_hi": 15.0,
            "precip_mm": 0.0, "wind_dir": "NW", "wind_kmh": 20.0, "thunder": "NONE"}


@pytest.mark.parametrize("lang, kopf, datum", [
    ("de", "Ausblick", "Do 30.10."), ("en", "Outlook", "Thu 30 Oct"),
])
def test_ac8_ausblick_datum_aus_i18n_kern(lang, kopf, datum):
    zeilen = _outlook_lines([_stage(date(2025, 10, 30))], lang=lang)
    assert zeilen[0] == kopf
    assert zeilen[1] == f"{datum}  5.0/15.0°C  R–  NW20.0  ⚡–"


def test_ac8_ausblick_in_der_englischen_briefing_bubble():
    texts = build_texts(lang="en")
    assert _bubble(texts, "Outlook").split("\n")[1].startswith("Fri 30 Oct  ")


# --- AC-9 -------------------------------------------------------------------

def test_ac9_schluesselparitaet_telegram_katalog():
    de, en = _katalog("de"), _katalog("en")
    assert set(de) == set(en)
    assert all(k.startswith("telegram.") for k in de)
    assert {"telegram.hinweis.unvollstaendig.one",
            "telegram.hinweis.unvollstaendig.other"} <= set(de)
    assert [k for k in de if not de[k].strip() or not en[k].strip()] == []


# --- AC-10 ------------------------------------------------------------------

@pytest.fixture
def zwei_nutzer(tmp_path, monkeypatch):
    daten = tmp_path / "data"
    for uid, lang in (("nutzer-a", "en"), ("nutzer-b", "de"), ("default", "en")):
        ordner = daten / "users" / uid
        ordner.mkdir(parents=True)
        (ordner / "user.json").write_text(json.dumps({"language": lang}), encoding="utf-8")
    monkeypatch.setattr(loader, "_DATA_ROOT", str(daten))


def _briefing(uid: str) -> list[str]:
    return build_texts(trip_name=f"Trip {uid}", lang=resolve_user_lang(uid))


def test_ac10_zwei_nutzer_je_eigene_sprache_in_beiden_reihenfolgen(zwei_nutzer):
    for reihenfolge in (("nutzer-a", "nutzer-b"), ("nutzer-b", "nutzer-a")):
        out = {uid: _briefing(uid) for uid in reihenfolge}
        a, b = "\n".join(out["nutzer-a"]), "\n".join(out["nutzer-b"])
        assert "Summary" in a and "Kurzübersicht" not in a
        assert "Kurzübersicht" in b and "Summary" not in b
        assert "Trip nutzer-a" in a and "nutzer-b" not in a
        assert "Trip nutzer-b" in b and "nutzer-a" not in b
        assert out["nutzer-b"][1:] == _golden_de()[1:]


def test_ac10_ohne_user_id_kein_rueckfall_auf_default_nutzer(zwei_nutzer):
    # "default" hat en -- ein leerer/fehlender Kontext darf diese Daten nie lesen.
    for kaputt in ("", None):
        assert resolve_user_lang(kaputt) == "de"
    assert "Kurzübersicht" in "\n".join(build_texts(lang=resolve_user_lang("")))


# --- Fix-Loop Adversary F001-F003 ------------------------------------------

@pytest.mark.parametrize("lang, soll", [("de", "Seg 2: keine Daten"), ("en", "Seg 2: no data")])
def test_f001_segment_ohne_daten_in_nutzersprache(lang, soll):
    texts = build_texts(lang=lang, error_segment=True)
    assert soll in texts
    assert t("telegram.segment.keine_daten", lang, id=2) == soll


def _stage_mit_stundenwerten() -> dict:
    from output.tokens.dto import HourlyValue
    return {"weekday": "Di", "temp_lo": 12, "temp_hi": 15, "precip_mm": 6.0,
            "wind_dir": "W", "wind_kmh": 45, "thunder": "NONE", "note": None,
            "hourly_precip": (HourlyValue(hour=10, value=0.6), HourlyValue(hour=15, value=6.0)),
            "hourly_wind": (HourlyValue(hour=9, value=35.0), HourlyValue(hour=14, value=45.0)),
            "hourly_gust": (), "hourly_thunder": ()}


def test_f002_legacy_ausblick_protokoll_kuerzel_r_w_sprachgleich():
    zeile = "Di  12/15°C  R0.6@10(6.0@15)  W35@9(45@14)  ⚡–"
    for lang, kopf in (("de", "Ausblick"), ("en", "Outlook")):
        assert _outlook_lines([_stage_mit_stundenwerten()], None, lang=lang) == [kopf, zeile]


@pytest.mark.parametrize("lang", ["de", "en"])
def test_f003_ausblick_zustand_ohne_trend_traegt_kopf_in_nutzersprache(lang):
    from app.models import OutlookState

    texts = build_texts(lang=lang, multi_day_trend=None,
                        outlook_state=OutlookState.UNAVAILABLE)
    ausblick = texts[-2]
    assert ausblick.split("\n", 1)[0] == t("telegram.kopf.ausblick", lang)
    assert ausblick.split("\n", 1)[0] == {"de": "Ausblick", "en": "Outlook"}[lang]
