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
    imap_host: Optional[str] = Field(default=None, description="IMAP server host (default: smtp_host)")
    imap_port: int = Field(default=993, description="IMAP server port")
    imap_user: Optional[str] = Field(default=None, description="IMAP username (default: smtp_user)")
    imap_pass: Optional[str] = Field(default=None, description="IMAP password (default: smtp_pass)")

    # Google SMTP settings (for tests — avoids burning Resend quota)
    google_smtp_host: Optional[str] = Field(default=None, description="Gmail SMTP host for tests")
    google_smtp_port: int = Field(default=587, description="Gmail SMTP port for tests")
    google_smtp_user: Optional[str] = Field(default=None, description="Gmail SMTP user for tests")
    google_smtp_pass: Optional[str] = Field(default=None, description="Gmail SMTP password for tests")
    google_mail_from: Optional[str] = Field(default=None, description="Gmail sender for tests")

    # SMS settings (for sms channel)
    sms_gateway_url: Optional[str] = Field(default=None, description="SMS gateway HTTP endpoint")
    sms_api_key: Optional[str] = Field(default=None, description="SMS gateway API key")
    sms_from: Optional[str] = Field(default=None, description="SMS sender ID or number")
    sms_to: Optional[str] = Field(default=None, description="SMS recipient phone number")

    # Signal settings (for signal channel via Callmebot)
    signal_phone: str = Field(default="", description="Signal recipient phone (E.164 format)")
    signal_api_key: str = Field(default="", description="Callmebot API key")
    signal_api_url: str = Field(default="", description="Callmebot API URL (default built-in)")

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
        """Return a copy with Google SMTP credentials for test email sending.

        Falls back to regular SMTP if Google credentials are not configured.
        Preserves IMAP and mail_to settings.
        """
        if not self.google_smtp_host or not self.google_smtp_user:
            return self
        return self.model_copy(update={
            "smtp_host": self.google_smtp_host,
            "smtp_port": self.google_smtp_port,
            "smtp_user": self.google_smtp_user,
            "smtp_pass": self.google_smtp_pass,
            "mail_from": self.google_mail_from or self.google_smtp_user,
        })

    def can_send_sms(self) -> bool:
        """Check if SMS configuration is complete."""
        return all([
            self.sms_gateway_url,
            self.sms_api_key,
            self.sms_to,
        ])

    def can_send_signal(self) -> bool:
        """Check if Signal configuration is complete."""
        return bool(self.signal_phone and self.signal_api_key)
