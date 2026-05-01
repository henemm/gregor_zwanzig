"""
TDD RED tests for Signal Output channel.

These tests MUST FAIL until SignalOutput is implemented.
Spec: docs/specs/modules/signal_output.md
GitHub Issue: #4
"""


def test_signal_output_import():
    """GIVEN outputs package WHEN importing SignalOutput THEN class exists."""
    from outputs.signal import SignalOutput
    assert SignalOutput is not None


def test_signal_output_implements_protocol():
    """GIVEN SignalOutput WHEN checking protocol THEN satisfies OutputChannel."""
    from outputs.base import OutputChannel
    from outputs.signal import SignalOutput
    from app.config import Settings
    settings = Settings(signal_phone="+43000000", signal_api_key="000000")
    output = SignalOutput(settings)
    assert isinstance(output, OutputChannel)


def test_signal_output_name():
    """GIVEN SignalOutput WHEN accessing .name THEN returns signal."""
    from outputs.signal import SignalOutput
    from app.config import Settings
    settings = Settings(signal_phone="+43000000", signal_api_key="000000")
    output = SignalOutput(settings)
    assert output.name == "signal"


def test_signal_output_config_fields():
    """GIVEN Settings WHEN creating with signal fields THEN accessible."""
    from app.config import Settings
    settings = Settings(
        signal_phone="+43000000",
        signal_api_key="000000",
        signal_api_url="https://test.example.com",
    )
    assert settings.signal_phone == "+43000000"
    assert settings.signal_api_key == "000000"
    assert settings.signal_api_url == "https://test.example.com"


def test_signal_output_can_send_true():
    """GIVEN Settings with phone and code WHEN can_send_signal THEN True."""
    from app.config import Settings
    settings = Settings(signal_phone="+43000000", signal_api_key="000000")
    assert settings.can_send_signal() is True


def test_signal_output_can_send_false():
    """GIVEN Settings without phone WHEN can_send_signal THEN False."""
    from app.config import Settings
    settings = Settings(signal_phone="", signal_api_key="000000")
    assert settings.can_send_signal() is False


def test_signal_output_factory():
    """GIVEN get_channel WHEN requesting signal THEN returns SignalOutput."""
    from outputs.base import get_channel
    from app.config import Settings
    settings = Settings(signal_phone="+43000000", signal_api_key="000000")
    channel = get_channel("signal", settings)
    assert channel.name == "signal"


def test_signal_output_trip_config():
    """GIVEN TripReportConfig WHEN send_signal THEN field exists."""
    from app.models import TripReportConfig
    config = TripReportConfig(trip_id="test")
    assert config.send_signal is False
    config2 = TripReportConfig(trip_id="test", send_signal=True)
    assert config2.send_signal is True
