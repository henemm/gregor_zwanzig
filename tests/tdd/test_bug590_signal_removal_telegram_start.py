"""
TDD RED — Bug #590: Signal entfernen + Telegram /start-Flow

Tests prüfen den SOLL-Zustand nach der Implementierung.
Alle Tests schlagen aktuell fehl, weil Signal noch existiert
und der /start-Flow noch nicht implementiert ist.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ──────────────────────────────────────────────────────────────
# AC-7: Signal vollständig aus Python-Backend entfernt
# ──────────────────────────────────────────────────────────────


def test_settings_has_no_signal_phone_field():
    """AC-7: signal_phone darf nicht mehr in Settings existieren."""
    from app.config import Settings

    assert "signal_phone" not in Settings.model_fields, (
        "signal_phone ist noch in Settings — muss entfernt werden"
    )


def test_settings_has_no_signal_api_key_field():
    """AC-7: signal_api_key darf nicht mehr in Settings existieren."""
    from app.config import Settings

    assert "signal_api_key" not in Settings.model_fields, (
        "signal_api_key ist noch in Settings — muss entfernt werden"
    )


def test_settings_has_no_can_send_signal_method():
    """AC-7: can_send_signal() darf nicht mehr in Settings existieren."""
    from app.config import Settings

    assert not hasattr(Settings, "can_send_signal"), (
        "can_send_signal() ist noch in Settings — muss entfernt werden"
    )


def test_signal_output_module_does_not_exist():
    """AC-7: outputs/signal.py muss gelöscht sein."""
    signal_path = Path(__file__).parent.parent.parent / "src" / "outputs" / "signal.py"
    assert not signal_path.exists(), (
        f"src/outputs/signal.py existiert noch: {signal_path}"
    )


def test_trip_report_config_has_no_send_signal():
    """AC-7: TripReportConfig darf kein send_signal-Feld mehr haben."""
    from app.models import TripReportConfig

    instance = TripReportConfig()
    assert not hasattr(instance, "send_signal"), (
        "TripReportConfig hat noch send_signal — muss entfernt werden"
    )


def test_trip_subscription_has_no_send_signal():
    """AC-7: CompareSubscription darf kein send_signal mehr haben."""
    import inspect
    from app.user import CompareSubscription

    fields = inspect.signature(CompareSubscription.__init__).parameters
    assert "send_signal" not in fields, (
        "CompareSubscription hat noch send_signal — muss entfernt werden"
    )


def test_scheduler_imports_no_signal_output():
    """AC-7: trip_report_scheduler.py darf SignalOutput nicht mehr referenzieren."""
    source = (
        Path(__file__).parent.parent.parent
        / "src"
        / "services"
        / "trip_report_scheduler.py"
    )
    content = source.read_text()
    assert "SignalOutput" not in content, (
        "trip_report_scheduler.py referenziert noch SignalOutput"
    )


# ──────────────────────────────────────────────────────────────
# AC-3: Telegram /start TOKEN → chat_id registrieren
# ──────────────────────────────────────────────────────────────


def test_inbound_telegram_reader_handles_start_command():
    """
    AC-3: _process_start_command() muss existieren und True zurückgeben.
    """
    from services.inbound_telegram_reader import InboundTelegramReader

    reader = InboundTelegramReader()

    settings = MagicMock()
    settings.telegram_bot_token = "testtoken"

    with patch("services.inbound_telegram_reader.httpx") as mock_httpx:
        mock_httpx.post.return_value = MagicMock(status_code=200)
        result = reader._process_start_command(
            token="abc123token",
            chat_id="987654321",
            settings=settings,
        )

    assert result is True, (
        "_process_start_command existiert noch nicht — muss implementiert werden"
    )


def test_inbound_telegram_reader_dispatches_start_to_handler():
    """
    AC-3: _process_update erkennt /start TOKEN und delegiert an
    _process_start_command (nicht als 'Unbekannter Befehl' behandeln).
    """
    from services.inbound_telegram_reader import InboundTelegramReader

    reader = InboundTelegramReader()

    fake_update = {
        "update_id": 1000,
        "message": {
            "text": "/start mytoken42",
            "chat": {"id": 111222333},
            "from": {"id": 99},
        },
    }

    settings = MagicMock()
    settings.telegram_bot_token = "tok"

    with patch.object(reader, "_process_start_command", return_value=True) as mock_start:
        reader._process_update(fake_update, settings)

    mock_start.assert_called_once_with(
        token="mytoken42",
        chat_id="111222333",
        settings=settings,
    )


# ──────────────────────────────────────────────────────────────
# AC-7: Settings nach Entfernung stabil initialisierbar
# ──────────────────────────────────────────────────────────────


def test_scheduler_send_report_ignores_signal_silently():
    """
    AC-7: Settings ohne signal_phone/signal_api_key initialisierbar —
    kein AttributeError nach Entfernung.
    """
    from app.config import Settings

    s = Settings()
    assert not hasattr(s, "signal_phone"), (
        "Settings hat noch signal_phone — nach Entfernung darf es das nicht mehr geben"
    )
    assert not hasattr(s, "signal_api_key"), (
        "Settings hat noch signal_api_key"
    )
