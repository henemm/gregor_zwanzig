"""TDD RED: Bug Fix — Inbound Email Reader Feedback Loop

Stalwart kopiert gesendete E-Mails zurück in den Posteingang.
Der Reader darf diese NICHT als Befehle verarbeiten, da ihr Absender
die System-Sendeadresse (mail_from) ist — kein echter Nutzer.

Issue #2143 (SECURITY-FIX v1.5): `_authorize()` bekam eine dritte Signatur-
Position `msg` (Authentication-Results-Pruefung) sowie eine
`email_verified_at`-Pflicht. Diese Datei testet weiterhin ausschliesslich
die URSPRUENGLICHE Adress-Logik (mail_from/mail_to/inbound_address) — die
NEUEN Pruefungen (SPF/DKIM, Verifizierung) werden ueber `_settings()`/`_msg()`
bewusst IMMER erfuellt gehalten, damit diese Tests isoliert die Adress-Logik
pruefen. Die neuen Pruefungen selbst sind in
`test_inbound_email_sender_authentication.py` (Ende-zu-Ende) und
`test_authentication_results_parsing.py` (Parser/SPF-DKIM-Unit) abgedeckt.

SPEC: docs/specs/modules/bug_inbound_email_loop.md;
      docs/specs/modules/inbound_command_channels.md v1.5 (#2143, _authorize-Signatur)
"""
import email

from app.config import Settings
from services.inbound_email_reader import InboundEmailReader
from tests.fixtures.authentication_results_fixtures import AR_PASS, TEST_AUTHSERV_ID

_VALID_MSG = email.message_from_bytes(
    f"Authentication-Results: {AR_PASS}\r\n\r\nstatus".encode("utf-8")
)


def _settings(mail_to: str, mail_from: str, inbound_address: str | None = None) -> Settings:
    return Settings(
        mail_to=mail_to,
        mail_from=mail_from,
        inbound_address=inbound_address,
        email_verified_at="2026-01-01T00:00:00Z",
        mail_server_hostname=TEST_AUTHSERV_ID,
    )


class TestAuthorizeRejectsSytemSender:
    """AC-1: mail_from (System-Sendeadresse) ist KEIN erlaubter Absender."""

    def test_mail_from_is_rejected(self):
        """System sendet von gregor_zwanzig@henemm.com — darf nicht als Befehlsgeber akzeptiert werden."""
        reader = InboundEmailReader()
        settings = _settings(
            mail_to="gregor-test@henemm.com",
            mail_from="gregor_zwanzig@henemm.com",
        )
        # BUG: aktuell gibt _authorize True zurück, weil mail_from in allowed steht
        # Nach Fix muss False zurückkommen
        assert reader._authorize("gregor_zwanzig@henemm.com", settings, _VALID_MSG) is False

    def test_mail_from_variation_rejected(self):
        """Auch andere mail_from-Adressen dürfen nicht autorisiert werden."""
        reader = InboundEmailReader()
        settings = _settings(
            mail_to="user@example.com",
            mail_from="noreply@myapp.com",
        )
        assert reader._authorize("noreply@myapp.com", settings, _VALID_MSG) is False


class TestAuthorizeAcceptsMailTo:
    """AC-2: mail_to (Nutzer-Empfangsadresse) ist erlaubter Absender."""

    def test_mail_to_is_authorized(self):
        """Nutzer schickt Befehl von seiner Empfangs-Adresse — muss akzeptiert werden."""
        reader = InboundEmailReader()
        settings = _settings(
            mail_to="gregor-test@henemm.com",
            mail_from="gregor_zwanzig@henemm.com",
        )
        assert reader._authorize("gregor-test@henemm.com", settings, _VALID_MSG) is True

    def test_mail_to_case_insensitive(self):
        """Groß-/Kleinschreibung ist irrelevant."""
        reader = InboundEmailReader()
        settings = _settings(
            mail_to="User@Example.COM",
            mail_from="system@app.com",
        )
        assert reader._authorize("user@example.com", settings, _VALID_MSG) is True


class TestAuthorizeRejectsUnknown:
    """AC-3: Unbekannte Adressen werden abgelehnt."""

    def test_unknown_address_rejected(self):
        reader = InboundEmailReader()
        settings = _settings(
            mail_to="user@example.com",
            mail_from="system@app.com",
        )
        assert reader._authorize("attacker@evil.com", settings, _VALID_MSG) is False


class TestAuthorizeInboundAddress:
    """AC-4: inbound_address (Plus-Adressierung) wird akzeptiert — keine Regression."""

    def test_inbound_address_authorized(self):
        reader = InboundEmailReader()
        settings = _settings(
            mail_to="user@example.com",
            mail_from="system@app.com",
            inbound_address="user+gregor@example.com",
        )
        assert reader._authorize("user+gregor@example.com", settings, _VALID_MSG) is True

    def test_inbound_address_does_not_accept_mail_from(self):
        """inbound_address ändert nichts daran, dass mail_from abgelehnt wird."""
        reader = InboundEmailReader()
        settings = _settings(
            mail_to="user@example.com",
            mail_from="system@app.com",
            inbound_address="user+gregor@example.com",
        )
        assert reader._authorize("system@app.com", settings, _VALID_MSG) is False


class TestAuthorizeProductionScenario:
    """Produktionsszenario: inbound_address == mail_from → Feedback-Loop unterbunden."""

    def test_inbound_address_equals_mail_from_rejected(self):
        """GZ_INBOUND_ADDRESS=gregor_zwanzig@henemm.com == GZ_MAIL_FROM → abgelehnt."""
        reader = InboundEmailReader()
        settings = _settings(
            mail_to="gregor-test@henemm.com",
            mail_from="gregor_zwanzig@henemm.com",
            inbound_address="gregor_zwanzig@henemm.com",  # gleich wie mail_from
        )
        # Diese E-Mail ist eine Stalwart-Kopie der gesendeten Mail
        # Sie darf NICHT verarbeitet werden
        assert reader._authorize("gregor_zwanzig@henemm.com", settings, _VALID_MSG) is False

    def test_inbound_address_different_from_mail_from_accepted(self):
        """Wenn inbound_address eine echte User-Adresse ist, bleibt sie erlaubt."""
        reader = InboundEmailReader()
        settings = _settings(
            mail_to="user@example.com",
            mail_from="system@app.com",
            inbound_address="user+commands@example.com",  # verschieden von mail_from
        )
        assert reader._authorize("user+commands@example.com", settings, _VALID_MSG) is True

    def test_mail_to_none_returns_false(self):
        """Wenn mail_to nicht gesetzt ist (None), wird alles abgelehnt."""
        reader = InboundEmailReader()
        # Settings ohne mail_to
        settings = Settings(
            mail_to=None, mail_from="system@app.com",
            email_verified_at="2026-01-01T00:00:00Z", mail_server_hostname=TEST_AUTHSERV_ID,
        )
        assert reader._authorize("anyone@example.com", settings, _VALID_MSG) is False

    def test_mail_from_rejected_even_when_equals_mail_to(self):
        """Fallback: user.json fehlt → base-env hat mail_to==mail_from → mail_from trotzdem abgelehnt."""
        reader = InboundEmailReader()
        # Simuliert: user.json nicht vorhanden, GZ_MAIL_TO==GZ_MAIL_FROM aus .env
        settings = _settings(
            mail_to="gregor_zwanzig@henemm.com",   # gleich wie mail_from (kein Override)
            mail_from="gregor_zwanzig@henemm.com",
        )
        # Expliziter mail_from-Guard macht den Schutz unabhängig von user.json
        assert reader._authorize("gregor_zwanzig@henemm.com", settings, _VALID_MSG) is False


class TestAuthorizeRequiresVerificationAndSpfDkim:
    """#2143 NEU: email_verified_at + SPF/DKIM sind zusaetzliche Pflichtbedingungen,
    auch wenn die Adress-Logik oben bereits durchgelaufen waere."""

    def test_missing_email_verified_at_rejects_otherwise_valid_sender(self):
        reader = InboundEmailReader()
        settings = Settings(
            mail_to="user@example.com", mail_from="system@app.com",
            email_verified_at=None, mail_server_hostname=TEST_AUTHSERV_ID,
        )
        assert reader._authorize("user@example.com", settings, _VALID_MSG) is False

    def test_missing_spf_dkim_header_rejects_otherwise_valid_sender(self):
        reader = InboundEmailReader()
        settings = _settings(mail_to="user@example.com", mail_from="system@app.com")
        no_auth_msg = email.message_from_bytes(b"\r\n\r\nstatus")
        assert reader._authorize("user@example.com", settings, no_auth_msg) is False
