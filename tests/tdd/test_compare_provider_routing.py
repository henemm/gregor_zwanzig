"""
TDD RED: Compare Provider Routing — Provider-Auswahl pro Location.

Bug: fetch_forecast_for_location() hardcodes GeoSphereProvider,
     Locations ausserhalb Alpenraum (z.B. Mallorca) bekommen HTTP 400.

Fix: _select_provider_for_location() waehlt GeoSphere fuer Alpen,
     OpenMeteo fuer alles andere.

Spec: docs/specs/bugfix/compare_provider_routing.md
"""


# ---------------------------------------------------------------------------
# Test 1: Provider-Auswahl nach Koordinaten
# ---------------------------------------------------------------------------

class TestSelectProviderForLocation:
    """Provider selection based on geographic coordinates."""

    def test_alpenraum_returns_geosphere(self):
        """
        GIVEN: Coordinates in the Alps (Innsbruck, 47.3N, 11.4E)
        WHEN: _select_provider_for_location is called
        THEN: Returns GeoSphereProvider instance
        """
        from providers.geosphere import GeoSphereProvider
        from web.pages.compare import _select_provider_for_location

        provider = _select_provider_for_location(47.3, 11.4)
        assert isinstance(provider, GeoSphereProvider)
        provider.close()

    def test_mallorca_returns_openmeteo(self):
        """
        GIVEN: Coordinates on Mallorca (Valdemossa, 39.7N, 2.6E)
        WHEN: _select_provider_for_location is called
        THEN: Returns OpenMeteoProvider instance
        """
        from providers.openmeteo import OpenMeteoProvider
        from web.pages.compare import _select_provider_for_location

        provider = _select_provider_for_location(39.7, 2.6)
        assert isinstance(provider, OpenMeteoProvider)

    def test_boundary_lower_left_returns_geosphere(self):
        """
        GIVEN: Coordinates exactly on lower-left GeoSphere bound (45.0N, 8.0E)
        WHEN: _select_provider_for_location is called
        THEN: Returns GeoSphereProvider (inclusive bounds)
        """
        from providers.geosphere import GeoSphereProvider
        from web.pages.compare import _select_provider_for_location

        provider = _select_provider_for_location(45.0, 8.0)
        assert isinstance(provider, GeoSphereProvider)
        provider.close()

    def test_boundary_upper_right_returns_geosphere(self):
        """
        GIVEN: Coordinates exactly on upper-right GeoSphere bound (50.0N, 18.0E)
        WHEN: _select_provider_for_location is called
        THEN: Returns GeoSphereProvider (inclusive bounds)
        """
        from providers.geosphere import GeoSphereProvider
        from web.pages.compare import _select_provider_for_location

        provider = _select_provider_for_location(50.0, 18.0)
        assert isinstance(provider, GeoSphereProvider)
        provider.close()

    def test_scandinavia_returns_openmeteo(self):
        """
        GIVEN: Coordinates in Scandinavia (Oslo, 59.9N, 10.8E)
        WHEN: _select_provider_for_location is called
        THEN: Returns OpenMeteoProvider (outside GeoSphere bounds)
        """
        from providers.openmeteo import OpenMeteoProvider
        from web.pages.compare import _select_provider_for_location

        provider = _select_provider_for_location(59.9, 10.8)
        assert isinstance(provider, OpenMeteoProvider)


# ---------------------------------------------------------------------------
# Test 2: Echter API-Call Mallorca (kein HTTP 400 mehr)
# ---------------------------------------------------------------------------

class TestFetchForecastMallorca:
    """Real API calls for Mallorca locations must succeed."""

    def test_valdemossa_returns_data(self):
        """
        GIVEN: Valdemossa location (Mallorca, 39.71N, 2.63E)
        WHEN: fetch_forecast_for_location is called
        THEN: Returns valid weather data (no error, raw_data present)
        """
        from app.loader import SavedLocation
        from web.pages.compare import fetch_forecast_for_location

        loc = SavedLocation(
            id="test-valdemossa",
            name="Valdemossa",
            lat=39.71,
            lon=2.63,
            elevation_m=600,
        )
        result = fetch_forecast_for_location(loc, hours=48)

        assert result["error"] is None, f"Expected no error, got: {result['error']}"
        assert len(result.get("raw_data", [])) > 0, "Expected raw_data with data points"
        assert result.get("temp_min") is not None, "Expected temp_min to be set"
        assert result.get("temp_max") is not None, "Expected temp_max to be set"

    def test_pollenca_returns_data(self):
        """
        GIVEN: Pollenca location (Mallorca, 39.9N, 3.08E)
        WHEN: fetch_forecast_for_location is called
        THEN: Returns valid weather data
        """
        from app.loader import SavedLocation
        from web.pages.compare import fetch_forecast_for_location

        loc = SavedLocation(
            id="test-pollenca",
            name="Pollenca",
            lat=39.90,
            lon=3.08,
            elevation_m=10,
        )
        result = fetch_forecast_for_location(loc, hours=48)

        assert result["error"] is None, f"Expected no error, got: {result['error']}"
        assert len(result.get("raw_data", [])) > 0


# ---------------------------------------------------------------------------
# Test 3: Regression — Alpenraum funktioniert weiterhin
# ---------------------------------------------------------------------------

class TestFetchForecastAlpsRegression:
    """Alps locations must continue to work with GeoSphere + SNOWGRID."""

    def test_innsbruck_returns_data(self):
        """
        GIVEN: Innsbruck location (Alps, 47.26N, 11.39E)
        WHEN: fetch_forecast_for_location is called
        THEN: Returns valid weather data via GeoSphere
        """
        from app.loader import SavedLocation
        from web.pages.compare import fetch_forecast_for_location

        loc = SavedLocation(
            id="test-innsbruck",
            name="Innsbruck",
            lat=47.26,
            lon=11.39,
            elevation_m=574,
        )
        result = fetch_forecast_for_location(loc, hours=48)

        assert result["error"] is None, f"Expected no error, got: {result['error']}"
        assert len(result.get("raw_data", [])) > 0
        assert result.get("temp_min") is not None
