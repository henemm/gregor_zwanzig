"""Geruest-Beweis fuer das gemeinsame Fundament ``_befehl_e2e_fixtures.py``
(#2417).

Je EIN Fall pro Kanal, der HEUTE schon funktioniert und deshalb GRUEN sein
MUSS -- reine Selbstpruefung des Fundaments, keine der eigentlichen ACs aus
der Spec. Faellt einer dieser Faelle rot, ist das Fundament kaputt, nicht das
Produkt.

SPEC: docs/specs/modules/feat_2417_befehle_e2e_echter_eingang.md
"""
from __future__ import annotations

import email as email_lib

from tests.tdd._befehl_e2e_fixtures import (
    basis_settings,
    install_transport_fakes,
    klicke_telegram_knopf,
    lege_lage_an,
    lege_po_lage_nutzer_an,
    merkmal_fuer,
    sende_email,
    sende_premium_sms,
    sende_telegram_text,
    sms_segments,
    user_ids,
)

__all__ = ["user_ids"]  # pytest muss die importierte Fixture im Modul finden


def test_l2_heute_per_telegram_text_liefert_das_briefing(monkeypatch, user_ids):
    """L2 (1 Trip, 0 Vergleiche): ``heute`` per Telegram-Text loest das volle
    On-Demand-Briefing aus -- HEUTE schon funktionierendes Verhalten."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    settings = basis_settings()

    sende_telegram_text(settings, nutzer, "heute")

    recorder.pruefe_keine_unbekannten_aufrufe()
    inhalte = recorder.telegram_inhalte(nutzer.telegram_chat_id)
    assert inhalte, (
        f"Es wurde ueberhaupt kein Telegram-Inhalt gesendet -- "
        f"Rohaufzeichnung: {recorder.telegram!r}"
    )
    texte = " ".join(e["payload"].get("text", "") for e in inhalte)
    assert nutzer.trip.name in texte, (
        f"Der gesendete Text enthaelt nicht den Trip-Namen {nutzer.trip.name!r}: {texte!r}"
    )
    assert "Unbekannter Befehl" not in texte and "Mehrdeutig" not in texte


def test_hilfe_per_email_reines_text_plain(monkeypatch, user_ids):
    """``hilfe`` per reiner ``text/plain``-Mail (kein Apple-Mail-Sonderfall)
    -- HEUTE schon funktionierendes Verhalten (B2 betrifft nur die
    HTML-only-Form)."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    settings = basis_settings()

    ergebnis = sende_email(settings, nutzer, "hilfe", form="plain")

    recorder.pruefe_keine_unbekannten_aufrufe()
    assert ergebnis == 1, "Die Mail wurde nicht als Befehl verarbeitet."
    assert recorder.emails, f"Es wurde keine Antwortmail versendet: {recorder.emails!r}"
    gesendet = recorder.emails[-1]
    msg = email_lib.message_from_string(gesendet["raw"])
    body = msg.get_payload(decode=True).decode(
        msg.get_content_charset() or "utf-8", errors="replace"
    ) if not msg.is_multipart() else "\n".join(
        p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8", errors="replace")
        for p in msg.walk() if p.get_content_type() == "text/plain"
    )
    for wort in ("HEUTE", "MORGEN", "HILFE"):
        assert wort in body, f"Hilfetext enthaelt nicht {wort!r}: {body!r}"


def test_l2_status_per_premium_sms_ohne_kartenlink(monkeypatch, user_ids):
    """L2, ``status`` per Premium-SMS-Journal-Eingang, OHNE Kartenlink --
    HEUTE schon funktionierendes Verhalten."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    settings = basis_settings()

    gelernt = sende_premium_sms(settings, recorder, nutzer, "status", mit_kartenlink=False)

    recorder.pruefe_keine_unbekannten_aufrufe()
    assert gelernt == 1, "Die Rueckadresse wurde nicht als neu gelernt erkannt."
    assert recorder.premium_sms_out, (
        f"Es wurde keine Premium-SMS versendet: {recorder.premium_sms_out!r}"
    )
    gesendet = recorder.premium_sms_out[-1]
    assert gesendet["to"] == nutzer.premium_sms_reply_to
    assert "Unbekannter Befehl" not in gesendet["text"]
    assert "Mehrdeutig" not in gesendet["text"]


def test_knopf_act_overview_per_echtem_callback_eingang(monkeypatch, user_ids):
    """L2, Knopf ``act_overview`` durch den ECHTEN Callback-Eingang
    (``_process_update`` mit ``callback_query``) -- HEUTE schon
    funktionierendes Verhalten. Regressionsschutz fuer den Fund aus
    red-telegram-2417/Team-Lead (2026-09-25): ein direkter Aufruf von
    ``_process_callback_query`` OHNE vorheriges
    ``_ensure_notification_service()`` krachte mit ``AttributeError``
    (verdeckte AC-8/AC-9-Befunde als falsche Rot-Ursache). ``klicke_
    telegram_knopf`` geht seitdem ueber ``_process_update`` -- dieser Test
    haelt genau das fest."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    settings = basis_settings()

    klicke_telegram_knopf(settings, nutzer, "act_overview", message_id=555)

    recorder.pruefe_keine_unbekannten_aufrufe()
    inhalte = [
        e for e in recorder.telegram
        if e["methode"] in ("sendMessage", "editMessageText")
        and str(e["payload"].get("chat_id")) == str(nutzer.telegram_chat_id)
    ]
    assert inhalte, (
        f"Der Knopf-Klick hat KEINEN sichtbaren Inhalt gesendet (stiller "
        f"No-Op) -- Rohaufzeichnung: {recorder.telegram!r}"
    )
    texte = " ".join(e["payload"].get("text", "") for e in inhalte)
    merkmal = merkmal_fuer("act_overview", nutzer=nutzer)
    merkmale = merkmal if isinstance(merkmal, tuple) else (merkmal,)
    for teil in merkmale:
        assert teil in texte, (
            f"Merkmal {teil!r} fuer act_overview fehlt im gesendeten Text: {texte!r}"
        )
    assert "Unbekannter Befehl" not in texte and "Mehrdeutig" not in texte
    # answerCallbackQuery muss trotzdem gelaufen sein (Spinner-Ende, AC-2
    # der aeltesten Telegram-Spec) -- misslingt das, ist das ein Anzeichen
    # fuer genau den AttributeError-Absturz aus dem Fundament-Fund.
    assert any(e["methode"] == "answerCallbackQuery" for e in recorder.telegram)


def test_sms_segments_bekannte_laengen():
    """``sms_segments`` auf bekannten Laengen (GSM-7 Basis + UCS-2-Fallback)."""
    assert sms_segments("a" * 160) == 1
    assert sms_segments("a" * 161) == 2
    assert sms_segments("a" * 306) == 2
    assert sms_segments("a" * 307) == 3
    # Ein einzelnes UCS-2-erzwingendes Zeichen (nicht im GSM-7-Alphabet, z.B.
    # "ê") kippt die ganze SMS auf 70/67 Zeichen je Teil.
    assert sms_segments("a" * 69 + "ê") == 1
    assert sms_segments("a" * 70 + "ê") == 2
