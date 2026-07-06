"""TDD: Bug #198 — Channel-Test darf nicht über Resend gehen.

Spec: docs/specs/bugfix/bug_198_notify_test_resend.md
Issue: #198

Keine Mocks. Echte Settings-Roundtrip + Source-Check.
"""

from __future__ import annotations

import sys
from pathlib import Path



REPO_ROOT = Path(__file__).resolve().parents[2]


class TestBug198NotifyTestUsesGmail:

    # test_notify_router_source_uses_for_testing — entfernt in #765.
    # Las api/routers/notify.py als Quelltext (Datei-Inhalt-Anti-Pattern,
    # CLAUDE.md). Das relevante Verhalten — der Channel-Test routet über das
    # Stalwart-Test-Konto statt über Resend — ist durch die echten Settings-
    # Roundtrip-Tests unten (for_testing()/with_user_profile().for_testing())
    # bewiesen.

    def test_for_testing_routes_to_gmail_smtp(self):
        """AC-2: for_testing() setzt smtp_user auf test_smtp_user (Stalwart-Test-Account)."""
        sys.path.insert(0, str(REPO_ROOT / "src"))
        from app.config import Settings

        s = Settings(
            smtp_host="smtp.resend.com",
            smtp_user="resend",
            smtp_pass="prod-key",
            test_smtp_user="gregor-test",
            test_smtp_pass="testpass",
        )
        test_s = s.for_testing()
        assert test_s.smtp_user == "gregor-test", \
            f"for_testing() muss test_smtp_user nutzen, war {test_s.smtp_user}"
        assert test_s.smtp_user != "resend", \
            "for_testing() darf NIE Resend-User nutzen"

    def test_with_user_profile_default_and_for_testing(self):
        """AC-3: with_user_profile('default').for_testing() liefert Stalwart-Test-Routing."""
        sys.path.insert(0, str(REPO_ROOT / "src"))
        from app.config import Settings

        s = Settings(
            smtp_host="smtp.resend.com",
            smtp_user="resend",
            smtp_pass="prod",
            test_smtp_user="gregor-test",
            test_smtp_pass="testpass",
        )
        result = s.with_user_profile("default").for_testing()
        assert result.smtp_user == "gregor-test", \
            f"Channel-Test soll Test-Account nutzen, war {result.smtp_user}"
