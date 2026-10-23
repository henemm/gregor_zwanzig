"""Die Stub-Server der ``AlarmPruefstrecke`` ueberleben ihren Test nicht.

CI-Befund 2026-10-22 (jobs 120076448426/120076736399/120085163950): der
Thread-Dump von pytest-timeout zeigte >= 56 lebende ``serve_forever``-Threads
der Telegram-/seven.io-Stubs. Leerlaufende Stub-Threads auf unbrauchbaren
Sockets fressen den GIL -- ein CPU-gebundener Repo-Scan lief damit 4x
langsamer (3,4 s -> 13 s gemessen) und im CI in die 30-s-Schranke.
"""
from __future__ import annotations

import socket

from tests.helpers.alarm_pruefstrecke import (
    _OFFENE_SERVER, AlarmPruefstrecke, lebende_stub_threads, offene_server_beenden,
)
from tests.helpers.alert_log_fixtures import settings_email_only

_ZUSTAND: dict[str, int] = {}


def _port_antwortet(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def test_beenden_stoppt_threads_und_schliesst_die_ports():
    vorher = lebende_stub_threads()
    AlarmPruefstrecke(user_id="gz-stub-aufraeumen-direkt", settings=settings_email_only())
    assert lebende_stub_threads() == vorher + 2, "Testvoraussetzung: zwei Stubs laufen"
    ports = [server.server_address[1] for server, _ in _OFFENE_SERVER]
    assert ports and all(_port_antwortet(p) for p in ports), "Testvoraussetzung: Stubs erreichbar"

    beendet = offene_server_beenden()

    assert beendet >= 2
    assert lebende_stub_threads() == 0
    assert not any(_port_antwortet(p) for p in ports), "Ports muessen frei sein"
    assert _OFFENE_SERVER == []


def test_a_pruefstrecke_laesst_ihre_stubs_laufen():
    """Erster Teil des Fixture-Nachweises: der Test selbst raeumt NICHT auf."""
    _ZUSTAND["vorher"] = lebende_stub_threads()
    AlarmPruefstrecke(user_id="gz-stub-aufraeumen-fixture", settings=settings_email_only())
    assert lebende_stub_threads() == _ZUSTAND["vorher"] + 2


def test_b_nach_dem_test_sind_die_stubs_weg():
    """Zweiter Teil: ``_pruefstrecken_server_beenden`` (tests/conftest.py) hat
    aufgeraeumt -- sonst lebten hier noch die zwei Threads des Vorgaengers."""
    assert lebende_stub_threads() == 0
    assert _OFFENE_SERVER == []


def test_mehrere_pruefstrecken_in_einem_test_werden_alle_beendet():
    anzahl = 3
    for i in range(anzahl):
        AlarmPruefstrecke(user_id=f"gz-stub-aufraeumen-{i}", settings=settings_email_only())
    assert lebende_stub_threads() == 2 * anzahl
    assert offene_server_beenden() == 2 * anzahl
    assert lebende_stub_threads() == 0
