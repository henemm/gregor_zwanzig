"""
TDD RED: Bug #801 + #803 — Alert-Mail Segment-km & Vortags-Zeile.

Kein Mock: Tests bauen echte SegmentWeatherData/DayComparison-Objekte und
rendern über die echten Renderer.

#801 — Snapshot persistiert distance_from_start_km nicht → Alert-Mail "km 0.0–0.0".
  AC-1: Roundtrip save→load erhält start/end distance_from_start_km.
  AC-2: Alter Snapshot ohne km-Felder lädt fail-soft auf 0.0.
  AC-3: Plain-Renderer zeigt echten km-Bereich, nicht "0.0–0.0".

#803 — Vortags-Zeile: Label + feinere Schwelle.
  AC-4: Zeile beginnt mit "Vergleich zum Vortag:" statt "Vortag:".
  AC-5: temp-Delta +3,5°C (über neuer Schwelle 3, unter alter 5) → "wärmer".
  AC-6: Entkopplung — metric_catalog default_change_threshold bleibt 5.0.

SPEC: docs/specs/modules/bug_801_803_mail_segmente_vortag.md
"""
import json
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _make_seg_with_km(segment_id, start_km, end_km, **summary_kwargs):
    """SegmentWeatherData mit echten Streckenpositionen."""
    from app.models import (
        GPXPoint,
        SegmentWeatherData,
        SegmentWeatherSummary,
        TripSegment,
    )

    segment = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=200.0,
                             distance_from_start_km=start_km),
        end_point=GPXPoint(lat=42.2, lon=9.2, elevation_m=300.0,
                           distance_from_start_km=end_km),
        start_time=datetime(2026, 6, 11, 7, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 6, 11, 11, 0, tzinfo=timezone.utc),
        duration_hours=4.0,
        distance_km=end_km - start_km,
        ascent_m=600.0,
        descent_m=200.0,
    )
    return SegmentWeatherData(
        segment=segment,
        timeseries=None,
        aggregated=SegmentWeatherSummary(**summary_kwargs),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def _comparison(today_kwargs: dict, yday_kwargs: dict):
    """DayComparison aus heute/gestern Aggregat-Werten (ein Segment)."""
    from services.day_comparison import DayComparisonService

    today = [_make_seg_with_km(1, 0.0, 10.0, **today_kwargs)]
    yday = [_make_seg_with_km(1, 0.0, 10.0, **yday_kwargs)]
    return DayComparisonService().compare(today, yday)


# ===========================================================================
# Bug #801 — Snapshot distance_from_start_km
# ===========================================================================

class TestBug801SnapshotDistanceRoundtrip:

    def test_distance_roundtrip(self, tmp_path):
        """
        AC-1: GIVEN Snapshot mit Segmenten, deren distance_from_start_km > 0
        WHEN save_dated → load_dated
        THEN tragen die geladenen Segmente dieselben Start-/End-km (kein 0.0-Fallback).
        """
        from services.weather_snapshot import WeatherSnapshotService

        seg = _make_seg_with_km(1, 12.3, 18.7, temp_min_c=5.0, temp_max_c=15.0)
        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path

        target = date(2026, 6, 11)
        service.save_dated("trip-km", target, [seg])
        loaded = service.load_dated("trip-km", target)

        assert loaded is not None
        lseg = loaded[0].segment
        assert lseg.start_point.distance_from_start_km == pytest.approx(12.3)
        assert lseg.end_point.distance_from_start_km == pytest.approx(18.7)

    def test_old_snapshot_without_distance_loads(self, tmp_path):
        """
        AC-2: GIVEN alter Snapshot ohne km-Felder
        WHEN load
        THEN distance_from_start_km == 0.0, kein Fehler.
        """
        from services.weather_snapshot import WeatherSnapshotService

        old = {
            "trip_id": "old-trip",
            "target_date": "2026-06-11",
            "snapshot_at": "2026-06-11T18:00:00+00:00",
            "provider": "openmeteo",
            "segments": [
                {
                    "segment_id": 1,
                    "start_time": "2026-06-11T07:00:00+00:00",
                    "end_time": "2026-06-11T11:00:00+00:00",
                    "start_lat": 42.1, "start_lon": 9.1, "start_elevation_m": 200.0,
                    "end_lat": 42.2, "end_lon": 9.2, "end_elevation_m": 300.0,
                    "aggregated": {"temp_min_c": 5.0, "temp_max_c": 15.0},
                }
            ],
        }
        (tmp_path / "old-trip.json").write_text(json.dumps(old))

        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path
        loaded = service.load("old-trip")

        assert loaded is not None
        lseg = loaded[0].segment
        assert lseg.start_point.distance_from_start_km == 0.0
        assert lseg.end_point.distance_from_start_km == 0.0

    def test_alert_mail_shows_real_km(self, tmp_path):
        """
        AC-3: GIVEN Snapshot mit echten km geladen
        WHEN Plain-Renderer rendert die Segment-Kopfzeile
        THEN zeigt sie den echten km-Bereich, NICHT "0.0–0.0".
        """
        from app.models import MetricConfig, UnifiedWeatherDisplayConfig
        from output.renderers.email.plain import render_plain
        from services.weather_snapshot import WeatherSnapshotService

        seg = _make_seg_with_km(1, 12.3, 18.7, temp_min_c=5.0, temp_max_c=15.0)
        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path
        target = date(2026, 6, 11)
        service.save_dated("trip-km", target, [seg])
        loaded = service.load_dated("trip-km", target)
        assert loaded is not None

        dc = UnifiedWeatherDisplayConfig(
            trip_id="trip-km",
            metrics=[MetricConfig(metric_id="temperature", enabled=True, aggregations=["max"])],
            show_night_block=False,
            night_interval_hours=2,
            thunder_forecast_days=0,
            updated_at=datetime.now(timezone.utc),
        )
        text = render_plain(
            segments=loaded,
            seg_tables=[[]],
            trip_name="KM-Test", report_type="morning",
            dc=dc, night_rows=[], thunder_forecast=None,
            changes=None, stage_name="Etappe 1",
            stage_stats=None, multi_day_trend=None, compact_summary=None,
            tz=ZoneInfo("Europe/Berlin"), friendly_keys=set(),
        )
        assert "km 12.3" in text, f"Echte km fehlen in Mail:\n{text[:400]!r}"
        assert "km 0.0–0.0" not in text, "Mail zeigt weiterhin km 0.0–0.0"


# ===========================================================================
# Bug #803 — Vortags-Zeile
# ===========================================================================

class TestBug803VortagsLabel:

    def test_mail_label_is_vergleich_zum_vortag(self):
        """
        AC-4: GIVEN DayComparison mit spürbarem Wind-Delta
        WHEN summarize_day_comparison
        THEN beginnt die Zeile mit "Vergleich zum Vortag:" und nicht mit "Vortag:".
        """
        from services.day_comparison import summarize_day_comparison

        comp = _comparison({"wind_max_kmh": 50.0}, {"wind_max_kmh": 20.0})
        line = summarize_day_comparison(comp, selected_metrics=["wind"])

        assert line, "Vortags-Zeile leer trotz spürbarem Delta"
        assert line.startswith("Vergleich zum Vortag:"), (
            f"Falsches Label: {line!r}"
        )
        assert not line.startswith("Vortag:"), f"Altes Label noch da: {line!r}"

    def test_telegram_label_is_unambiguous(self):
        """
        AC-4 (Konsistenz): Telegram-Vortag-Zeile beginnt nicht mehr mit "Vortag:".
        """
        from output.renderers.narrow import _tg_vortag_line

        comp = _comparison({"wind_max_kmh": 50.0}, {"wind_max_kmh": 20.0})
        line = _tg_vortag_line(comp)

        assert line, "Telegram-Vortag-Zeile leer trotz Delta"
        assert not line.startswith("Vortag:"), (
            f"Telegram nutzt weiterhin missverständliches 'Vortag:': {line!r}"
        )
        assert "Vortag" in line, f"Bezug zum Vortag verloren: {line!r}"


class TestBug803FinerThreshold:

    def test_temp_delta_3_5_appears(self):
        """
        AC-5: GIVEN temp_max heute +3,5°C wärmer als gestern (über neuer Schwelle 3,
        unter alter 5)
        WHEN summarize_day_comparison mit 'temperature'
        THEN erscheint "wärmer".
        """
        from services.day_comparison import summarize_day_comparison

        comp = _comparison({"temp_max_c": 18.5}, {"temp_max_c": 15.0})
        line = summarize_day_comparison(comp, selected_metrics=["temperature"])

        assert "wärmer" in line, (
            f"+3,5°C unter Schwelle gefallen — Schwelle nicht feiner: {line!r}"
        )

    def test_temp_delta_2_0_absent(self):
        """
        AC-5 (Kontrolle): +2,0°C bleibt unter der neuen Schwelle 3 → "wärmer" fehlt.
        """
        from services.day_comparison import summarize_day_comparison

        comp = _comparison({"temp_max_c": 17.0}, {"temp_max_c": 15.0})
        line = summarize_day_comparison(comp, selected_metrics=["temperature"])

        assert "wärmer" not in line, (
            f"+2,0°C sollte unter Schwelle bleiben (Rausch-Vermeidung): {line!r}"
        )


class TestBug803Decoupling:

    def test_alert_threshold_unchanged(self):
        """
        AC-6: Die Alert-Empfindlichkeit (metric_catalog default_change_threshold)
        bleibt für 'temperature' bei 5.0 — die feinere Schwelle wirkt NUR auf die
        Vortags-Anzeige, nicht auf Alerts.
        """
        from app.metric_catalog import get_metric

        assert get_metric("temperature").default_change_threshold == 5.0, (
            "Katalog-Schwelle wurde verändert → Alerts feuern häufiger (Kopplung!)"
        )
