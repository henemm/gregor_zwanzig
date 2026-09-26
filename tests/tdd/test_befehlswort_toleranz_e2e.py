"""TDD RED — Befehlswort-Toleranz (#2417 AC-20).

SPEC: docs/specs/modules/feat_2417_befehle_e2e_echter_eingang.md
FUNDAMENT: tests/tdd/_befehl_e2e_fixtures.py

Ein Befehlswort, das von Satzzeichen, einem BOM, einem Zero-Width-Space oder
geschuetzten Leerzeichen umgeben ist, muss genauso beantwortet werden wie das
nackte Wort -- ueber alle drei Kanaele, durch den echten Eingang. Die
Gegenprobe stellt sicher, dass die Toleranz nicht in beliebiges
Praefix-Matching ausartet (echte Fremdwoerter wie "Hilfen" bleiben unbekannt).

Lagen-Wahl: L2 (1 Trip, 0 Vergleiche) fuer ALLE Faelle dieser Datei -- in der
PO-Lage (L3) beantworten Telegram/Premium-SMS heute JEDES Wort ohne Namen mit
der Mehrdeutigkeits-Rueckfrage (U1, alte AC-4 aus #2282); das wuerde die
Toleranz-Frage selbst verdecken. E-Mail waere davon zwar nicht betroffen,
aber ein einheitliches Setup je Kanal haelt diese Datei einfach.

Pro Testfall werden ZWEI frische Nutzer angelegt (nackte Form + Variante) --
ein mutierender Befehl wie "pause" darf den Zustand der nackten
Referenz-Messung nicht verfaelschen, bevor die Variante gesendet wird.
"""
from __future__ import annotations

import email as email_lib
from typing import Optional

import pytest

from tests.tdd._befehl_e2e_fixtures import (
    FEHLERTEXTE,
    basis_settings,
    install_transport_fakes,
    lege_lage_an,
    merkmal_fuer,
    sende_email,
    sende_premium_sms,
    sende_telegram_text,
    user_ids,
)

__all__ = ["user_ids"]  # pytest muss die importierte Fixture im Modul finden


# ---------------------------------------------------------------------------
# Kanal-Matrix + Sende-/Lese-Helfer (Vorbild test_abruf_jede_metrik_e2e.py)
# ---------------------------------------------------------------------------

CHANNEL_MATRIX = [
    ("telegram", None),
    ("premium_sms", None),
    ("email", "plain"),
    ("email", "alternative_beide"),
    ("email", "apple_html"),
]
CHANNEL_IDS = [
    "telegram", "premium_sms", "email_plain", "email_alternative_beide", "email_apple_html",
]


def _sende(kanal: str, mail_form: Optional[str], settings, recorder, nutzer, text: str) -> None:
    if kanal == "telegram":
        sende_telegram_text(settings, nutzer, text)
    elif kanal == "premium_sms":
        sende_premium_sms(settings, recorder, nutzer, text)
    elif kanal == "email":
        sende_email(settings, nutzer, text, form=mail_form)
    else:
        raise ValueError(kanal)


def _email_text(raw: str) -> str:
    msg = email_lib.message_from_string(raw)
    subject = msg.get("Subject", "")
    if msg.is_multipart():
        teile = [
            p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8", errors="replace")
            for p in msg.walk() if p.get_content_type() == "text/plain"
        ]
    else:
        teile = [
            msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="replace")
        ]
    return subject + "\n" + "\n".join(teile)


def _text(kanal: str, recorder, nutzer) -> str:
    """Gejoint ueber ALLE an ``nutzer`` gerichteten Sends dieses Kanals, nach
    Empfaenger gefiltert -- zwei Nutzer teilen sich in dieser Datei bewusst
    EINEN Recorder (nackte Form + Variante), ohne sich zu verfaelschen."""
    if kanal == "telegram":
        inhalte = recorder.telegram_inhalte(nutzer.telegram_chat_id)
        assert inhalte, f"Kein Telegram-Inhalt gesendet: {recorder.telegram!r}"
        return "\n".join(e["payload"].get("text", "") for e in inhalte)
    if kanal == "premium_sms":
        eintraege = [e for e in recorder.premium_sms_out if e["to"] == nutzer.premium_sms_reply_to]
        assert eintraege, f"Keine Premium-SMS an {nutzer.premium_sms_reply_to} gesendet."
        return "\n".join(e["text"] for e in eintraege)
    if kanal == "email":
        eintraege = [e for e in recorder.emails if nutzer.mail_to in e["to"]]
        assert eintraege, f"Keine Antwortmail an {nutzer.mail_to} gesendet."
        return "\n".join(_email_text(e["raw"]) for e in eintraege)
    raise ValueError(kanal)


def _enthaelt_merkmal(text: str, merkmal) -> bool:
    if isinstance(merkmal, tuple):
        return all(teil in text for teil in merkmal)
    return merkmal in text


def _ist_unbekannt_antwort(text: str) -> bool:
    """Erkennt BEIDE Formen des Unbekannt-Zweigs (``process()``): mit
    Trip-Bezug ("'{key}' ist kein gueltiger Befehl.") und ohne (generisches
    "Befehlsformat: ### key: value"). Premium-SMS sendet KEINEN Betreff --
    dort ist "Unbekannter Befehl" (nur im Subject) nicht sichtbar, wohl aber
    der Body-Text."""
    return (
        "Unbekannter Befehl" in text
        or "Befehlsformat: ### key: value" in text
        or "ist kein gueltiger Befehl" in text
        or "ist kein gültiger Befehl" in text
    )


# ---------------------------------------------------------------------------
# AC-20 — Varianten, die genauso wie die nackte Form beantwortet werden
# ---------------------------------------------------------------------------

#: Mindestens die in der Spec genannten Varianten (Abschnitt AC-20). Die
#: meisten sind Satzzeichen-/Sonderzeichen-Varianten von "hilfe"; "heute" und
#: "pause" pruefen, dass die Toleranz NICHT hilfe-spezifisch implementiert
#: wird.
FAMILIEN: dict[str, list[str]] = {
    "hilfe": [
        "Hilfe.", "HILFE!", "hilfe?", "Hilfe,",
        "﻿Hilfe",       # BOM davor
        "Hilfe​",       # Zero-Width-Space danach
        " Hilfe ",  # geschuetzte Leerzeichen (NBSP)
        "  hilfe  \n",       # Leerraum + Zeilenumbruch
    ],
    "heute": ["Heute."],
    "pause": ["Pause!"],
}

FAELLE = [(fall, variante) for fall, varianten in FAMILIEN.items() for variante in varianten]


def _fall_id(fall_variante) -> str:
    fall, variante = fall_variante
    return f"{fall}_{variante!r}"


@pytest.mark.parametrize("kanal,mail_form", CHANNEL_MATRIX, ids=CHANNEL_IDS)
@pytest.mark.parametrize("fall_variante", FAELLE, ids=_fall_id)
def test_variante_wird_wie_die_nackte_form_beantwortet(monkeypatch, user_ids, kanal, mail_form, fall_variante):
    fall, variante = fall_variante
    recorder = install_transport_fakes(monkeypatch)
    settings = basis_settings()

    # -- Referenz: die nackte Form, EIGENER frischer Nutzer --------------
    nutzer_nackt = lege_lage_an(user_ids, "L2")
    _sende(kanal, mail_form, settings, recorder, nutzer_nackt, fall)
    recorder.pruefe_keine_unbekannten_aufrufe()
    text_nackt = _text(kanal, recorder, nutzer_nackt)
    merkmal_nackt = merkmal_fuer(fall, nutzer=nutzer_nackt, kanal=kanal)
    assert not _ist_unbekannt_antwort(text_nackt), (
        f"Testfundament fehlerhaft, KEIN AC-20-Befund: die nackte Form "
        f"{fall!r} selbst wird schon als unbekannter Befehl behandelt: {text_nackt!r}"
    )
    assert _enthaelt_merkmal(text_nackt, merkmal_nackt), (
        f"Testfundament fehlerhaft, KEIN AC-20-Befund: die nackte Form "
        f"{fall!r} traegt nicht ihr eigenes Merkmal {merkmal_nackt!r}: {text_nackt!r}"
    )

    # -- Pruefling: die Variante, EIGENER frischer Nutzer -----------------
    nutzer_variante = lege_lage_an(user_ids, "L2")
    _sende(kanal, mail_form, settings, recorder, nutzer_variante, variante)
    recorder.pruefe_keine_unbekannten_aufrufe()
    text_variante = _text(kanal, recorder, nutzer_variante)
    merkmal_variante = merkmal_fuer(fall, nutzer=nutzer_variante, kanal=kanal)

    assert not _ist_unbekannt_antwort(text_variante), (
        f"[{kanal}] Variante {variante!r} wird als unbekannter Befehl "
        f"behandelt statt wie {fall!r}: {text_variante!r}"
    )
    for f in FEHLERTEXTE:
        assert f not in text_variante, (
            f"[{kanal}] Variante {variante!r} traegt den Fehlertext {f!r}: {text_variante!r}"
        )
    assert _enthaelt_merkmal(text_variante, merkmal_variante), (
        f"[{kanal}] Variante {variante!r} liefert nicht dasselbe Merkmal wie "
        f"die nackte Form {fall!r} ({merkmal_variante!r}): {text_variante!r}"
    )


# ---------------------------------------------------------------------------
# Gegenprobe — echte Fremdwoerter bleiben unbekannt (keine Praefix-Ausartung)
# ---------------------------------------------------------------------------

GEGENPROBEN = ["Hilfen", "Heutegestern"]


@pytest.mark.parametrize("kanal,mail_form", CHANNEL_MATRIX, ids=CHANNEL_IDS)
@pytest.mark.parametrize("fremdwort", GEGENPROBEN)
def test_fremdwort_bleibt_unbekannt(monkeypatch, user_ids, kanal, mail_form, fremdwort):
    """Gegenprobe zu AC-20: die Toleranz gegenueber Satzzeichen/BOM/ZWSP darf
    NICHT in beliebiges Praefix-Matching ausarten."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    settings = basis_settings()

    _sende(kanal, mail_form, settings, recorder, nutzer, fremdwort)

    recorder.pruefe_keine_unbekannten_aufrufe()
    text = _text(kanal, recorder, nutzer)
    assert _ist_unbekannt_antwort(text), (
        f"[{kanal}] Fremdwort {fremdwort!r} wird faelschlich als Befehl "
        f"erkannt (Praefix-Ausartung der Toleranz): {text!r}"
    )
