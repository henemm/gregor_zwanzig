"""
Settings page for SMTP and provider configuration.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional

from nicegui import ui


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
            ui.link("Vergleich", "/compare").classes("text-white mx-2")
            ui.link("Settings", "/settings").classes("text-white mx-2")


def render_settings() -> None:
    """Render the settings page."""
    render_header()

    settings = load_env_settings()

    with ui.column().classes("w-full max-w-4xl mx-auto p-4"):
        ui.label("Settings").classes("text-h4 mb-4")

        # SMTP Settings
        with ui.card().classes("w-full mb-4"):
            ui.label("E-Mail (SMTP)").classes("text-h6 mb-2")

            smtp_host = ui.input(
                "SMTP Host",
                value=settings.get("GZ_SMTP_HOST", ""),
                placeholder="z.B. smtp.gmail.com",
            ).classes("w-full")

            smtp_port = ui.number(
                "SMTP Port",
                value=int(settings.get("GZ_SMTP_PORT", "587")),
            ).classes("w-full")

            smtp_user = ui.input(
                "SMTP Benutzer",
                value=settings.get("GZ_SMTP_USER", ""),
                placeholder="E-Mail-Adresse",
            ).classes("w-full")

            smtp_pass = ui.input(
                "SMTP Passwort",
                value=settings.get("GZ_SMTP_PASS", ""),
                password=True,
                password_toggle_button=True,
            ).classes("w-full")

            mail_from = ui.input(
                "Absender (From)",
                value=settings.get("GZ_MAIL_FROM", ""),
                placeholder="noreply@example.com",
            ).classes("w-full")

            mail_to = ui.input(
                "Empfänger (To)",
                value=settings.get("GZ_MAIL_TO", ""),
                placeholder="deine@email.com",
            ).classes("w-full")

        # Provider Settings
        with ui.card().classes("w-full mb-4"):
            ui.label("Wetter-Provider").classes("text-h6 mb-2")

            provider = ui.select(
                "Provider",
                options=["geosphere"],
                value=settings.get("GZ_PROVIDER", "geosphere"),
            ).classes("w-full")

        # Location Defaults
        with ui.card().classes("w-full mb-4"):
            ui.label("Standard-Location").classes("text-h6 mb-2")

            lat = ui.number(
                "Breitengrad",
                value=float(settings.get("GZ_LATITUDE", "47.2692")),
                format="%.4f",
            ).classes("w-full")

            lon = ui.number(
                "Längengrad",
                value=float(settings.get("GZ_LONGITUDE", "11.4041")),
                format="%.4f",
            ).classes("w-full")

            location_name = ui.input(
                "Ortsname",
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
                "GZ_PROVIDER": provider.value or "geosphere",
                "GZ_LATITUDE": str(lat.value or 47.2692),
                "GZ_LONGITUDE": str(lon.value or 11.4041),
                "GZ_LOCATION_NAME": location_name.value or "Innsbruck",
            }
            save_env_settings(new_settings)
            ui.notify("Settings gespeichert", type="positive")

        with ui.row().classes("gap-4"):
            ui.button(
                "Speichern",
                on_click=save,
                icon="save",
            ).props("color=primary")

            async def test_email() -> None:
                ui.notify("E-Mail-Test noch nicht implementiert", type="info")

            ui.button(
                "Test-Mail senden",
                on_click=test_email,
                icon="mail",
            ).props("outline")
