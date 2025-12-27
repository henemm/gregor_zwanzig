"""
Output channels for weather reports.

Provides different output destinations (console, email, etc.)
implementing a common OutputChannel protocol.
"""
from outputs.base import OutputChannel, get_channel
from outputs.console import ConsoleOutput
from outputs.email import EmailOutput

__all__ = ["OutputChannel", "get_channel", "ConsoleOutput", "EmailOutput"]
