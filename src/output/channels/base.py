"""
Output channel protocol and factory.

Defines the interface that all output channels must implement,
enabling easy extension with new output destinations.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from app.config import Settings


@runtime_checkable
class OutputChannel(Protocol):
    """
    Protocol for output channels.

    All output channels must implement this interface to be usable
    by the reporting system.

    Example:
        >>> channel = get_channel("console", settings)
        >>> channel.send("Weather Report", "Today's forecast...")
    """

    @property
    def name(self) -> str:
        """
        Channel identifier.

        Returns:
            Short name like "console", "email", "sms"
        """
        ...

    def send(self, subject: str, body: str) -> None:
        """
        Send a message through this channel.

        Args:
            subject: Message subject/title
            body: Message content

        Raises:
            OutputError: If sending fails
        """
        ...


class OutputError(Exception):
    """Base exception for output channel errors."""

    def __init__(self, channel: str, message: str) -> None:
        self.channel = channel
        super().__init__(f"[{channel}] {message}")


class OutputConfigError(OutputError):
    """Raised when output channel configuration is incomplete."""

    pass


class ChannelBlockedError(OutputConfigError):
    """Sperre mit maschinenlesbarem Grund: Prosatext UND stabiler Kurzschluessel.

    Warum an der Ausnahme und nicht als weiteres Ergebnisfeld beim Aufrufer:
    ein Aufrufer, der den Sperrgrund WEITERBUCHEN muss — das Alarm-Protokoll
    (`services/alert_log.py`, `channels_not_sent`) — sieht ausschliesslich die
    Ausnahme des Kanals; ein Feld an `NotificationResult` erreicht ihn nie.
    Und er darf den Fall nicht am deutschen Prosatext erkennen muessen: ein
    solcher Vergleich bricht still beim ersten Umformulieren.

    `reason_code` ist deshalb PFLICHT (keyword-only, ohne Vorgabewert) — eine
    Sperre ohne Kurzschluessel soll beim Erzeugen auffallen, nicht spaeter
    beim Auswerten leer sein. Die Werte folgen dem Vokabular der bestehenden
    Kurzschluessel in `alert_log.py` (`channel_disabled`, `delivery_failed`,
    `below_channel_threshold`) und stehen als Konstanten beim jeweiligen Kanal.

    `OutputError`/`OutputConfigError` bleiben unveraendert: bestehende
    `except OutputConfigError`-Zweige fangen diese Unterklasse mit, `str(exc)`
    liefert weiter den Prosatext, und Kanaele ohne Kurzschluessel aendern sich
    nicht. Auslesen deshalb einheitlich und gefahrlos auch fuer Ausnahmen
    ohne Kurzschluessel:

        >>> code = getattr(exc, "reason_code", None)
    """

    def __init__(self, channel: str, message: str, *, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(channel, message)


def get_channel(name: str, settings: "Settings") -> OutputChannel:
    """
    Factory function to create output channel instances.

    Args:
        name: Channel identifier (e.g., "console", "email")
        settings: Application settings for channel configuration

    Returns:
        OutputChannel instance

    Raises:
        ValueError: If channel is not known
        OutputConfigError: If channel configuration is incomplete

    Example:
        >>> channel = get_channel("email", settings)
        >>> channel.send("Report", "Content here...")
    """
    # Import here to avoid circular imports
    from output.channels.console import ConsoleOutput
    from output.channels.email import EmailOutput

    if name == "console":
        return ConsoleOutput()
    elif name == "email":
        return EmailOutput(settings)
    elif name == "sms":
        from output.channels.sms import SMSOutput
        return SMSOutput(settings)
    elif name == "premium_sms":
        # Issue #1676 S2a (ADR-0049): vierter Kanal, damit die CLI ihn
        # genauso ansprechen kann wie die drei bestehenden.
        from output.channels.premium_sms import PremiumSmsOutput
        return PremiumSmsOutput(settings)
    elif name == "telegram":
        from output.channels.telegram import TelegramOutput
        return TelegramOutput(settings)
    elif name == "none":
        return NullOutput()
    else:
        raise ValueError(f"Unknown output channel: {name}")


class NullOutput:
    """Null output channel that discards all messages."""

    @property
    def name(self) -> str:
        return "none"

    def send(self, subject: str, body: str) -> None:
        pass  # Intentionally do nothing
