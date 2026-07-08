"""
Application configuration.

Centralized settings with support for:
- Environment variables (GZ_ prefix)
- .env file
- CLI argument overrides
"""
from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


def _in_pytest() -> bool:
    """True, wenn der aktuelle Prozess ein pytest-Lauf ist (Issue #1122)."""
    return "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules


def is_test_user_id(user_id: str, data_dir: str = "data") -> bool:
    """Zentrales Test-User-Prädikat (Issue #1013 — eine Quelle statt zwei Konventionen).

    True bei "test"/"tdd"-Substring (case-insensitive), dem Fixture-User tg-live-e2e,
    oder wenn das Profil (data_dir/users/<user_id>/user.json) is_test_user=True setzt
    (Adversary-Finding F002 — Namens-Heuristik allein wird von neutral benannten
    Test-Usern mit gesetztem Profil-Flag umgangen). Fail-soft: fehlt/kaputt die
    Profildatei, entscheidet nur die Namens-Heuristik.
    """
    uid = user_id.lower()
    if "test" in uid or "tdd" in uid or user_id == "tg-live-e2e":
        return True
    try:
        profile_path = Path(data_dir) / "users" / user_id / "user.json"
        if profile_path.exists():
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            if profile.get("is_test_user") is True:
                return True
    except Exception:
        pass
    return False


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
    test_smtp_host: str = Field(default="mail.henemm.com", description="Test SMTP host (Stalwart, GZ_TEST_SMTP_HOST)")
    test_smtp_port: int = Field(default=587, description="Test SMTP port (GZ_TEST_SMTP_PORT)")
    test_smtp_user: Optional[str] = Field(default=None, description="Test SMTP username (GZ_TEST_SMTP_USER)")
    test_smtp_pass: Optional[str] = Field(default=None, description="Test SMTP password (GZ_TEST_SMTP_PASS)")
    test_mail_from: Optional[str] = Field(default=None, description="Test sender address (GZ_TEST_MAIL_FROM)")
    test_imap_user: Optional[str] = Field(default=None, description="Test IMAP username (GZ_TEST_IMAP_USER)")
    test_imap_pass: Optional[str] = Field(default=None, description="Test IMAP password (GZ_TEST_IMAP_PASS)")

    # Internal flag set by for_testing() / Test-User-Routing.
    # Wenn True, blockiert EmailOutput jeden Versand über Resend (Production-Versanddienst).
    is_test_mode: bool = Field(default=False, description="Test-Modus: blockiert Resend-Versand")

    # Issue #1122 — Resend Default-Deny: Resend-Versand ist grundsätzlich gesperrt.
    # Nur die Prod-Systemd-Units setzen GZ_RESEND_ALLOWED=1. Ohne Token lenkt der
    # Validator _resend_default_deny jeden Resend-Host auf den Stalwart-Test-Host um.
    resend_allowed: bool = Field(
        default=False,
        description="Explizite Resend-Freigabe (GZ_RESEND_ALLOWED=1) — nur Prod-Units (#1122)",
    )

    # Deployment environment (GZ_ENV)
    env: str = Field(default="production", description="Deployment environment (GZ_ENV)")

    # SMS settings (for sms channel)
    sms_gateway_url: str = Field(default="https://gateway.seven.io/api/sms", description="SMS gateway HTTP endpoint")
    seven_api_key: Optional[str] = Field(default=None, description="seven.io API key (env: GZ_SEVEN_API_KEY)")
    sms_from: Optional[str] = Field(default=None, description="SMS sender ID or number")
    sms_to: Optional[str] = Field(default=None, description="SMS recipient phone number")

    # Telegram settings (for telegram channel via Bot API)
    telegram_bot_token: str = Field(default="", description="Telegram Bot API token from @BotFather")
    telegram_chat_id: str = Field(default="", description="Telegram chat ID of recipient")
    telegram_test_chat_id: str = Field(default="", description="Telegram test chat ID (staging/test users) — GZ_TELEGRAM_TEST_CHAT_ID")

    @model_validator(mode="after")
    def _resend_default_deny(self) -> "Settings":
        """Issue #1122 — Default-Deny: kein Prozess ohne Token hält einen Resend-Host.

        Umlenkung (statt Raise): ein Raise würde ganze Apps beim Settings-Konstrukt
        crashen. Credentials werden bewusst NICHT mitgeswappt — Resend-Creds gegen
        Stalwart ergeben einen lauten 535-Auth-Fehler statt eines stillen Reroutes.
        Der sanktionierte Testpfad bleibt for_testing(). pytest-Prozesse sind auch
        MIT Token gesperrt. model_copy() umgeht Validatoren — dafür bleiben die
        Guards in EmailOutput (#879/#924) als zweite Linie.
        """
        if "resend" not in (self.smtp_host or "").lower():
            return self
        if self.resend_allowed and not _in_pytest():
            return self
        reason = "pytest-Lauf" if _in_pytest() else "GZ_RESEND_ALLOWED fehlt"
        logger.error(
            "Resend Default-Deny (#1122): smtp_host %r wird auf %r umgelenkt (%s). "
            "Produktiver Resend-Versand erfordert GZ_RESEND_ALLOWED=1 in der Prod-Unit.",
            self.smtp_host, self.test_smtp_host, reason,
        )
        self.smtp_host = self.test_smtp_host or "mail.henemm.com"
        self.smtp_port = self.test_smtp_port
        return self

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
        """Return a copy routed to the local Stalwart test host (away from Resend).

        Lenkt smtp_host/-port immer auf test_smtp_host/-port (Default mail.henemm.com),
        damit Test-/E2E-Mails NIE das Resend-Produktivkontingent belasten. Auch ohne
        Test-Credentials wird der Host von Resend weggenommen.
        """
        test_host = self.test_smtp_host or "mail.henemm.com"
        if not self.test_smtp_user or not self.test_smtp_pass:
            return self.model_copy(update={
                "is_test_mode": True,
                "smtp_host": test_host,
                "smtp_port": self.test_smtp_port,
                "telegram_chat_id": self.telegram_test_chat_id or self.telegram_chat_id,
            })
        return self.model_copy(update={
            "smtp_host": test_host,
            "smtp_port": self.test_smtp_port,
            "smtp_user": self.test_smtp_user,
            "smtp_pass": self.test_smtp_pass,
            "mail_from": self.test_mail_from or f"{self.test_smtp_user}@henemm.com",
            "inbound_address": f"{self.test_smtp_user}@henemm.com",
            "imap_user": self.test_imap_user or self.test_smtp_user,
            "imap_pass": self.test_imap_pass or self.test_smtp_pass,
            "is_test_mode": True,
            "telegram_chat_id": self.telegram_test_chat_id or self.telegram_chat_id,
        })

    @staticmethod
    def _is_test_user(user_id: str) -> bool:
        """Detect test user IDs. Thin wrapper — siehe is_test_user_id() (Issue #1013)."""
        return is_test_user_id(user_id)

    def with_user_profile(self, user_id: str) -> "Settings":
        """Return a copy with recipient settings from user profile.

        Loads data/users/{user_id}/user.json and overrides recipient fields.
        SMTP/Telegram infrastructure stays global.
        Test users automatically use Stalwart test credentials instead of Resend.
        Falls back to global settings if profile doesn't exist or fields are empty.
        """
        import json
        from pathlib import Path

        # Test users AND staging always use the Stalwart test account: staging must
        # never send real briefings over Resend to real recipients (burns prod quota).
        force_test = (self.env or "").lower() == "staging" or self._is_test_user(user_id)
        base = self.for_testing() if force_test else self

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
        if profile.get("telegram_chat_id") and not force_test:
            overrides["telegram_chat_id"] = profile["telegram_chat_id"]
        if profile.get("sms_to"):
            overrides["sms_to"] = profile["sms_to"]

        if not overrides:
            return base

        return base.model_copy(update=overrides)

    def can_send_sms(self) -> bool:
        """Check if SMS configuration is complete."""
        return all([
            self.sms_gateway_url,
            self.seven_api_key,
            self.sms_to,
        ])

    def can_send_telegram(self) -> bool:
        """Check if Telegram configuration is complete."""
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    _SENSITIVE_FIELDS = {
        "smtp_pass", "imap_pass", "test_smtp_pass", "test_imap_pass",
        "seven_api_key", "telegram_bot_token",
    }

    def __repr__(self) -> str:
        fields = []
        for name, value in self.__iter__():
            if name in self._SENSITIVE_FIELDS and value:
                fields.append(f"{name}='***'")
            else:
                fields.append(f"{name}={value!r}")
        return f"Settings({', '.join(fields)})"
