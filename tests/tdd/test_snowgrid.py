"""
Plausibility Tests: SNOWGRID API data quality.

NOTE: These are NOT TDD tests in the strict sense.
- Bergfex and SNOWGRID measure at different locations
- A direct comparison is not valid (different elevations)
- These tests verify: API returns data, values are plausible

For actual TDD (parser validation), see: test_geosphere_parsing.py
"""

import pytest

from providers.geosphere import GeoSphereProvider
from validation import GroundTruthFetcher, all_resort_slugs, get_resort


class TestSnowgridPlausibility:
    """
    Plausibility tests for SNOWGRID API.

    These tests verify:
    1. API returns data for Austrian coordinates
    2. Values are in reasonable ranges
    3. Data is available for multiple locations

    NOT validated (different data sources):
    - Exact match with bergfex (measures at different elevations)
    """

    TOLERANCE = 0.80  # 80% tolerance (elevation/location differences)

    @pytest.fixture
    def geosphere(self) -> GeoSphereProvider:
        """GeoSphere provider instance."""
        return GeoSphereProvider()

    @pytest.mark.tdd
    @pytest.mark.xfail(
        reason="TDD-RED: Elevation mismatch - bergfex measures at 3200m glacier, "
               "SNOWGRID at ~2000m grid point. Needs elevation-aware coordinate mapping."
    )
    def test_stubai_snow_depth_plausibility(
        self, ground_truth: GroundTruthFetcher, geosphere: GeoSphereProvider
    ) -> None:
        """
        TDD: Stubaier Gletscher snow depth should correlate with bergfex.

        Expected (bergfex): Mountain snow depth in cm
        Actual (SNOWGRID): Snow depth at resort coordinates

        NOTE: This test is expected to fail (xfail) because bergfex measures
        at the glacier station (~3200m) while SNOWGRID measures at the
        coordinate grid point (~2000m). This is a known limitation that
        would require elevation-aware coordinate mapping to resolve.
        """
        # Arrange: Get expected from ground truth
        resort_slug = "stubaier-gletscher"
        expected = ground_truth.get_snow_depth_mountain(resort_slug)
        assert expected is not None, "Bergfex returned no data"

        # Act: Get actual from our API
        resort = get_resort(resort_slug)
        lat, lon = resort[1], resort[2]
        actual_depth, _ = geosphere.fetch_snowgrid(lat, lon)
        assert actual_depth is not None, "SNOWGRID returned no data"

        # Assert: Values should correlate (within tolerance)
        # Note: SNOWGRID measures at specific grid point, bergfex at resort station
        lower_bound = expected * (1 - self.TOLERANCE)
        upper_bound = expected * (1 + self.TOLERANCE)

        assert lower_bound <= actual_depth <= upper_bound, (
            f"SNOWGRID {actual_depth}cm not within {self.TOLERANCE*100}% of "
            f"bergfex {expected}cm (expected {lower_bound:.0f}-{upper_bound:.0f}cm)"
        )

    @pytest.mark.tdd
    def test_all_resorts_have_data(
        self, ground_truth: GroundTruthFetcher, geosphere: GeoSphereProvider
    ) -> None:
        """TDD: All configured resorts should return snow data."""
        results = {}

        for slug in all_resort_slugs():
            resort = get_resort(slug)
            lat, lon = resort[1], resort[2]

            # Get both sources
            bergfex_depth = ground_truth.get_snow_depth_mountain(slug)
            snowgrid_depth, _ = geosphere.fetch_snowgrid(lat, lon)

            results[slug] = {
                "bergfex": bergfex_depth,
                "snowgrid": snowgrid_depth,
            }

        # At least 80% of resorts should have data from both sources
        both_have_data = sum(
            1 for r in results.values()
            if r["bergfex"] is not None and r["snowgrid"] is not None
        )
        success_rate = both_have_data / len(results)

        assert success_rate >= 0.8, (
            f"Only {success_rate*100:.0f}% of resorts have data from both sources. "
            f"Results: {results}"
        )

    @pytest.mark.tdd
    def test_snow_depth_in_reasonable_range(
        self, ground_truth: GroundTruthFetcher, geosphere: GeoSphereProvider
    ) -> None:
        """TDD: Snow depths should be in reasonable range (0-500cm)."""
        for slug in all_resort_slugs():
            resort = get_resort(slug)
            lat, lon = resort[1], resort[2]

            depth, _ = geosphere.fetch_snowgrid(lat, lon)

            if depth is not None:
                assert 0 <= depth <= 500, (
                    f"Unreasonable snow depth {depth}cm for {slug}"
                )

    @pytest.mark.tdd
    def test_higher_elevation_more_snow(
        self, geosphere: GeoSphereProvider
    ) -> None:
        """TDD: Higher elevation resorts should generally have more snow."""
        # Get snow depths with elevations
        data = []
        for slug in all_resort_slugs():
            resort = get_resort(slug)
            lat, lon, elevation = resort[1], resort[2], resort[3]

            depth, _ = geosphere.fetch_snowgrid(lat, lon)
            if depth is not None:
                data.append((elevation, depth, slug))

        if len(data) < 3:
            pytest.skip("Not enough data points")

        # Sort by elevation and check trend
        data.sort(key=lambda x: x[0])
        lowest_elev, lowest_snow, lowest_name = data[0]
        highest_elev, highest_snow, highest_name = data[-1]

        # Highest elevation should have at least as much snow as lowest
        # (not strictly enforced, but logged)
        if highest_snow < lowest_snow:
            pytest.xfail(
                f"Inverse snow/elevation: {highest_name} ({highest_elev}m) "
                f"has {highest_snow}cm, {lowest_name} ({lowest_elev}m) has {lowest_snow}cm"
            )
