"""
TDD Tests: GeoSphere API Parsing Validation.

These tests verify that our GeoSphereProvider correctly parses API responses.
Ground truth: Raw API JSON response → Expected transformed values.

This is the core TDD validation:
- Make raw API call
- Apply expected transformations manually
- Compare with what our parser returns
- Any difference = parsing bug
"""

import math

import pytest

from validation import GeoSphereValidator


class TestSnowgridParsing:
    """TDD: Validate SNOWGRID API parsing."""

    @pytest.fixture
    def validator(self) -> GeoSphereValidator:
        return GeoSphereValidator()

    @pytest.mark.tdd
    def test_snowgrid_depth_conversion(self, validator: GeoSphereValidator) -> None:
        """
        TDD: Snow depth should be correctly converted from meters to cm.

        Raw API returns: snow_depth in meters
        Our parser should return: snow_depth in cm (meters * 100)
        """
        # Test with Innsbruck coordinates
        lat, lon = 47.26, 11.39

        result = validator.validate_snowgrid_parsing(lat, lon)

        # Validation
        assert result["validation"]["depth_matches"], (
            f"SNOWGRID parsing mismatch!\n"
            f"Raw API: {result['raw_api']['snow_depth_m']}m = {result['raw_api']['snow_depth_cm']}cm\n"
            f"Parsed:  {result['parsed']['snow_depth_cm']}cm\n"
            f"Difference: {result['validation']['difference_cm']}cm"
        )

    @pytest.mark.tdd
    def test_snowgrid_multiple_locations(self, validator: GeoSphereValidator) -> None:
        """TDD: Parsing should work correctly for multiple Austrian locations."""
        locations = [
            (47.26, 11.39, "Innsbruck"),
            (47.00, 11.30, "Stubai"),
            (47.07, 12.69, "Grossglockner"),
        ]

        for lat, lon, name in locations:
            result = validator.validate_snowgrid_parsing(lat, lon)

            assert result["validation"]["depth_matches"], (
                f"SNOWGRID parsing failed for {name}!\n"
                f"Raw: {result['raw_api']['snow_depth_cm']}cm, "
                f"Parsed: {result['parsed']['snow_depth_cm']}cm"
            )


class TestNwpParsing:
    """TDD: Validate NWP (AROME) API parsing."""

    @pytest.fixture
    def validator(self) -> GeoSphereValidator:
        return GeoSphereValidator()

    @pytest.mark.tdd
    def test_nwp_temperature_passthrough(self, validator: GeoSphereValidator) -> None:
        """
        TDD: Temperature should be passed through with rounding.

        Raw API: t2m in Celsius
        Parsed: t2m_c rounded to 1 decimal
        """
        lat, lon = 47.26, 11.39

        result = validator.validate_nwp_parsing(lat, lon)

        if "error" in result:
            pytest.skip(result["error"])

        assert result["validation"]["temp_matches"], (
            f"Temperature parsing mismatch!\n"
            f"Raw: {result['raw_api']['t2m']}\n"
            f"Expected: {result['expected_after_transform']['t2m_c']}\n"
            f"Parsed: {result['parsed']['t2m_c']}"
        )

    @pytest.mark.tdd
    def test_nwp_wind_vector_conversion(self, validator: GeoSphereValidator) -> None:
        """
        TDD: Wind should be correctly calculated from U/V components.

        Raw API: u10m, v10m in m/s
        Expected: sqrt(u² + v²) * 3.6 → km/h
        """
        lat, lon = 47.26, 11.39

        result = validator.validate_nwp_parsing(lat, lon)

        if "error" in result:
            pytest.skip(result["error"])

        assert result["validation"]["wind_matches"], (
            f"Wind calculation mismatch!\n"
            f"Raw U: {result['raw_api']['u10m']} m/s\n"
            f"Raw V: {result['raw_api']['v10m']} m/s\n"
            f"Expected: {result['expected_after_transform']['wind10m_kmh']} km/h\n"
            f"Parsed: {result['parsed']['wind10m_kmh']} km/h"
        )

    @pytest.mark.tdd
    def test_nwp_cloud_cover_conversion(self, validator: GeoSphereValidator) -> None:
        """
        TDD: Cloud cover should be converted from 0-1 to 0-100%.

        Raw API: tcc as fraction (0.0 - 1.0)
        Expected: tcc * 100 → percentage (0-100)
        """
        lat, lon = 47.26, 11.39

        result = validator.validate_nwp_parsing(lat, lon)

        if "error" in result:
            pytest.skip(result["error"])

        assert result["validation"]["cloud_matches"], (
            f"Cloud cover conversion mismatch!\n"
            f"Raw: {result['raw_api']['tcc']} (fraction)\n"
            f"Expected: {result['expected_after_transform']['cloud_total_pct']}%\n"
            f"Parsed: {result['parsed']['cloud_total_pct']}%"
        )

    @pytest.mark.tdd
    def test_nwp_pressure_conversion(self, validator: GeoSphereValidator) -> None:
        """
        TDD: Pressure should be converted from Pa to hPa.

        Raw API: sp in Pascal
        Expected: sp / 100 → hPa
        """
        lat, lon = 47.26, 11.39

        result = validator.validate_nwp_parsing(lat, lon)

        if "error" in result:
            pytest.skip(result["error"])

        assert result["validation"]["pressure_matches"], (
            f"Pressure conversion mismatch!\n"
            f"Raw: {result['raw_api']['sp']} Pa\n"
            f"Expected: {result['expected_after_transform']['pressure_msl_hpa']} hPa\n"
            f"Parsed: {result['parsed']['pressure_msl_hpa']} hPa"
        )

    @pytest.mark.tdd
    def test_nwp_all_conversions(self, validator: GeoSphereValidator) -> None:
        """TDD: All NWP conversions should match in a single test."""
        lat, lon = 47.26, 11.39

        result = validator.validate_nwp_parsing(lat, lon)

        if "error" in result:
            pytest.skip(result["error"])

        validations = result["validation"]
        all_match = all(validations.values())

        assert all_match, (
            f"NWP parsing has mismatches!\n"
            f"Temperature: {'✓' if validations['temp_matches'] else '✗'}\n"
            f"Wind: {'✓' if validations['wind_matches'] else '✗'}\n"
            f"Cloud: {'✓' if validations['cloud_matches'] else '✗'}\n"
            f"Pressure: {'✓' if validations['pressure_matches'] else '✗'}\n"
            f"\nRaw API: {result['raw_api']}\n"
            f"Expected: {result['expected_after_transform']}\n"
            f"Parsed: {result['parsed']}"
        )
