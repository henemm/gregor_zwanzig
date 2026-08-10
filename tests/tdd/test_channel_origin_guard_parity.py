"""Issue #1476 AC-6 — Herkunftssperre gilt auch für E-Mail und SMS.

Messergebnis (vor dieser Aenderung, per Codelesen belegt): BEIDE Kanaele
hatten dieselbe Luecke wie Telegram. `EmailOutput`s einzige Guards haengen an
`is_test_mode`/`env=="staging"` (Resend-Host-Sperre) bzw. an einer Allowlist
ECHTER Nutzerprofile — ein aus Settings() normal geladener Prod-`mail_to`
gehoert zu einem echten Profil und passiert die Allowlist unveraendert.
`SMSOutput._guard_test_mode_sandbox_key` haengt exakt wie die drei
Telegram-Waechter an `is_test_mode`. Ein Skript, das `Settings()` normal aus
einem Testlauf-Verzeichnis laedt (is_test_mode=False, env='production'),
haette in beiden Kanaelen ungebremst an die echten Prod-Ziele gesendet.

Boundary-Sinks (kein Live-Call): smtplib.SMTP fuer E-Mail, httpx.post fuer SMS.

Spec: docs/specs/fast/fix-1476-telegram-herkunftssperre.md
"""
from __future__ import annotations

import http.server
import smtplib
import socket
import threading
import urllib.parse
from datetime import datetime, timezone

import httpx
import pytest

from app.config import Settings
from output.channels import email as email_mod
from output.channels import sms as sms_mod
from output.channels.base import OutputConfigError
from output.channels.email import EmailOutput
from output.channels.sms import SMSOutput

# Lokal (@henemm.com) statt extern: smtp_host="mail.henemm.com" (Nicht-Resend-
# Pfad, s. #1235) lässt nur lokale Empfänger durch -- ein echter Resend-Host
# ist aus pytest heraus strukturell nicht erreichbar (#1122 Default-Deny lenkt
# ihn IMMER auf test_smtp_host um, auch mit resend_allowed=True).
PROD_RECIPIENT = "henning@henemm.com"
PROD_SMS_TO = "+491700000000"


class _SmtpSink:
    def __init__(self) -> None:
        self.sent: list[tuple] = []
        self.sock = self

    def settimeout(self, *a, **k):
        return None

    def __call__(self, host, port, *a, **k):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        return None

    def login(self, user, password):
        return None

    def sendmail(self, from_addr, to_addrs, msg):
        self.sent.append((from_addr, tuple(to_addrs)))


@pytest.fixture
def smtp_sink(monkeypatch) -> _SmtpSink:
    sink = _SmtpSink()
    monkeypatch.setattr(smtplib, "SMTP", sink)
    return sink


def _prod_style_email_settings(**overrides) -> Settings:
    defaults = dict(
        smtp_host="mail.henemm.com", smtp_user="prod-user", smtp_pass="prod-pass",
        mail_to=PROD_RECIPIENT,
    )
    defaults.update(overrides)
    settings = Settings(**defaults)
    assert settings.is_test_mode is False
    assert settings.env == "production"
    return settings


def test_email_test_origin_switches_away_from_prod_recipient(smtp_sink):
    """AC-6 (E-Mail): Testlauf-Herkunft schaltet auf die Test-Mailbox um --
    statt an den echten, normal geladenen mail_to zu senden."""
    EmailOutput(_prod_style_email_settings()).send("Betreff", "<p>Text</p>")

    assert len(smtp_sink.sent) == 1
    _, to_addrs = smtp_sink.sent[0]
    assert to_addrs == ("gregor-test@henemm.com",)
    assert PROD_RECIPIENT not in to_addrs


def test_email_production_origin_delivers_unchanged(smtp_sink, monkeypatch):
    """AC-6 (E-Mail, Regressionsschutz): Herkunft='production' gefaked ->
    unveraenderter Empfaenger, wie vor #1476."""
    monkeypatch.setattr(email_mod, "running_origin", lambda module_file: "production")

    EmailOutput(_prod_style_email_settings()).send("Betreff", "<p>Text</p>")

    assert smtp_sink.sent[0][1] == (PROD_RECIPIENT,)


class _HttpxPostSink:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, url, headers=None, data=None, timeout=None, **kwargs):
        self.calls.append({"headers": headers, "data": data})
        return httpx.Response(200, text="100")


@pytest.fixture
def sms_httpx_sink(monkeypatch) -> _HttpxPostSink:
    sink = _HttpxPostSink()
    monkeypatch.setattr(httpx, "post", sink)
    return sink


def _prod_style_sms_settings(**overrides) -> Settings:
    defaults = dict(seven_api_key="prod-key", sms_to=PROD_SMS_TO)
    defaults.update(overrides)
    settings = Settings(**defaults)
    assert settings.is_test_mode is False
    assert settings.env == "production"
    return settings


def test_sms_test_origin_switches_to_sandbox_key(sms_httpx_sink):
    """AC-6 (SMS): Testlauf-Herkunft erzwingt den Sandbox-Key -- der laut
    seven.io-Doku nie eine echte SMS sendet."""
    SMSOutput(_prod_style_sms_settings(seven_sandbox_key="sandbox-key")).send("x", "Text")

    assert sms_httpx_sink.calls[0]["headers"]["X-Api-Key"] == "sandbox-key"


def test_sms_test_origin_without_sandbox_key_hard_aborts(sms_httpx_sink):
    """AC-6 (SMS): keine Sandbox-Key konfiguriert -> harter Abbruch, kein POST."""
    with pytest.raises(OutputConfigError, match="1476"):
        SMSOutput(_prod_style_sms_settings(seven_sandbox_key=None)).send("x", "Text")

    assert sms_httpx_sink.calls == []


def test_sms_production_origin_delivers_unchanged(sms_httpx_sink, monkeypatch):
    """AC-6 (SMS, Regressionsschutz): Herkunft='production' gefaked ->
    unveraenderter Prod-Key, wie vor #1476."""
    monkeypatch.setattr(sms_mod, "running_origin", lambda module_file: "production")

    SMSOutput(_prod_style_sms_settings()).send("x", "Text")

    assert sms_httpx_sink.calls[0]["headers"]["X-Api-Key"] == "prod-key"


# ---------------------------------------------------------------------------
# Issue #1676 S2a, AC-7 — dieselbe Herkunftssperre fuer den VIERTEN Kanal
# (Premium-SMS/Garmin inReach). Diese Datei prueft die Sperre bis heute nur
# namentlich fuer EmailOutput/SMSOutput; ein neuer Kanal ohne Guards faellt der
# Suite sonst nicht auf (gemessener Befund, Kontextdokument "Existing Patterns").
#
# Gemessen wird hier am ECHTEN lokalen HTTP-Server statt am httpx-Sink oben:
# der `X-Api-Key` ist damit am tatsaechlich EINGEGANGENEN Request nachgewiesen,
# und "kein Aufruf" heisst "kein Byte auf der Leitung". Die bestehenden
# E-Mail-/SMS-Faelle bleiben unveraendert auf ihren Boundary-Sinks.
# ---------------------------------------------------------------------------

PREMIUM_REPLY_TO = "+4915799912345"


class _SevenIoStub:
    """Lokaler HTTP-Server (127.0.0.1), der die seven.io-POSTs entgegennimmt."""

    def __init__(self) -> None:
        self.received: list[dict] = []
        received = self.received

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                data = urllib.parse.parse_qs(self.rfile.read(length).decode())
                received.append({
                    "api_key": self.headers.get("X-Api-Key"),
                    "payload": {k: v[0] for k, v in data.items()},
                })
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"100")

            def log_message(self, *args):
                pass

        probe = socket.socket()
        probe.bind(("", 0))
        self.port = probe.getsockname()[1]
        probe.close()
        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def stop(self) -> None:
        self._server.shutdown()


@pytest.fixture()
def premium_sms_stub():
    stub = _SevenIoStub()
    yield stub
    stub.stop()


def _prod_style_premium_sms_settings(port: int, **overrides) -> Settings:
    defaults = dict(
        seven_api_key="prod-key",
        sms_gateway_url=f"http://127.0.0.1:{port}/api/sms",
        premium_sms_reply_to=PREMIUM_REPLY_TO,
        premium_sms_reply_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    settings = Settings(**defaults)
    assert settings.is_test_mode is False
    assert settings.env == "production"
    return settings


def test_premium_sms_test_origin_switches_to_sandbox_key(premium_sms_stub):
    """AC-7 (Premium-SMS): Testlauf-Herkunft — jeder pytest-Lauf in einem
    Arbeitsordner ist eine — erzwingt den Sandbox-Key, der laut seven.io-Doku
    nie eine echte SMS sendet."""
    from output.channels.premium_sms import PremiumSmsOutput

    settings = _prod_style_premium_sms_settings(
        premium_sms_stub.port, seven_sandbox_key="sandbox-key",
    )
    PremiumSmsOutput(settings).send("x", "Text")

    assert len(premium_sms_stub.received) == 1, (
        f"Erwartet genau EINEN POST, bekommen: {premium_sms_stub.received!r}"
    )
    assert premium_sms_stub.received[0]["api_key"] == "sandbox-key", (
        "Premium-SMS ging mit dem Prod-Key hinaus: "
        f"{premium_sms_stub.received[0]['api_key']!r}"
    )


def test_premium_sms_test_origin_without_sandbox_key_hard_aborts(premium_sms_stub):
    """AC-7 (Premium-SMS): kein Sandbox-Key konfiguriert -> harter Abbruch,
    BEVOR ein HTTP-Aufruf stattfindet."""
    from output.channels.premium_sms import PremiumSmsOutput

    settings = _prod_style_premium_sms_settings(
        premium_sms_stub.port, seven_sandbox_key=None,
    )
    with pytest.raises(OutputConfigError, match="1476"):
        PremiumSmsOutput(settings).send("x", "Text")

    assert premium_sms_stub.received == [], (
        f"Trotz Abbruch ging etwas hinaus: {premium_sms_stub.received!r}"
    )
