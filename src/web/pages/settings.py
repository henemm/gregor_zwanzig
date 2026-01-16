"""
Settings page for SMTP and provider configuration.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict

from nicegui import ui

from app.config import Settings
from outputs.email import EmailOutput
from outputs.base import OutputConfigError, OutputError


ENV_FILE = Path(".env")


def load_env_settings() -> Dict[str, str]:
    """Load settings from .env file."""
    settings: Dict[str, str] = {}
    if not ENV_FILE.exists():
        return settings

    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                settings[key.strip()] = value.strip().strip('"').strip("'")

    return settings


def save_env_settings(settings: Dict[str, str]) -> None:
    """Save settings to .env file."""
    lines = []
    for key, value in settings.items():
        if value:
            lines.append(f'{key}="{value}"')

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def render_header() -> None:
    """Render navigation header."""
    with ui.header().classes("items-center justify-between"):
        ui.label("Gregor Zwanzig").classes("text-h6")
        with ui.row():
            ui.link("Dashboard", "/").classes("text-white mx-2")
            ui.link("Locations", "/locations").classes("text-white mx-2")
            ui.link("Trips", "/trips").classes("text-white mx-2")
            ui.link("Compare", "/compare").classes("text-white mx-2")
            ui.link("Subscriptions", "/subscriptions").classes("text-white mx-2")
            ui.link("Settings", "/settings").classes("text-white mx-2")


def render_settings() -> None:
    """Render the settings page."""
    render_header()

    settings = load_env_settings()

    with ui.column().classes("w-full max-w-4xl mx-auto p-4"):
        ui.label("Settings").classes("text-h4 mb-4")

        # SMTP Settings
        with ui.card().classes("w-full mb-4"):
            ui.label("Email (SMTP)").classes("text-h6 mb-2")

            smtp_host = ui.input(
                "SMTP Host",
                value=settings.get("GZ_SMTP_HOST", ""),
                placeholder="e.g. smtp.gmail.com",
            ).classes("w-full")

            smtp_port = ui.number(
                "SMTP Port",
                value=int(settings.get("GZ_SMTP_PORT", "587")),
            ).classes("w-full")

            smtp_user = ui.input(
                "SMTP User",
                value=settings.get("GZ_SMTP_USER", ""),
                placeholder="Email address",
            ).classes("w-full")

            smtp_pass = ui.input(
                "SMTP Password",
                value=settings.get("GZ_SMTP_PASS", ""),
                password=True,
                password_toggle_button=True,
            ).classes("w-full")

            mail_from = ui.input(
                "Sender (From)",
                value=settings.get("GZ_MAIL_FROM", ""),
                placeholder="noreply@example.com",
            ).classes("w-full")

            mail_to = ui.input(
                "Recipient (To)",
                value=settings.get("GZ_MAIL_TO", ""),
                placeholder="your@email.com",
            ).classes("w-full")

            email_plain_text = ui.checkbox(
                "Plain text email (no emojis)",
                value=settings.get("GZ_EMAIL_PLAIN_TEXT", "false").lower() == "true",
            ).classes("mt-4")

        # Provider Settings
        with ui.card().classes("w-full mb-4"):
            ui.label("Weather Provider").classes("text-h6 mb-2")

            provider = ui.select(
                options=["geosphere"],
                label="Provider",
                value=settings.get("GZ_PROVIDER", "geosphere"),
            ).classes("w-full")

        # Location Defaults
        with ui.card().classes("w-full mb-4"):
            ui.label("Default Location").classes("text-h6 mb-2")

            lat = ui.number(
                "Latitude",
                value=float(settings.get("GZ_LATITUDE", "47.2692")),
                format="%.4f",
            ).classes("w-full")

            lon = ui.number(
                "Longitude",
                value=float(settings.get("GZ_LONGITUDE", "11.4041")),
                format="%.4f",
            ).classes("w-full")

            location_name = ui.input(
                "Location Name",
                value=settings.get("GZ_LOCATION_NAME", "Innsbruck"),
            ).classes("w-full")

        # Save Button
        def save() -> None:
            new_settings = {
                "GZ_SMTP_HOST": smtp_host.value or "",
                "GZ_SMTP_PORT": str(int(smtp_port.value or 587)),
                "GZ_SMTP_USER": smtp_user.value or "",
                "GZ_SMTP_PASS": smtp_pass.value or "",
                "GZ_MAIL_FROM": mail_from.value or "",
                "GZ_MAIL_TO": mail_to.value or "",
                "GZ_EMAIL_PLAIN_TEXT": "true" if email_plain_text.value else "false",
                "GZ_PROVIDER": provider.value or "geosphere",
                "GZ_LATITUDE": str(lat.value or 47.2692),
                "GZ_LONGITUDE": str(lon.value or 11.4041),
                "GZ_LOCATION_NAME": location_name.value or "Innsbruck",
            }
            save_env_settings(new_settings)
            ui.notify("Settings saved", type="positive")

        def make_save_handler():
            """Factory function for save button (Safari compatibility)."""
            def do_save() -> None:
                save()
            return do_save

        with ui.row().classes("gap-4"):
            ui.button(
                "Save",
                on_click=make_save_handler(),
                icon="save",
            ).props("color=primary")

            async def test_email() -> None:
                # First save current settings
                save()

                try:
                    # Reload settings from .env
                    settings = Settings()

                    if not settings.can_send_email():
                        ui.notify(
                            "SMTP not fully configured. Please fill all fields.",
                            type="negative",
                        )
                        return

                    ui.notify("Sending test email...", type="info")

                    email_output = EmailOutput(settings)
                    subject = "Gregor Zwanzig - Test"
                    body = "This is a test email from Gregor Zwanzig.\n\nIf you receive this, SMTP is configured correctly!"

                    await asyncio.get_event_loop().run_in_executor(
                        None, lambda: email_output.send(subject, body)
                    )

                    ui.notify(f"Test email sent to {settings.mail_to}!", type="positive")

                except OutputConfigError as e:
                    ui.notify(f"Configuration error: {e}", type="negative")
                except OutputError as e:
                    ui.notify(f"Send failed: {e}", type="negative")
                except Exception as e:
                    ui.notify(f"Error: {e}", type="negative")

            def make_test_email_handler():
                """Factory function for test email button (Safari compatibility)."""
                async def do_test() -> None:
                    await test_email()
                return do_test

            ui.button(
                "Send Test Email",
                on_click=make_test_email_handler(),
                icon="mail",
            ).props("outline")
