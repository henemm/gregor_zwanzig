"""
Test email output - saves to file instead of sending.

Used for automated testing of email content.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path


class TestEmailOutput:
    """
    Test email output that saves to file.

    Saves emails to /tmp/gregor_email_test/ for inspection.
    """

    OUTPUT_DIR = Path("/tmp/gregor_email_test")

    def __init__(self) -> None:
        """Initialize test email output."""
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def name(self) -> str:
        """Channel identifier."""
        return "test_email"

    def send(self, subject: str, body: str) -> Path:
        """
        Save email to file.

        Args:
            subject: Email subject line
            body: Email body (plain text)

        Returns:
            Path to saved email file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"email_{timestamp}.txt"
        filepath = self.OUTPUT_DIR / filename

        content = f"""{'='*70}
SUBJECT: {subject}
DATE: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*70}

{body}
"""

        filepath.write_text(content, encoding="utf-8")

        # Also save as "latest.txt" for easy access
        latest = self.OUTPUT_DIR / "latest.txt"
        latest.write_text(content, encoding="utf-8")

        # Save HTML version for browser preview
        if "<html" in body.lower():
            html_path = self.OUTPUT_DIR / "latest.html"
            html_path.write_text(body, encoding="utf-8")

        return filepath

    @classmethod
    def get_latest(cls) -> str | None:
        """Read the latest test email."""
        latest = cls.OUTPUT_DIR / "latest.txt"
        if latest.exists():
            return latest.read_text(encoding="utf-8")
        return None

    @classmethod
    def clear(cls) -> None:
        """Clear all test emails."""
        if cls.OUTPUT_DIR.exists():
            for f in cls.OUTPUT_DIR.glob("*.txt"):
                f.unlink()
