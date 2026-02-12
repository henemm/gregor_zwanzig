"""
TDD Tests for Weather Config Phase 2: API-Aware UI.

Tests verify:
1. Provider detection from trip waypoint coordinates
2. Category grouping (5 categories from MetricCatalog)
3. 19 metrics from MetricCatalog (15 base + 4 new: visibility, rain_probability, cape, freezing_level)
4. Grayed-out unavailable metrics
5. Per-metric aggregation dropdowns
6. Saves as UnifiedWeatherDisplayConfig (not legacy TripWeatherConfig)

SPEC: docs/specs/modules/weather_config.md v2.1 (Phase 2)

These tests MUST FAIL (RED) because Phase 2 is not implemented yet.
"""

import json
import os
import subprocess
import sys
import time
from datetime import date, time as dt_time
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import sync_playwright

# Add src to path for direct imports
sys.path.insert(0, "/opt/gregor_zwanziger/src")

from app.trip import Trip, Stage, Waypoint, TimeWindow


SERVER_PORT = 18092
SERVER_URL = f"http://localhost:{SERVER_PORT}"


# --- Test Data ---

def _make_trip_austria() -> Trip:
    """Trip with waypoints in Austria -> GeoSphere + OpenMeteo available."""
    return Trip(
        id="test-austria",
        name="Stubaier Skitour",
        stages=[Stage(
            id="T1", name="Tag 1", date=date(2026, 3, 1),
            waypoints=[
                Waypoint(id="G1", name="Neustift", lat=47.1, lon=11.3, elevation_m=1000),
                Waypoint(id="G2", name="Elferhuette", lat=47.08, lon=11.32, elevation_m=2080),
            ],
        )],
    )


def _make_trip_corsica() -> Trip:
    """Trip with waypoints in Corsica -> only OpenMeteo available."""
    return Trip(
        id="test-corsica",
        name="GR20 Etappe 1",
        stages=[Stage(
            id="T1", name="Tag 1", date=date(2026, 6, 15),
            waypoints=[
                Waypoint(id="G1", name="Calenzana", lat=42.5, lon=8.85, elevation_m=275),
                Waypoint(id="G2", name="Ortu di Piobbu", lat=42.38, lon=8.92, elevation_m=1570),
            ],
        )],
    )


# --- Fixtures ---

@pytest.fixture(scope="module")
def running_server():
    """Start real NiceGUI server for E2E tests."""
    log = open("/tmp/nicegui_weather_config_test.log", "w")
    python = "/opt/gregor_zwanziger/.venv/bin/python3"
    env = {k: v for k, v in os.environ.items()
           if "PYTEST" not in k and "NICEGUI" not in k}
    proc = subprocess.Popen(
        [python, "-c",
         "import sys; sys.path.insert(0, 'src'); "
         "from nicegui import ui, app; "
         "from web.main import *; "
         f"ui.run(port={SERVER_PORT}, reload=False, show=False)"],
        cwd="/opt/gregor_zwanziger",
        stdout=log,
        stderr=log,
        env=env,
    )
    for _ in range(60):
        poll = proc.poll()
        if poll is not None:
            log.close()
            with open("/tmp/nicegui_weather_config_test.log") as f:
                pytest.fail(f"Server exited with code {poll}: {f.read()[:500]}")
        try:
            resp = httpx.get(SERVER_URL, timeout=2, follow_redirects=True)
            if resp.status_code == 200:
                break
        except (httpx.ConnectError, httpx.ReadTimeout):
            time.sleep(0.5)
    else:
        proc.kill()
        log.close()
        with open("/tmp/nicegui_weather_config_test.log") as f:
            pytest.fail(f"Server did not start within 30s. Log: {f.read()[:500]}")

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


# =============================================================================
# Test 1: Provider Detection Function
# =============================================================================

class TestProviderDetection:
    """Test get_available_providers_for_trip() function."""

    def test_function_exists(self):
        """
        GIVEN: weather_config module
        WHEN: importing get_available_providers_for_trip
        THEN: function exists and is callable

        Expected RED: Function doesn't exist yet.
        """
        from web.pages.weather_config import get_available_providers_for_trip
        assert callable(get_available_providers_for_trip)

    def test_austria_trip_has_geosphere(self):
        """
        GIVEN: Trip with waypoints in Austria (47.1N, 11.3E)
        WHEN: detecting available providers
        THEN: both openmeteo and geosphere are available

        Expected RED: Function doesn't exist yet.
        """
        from web.pages.weather_config import get_available_providers_for_trip
        trip = _make_trip_austria()
        providers = get_available_providers_for_trip(trip)
        assert "openmeteo" in providers, "OpenMeteo should always be available"
        assert "geosphere" in providers, "GeoSphere should be available for Austria"

    def test_corsica_trip_only_openmeteo(self):
        """
        GIVEN: Trip with waypoints in Corsica (42.5N, 8.85E - outside Austria)
        WHEN: detecting available providers
        THEN: only openmeteo is available (no geosphere)

        Expected RED: Function doesn't exist yet.
        """
        from web.pages.weather_config import get_available_providers_for_trip
        trip = _make_trip_corsica()
        providers = get_available_providers_for_trip(trip)
        assert "openmeteo" in providers, "OpenMeteo should always be available"
        assert "geosphere" not in providers, "GeoSphere should NOT be available for Corsica"

    def test_returns_set_type(self):
        """
        GIVEN: Any trip
        WHEN: detecting available providers
        THEN: returns a set of strings

        Expected RED: Function doesn't exist yet.
        """
        from web.pages.weather_config import get_available_providers_for_trip
        trip = _make_trip_austria()
        result = get_available_providers_for_trip(trip)
        assert isinstance(result, set), f"Expected set, got {type(result)}"


# =============================================================================
# Test 2: Category Grouping in UI
# =============================================================================

class TestCategoryGrouping:
    """Test that dialog shows metrics grouped by 5 categories."""

    def test_category_headers_present(self, running_server):
        """
        GIVEN: Weather config dialog is open
        WHEN: inspecting dialog content
        THEN: 5 category headers are visible

        Expected RED: Dialog uses old Basis/Extended grouping, not 5 categories.
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            page.goto(f"{SERVER_URL}/trips", timeout=10000)
            time.sleep(2)

            page.locator('button:has-text("Wetter-Metriken")').first.click()
            time.sleep(1)

            page.screenshot(path="/tmp/weather_config_categories.png")

            expected_categories = ["Temperatur", "Wind", "Niederschlag", "Atmosphäre", "Winter"]
            found = 0
            for category in expected_categories:
                header = page.locator(f"text={category}")
                if header.count() > 0:
                    found += 1

            assert found == 5, (
                f"Expected 5 category headers, found {found}. "
                "Phase 2 requires: Temperatur, Wind, Niederschlag, Atmosphäre, Winter"
            )

            browser.close()

    def test_no_old_basis_extended_sections(self, running_server):
        """
        GIVEN: Weather config dialog is open
        WHEN: inspecting dialog content
        THEN: old section headers are gone

        Expected RED: Old headers still present.
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            page.goto(f"{SERVER_URL}/trips", timeout=10000)
            time.sleep(2)

            page.locator('button:has-text("Wetter-Metriken")').first.click()
            time.sleep(1)

            basis = page.locator('text=Basis-Metriken')
            extended = page.locator('text=Erweiterte Metriken')
            assert basis.count() == 0, "Old 'Basis-Metriken' header still present"
            assert extended.count() == 0, "Old 'Erweiterte Metriken' header still present"

            browser.close()


# =============================================================================
# Test 3: 15 Metrics from MetricCatalog
# =============================================================================

class TestMetricCount:
    """Test that dialog shows all 15 metrics from MetricCatalog."""

    def test_fifteen_metric_checkboxes(self, running_server):
        """
        GIVEN: Weather config dialog is open
        WHEN: counting checkboxes
        THEN: exactly 15 checkboxes (one per MetricCatalog metric)

        Expected RED: Current dialog shows 13 hardcoded checkboxes.
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            page.goto(f"{SERVER_URL}/trips", timeout=10000)
            time.sleep(2)

            page.locator('button:has-text("Wetter-Metriken")').first.click()
            time.sleep(1)

            page.screenshot(path="/tmp/weather_config_15_metrics.png")

            checkboxes = page.locator("div.q-checkbox")
            count = checkboxes.count()
            assert count >= 15, (
                f"Expected at least 15 metric checkboxes (from MetricCatalog), found {count}. "
                "Phase 2 replaces 13 hardcoded metrics with metrics from MetricCatalog."
            )

            browser.close()

    def test_metric_labels_from_catalog(self, running_server):
        """
        GIVEN: Weather config dialog is open
        WHEN: checking metric labels
        THEN: labels match MetricCatalog label_de values

        Expected RED: Labels are hardcoded old format.
        """
        from app.metric_catalog import get_all_metrics

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            page.goto(f"{SERVER_URL}/trips", timeout=10000)
            time.sleep(2)

            page.locator('button:has-text("Wetter-Metriken")').first.click()
            time.sleep(1)

            # Check specific MetricCatalog labels that differ from old hardcoded ones
            new_labels = ["Schneefallgrenze", "Tiefe Wolken", "Mittelhohe Wolken",
                          "Hohe Wolken", "Schneehöhe"]
            found = 0
            for label in new_labels:
                if page.locator(f"text={label}").count() > 0:
                    found += 1

            assert found == len(new_labels), (
                f"Only {found}/{len(new_labels)} MetricCatalog labels found. "
                "Phase 2 should show all labels from MetricCatalog."
            )

            browser.close()


# =============================================================================
# Test 4: Aggregation Dropdowns
# =============================================================================

class TestAggregationDropdowns:
    """Test per-metric aggregation selection dropdowns."""

    def test_aggregation_selects_present(self, running_server):
        """
        GIVEN: Weather config dialog is open
        WHEN: inspecting per-metric rows
        THEN: aggregation selection elements exist

        Expected RED: Current dialog has no aggregation dropdowns.
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            page.goto(f"{SERVER_URL}/trips", timeout=10000)
            time.sleep(2)

            page.locator('button:has-text("Wetter-Metriken")').first.click()
            time.sleep(1)

            page.screenshot(path="/tmp/weather_config_aggregations.png")

            # NiceGUI ui.select with label="Agg" - one per metric
            # Disabled selects lose role="combobox", so count by Agg label
            dialog = page.locator("div.q-dialog")
            agg_selects = dialog.locator("label:has-text('Agg')")
            count = agg_selects.count()
            assert count >= 15, (
                f"Expected at least 15 aggregation dropdowns, found {count}. "
                "Phase 2 requires per-metric aggregation selection."
            )

            browser.close()


# =============================================================================
# Test 5: Provider Header Info
# =============================================================================

class TestProviderInfo:
    """Test provider information display in dialog header."""

    def test_provider_info_shown(self, running_server):
        """
        GIVEN: Weather config dialog is open
        WHEN: inspecting dialog header
        THEN: provider name(s) are displayed

        Expected RED: Current dialog has no provider info.
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            page.goto(f"{SERVER_URL}/trips", timeout=10000)
            time.sleep(2)

            page.locator('button:has-text("Wetter-Metriken")').first.click()
            time.sleep(1)

            page.screenshot(path="/tmp/weather_config_provider_info.png")

            provider_text = page.locator("text=Provider")
            openmeteo_text = page.locator("text=OpenMeteo")
            assert provider_text.count() > 0 or openmeteo_text.count() > 0, (
                "No provider info found in dialog header. "
                "Phase 2 shows available providers."
            )

            browser.close()


# =============================================================================
# Test 6: Save as UnifiedWeatherDisplayConfig
# =============================================================================

class TestSaveFormat:
    """Test that save creates UnifiedWeatherDisplayConfig, not TripWeatherConfig."""

    def test_save_creates_display_config_with_aggregations(self, running_server):
        """
        GIVEN: Weather config dialog with metrics selected
        WHEN: clicking save
        THEN: trip JSON has display_config with MetricConfig including aggregations

        Expected RED: Current save creates TripWeatherConfig (old format).
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            page.goto(f"{SERVER_URL}/trips", timeout=10000)
            time.sleep(2)

            page.locator('button:has-text("Wetter-Metriken")').first.click()
            time.sleep(1)

            # Click save with defaults
            page.locator('button:has-text("Speichern")').click()
            time.sleep(1)

            browser.close()

        # Read saved trip JSON and check format
        trips_dir = Path("/opt/gregor_zwanziger/data/users/default/trips")
        trip_files = list(trips_dir.glob("*.json"))
        assert len(trip_files) > 0, "No trip files found"

        trip_data = json.loads(trip_files[0].read_text())

        dc = trip_data.get("display_config")
        assert dc is not None, (
            "display_config not found in trip JSON after save. "
            "Phase 2 should save as UnifiedWeatherDisplayConfig."
        )
        assert "metrics" in dc, "display_config.metrics not found"

        metrics = dc["metrics"]
        assert len(metrics) > 0, "No metrics in display_config"
        first = metrics[0]
        assert "metric_id" in first, "MetricConfig should have metric_id field"
        assert "aggregations" in first, "MetricConfig should have aggregations field"
        assert "enabled" in first, "MetricConfig should have enabled field"
        # Verify aggregations is a list (not just a boolean)
        assert isinstance(first["aggregations"], list), (
            f"aggregations should be list, got {type(first['aggregations'])}"
        )


# =============================================================================
# Test 7: OpenMeteo Additional Metrics - MetricCatalog Registration
# SPEC: docs/specs/modules/openmeteo_additional_metrics.md v1.0
# =============================================================================

class TestAdditionalMetricsCatalog:
    """Test that 4 new metrics are registered in MetricCatalog."""

    def test_catalog_has_19_metrics(self):
        """
        GIVEN: MetricCatalog with additional metrics registered
        WHEN: counting all metrics
        THEN: exactly 19 metrics (15 base + 4 new)

        Expected RED: Currently 15 metrics, missing visibility/rain_probability/cape/freezing_level.
        """
        from app.metric_catalog import get_all_metrics
        metrics = get_all_metrics()
        assert len(metrics) == 19, (
            f"Expected 19 metrics (15 base + 4 new), got {len(metrics)}. "
            "Missing: visibility, rain_probability, cape, freezing_level"
        )

    def test_visibility_metric_exists(self):
        """
        GIVEN: MetricCatalog
        WHEN: looking up 'visibility' metric
        THEN: metric exists with correct properties

        Expected RED: 'visibility' not registered in catalog.
        """
        from app.metric_catalog import get_metric
        m = get_metric("visibility")
        assert m.dp_field == "visibility_m"
        assert m.unit == "m"
        assert m.category == "atmosphere"
        assert m.default_enabled is False

    def test_rain_probability_metric_exists(self):
        """
        GIVEN: MetricCatalog
        WHEN: looking up 'rain_probability' metric
        THEN: metric exists with correct properties

        Expected RED: 'rain_probability' not registered in catalog.
        """
        from app.metric_catalog import get_metric
        m = get_metric("rain_probability")
        assert m.dp_field == "pop_pct"
        assert m.unit == "%"
        assert m.category == "precipitation"
        assert m.default_enabled is False

    def test_cape_metric_exists(self):
        """
        GIVEN: MetricCatalog
        WHEN: looking up 'cape' metric
        THEN: metric exists with correct properties

        Expected RED: 'cape' not registered in catalog.
        """
        from app.metric_catalog import get_metric
        m = get_metric("cape")
        assert m.dp_field == "cape_jkg"
        assert m.unit == "J/kg"
        assert m.category == "precipitation"
        assert m.default_enabled is False

    def test_freezing_level_metric_exists(self):
        """
        GIVEN: MetricCatalog
        WHEN: looking up 'freezing_level' metric
        THEN: metric exists with correct properties

        Expected RED: 'freezing_level' not registered in catalog.
        """
        from app.metric_catalog import get_metric
        m = get_metric("freezing_level")
        assert m.dp_field == "freezing_level_m"
        assert m.unit == "m"
        assert m.category == "winter"
        assert m.default_enabled is False

    def test_new_metrics_categories(self):
        """
        GIVEN: MetricCatalog with new metrics
        WHEN: grouping by category
        THEN: precipitation has +2, atmosphere has +1, winter has +1

        Expected RED: New metrics not in catalog yet.
        """
        from app.metric_catalog import get_metrics_by_category
        precip = get_metrics_by_category("precipitation")
        atmosphere = get_metrics_by_category("atmosphere")
        winter = get_metrics_by_category("winter")

        precip_ids = [m.id for m in precip]
        assert "rain_probability" in precip_ids, "rain_probability missing from precipitation"
        assert "cape" in precip_ids, "cape missing from precipitation"

        atmo_ids = [m.id for m in atmosphere]
        assert "visibility" in atmo_ids, "visibility missing from atmosphere"

        winter_ids = [m.id for m in winter]
        assert "freezing_level" in winter_ids, "freezing_level missing from winter"


# =============================================================================
# Test 8: OpenMeteo Provider - New Parameters
# SPEC: docs/specs/modules/openmeteo_additional_metrics.md v1.0
# =============================================================================

class TestOpenMeteoNewParameters:
    """Test that OpenMeteo provider fetches and parses new parameters."""

    def test_provider_returns_cape(self):
        """
        GIVEN: OpenMeteo provider fetching forecast
        WHEN: parsing response with CAPE data
        THEN: ForecastDataPoint.cape_jkg is NOT None

        Expected RED: cape_jkg is hardcoded to None in openmeteo.py line 295.
        """
        from providers.openmeteo import OpenMeteoProvider
        from app.config import Location

        provider = OpenMeteoProvider()
        loc = Location(
            name="Innsbruck",
            latitude=47.26,
            longitude=11.39,
            elevation_m=574,
        )
        ts = provider.fetch_forecast(loc)

        # Check at least some data points have CAPE values
        cape_values = [dp.cape_jkg for dp in ts.data if dp.cape_jkg is not None]
        assert len(cape_values) > 0, (
            "Expected at least some non-None cape_jkg values from OpenMeteo. "
            "Currently hardcoded to None in openmeteo.py."
        )

    def test_provider_returns_pop(self):
        """
        GIVEN: OpenMeteo provider fetching forecast
        WHEN: parsing response with precipitation_probability data
        THEN: ForecastDataPoint.pop_pct is NOT None

        Expected RED: pop_pct is hardcoded to None in openmeteo.py line 296.
        """
        from providers.openmeteo import OpenMeteoProvider
        from app.config import Location

        provider = OpenMeteoProvider()
        loc = Location(
            name="Innsbruck",
            latitude=47.26,
            longitude=11.39,
            elevation_m=574,
        )
        ts = provider.fetch_forecast(loc)

        pop_values = [dp.pop_pct for dp in ts.data if dp.pop_pct is not None]
        assert len(pop_values) > 0, (
            "Expected at least some non-None pop_pct values from OpenMeteo. "
            "Currently hardcoded to None in openmeteo.py."
        )

    def test_provider_returns_visibility(self):
        """
        GIVEN: OpenMeteo provider fetching forecast
        WHEN: parsing response with visibility data
        THEN: ForecastDataPoint.visibility_m is NOT None

        Expected RED: visibility_m is hardcoded to None in openmeteo.py line 313.
        """
        from providers.openmeteo import OpenMeteoProvider
        from app.config import Location

        provider = OpenMeteoProvider()
        loc = Location(
            name="Innsbruck",
            latitude=47.26,
            longitude=11.39,
            elevation_m=574,
        )
        ts = provider.fetch_forecast(loc)

        vis_values = [dp.visibility_m for dp in ts.data if dp.visibility_m is not None]
        assert len(vis_values) > 0, (
            "Expected at least some non-None visibility_m values from OpenMeteo. "
            "Currently hardcoded to None in openmeteo.py."
        )

    def test_provider_returns_freezing_level(self):
        """
        GIVEN: OpenMeteo provider fetching forecast
        WHEN: parsing response with freezing_level_height data
        THEN: ForecastDataPoint.freezing_level_m is NOT None

        Expected RED: freezing_level_m is hardcoded to None in openmeteo.py line 311.
        """
        from providers.openmeteo import OpenMeteoProvider
        from app.config import Location

        provider = OpenMeteoProvider()
        loc = Location(
            name="Innsbruck",
            latitude=47.26,
            longitude=11.39,
            elevation_m=574,
        )
        ts = provider.fetch_forecast(loc)

        fl_values = [dp.freezing_level_m for dp in ts.data if dp.freezing_level_m is not None]
        assert len(fl_values) > 0, (
            "Expected at least some non-None freezing_level_m values from OpenMeteo. "
            "Currently hardcoded to None in openmeteo.py."
        )


# =============================================================================
# Test 9: UI Shows 19 Metrics (Updated from 15)
# SPEC: docs/specs/modules/openmeteo_additional_metrics.md v1.0
# =============================================================================

class TestUIMetricCount19:
    """Test that dialog shows 19 metrics after additional metrics are added."""

    def test_nineteen_metric_checkboxes(self, running_server):
        """
        GIVEN: Weather config dialog with 19 MetricCatalog metrics
        WHEN: counting checkboxes in dialog
        THEN: exactly 19 checkboxes

        Expected RED: Currently 15 checkboxes (4 new metrics not in catalog yet).
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            page.goto(f"{SERVER_URL}/trips", timeout=10000)
            time.sleep(2)

            page.locator('button:has-text("Wetter-Metriken")').first.click()
            time.sleep(1)

            page.screenshot(path="/tmp/weather_config_19_metrics.png")

            checkboxes = page.locator("div.q-checkbox")
            count = checkboxes.count()
            assert count == 19, (
                f"Expected 19 metric checkboxes (15 base + 4 new), found {count}. "
                "New metrics: Sichtweite, Regenwahrscheinlichkeit, CAPE, Nullgradgrenze"
            )

            browser.close()

    def test_new_metric_labels_present(self, running_server):
        """
        GIVEN: Weather config dialog with 19 MetricCatalog metrics
        WHEN: checking for new metric labels
        THEN: all 4 new German labels are visible

        Expected RED: New metric labels not in catalog yet.
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            page.goto(f"{SERVER_URL}/trips", timeout=10000)
            time.sleep(2)

            page.locator('button:has-text("Wetter-Metriken")').first.click()
            time.sleep(1)

            new_labels = [
                "Sichtweite",
                "Regenwahrscheinlichkeit",
                "Gewitterenergie (CAPE)",
                "Nullgradgrenze",
            ]
            found = []
            missing = []
            for label in new_labels:
                if page.locator(f"text={label}").count() > 0:
                    found.append(label)
                else:
                    missing.append(label)

            assert len(found) == 4, (
                f"Found {len(found)}/4 new metric labels. Missing: {missing}"
            )

            browser.close()
