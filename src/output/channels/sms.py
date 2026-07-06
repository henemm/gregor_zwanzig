"""SMS output channel via seven.io HTTP API."""
import logging

import httpx

from app.config import Settings
from output.channels.base import OutputConfigError, OutputError

logger = logging.getLogger(__name__)


class SMSOutput:
    """Sends SMS via seven.io REST API.

    Implements the OutputChannel protocol: send(subject, body).
    subject is ignored — SMS has no subject field.
    Uses a 10s timeout; on failure raises OutputError.
    """

    def __init__(self, settings: Settings) -> None:
        if not settings.can_send_sms():
            raise OutputConfigError(
                "sms",
                "SMS nicht konfiguriert: sms_api_key und sms_to sind Pflichtfelder",
            )
        self._settings = settings

    @property
    def name(self) -> str:
        return "sms"

    def send(self, subject: str, body: str) -> None:
        """Send body as SMS via seven.io. subject is ignored."""
        payload: dict[str, str] = {
            "to": self._settings.sms_to,
            "text": body,
        }
        if self._settings.sms_from:
            payload["from"] = self._settings.sms_from

        response = httpx.post(
            self._settings.sms_gateway_url,
            headers={"X-Api-Key": self._settings.seven_api_key},
            data=payload,
            timeout=10,
        )
        if response.status_code != 200:
            raise OutputError(
                "sms",
                f"seven.io HTTP {response.status_code}: {response.text[:200]}",
            )
        status_code = response.text.strip()
        if status_code != "100":
            raise OutputError("sms", f"seven.io Fehler-Code: {status_code!r}")
        logger.info("SMS sent to %s via seven.io", self._settings.sms_to)
