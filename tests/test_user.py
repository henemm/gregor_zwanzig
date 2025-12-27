"""Tests for User and Subscription models."""
import pytest

from app.user import (
    LocationSubscription,
    SavedLocation,
    Schedule,
    TriggerTiming,
    TripSubscription,
    User,
    UserPreferences,
)


class TestSavedLocation:
    """Tests for SavedLocation."""

    def test_saved_location_creation(self):
        """SavedLocation can be created with required fields."""
        loc = SavedLocation(
            id="stubai",
            name="Stubaier Gletscher",
            lat=47.0753,
            lon=11.1097,
            elevation_m=2302,
        )
        assert loc.id == "stubai"
        assert loc.name == "Stubaier Gletscher"
        assert loc.region is None

    def test_saved_location_with_region(self):
        """SavedLocation can have avalanche region."""
        loc = SavedLocation(
            id="stubai",
            name="Stubaier Gletscher",
            lat=47.0753,
            lon=11.1097,
            elevation_m=2302,
            region="AT-7",
        )
        assert loc.region == "AT-7"

    def test_saved_location_is_frozen(self):
        """SavedLocation should be immutable."""
        loc = SavedLocation(
            id="stubai",
            name="Test",
            lat=47.0,
            lon=11.0,
            elevation_m=2000,
        )
        with pytest.raises(AttributeError):
            loc.name = "Changed"


class TestUserPreferences:
    """Tests for UserPreferences."""

    def test_default_preferences(self):
        """UserPreferences has sensible defaults."""
        prefs = UserPreferences()
        assert prefs.units == "metric"
        assert prefs.language == "de"
        assert prefs.avalanche_level_warning == 3
        assert prefs.wind_chill_warning == -20

    def test_custom_preferences(self):
        """UserPreferences can be customized."""
        prefs = UserPreferences(
            units="imperial",
            language="en",
            avalanche_level_warning=4,
        )
        assert prefs.units == "imperial"
        assert prefs.avalanche_level_warning == 4


class TestSubscriptions:
    """Tests for subscription types."""

    def test_location_subscription(self):
        """LocationSubscription stores reference and schedule."""
        sub = LocationSubscription(
            id="sub-1",
            name="Stubai Check",
            location_ref="stubai",
            schedule=Schedule.DAILY_EVENING,
        )
        assert sub.location_ref == "stubai"
        assert sub.schedule == Schedule.DAILY_EVENING
        assert sub.enabled is True

    def test_trip_subscription(self):
        """TripSubscription stores file path and trigger."""
        sub = TripSubscription(
            id="sub-2",
            name="Weekend Tour",
            trip_file="trips/weekend.json",
            trigger=TriggerTiming.TWO_DAYS_BEFORE,
        )
        assert sub.trip_file == "trips/weekend.json"
        assert sub.trigger == TriggerTiming.TWO_DAYS_BEFORE


class TestUser:
    """Tests for User."""

    def _create_user(self):
        """Helper to create a test user."""
        loc = SavedLocation(
            id="stubai",
            name="Stubaier Gletscher",
            lat=47.0753,
            lon=11.1097,
            elevation_m=2302,
            region="AT-7",
        )
        loc_sub = LocationSubscription(
            id="sub-1",
            name="Stubai Evening",
            location_ref="stubai",
            schedule=Schedule.DAILY_EVENING,
        )
        trip_sub = TripSubscription(
            id="sub-2",
            name="Weekend Tour",
            trip_file="trips/weekend.json",
            trigger=TriggerTiming.TWO_DAYS_BEFORE,
        )
        return User(
            id="user-001",
            email="user@example.com",
            locations={"stubai": loc},
            location_subscriptions=[loc_sub],
            trip_subscriptions=[trip_sub],
        )

    def test_user_creation(self):
        """User can be created with locations and subscriptions."""
        user = self._create_user()
        assert user.id == "user-001"
        assert user.email == "user@example.com"
        assert len(user.locations) == 1
        assert len(user.location_subscriptions) == 1
        assert len(user.trip_subscriptions) == 1

    def test_user_get_location(self):
        """User can retrieve saved location by ID."""
        user = self._create_user()
        loc = user.get_location("stubai")
        assert loc is not None
        assert loc.name == "Stubaier Gletscher"

        missing = user.get_location("unknown")
        assert missing is None

    def test_user_active_subscriptions(self):
        """User can filter active subscriptions."""
        user = self._create_user()
        active_loc = user.get_active_location_subscriptions()
        active_trip = user.get_active_trip_subscriptions()
        assert len(active_loc) == 1
        assert len(active_trip) == 1

    def test_user_disabled_subscription(self):
        """Disabled subscriptions are filtered out."""
        loc_sub = LocationSubscription(
            id="sub-1",
            name="Disabled",
            location_ref="stubai",
            schedule=Schedule.DAILY_EVENING,
            enabled=False,
        )
        user = User(
            id="user-002",
            email="test@example.com",
            location_subscriptions=[loc_sub],
        )
        assert len(user.get_active_location_subscriptions()) == 0

    def test_user_default_preferences(self):
        """User has default preferences if not specified."""
        user = User(id="user-003", email="test@example.com")
        assert user.preferences.language == "de"
        assert user.preferences.units == "metric"
