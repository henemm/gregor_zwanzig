"""
TDD RED tests for weather-metrics-ux feature.

SPEC: docs/specs/modules/weather_metrics_ux.md v1.1

Tests verify:
1. col_label values updated in MetricCatalog (13 changes) — v1.0
2. _fmt_val() level-based formatting for cloud/cape/visibility — v1.0
3. Config UI shows col_label next to German label (checked via get_col_defs) — v1.0
4. Per-metric friendly format toggle — v1.1
"""
import pytest

from app.metric_catalog import get_metric, get_col_defs


# ============================================================
# Change 1: col_label updates (13 metrics) — v1.0
# ============================================================

class TestColLabelUpdates:
    """Verify all 13 col_label values have been updated."""

    def test_wind_chill_label_feels(self):
        m = get_metric("wind_chill")
        assert m.col_label == "Feels", f"Expected 'Feels', got '{m.col_label}'"

    def test_thunder_label_blitz(self):
        m = get_metric("thunder")
        assert m.col_label == "Thdr", f"Expected 'Thdr', got '{m.col_label}'"

    def test_snowfall_limit_label_snowl(self):
        m = get_metric("snowfall_limit")
        assert m.col_label == "SnowL", f"Expected 'SnowL', got '{m.col_label}'"

    def test_cloud_total_label_cloud(self):
        m = get_metric("cloud_total")
        assert m.col_label == "Cloud", f"Expected 'Cloud', got '{m.col_label}'"

    def test_cloud_low_label_cldlow(self):
        m = get_metric("cloud_low")
        assert m.col_label == "CldLow", f"Expected 'CldLow', got '{m.col_label}'"

    def test_cloud_mid_label_cldmid(self):
        m = get_metric("cloud_mid")
        assert m.col_label == "CldMid", f"Expected 'CldMid', got '{m.col_label}'"

    def test_cloud_high_label_cldhi(self):
        m = get_metric("cloud_high")
        assert m.col_label == "CldHi", f"Expected 'CldHi', got '{m.col_label}'"

    def test_dewpoint_label_cond(self):
        m = get_metric("dewpoint")
        assert m.col_label == "Cond°", f"Expected 'Cond°', got '{m.col_label}'"

    def test_visibility_label_visib(self):
        m = get_metric("visibility")
        assert m.col_label == "Visib", f"Expected 'Visib', got '{m.col_label}'"

    def test_rain_probability_label_rain_pct(self):
        m = get_metric("rain_probability")
        assert m.col_label == "Rain%", f"Expected 'Rain%', got '{m.col_label}'"

    def test_cape_label_thndr_pct(self):
        m = get_metric("cape")
        assert m.col_label == "CAPE", f"Expected 'CAPE', got '{m.col_label}'"

    def test_freezing_level_label_zeroline(self):
        m = get_metric("freezing_level")
        assert m.col_label == "0°Line", f"Expected '0°Line', got '{m.col_label}'"

    def test_snow_depth_label_snowh(self):
        m = get_metric("snow_depth")
        assert m.col_label == "SnowH", f"Expected 'SnowH', got '{m.col_label}'"

    def test_unchanged_labels_still_correct(self):
        """Verify unchanged labels haven't been accidentally modified."""
        assert get_metric("temperature").col_label == "Temp"
        assert get_metric("wind").col_label == "Wind"
        assert get_metric("gust").col_label == "Gust"
        assert get_metric("precipitation").col_label == "Rain"
        assert get_metric("humidity").col_label == "Humid"
        assert get_metric("pressure").col_label == "hPa"

    def test_col_defs_contain_new_labels(self):
        """get_col_defs() should return the new labels."""
        col_defs = get_col_defs()
        labels = {cd[0]: cd[1] for cd in col_defs}
        assert labels["felt"] == "Feels"
        assert labels["thunder"] == "Thdr"
        assert labels["cloud"] == "Cloud"
        assert labels["pop"] == "Rain%"
        assert labels["cape"] == "CAPE"
        assert labels["freeze_lvl"] == "0°Line"


# ============================================================
# Change 2: Level-based formatting in _fmt_val() — v1.0
# ============================================================

class TestCloudEmojiFormatting:
    """Cloud metrics should show emoji based on percentage.

    Issue #1214 Scheibe 4: portiert von TripReportFormatter._fmt_val (tot,
    #778) auf den lebendigen Pfad helpers.fmt_val — identische Emoji-Skala,
    nur friendly_keys statt formatter._friendly_keys als Toggle-Quelle.
    """

    _FRIENDLY = {"cloud", "cloud_low", "cloud_mid", "cloud_high"}

    @pytest.fixture()
    def fmt(self):
        from src.output.renderers.email.helpers import fmt_val
        return fmt_val

    # --- Plain text: emoji only ---

    def test_cloud_clear_plain(self, fmt):
        """0-10% → ☀️"""
        result = fmt("cloud", 5, friendly_keys=self._FRIENDLY, html=False)
        assert "☀️" in result

    def test_cloud_partly_plain(self, fmt):
        """11-30% → 🌤️"""
        result = fmt("cloud", 25, friendly_keys=self._FRIENDLY, html=False)
        assert "🌤️" in result

    def test_cloud_half_plain(self, fmt):
        """31-70% → ⛅"""
        result = fmt("cloud", 50, friendly_keys=self._FRIENDLY, html=False)
        assert "⛅" in result

    def test_cloud_mostly_plain(self, fmt):
        """71-90% → 🌥️"""
        result = fmt("cloud", 85, friendly_keys=self._FRIENDLY, html=False)
        assert "🌥️" in result

    def test_cloud_overcast_plain(self, fmt):
        """91-100% → ☁️"""
        result = fmt("cloud", 95, friendly_keys=self._FRIENDLY, html=False)
        assert "☁️" in result

    # --- HTML: emoji + percentage ---

    def test_cloud_html_shows_emoji_only(self, fmt):
        """HTML should show emoji only (no numeric value)."""
        result = fmt("cloud", 25, friendly_keys=self._FRIENDLY, html=True)
        assert "🌤️" in result
        assert "25" not in result

    # --- Boundary values ---

    def test_cloud_boundary_10_is_clear(self, fmt):
        result = fmt("cloud", 10, friendly_keys=self._FRIENDLY, html=False)
        assert "☀️" in result

    def test_cloud_boundary_11_is_partly(self, fmt):
        result = fmt("cloud", 11, friendly_keys=self._FRIENDLY, html=False)
        assert "🌤️" in result

    def test_cloud_boundary_70_is_half(self, fmt):
        result = fmt("cloud", 70, friendly_keys=self._FRIENDLY, html=False)
        assert "⛅" in result

    def test_cloud_boundary_91_is_overcast(self, fmt):
        result = fmt("cloud", 91, friendly_keys=self._FRIENDLY, html=False)
        assert "☁️" in result

    # --- Cloud sub-types also work ---

    def test_cloud_low_emoji(self, fmt):
        result = fmt("cloud_low", 50, friendly_keys=self._FRIENDLY, html=False)
        assert "⛅" in result

    def test_cloud_mid_emoji(self, fmt):
        result = fmt("cloud_mid", 5, friendly_keys=self._FRIENDLY, html=False)
        assert "☀️" in result

    def test_cloud_high_emoji(self, fmt):
        result = fmt("cloud_high", 95, friendly_keys=self._FRIENDLY, html=False)
        assert "☁️" in result

    def test_cloud_none_returns_dash(self, fmt):
        result = fmt("cloud", None, friendly_keys=self._FRIENDLY, html=False)
        assert result == "–"


# Issue #1214 Scheibe 4: TestCapeEmojiFormatting und TestVisibilityLevelFormatting
# ersatzlos entfernt (#778) — beide testeten ausschliesslich Verhalten, das nur
# die tote _fmt_val-Kopie hatte: CAPE lieferte im friendly-Zweig IMMER (auch
# plain=html=False) einen CSS-Dot statt einer Zahl (widerlegt durch die
# lebendigen #811-Mode-Matrix-Tests test_cape_plain_einfach_is_number_not_emoji
# etc.); Visibility zeigte englische Woerter good/fair/poor/"⚠️ fog", was
# #814 AC-5 explizit verbietet (lebendiger Pfad zeigt immer die km-Zahl, nie
# ein Wort). Kein Aequivalent im lebendigen Pfad zu portieren.


# ============================================================
# v1.1 Change 4: Per-Metric Friendly Format Toggle
# ============================================================

class TestMetricDefinitionHasFriendlyFormat:
    """4a) MetricDefinition should have has_friendly_format flag."""

    def test_cloud_total_has_friendly_format(self):
        m = get_metric("cloud_total")
        assert m.has_friendly_format is True

    def test_cloud_low_has_friendly_format(self):
        m = get_metric("cloud_low")
        assert m.has_friendly_format is True

    def test_cloud_mid_has_friendly_format(self):
        m = get_metric("cloud_mid")
        assert m.has_friendly_format is True

    def test_cloud_high_has_friendly_format(self):
        m = get_metric("cloud_high")
        assert m.has_friendly_format is True

    def test_cape_has_friendly_format(self):
        m = get_metric("cape")
        assert m.has_friendly_format is True

    def test_visibility_has_friendly_format(self):
        # Issue #819: visibility ist numerisch-only → has_friendly_format False
        m = get_metric("visibility")
        assert m.has_friendly_format is False

    def test_temperature_has_no_friendly_format(self):
        m = get_metric("temperature")
        assert m.has_friendly_format is False

    def test_wind_has_no_friendly_format(self):
        m = get_metric("wind")
        assert m.has_friendly_format is False

    def test_precipitation_has_no_friendly_format(self):
        m = get_metric("precipitation")
        assert m.has_friendly_format is False


class TestMetricConfigUseFriendlyFormat:
    """4b) MetricConfig should have use_friendly_format field."""

    def test_default_is_true(self):
        from app.models import MetricConfig
        mc = MetricConfig(metric_id="cloud_total")
        assert mc.use_friendly_format is True

    def test_can_set_false(self):
        from app.models import MetricConfig
        mc = MetricConfig(metric_id="cloud_total", use_friendly_format=False)
        assert mc.use_friendly_format is False


class TestLoaderUseFriendlyFormat:
    """4c) Loader serializes/deserializes use_friendly_format."""

    def test_deserialize_with_field(self):
        """Config with use_friendly_format=False should deserialize correctly."""
        from app.loader import _parse_display_config
        data = {
            "trip_id": "test",
            "metrics": [
                {
                    "metric_id": "cloud_total",
                    "enabled": True,
                    "aggregations": ["avg"],
                    "use_friendly_format": False,
                }
            ],
        }
        dc = _parse_display_config(data)
        mc = dc.metrics[0]
        assert mc.use_friendly_format is False

    def test_deserialize_without_field_defaults_true(self):
        """Old config without use_friendly_format should default to True."""
        from app.loader import _parse_display_config
        data = {
            "trip_id": "test",
            "metrics": [
                {
                    "metric_id": "cloud_total",
                    "enabled": True,
                    "aggregations": ["avg"],
                }
            ],
        }
        dc = _parse_display_config(data)
        mc = dc.metrics[0]
        assert mc.use_friendly_format is True

    def test_serialize_includes_field(self):
        """Serialization should include use_friendly_format."""
        import json
        from datetime import date
        from app.loader import save_trip, get_briefings_dir
        from app.models import MetricConfig, UnifiedWeatherDisplayConfig
        from app.trip import Trip, Stage, Waypoint

        # Create a trip with use_friendly_format=False
        wp = Waypoint(id="G1", name="Test", lat=47.0, lon=11.0, elevation_m=1000)
        stage = Stage(
            id="T1",
            name="Test Stage",
            date=date(2026, 3, 1),
            waypoints=[wp],
        )
        trip = Trip(id="test-friendly-fmt", name="Test Friendly Fmt", stages=[stage])
        trip.display_config = UnifiedWeatherDisplayConfig(
            trip_id="test-friendly-fmt",
            metrics=[
                MetricConfig(
                    metric_id="cloud_total",
                    enabled=True,
                    aggregations=["avg"],
                    use_friendly_format=False,
                )
            ],
        )

        # Save and read raw JSON
        save_trip(trip, user_id="default")
        trip_path = get_briefings_dir("default") / "test-friendly-fmt.json"
        try:
            raw = json.loads(trip_path.read_text())
            mc_data = raw["display_config"]["metrics"][0]
            assert "use_friendly_format" in mc_data
            assert mc_data["use_friendly_format"] is False
        finally:
            # Cleanup
            trip_path.unlink(missing_ok=True)


class TestFmtValFriendlyToggle:
    """4d) fmt_val() respects per-metric friendly format toggle.

    Issue #1214 Scheibe 4: portiert von TripReportFormatter._fmt_val (tot,
    #778) auf helpers.fmt_val. CAPE-Faelle ersatzlos entfernt — die tote
    Kopie lieferte im friendly-Zweig IMMER (auch plain) einen CSS-Dot und im
    Roh-Zweig eine 2-stufige Highlight-Span; beides widerlegt der lebendige
    Pfad (#811-Mode-Matrix: plain=Zahl, Ampel nur ueber indicator_keys+html).
    Visibility "friendly ON" (englisches Wort) ebenso entfernt (#814 AC-5) —
    der lebendige Pfad kennt fuer visibility keinen friendly/raw-Unterschied
    und zeigt immer die km-Zahl ohne Highlight; die verbleibenden Tests
    pruefen genau das (Rundung + kein Highlight, auch bei html=True).
    """

    _FRIENDLY = {"cloud", "cloud_low", "cloud_mid", "cloud_high"}

    @pytest.fixture()
    def fmt(self):
        from src.output.renderers.email.helpers import fmt_val
        return fmt_val

    # --- Cloud: friendly ON → emoji (unchanged from v1.0) ---

    def test_cloud_friendly_on_shows_emoji(self, fmt):
        result = fmt("cloud", 50, friendly_keys=self._FRIENDLY, html=False)
        assert "⛅" in result

    def test_cloud_friendly_on_html_shows_emoji_only(self, fmt):
        result = fmt("cloud", 50, friendly_keys=self._FRIENDLY, html=True)
        assert "⛅" in result
        assert "50" not in result

    # --- Cloud: friendly OFF → raw percentage ---

    def test_cloud_friendly_off_shows_raw(self, fmt):
        result = fmt("cloud", 50, friendly_keys=set(), html=False)
        assert result == "50"

    def test_cloud_friendly_off_html_shows_raw(self, fmt):
        result = fmt("cloud", 50, friendly_keys=set(), html=True)
        assert result == "50"

    def test_cloud_low_friendly_off_shows_raw(self, fmt):
        result = fmt("cloud_low", 75, friendly_keys=set(), html=False)
        assert result == "75"

    # --- Visibility: immer km-Zahl, kein friendly/raw-Unterschied (#814 AC-5) ---

    def test_visibility_high_shows_km(self, fmt):
        """>=10000m → '15' (km, no suffix)"""
        result = fmt("visibility", 15000, html=False)
        assert result == "15"

    def test_visibility_mid_shows_km(self, fmt):
        """>=1000m, <10000m → '5.0' (km, no suffix)"""
        result = fmt("visibility", 5000, html=False)
        assert result == "5.0"

    def test_visibility_low_shows_km_decimal(self, fmt):
        """<1000m → '0.8' (km decimal)"""
        result = fmt("visibility", 800, html=False)
        assert result == "0.8"

    def test_visibility_html_no_highlight_low_value(self, fmt):
        """#814 AC-5: kein Highlight mehr, auch bei kleinen Werten und html=True."""
        result = fmt("visibility", 300, html=True)
        assert result == "0.3"
        assert "background" not in result

    def test_visibility_html_same_as_plain(self, fmt):
        """>=500m: html und plain identisch (keine Markierung)."""
        result = fmt("visibility", 5000, html=True)
        assert result == "5.0"


class TestBuildFriendlyKeys:
    """4d) build_friendly_keys() builds correct set from config.

    Issue #435 / AC-10: konsolidiert in email/helpers.py (Vor-Commit). Die
    frühere TripReportFormatter._build_friendly_keys() wurde gelöscht; der
    Adapter importiert jetzt aus helpers.py.
    """

    def test_builds_keys_for_enabled_metrics(self):
        from src.output.renderers.email.helpers import build_friendly_keys
        from app.models import MetricConfig, UnifiedWeatherDisplayConfig
        dc = UnifiedWeatherDisplayConfig(
            trip_id="test",
            metrics=[
                MetricConfig(metric_id="cloud_total", use_friendly_format=True),
                MetricConfig(metric_id="cape", use_friendly_format=True),
                MetricConfig(metric_id="visibility", use_friendly_format=False),
                MetricConfig(metric_id="temperature", use_friendly_format=True),
            ],
        )
        keys = build_friendly_keys(dc)
        assert "cloud" in keys      # cloud_total → col_key "cloud"
        assert "cape" in keys
        assert "visibility" not in keys  # explicitly disabled
        assert "temp" not in keys    # temperature has no friendly format

    def test_empty_config_returns_empty_set(self):
        from src.output.renderers.email.helpers import build_friendly_keys
        from app.models import UnifiedWeatherDisplayConfig
        dc = UnifiedWeatherDisplayConfig(trip_id="test", metrics=[])
        keys = build_friendly_keys(dc)
        assert keys == set()


class TestFormatEmailStoresFriendlyKeys:
    """4d) format_email() stores _friendly_keys from display_config."""

    def test_format_email_sets_friendly_keys(self):
        from datetime import datetime, timezone
        from output.renderers.trip_report import TripReportFormatter
        from app.models import (
            MetricConfig, UnifiedWeatherDisplayConfig,
            ForecastDataPoint, ForecastMeta, NormalizedTimeseries,
            SegmentWeatherData, SegmentWeatherSummary, TripSegment,
            GPXPoint, Provider, ThunderLevel,
        )

        f = TripReportFormatter()
        dc = UnifiedWeatherDisplayConfig(
            trip_id="test",
            metrics=[
                MetricConfig(metric_id="cloud_total", use_friendly_format=False),
                MetricConfig(metric_id="cape", use_friendly_format=True),
            ],
        )

        dp = ForecastDataPoint(
            ts=datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc),
            t2m_c=15.0, wind10m_kmh=12.0, gust_kmh=30.0,
            precip_1h_mm=0.0, cloud_total_pct=50,
            thunder_level=ThunderLevel.NONE, wind_chill_c=10.0,
        )
        meta = ForecastMeta(
            provider=Provider.OPENMETEO, model="test",
            run=datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc),
            grid_res_km=1.0, interp="point_grid",
        )
        ts = NormalizedTimeseries(meta=meta, data=[dp])
        seg_obj = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000),
            end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1200),
            start_time=datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
            duration_hours=2.0, distance_km=4.0, ascent_m=200, descent_m=0,
        )
        agg = SegmentWeatherSummary(
            temp_min_c=10.0, temp_max_c=18.0, temp_avg_c=14.0,
            wind_max_kmh=20.0, gust_max_kmh=30.0, precip_sum_mm=0.0,
            cloud_avg_pct=50, thunder_level_max=ThunderLevel.NONE,
            wind_chill_min_c=8.0,
        )
        seg = SegmentWeatherData(
            segment=seg_obj, timeseries=ts, aggregated=agg,
            fetched_at=datetime.now(timezone.utc), provider="openmeteo",
        )

        f.format_email(
            segments=[seg],
            trip_name="Test Trip",
            report_type="evening",
            display_config=dc,
        )

        # After format_email, _friendly_keys should be set
        assert hasattr(f, '_friendly_keys')
        assert "cape" in f._friendly_keys       # cape with use_friendly_format=True
        assert "cloud" not in f._friendly_keys   # cloud with use_friendly_format=False
