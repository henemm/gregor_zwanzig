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

    # SMTP settings (for email channel)
    smtp_host: Optional[str] = Field(default=None, description="SMTP server host")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_user: Optional[str] = Field(default=None, description="SMTP username")
    smtp_pass: Optional[str] = Field(default=None, description="SMTP password")
    mail_to: Optional[str] = Field(default=None, description="Recipient email address")
    mail_from: Optional[str] = Field(default=None, description="Sender email address")
    inbound_address: Optional[str] = Field(default=None, description="Plus-address for inbound commands (e.g. user+gregor@gmail.com)")

    # SMS settings (for sms channel)
    sms_gateway_url: Optional[str] = Field(default=None, description="SMS gateway HTTP endpoint")
    sms_api_key: Optional[str] = Field(default=None, description="SMS gateway API key")
    sms_from: Optional[str] = Field(default=None, description="SMS sender ID or number")
    sms_to: Optional[str] = Field(default=None, description="SMS recipient phone number")

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

    def can_send_sms(self) -> bool:
        """Check if SMS configuration is complete."""
        return all([
            self.sms_gateway_url,
            self.sms_api_key,
            self.sms_to,
        ])
