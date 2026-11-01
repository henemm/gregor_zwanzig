"""Zwei Nutzer, derselbe Befehl, je eigene Sprache (Issue #2673, AC-6).

SPEC: docs/specs/modules/i18n_p10_inbound_2673.md AC-6, Querschnitts-
Pruefpunkt Mandantentrennung: ``resolve_user_lang(msg.user_id)`` je Nachricht,
keine Modul- oder Prozess-globale Sprache, kein Rueckfall auf ``"default"``.

Ein Prozess, echte Eingaenge (E-Mail und Telegram), Nachrichten von A (de),
B (en) und C (ohne Feld) verschachtelt hintereinander. Jede Aenderung trifft
nur den eigenen Trip. Feste Uhr 2026-10-29T04:00Z.
"""
from __future__ import annotations

from datetime import date

import pytest
from freezegun import freeze_time

from tests.helpers.inbound_sprache_fixture import (
    FEST, JETZT, TRIP_NAME, email_texte, nutzer_anlegen, telegram_texte, trip_anlegen,
)
from tests.tdd._befehl_e2e_fixtures import basis_settings, install_transport_fakes

VERSCHOBEN = [date(2026, 10, 28), date(2026, 10, 29), date(2026, 11, 2)]
UNVERAENDERT = [date(2026, 10, 28), date(2026, 10, 29), date(2026, 10, 31)]


@pytest.fixture
def netz(monkeypatch):
    return install_transport_fakes(monkeypatch)


def _stages(uid: str) -> list[date]:
    from app.loader import load_all_trips

    (trip,) = load_all_trips(uid)
    return [s.date for s in trip.stages]


@freeze_time(FEST)
def test_ac6_verschachtelt_jeder_nutzer_in_seiner_sprache_nur_eigener_trip(netz):
    s = basis_settings()
    for uid, lang in (("p10-ac6-a", "de"), ("p10-ac6-b", "en"), ("p10-ac6-c", None)):
        nutzer_anlegen(uid, lang)
        trip_anlegen(uid)

    (a1,) = email_texte(netz, s, "p10-ac6-a", "RUHETAG 2")
    assert "Ruhetag eingetragen: +2 Tage." in a1
    assert _stages("p10-ac6-a") == VERSCHOBEN
    assert _stages("p10-ac6-b") == UNVERAENDERT

    (b1,) = telegram_texte(netz, s, "p10-ac6-b", "RUHETAG 2")
    assert "Rest day added: +2 days." in b1 and "Stage 3" in b1, b1
    assert _stages("p10-ac6-b") == VERSCHOBEN
    assert _stages("p10-ac6-c") == UNVERAENDERT

    (a2,) = telegram_texte(netz, s, "p10-ac6-a", "RUHETAG")
    assert "Ruhetag bereits eingetragen" in a2, a2
    (b2,) = email_texte(netz, s, "p10-ac6-b", "RUHETAG")
    assert "Rest day already set" in b2, b2
    (c1,) = telegram_texte(netz, s, "p10-ac6-c", "RUHETAG 2")
    assert "Ruhetag eingetragen: +2 Tage." in c1 and "Etappe 3" in c1, c1
    # Wiederholungen haben nichts ein zweites Mal verschoben.
    assert _stages("p10-ac6-a") == _stages("p10-ac6-b") == _stages("p10-ac6-c") == VERSCHOBEN


@freeze_time(FEST)
def test_ac6_ein_prozessor_objekt_nimmt_die_sprache_je_nachricht(netz):
    """Dieselbe Instanz verarbeitet A, B, A: ``_lang`` wird je ``process()``
    gesetzt, nie vom Vorgaenger geerbt (kein Leck von B zu A)."""
    from services.trip_command_processor import InboundMessage, TripCommandProcessor

    for uid, lang in (("p10-ac6-p-a", "de"), ("p10-ac6-p-b", "en")):
        nutzer_anlegen(uid, lang)
        trip_anlegen(uid)
    proc = TripCommandProcessor()

    def status(uid: str) -> str:
        return proc.process(InboundMessage(
            trip_name=TRIP_NAME, body="STATUS", sender="x", channel="email",
            received_at=JETZT, user_id=uid)).confirmation_body

    assert "Etappe 2" in status("p10-ac6-p-a")
    assert "Stage 2" in status("p10-ac6-p-b")
    assert "Etappe 2" in status("p10-ac6-p-a")
    assert TripCommandProcessor._lang == "de"  # Klassen-Default unberuehrt


@freeze_time(FEST)
def test_ac6_unbekannter_nutzer_faellt_nie_auf_fremde_sprache(netz):
    """Kein Konto-Feld bzw. kein lesbares Konto ergibt ``de`` -- auch direkt
    nach einem englischen Nutzer im selben Prozess."""
    from i18n import resolve_user_lang

    nutzer_anlegen("p10-ac6-en", "en")
    assert resolve_user_lang("p10-ac6-en") == "en"
    assert resolve_user_lang("p10-ac6-gibtsnicht") == "de"
