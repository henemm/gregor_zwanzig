"""
Tests fuer F11b: Generic Locations UI.

v1.1 (Bug #89): Location-Dialog-Tests entfernt — die Funktionen
`show_location_weather_config_dialog` und das Modul `web.pages.locations`
wurden entfernt (UI-tot seit F76: /locations -> 301 -> /compare).

Verbleibende Tests: Provider-Detection (lat/lon-basiert) bleibt fuer den
Loader / SvelteKit-Frontend / Go-API relevant.
"""


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
