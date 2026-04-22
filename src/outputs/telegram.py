"""Telegram output channel via Bot API."""
import logging

import httpx

from app.config import Settings
from outputs.base import OutputError

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"
MAX_MESSAGE_LENGTH = 4096


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

    def send(self, subject: str, body: str) -> None:
        """Send a Telegram message via Bot API."""
        token = self._settings.telegram_bot_token
        chat_id = self._settings.telegram_chat_id
        url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"

        message = f"[{subject}]\n\n{body}"
        if len(message) > MAX_MESSAGE_LENGTH:
            message = message[:MAX_MESSAGE_LENGTH]
            logger.warning("Telegram message truncated to %d chars", MAX_MESSAGE_LENGTH)

        payload = {"chat_id": chat_id, "text": message}

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
                raise OutputError(f"Telegram API returned status {response.status_code}")
        except httpx.TimeoutException:
            logger.error("Telegram send timed out after %ds (subject=%r)", self._timeout, subject)
            raise OutputError(f"Telegram send timed out after {self._timeout}s")
        except httpx.HTTPError as exc:
            logger.error("Telegram send failed: %s", exc)
            raise OutputError(f"Telegram send failed: {exc}") from exc
