"""
TDD RED tests for Telegram Output channel.

These tests MUST FAIL until TelegramOutput is implemented.
Spec: docs/specs/modules/telegram_output.md
GitHub Issue: #11
"""
import json



# =============================================================================
# Test 1: TelegramOutput class exists and follows protocol
# =============================================================================


def test_telegram_output_import():
    """GIVEN outputs package WHEN importing TelegramOutput THEN class exists."""
    from outputs.telegram import TelegramOutput
    assert TelegramOutput is not None


def test_telegram_output_implements_protocol():
    """GIVEN TelegramOutput WHEN checking protocol THEN satisfies OutputChannel."""
    from outputs.base import OutputChannel
    from outputs.telegram import TelegramOutput
    from app.config import Settings
    settings = Settings(telegram_bot_token="fake:token", telegram_chat_id="12345")
    output = TelegramOutput(settings)
    assert isinstance(output, OutputChannel)


def test_telegram_output_name():
    """GIVEN TelegramOutput WHEN accessing .name THEN returns telegram."""
    from outputs.telegram import TelegramOutput
    from app.config import Settings
    settings = Settings(telegram_bot_token="fake:token", telegram_chat_id="12345")
    output = TelegramOutput(settings)
    assert output.name == "telegram"


# =============================================================================
# Test 2: Settings fields and can_send_telegram()
# =============================================================================


def test_telegram_config_fields():
    """GIVEN Settings WHEN creating with telegram fields THEN accessible."""
    from app.config import Settings
    settings = Settings(
        telegram_bot_token="123456:ABC-DEF",
        telegram_chat_id="987654321",
    )
    assert settings.telegram_bot_token == "123456:ABC-DEF"
    assert settings.telegram_chat_id == "987654321"


def test_telegram_can_send_true():
    """GIVEN Settings with token and chat_id WHEN can_send_telegram THEN True."""
    from app.config import Settings
    settings = Settings(telegram_bot_token="123:ABC", telegram_chat_id="12345")
    assert settings.can_send_telegram() is True


def test_telegram_can_send_false_no_token():
    """GIVEN Settings without token WHEN can_send_telegram THEN False."""
    from app.config import Settings
    settings = Settings(telegram_bot_token="", telegram_chat_id="12345")
    assert settings.can_send_telegram() is False


def test_telegram_can_send_false_no_chat_id():
    """GIVEN Settings without chat_id WHEN can_send_telegram THEN False."""
    from app.config import Settings
    settings = Settings(telegram_bot_token="123:ABC", telegram_chat_id="")
    assert settings.can_send_telegram() is False


# =============================================================================
# Test 3: Factory integration
# =============================================================================


def test_telegram_output_factory():
    """GIVEN get_channel WHEN requesting telegram THEN returns TelegramOutput."""
    from outputs.base import get_channel
    from app.config import Settings
    settings = Settings(telegram_bot_token="123:ABC", telegram_chat_id="12345")
    channel = get_channel("telegram", settings)
    assert channel.name == "telegram"


# =============================================================================
# Test 4: Model flags
# =============================================================================


def test_telegram_trip_config_default():
    """GIVEN TripReportConfig WHEN created without send_telegram THEN False."""
    from app.models import TripReportConfig
    config = TripReportConfig(trip_id="test")
    assert config.send_telegram is False


def test_telegram_trip_config_explicit():
    """GIVEN TripReportConfig WHEN send_telegram=True THEN True."""
    from app.models import TripReportConfig
    config = TripReportConfig(trip_id="test", send_telegram=True)
    assert config.send_telegram is True


def test_telegram_subscription_default():
    """GIVEN CompareSubscription WHEN created without send_telegram THEN False."""
    from app.user import CompareSubscription
    sub = CompareSubscription(id="test", name="Test")
    assert sub.send_telegram is False


def test_telegram_subscription_explicit():
    """GIVEN CompareSubscription WHEN send_telegram=True THEN True."""
    from app.user import CompareSubscription
    sub = CompareSubscription(id="test", name="Test", send_telegram=True)
    assert sub.send_telegram is True


# =============================================================================
# Test 5: Loader round-trip for send_telegram
# =============================================================================


class TestLoaderTelegramRoundTrip:
    """Loader serializes and deserializes send_telegram flag."""

    def test_subscription_save_load_telegram(self):
        """
        GIVEN: CompareSubscription with send_telegram=True
        WHEN: saved and loaded back
        THEN: send_telegram round-trips correctly
        """
        from app.user import CompareSubscription
        from app.loader import save_compare_subscription, load_compare_subscriptions

        sub = CompareSubscription(
            id="telegram-test", name="Telegram Test",
            send_email=True, send_signal=False, send_telegram=True,
        )
        save_compare_subscription(sub, user_id="__test_telegram__")
        loaded = load_compare_subscriptions(user_id="__test_telegram__")

        found = [s for s in loaded if s.id == "telegram-test"]
        assert len(found) == 1
        assert found[0].send_telegram is True
        assert found[0].send_email is True
        assert found[0].send_signal is False

    def test_subscription_json_contains_send_telegram(self):
        """
        GIVEN: CompareSubscription with send_telegram=True
        WHEN: saved to JSON
        THEN: JSON contains send_telegram key
        """
        from app.user import CompareSubscription
        from app.loader import save_compare_subscription, get_compare_subscriptions_file

        sub = CompareSubscription(
            id="tg-json-check", name="TG JSON Check",
            send_telegram=True,
        )
        save_compare_subscription(sub, user_id="__test_json_tg__")

        path = get_compare_subscriptions_file("__test_json_tg__")
        with open(path) as f:
            data = json.load(f)

        subs = data["subscriptions"]
        found = [s for s in subs if s["id"] == "tg-json-check"]
        assert len(found) == 1
        assert found[0]["send_telegram"] is True

    def test_backward_compat_no_telegram_field(self):
        """
        GIVEN: Legacy JSON without send_telegram field
        WHEN: loaded via load_compare_subscriptions
        THEN: defaults to send_telegram=False
        """
        from app.loader import load_compare_subscriptions, get_compare_subscriptions_file

        path = get_compare_subscriptions_file("__test_legacy_tg__")
        path.parent.mkdir(parents=True, exist_ok=True)
        legacy = {
            "subscriptions": [{
                "id": "legacy-tg",
                "name": "Legacy No Telegram",
                "enabled": True,
                "locations": ["*"],
                "forecast_hours": 48,
                "time_window_start": 9,
                "time_window_end": 16,
                "schedule": "weekly",
                "weekday": 4,
                "send_email": True,
                "send_signal": False,
            }]
        }
        with open(path, "w") as f:
            json.dump(legacy, f)

        loaded = load_compare_subscriptions(user_id="__test_legacy_tg__")
        assert len(loaded) == 1
        assert loaded[0].send_telegram is False
