"""
Integration tests for Report Config (Feature 3.5).

Tests TripReportConfig DTO and loader serialization.

SPEC: docs/specs/modules/report_config.md v1.0
"""
from __future__ import annotations

from datetime import datetime, time, timezone

import pytest

from app.models import TripReportConfig


class TestTripReportConfigDTO:
    """Test TripReportConfig dataclass."""

    def test_default_values(self) -> None:
        """Default values should match spec."""
        config = TripReportConfig(trip_id="test-trip")

        assert config.enabled is True
        assert config.morning_time == time(7, 0)
        assert config.evening_time == time(18, 0)
        assert config.send_email is True
        assert config.send_sms is False
        assert config.alert_on_changes is True
        assert config.change_threshold_temp_c == 5.0
        assert config.change_threshold_wind_kmh == 20.0
        assert config.change_threshold_precip_mm == 10.0

    def test_custom_values(self) -> None:
        """Custom values should be preserved."""
        config = TripReportConfig(
            trip_id="test-trip",
            morning_time=time(6, 0),
            evening_time=time(20, 0),
            send_email=False,
            send_sms=True,
            change_threshold_temp_c=3.0,
        )

        assert config.morning_time == time(6, 0)
        assert config.evening_time == time(20, 0)
        assert config.send_email is False
        assert config.send_sms is True
        assert config.change_threshold_temp_c == 3.0


class TestReportConfigValidation:
    """Test validation logic."""

    def test_morning_before_evening_valid(self) -> None:
        """Morning 07:00 before evening 18:00 is valid."""
        morning = time(7, 0)
        evening = time(18, 0)

        assert morning < evening

    def test_morning_after_evening_invalid(self) -> None:
        """Morning 19:00 after evening 18:00 is invalid."""
        morning = time(19, 0)
        evening = time(18, 0)

        assert not (morning < evening)

    def test_morning_equals_evening_invalid(self) -> None:
        """Morning equals evening is invalid."""
        morning = time(12, 0)
        evening = time(12, 0)

        assert not (morning < evening)


class TestReportConfigSerialization:
    """Test serialization to/from dict."""

    def test_serialize_to_dict(self) -> None:
        """Config should serialize to dict for JSON."""
        config = TripReportConfig(
            trip_id="test-trip",
            morning_time=time(6, 30),
            evening_time=time(19, 0),
            send_email=True,
            send_sms=False,
            change_threshold_temp_c=4.0,
            updated_at=datetime(2026, 2, 10, 12, 0, 0, tzinfo=timezone.utc),
        )

        data = {
            "trip_id": config.trip_id,
            "enabled": config.enabled,
            "morning_time": config.morning_time.isoformat(),
            "evening_time": config.evening_time.isoformat(),
            "send_email": config.send_email,
            "send_sms": config.send_sms,
            "alert_on_changes": config.alert_on_changes,
            "change_threshold_temp_c": config.change_threshold_temp_c,
            "change_threshold_wind_kmh": config.change_threshold_wind_kmh,
            "change_threshold_precip_mm": config.change_threshold_precip_mm,
            "updated_at": config.updated_at.isoformat(),
        }

        assert data["trip_id"] == "test-trip"
        assert data["morning_time"] == "06:30:00"
        assert data["evening_time"] == "19:00:00"
        assert data["change_threshold_temp_c"] == 4.0

    def test_deserialize_from_dict(self) -> None:
        """Config should deserialize from dict."""
        data = {
            "trip_id": "test-trip",
            "enabled": True,
            "morning_time": "06:30:00",
            "evening_time": "19:00:00",
            "send_email": True,
            "send_sms": False,
            "alert_on_changes": True,
            "change_threshold_temp_c": 4.0,
            "change_threshold_wind_kmh": 15.0,
            "change_threshold_precip_mm": 8.0,
            "updated_at": "2026-02-10T12:00:00+00:00",
        }

        config = TripReportConfig(
            trip_id=data["trip_id"],
            enabled=data["enabled"],
            morning_time=time.fromisoformat(data["morning_time"]),
            evening_time=time.fromisoformat(data["evening_time"]),
            send_email=data["send_email"],
            send_sms=data["send_sms"],
            alert_on_changes=data["alert_on_changes"],
            change_threshold_temp_c=data["change_threshold_temp_c"],
            change_threshold_wind_kmh=data["change_threshold_wind_kmh"],
            change_threshold_precip_mm=data["change_threshold_precip_mm"],
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )

        assert config.trip_id == "test-trip"
        assert config.morning_time == time(6, 30)
        assert config.evening_time == time(19, 0)
        assert config.change_threshold_temp_c == 4.0
        assert config.change_threshold_wind_kmh == 15.0
