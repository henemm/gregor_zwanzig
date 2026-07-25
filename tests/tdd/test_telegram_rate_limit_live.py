"""Live-Nachweis der Telegram-Sendedrossel gegen die ECHTE Bot-API (Issue #1370).

SPEC: docs/specs/modules/telegram_send_pacing.md, Abschnitt „Test Coverage":

    Echte lange Serie (>=20 Bubbles) gegen den Staging-Test-Chat, die Drossel-
    Bremse tatsaechlich ausloest — bestaetigt, dass alle Teile ankommen und die
    Gesamtlaufzeit innerhalb des 120-Sekunden-Scheduler-Budgets bleibt.

Abgrenzung zu ``test_telegram_rate_limit.py``: dort laeuft alles gegen eine
lokale HTTP-Gegenstelle mit auf Millisekunden geschrumpften Grenzwerten (AC-8).
Hier laufen die PRODUKTIV-Voreinstellungen (18 Schreibzugriffe je 60 s, Deckel
45 s) gegen ``api.telegram.org`` — nur so ist bewiesen, dass die selbst gewaehlte
Schwelle unter der echten Telegram-Grenze liegt und der Zeitplaner-Rahmen haelt.
Die Grenzwerte werden hier BEWUSST nicht veraendert.

Sicherheit: opt-in ueber ``GZ_TELEGRAM_LIVE=1`` (Gate aus
``tests/tdd/_telegram_live_fixture.py``, Issue #1014) und ausschliesslich gegen
den Staging-Test-Chat (``GZ_TELEGRAM_TEST_CHAT_ID``). Jede erzeugte Nachricht
wird am Ende wieder geloescht — auch wenn der Test scheitert.

Ausfuehren (nur im Rahmen der Staging-Pruefung):

    GZ_TELEGRAM_LIVE=1 uv run pytest tests/tdd/test_telegram_rate_limit_live.py -m live -v -s
"""
from __future__ import annotations

import os
import time

import pytest

import output.channels.telegram as tg_module
from output.channels.telegram import (
    TelegramOutput,
    reset_telegram_rate_limit_for_tests,
)
from tests.tdd import _telegram_live_fixture as live_fixture
from tests.tdd._telegram_live_fixture import live_telegram_enabled, staging_live_settings

# 22 > Produktiv-Obergrenze (18 je 60-s-Fenster): ab Nachricht 19 MUSS die
# eigene Bremse warten, sonst waere der Nachweis wertlos.
MESSAGE_COUNT = 22

# Budget eines Zeitplaner-Laufs (internal/scheduler/scheduler.go:82).
SCHEDULER_BUDGET_SECONDS = 120.0

# Zeitplaner-Budget (Serie) + Aufraeumen (22 deleteMessage zaehlen selbst gegen
# die Drossel und brauchen daher noch einmal bis zu einer Fensterlaenge) +
# Reserve fuer echte Netz-Latenz.
pytestmark = [
    pytest.mark.live,
    pytest.mark.timeout(300),
    pytest.mark.skipif(
        not live_telegram_enabled(),
        reason="GZ_TELEGRAM_LIVE=1 + Staging-Zugangsdaten noetig — Live-Sends nur opt-in (#1014)",
    ),
]


def _ensure_unpaced_transport() -> None:
    """Stellt den ECHTEN httpx-Transportweg sicher.

    ``_telegram_live_fixture._ensure_paced_telegram_post()`` legt fuer die
    #686-Live-Tests prozessweit eine Testbremse von 3,5 s je Telegram-POST auf
    ``output.channels.telegram.httpx.post``. Liefe dieser Test im selben Prozess
    danach, wuerde die Testbremse die zu beweisende Produktiv-Bremse
    verdecken (und die Laufzeit sprengen). Hier wird deshalb der urspruengliche
    ``httpx.post`` zurueckgestellt — kein Eingriff in Produktivcode.
    """
    if getattr(live_fixture, "_patch_state", {}).get("installed"):
        tg_module.httpx.post = live_fixture._real_httpx_post
        live_fixture._patch_state["installed"] = False


def _cleanup(chat_id: str, message_ids: list[int]) -> list[str]:
    """Loescht jede erzeugte Nachricht wieder. Gibt die Fehlschlaege zurueck.

    Die Loeschungen laufen ueber denselben gedrosselten Transportweg und zaehlen
    selbst gegen die Fenstergrenze — das ist erwartet und Teil des Nachweises
    (AC-7: alle Schreibzugriffe eines Chats teilen sich das Limit).
    """
    settings = staging_live_settings()
    failures: list[str] = []
    for message_id in message_ids:
        try:
            if not TelegramOutput(settings).delete_message(chat_id, message_id):
                failures.append(f"message_id={message_id}: deleteMessage nicht bestaetigt")
        except Exception as exc:  # noqa: BLE001 — Aufraeumen darf nie hart abbrechen
            failures.append(f"message_id={message_id}: {exc!r}")
    return failures


def test_long_live_series_stays_within_scheduler_budget():
    """Given eine echte Serie von 22 Nachrichten geht mit den Produktiv-Grenzwerten
    an den Staging-Test-Chat / When der Versand gegen die echte Bot-API laeuft /
    Then bekommt JEDE Nachricht eine message_id von Telegram zurueck, es fliegt
    kein OutputError, und die Serie bleibt unter dem 120-s-Budget eines
    Zeitplaner-Laufs — obwohl die eigene Bremse nachweislich gewartet hat.
    """
    _ensure_unpaced_transport()

    # --- Testkanal-Schutz: VOR der ersten Nachricht ---------------------------
    test_chat_id = os.environ.get("GZ_TELEGRAM_TEST_CHAT_ID", "").strip()
    assert test_chat_id, "GZ_TELEGRAM_TEST_CHAT_ID fehlt — es wird NUR in den Testkanal gesendet."
    user_chat_id = os.environ.get("GZ_TELEGRAM_CHAT_ID", "").strip()
    assert test_chat_id != user_chat_id, (
        "GZ_TELEGRAM_TEST_CHAT_ID ist identisch mit dem echten Nutzer-Chat "
        f"({user_chat_id!r}) — dieser Test darf niemals an einen Nutzer senden."
    )

    settings = staging_live_settings()
    assert str(settings.telegram_chat_id) == test_chat_id, (
        f"Zielchat {settings.telegram_chat_id!r} ist nicht der Testkanal {test_chat_id!r}."
    )

    # --- Produktiv-Grenzwerte, nicht verbogen --------------------------------
    assert settings.telegram_rate_limit_max_per_window == 18
    assert settings.telegram_rate_limit_window_seconds == 60
    assert settings.telegram_retry_after_cap_seconds == 45
    assert MESSAGE_COUNT > settings.telegram_rate_limit_max_per_window, (
        "Die Serie muss laenger sein als das Sendefenster, sonst loest sie die Bremse nie aus."
    )

    # Deterministischer Startpunkt: fremde Zeitstempel aus vorherigen Testfaellen
    # wuerden die Messung verfaelschen (sanktionierter Testhaken, kein Sonderpfad).
    reset_telegram_rate_limit_for_tests()

    message_ids: list[int] = []
    send_errors: list[str] = []
    try:
        started = time.monotonic()
        for i in range(1, MESSAGE_COUNT + 1):
            text = (
                f"🤖 GZ-Testlauf Sendedrossel (#1370) — Teil {i}/{MESSAGE_COUNT}. "
                "Automatischer Live-Test, wird nach dem Lauf wieder geloescht."
            )
            try:
                # Frische Instanz je Nachricht — genau wie notification_service.py:344.
                # Beweist, dass die Buchfuehrung prozessweit greift, nicht je Objekt.
                message_id = TelegramOutput(settings).send(
                    "GZ-Testlauf", text, parse_mode="HTML", suppress_subject_line=True,
                )
            except Exception as exc:  # noqa: BLE001 — Fehlerbild soll sichtbar sein
                send_errors.append(f"Teil {i}/{MESSAGE_COUNT}: {exc!r}")
                continue
            if message_id is not None:
                message_ids.append(int(message_id))
            else:
                send_errors.append(f"Teil {i}/{MESSAGE_COUNT}: keine message_id (nicht zugestellt)")
        elapsed = time.monotonic() - started

        # (b) kein OutputError / kein stiller Fehlschlag
        assert not send_errors, (
            "Der Live-Versand ist an der echten Bot-API gescheitert — genau das "
            "Fehlerbild aus #1370 (429 als Dauerfehler):\n  " + "\n  ".join(send_errors)
        )
        # (a) alle Teile wirklich zugestellt (message_id = Telegram-Quittung)
        assert len(message_ids) == MESSAGE_COUNT, (
            f"Nur {len(message_ids)} von {MESSAGE_COUNT} Teilen haben eine message_id "
            "von Telegram zurueckbekommen."
        )
        assert len(set(message_ids)) == MESSAGE_COUNT, (
            f"Doppelte message_ids — Serie nicht vollstaendig eigenstaendig: {message_ids}"
        )
        # Die Bremse hat nachweislich gewartet: ab Teil 19 muss sie das Fenster
        # abwarten. Ohne Wartezeit waere die Serie gegen die echte API in wenigen
        # Sekunden durch — dann liefe der Test an der Drossel vorbei.
        assert elapsed > 30.0, (
            f"Die Serie war nach {elapsed:.1f}s durch, ohne dass die Bremse gewartet hat — "
            f"{MESSAGE_COUNT} Nachrichten koennen die Grenze von "
            f"{settings.telegram_rate_limit_max_per_window} je "
            f"{settings.telegram_rate_limit_window_seconds:.0f}s nicht ungebremst passieren. "
            "Der Nachweis waere wertlos (laeuft eine Testbremse mit?)."
        )
        # (c) Zeitplaner-Budget gehalten
        assert elapsed < SCHEDULER_BUDGET_SECONDS, (
            f"Die Serie brauchte {elapsed:.1f}s und sprengt damit das "
            f"{SCHEDULER_BUDGET_SECONDS:.0f}-s-Budget eines Zeitplaner-Laufs "
            "(internal/scheduler/scheduler.go:82)."
        )
    finally:
        cleanup_failures = _cleanup(test_chat_id, message_ids)

    assert not cleanup_failures, (
        "Aufraeumen im Testkanal fehlgeschlagen (Chat-Muell):\n  "
        + "\n  ".join(cleanup_failures)
    )
