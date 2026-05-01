"""
TDD RED tests for F14a: Subscription Metriken-Auswahl.

Tests display_config on CompareSubscription, loader round-trip,
and weather config dialog existence.
"""
import json


class TestSubscriptionDisplayConfig:
    """CompareSubscription gains display_config field."""

    def test_default_display_config_none(self):
        """
        GIVEN: CompareSubscription without display_config
        WHEN: accessing display_config
        THEN: defaults to None
        """
        from app.user import CompareSubscription
        sub = CompareSubscription(id="test", name="Test")
        assert sub.display_config is None

    def test_explicit_display_config(self):
        """
        GIVEN: CompareSubscription with display_config
        WHEN: accessing display_config
        THEN: returns the config
        """
        from app.user import CompareSubscription
        from app.metric_catalog import build_default_display_config
        config = build_default_display_config("test-sub")
        sub = CompareSubscription(id="test", name="Test", display_config=config)
        assert sub.display_config is not None
        assert sub.display_config.trip_id == "test-sub"

    def test_display_config_mutable(self):
        """
        GIVEN: CompareSubscription (non-frozen dataclass)
        WHEN: assigning display_config
        THEN: mutation works (unlike SavedLocation which is frozen)
        """
        from app.user import CompareSubscription
        from app.metric_catalog import build_default_display_config
        sub = CompareSubscription(id="test", name="Test")
        assert sub.display_config is None
        sub.display_config = build_default_display_config("test")
        assert sub.display_config is not None


class TestSubscriptionMetricsLoaderRoundTrip:
    """Loader serializes/deserializes display_config on subscriptions."""

    def test_save_load_with_display_config(self):
        """
        GIVEN: CompareSubscription with display_config
        WHEN: saved and loaded
        THEN: display_config round-trips with metrics
        """
        from app.user import CompareSubscription
        from app.metric_catalog import build_default_display_config
        from app.loader import save_compare_subscription, load_compare_subscriptions

        config = build_default_display_config("metrics-test")
        sub = CompareSubscription(
            id="metrics-test", name="Metrics Test", display_config=config,
        )
        save_compare_subscription(sub, user_id="__test_sub_metrics__")
        loaded = load_compare_subscriptions(user_id="__test_sub_metrics__")

        found = [s for s in loaded if s.id == "metrics-test"]
        assert len(found) == 1
        assert found[0].display_config is not None
        assert len(found[0].display_config.metrics) > 0

    def test_save_load_without_display_config(self):
        """
        GIVEN: CompareSubscription without display_config
        WHEN: saved and loaded
        THEN: display_config is None
        """
        from app.user import CompareSubscription
        from app.loader import save_compare_subscription, load_compare_subscriptions

        sub = CompareSubscription(id="no-dc-test", name="No DC")
        save_compare_subscription(sub, user_id="__test_sub_nodc__")
        loaded = load_compare_subscriptions(user_id="__test_sub_nodc__")

        found = [s for s in loaded if s.id == "no-dc-test"]
        assert len(found) == 1
        assert found[0].display_config is None

    def test_backward_compat_legacy_json(self):
        """
        GIVEN: Legacy subscription JSON without display_config
        WHEN: loaded
        THEN: display_config is None, no error
        """
        from app.loader import load_compare_subscriptions, get_compare_subscriptions_file

        path = get_compare_subscriptions_file("__test_sub_legacy__")
        path.parent.mkdir(parents=True, exist_ok=True)
        legacy = {
            "subscriptions": [{
                "id": "legacy", "name": "Legacy",
                "enabled": True, "locations": ["*"],
                "forecast_hours": 48, "schedule": "weekly",
            }]
        }
        with open(path, "w") as f:
            json.dump(legacy, f)

        loaded = load_compare_subscriptions(user_id="__test_sub_legacy__")
        assert len(loaded) == 1
        assert loaded[0].display_config is None

    def test_json_contains_display_config(self):
        """
        GIVEN: CompareSubscription with display_config
        WHEN: saved
        THEN: JSON contains display_config with metrics
        """
        from app.user import CompareSubscription
        from app.metric_catalog import build_default_display_config
        from app.loader import save_compare_subscription, get_compare_subscriptions_file

        config = build_default_display_config("json-test")
        sub = CompareSubscription(
            id="json-test", name="JSON Test", display_config=config,
        )
        save_compare_subscription(sub, user_id="__test_sub_json__")

        path = get_compare_subscriptions_file("__test_sub_json__")
        with open(path) as f:
            data = json.load(f)
        found = [s for s in data["subscriptions"] if s["id"] == "json-test"]
        assert len(found) == 1
        assert "display_config" in found[0]
        assert "metrics" in found[0]["display_config"]


# TestSubscriptionWeatherConfigDialog entfernt (Bug #89 v1.1):
# show_subscription_weather_config_dialog ist UI-tot seit F76
# (/subscriptions -> 301 -> /compare) und wurde aus weather_config.py entfernt.
# Loader-Roundtrip-Tests in TestSubscriptionMetricsLoaderRoundTrip bleiben
# als Regression-Anker fuer den Persistenz-Layer (SvelteKit/Go-API).
