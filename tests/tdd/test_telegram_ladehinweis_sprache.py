"""TDD RED -- #2417: Der Telegram-Ladehinweis folgt der Kurzform-Sprache.

SPEC: docs/specs/modules/feat_2417_kurzform_englisch.md (Abschnitt H, AC-4/AC-19)
BUG (#2417): ``inbound_telegram_reader.py::_dispatch_and_reply`` sendet die
Lade-Zwischennachricht ("⏳ Wetter wird geladen...") fest deutsch, auch wenn
das aufgeloeste Ziel ``telegram_style == "kurzform"`` fuehrt und die
eigentliche Antwort englisch ist -- Verstoss gegen AC-4/AC-19 ("auf
Kurzform-Kanaelen ist JEDE Antwort englisch").

Alle Tests laufen durch den ECHTEN Telegram-Eingang
(``InboundTelegramReader._process_update`` via ``sende_telegram_text``),
Netzrand ``httpx.post`` durch den Recorder aus ``_befehl_e2e_fixtures``
aufgezeichnet -- kein Mock/patch/MagicMock. Anders als die uebrigen
#2417-Kanaltests wird hier NICHT die gefilterte Antwort (``_antworten`` in
den Geschwister-Testdateien klammert die Lade-Blase ausdruecklich aus)
gemessen, sondern der RAW-Recorder (``recorder.telegram``) -- genau die
Lade-Blase ist der Pruefgegenstand dieser Datei.
"""
from __future__ import annotations

import dataclasses

import pytest

from app.loader import load_all_trips, save_trip
from tests.tdd._befehl_e2e_fixtures import (
    BefehlNutzer,
    basis_settings,
    install_transport_fakes,
    lege_lage_an,
    sende_telegram_text,
    user_ids,
)

__all__ = ["user_ids"]  # pytest muss die importierte Fixture im Modul finden


def _trip_im_stil(nutzer: BefehlNutzer, stil: str | None) -> None:
    """Setzt ``report_config.telegram_style`` per Read-Modify-Write (Vorbild
    ``test_kurzform_befehle_englisch.py::_trip_im_stil``)."""
    if stil is None:
        return
    trip = next(t for t in load_all_trips(nutzer.user_id) if t.id == nutzer.trip.id)
    rc = dataclasses.replace(trip.report_config, telegram_style=stil)
    save_trip(dataclasses.replace(trip, report_config=rc), nutzer.user_id)
    geladen = next(t for t in load_all_trips(nutzer.user_id) if t.id == nutzer.trip.id)
    assert geladen.report_config.telegram_style == stil, (
        "Testaufbau: telegram_style ueberlebt den Speicher-Roundtrip nicht."
    )
    nutzer.trip = geladen


def _lade_nachricht(recorder, chat_id: str) -> dict:
    """Der ERSTE an ``chat_id`` gesendete Telegram-Aufruf -- die Lade-
    Zwischennachricht (Subject "⏳"), UNGEFILTERT (anders als ``_antworten``
    in den Geschwister-Testdateien, die genau diese Blase ausklammert)."""
    treffer = [
        e for e in recorder.telegram
        if str(e["payload"].get("chat_id")) == str(chat_id)
    ]
    assert treffer, f"Kein Telegram-Send an chat_id={chat_id!r} aufgezeichnet."
    erster = treffer[0]
    assert erster["methode"] == "sendMessage", (
        f"Erwartet die Lade-Nachricht als sendMessage, war {erster['methode']!r}."
    )
    return erster


# ===========================================================================
# Test A/B -- Kurzform: die Lade-Nachricht ist englisch, auf BEIDEN Pfaden
# (tomorrow/morgen loescht sie danach -- suppress_email_reply=True; glance
# editiert sie in-place -- der andere Zweig in _dispatch_and_reply)
# ===========================================================================

@pytest.mark.parametrize("befehl", ["tomorrow", "glance"])
def test_ladehinweis_ist_englisch_auf_kurzform(monkeypatch, user_ids, befehl):
    """AC-4/AC-19 GIVEN ein Trip im Telegram-Stil ``kurzform`` WHEN ein
    Wetter-Query-Befehl eintrifft THEN ist die GESENDETE Lade-Nachricht
    englisch ("Loading weather...") statt der fest deutschen Fassung."""
    recorder = install_transport_fakes(monkeypatch)
    settings = basis_settings()
    nutzer = lege_lage_an(user_ids, "L2")
    _trip_im_stil(nutzer, "kurzform")

    sende_telegram_text(settings, nutzer, befehl)

    lade = _lade_nachricht(recorder, nutzer.telegram_chat_id)
    text = lade["payload"].get("text", "")
    assert "Loading weather" in text, (
        f"#2417 AC-4/AC-19 ({befehl!r}): Lade-Nachricht nicht englisch:\n{text!r}"
    )
    assert "Wetter wird geladen" not in text, (
        f"#2417 AC-4/AC-19 ({befehl!r}): Lade-Nachricht traegt noch den fest "
        f"deutschen Text:\n{text!r}"
    )


# ===========================================================================
# Test C -- Gegenprobe: Standard-Stil bleibt deutsch
# ===========================================================================

def test_ladehinweis_bleibt_deutsch_ohne_kurzform(monkeypatch, user_ids):
    """Gegenprobe: Trip OHNE ``telegram_style`` (Standard-Stil "rich") ->
    die Lade-Nachricht bleibt deutsch."""
    recorder = install_transport_fakes(monkeypatch)
    settings = basis_settings()
    nutzer = lege_lage_an(user_ids, "L2")

    sende_telegram_text(settings, nutzer, "morgen")

    lade = _lade_nachricht(recorder, nutzer.telegram_chat_id)
    text = lade["payload"].get("text", "")
    assert "Wetter wird geladen" in text, (
        f"Gegenprobe: Standard-Stil sollte deutsch bleiben:\n{text!r}"
    )
    assert "Loading weather" not in text
