"""
TDD: Tests fuer HTML-E-Mail-Versand (Subscription-Pipeline + echter Stalwart-E2E).

Mocks sind in diesem Projekt verboten (siehe CLAUDE.md "KEINE MOCKED TESTS!").
Diese Datei enthaelt nur zwei Tests:

- ``TestSubscriptionEmailGeneration``: prueft die Generierungs-Pipeline ohne Versand
  (schnell, ohne Netz fuer den SMTP-Teil — load_all_locations() macht ggf. einen
  echten Forecast-Call, aber kein SMTP).
- ``TestRealStalwartE2E``: echter End-to-End-Test (Stalwart SMTP + IMAP). Per
  ``@pytest.mark.email`` standardmaessig deselected.

Frueher gab es zusaetzlich ``TestHTMLEmailFormat``, ``TestEndToEndEmailSending``
und ``TestEmailRetryMechanism``. Diese wurden in Issue #201 ersatzlos entfernt:
ihre Coverage steckt 1:1 in ``TestRealStalwartE2E::test_real_gmail_e2e_html_email``
(echter Versand statt fake SMTP-Server).
"""
import os
import pytest
from datetime import datetime, date
from email import message_from_string

from app.user import SavedLocation, CompareSubscription, ComparisonResult, LocationResult
from output.renderers.comparison import render_comparison_html
from services.compare_subscription import run_comparison_for_subscription


class TestSubscriptionEmailGeneration:
    """Test that subscription email generation produces HTML."""

    @pytest.fixture
    def sample_subscription(self) -> CompareSubscription:
        """Create a sample subscription."""
        return CompareSubscription(
            id="test-sub",
            name="Test Subscription",
            locations=["*"],
            forecast_hours=48,
            time_window_start=9,
            time_window_end=16,
            schedule="daily_morning",
            include_hourly=True,
            top_n=3,
        )

    @pytest.fixture
    def sample_locations(self) -> list:
        """Create sample locations."""
        return [
            SavedLocation(
                id="loc1",
                name="Skigebiet Eins",
                lat=47.0,
                lon=11.0,
                elevation_m=2000,
            ),
            SavedLocation(
                id="loc2",
                name="Skigebiet Zwei",
                lat=47.1,
                lon=11.1,
                elevation_m=2200,
            ),
        ]

    def test_subscription_generates_html_email_with_real_data(self, sample_subscription):
        """run_comparison_for_subscription must return HTML and text body with real locations."""
        from app.loader import load_all_locations

        # Load real locations from disk
        locations = load_all_locations()
        if not locations:
            pytest.skip("No locations configured")

        # Run with real data (network call)
        # SPEC: docs/specs/compare_email.md v4.2 - Multipart Email
        # Issue #456: 4-tuple incl. winner_name
        subject, html_body, text_body, _winner_name = run_comparison_for_subscription(sample_subscription, locations[:2])

        assert "<!DOCTYPE html>" in html_body, \
            f"Subscription email must be HTML. Got: {html_body[:200]}"
        # Renderer schreibt <table class="matrix-table" ...> mit Attributen
        # (Issue #355): "<table " (mit Space) statt nacktem "<table>".
        assert "<table " in html_body.lower(), \
            "Subscription email must contain HTML tables"
        assert "======" not in html_body, \
            "HTML email should not contain ASCII table borders"

        # Check plain-text body
        assert text_body, "Plain-text body must not be empty"
        assert "⛷️ SKIGEBIETE-VERGLEICH" in text_body, \
            "Plain-text body must contain header"


@pytest.mark.email
class TestRealStalwartE2E:
    """
    ECHTER E2E Test: Sendet via SMTP, ruft via IMAP ab, analysiert.

    Kein Mocking - testet was WIRKLICH passiert.
    """

    def test_real_gmail_e2e_html_email(self):
        """
        Echter E2E Test:
        1. Sende E-Mail via Stalwart SMTP
        2. Rufe E-Mail via Stalwart IMAP aus INBOX ab
        3. Analysiere MIME-Struktur
        4. Verifiziere HTML-Inhalt
        """
        import imaplib
        import time
        import email

        from app.config import Settings
        from app.loader import load_all_locations, load_compare_subscriptions
        from outputs.email import EmailOutput

        # 1. Lade echte Daten (Stalwart fuer Tests, spart Resend-Quota)
        settings = Settings().for_testing()
        if not settings.can_send_email():
            pytest.skip("SMTP nicht konfiguriert")

        subs = load_compare_subscriptions()
        if not subs:
            pytest.skip("Keine Subscriptions")

        locations = load_all_locations()
        if not locations:
            pytest.skip("Keine Locations")

        # 2. Generiere E-Mail
        # SPEC: docs/specs/compare_email.md v4.2 - Multipart Email
        sub = subs[0]
        # Issue #456: 4-tuple incl. winner_name
        subject, html_body, text_body, _winner_name = run_comparison_for_subscription(sub, locations)

        # Unique Subject für Suche
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        test_subject = f"[TEST-{unique_id}] {subject}"

        # 3. Sende via SMTP mit Multipart
        email_output = EmailOutput(settings)
        email_output.send(test_subject, html_body, plain_text_body=text_body)

        print(f"\n>>> E-Mail gesendet: {test_subject}")

        # 4. Warte auf E-Mail-Zustellung
        time.sleep(5)

        # 5. Verbinde via IMAP (Stalwart)
        imap_host = settings.imap_host or settings.smtp_host
        imap_user = settings.imap_user or settings.smtp_user
        imap_pass = settings.imap_pass or settings.smtp_pass
        imap = imaplib.IMAP4_SSL(imap_host, settings.imap_port)
        imap.login(imap_user, imap_pass)

        # 6. Öffne Posteingang
        status, _ = imap.select('INBOX')

        # 7. Suche nach der E-Mail
        _, data = imap.search(None, f'SUBJECT "{unique_id}"')
        msg_ids = data[0].split()

        assert len(msg_ids) > 0, f"E-Mail mit ID {unique_id} nicht in Gesendet gefunden!"

        # 8. Hole die neueste
        latest_id = msg_ids[-1]
        _, msg_data = imap.fetch(latest_id, "(RFC822)")

        # 9. Parse MIME
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        # Speichere für Debugging
        os.makedirs("/tmp/gregor_email_test", exist_ok=True)
        with open("/tmp/gregor_email_test/imap_retrieved.eml", "wb") as f:
            f.write(raw_email)

        print(f">>> E-Mail abgerufen, Content-Type: {msg.get_content_type()}")

        # 10. ASSERTIONS

        # A) Muss multipart/alternative sein
        content_type = msg.get_content_type()
        assert content_type == "multipart/alternative", \
            f"E-Mail muss multipart/alternative sein, ist aber: {content_type}"

        # B) Finde HTML und Plain-Text Parts
        html_part = None
        plain_part = None

        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/html":
                html_part = part.get_payload(decode=True).decode("utf-8")
            elif ct == "text/plain":
                plain_part = part.get_payload(decode=True).decode("utf-8")

        # C) HTML-Teil muss existieren
        assert html_part is not None, "Kein text/html Teil gefunden!"

        # D) HTML muss echtes HTML sein
        assert "<!DOCTYPE html>" in html_part, \
            f"HTML-Teil beginnt nicht mit DOCTYPE: {html_part[:200]}"
        assert "<table>" in html_part.lower(), \
            "HTML-Teil enthält keine <table> Tags"
        assert "<style>" in html_part, \
            "HTML-Teil enthält kein CSS"

        # E) Plain-Text darf KEIN CSS enthalten (der alte Bug)
        assert plain_part is not None, "Kein text/plain Teil gefunden!"
        assert "font-family" not in plain_part, \
            f"Plain-Text enthält CSS! Anfang: {plain_part[:200]}"
        assert "border-collapse" not in plain_part, \
            "Plain-Text enthält CSS (border-collapse)"

        # F) HTML darf keine ASCII-Tabellen haben
        assert "======" not in html_part, \
            "HTML enthält ASCII-Borders (===)"
        assert "------" not in html_part, \
            "HTML enthält ASCII-Borders (---)"

        print(">>> ALLE CHECKS BESTANDEN!")

        # Cleanup: Lösche Test-E-Mail
        imap.store(latest_id, "+FLAGS", "\\Deleted")
        imap.expunge()
        imap.logout()
