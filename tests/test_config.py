"""Tests for configuration module."""
import os
from unittest.mock import patch

import pytest

from app.config import Location, Settings


class TestLocation:
    """Tests for Location dataclass."""

    def test_location_basic(self):
        """Location holds coordinates."""
        loc = Location(latitude=47.0, longitude=11.5)
        assert loc.latitude == 47.0
        assert loc.longitude == 11.5
        assert loc.name is None
        assert loc.elevation_m is None

    def test_location_with_all_fields(self):
        """Location with all optional fields."""
        loc = Location(
            latitude=47.2692,
            longitude=11.4041,
            name="Innsbruck",
            elevation_m=574,
        )
        assert loc.name == "Innsbruck"
        assert loc.elevation_m == 574

    def test_location_str_with_name(self):
        """Location string representation with name."""
        loc = Location(latitude=47.0, longitude=11.5, name="Test")
        assert "Test" in str(loc)
        assert "47.0" in str(loc)

    def test_location_str_without_name(self):
        """Location string representation without name."""
        loc = Location(latitude=47.0, longitude=11.5)
        assert "47.0" in str(loc)
        assert "11.5" in str(loc)

    def test_location_is_frozen(self):
        """Location should be immutable."""
        loc = Location(latitude=47.0, longitude=11.5)
        with pytest.raises(AttributeError):
            loc.latitude = 48.0


class TestSettings:
    """Tests for Settings class."""

    def test_settings_defaults(self):
        """Settings has sensible defaults."""
        settings = Settings()
        assert settings.latitude == 47.2692  # Default: Innsbruck
        assert settings.longitude == 11.4041
        assert settings.provider == "geosphere"
        assert settings.channel == "console"
        assert settings.dry_run is False

    def test_settings_override(self):
        """Settings can be overridden via constructor."""
        settings = Settings(
            latitude=48.0,
            longitude=12.0,
            provider="geosphere",
            channel="email",
        )
        assert settings.latitude == 48.0
        assert settings.channel == "email"

    @patch.dict(os.environ, {"GZ_LATITUDE": "49.0", "GZ_LONGITUDE": "13.0"})
    def test_settings_from_env(self):
        """Settings reads from environment variables with GZ_ prefix."""
        settings = Settings()
        assert settings.latitude == 49.0
        assert settings.longitude == 13.0

    def test_get_location(self):
        """get_location returns proper Location object."""
        settings = Settings(
            latitude=47.0,
            longitude=11.5,
            location_name="Test",
            elevation_m=1000,
        )
        loc = settings.get_location()
        assert isinstance(loc, Location)
        assert loc.latitude == 47.0
        assert loc.name == "Test"
        assert loc.elevation_m == 1000

    def test_can_send_email_false_when_incomplete(self):
        """can_send_email returns False when SMTP config incomplete."""
        settings = Settings()
        assert settings.can_send_email() is False

    def test_can_send_email_true_when_complete(self):
        """can_send_email returns True when SMTP config complete."""
        settings = Settings(
            smtp_host="smtp.example.com",
            smtp_user="user@example.com",
            smtp_pass="secret",
            mail_to="recipient@example.com",
        )
        assert settings.can_send_email() is True
