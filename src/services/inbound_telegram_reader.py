"""
Inbound Telegram Reader — Bot API long-polling for trip commands.

Polls getUpdates for new messages, extracts commands (free-text, no ### prefix),
delegates to TripCommandProcessor, and sends confirmation via TelegramOutput.

SPEC: docs/specs/modules/inbound_telegram_reader.md v1.0
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone

import httpx

from app.config import Settings
from app.loader import load_all_trips
from app.trip import Trip
from outputs.telegram import TelegramOutput
from services.trip_command_processor import (
    CommandResult,
    InboundMessage,
    TripCommandProcessor,
)

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"

_VALID_COMMANDS = {"ruhetag", "startdatum", "report", "abbruch", "status", "hilfe"}


class InboundTelegramReader:
    """Polls Telegram Bot API and processes trip commands from messages."""

    def __init__(self) -> None:
        self._offset: int = 0

    def poll_and_process(self, settings: Settings) -> int:
        """Long-polling: holt neue Updates, verarbeitet Befehle.

        Returns: Anzahl verarbeiteter Befehle.
        Gibt 0 zurück und macht keinen API-Call wenn settings.can_send_telegram() False ist.
        """
        if not settings.can_send_telegram():
            return 0

        token = settings.telegram_bot_token
        updates = self._get_updates(token)
        if not updates:
            return 0

        processed = 0
        max_update_id = self._offset - 1
        for update in updates:
            update_id = update.get("update_id", 0)
            if update_id > max_update_id:
                max_update_id = update_id
            try:
                if self._process_update(update, settings):
                    processed += 1
            except Exception as e:
                logger.error(f"Error processing update {update_id}: {e}")

        self._offset = max_update_id + 1
        return processed

    def _get_updates(self, token: str) -> list[dict]:
        """GET getUpdates with offset and timeout=30.

        Returns empty list on any error (fail-soft).
        """
        url = f"{TELEGRAM_API_BASE}/bot{token}/getUpdates"
        params = {"offset": self._offset, "timeout": 30}
        try:
            response = httpx.get(url, params=params, timeout=35)
            if response.status_code == 200:
                data = response.json()
                return data.get("result", [])
            logger.error(
                "getUpdates returned status %d: %s",
                response.status_code,
                response.text[:200],
            )
        except Exception as e:
            logger.error("getUpdates failed: %s", e)
        return []

    def _process_update(self, update: dict, settings: Settings) -> bool:
        """Verarbeitet ein einzelnes Update.

        Returns True wenn Update verarbeitet (nicht: ob Befehl erfolgreich).
        """
        message = update.get("message")
        if not message:
            return False

        text = message.get("text", "").strip()
        chat_id = str(message.get("chat", {}).get("id", ""))
        if not text or not chat_id:
            return False

        # /start TOKEN Handling — VOR user-resolve (user noch nicht bekannt)
        if text.startswith("/start "):
            token = text[len("/start "):].strip()
            if token:
                return self._process_start_command(token=token, chat_id=chat_id, settings=settings)

        # Resolve user-scoped settings for this chat_id
        user_id, user_settings = self._resolve_user_for_chat(chat_id, settings)

        # Aktiven Trip ermitteln (user-scoped)
        trip = self._find_active_trip(user_id)
        if not trip:
            TelegramOutput(user_settings).send(
                "Fehler",
                "Kein aktiver Trip gefunden. Erstelle oder aktiviere einen Trip auf gregor20.henemm.com",
            )
            return True

        # Befehl parsen
        key, value = self._parse_command(text)
        if key is None:
            TelegramOutput(user_settings).send(
                "Unbekannter Befehl",
                "Bekannte Befehle: ruhetag, startdatum, report, abbruch, status, hilfe",
            )
            return True

        # InboundMessage bauen und verarbeiten
        inbound = InboundMessage(
            channel="telegram",
            trip_name=trip.name,
            body=f"### {key}: {value}" if value else f"### {key}",
            sender=chat_id,
            received_at=datetime.now(tz=timezone.utc),
            user_id=user_id,
        )
        result: CommandResult = TripCommandProcessor().process(inbound)

        TelegramOutput(user_settings).send(
            result.confirmation_subject,
            result.confirmation_body,
        )
        return True

    def _find_active_trip(self, user_id: str = "default") -> Trip | None:
        """Aktiver Trip = erster Trip mit Datum-Overlap.

        Fallback: nächster zukünftiger Trip.
        Gibt None zurück wenn keine Trips existieren.
        """
        today = date.today()
        trips = load_all_trips(user_id)
        if not trips:
            return None

        # 1. Overlap: stage[0].date <= heute <= stage[-1].date
        for trip in trips:
            if not trip.stages:
                continue
            if trip.stages[0].date <= today <= trip.stages[-1].date:
                return trip

        # 2. Fallback: frühester zukünftiger Trip
        future = [t for t in trips if t.stages and t.stages[0].date > today]
        if future:
            return min(future, key=lambda t: t.stages[0].date)

        return None

    def _resolve_user_for_chat(
        self, chat_id: str, base_settings: Settings, data_dir: str = "data"
    ) -> tuple[str, Settings]:
        """Resolve user_id and user-scoped Settings for an incoming Telegram chat ID.

        Args:
            chat_id: Telegram chat ID (as string)
            base_settings: Base Settings object to derive user profile from
            data_dir: Root data directory (default: "data")

        Returns:
            (user_id, user_scoped_settings) — user_id is "default" if no match
        """
        from app.loader import lookup_user_by_telegram_chat_id
        user_id = lookup_user_by_telegram_chat_id(chat_id, data_dir=data_dir) or "default"
        return user_id, base_settings.with_user_profile(user_id)

    def _process_start_command(self, token: str, chat_id: str, settings: Settings) -> bool:
        """Verarbeitet /start TOKEN — registriert chat_id beim Go-Backend."""
        try:
            resp = httpx.post(
                "http://localhost:8090/api/internal/telegram-connect",
                json={"token": token, "chat_id": chat_id},
                timeout=5,
            )
            if resp.status_code == 200:
                logger.info(f"Telegram chat_id {chat_id} via token registriert")
                try:
                    confirm_settings = settings.model_copy(update={"telegram_chat_id": chat_id})
                    TelegramOutput(confirm_settings).send(
                        "Verbunden",
                        "✓ Du bist jetzt mit Gregor verbunden! Sende 'hilfe' für verfügbare Befehle.",
                    )
                except Exception as ce:
                    logger.warning(f"Bestätigungsnachricht fehlgeschlagen: {ce}")
            else:
                logger.warning(f"telegram-connect returned {resp.status_code}")
        except Exception as e:
            logger.error(f"telegram-connect Fehler: {e}")
        return True

    def _parse_command(self, text: str) -> tuple[str | None, str | None]:
        """Parst ersten nicht-leeren Satz: 'ruhetag 2' → ('ruhetag', '2').

        Immer lowercase. Unbekannte Befehle → (None, None).
        Bekannte Befehle: ruhetag, startdatum, report, abbruch, status, hilfe.
        Kein '### ' Prefix nötig — Freitext.
        """
        first_line = next(
            (line.strip() for line in text.splitlines() if line.strip()),
            "",
        )
        if not first_line:
            return None, None

        parts = first_line.lower().split(None, 1)
        key = parts[0]
        value = parts[1].strip() if len(parts) > 1 else None

        if key not in _VALID_COMMANDS:
            return None, None

        return key, value or None

