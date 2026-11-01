"""Zwei-Nutzer-Zuordnung eingehender Telegram-Befehle (Python-Seite).

Deckt AC-5 der Spec ``docs/specs/modules/fix_1814_s2_telegram_alt_route_entfernen.md``
(Issue #1814): Zwei verschiedene Nutzer mit je einem verknuepften Telegram-Chat
senden nacheinander einen Befehl -> jeder Befehl wird dem richtigen Nutzer
zugeordnet.

Die Go-API reicht den Webhook-Body nur durch; die Zuordnung Chat-ID -> Nutzer
macht der Python-Core im ``InboundTelegramReader._resolve_user_for_chat`` (auf
Basis von ``app.loader.lookup_user_by_telegram_chat_id``). Dieser Test prueft
genau diese Wirkstelle POSITIV mit zwei echten Konten.

Nachweisform (CLAUDE.md, Mock-Verbot): echtes Dateisystem (``tmp_path``) mit
echten ``users/<id>/user.json``-Profilen; kein Netz, kein Mock/patch. Einzig
die Datenwurzel wird per ``monkeypatch.setattr`` auf ``tmp_path`` gelegt
(gleiches Muster wie ``test_telegram_chat_id_ownership.py``).
"""
from __future__ import annotations

import json
from pathlib import Path

from app import loader
from app.config import Settings
from app.loader import lookup_user_by_telegram_chat_id
from services.inbound_telegram_reader import InboundTelegramReader

CHAT_ANNA = "710001"
CHAT_BERTRAM = "720002"


def _write_user(data_root: Path, user_id: str, chat_id: str, mail_to: str) -> None:
    """Echtes Nutzerprofil auf die Platte schreiben (kein gemocktes Listing)."""
    user_dir = data_root / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    profile = {"id": user_id, "telegram_chat_id": chat_id, "mail_to": mail_to}
    (user_dir / "user.json").write_text(json.dumps(profile), encoding="utf-8")


def _zwei_nutzer(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(loader, "_DATA_ROOT", str(tmp_path))
    # "anna" ist alphabetisch zuerst: ein Lookup, der still den ersten Nutzer
    # liefert, ordnet Bertrams Befehl Anna zu und wird hier rot.
    _write_user(tmp_path, "anna", chat_id=CHAT_ANNA, mail_to="anna@example.com")
    _write_user(tmp_path, "bertram", chat_id=CHAT_BERTRAM, mail_to="bertram@example.com")
    # Drittes Konto ohne verknuepften Chat: darf nie getroffen werden.
    _write_user(tmp_path, "carla", chat_id="", mail_to="carla@example.com")


def test_lookup_ordnet_jede_chat_id_ihrem_eigenen_nutzer_zu(tmp_path, monkeypatch):
    """AC-5: GIVEN zwei echte Nutzer mit verschiedenen Telegram-Chat-IDs
    WHEN nacheinander nach beiden Chat-IDs aufgeloest wird
    THEN liefert jede Chat-ID genau ihren Nutzer, nie den anderen."""
    _zwei_nutzer(tmp_path, monkeypatch)
    data_dir = str(tmp_path)

    assert lookup_user_by_telegram_chat_id(CHAT_ANNA, data_dir=data_dir) == "anna"
    assert lookup_user_by_telegram_chat_id(CHAT_BERTRAM, data_dir=data_dir) == "bertram"
    # Umgekehrte Reihenfolge: kein Zustand aus dem vorigen Aufruf bleibt haengen.
    assert lookup_user_by_telegram_chat_id(CHAT_BERTRAM, data_dir=data_dir) == "bertram"
    assert lookup_user_by_telegram_chat_id(CHAT_ANNA, data_dir=data_dir) == "anna"
    # int-tolerant (Telegram liefert chat.id als Zahl).
    assert lookup_user_by_telegram_chat_id(int(CHAT_BERTRAM), data_dir=data_dir) == "bertram"
    # Unbekannte Chat-ID: keine Zuordnung, kein Rueckfall auf irgendein Konto.
    assert lookup_user_by_telegram_chat_id("799999", data_dir=data_dir) is None


def test_eingehende_befehle_zweier_nutzer_landen_beim_richtigen_konto(tmp_path, monkeypatch):
    """AC-5 am Eingangs-Pfad: GIVEN zwei echte Nutzer mit je verknuepftem Chat
    WHEN der InboundTelegramReader nacheinander einen Befehl von Annas und
    dann von Bertrams Chat aufloest
    THEN bekommt jeder Befehl die user_id UND die nutzerbezogenen Settings
    (Empfaenger) seines eigenen Kontos, nie die des anderen."""
    _zwei_nutzer(tmp_path, monkeypatch)
    reader = InboundTelegramReader()
    base = Settings()

    uid_a, settings_a = reader._resolve_user_for_chat(CHAT_ANNA, base)
    uid_b, settings_b = reader._resolve_user_for_chat(CHAT_BERTRAM, base)

    assert uid_a == "anna"
    assert uid_b == "bertram"
    assert uid_a != uid_b
    assert settings_a.mail_to == "anna@example.com"
    assert settings_b.mail_to == "bertram@example.com"

    # Und in umgekehrter Reihenfolge erneut -- keine Vertauschung.
    uid_b2, settings_b2 = reader._resolve_user_for_chat(CHAT_BERTRAM, base)
    uid_a2, settings_a2 = reader._resolve_user_for_chat(CHAT_ANNA, base)
    assert (uid_b2, settings_b2.mail_to) == ("bertram", "bertram@example.com")
    assert (uid_a2, settings_a2.mail_to) == ("anna", "anna@example.com")
