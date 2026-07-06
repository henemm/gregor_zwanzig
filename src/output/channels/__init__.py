"""
Output channels for weather reports.

Provides different output destinations (console, email, etc.)
implementing a common OutputChannel protocol.
"""
from output.channels.base import OutputChannel, get_channel
from output.channels.console import ConsoleOutput
from output.channels.email import EmailOutput
from output.channels.sms import SMSOutput

__all__ = ["OutputChannel", "get_channel", "ConsoleOutput", "EmailOutput", "SMSOutput"]
