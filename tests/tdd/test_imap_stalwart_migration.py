"""
TDD RED Tests: E2E IMAP Stalwart Migration

Verifies that all IMAP connections use Settings-based configuration
(Stalwart at mail.henemm.com) instead of hardcoded Gmail references.

These tests MUST FAIL before the fix (hardcoded Gmail still present)
and PASS after the fix.
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestNoHardcodedGmail:
    """No file should contain hardcoded Gmail IMAP references."""

    AFFECTED_FILES = [
        ".claude/hooks/e2e_browser_test.py",
        ".claude/hooks/email_spec_validator.py",
        ".claude/tools/output_validator.py",
        "tests/tdd/test_html_email.py",
        "tests/e2e/test_e2e_story3_reports.py",
        "tests/e2e/test_e2e_friendly_format_config.py",
    ]

    def _read(self, rel_path: str) -> str:
        return (PROJECT_ROOT / rel_path).read_text()

    def test_no_hardcoded_gmail_imap_host(self):
        """
        GIVEN: 6 files that previously used imap.gmail.com
        WHEN: reading their source code
        THEN: none should contain the string 'imap.gmail.com'
        """
        violations = []
        for f in self.AFFECTED_FILES:
            content = self._read(f)
            if "imap.gmail.com" in content:
                violations.append(f)
        assert not violations, (
            f"Hardcoded 'imap.gmail.com' found in: {violations}"
        )

    def test_no_gmail_folder_references(self):
        """
        GIVEN: 6 files that previously used Gmail folder names
        WHEN: reading their source code
        THEN: none should contain '[Google Mail]' folder references
        """
        violations = []
        for f in self.AFFECTED_FILES:
            content = self._read(f)
            if "[Google Mail]" in content:
                violations.append(f)
        assert not violations, (
            f"Gmail folder '[Google Mail]' found in: {violations}"
        )

    def test_no_smtp_credentials_for_imap_login(self):
        """
        GIVEN: files that connect to IMAP
        WHEN: reading their IMAP login calls
        THEN: none should use smtp_user/smtp_pass for IMAP login
              (must use imap_user/imap_pass or GZ_IMAP_USER/GZ_IMAP_PASS)
        """
        # Pattern: imap.login(settings.smtp_user, settings.smtp_pass)
        # or imap.login(smtp_user, smtp_pass) where smtp vars come from settings
        pattern = re.compile(r"imap\.login\(.*smtp_(?:user|pass)")
        violations = []
        for f in self.AFFECTED_FILES:
            content = self._read(f)
            if pattern.search(content):
                violations.append(f)
        assert not violations, (
            f"SMTP credentials used for IMAP login in: {violations}"
        )

    def test_e2e_friendly_format_uses_correct_env_vars(self):
        """
        GIVEN: test_e2e_friendly_format_config.py
        WHEN: reading its IMAP configuration variables
        THEN: IMAP_USER should use GZ_IMAP_USER, not GZ_SMTP_USER
        """
        content = self._read("tests/e2e/test_e2e_friendly_format_config.py")
        # The IMAP_USER assignment must not reference GZ_SMTP_USER
        assert 'IMAP_USER = os.getenv("GZ_SMTP_USER")' not in content, (
            "test_e2e_friendly_format_config.py uses GZ_SMTP_USER for IMAP_USER"
        )

    def test_e2e_browser_test_uses_settings_imap(self):
        """
        GIVEN: e2e_browser_test.py
        WHEN: reading its IMAP connection setup
        THEN: should reference imap_host/imap_user/imap_pass from settings
        """
        content = self._read(".claude/hooks/e2e_browser_test.py")
        # Must use settings-based IMAP
        assert "settings.imap_host" in content or "imap_host" in content, (
            "e2e_browser_test.py does not use settings-based imap_host"
        )
        # Must NOT have hardcoded IMAP4_SSL('imap.gmail.com')
        assert "IMAP4_SSL('imap.gmail.com')" not in content, (
            "e2e_browser_test.py still has hardcoded Gmail IMAP"
        )

    def test_output_validator_no_gmail_default(self):
        """
        GIVEN: output_validator.py
        WHEN: reading its IMAP fallback config
        THEN: should not default to imap.gmail.com
        """
        content = self._read(".claude/tools/output_validator.py")
        assert "imap.gmail.com" not in content, (
            "output_validator.py still defaults to imap.gmail.com"
        )

    def test_positive_settings_pattern_present(self):
        """
        GIVEN: all affected files
        WHEN: reading their IMAP setup
        THEN: they should contain the correct settings-based pattern
              (not just be missing Gmail — the correct code must be there)
        """
        # e2e_browser_test.py must have settings.imap_host fallback
        content = self._read(".claude/hooks/e2e_browser_test.py")
        assert "settings.imap_host or settings.smtp_host" in content

        # email_spec_validator.py must have settings.imap_host fallback
        content = self._read(".claude/hooks/email_spec_validator.py")
        assert "settings.imap_host or settings.smtp_host" in content

        # output_validator.py must use GZ_IMAP env vars
        content = self._read(".claude/tools/output_validator.py")
        assert "GZ_IMAP_USER" in content
        assert "GZ_IMAP_PASS" in content

        # test_html_email.py must have settings-based IMAP
        content = self._read("tests/tdd/test_html_email.py")
        assert "settings.imap_host or settings.smtp_host" in content

        # test_e2e_story3_reports.py must have settings-based IMAP
        content = self._read("tests/e2e/test_e2e_story3_reports.py")
        assert "settings.imap_host or settings.smtp_host" in content

        # test_e2e_friendly_format_config.py must use GZ_IMAP_USER
        content = self._read("tests/e2e/test_e2e_friendly_format_config.py")
        assert 'GZ_IMAP_USER' in content
        assert 'GZ_IMAP_HOST' in content
