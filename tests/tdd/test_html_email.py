"""
TDD-RED: Test that email output is proper HTML, not plain text.

This test should FAIL if emails are being sent as plain text
with space-aligned tables instead of proper HTML tables.
"""
import os
import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch, Mock
from email import message_from_string

from app.user import SavedLocation, CompareSubscription, ComparisonResult, LocationResult
from web.pages.compare import render_comparison_html, run_comparison_for_subscription


class TestHTMLEmailFormat:
    """Tests to verify email is HTML formatted, not plain text."""

    @pytest.fixture
    def sample_location(self) -> SavedLocation:
        """Create a sample location for testing."""
        return SavedLocation(
            id="test-loc",
            name="Test Skigebiet",
            lat=47.0,
            lon=11.0,
            elevation_m=2000,
        )

    @pytest.fixture
    def sample_comparison_result(self, sample_location) -> ComparisonResult:
        """Create sample ComparisonResult for testing."""
        from datetime import date, datetime
        loc_result = LocationResult(
            location=sample_location,
            score=75,
            snow_depth_cm=120,
            snow_new_cm=15,
            wind_max=25,
            wind_chill_min=-8,
            sunny_hours=4,
            cloud_avg=40,
            hourly_data=[],
        )
        return ComparisonResult(
            locations=[loc_result],
            time_window=(9, 16),
            target_date=date.today(),
            created_at=datetime.now(),
        )

    def test_email_starts_with_doctype_html(self, sample_comparison_result):
        """Email must start with <!DOCTYPE html> - not plain text."""
        body = render_comparison_html(sample_comparison_result)

        assert body.strip().startswith("<!DOCTYPE html>"), \
            f"Email should start with <!DOCTYPE html>, but starts with: {body[:100]}"

    def test_email_contains_html_table_tags(self, sample_comparison_result):
        """Email must use <table> tags, not space-aligned text."""
        body = render_comparison_html(sample_comparison_result)

        assert "<table>" in body.lower(), "Email must contain <table> tags"
        assert "<tr>" in body.lower(), "Email must contain <tr> tags"
        assert "<td" in body.lower(), "Email must contain <td> tags"

    def test_email_contains_css_styling(self, sample_comparison_result):
        """Email must have CSS styles for proper formatting."""
        body = render_comparison_html(sample_comparison_result)

        assert "<style>" in body, "Email must contain <style> block"
        assert "font-family" in body, "Email must have font styling"

    def test_email_does_not_use_ascii_table_borders(self, sample_comparison_result):
        """Email must NOT use ASCII art for tables (===, ---, |)."""
        body = render_comparison_html(sample_comparison_result)

        # These are signs of plain-text table formatting
        assert "======" not in body, "Email should not use === for borders"
        assert "------" not in body, "Email should not use --- for borders"
        # Allow | in CSS but not as table borders
        lines = body.split("\n")
        table_border_lines = [l for l in lines if l.strip().startswith("|") or l.strip().endswith("|")]
        assert len(table_border_lines) == 0, \
            f"Email should not use | for table borders, found: {table_border_lines[:3]}"

    def test_email_has_proper_structure(self, sample_comparison_result):
        """Email must have proper HTML structure."""
        body = render_comparison_html(sample_comparison_result)

        assert "<html>" in body.lower(), "Email must have <html> tag"
        assert "<head>" in body.lower(), "Email must have <head> tag"
        assert "<body>" in body.lower(), "Email must have <body> tag"
        assert "</html>" in body.lower(), "Email must have closing </html> tag"

    def test_best_values_are_highlighted(self, sample_comparison_result):
        """Best values should be marked with CSS class."""
        body = render_comparison_html(sample_comparison_result)

        # Should use CSS class for best values, not asterisks
        assert 'class="best"' in body or "class='best'" in body, \
            "Best values should be marked with CSS class 'best'"
        assert body.count("*75*") == 0, "Should not use *value* for highlighting"


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
        # SPEC: docs/specs/compare_email.md v4.2 - Multipart Email returns 3 values
        subject, html_body, text_body = run_comparison_for_subscription(sample_subscription, locations[:2])

        assert "<!DOCTYPE html>" in html_body, \
            f"Subscription email must be HTML. Got: {html_body[:200]}"
        assert "<table>" in html_body.lower(), \
            "Subscription email must contain HTML tables"
        assert "======" not in html_body, \
            "HTML email should not contain ASCII table borders"

        # Check plain-text body
        assert text_body, "Plain-text body must not be empty"
        assert "⛷️ SKIGEBIETE-VERGLEICH" in text_body, \
            "Plain-text body must contain header"


class TestEndToEndEmailSending:
    """
    E2E Test: Full pipeline from subscription to SMTP send.

    Tests that the ACTUAL email sent via SMTP is:
    1. multipart/alternative (HTML + plain text)
    2. Contains proper HTML in the HTML part
    3. Contains proper tables, not ASCII art
    """

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings with SMTP config."""
        settings = Mock()
        settings.can_send_email.return_value = True
        settings.smtp_host = "smtp.test.com"
        settings.smtp_port = 587
        settings.smtp_user = "test@test.com"
        settings.smtp_pass = "password"
        settings.mail_to = "recipient@test.com"
        settings.mail_from = "sender@test.com"
        return settings

    def test_e2e_smtp_sends_multipart_html_email(self, mock_settings):
        """
        E2E: Full pipeline sends multipart/alternative email with HTML.

        This captures the ACTUAL SMTP message and verifies its structure.
        """
        from outputs.email import EmailOutput
        from app.loader import load_all_locations, load_compare_subscriptions

        # Capture the sent message
        sent_messages = []

        class MockSMTP:
            def __init__(self, host, port):
                self.host = host
                self.port = port

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def starttls(self):
                pass

            def login(self, user, password):
                pass

            def sendmail(self, from_addr, to_addrs, msg):
                sent_messages.append(msg)

        # Load real data
        subs = load_compare_subscriptions()
        if not subs:
            pytest.skip("No subscriptions configured")

        locations = load_all_locations()
        if not locations:
            pytest.skip("No locations configured")

        # Generate email content
        # SPEC: docs/specs/compare_email.md v4.2 - Multipart Email
        sub = subs[0]
        subject, html_body, text_body = run_comparison_for_subscription(sub, locations)

        # Send via EmailOutput with mocked SMTP
        with patch("smtplib.SMTP", MockSMTP):
            email_output = EmailOutput(mock_settings)
            email_output.send(subject, html_body, plain_text_body=text_body)

        # Verify email was sent
        assert len(sent_messages) == 1, "Expected exactly one email to be sent"

        # Parse the sent message
        msg = message_from_string(sent_messages[0])

        # Check MIME structure
        content_type = msg.get_content_type()
        assert content_type == "multipart/alternative", \
            f"Email must be multipart/alternative, got: {content_type}"

        # Get parts
        parts = list(msg.walk())

        # Find plain text and HTML parts
        plain_part = None
        html_part = None

        for part in parts:
            if part.get_content_type() == "text/plain":
                plain_part = part.get_payload(decode=True).decode("utf-8")
            elif part.get_content_type() == "text/html":
                html_part = part.get_payload(decode=True).decode("utf-8")

        # Verify both parts exist
        assert plain_part is not None, "Email must have plain text part"
        assert html_part is not None, "Email must have HTML part"

        # Verify HTML part is actual HTML
        assert "<!DOCTYPE html>" in html_part, \
            f"HTML part must start with DOCTYPE. Got: {html_part[:100]}"
        assert "<table>" in html_part.lower(), \
            "HTML part must contain <table> tags"
        assert "<style>" in html_part, \
            "HTML part must contain CSS styles"

        # Verify HTML does NOT use ASCII table formatting
        assert "======" not in html_part, \
            "HTML part should not use === for borders"
        assert "------" not in html_part, \
            "HTML part should not use --- for borders"

        # Verify plain text fallback exists but is different from HTML
        assert "<table>" not in plain_part.lower(), \
            "Plain text part should not contain HTML tags"

    def test_e2e_email_contains_all_data(self, mock_settings):
        """E2E: Verify email contains all expected data fields."""
        from outputs.email import EmailOutput
        from app.loader import load_all_locations, load_compare_subscriptions

        sent_messages = []

        class MockSMTP:
            def __init__(self, host, port):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def starttls(self):
                pass
            def login(self, user, password):
                pass
            def sendmail(self, from_addr, to_addrs, msg):
                sent_messages.append(msg)

        subs = load_compare_subscriptions()
        locations = load_all_locations()

        if not subs or not locations:
            pytest.skip("No test data")

        # SPEC: docs/specs/compare_email.md v4.2 - Multipart Email
        sub = subs[0]
        subject, html_body, text_body = run_comparison_for_subscription(sub, locations)

        with patch("smtplib.SMTP", MockSMTP):
            email_output = EmailOutput(mock_settings)
            email_output.send(subject, html_body, plain_text_body=text_body)

        msg = message_from_string(sent_messages[0])

        # Get HTML part
        html_part = None
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                html_part = part.get_payload(decode=True).decode("utf-8")
                break

        assert html_part is not None

        # Check for expected content
        assert "Empfehlung" in html_part or "empfehlung" in html_part.lower(), \
            "Email must contain recommendation"
        assert "Score" in html_part or "score" in html_part.lower(), \
            "Email must contain score"
        assert "Schnee" in html_part or "schnee" in html_part.lower(), \
            "Email must contain snow info"

        # Check for Wolkenlage (cloud situation) - MUST match Web UI
        assert "Wolkenlage" in html_part, \
            "Email must contain Wolkenlage row (identical to Web UI)"

        # Check hourly data (09:00 - 16:00)
        assert "09:00" in html_part, "Email must contain 09:00 hour"
        assert "16:00" in html_part, "Email must contain 16:00 hour"

    def test_e2e_plain_text_does_not_contain_css(self, mock_settings):
        """
        Regression test: Plain text fallback must NOT contain CSS code.

        Bug: The regex only stripped tags but left CSS content between
        <style>...</style> tags, resulting in garbage like:
        'body { font-family: -apple-system...'
        """
        from outputs.email import EmailOutput
        from app.loader import load_all_locations, load_compare_subscriptions

        sent_messages = []

        class MockSMTP:
            def __init__(self, host, port):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def starttls(self):
                pass
            def login(self, user, password):
                pass
            def sendmail(self, from_addr, to_addrs, msg):
                sent_messages.append(msg)

        subs = load_compare_subscriptions()
        locations = load_all_locations()

        if not subs or not locations:
            pytest.skip("No test data")

        # SPEC: docs/specs/compare_email.md v4.2 - Multipart Email
        sub = subs[0]
        subject, html_body, text_body = run_comparison_for_subscription(sub, locations)

        with patch("smtplib.SMTP", MockSMTP):
            email_output = EmailOutput(mock_settings)
            email_output.send(subject, html_body, plain_text_body=text_body)

        msg = message_from_string(sent_messages[0])

        # Get plain text part
        plain_part = None
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                plain_part = part.get_payload(decode=True).decode("utf-8")
                break

        assert plain_part is not None, "Email must have plain text part"

        # With explicit plain-text body, it should contain our structured format
        assert "⛷️ SKIGEBIETE-VERGLEICH" in plain_part, \
            "Plain text must contain our formatted header"

        # Must NOT contain CSS artifacts
        assert "font-family" not in plain_part, \
            "Plain text must not contain CSS (font-family)"
        assert "border-collapse" not in plain_part, \
            "Plain text must not contain CSS (border-collapse)"
        assert "background:" not in plain_part, \
            "Plain text must not contain CSS (background)"


class TestRealGmailE2E:
    """
    ECHTER E2E Test: Sendet via SMTP, ruft via IMAP ab, analysiert.

    Kein Mocking - testet was WIRKLICH passiert.
    """

    def test_real_gmail_e2e_html_email(self):
        """
        Echter E2E Test:
        1. Sende E-Mail via Gmail SMTP
        2. Rufe E-Mail via Gmail IMAP aus "Gesendet" ab
        3. Analysiere MIME-Struktur
        4. Verifiziere HTML-Inhalt
        """
        import imaplib
        import time
        import email
        from email.header import decode_header

        from app.config import Settings
        from app.loader import load_all_locations, load_compare_subscriptions
        from outputs.email import EmailOutput

        # 1. Lade echte Daten
        settings = Settings()
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
        subject, html_body, text_body = run_comparison_for_subscription(sub, locations)

        # Unique Subject für Suche
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        test_subject = f"[TEST-{unique_id}] {subject}"

        # 3. Sende via SMTP mit Multipart
        email_output = EmailOutput(settings)
        email_output.send(test_subject, html_body, plain_text_body=text_body)

        print(f"\n>>> E-Mail gesendet: {test_subject}")

        # 4. Warte auf Gmail-Sync
        time.sleep(5)

        # 5. Verbinde via IMAP
        imap = imaplib.IMAP4_SSL("imap.gmail.com")
        imap.login(settings.smtp_user, settings.smtp_pass)

        # 6. Öffne Gesendet-Ordner (Google Mail auf Deutsch)
        status, _ = imap.select('"[Google Mail]/Gesendet"')

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


class TestEmailRetryMechanism:
    """
    TDD GREEN: Tests für automatische Wiederholungsversuche bei E-Mail-Versand.

    SPEC: docs/specs/bugfix/email_retry_mechanism_spec.md v1.0
    RED Artifact: docs/artifacts/bugfix-email-retry-mechanism/test-red-output.txt
    """

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings with SMTP config."""
        settings = Mock()
        settings.can_send_email.return_value = True
        settings.smtp_host = "smtp.test.com"
        settings.smtp_port = 587
        settings.smtp_user = "test@test.com"
        settings.smtp_pass = "password"
        settings.mail_to = "recipient@test.com"
        settings.mail_from = "sender@test.com"
        return settings

    def test_temporary_dns_error_succeeds_after_retry(self, mock_settings):
        """
        TDD GREEN: Temporärer DNS-Fehler löst Retry aus.

        GIVEN: EmailOutput mit Retry-Mechanismus
        WHEN: send() stößt 2x auf DNS-Fehler, dann Erfolg
        THEN: Sollte nach Retries erfolgreich sein
        """
        from outputs.email import EmailOutput

        attempt_count = [0]

        class MockSMTP:
            def __init__(self, host, port):
                attempt_count[0] += 1
                if attempt_count[0] <= 2:
                    raise OSError(-5, "No address associated with hostname")
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def starttls(self):
                pass
            def login(self, user, password):
                pass
            def sendmail(self, from_addr, to_addrs, msg):
                pass

        with patch("smtplib.SMTP", MockSMTP):
            with patch("time.sleep"):  # Speed up test
                email_output = EmailOutput(mock_settings)
                # Should succeed after 2 retries
                email_output.send("Test Subject", "Test Body")

        assert attempt_count[0] == 3, \
            f"Should have made 3 attempts (2 retries), but made {attempt_count[0]}"

    def test_exponential_backoff_timing(self, mock_settings):
        """
        TDD GREEN: Exponential Backoff wartet 5s, 15s, 30s.

        GIVEN: EmailOutput mit Retry-Mechanismus
        WHEN: send() schlägt mit Netzwerk-Fehlern fehl
        THEN: Sollte 5s, 15s, 30s zwischen Versuchen warten
        """
        from outputs.email import EmailOutput
        from outputs.base import OutputError

        sleep_calls = []

        class MockSMTP:
            def __init__(self, host, port):
                raise OSError(-5, "DNS error")

        with patch("smtplib.SMTP", MockSMTP):
            with patch("time.sleep") as mock_sleep:
                mock_sleep.side_effect = lambda x: sleep_calls.append(x)

                email_output = EmailOutput(mock_settings)
                with pytest.raises(OutputError):
                    email_output.send("Test Subject", "Test Body")

        assert sleep_calls == [5, 15, 30], \
            f"Expected backoff [5, 15, 30], got {sleep_calls}"
