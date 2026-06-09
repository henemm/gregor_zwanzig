"""
TDD RED: Bug Fix — Inbound Email Reader Feedback Loop

Stalwart kopiert gesendete E-Mails zurück in den Posteingang.
Der Reader darf diese NICHT als Befehle verarbeiten, da ihr Absender
die System-Sendeadresse (mail_from) ist — kein echter Nutzer.

SPEC: docs/specs/modules/bug_inbound_email_loop.md
"""
from app.config import Settings
from services.inbound_email_reader import InboundEmailReader


def _settings(mail_to: str, mail_from: str, inbound_address: str | None = None) -> Settings:
    return Settings(
        mail_to=mail_to,
        mail_from=mail_from,
        inbound_address=inbound_address,
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
        assert reader._authorize("gregor_zwanzig@henemm.com", settings) is False

    def test_mail_from_variation_rejected(self):
        """Auch andere mail_from-Adressen dürfen nicht autorisiert werden."""
        reader = InboundEmailReader()
        settings = _settings(
            mail_to="user@example.com",
            mail_from="noreply@myapp.com",
        )
        assert reader._authorize("noreply@myapp.com", settings) is False


class TestAuthorizeAcceptsMailTo:
    """AC-2: mail_to (Nutzer-Empfangsadresse) ist erlaubter Absender."""

    def test_mail_to_is_authorized(self):
        """Nutzer schickt Befehl von seiner Empfangs-Adresse — muss akzeptiert werden."""
        reader = InboundEmailReader()
        settings = _settings(
            mail_to="gregor-test@henemm.com",
            mail_from="gregor_zwanzig@henemm.com",
        )
        assert reader._authorize("gregor-test@henemm.com", settings) is True

    def test_mail_to_case_insensitive(self):
        """Groß-/Kleinschreibung ist irrelevant."""
        reader = InboundEmailReader()
        settings = _settings(
            mail_to="User@Example.COM",
            mail_from="system@app.com",
        )
        assert reader._authorize("user@example.com", settings) is True


class TestAuthorizeRejectsUnknown:
    """AC-3: Unbekannte Adressen werden abgelehnt."""

    def test_unknown_address_rejected(self):
        reader = InboundEmailReader()
        settings = _settings(
            mail_to="user@example.com",
            mail_from="system@app.com",
        )
        assert reader._authorize("attacker@evil.com", settings) is False


class TestAuthorizeInboundAddress:
    """AC-4: inbound_address (Plus-Adressierung) wird akzeptiert — keine Regression."""

    def test_inbound_address_authorized(self):
        reader = InboundEmailReader()
        settings = _settings(
            mail_to="user@example.com",
            mail_from="system@app.com",
            inbound_address="user+gregor@example.com",
        )
        assert reader._authorize("user+gregor@example.com", settings) is True

    def test_inbound_address_does_not_accept_mail_from(self):
        """inbound_address ändert nichts daran, dass mail_from abgelehnt wird."""
        reader = InboundEmailReader()
        settings = _settings(
            mail_to="user@example.com",
            mail_from="system@app.com",
            inbound_address="user+gregor@example.com",
        )
        assert reader._authorize("system@app.com", settings) is False


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
        assert reader._authorize("gregor_zwanzig@henemm.com", settings) is False

    def test_inbound_address_different_from_mail_from_accepted(self):
        """Wenn inbound_address eine echte User-Adresse ist, bleibt sie erlaubt."""
        reader = InboundEmailReader()
        settings = _settings(
            mail_to="user@example.com",
            mail_from="system@app.com",
            inbound_address="user+commands@example.com",  # verschieden von mail_from
        )
        assert reader._authorize("user+commands@example.com", settings) is True

    def test_mail_to_none_returns_false(self):
        """Wenn mail_to nicht gesetzt ist (None), wird alles abgelehnt."""
        reader = InboundEmailReader()
        # Settings ohne mail_to
        settings = Settings(mail_to=None, mail_from="system@app.com")
        assert reader._authorize("anyone@example.com", settings) is False

    def test_mail_from_rejected_even_when_equals_mail_to(self):
        """Fallback: user.json fehlt → base-env hat mail_to==mail_from → mail_from trotzdem abgelehnt."""
        reader = InboundEmailReader()
        # Simuliert: user.json nicht vorhanden, GZ_MAIL_TO==GZ_MAIL_FROM aus .env
        settings = _settings(
            mail_to="gregor_zwanzig@henemm.com",   # gleich wie mail_from (kein Override)
            mail_from="gregor_zwanzig@henemm.com",
        )
        # Expliziter mail_from-Guard macht den Schutz unabhängig von user.json
        assert reader._authorize("gregor_zwanzig@henemm.com", settings) is False
