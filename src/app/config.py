"""
Application configuration.

Centralized settings with support for:
- Environment variables (GZ_ prefix)
- .env file
- CLI argument overrides
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(frozen=True)
class Location:
    """
    Geographic location for weather queries.

    Immutable value object representing a point on Earth.
    """

    latitude: float
    longitude: float
    name: Optional[str] = None
    elevation_m: Optional[int] = None

    def __str__(self) -> str:
        if self.name:
            return f"{self.name} ({self.latitude:.4f}N, {self.longitude:.4f}E)"
        return f"{self.latitude:.4f}N, {self.longitude:.4f}E"


class Settings(BaseSettings):
    """
    Application settings with environment variable support.

    Priority: CLI args > Environment > .env file > defaults

    Environment variables use GZ_ prefix:
    - GZ_LATITUDE, GZ_LONGITUDE, GZ_LOCATION_NAME
    - GZ_PROVIDER, GZ_REPORT_TYPE, GZ_CHANNEL
    - GZ_SMTP_HOST, GZ_SMTP_PORT, etc.
    """

    model_config = SettingsConfigDict(
        env_prefix="GZ_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Location (required for weather queries)
    latitude: float = Field(default=47.2692, description="Latitude (default: Innsbruck)")
    longitude: float = Field(default=11.4041, description="Longitude (default: Innsbruck)")
    location_name: str = Field(default="Innsbruck", description="Location name for display")
    elevation_m: Optional[int] = Field(default=None, description="Elevation in meters")

    # Provider selection
    provider: str = Field(default="geosphere", description="Weather provider")

    # Report settings
    report_type: str = Field(default="evening", description="Report type: evening, morning, alert")
    channel: str = Field(default="console", description="Output channel: console, email, none")
    debug_level: str = Field(default="info", description="Debug level: info, verbose")
    dry_run: bool = Field(default=False, description="Don't send, only preview")

    # Forecast settings
    forecast_hours: int = Field(default=48, description="Hours to forecast ahead")
    include_snow: bool = Field(default=True, description="Include snow data if available")

    # Sunny-hours calculation (Issue #347): DNI interpolation band + cloud-fallback threshold
    sunny_dni_min_wm2: float = Field(default=60.0, description="DNI lower bound (W/m²); below = 0 sunny hours")
    sunny_dni_max_wm2: float = Field(default=180.0, description="DNI upper bound (W/m²); at/above = full sunny hour")
    sunny_cloud_threshold_pct: int = Field(default=30, description="Reserved cloud threshold for sunny-hours (Issue #347)")

    # SMTP settings (for email channel)
    smtp_host: Optional[str] = Field(default=None, description="SMTP server host")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_user: Optional[str] = Field(default=None, description="SMTP username")
    smtp_pass: Optional[str] = Field(default=None, description="SMTP password")
    mail_to: Optional[str] = Field(default=None, description="Recipient email address")
    mail_from: Optional[str] = Field(default=None, description="Sender email address")
    inbound_address: Optional[str] = Field(default=None, description="Plus-address for inbound commands (e.g. user+gregor@gmail.com)")
    imap_host: Optional[str] = Field(default=None, description="IMAP server host (default: smtp_host)")
    imap_port: int = Field(default=993, description="IMAP server port")
    imap_user: Optional[str] = Field(default=None, description="IMAP username (default: smtp_user)")
    imap_pass: Optional[str] = Field(default=None, description="IMAP password (default: smtp_pass)")

    # Test-Account-Credentials (gregor-test@henemm.com auf Stalwart)
    test_smtp_user: Optional[str] = Field(default=None, description="Test SMTP username (GZ_TEST_SMTP_USER)")
    test_smtp_pass: Optional[str] = Field(default=None, description="Test SMTP password (GZ_TEST_SMTP_PASS)")
    test_mail_from: Optional[str] = Field(default=None, description="Test sender address (GZ_TEST_MAIL_FROM)")
    test_imap_user: Optional[str] = Field(default=None, description="Test IMAP username (GZ_TEST_IMAP_USER)")
    test_imap_pass: Optional[str] = Field(default=None, description="Test IMAP password (GZ_TEST_IMAP_PASS)")

    # Internal flag set by for_testing() / Test-User-Routing.
    # Wenn True, blockiert EmailOutput jeden Versand über Resend (Production-Versanddienst).
    is_test_mode: bool = Field(default=False, description="Test-Modus: blockiert Resend-Versand")

    # SMS settings (for sms channel)
    sms_gateway_url: Optional[str] = Field(default=None, description="SMS gateway HTTP endpoint")
    sms_api_key: Optional[str] = Field(default=None, description="SMS gateway API key")
    sms_from: Optional[str] = Field(default=None, description="SMS sender ID or number")
    sms_to: Optional[str] = Field(default=None, description="SMS recipient phone number")

    # Telegram settings (for telegram channel via Bot API)
    telegram_bot_token: str = Field(default="", description="Telegram Bot API token from @BotFather")
    telegram_chat_id: str = Field(default="", description="Telegram chat ID of recipient")

    def get_location(self) -> Location:
        """Create Location object from settings."""
        return Location(
            latitude=self.latitude,
            longitude=self.longitude,
            name=self.location_name,
            elevation_m=self.elevation_m,
        )

    def can_send_email(self) -> bool:
        """Check if email configuration is complete."""
        return all([
            self.smtp_host,
            self.smtp_user,
            self.smtp_pass,
            self.mail_to,
        ])

    def get_inbound_address(self) -> str | None:
        """Get inbound command address (plus-address or smtp_user fallback)."""
        return self.inbound_address or self.smtp_user

    def for_testing(self) -> "Settings":
        """Return a copy with Stalwart test credentials for test email sending.

        Falls back to is_test_mode=True only if test credentials are not configured.
        smtp_host/imap_host bleiben unverändert — gleicher Stalwart-Server wie Produktion.
        """
        if not self.test_smtp_user or not self.test_smtp_pass:
            return self.model_copy(update={"is_test_mode": True})
        return self.model_copy(update={
            "smtp_user": self.test_smtp_user,
            "smtp_pass": self.test_smtp_pass,
            "mail_from": self.test_mail_from or f"{self.test_smtp_user}@henemm.com",
            "inbound_address": f"{self.test_smtp_user}@henemm.com",
            "imap_user": self.test_imap_user or self.test_smtp_user,
            "imap_pass": self.test_imap_pass or self.test_smtp_pass,
            "is_test_mode": True,
        })

    @staticmethod
    def _is_test_user(user_id: str) -> bool:
        """Detect test user IDs by naming pattern."""
        uid = user_id.lower()
        return "test" in uid or "tdd" in uid

    def with_user_profile(self, user_id: str) -> "Settings":
        """Return a copy with recipient settings from user profile.

        Loads data/users/{user_id}/user.json and overrides recipient fields.
        SMTP/Telegram infrastructure stays global.
        Test users automatically use Stalwart test credentials instead of Resend.
        Falls back to global settings if profile doesn't exist or fields are empty.
        """
        import json
        from pathlib import Path

        # Test users use Stalwart test account to avoid burning Resend quota
        base = self.for_testing() if self._is_test_user(user_id) else self

        profile_path = Path(f"data/users/{user_id}/user.json")
        if not profile_path.exists():
            return base

        try:
            profile = json.loads(profile_path.read_text())
        except (json.JSONDecodeError, OSError):
            return base

        overrides = {}
        if profile.get("mail_to"):
            overrides["mail_to"] = profile["mail_to"]
        if profile.get("telegram_chat_id"):
            overrides["telegram_chat_id"] = profile["telegram_chat_id"]

        if not overrides:
            return base

        return base.model_copy(update=overrides)

    def can_send_sms(self) -> bool:
        """Check if SMS configuration is complete."""
        return all([
            self.sms_gateway_url,
            self.sms_api_key,
            self.sms_to,
        ])

    def can_send_telegram(self) -> bool:
        """Check if Telegram configuration is complete."""
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    _SENSITIVE_FIELDS = {
        "smtp_pass", "imap_pass", "test_smtp_pass", "test_imap_pass",
        "sms_api_key", "telegram_bot_token",
    }

    def __repr__(self) -> str:
        fields = []
        for name, value in self.__iter__():
            if name in self._SENSITIVE_FIELDS and value:
                fields.append(f"{name}='***'")
            else:
                fields.append(f"{name}={value!r}")
        return f"Settings({', '.join(fields)})"
