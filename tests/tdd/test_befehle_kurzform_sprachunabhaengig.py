"""Kurzform (Premium-SMS, Telegram-Kurzstil) ist in jeder Kontosprache gleich
(Issue #2673, PO-Vorgabe: SMS, Premium-SMS und Telegram-Kurzform bleiben in
JEDER Sprache exakt wie bisher).

SPEC: docs/specs/modules/i18n_p10_inbound_2673.md AC-3, AC-4.

Echter Premium-SMS-Eingang (``poll_and_process`` -> ``_verarbeite_befehl``,
Journal/Lern-Endpunkt/seven.io am Recorder) und echter Telegram-Webhook.
Vergleich mit ``tests/golden/inbound/kurz_*.en.txt`` (vor der Umstellung
erzeugt). Feste Uhr 2026-10-29T04:00Z.
"""
from __future__ import annotations

import re

import pytest
from freezegun import freeze_time

from tests.helpers.inbound_sprache_fixture import (
    FEST, _nutzer, email_texte, golden_pfad, nutzer_anlegen, telegram_texte,
    trip_anlegen, vergleich_anlegen,
)
from tests.tdd._befehl_e2e_fixtures import (
    _first_non_gsm7_char, basis_settings, install_transport_fakes, sende_premium_sms,
    sms_segments,
)

SIGNALWORT = re.compile(r"[äöüÄÖÜß]|\b(nicht|bitte|keine|Befehl|Etappe|Verfügbar|Hilfe)\b")


@pytest.fixture
def netz(monkeypatch):
    return install_transport_fakes(monkeypatch)


def _abschnitt(datei: str, name: str) -> str:
    text = golden_pfad(datei, "en").read_text(encoding="utf-8")
    teile = re.split(r"^----- (\S+) -----\n", text, flags=re.M)
    return dict(zip(teile[1::2], teile[2::2]))[name].removesuffix("\n")


def _rumpf(golden: str) -> str:
    """Premium-SMS uebertraegt nur den Rumpf (der Betreff entfaellt)."""
    return golden.split("\n\n", 1)[1] if golden.startswith("[") else golden


_SMS_FAELLE = (
    ("HELP", lambda: golden_pfad("kurz_hilfe", "en").read_text(encoding="utf-8")),
    ("CODES", lambda: golden_pfad("kurz_codes", "en").read_text(encoding="utf-8")),
    ("STATUS", lambda: golden_pfad("kurz_status", "en").read_text(encoding="utf-8")),
    ("Hilfen", lambda: golden_pfad("kurz_unbekannt", "en").read_text(encoding="utf-8")),
    ("TOMORROW", lambda: _abschnitt("kurz_weitere", "morgen")),
    ("PAUSE", lambda: _abschnitt("kurz_weitere", "mehrdeutig")),
)


def _premium_antwort(netz, uid: str, text: str) -> str:
    vorher = len(netz.premium_sms_out)
    sende_premium_sms(basis_settings(), netz, _nutzer(uid), text)
    neu = netz.premium_sms_out[vorher:]
    assert len(neu) == 1, neu
    return neu[0]["text"]


def _lage(uid: str, lang: str | None, *, vergleiche: bool = False) -> None:
    """Trip; mit ``vergleiche`` zusaetzlich zwei aktive Ortsvergleiche
    (Mehrdeutigkeit fuer Trip-und-Vergleich-Befehle wie PAUSE)."""
    nutzer_anlegen(uid, lang)
    trip_anlegen(uid)
    if vergleiche:
        vergleich_anlegen(uid)
        vergleich_anlegen(uid, "Zweiter Vergleich", nr=2)


# ------------------------------------------------------------------ AC-3


@freeze_time(FEST)
@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("text,golden", _SMS_FAELLE, ids=[f[0] for f in _SMS_FAELLE])
def test_ac3_ac4_premium_sms_antwort_byte_gleich_zur_kurzform(netz, lang, text, golden):
    uid = f"p10-kurz-{lang}-{text.lower()}"
    _lage(uid, lang, vergleiche=text == "PAUSE")
    antwort = _premium_antwort(netz, uid, text)
    assert antwort == _rumpf(golden())
    assert _first_non_gsm7_char(antwort) is None, antwort
    assert sms_segments(antwort) <= 3 or text in ("HELP", "CODES"), antwort
    assert not SIGNALWORT.search(antwort.replace("Golden", "")), antwort


# ------------------------------------------------------------------ AC-4


# Ein unbekanntes Wort hat am Telegram-Eingang kein Ziel und damit keinen
# Kurzstil (#2417 AC-19) -- es folgt der Kontosprache (AC-7), nicht hier.
_TG_KURZ = ("STATUS", "GEWITTER", "RUHETAG 2", "/th", "temp")


@freeze_time(FEST)
@pytest.mark.parametrize("text", _TG_KURZ)
def test_ac4_telegram_kurzstil_fuer_de_und_en_identisch(netz, text):
    antworten, knoepfe = {}, {}
    for lang in ("de", "en"):
        uid = f"p10-tgkurz-{lang}-{_TG_KURZ.index(text)}"
        nutzer_anlegen(uid, lang)
        trip_anlegen(uid, stil="kurzform")
        vorher = len(netz.telegram_inhalte())
        antworten[lang] = telegram_texte(netz, basis_settings(), uid, text)
        knoepfe[lang] = [e["payload"].get("reply_markup")
                         for e in netz.telegram_inhalte()[vorher:]]
    assert antworten["de"] == antworten["en"], antworten
    # auch die Knopf-Beschriftungen bleiben im Kurzstil wie bisher
    assert knoepfe["de"] == knoepfe["en"], knoepfe
    if text == "STATUS":
        assert "Stage 2: Stubai - Neustift" in antworten["de"][0]
        assert "29.10.2026 - Stage 2" in antworten["de"][0]


@freeze_time(FEST)
def test_ac4_kuerzel_bedeutung_englisch_und_positivkontrolle_email(netz):
    from app.metric_catalog import get_metric

    antworten = {}
    for lang in ("de", "en"):
        uid = f"p10-codes-{lang}"
        _lage(uid, lang)
        antworten[lang] = (_premium_antwort(netz, uid, "CODES"),
                           email_texte(netz, basis_settings(), uid, "STATUS")[0])
    assert antworten["de"][0] == antworten["en"][0]
    bedeutung = get_metric("humidity").kuerzel_bedeutung_en["HU"]
    assert f"HU {bedeutung}" in antworten["de"][0]
    # Positivkontrolle: dieselbe Nachricht per E-Mail unterscheidet sich.
    assert antworten["de"][1] != antworten["en"][1]
    assert "Etappe 2" in antworten["de"][1] and "Stage 2" in antworten["en"][1]
