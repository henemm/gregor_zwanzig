"""Tests for output channels."""
from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from outputs.base import (
    OutputChannel,
    OutputError,
    OutputConfigError,
    NullOutput,
    get_channel,
)
from outputs.console import ConsoleOutput
from outputs.email import EmailOutput


class TestOutputChannelProtocol:
    """Tests for OutputChannel protocol compliance."""

    def test_console_implements_protocol(self):
        """ConsoleOutput implements OutputChannel protocol."""
        output = ConsoleOutput()
        assert isinstance(output, OutputChannel)

    def test_null_implements_protocol(self):
        """NullOutput implements OutputChannel protocol."""
        output = NullOutput()
        assert isinstance(output, OutputChannel)


class TestConsoleOutput:
    """Tests for ConsoleOutput."""

    def test_console_name(self):
        """ConsoleOutput has correct name."""
        output = ConsoleOutput()
        assert output.name == "console"

    def test_console_send(self, capsys):
        """ConsoleOutput prints to stdout."""
        output = ConsoleOutput()
        output.send("Test Subject", "Test body content")

        captured = capsys.readouterr()
        assert "Test Subject" in captured.out
        assert "Test body content" in captured.out


class TestNullOutput:
    """Tests for NullOutput."""

    def test_null_name(self):
        """NullOutput has correct name."""
        output = NullOutput()
        assert output.name == "none"

    def test_null_send_does_nothing(self, capsys):
        """NullOutput send does nothing."""
        output = NullOutput()
        output.send("Subject", "Body")

        captured = capsys.readouterr()
        assert captured.out == ""


class TestEmailOutput:
    """Tests for EmailOutput."""

    def _create_email_settings(self):
        """Create settings with complete email config."""
        return Settings(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="user@example.com",
            smtp_pass="secret",
            mail_to="recipient@example.com",
        )

    def test_email_requires_config(self):
        """EmailOutput raises if config incomplete."""
        settings = Settings()  # No SMTP config
        with pytest.raises(OutputConfigError) as exc_info:
            EmailOutput(settings)
        assert "SMTP" in str(exc_info.value)

    def test_email_name(self):
        """EmailOutput has correct name."""
        settings = self._create_email_settings()
        output = EmailOutput(settings)
        assert output.name == "email"

    @patch("outputs.email.smtplib.SMTP")
    def test_email_send(self, mock_smtp):
        """EmailOutput sends via SMTP."""
        settings = self._create_email_settings()
        output = EmailOutput(settings)

        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        output.send("Test Subject", "Test body")

        mock_smtp.assert_called_once_with("smtp.example.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.sendmail.assert_called_once()


class TestChannelFactory:
    """Tests for get_channel factory."""

    def test_get_channel_console(self):
        """get_channel returns ConsoleOutput for 'console'."""
        settings = Settings()
        channel = get_channel("console", settings)
        assert isinstance(channel, ConsoleOutput)

    def test_get_channel_none(self):
        """get_channel returns NullOutput for 'none'."""
        settings = Settings()
        channel = get_channel("none", settings)
        assert isinstance(channel, NullOutput)

    def test_get_channel_unknown_raises(self):
        """get_channel raises for unknown channel."""
        settings = Settings()
        with pytest.raises(ValueError) as exc_info:
            get_channel("unknown", settings)
        assert "unknown" in str(exc_info.value).lower()


class TestOutputErrors:
    """Tests for output error classes."""

    def test_output_error_formatting(self):
        """OutputError formats message with channel name."""
        error = OutputError("email", "Connection failed")
        assert "[email]" in str(error)
        assert "Connection failed" in str(error)

    def test_output_config_error(self):
        """OutputConfigError inherits from OutputError."""
        error = OutputConfigError("email", "Missing host")
        assert isinstance(error, OutputError)
