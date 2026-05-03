"""TDD RED: Loader injects a profile-aware default UnifiedWeatherDisplayConfig
when a Trip JSON has neither `display_config` nor legacy `weather_config`.

Issue #111. Spec: docs/specs/modules/loader_display_config_default.md

Diese Tests MUESSEN aktuell scheitern — der else-Branch in `_parse_trip` ist
noch nicht implementiert. `Trip.display_config` ist daher None, wenn keiner
der beiden Bloecke im JSON steht.
"""
import json
from pathlib import Path

import pytest

from app.loader import load_trip_from_dict
from app.profile import ActivityProfile

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GR221_TRIP_FILE = PROJECT_ROOT / "data" / "users" / "default" / "trips" / "gr221-mallorca.json"


def _minimal_trip(**extra) -> dict:
    """Return a minimal valid trip dict, optionally enriched with extra keys."""
    base = {
        "id": "test-trip",
        "name": "Test Trip",
        "stages": [
            {
                "id": "T1",
                "name": "Day 1",
                "date": "2026-05-15",
                "waypoints": [
                    {
                        "id": "G1",
                        "name": "Start",
                        "lat": 47.0,
                        "lon": 11.0,
                        "elevation_m": 2000,
                    }
                ],
            }
        ],
    }
    base.update(extra)
    return base


class TestLoaderDisplayConfigDefault:
    """Specs: Loader injiziert Default-display_config wenn keiner vorhanden."""

    def test_trip_without_display_config_or_weather_config_gets_default(self):
        """GIVEN Trip ohne display_config + ohne weather_config
        WHEN  load_trip_from_dict
        THEN  trip.display_config ist nicht None und hat Metric-Liste."""
        data = _minimal_trip(aggregation={"profile": "wintersport"})

        trip = load_trip_from_dict(data)

        assert trip.display_config is not None, (
            "Loader sollte Default-display_config injizieren statt None"
        )
        assert len(trip.display_config.metrics) > 0, (
            "Default-display_config sollte MetricConfig-Eintraege enthalten"
        )

    def test_wintersport_profile_uses_wintersport_template(self):
        """Profile 'wintersport' → Default enthaelt typische Wintersport-Metriken."""
        data = _minimal_trip(aggregation={"profile": "wintersport"})

        trip = load_trip_from_dict(data)

        enabled_ids = {m.metric_id for m in trip.display_config.metrics if m.enabled}
        assert "fresh_snow" in enabled_ids, (
            f"Wintersport-Template sollte fresh_snow enthalten. Enabled: {enabled_ids}"
        )
        assert "snow_depth" in enabled_ids, (
            f"Wintersport-Template sollte snow_depth enthalten. Enabled: {enabled_ids}"
        )

    def test_trip_without_aggregation_uses_allgemein_fallback(self):
        """GIVEN Trip ohne aggregation-Block
        THEN  Default nutzt ALLGEMEIN-Template (nicht crashen)."""
        data = _minimal_trip()

        trip = load_trip_from_dict(data)

        assert trip.display_config is not None
        enabled_ids = {m.metric_id for m in trip.display_config.metrics if m.enabled}
        assert "temperature" in enabled_ids, (
            f"ALLGEMEIN-Template sollte temperature enthalten. Enabled: {enabled_ids}"
        )

    def test_trip_with_unknown_profile_falls_back_to_allgemein(self):
        """Unbekanntes Profile → ALLGEMEIN-Fallback (kein Crash)."""
        data = _minimal_trip(aggregation={"profile": "summer_trekking"})

        trip = load_trip_from_dict(data)

        assert trip.display_config is not None
        assert len(trip.display_config.metrics) > 0

    def test_explicit_display_config_is_not_overridden_by_default(self):
        """GIVEN Trip mit eigenem display_config
        THEN  Loader nutzt diesen, NICHT den Default."""
        custom_metrics = [
            {"metric_id": "temperature", "enabled": True, "alert_enabled": True}
        ]
        data = _minimal_trip(
            display_config={
                "trip_id": "test-trip",
                "metrics": custom_metrics,
            }
        )

        trip = load_trip_from_dict(data)

        assert trip.display_config is not None
        assert len(trip.display_config.metrics) == 1, (
            "Eigene Config darf nicht durch Default ueberschrieben werden"
        )
        assert trip.display_config.metrics[0].metric_id == "temperature"
        assert trip.display_config.metrics[0].alert_enabled is True

    def test_legacy_weather_config_still_takes_precedence_over_default(self):
        """GIVEN Trip mit Legacy weather_config
        THEN  Loader migriert das Legacy-Format, nicht den Catalog-Default."""
        data = _minimal_trip(
            weather_config={
                "trip_id": "test-trip",
                "enabled_metrics": ["temp_min_c"],
                "updated_at": "2026-01-01T00:00:00",
            }
        )

        trip = load_trip_from_dict(data)

        assert trip.display_config is not None
        # Legacy-Migration setzt enabled basierend auf der alten Liste —
        # nur 'temperature' ist enabled, nicht das volle wintersport-Template.
        enabled_ids = {m.metric_id for m in trip.display_config.metrics if m.enabled}
        assert enabled_ids == {"temperature"}, (
            f"Legacy-Migration darf nicht durch Default ueberschrieben werden. "
            f"Enabled: {enabled_ids}"
        )


class TestLoaderDisplayConfigDefaultRealFiles:
    """Specs gegen die echten Trip-JSON-Files in data/."""

    def test_gr221_real_file_loads_with_non_none_display_config(self):
        """Issue #111: GR221-Trip MUSS nach Load ein gueltiges display_config haben —
        unabhaengig davon, ob es aus dem File kommt (Backfill) oder vom Loader-Default
        injiziert wird. Beide Pfade muessen das gleiche Ergebnis liefern."""
        if not GR221_TRIP_FILE.exists():
            pytest.skip(f"GR221 trip file fehlt: {GR221_TRIP_FILE}")

        with open(GR221_TRIP_FILE) as f:
            data = json.load(f)

        trip = load_trip_from_dict(data)

        assert trip.display_config is not None, (
            "Loader muss bei gr221-mallorca.json ein gueltiges display_config liefern — "
            "sonst crasht test_alert_enabled in test_e2e_friendly_format_config.py"
        )
        assert len(trip.display_config.metrics) > 0
        # Helper-Pfad aus test_alert_enabled (modify_metric_config) muss funktionieren:
        # data["display_config"]["metrics"] direkt aus der File-JSON darf nicht crashen.
        assert "display_config" in data, (
            "Backfill-Voraussetzung: GR221 JSON braucht display_config-Block direkt im File, "
            "weil test_alert_enabled das File direkt mutiert (am Loader vorbei)."
        )


class TestWeatherChangeDetectionIntegrationWithDefault:
    """Specs: Default-display_config funktioniert im downstream WeatherChangeDetectionService."""

    def test_change_detection_service_consumes_default_display_config(self):
        """from_display_config() darf nicht crashen bei Default-Config."""
        from services.weather_change_detection import WeatherChangeDetectionService

        data = _minimal_trip(aggregation={"profile": "wintersport"})
        trip = load_trip_from_dict(data)

        # Darf nicht crashen — vorher: AttributeError 'NoneType' has no attribute 'metrics'
        svc = WeatherChangeDetectionService.from_display_config(trip.display_config)

        # Default hat alert_enabled=False fuer alle → thresholds-Map ist leer.
        # Das ist erwartet und korrekt: User aktiviert Alerts manuell pro Metric.
        assert svc is not None
