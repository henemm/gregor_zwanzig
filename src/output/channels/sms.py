"""SMS output channel via seven.io HTTP API."""
import logging
from pathlib import Path

import httpx

from app.config import Settings
from app.origin_guard import running_origin
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

    def _guard_test_mode_sandbox_key(self) -> None:
        """Bedingungsloser Guard (Issue #1336, Vorbild telegram.py #1288): im
        Test-Modus (is_test_mode=True) ist AUSSCHLIESSLICH der konfigurierte
        seven.io-Sandbox-Key erlaubt. Faengt die Fallback-Luecke aus
        config.py::for_testing() ab: fehlt seven_sandbox_key, bleibt
        seven_api_key sonst unveraendert der Prod-Key.
        """
        if not self._settings.is_test_mode:
            return
        sandbox_key = self._settings.seven_sandbox_key
        active = self._settings.seven_api_key
        if not sandbox_key or active != sandbox_key:
            raise OutputConfigError(
                "sms",
                "Test-Modus aktiv, aber seven_api_key ist nicht der "
                "Sandbox-Zugang (GZ_SEVEN_SANDBOX_KEY) — Versand blockiert "
                "(Issue #1336).",
            )

    def _guard_code_origin(self) -> str:
        """Herkunftssperre (Issue #1476, AC-6 — Vorbild
        telegram.py::_guard_code_origin): bei Testlauf-Herkunft ist der
        Prod-API-Key unzulaessig. Der Sandbox-Key sendet laut seven.io-Doku
        NIE eine echte SMS ("sendet nie, kostet nie") und ist damit der
        sichere Ersatz -- keine Rufnummer muss umgeschaltet werden.
        """
        if running_origin(Path(__file__)) != "test":
            return self._settings.seven_api_key
        sandbox_key = self._settings.seven_sandbox_key
        if not sandbox_key:
            raise OutputConfigError(
                "sms",
                "Herkunftssperre (Issue #1476): Code laeuft aus einem "
                "Testlauf-Verzeichnis, aber kein Sandbox-Key konfiguriert "
                "(GZ_SEVEN_SANDBOX_KEY) -- Versand abgebrochen.",
            )
        if self._settings.seven_api_key != sandbox_key:
            logger.warning(
                "Herkunftssperre (Issue #1476): Testlauf-Herkunft erkannt "
                "-- SMS-Key auf den Sandbox-Key umgeschaltet.",
            )
        return sandbox_key

    def send(self, subject: str, body: str) -> None:
        """Send body as SMS via seven.io. subject is ignored."""
        self._guard_test_mode_sandbox_key()
        api_key = self._guard_code_origin()
        payload: dict[str, str] = {
            "to": self._settings.sms_to,
            "text": body,
        }
        if self._settings.sms_from:
            payload["from"] = self._settings.sms_from

        response = httpx.post(
            self._settings.sms_gateway_url,
            headers={"X-Api-Key": api_key},
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
