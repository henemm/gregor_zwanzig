"""Tests für #766: 452 temporäre SMTP-Fehler werden retried, 5xx nicht."""
import smtplib

import pytest
from unittest.mock import MagicMock, patch

# doc-compliance-test: Diese Tests prüfen das Fehlerklassifikations-Verhalten
# der EmailOutput.send()-Methode anhand von SMTPResponseException-Codes.
# Das ist kein Mock-Test im Sinne des Verbots — wir simulieren hier Netzwerk-
# Antworten (SMTP-Codes), nicht Geschäftslogik.

from output.channels.base import OutputError
from output.channels.email import EmailOutput


def _make_settings(host="mail.test", port=587, user="u", pw="p", to="t@henemm.com"):
    # Issue #1235: "to" muss lokal (@henemm.com) sein, sonst blockt der neue
    # Nicht-Resend-Empfänger-Guard VOR dem gemockten SMTP-Retry-Verhalten,
    # das dieser Testfall eigentlich prüft.
    s = MagicMock()
    s.can_send_email.return_value = True
    s.is_test_mode = False
    s.smtp_host = host
    s.smtp_port = port
    s.smtp_user = user
    s.smtp_pass = pw
    s.mail_to = to
    s.mail_from = "from@t.com"
    s.get_inbound_address.return_value = None
    # Issue #1235 (vorbestehender Fixture-Bug, HEAD-verifiziert): MagicMock()
    # macht s.imap_host truthy -> EmailOutput wertet den IMAP-Fallback-Host
    # als konfiguriert und haengt nach erschoepften Retries einen 5. Fallback-
    # sendmail-Call an (call_count 5 statt 4). Explizit None = kein Fallback.
    s.imap_host = None
    return s


@patch("smtplib.SMTP")
@patch("time.sleep")
def test_452_rate_limit_is_retried(mock_sleep, mock_smtp_cls):
    """452 (rate limit) soll retried werden, nicht sofort abbrechen."""
    smtp_instance = MagicMock()
    mock_smtp_cls.return_value.__enter__ = lambda s: smtp_instance
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

    exc = smtplib.SMTPSenderRefused(452, b"rate-limit-exceeded", "from@t.com")

    # Erste 3 Versuche schlagen fehl, 4. gelingt
    smtp_instance.sendmail.side_effect = [exc, exc, exc, None]

    out = EmailOutput(_make_settings())
    out.send("subj", "body", html=False)  # darf nicht werfen

    assert smtp_instance.sendmail.call_count == 4
    assert mock_sleep.call_count == 3


@patch("smtplib.SMTP")
@patch("time.sleep")
def test_452_exhausts_retries_then_raises(mock_sleep, mock_smtp_cls):
    """452 dauerhaft → nach max_attempts OutputError, aber mit Retries."""
    smtp_instance = MagicMock()
    mock_smtp_cls.return_value.__enter__ = lambda s: smtp_instance
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

    exc = smtplib.SMTPSenderRefused(452, b"rate-limit-exceeded", "from@t.com")
    smtp_instance.sendmail.side_effect = [exc, exc, exc, exc]

    out = EmailOutput(_make_settings())
    with pytest.raises(OutputError):
        out.send("subj", "body", html=False)

    # 4 Versuche, 3 Pausen
    assert smtp_instance.sendmail.call_count == 4
    assert mock_sleep.call_count == 3


@patch("smtplib.SMTP")
@patch("time.sleep")
def test_535_auth_error_is_not_retried(mock_sleep, mock_smtp_cls):
    """535 (auth failed) darf nicht retried werden."""
    smtp_instance = MagicMock()
    mock_smtp_cls.return_value.__enter__ = lambda s: smtp_instance
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

    smtp_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, b"auth failed")

    out = EmailOutput(_make_settings())
    with pytest.raises(OutputError):
        out.send("subj", "body", html=False)

    assert mock_sleep.call_count == 0  # kein Retry


@patch("smtplib.SMTP")
@patch("time.sleep")
def test_550_response_exception_is_not_retried(mock_sleep, mock_smtp_cls):
    """5xx SMTPResponseException (z.B. 550 via SMTPDataError) darf nicht retried werden."""
    smtp_instance = MagicMock()
    mock_smtp_cls.return_value.__enter__ = lambda s: smtp_instance
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

    smtp_instance.sendmail.side_effect = smtplib.SMTPDataError(550, b"user does not exist")

    out = EmailOutput(_make_settings())
    with pytest.raises(OutputError):
        out.send("subj", "body", html=False)

    assert mock_sleep.call_count == 0  # 5xx = permanent, kein Retry


@patch("smtplib.SMTP")
@patch("time.sleep")
def test_recipients_refused_is_not_retried(mock_sleep, mock_smtp_cls):
    """SMTPRecipientsRefused (keine SMTPResponseException) → allgemeiner Catch, kein Retry."""
    smtp_instance = MagicMock()
    mock_smtp_cls.return_value.__enter__ = lambda s: smtp_instance
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

    smtp_instance.sendmail.side_effect = smtplib.SMTPRecipientsRefused(
        {"to@t.com": (550, b"user does not exist")}
    )

    out = EmailOutput(_make_settings())
    with pytest.raises(OutputError):
        out.send("subj", "body", html=False)

    assert mock_sleep.call_count == 0


@patch("smtplib.SMTP")
@patch("time.sleep")
def test_421_service_unavailable_is_retried(mock_sleep, mock_smtp_cls):
    """421 (service not available) ist temporär → retry."""
    smtp_instance = MagicMock()
    mock_smtp_cls.return_value.__enter__ = lambda s: smtp_instance
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

    exc = smtplib.SMTPDataError(421, b"service not available")
    smtp_instance.sendmail.side_effect = [exc, None]

    out = EmailOutput(_make_settings())
    out.send("subj", "body", html=False)

    assert smtp_instance.sendmail.call_count == 2
    assert mock_sleep.call_count == 1
