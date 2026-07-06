"""
Issue #805 + #789 — save_trip/_trip_to_dict Roundtrip-Datenverlust.

Regression-Tests: load → save → reload muss alle Felder erhalten.
Kein Mock, echte File-I/O.
"""
import json


from app.loader import _parse_trip, save_trip


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TRIP_FULL = {
    "id": "test-805-roundtrip",
    "name": "Roundtrip-Test Tour",
    "region": "GR20",
    "archived_at": "2025-09-01T12:00:00Z",
    "stages": [
        {
            "id": "T1",
            "name": "Etappe 1",
            "date": "2025-08-01",
            "waypoints": [
                {"id": "W1", "name": "Start", "lat": 42.1, "lon": 9.1, "elevation_m": 800},
                {"id": "W2", "name": "Ziel", "lat": 42.2, "lon": 9.2, "elevation_m": 1200},
            ],
        },
        {
            "id": "T2-pause",
            "name": "Ruhetag",
            "date": "2025-08-02",
            "waypoints": [],  # Pausen-Etappe — Issue #805
        },
    ],
    "aggregation": {"profile": "allgemein"},
    "display_config": {
        "trip_id": "test-805-roundtrip",
        "metrics": [
            {
                "metric_id": "temperature_max",
                "enabled": True,
                "aggregations": ["MAX"],
                "morning_enabled": True,
                "evening_enabled": False,
                "use_friendly_format": True,
                "alert_enabled": False,
                "alert_threshold": None,
                "bucket": "primary",
                "order": 0,
                "horizons": {"today": True, "tomorrow": False, "day_after": False},  # Issue #805
            }
        ],
        "channels": ["email", "telegram"],  # Go-Feld — muss erhalten bleiben
        "show_night_block": True,
        "night_interval_hours": 2,
        "thunder_forecast_days": 2,
        "multi_day_trend_reports": ["evening"],
        "sms_metrics": [],
        "updated_at": "2025-08-01T10:00:00",
    },
    "report_config": {
        "trip_id": "test-805-roundtrip",
        "enabled": True,
        "morning_time": "07:00:00",
        "evening_time": "18:00:00",
        "send_email": True,
        "send_sms": False,
        "send_telegram": False,
        "alert_on_changes": True,
        "change_threshold_temp_c": 5.0,
        "change_threshold_wind_kmh": 20.0,
        "change_threshold_precip_mm": 10.0,
        "wind_exposition_min_elevation_m": None,
        "show_compact_summary": True,
        "show_daylight": True,
        "multi_day_trend_reports": ["evening"],
        "show_stage_stats": True,
        "show_quick_take_tags": True,
        "show_stability": True,
        "show_highlights": True,
        "daily_summary_metrics": ["precipitation", "wind"],
        "show_metrics_summary": False,
        "show_outlook": True,
        "email_format": "full",
        "show_yesterday_comparison": False,  # Issue #789 — False muss erhalten bleiben
        "send_signal": "channel_xyz",  # Legacy-Feld — muss erhalten bleiben (RMW)
        "paused_until": None,
        "skip_next": False,
        "updated_at": "2025-08-01T10:00:00",
    },
    "alert_rules": [],
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBug805PauseStage:
    """Issue #805: Pausen-Etappe (0 Wegpunkte) darf _parse_trip nicht crashen."""

    def test_parse_trip_with_pause_stage_does_not_crash(self):
        trip = _parse_trip(_TRIP_FULL)
        pause_stage = next(s for s in trip.stages if s.id == "T2-pause")
        assert pause_stage.waypoints == []

    def test_pause_stage_properties_return_none(self):
        trip = _parse_trip(_TRIP_FULL)
        pause = next(s for s in trip.stages if s.id == "T2-pause")
        assert pause.first_waypoint is None
        assert pause.last_waypoint is None
        assert pause.highest_waypoint is None
        assert pause.lowest_waypoint is None


class TestBug805RoundtripNoDataLoss:
    """Issue #805/#789: save_trip muss alle Felder verlustfrei roundtrippen."""

    def test_region_preserved_after_roundtrip(self, tmp_path):
        trip = _parse_trip(_TRIP_FULL)
        save_trip(trip, user_id="testuser", data_dir=tmp_path)
        saved = json.loads((tmp_path / "users" / "testuser" / "trips" / "test-805-roundtrip.json").read_text())
        assert saved.get("region") == "GR20"

    def test_archived_at_preserved_after_roundtrip(self, tmp_path):
        trip = _parse_trip(_TRIP_FULL)
        save_trip(trip, user_id="testuser", data_dir=tmp_path)
        saved = json.loads((tmp_path / "users" / "testuser" / "trips" / "test-805-roundtrip.json").read_text())
        assert saved.get("archived_at") == "2025-09-01T12:00:00Z"

    def test_show_yesterday_comparison_false_preserved(self, tmp_path):
        """Issue #789: show_yesterday_comparison=False darf nach Save nicht zu True werden."""
        trip = _parse_trip(_TRIP_FULL)
        assert trip.report_config.show_yesterday_comparison is False
        save_trip(trip, user_id="testuser", data_dir=tmp_path)
        saved = json.loads((tmp_path / "users" / "testuser" / "trips" / "test-805-roundtrip.json").read_text())
        assert saved["report_config"]["show_yesterday_comparison"] is False

    def test_horizons_preserved_after_roundtrip(self, tmp_path):
        """Issue #805: MetricConfig.horizons muss serialisiert werden."""
        trip = _parse_trip(_TRIP_FULL)
        save_trip(trip, user_id="testuser", data_dir=tmp_path)
        saved = json.loads((tmp_path / "users" / "testuser" / "trips" / "test-805-roundtrip.json").read_text())
        metrics = saved["display_config"]["metrics"]
        assert metrics[0]["horizons"] == {"today": True, "tomorrow": False, "day_after": False}

    def test_display_config_channels_preserved_via_rmw(self, tmp_path):
        """Issue #805: display_config.channels (Go-Feld) bleibt durch RMW-Merge erhalten."""
        # Erst die Trip-JSON direkt schreiben (simuliert Go-written file)
        trips_dir = tmp_path / "users" / "testuser" / "trips"
        trips_dir.mkdir(parents=True)
        (trips_dir / "test-805-roundtrip.json").write_text(json.dumps(_TRIP_FULL))

        trip = _parse_trip(_TRIP_FULL)
        save_trip(trip, user_id="testuser", data_dir=tmp_path)
        saved = json.loads((trips_dir / "test-805-roundtrip.json").read_text())
        assert saved["display_config"]["channels"] == ["email", "telegram"]

    def test_legacy_send_signal_preserved_via_rmw(self, tmp_path):
        """Issue #805: report_config.send_signal (Legacy-Feld) bleibt durch RMW-Merge erhalten."""
        trips_dir = tmp_path / "users" / "testuser" / "trips"
        trips_dir.mkdir(parents=True)
        (trips_dir / "test-805-roundtrip.json").write_text(json.dumps(_TRIP_FULL))

        trip = _parse_trip(_TRIP_FULL)
        save_trip(trip, user_id="testuser", data_dir=tmp_path)
        saved = json.loads((trips_dir / "test-805-roundtrip.json").read_text())
        assert saved["report_config"]["send_signal"] == "channel_xyz"

    def test_pause_stage_waypoints_empty_after_roundtrip(self, tmp_path):
        """Pausen-Etappe bleibt nach Roundtrip erhalten (0 Wegpunkte)."""
        trip = _parse_trip(_TRIP_FULL)
        save_trip(trip, user_id="testuser", data_dir=tmp_path)
        saved = json.loads((tmp_path / "users" / "testuser" / "trips" / "test-805-roundtrip.json").read_text())
        pause = next(s for s in saved["stages"] if s["id"] == "T2-pause")
        assert pause["waypoints"] == []
