"""TDD: Bug #198 — Channel-Test darf nicht über Resend gehen.

Spec: docs/specs/bugfix/bug_198_notify_test_resend.md
Issue: #198

Keine Mocks. Echte Settings-Roundtrip + Source-Check.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


class TestBug198NotifyTestUsesGmail:

    def test_notify_router_source_uses_for_testing(self):
        """AC-1: api/routers/notify.py muss .for_testing() in test_notify() aufrufen."""
        src = (REPO_ROOT / "api" / "routers" / "notify.py").read_text()

        # Settings-Initialisierung im test_notify Endpoint
        assert "Settings()" in src and "with_user_profile" in src, \
            "notify.py muss Settings().with_user_profile(...) nutzen"

        # Pflicht: .for_testing() im Endpoint
        assert ".for_testing()" in src, \
            "notify.py: test_notify() muss .for_testing() anwenden — Test-Mails immer über Gmail"

    def test_for_testing_routes_to_gmail_smtp(self):
        """AC-2: for_testing() setzt smtp_host auf google_smtp_host."""
        sys.path.insert(0, str(REPO_ROOT / "src"))
        from app.config import Settings

        # Custom Settings mit Gmail-Werten setzen
        s = Settings(
            smtp_host="smtp.resend.com",
            smtp_user="resend",
            smtp_pass="prod-key",
            google_smtp_host="smtp.gmail.com",
            google_smtp_user="gmail-user@gmail.com",
            google_smtp_pass="gmail-pass",
        )
        test_s = s.for_testing()
        assert test_s.smtp_host == "smtp.gmail.com", \
            f"for_testing() muss Gmail-Host nutzen, war {test_s.smtp_host}"
        assert test_s.smtp_host != "smtp.resend.com", \
            "for_testing() darf NIE Resend nutzen"

    def test_with_user_profile_default_and_for_testing(self):
        """AC-3: with_user_profile('default').for_testing() liefert Gmail-Routing."""
        sys.path.insert(0, str(REPO_ROOT / "src"))
        from app.config import Settings

        s = Settings(
            smtp_host="smtp.resend.com",
            smtp_user="resend",
            smtp_pass="prod",
            google_smtp_host="smtp.gmail.com",
            google_smtp_user="gmail@x",
            google_smtp_pass="gmail-pass",
        )
        result = s.with_user_profile("default").for_testing()
        assert result.smtp_host == "smtp.gmail.com", \
            f"Channel-Test soll Gmail nutzen, war {result.smtp_host}"
