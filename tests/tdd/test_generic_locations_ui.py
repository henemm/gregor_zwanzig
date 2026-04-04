"""
TDD RED tests for F11b: Generic Locations UI.

Tests the UI-layer additions:
- Provider detection for locations
- Location weather config dialog existence
- Profile dropdown integration
- Wetter-Metriken button handler pattern

All tests MUST FAIL before implementation (TDD RED phase).
"""
import pytest


# =============================================================================
# Test 1: Provider Detection for Locations
# =============================================================================

class TestProviderDetectionForLocations:
    """get_available_providers_for_location() function."""

    def test_function_exists(self):
        """
        GIVEN: weather_config module
        WHEN: importing get_available_providers_for_location
        THEN: import succeeds
        """
        from web.pages.weather_config import get_available_providers_for_location
        assert callable(get_available_providers_for_location)

    def test_austria_location_has_geosphere(self):
        """
        GIVEN: Location in Austria (Innsbruck: lat=47.3, lon=11.4)
        WHEN: detecting available providers
        THEN: both openmeteo and geosphere available
        """
        from app.user import SavedLocation
        from web.pages.weather_config import get_available_providers_for_location

        loc = SavedLocation(
            id="innsbruck", name="Innsbruck", lat=47.3, lon=11.4, elevation_m=600
        )
        providers = get_available_providers_for_location(loc)
        assert "openmeteo" in providers
        assert "geosphere" in providers

    def test_non_austria_location_no_geosphere(self):
        """
        GIVEN: Location outside Austria (Corsica: lat=42.0, lon=9.0)
        WHEN: detecting available providers
        THEN: only openmeteo available, no geosphere
        """
        from app.user import SavedLocation
        from web.pages.weather_config import get_available_providers_for_location

        loc = SavedLocation(
            id="corsica", name="Corsica", lat=42.0, lon=9.0, elevation_m=1500
        )
        providers = get_available_providers_for_location(loc)
        assert "openmeteo" in providers
        assert "geosphere" not in providers

    def test_austria_boundary_south(self):
        """
        GIVEN: Location at south boundary of Austria box (lat=46.0)
        WHEN: detecting available providers
        THEN: geosphere available (inclusive boundary)
        """
        from app.user import SavedLocation
        from web.pages.weather_config import get_available_providers_for_location

        loc = SavedLocation(
            id="border", name="South Border", lat=46.0, lon=13.0, elevation_m=500
        )
        providers = get_available_providers_for_location(loc)
        assert "geosphere" in providers

    def test_austria_boundary_outside(self):
        """
        GIVEN: Location just south of Austria box (lat=45.9)
        WHEN: detecting available providers
        THEN: no geosphere
        """
        from app.user import SavedLocation
        from web.pages.weather_config import get_available_providers_for_location

        loc = SavedLocation(
            id="italy", name="Italy", lat=45.9, lon=13.0, elevation_m=500
        )
        providers = get_available_providers_for_location(loc)
        assert "geosphere" not in providers


# =============================================================================
# Test 2: Location Weather Config Dialog exists
# =============================================================================

class TestLocationWeatherConfigDialog:
    """show_location_weather_config_dialog() function."""

    def test_function_exists(self):
        """
        GIVEN: weather_config module
        WHEN: importing show_location_weather_config_dialog
        THEN: import succeeds
        """
        from web.pages.weather_config import show_location_weather_config_dialog
        assert callable(show_location_weather_config_dialog)

    def test_function_signature(self):
        """
        GIVEN: show_location_weather_config_dialog function
        WHEN: inspecting its signature
        THEN: accepts location and optional user_id parameters
        """
        import inspect
        from web.pages.weather_config import show_location_weather_config_dialog

        sig = inspect.signature(show_location_weather_config_dialog)
        params = list(sig.parameters.keys())
        assert "location" in params
        assert "user_id" in params


# =============================================================================
# Test 3: Locations page imports LocationActivityProfile
# =============================================================================

class TestLocationsPageImports:
    """Locations page must import LocationActivityProfile for dropdown."""

    def test_locations_module_imports_profile(self):
        """
        GIVEN: locations page module
        WHEN: checking if LocationActivityProfile is used
        THEN: the module can access LocationActivityProfile
        """
        from web.pages import locations
        from app.user import LocationActivityProfile

        # The module should use LocationActivityProfile
        source = open(locations.__file__).read()
        assert "LocationActivityProfile" in source

    def test_locations_module_imports_weather_config(self):
        """
        GIVEN: locations page module
        WHEN: checking if weather config dialog is imported
        THEN: show_location_weather_config_dialog is imported
        """
        from web.pages import locations

        source = open(locations.__file__).read()
        assert "show_location_weather_config_dialog" in source
