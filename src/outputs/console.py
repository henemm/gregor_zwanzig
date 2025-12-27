"""
Console output channel.

Writes weather reports to stdout for terminal display.
"""
from __future__ import annotations


class ConsoleOutput:
    """
    Console output channel.

    Writes formatted reports to stdout with simple headers.

    Example:
        >>> output = ConsoleOutput()
        >>> output.send("Evening Report", "Temperature: 5C")
        === Evening Report ===
        Temperature: 5C
    """

    @property
    def name(self) -> str:
        """Channel identifier."""
        return "console"

    def send(self, subject: str, body: str) -> None:
        """
        Print report to console.

        Args:
            subject: Report title (displayed as header)
            body: Report content
        """
        print(f"\n{'=' * 60}")
        print(f"  {subject}")
        print(f"{'=' * 60}")
        print(body)
        print(f"{'=' * 60}\n")
