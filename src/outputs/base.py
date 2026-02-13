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
    from outputs.console import ConsoleOutput
    from outputs.email import EmailOutput
    from outputs.sms import SMSOutput

    if name == "console":
        return ConsoleOutput()
    elif name == "email":
        return EmailOutput(settings)
    elif name == "sms":
        return SMSOutput(settings)
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
