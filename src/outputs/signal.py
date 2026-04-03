"""Signal output channel via Callmebot API."""
import logging
import urllib.parse

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

DEFAULT_API_URL = "https://signal.callmebot.com/signal/send.php"
MAX_MESSAGE_LENGTH = 4000


class SignalOutput:
    """Sends messages via Signal using the Callmebot API."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings if settings else Settings()
        self._timeout = 10

    @property
    def name(self) -> str:
        return "signal"

    def send(self, subject: str, body: str) -> None:
        """Send a Signal message via Callmebot."""
        phone = self._settings.signal_phone
        apikey = self._settings.signal_api_key
        api_url = self._settings.signal_api_url or DEFAULT_API_URL

        message = f"[{subject}]\n\n{body}"
        if len(message) > MAX_MESSAGE_LENGTH:
            message = message[:MAX_MESSAGE_LENGTH]
            logger.warning("Signal message truncated to %d chars", MAX_MESSAGE_LENGTH)

        encoded = urllib.parse.quote(message)
        url = f"{api_url}?phone={phone}&apikey={apikey}&text={encoded}"

        try:
            response = httpx.get(url, timeout=self._timeout)
            if response.status_code == 200:
                logger.info("Signal message sent (subject=%r)", subject)
            else:
                logger.error(
                    "Callmebot returned status %d: %s",
                    response.status_code,
                    response.text[:200],
                )
        except httpx.TimeoutException:
            logger.error("Signal send timed out after %ds (subject=%r)", self._timeout, subject)
        except httpx.HTTPError as exc:
            logger.error("Signal send failed: %s", exc)
