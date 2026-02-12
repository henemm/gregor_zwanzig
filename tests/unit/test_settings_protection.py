"""
Unit Tests: Settings Protection Mechanism

Tests that save_env_settings() rejects test values and creates backups.

Related: src/web/pages/settings.py
"""
import pytest
import sys
from pathlib import Path
import shutil

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from web.pages.settings import save_env_settings


class TestSettingsProtection:
    """Test .env protection against accidental overwrites."""

    def test_blocks_test_smtp_host(self, tmp_path):
        """Blocks saving .test.com SMTP hosts."""
        # Setup
        env_file = tmp_path / ".env"
        env_file.write_text('GZ_SMTP_HOST="smtp.gmail.com"\n')

        # Monkey-patch ENV_FILE
        import web.pages.settings as settings_module
        original_env_file = settings_module.ENV_FILE
        settings_module.ENV_FILE = env_file

        try:
            # Test
            with pytest.raises(ValueError, match="Refusing to save test SMTP host"):
                save_env_settings({
                    "GZ_SMTP_HOST": "smtp.test.com",
                    "GZ_SMTP_PORT": "587",
                })

            # Verify original file unchanged
            assert "smtp.gmail.com" in env_file.read_text()
            assert "smtp.test.com" not in env_file.read_text()

        finally:
            settings_module.ENV_FILE = original_env_file

    def test_blocks_test_email(self, tmp_path):
        """Blocks saving test@example.com email."""
        # Setup
        env_file = tmp_path / ".env"
        env_file.write_text('GZ_SMTP_USER="real@gmail.com"\n')

        # Monkey-patch ENV_FILE
        import web.pages.settings as settings_module
        original_env_file = settings_module.ENV_FILE
        settings_module.ENV_FILE = env_file

        try:
            # Test
            with pytest.raises(ValueError, match="Refusing to save test email"):
                save_env_settings({
                    "GZ_SMTP_HOST": "smtp.gmail.com",
                    "GZ_SMTP_USER": "test@example.com",
                })

            # Verify original file unchanged
            assert "real@gmail.com" in env_file.read_text()
            assert "test@example.com" not in env_file.read_text()

        finally:
            settings_module.ENV_FILE = original_env_file

    def test_creates_backup_before_save(self, tmp_path):
        """Creates timestamped backup before overwriting .env."""
        # Setup
        env_file = tmp_path / ".env"
        env_file.write_text('GZ_SMTP_HOST="old.value"\n')

        # Monkey-patch ENV_FILE
        import web.pages.settings as settings_module
        original_env_file = settings_module.ENV_FILE
        settings_module.ENV_FILE = env_file

        try:
            # Test
            save_env_settings({
                "GZ_SMTP_HOST": "smtp.gmail.com",
                "GZ_SMTP_PORT": "587",
            })

            # Verify backup created
            backups = list(tmp_path.glob(".env.backup.*"))
            assert len(backups) == 1, "Backup not created"

            # Verify backup contains old value
            backup_content = backups[0].read_text()
            assert "old.value" in backup_content

            # Verify new file has new value
            new_content = env_file.read_text()
            assert "smtp.gmail.com" in new_content

        finally:
            settings_module.ENV_FILE = original_env_file

    def test_allows_valid_values(self, tmp_path):
        """Allows saving valid (non-test) values."""
        # Setup
        env_file = tmp_path / ".env"

        # Monkey-patch ENV_FILE
        import web.pages.settings as settings_module
        original_env_file = settings_module.ENV_FILE
        settings_module.ENV_FILE = env_file

        try:
            # Test - should NOT raise
            save_env_settings({
                "GZ_SMTP_HOST": "smtp.gmail.com",
                "GZ_SMTP_PORT": "587",
                "GZ_SMTP_USER": "real@gmail.com",
                "GZ_MAIL_FROM": "sender@gmail.com",
                "GZ_MAIL_TO": "recipient@icloud.com",
            })

            # Verify saved
            content = env_file.read_text()
            assert "smtp.gmail.com" in content
            assert "real@gmail.com" in content

        finally:
            settings_module.ENV_FILE = original_env_file
