"""
TDD tests for weather_emoji_dni spec.
SPEC: docs/specs/modules/weather_emoji_dni.md v1.0
"""
import pytest
from services.weather_metrics import (
    get_weather_emoji,
    _dni_emoji,
    _night_emoji,
    _cloud_pct_emoji,
    _WMO_PRECIP_EMOJI,
    _WMO_SEVERITY,
)


class TestGetWeatherEmoji:
    """Test the central get_weather_emoji() function priority chain."""

    def test_wmo_rain_overrides_sunny_dni(self):
        assert get_weather_emoji(is_day=1, dni_wm2=800, wmo_code=61, cloud_pct=0) == "\U0001f327\ufe0f"

    def test_wmo_snow_overrides_everything(self):
        assert get_weather_emoji(is_day=1, dni_wm2=500, wmo_code=71, cloud_pct=10) == "\u2744\ufe0f"

    def test_wmo_thunderstorm(self):
        assert get_weather_emoji(is_day=1, dni_wm2=200, wmo_code=95, cloud_pct=80) == "\u26c8\ufe0f"

    def test_wmo_fog(self):
        assert get_weather_emoji(is_day=1, dni_wm2=50, wmo_code=45, cloud_pct=100) == "\U0001f32b\ufe0f"

    def test_wmo_drizzle_light(self):
        assert get_weather_emoji(is_day=1, dni_wm2=300, wmo_code=51, cloud_pct=60) == "\U0001f326\ufe0f"

    def test_wmo_freezing_rain(self):
        assert get_weather_emoji(is_day=0, dni_wm2=0, wmo_code=66, cloud_pct=100) == "\U0001f328\ufe0f"

    def test_wmo_rain_at_night(self):
        assert get_weather_emoji(is_day=0, dni_wm2=0, wmo_code=63, cloud_pct=100) == "\U0001f327\ufe0f"

    def test_night_clear(self):
        assert get_weather_emoji(is_day=0, dni_wm2=0, wmo_code=0, cloud_pct=10) == "\U0001f319"

    def test_night_partly_cloudy(self):
        assert get_weather_emoji(is_day=0, dni_wm2=0, wmo_code=2, cloud_pct=50) == "\U0001f319\u2601\ufe0f"

    def test_night_overcast(self):
        assert get_weather_emoji(is_day=0, dni_wm2=0, wmo_code=3, cloud_pct=85) == "\u2601\ufe0f"

    def test_day_full_sun_high_dni(self):
        assert get_weather_emoji(is_day=1, dni_wm2=800, wmo_code=0, cloud_pct=100) == "\u2600\ufe0f"

    def test_day_mostly_sunny(self):
        assert get_weather_emoji(is_day=1, dni_wm2=400, wmo_code=2, cloud_pct=70) == "\U0001f324\ufe0f"

    def test_day_partly_sunny(self):
        assert get_weather_emoji(is_day=1, dni_wm2=150, wmo_code=3, cloud_pct=90) == "\u26c5"

    def test_day_barely_sunny(self):
        assert get_weather_emoji(is_day=1, dni_wm2=50, wmo_code=3, cloud_pct=95) == "\U0001f325\ufe0f"

    def test_day_no_sun(self):
        assert get_weather_emoji(is_day=1, dni_wm2=0, wmo_code=3, cloud_pct=100) == "\u2601\ufe0f"

    def test_cirrus_scenario_mallorca(self):
        """THE BUG: 100% high clouds but 811 DNI. Must show sun."""
        assert get_weather_emoji(is_day=1, dni_wm2=811, wmo_code=3, cloud_pct=97) == "\u2600\ufe0f"

    def test_fallback_clear(self):
        assert get_weather_emoji(is_day=1, dni_wm2=None, wmo_code=0, cloud_pct=10) == "\u2600\ufe0f"

    def test_fallback_mostly_clear(self):
        assert get_weather_emoji(is_day=1, dni_wm2=None, wmo_code=1, cloud_pct=30) == "\U0001f324\ufe0f"

    def test_fallback_partly_cloudy(self):
        assert get_weather_emoji(is_day=1, dni_wm2=None, wmo_code=2, cloud_pct=55) == "\u26c5"

    def test_fallback_mostly_cloudy(self):
        assert get_weather_emoji(is_day=1, dni_wm2=None, wmo_code=3, cloud_pct=80) == "\U0001f325\ufe0f"

    def test_fallback_overcast(self):
        assert get_weather_emoji(is_day=1, dni_wm2=None, wmo_code=3, cloud_pct=95) == "\u2601\ufe0f"

    def test_fallback_unknown_is_day(self):
        assert get_weather_emoji(is_day=None, dni_wm2=None, wmo_code=None, cloud_pct=60) == "\u26c5"

    def test_fallback_everything_none(self):
        assert get_weather_emoji(is_day=None, dni_wm2=None, wmo_code=None, cloud_pct=None) == "?"

    def test_wmo_clear_not_in_precip(self):
        assert get_weather_emoji(is_day=1, dni_wm2=700, wmo_code=0, cloud_pct=5) == "\u2600\ufe0f"

    def test_wmo_overcast_not_in_precip(self):
        assert get_weather_emoji(is_day=1, dni_wm2=600, wmo_code=3, cloud_pct=100) == "\u2600\ufe0f"


class TestDniEmoji:
    def test_boundary_600(self):
        assert _dni_emoji(600) == "\u2600\ufe0f"
        assert _dni_emoji(599) == "\U0001f324\ufe0f"

    def test_boundary_300(self):
        assert _dni_emoji(300) == "\U0001f324\ufe0f"
        assert _dni_emoji(299) == "\u26c5"

    def test_boundary_120(self):
        assert _dni_emoji(120) == "\u26c5"
        assert _dni_emoji(119) == "\U0001f325\ufe0f"

    def test_boundary_zero(self):
        assert _dni_emoji(1) == "\U0001f325\ufe0f"
        assert _dni_emoji(0) == "\u2601\ufe0f"


class TestNightEmoji:
    def test_clear_night(self):
        assert _night_emoji(0) == "\U0001f319"
        assert _night_emoji(39) == "\U0001f319"

    def test_cloudy_night(self):
        assert _night_emoji(40) == "\U0001f319\u2601\ufe0f"
        assert _night_emoji(79) == "\U0001f319\u2601\ufe0f"

    def test_overcast_night(self):
        assert _night_emoji(80) == "\u2601\ufe0f"
        assert _night_emoji(100) == "\u2601\ufe0f"

    def test_none_cloud(self):
        assert _night_emoji(None) == "\U0001f319"


class TestCloudPctEmoji:
    def test_clear(self):
        assert _cloud_pct_emoji(0) == "\u2600\ufe0f"
        assert _cloud_pct_emoji(19) == "\u2600\ufe0f"

    def test_mostly_clear(self):
        assert _cloud_pct_emoji(20) == "\U0001f324\ufe0f"
        assert _cloud_pct_emoji(39) == "\U0001f324\ufe0f"

    def test_partly_cloudy(self):
        assert _cloud_pct_emoji(40) == "\u26c5"
        assert _cloud_pct_emoji(69) == "\u26c5"

    def test_mostly_cloudy(self):
        assert _cloud_pct_emoji(70) == "\U0001f325\ufe0f"
        assert _cloud_pct_emoji(89) == "\U0001f325\ufe0f"

    def test_overcast(self):
        assert _cloud_pct_emoji(90) == "\u2601\ufe0f"
        assert _cloud_pct_emoji(100) == "\u2601\ufe0f"

    def test_none(self):
        assert _cloud_pct_emoji(None) == "?"


class TestWmoMappings:
    def test_all_precip_codes_have_emoji(self):
        expected_codes = {45, 48, 51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99}
        assert set(_WMO_PRECIP_EMOJI.keys()) == expected_codes

    def test_severity_ranking_unique(self):
        values = list(_WMO_SEVERITY.values())
        assert len(values) == len(set(values))

    def test_severity_covers_all_precip_codes(self):
        for code in _WMO_PRECIP_EMOJI:
            assert code in _WMO_SEVERITY

    def test_clear_codes_not_in_precip(self):
        for code in [0, 1, 2, 3]:
            assert code not in _WMO_PRECIP_EMOJI
