"""
TDD RED tests for F11a: Generic Locations.

Tests the new LocationActivityProfile enum, SavedLocation model extensions,
profile-based default metric configs, and loader round-trip.

All tests MUST FAIL before implementation (TDD RED phase).
"""
import json
import tempfile
from pathlib import Path

import pytest


# =============================================================================
# Test 1: LocationActivityProfile Enum exists in user.py
# =============================================================================

class TestLocationActivityProfile:
    """LocationActivityProfile enum with WINTERSPORT, WANDERN, ALLGEMEIN."""

    def test_enum_exists(self):
        """
        GIVEN: src/app/user.py module
        WHEN: importing LocationActivityProfile
        THEN: import succeeds without error
        """
        from app.user import LocationActivityProfile
        assert LocationActivityProfile is not None

    def test_enum_values(self):
        """
        GIVEN: LocationActivityProfile enum
        WHEN: accessing values
        THEN: WINTERSPORT, WANDERN, ALLGEMEIN exist with correct string values
        """
        from app.user import LocationActivityProfile
        assert LocationActivityProfile.WINTERSPORT.value == "wintersport"
        assert LocationActivityProfile.WANDERN.value == "wandern"
        assert LocationActivityProfile.ALLGEMEIN.value == "allgemein"

    def test_enum_is_str_mixin(self):
        """
        GIVEN: LocationActivityProfile enum
        WHEN: used as string
        THEN: behaves like str (for JSON serialization)
        """
        from app.user import LocationActivityProfile
        profile = LocationActivityProfile.WANDERN
        assert isinstance(profile, str)
        assert profile == "wandern"


# =============================================================================
# Test 2: SavedLocation with new fields
# =============================================================================

class TestSavedLocationExtended:
    """SavedLocation gains activity_profile and display_config fields."""

    def test_default_activity_profile(self):
        """
        GIVEN: SavedLocation created without activity_profile
        WHEN: accessing activity_profile
        THEN: defaults to ALLGEMEIN
        """
        from app.user import SavedLocation, LocationActivityProfile
        loc = SavedLocation(
            id="test", name="Test", lat=47.0, lon=11.0, elevation_m=2000
        )
        assert loc.activity_profile == LocationActivityProfile.ALLGEMEIN

    def test_explicit_activity_profile(self):
        """
        GIVEN: SavedLocation created with activity_profile=WANDERN
        WHEN: accessing activity_profile
        THEN: returns WANDERN
        """
        from app.user import SavedLocation, LocationActivityProfile
        loc = SavedLocation(
            id="test", name="Test", lat=47.0, lon=11.0, elevation_m=2000,
            activity_profile=LocationActivityProfile.WANDERN,
        )
        assert loc.activity_profile == LocationActivityProfile.WANDERN

    def test_default_display_config_is_none(self):
        """
        GIVEN: SavedLocation created without display_config
        WHEN: accessing display_config
        THEN: returns None
        """
        from app.user import SavedLocation
        loc = SavedLocation(
            id="test", name="Test", lat=47.0, lon=11.0, elevation_m=2000
        )
        assert loc.display_config is None

    def test_explicit_display_config(self):
        """
        GIVEN: SavedLocation created with a UnifiedWeatherDisplayConfig
        WHEN: accessing display_config
        THEN: returns the config object
        """
        from app.user import SavedLocation, LocationActivityProfile
        from app.metric_catalog import build_default_display_config

        config = build_default_display_config("test")
        loc = SavedLocation(
            id="test", name="Test", lat=47.0, lon=11.0, elevation_m=2000,
            activity_profile=LocationActivityProfile.WINTERSPORT,
            display_config=config,
        )
        assert loc.display_config is not None
        assert loc.display_config.trip_id == "test"

    def test_frozen_with_new_fields(self):
        """
        GIVEN: SavedLocation with activity_profile and display_config
        WHEN: trying to mutate activity_profile
        THEN: raises FrozenInstanceError
        """
        from app.user import SavedLocation, LocationActivityProfile
        loc = SavedLocation(
            id="test", name="Test", lat=47.0, lon=11.0, elevation_m=2000,
            activity_profile=LocationActivityProfile.WANDERN,
        )
        with pytest.raises(AttributeError):
            loc.activity_profile = LocationActivityProfile.WINTERSPORT

    def test_existing_fields_unchanged(self):
        """
        GIVEN: SavedLocation with all fields
        WHEN: accessing bergfex_slug and region
        THEN: still works as before
        """
        from app.user import SavedLocation, LocationActivityProfile
        loc = SavedLocation(
            id="test", name="Test", lat=47.0, lon=11.0, elevation_m=2000,
            region="AT-7", bergfex_slug="hochfuegen",
            activity_profile=LocationActivityProfile.WINTERSPORT,
        )
        assert loc.region == "AT-7"
        assert loc.bergfex_slug == "hochfuegen"


# =============================================================================
# Test 3: Profile-based default metric configs
# =============================================================================

class TestProfileDefaultMetrics:
    """build_default_display_config_for_profile() factory."""

    def test_function_exists(self):
        """
        GIVEN: metric_catalog module
        WHEN: importing build_default_display_config_for_profile
        THEN: import succeeds
        """
        from app.metric_catalog import build_default_display_config_for_profile
        assert callable(build_default_display_config_for_profile)

    def test_wintersport_defaults(self):
        """
        GIVEN: profile=WINTERSPORT
        WHEN: building default display config
        THEN: winter-specific metrics are enabled (snow_depth, fresh_snow, wind_chill, etc.)
        """
        from app.user import LocationActivityProfile
        from app.metric_catalog import build_default_display_config_for_profile

        config = build_default_display_config_for_profile(
            "test-loc", LocationActivityProfile.WINTERSPORT
        )
        enabled_ids = {mc.metric_id for mc in config.metrics if mc.enabled}
        assert "snow_depth" in enabled_ids
        assert "fresh_snow" in enabled_ids
        assert "wind_chill" in enabled_ids
        assert "temperature" in enabled_ids

    def test_wandern_defaults(self):
        """
        GIVEN: profile=WANDERN
        WHEN: building default display config
        THEN: hiking metrics enabled, winter metrics disabled
        """
        from app.user import LocationActivityProfile
        from app.metric_catalog import build_default_display_config_for_profile

        config = build_default_display_config_for_profile(
            "test-loc", LocationActivityProfile.WANDERN
        )
        enabled_ids = {mc.metric_id for mc in config.metrics if mc.enabled}
        assert "humidity" in enabled_ids
        assert "uv_index" in enabled_ids
        assert "temperature" in enabled_ids
        # Winter metrics should NOT be enabled for hiking
        assert "snow_depth" not in enabled_ids
        assert "fresh_snow" not in enabled_ids

    def test_allgemein_defaults(self):
        """
        GIVEN: profile=ALLGEMEIN
        WHEN: building default display config
        THEN: only basic metrics enabled
        """
        from app.user import LocationActivityProfile
        from app.metric_catalog import build_default_display_config_for_profile

        config = build_default_display_config_for_profile(
            "test-loc", LocationActivityProfile.ALLGEMEIN
        )
        enabled_ids = {mc.metric_id for mc in config.metrics if mc.enabled}
        assert "temperature" in enabled_ids
        assert "wind" in enabled_ids
        assert "precipitation" in enabled_ids
        # Advanced metrics should NOT be enabled
        assert "snow_depth" not in enabled_ids
        assert "thunder" not in enabled_ids

    def test_returns_unified_display_config(self):
        """
        GIVEN: any profile
        WHEN: building default display config
        THEN: returns UnifiedWeatherDisplayConfig with correct trip_id (=location_id)
        """
        from app.user import LocationActivityProfile
        from app.metric_catalog import build_default_display_config_for_profile
        from app.models import UnifiedWeatherDisplayConfig

        config = build_default_display_config_for_profile(
            "my-location", LocationActivityProfile.ALLGEMEIN
        )
        assert isinstance(config, UnifiedWeatherDisplayConfig)
        assert config.trip_id == "my-location"

    def test_all_catalog_metrics_present(self):
        """
        GIVEN: any profile
        WHEN: building default display config
        THEN: all MetricCatalog metrics are present (some enabled, some disabled)
        """
        from app.user import LocationActivityProfile
        from app.metric_catalog import (
            build_default_display_config_for_profile,
            get_all_metrics,
        )

        config = build_default_display_config_for_profile(
            "test", LocationActivityProfile.WANDERN
        )
        config_ids = {mc.metric_id for mc in config.metrics}
        catalog_ids = {m.id for m in get_all_metrics()}
        assert config_ids == catalog_ids


# =============================================================================
# Test 4: Loader round-trip (serialize + deserialize)
# =============================================================================

class TestLoaderRoundTrip:
    """Loader persists and loads activity_profile and display_config."""

    def test_save_load_with_activity_profile(self):
        """
        GIVEN: SavedLocation with activity_profile=WANDERN
        WHEN: saved to JSON and loaded back
        THEN: activity_profile round-trips correctly
        """
        from app.user import SavedLocation, LocationActivityProfile
        from app.loader import save_location, load_all_locations

        loc = SavedLocation(
            id="roundtrip-test", name="Roundtrip", lat=47.0, lon=11.0,
            elevation_m=2000, activity_profile=LocationActivityProfile.WANDERN,
        )
        save_location(loc, user_id="__test_roundtrip__")
        loaded = load_all_locations(user_id="__test_roundtrip__")

        assert len(loaded) >= 1
        found = [l for l in loaded if l.id == "roundtrip-test"]
        assert len(found) == 1
        assert found[0].activity_profile == LocationActivityProfile.WANDERN

    def test_save_load_with_display_config(self):
        """
        GIVEN: SavedLocation with display_config
        WHEN: saved to JSON and loaded back
        THEN: display_config round-trips with correct metrics
        """
        from app.user import SavedLocation, LocationActivityProfile
        from app.metric_catalog import build_default_display_config_for_profile
        from app.loader import save_location, load_all_locations

        config = build_default_display_config_for_profile(
            "dc-test", LocationActivityProfile.WINTERSPORT
        )
        loc = SavedLocation(
            id="dc-test", name="Config Test", lat=47.0, lon=11.0,
            elevation_m=2000,
            activity_profile=LocationActivityProfile.WINTERSPORT,
            display_config=config,
        )
        save_location(loc, user_id="__test_dc__")
        loaded = load_all_locations(user_id="__test_dc__")

        found = [l for l in loaded if l.id == "dc-test"]
        assert len(found) == 1
        assert found[0].display_config is not None
        enabled_ids = {mc.metric_id for mc in found[0].display_config.metrics if mc.enabled}
        assert "snow_depth" in enabled_ids

    def test_backward_compat_no_activity_profile(self):
        """
        GIVEN: Legacy location JSON without activity_profile field
        WHEN: loaded via load_all_locations
        THEN: defaults to ALLGEMEIN, no error
        """
        from app.user import LocationActivityProfile
        from app.loader import load_all_locations, get_locations_dir

        # Write legacy JSON directly
        loc_dir = get_locations_dir("__test_legacy__")
        loc_dir.mkdir(parents=True, exist_ok=True)
        legacy_data = {
            "id": "legacy-loc",
            "name": "Legacy",
            "lat": 47.0,
            "lon": 11.0,
            "elevation_m": 1500,
            "region": None,
            "bergfex_slug": None,
        }
        with open(loc_dir / "legacy-loc.json", "w") as f:
            json.dump(legacy_data, f)

        loaded = load_all_locations(user_id="__test_legacy__")
        found = [l for l in loaded if l.id == "legacy-loc"]
        assert len(found) == 1
        assert found[0].activity_profile == LocationActivityProfile.ALLGEMEIN
        assert found[0].display_config is None

    def test_json_contains_activity_profile(self):
        """
        GIVEN: SavedLocation with activity_profile=WINTERSPORT
        WHEN: saved to JSON
        THEN: JSON file contains "activity_profile": "wintersport"
        """
        from app.user import SavedLocation, LocationActivityProfile
        from app.loader import save_location, get_locations_dir

        loc = SavedLocation(
            id="json-check", name="JSON Check", lat=47.0, lon=11.0,
            elevation_m=2000, activity_profile=LocationActivityProfile.WINTERSPORT,
        )
        save_location(loc, user_id="__test_json__")

        json_path = get_locations_dir("__test_json__") / "json-check.json"
        with open(json_path) as f:
            data = json.load(f)
        assert data["activity_profile"] == "wintersport"

    def test_json_contains_display_config(self):
        """
        GIVEN: SavedLocation with display_config
        WHEN: saved to JSON
        THEN: JSON file contains "display_config" with metrics list
        """
        from app.user import SavedLocation, LocationActivityProfile
        from app.metric_catalog import build_default_display_config_for_profile
        from app.loader import save_location, get_locations_dir

        config = build_default_display_config_for_profile(
            "json-dc", LocationActivityProfile.WANDERN
        )
        loc = SavedLocation(
            id="json-dc", name="DC Check", lat=47.0, lon=11.0,
            elevation_m=2000,
            activity_profile=LocationActivityProfile.WANDERN,
            display_config=config,
        )
        save_location(loc, user_id="__test_json_dc__")

        json_path = get_locations_dir("__test_json_dc__") / "json-dc.json"
        with open(json_path) as f:
            data = json.load(f)
        assert "display_config" in data
        assert "metrics" in data["display_config"]
        assert len(data["display_config"]["metrics"]) > 0
