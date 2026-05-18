"""TDD RED — Issue #206: preset_name in display_config persistieren.

Spec: docs/specs/modules/issue_206_weather_config_preset_name.md

Tests MÜSSEN scheitern (RED), weil:
- UnifiedWeatherDisplayConfig kein preset_name-Feld hat
- _parse_display_config() liest preset_name nicht
- _trip_to_dict() serialisiert preset_name nicht
"""
import pytest
import sys
import os

# Sicherstellen, dass src/ im Pfad ist
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


# =============================================================================
# AC-1 + Grundlage: UnifiedWeatherDisplayConfig hat preset_name-Feld
# =============================================================================

class TestModelPresetNameField:
    """preset_name ist Teil des UnifiedWeatherDisplayConfig-Dataclass."""

    def test_unified_display_config_has_preset_name(self):
        """GIVEN UnifiedWeatherDisplayConfig
        WHEN das Objekt ohne preset_name erstellt wird
        THEN hat es das Attribut preset_name mit Default None.
        Spec AC-1 Grundlage — RED: Feld existiert noch nicht."""
        from app.models import UnifiedWeatherDisplayConfig, MetricConfig
        from datetime import datetime, timezone

        cfg = UnifiedWeatherDisplayConfig(
            trip_id="t1",
            metrics=[],
        )
        # Feld muss existieren, Default ist None
        assert hasattr(cfg, 'preset_name'), "UnifiedWeatherDisplayConfig hat kein preset_name-Feld"
        assert cfg.preset_name is None

    def test_unified_display_config_stores_preset_name(self):
        """GIVEN UnifiedWeatherDisplayConfig
        WHEN mit preset_name='wandern' erstellt
        THEN gibt cfg.preset_name == 'wandern' zurück.
        RED: Feld existiert noch nicht."""
        from app.models import UnifiedWeatherDisplayConfig

        cfg = UnifiedWeatherDisplayConfig(
            trip_id="t1",
            metrics=[],
            preset_name="wandern",
        )
        assert cfg.preset_name == "wandern"


# =============================================================================
# AC-2 analog (Deserialisierung): _parse_display_config liest preset_name
# =============================================================================

class TestParseDisplayConfigPresetName:
    """_parse_display_config() überträgt preset_name aus JSON."""

    def test_parse_reads_preset_name(self):
        """GIVEN display_config-JSON mit preset_name='wintersport'
        WHEN _parse_display_config() aufgerufen wird
        THEN ist result.preset_name == 'wintersport'.
        RED: Feld wird nicht gelesen."""
        from app.loader import _parse_display_config

        data = {
            "trip_id": "t1",
            "metrics": [],
            "preset_name": "wintersport",
        }
        result = _parse_display_config(data)
        assert result.preset_name == "wintersport"

    def test_parse_returns_none_when_preset_name_missing(self):
        """GIVEN display_config-JSON ohne preset_name
        WHEN _parse_display_config() aufgerufen wird
        THEN ist result.preset_name is None (kein KeyError, kein AttributeError).
        RED: Feld existiert nicht auf dem Objekt."""
        from app.loader import _parse_display_config

        data = {
            "trip_id": "t1",
            "metrics": [],
        }
        result = _parse_display_config(data)
        assert result.preset_name is None

    def test_parse_handles_null_preset_name(self):
        """GIVEN display_config-JSON mit preset_name=null
        WHEN _parse_display_config() aufgerufen wird
        THEN ist result.preset_name is None.
        RED: Feld existiert nicht."""
        from app.loader import _parse_display_config

        data = {
            "trip_id": "t1",
            "metrics": [],
            "preset_name": None,
        }
        result = _parse_display_config(data)
        assert result.preset_name is None


# =============================================================================
# Serialisierung: _trip_to_dict schreibt preset_name
# =============================================================================

class TestTripToDictPresetName:
    """_trip_to_dict() serialisiert preset_name wenn gesetzt."""

    def _make_trip_with_preset(self, preset_name):
        """Hilfsfunktion: Trip mit display_config und preset_name."""
        from app.models import UnifiedWeatherDisplayConfig
        from app.trip import Trip, Stage, Waypoint
        from datetime import date, time

        waypoint = Waypoint(id="W1", name="Start", lat=47.0, lon=10.0, elevation_m=1000)
        stage = Stage(id="T1", name="Etappe 1", date=date(2026, 8, 1), waypoints=[waypoint])
        dc = UnifiedWeatherDisplayConfig(
            trip_id="t-preset-test",
            metrics=[],
            preset_name=preset_name,
        )
        trip = Trip(
            id="t-preset-test",
            name="Preset Test Trip",
            stages=[stage],
            display_config=dc,
        )
        return trip

    def test_trip_to_dict_serializes_preset_name(self):
        """GIVEN Trip mit display_config.preset_name='wandern'
        WHEN _trip_to_dict() aufgerufen wird
        THEN enthält result['display_config']['preset_name'] == 'wandern'.
        RED: preset_name wird nicht serialisiert."""
        from app.loader import _trip_to_dict

        trip = self._make_trip_with_preset("wandern")
        result = _trip_to_dict(trip)

        assert "display_config" in result
        assert "preset_name" in result["display_config"], (
            "preset_name fehlt in serialisiertem display_config"
        )
        assert result["display_config"]["preset_name"] == "wandern"

    def test_trip_to_dict_omits_preset_name_when_none(self):
        """GIVEN Trip mit display_config.preset_name=None
        WHEN _trip_to_dict() aufgerufen wird
        THEN fehlt 'preset_name' im serialisierten display_config (nicht als null-Wert).
        RED: Feld existiert nicht auf dem Objekt."""
        from app.loader import _trip_to_dict

        trip = self._make_trip_with_preset(None)
        result = _trip_to_dict(trip)

        assert "display_config" in result
        # None-Wert soll NICHT serialisiert werden (sauber, kein null im JSON)
        assert result["display_config"].get("preset_name") is None

    def test_roundtrip_preserves_preset_name(self):
        """GIVEN Trip mit preset_name='skitouren' wird serialisiert und zurückgelesen
        WHEN _trip_to_dict() → _parse_display_config(result['display_config'])
        THEN ist roundtrip.preset_name == 'skitouren'.
        RED: Roundtrip schlägt fehl weil Feld nicht existiert."""
        from app.loader import _trip_to_dict, _parse_display_config

        trip = self._make_trip_with_preset("skitouren")
        serialized = _trip_to_dict(trip)
        parsed_back = _parse_display_config(serialized["display_config"])

        assert parsed_back.preset_name == "skitouren"
