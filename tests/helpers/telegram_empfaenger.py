"""Gemeinsamer Test-Helper fuer den Telegram-Empfaengervertrag (Issue #1412 S4a).

Der Transport sendet nur noch an belegte Empfaenger:

* ``user_profile`` -- Profil-Chat aus ``user.json`` (``profil_chat`` schreibt
  ihn unter der per-Test isolierten Datenwurzel, ``profil_ausgang`` liefert
  den passenden ``TelegramOutput``);
* ``inbound_reply`` -- Absender des laufenden Webhook-Updates (``im_update``
  setzt den Herkunftsbeleg, ``antwort_ausgang`` liefert den Ausgang).

Kein Stub des Prueflings: es werden die echten Fabriken und der echte
Herkunftsbeleg benutzt.
"""
from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager

from app.loader import get_data_dir
from output.channels.recipient import TelegramRecipient, _current_inbound_sender
from output.channels.telegram import TelegramOutput


def numerische_chat_id(schluessel: str) -> str:
    """Deterministische, numerische Test-Chat-ID je Schluessel (meist die
    Nutzerkennung) -- die Formpruefung (AC-6) verlangt ``-?\\d{1,20}``.
    sha256 statt ``hash()`` (prozessweit gesalzen, nicht reproduzierbar);
    15 Stellen machen Kollisionen (Mehrdeutigkeit #2141) praktisch unmoeglich."""
    return str(int(hashlib.sha256(schluessel.encode()).hexdigest(), 16) % 10**15 + 10**14)


def profil_chat(user_id: str, chat_id, **felder) -> None:
    """Traegt ``telegram_chat_id`` (und weitere Felder) in ``user.json`` ein --
    Read-Modify-Write, bestehende Profilfelder bleiben erhalten."""
    ordner = get_data_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    datei = ordner / "user.json"
    try:
        profil = json.loads(datei.read_text())
    except (OSError, ValueError):
        profil = {}
    if not isinstance(profil, dict):
        profil = {}
    profil.setdefault("id", user_id)
    profil.update({"telegram_chat_id": chat_id, **felder})
    datei.write_text(json.dumps(profil))


def mit_profil_chat(user_id: str, settings) -> str:
    """Migrationshilfe #1412 S4a: traegt den Chat, den ein Test bisher nur in
    ``settings.telegram_chat_id`` setzte, ins Profil des Nutzers ein (dort
    liest ihn ``TelegramRecipient.for_user``) und gibt ``user_id`` zurueck --
    inline als ``user_id=mit_profil_chat(uid, settings)`` nutzbar."""
    chat = getattr(settings, "telegram_chat_id", None)
    if chat:
        profil_chat(user_id, chat)
    return user_id


def profil_ausgang(settings, user_id: str, chat_id=None) -> TelegramOutput:
    """``TelegramOutput`` mit Empfaenger ``for_user``; ``chat_id`` wird vorher
    ins Profil geschrieben (``None``: Profil bleibt, wie es ist)."""
    if chat_id is not None:
        profil_chat(user_id, chat_id)
    return TelegramOutput(settings, recipient=TelegramRecipient.for_user(user_id, settings))


@contextmanager
def im_update(chat_id):
    """Herkunftsbeleg "Absender des laufenden Updates" fuer die Dauer des Blocks."""
    token = _current_inbound_sender.set(None if chat_id is None else str(chat_id))
    try:
        yield
    finally:
        _current_inbound_sender.reset(token)


def antwort_ausgang(settings, chat_id, klasse=TelegramOutput) -> TelegramOutput:
    """``TelegramOutput`` (oder Unterklasse) mit Empfaenger
    ``inbound_reply(chat_id)`` -- sendet nur innerhalb von ``im_update(chat_id)``."""
    return klasse(settings, recipient=TelegramRecipient.inbound_reply(chat_id))


def antwort_im_update(settings, chat_id, klasse=TelegramOutput) -> TelegramOutput:
    """Wie ``antwort_ausgang``, setzt aber den Herkunftsbeleg fuer den Rest des
    Tests ("der Test laeuft im Update von ``chat_id``"). Zurueckgesetzt wird
    er von der autouse-Fixture ``_telegram_herkunftsbeleg_leeren``
    (``tests/conftest.py``)."""
    _current_inbound_sender.set(None if chat_id is None else str(chat_id))
    return antwort_ausgang(settings, chat_id, klasse)
