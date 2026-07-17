"""
TDD: Compare Provider Routing — Ortsvergleich holt ueberall openmeteo.

Historie: fetch_forecast_for_location() hardcodete frueher GeoSphereProvider
fuer Alpen-Koordinaten, Locations ausserhalb Alpenraum (z.B. Mallorca)
bekamen HTTP 400. Die standort-basierte Provider-Auswahl
(_select_provider_for_location) wurde danach eingefuehrt (GeoSphere fuer
Alpen, OpenMeteo fuer den Rest) und ist seit Epic #1301 A2 wieder entfallen:
der Vergleich holt jetzt ueberall ueber get_provider("openmeteo").

Spec: docs/specs/modules/epic_1301_a2_compare_openmeteo.md
"""
import pytest

pytestmark = pytest.mark.live


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
        from services.comparison_engine import fetch_forecast_for_location

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
        from services.comparison_engine import fetch_forecast_for_location

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
    """Alps locations must continue to work — now via openmeteo (A2)."""

    def test_innsbruck_returns_data(self):
        """
        GIVEN: Innsbruck location (Alps, 47.26N, 11.39E)
        WHEN: fetch_forecast_for_location is called
        THEN: Returns valid weather data via openmeteo
        """
        from app.loader import SavedLocation
        from services.comparison_engine import fetch_forecast_for_location

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
