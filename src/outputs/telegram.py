"""Telegram output channel via Bot API."""
import logging

import httpx

from app.config import Settings
from outputs.base import OutputError

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"
MAX_MESSAGE_LENGTH = 4096

BOT_COMMANDS = [
    {"command": "briefing", "description": "🌤️ Aktuelles Briefing"},
    {"command": "wetter", "description": "📊 Wetter-Details"},
    {"command": "hilfe", "description": "ℹ️ Verfügbare Befehle"},
]


def _api_ok(response: httpx.Response) -> bool:
    """True wenn die Bot-API-Antwort ein ok:true-JSON ist (HTTP 200 garantiert kein Erfolg)."""
    try:
        return bool(response.json().get("ok"))
    except ValueError:
        return False


class TelegramOutput:
    """Sends messages via the Telegram Bot API.

    Implements the OutputChannel protocol: send(subject, body).
    Uses fire-and-forget semantics — one attempt with a 10s timeout.
    On failure, logs the error; the next scheduled run is the implicit retry.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings if settings else Settings()
        self._timeout = 10

    @property
    def name(self) -> str:
        return "telegram"

    def send(self, subject: str, body: str, reply_markup: dict | None = None) -> None:
        """Send a Telegram message via Bot API.

        Args:
            subject: Message subject shown as header.
            body: Message body text.
            reply_markup: Optional Inline-Keyboard dict (Telegram Bot API format).
                          If None, payload is identical to the legacy format (no key added).
        """
        token = self._settings.telegram_bot_token
        chat_id = self._settings.telegram_chat_id
        url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"

        message = f"[{subject}]\n\n{body}"
        if len(message) > MAX_MESSAGE_LENGTH:
            message = message[:MAX_MESSAGE_LENGTH]
            logger.warning("Telegram message truncated to %d chars", MAX_MESSAGE_LENGTH)

        payload: dict = {"chat_id": chat_id, "text": message}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup

        try:
            response = httpx.post(url, json=payload, timeout=self._timeout)
            if response.status_code == 200:
                logger.info("Telegram message sent (subject=%r)", subject)
            else:
                logger.error(
                    "Telegram API returned status %d: %s",
                    response.status_code,
                    response.text[:200],
                )
                raise OutputError("telegram", f"Telegram API returned status {response.status_code}")
        except httpx.TimeoutException:
            logger.error("Telegram send timed out after %ds (subject=%r)", self._timeout, subject)
            raise OutputError("telegram", f"Telegram send timed out after {self._timeout}s")
        except httpx.HTTPError as exc:
            logger.error("Telegram send failed: %s", exc)
            raise OutputError("telegram", f"Telegram send failed: {exc}") from exc

    def edit_message_text(
        self, chat_id, message_id, text: str, reply_markup: dict | None = None
    ) -> None:
        """Edit an existing message in-place via editMessageText (Zoom-Navigation).

        fail-soft: a non-200 / HTTPError / Timeout is only logged, never raised —
        "message is not modified" and stale messages must not crash the webhook.
        """
        token = self._settings.telegram_bot_token
        url = f"{TELEGRAM_API_BASE}/bot{token}/editMessageText"

        message = text
        if len(message) > MAX_MESSAGE_LENGTH:
            message = message[:MAX_MESSAGE_LENGTH]
            logger.warning("Telegram edit message truncated to %d chars", MAX_MESSAGE_LENGTH)

        payload: dict = {"chat_id": chat_id, "message_id": message_id, "text": message}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup

        try:
            response = httpx.post(url, json=payload, timeout=self._timeout)
            if response.status_code != 200:
                logger.warning(
                    "editMessageText returned status %d: %s",
                    response.status_code,
                    response.text[:200],
                )
        except httpx.HTTPError as exc:
            logger.warning("editMessageText failed (fail-soft): %s", exc)

    def answer_callback_query(self, callback_query_id, text: str | None = None) -> None:
        """Acknowledge a callback_query via answerCallbackQuery (stop loading spinner).

        fail-soft: errors are only logged, never raised.
        """
        token = self._settings.telegram_bot_token
        url = f"{TELEGRAM_API_BASE}/bot{token}/answerCallbackQuery"

        payload: dict = {"callback_query_id": callback_query_id}
        if text is not None:
            payload["text"] = text

        try:
            response = httpx.post(url, json=payload, timeout=self._timeout)
            if response.status_code != 200:
                logger.warning(
                    "answerCallbackQuery returned status %d: %s",
                    response.status_code,
                    response.text[:200],
                )
        except httpx.HTTPError as exc:
            logger.warning("answerCallbackQuery failed (fail-soft): %s", exc)

    def set_my_commands(self, commands: list[dict] | None = None) -> None:
        """Register Bot-Menü commands via setMyCommands.

        Args:
            commands: List of command dicts with 'command' and 'description' keys.
                      Defaults to BOT_COMMANDS when None.
        """
        token = self._settings.telegram_bot_token
        url = f"{TELEGRAM_API_BASE}/bot{token}/setMyCommands"
        payload = {"commands": commands if commands is not None else BOT_COMMANDS}

        try:
            response = httpx.post(url, json=payload, timeout=self._timeout)
            if response.status_code != 200:
                raise OutputError("telegram", f"setMyCommands returned status {response.status_code}")
            # Bot-API kann HTTP 200 mit ok:false liefern → als Fehler behandeln.
            if not _api_ok(response):
                raise OutputError("telegram", f"setMyCommands rejected: {response.text[:200]}")
            logger.info("Telegram setMyCommands succeeded (%d commands)", len(payload["commands"]))
        except httpx.TimeoutException:
            raise OutputError("telegram", f"setMyCommands timed out after {self._timeout}s")
        except httpx.HTTPError as exc:
            raise OutputError("telegram", f"setMyCommands failed: {exc}") from exc

    def get_my_commands(self) -> list[dict]:
        """Fetch the currently registered Bot-Menü commands via getMyCommands.

        Returns:
            List of command dicts as returned by the Telegram Bot API.
        """
        token = self._settings.telegram_bot_token
        url = f"{TELEGRAM_API_BASE}/bot{token}/getMyCommands"

        try:
            response = httpx.post(url, json={}, timeout=self._timeout)
            if response.status_code != 200:
                raise OutputError("telegram", f"getMyCommands returned status {response.status_code}")
            try:
                data = response.json()
            except ValueError as exc:  # nicht-JSON-Body → sauberer OutputError statt rohem Decode-Fehler
                raise OutputError("telegram", f"getMyCommands returned non-JSON body: {exc}") from exc
            if not data.get("ok"):
                raise OutputError("telegram", f"getMyCommands rejected: {response.text[:200]}")
            return data.get("result", [])
        except httpx.TimeoutException:
            raise OutputError("telegram", f"getMyCommands timed out after {self._timeout}s")
        except httpx.HTTPError as exc:
            raise OutputError("telegram", f"getMyCommands failed: {exc}") from exc
