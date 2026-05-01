"""
TDD RED tests for F12a: Channel-Switch for Subscriptions.

Tests the new send_email/send_signal fields on CompareSubscription,
loader round-trip, and backward compatibility.

All tests MUST FAIL before implementation (TDD RED phase).
"""
import json



# =============================================================================
# Test 1: CompareSubscription new fields
# =============================================================================

class TestCompareSubscriptionChannelFields:
    """CompareSubscription gains send_email and send_signal fields."""

    def test_default_send_email_true(self):
        """
        GIVEN: CompareSubscription created without send_email
        WHEN: accessing send_email
        THEN: defaults to True
        """
        from app.user import CompareSubscription
        sub = CompareSubscription(id="test", name="Test")
        assert sub.send_email is True

    def test_default_send_signal_false(self):
        """
        GIVEN: CompareSubscription created without send_signal
        WHEN: accessing send_signal
        THEN: defaults to False
        """
        from app.user import CompareSubscription
        sub = CompareSubscription(id="test", name="Test")
        assert sub.send_signal is False

    def test_explicit_signal_true(self):
        """
        GIVEN: CompareSubscription with send_signal=True
        WHEN: accessing send_signal
        THEN: returns True
        """
        from app.user import CompareSubscription
        sub = CompareSubscription(id="test", name="Test", send_signal=True)
        assert sub.send_signal is True

    def test_explicit_email_false(self):
        """
        GIVEN: CompareSubscription with send_email=False
        WHEN: accessing send_email
        THEN: returns False
        """
        from app.user import CompareSubscription
        sub = CompareSubscription(id="test", name="Test", send_email=False)
        assert sub.send_email is False

    def test_both_channels_enabled(self):
        """
        GIVEN: CompareSubscription with both channels enabled
        WHEN: accessing both fields
        THEN: both are True
        """
        from app.user import CompareSubscription
        sub = CompareSubscription(
            id="test", name="Test", send_email=True, send_signal=True
        )
        assert sub.send_email is True
        assert sub.send_signal is True


# =============================================================================
# Test 2: Loader round-trip
# =============================================================================

class TestLoaderChannelRoundTrip:
    """Loader serializes and deserializes channel flags."""

    def test_save_load_with_signal(self):
        """
        GIVEN: CompareSubscription with send_signal=True
        WHEN: saved and loaded back
        THEN: send_signal round-trips correctly
        """
        from app.user import CompareSubscription
        from app.loader import save_compare_subscription, load_compare_subscriptions

        sub = CompareSubscription(
            id="channel-test", name="Channel Test",
            send_email=True, send_signal=True,
        )
        save_compare_subscription(sub, user_id="__test_channel__")
        loaded = load_compare_subscriptions(user_id="__test_channel__")

        found = [s for s in loaded if s.id == "channel-test"]
        assert len(found) == 1
        assert found[0].send_email is True
        assert found[0].send_signal is True

    def test_save_load_email_only(self):
        """
        GIVEN: CompareSubscription with default channels (email only)
        WHEN: saved and loaded back
        THEN: send_email=True, send_signal=False
        """
        from app.user import CompareSubscription
        from app.loader import save_compare_subscription, load_compare_subscriptions

        sub = CompareSubscription(
            id="email-only-test", name="Email Only",
        )
        save_compare_subscription(sub, user_id="__test_email_only__")
        loaded = load_compare_subscriptions(user_id="__test_email_only__")

        found = [s for s in loaded if s.id == "email-only-test"]
        assert len(found) == 1
        assert found[0].send_email is True
        assert found[0].send_signal is False

    def test_backward_compat_no_channel_fields(self):
        """
        GIVEN: Legacy JSON without send_email/send_signal fields
        WHEN: loaded via load_compare_subscriptions
        THEN: defaults to send_email=True, send_signal=False
        """
        from app.loader import load_compare_subscriptions, get_compare_subscriptions_file

        # Write legacy JSON directly
        path = get_compare_subscriptions_file("__test_legacy_ch__")
        path.parent.mkdir(parents=True, exist_ok=True)
        legacy = {
            "subscriptions": [{
                "id": "legacy-sub",
                "name": "Legacy Sub",
                "enabled": True,
                "locations": ["*"],
                "forecast_hours": 48,
                "time_window_start": 9,
                "time_window_end": 16,
                "schedule": "weekly",
                "weekday": 4,
            }]
        }
        with open(path, "w") as f:
            json.dump(legacy, f)

        loaded = load_compare_subscriptions(user_id="__test_legacy_ch__")
        assert len(loaded) == 1
        assert loaded[0].send_email is True
        assert loaded[0].send_signal is False

    def test_json_contains_channel_fields(self):
        """
        GIVEN: CompareSubscription with send_signal=True
        WHEN: saved to JSON
        THEN: JSON contains send_email and send_signal keys
        """
        from app.user import CompareSubscription
        from app.loader import save_compare_subscription, get_compare_subscriptions_file

        sub = CompareSubscription(
            id="json-check", name="JSON Check",
            send_email=False, send_signal=True,
        )
        save_compare_subscription(sub, user_id="__test_json_ch__")

        path = get_compare_subscriptions_file("__test_json_ch__")
        with open(path) as f:
            data = json.load(f)

        subs = data["subscriptions"]
        found = [s for s in subs if s["id"] == "json-check"]
        assert len(found) == 1
        assert found[0]["send_email"] is False
        assert found[0]["send_signal"] is True
