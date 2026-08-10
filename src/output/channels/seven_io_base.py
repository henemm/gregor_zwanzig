"""Gemeinsame Basis der beiden seven.io-Kanaele: SMS und Premium-SMS.

Issue #1676 S2a (ADR-0049, Spec D1). Beide Kanaele sprechen dasselbe
Gateway, unterscheiden sich aber fachlich in Absender, Empfaenger,
Fehlverhalten und Berechtigung. Gemeinsam bleiben genau zwei Dinge, und die
liegen deshalb HIER, ein einziges Mal:

* die beiden Sicherheitssperren — Test-Modus-Sandbox-Key (#1336) und
  Herkunftssperre (#1476),
* der HTTP-Transport samt Antwort-Auswertung.

Warum eine gemeinsame Basis und keine Kopie: der Paritaetstest
`tests/tdd/test_channel_origin_guard_parity.py` prueft die Sperren
**namentlich je Klasse** — eine in einer Kopie vergessene Sperre faellt der
Testsuite nicht auf. Eine Kopie haette also genau die Vergessbarkeit
verdoppelt, die die Sperren verhindern sollen.

Die Unterklassen fuellen nur `_resolve_sender()` / `_resolve_recipient()`
(und bei Bedarf `_validate_config()`).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import httpx

from app.config import Settings
from app.origin_guard import running_origin
from output.channels.base import OutputConfigError, OutputError

logger = logging.getLogger(__name__)


def mask_number(number: Optional[str]) -> str:
    """Rufnummer fuer Protokolle: nur die letzten drei Stellen.

    Die gelernte Garmin-Rueckadresse darf nach S1-Vorgabe nur maskiert in
    Logzeilen erscheinen; fuer die normale SMS-Nummer gilt dasselbe Mass.
    """
    if not number:
        return "<leer>"
    return f"…{number[-3:]}" if len(number) > 3 else "…"


class SevenIoChannelBase:
    """Template-Method fuer Kanaele, die ueber das seven.io-Gateway senden.

    Implementiert das OutputChannel-Protokoll: `send(subject, body)`.
    `subject` wird ignoriert — eine SMS hat kein Betreff-Feld.
    Zeitgrenze 10 s; ein Fehlschlag wirft `OutputError`.
    """

    #: Kanalname (`OutputChannel.name`) — von jeder Unterklasse zu setzen.
    CHANNEL_NAME = "seven_io"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._validate_config()

    @property
    def name(self) -> str:
        return self.CHANNEL_NAME

    # ------------------------------------------------------------------
    # Von den Kanaelen zu fuellen
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Transport-Voraussetzungen. Unterklassen verscharfen das.

        Bewusst NUR Gateway und Schluessel: ob ein Ziel vorliegt, entscheidet
        `_resolve_recipient()` zur Sendezeit — bei Premium-SMS ist das erst
        dort final bekannt (Spec D3).
        """
        if not (self._settings.sms_gateway_url and self._settings.seven_api_key):
            raise OutputConfigError(
                self.name,
                "seven.io nicht konfiguriert: sms_gateway_url und seven_api_key "
                "sind Pflichtfelder",
            )

    def _resolve_sender(self) -> Optional[str]:
        """Absender; `None` laesst das Gateway seinen Standard verwenden."""
        raise NotImplementedError

    def _resolve_recipient(self) -> str:
        """Empfaenger. Wirft `OutputConfigError`, wenn kein Versand erlaubt ist."""
        raise NotImplementedError

    def _origin(self) -> str:
        """Herkunft DIESES Kanal-Moduls (Issue #1476).

        Die Unterklassen ueberschreiben das mit `running_origin(Path(__file__))`
        aus ihrem EIGENEN Modul. Zwei Gruende, beide inhaltlich: die Sperre
        fragt nach der Herkunft des Kanal-Codes, nicht nach der dieser
        Basisdatei — und Tests, die eine Prod-Herkunft vortaeuschen muessen
        (`monkeypatch.setattr(sms_mod, "running_origin", …)`), setzen genau
        dort an.
        """
        return running_origin(Path(__file__))

    # ------------------------------------------------------------------
    # Sicherheitssperren — gelten fuer JEDEN seven.io-Kanal
    # ------------------------------------------------------------------

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
                self.name,
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
        if self._origin() != "test":
            return self._settings.seven_api_key
        sandbox_key = self._settings.seven_sandbox_key
        if not sandbox_key:
            raise OutputConfigError(
                self.name,
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

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def send(self, subject: str, body: str) -> None:
        """Sende `body` ueber das seven.io-Gateway. `subject` wird ignoriert.

        Reihenfolge ist Teil der Zusicherung: beide Sperren laufen
        BEDINGUNGSLOS und VOR jeder Ziel-Auflosung, damit kein Kanal am
        Sandbox-Zwang vorbeikommt.
        """
        self._guard_test_mode_sandbox_key()
        api_key = self._guard_code_origin()
        recipient = self._resolve_recipient()
        sender = self._resolve_sender()

        payload: dict[str, str] = {"to": recipient, "text": body}
        if sender:
            payload["from"] = sender

        response = httpx.post(
            self._settings.sms_gateway_url,
            headers={"X-Api-Key": api_key},
            data=payload,
            timeout=10,
        )
        if response.status_code != 200:
            raise OutputError(
                self.name,
                f"seven.io HTTP {response.status_code}: {response.text[:200]}",
            )
        status_code = response.text.strip()
        if status_code != "100":
            raise OutputError(self.name, f"seven.io Fehler-Code: {status_code!r}")
        logger.info(
            "%s an %s ueber seven.io gesendet", self.name, mask_number(recipient),
        )
