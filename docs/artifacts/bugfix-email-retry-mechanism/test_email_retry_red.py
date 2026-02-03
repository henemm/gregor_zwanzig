"""
TDD RED: Tests für automatische Wiederholungsversuche bei E-Mail-Versand.

Diese Tests MÜSSEN FEHLSCHLAGEN, da der Retry-Mechanismus noch nicht
implementiert ist.

SPEC: docs/specs/bugfix/email_retry_mechanism_spec.md v1.0
"""
import pytest
from unittest.mock import Mock, patch


class TestEmailRetryMechanism:
    """TDD RED: Tests für automatische Wiederholungsversuche."""

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
        GIVEN: EmailOutput ohne Retry-Mechanismus
        WHEN: send() stößt 2x auf DNS-Fehler, dann Erfolg
        THEN: Sollte nach Retries erfolgreich sein
        EXPECTED: FAIL (wird beim ersten Fehler abbrechen)
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
            with patch("time.sleep"):
                email_output = EmailOutput(mock_settings)
                # Should succeed after 2 retries (but will fail on first attempt)
                email_output.send("Test Subject", "Test Body")

        assert attempt_count[0] == 3, \
            f"Should have made 3 attempts (2 retries), but made {attempt_count[0]}"

    def test_exponential_backoff_timing(self, mock_settings):
        """
        GIVEN: EmailOutput ohne Retry-Mechanismus
        WHEN: send() schlägt mit Netzwerk-Fehlern fehl
        THEN: Sollte 5s, 15s, 30s zwischen Versuchen warten
        EXPECTED: FAIL (keine Wartezeiten, sofortiger Abbruch)
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
