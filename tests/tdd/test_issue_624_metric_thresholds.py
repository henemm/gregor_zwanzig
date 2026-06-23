"""TDD RED — #624: Konfigurierbare Schwellwerte pro Metrik (SMS/Telegram-Kurzform).

SPEC: docs/specs/modules/issue_624_metric_thresholds.md (AC-1..AC-5).
TEST-MANIFEST: docs/specs/tests/issue_624_metric_thresholds_tests.md.

Beschreibt die NOCH NICHT existierende API:
  - src/app/models.py: MetricConfig.sms_threshold (neues additives Feld, Default None)
  - src/formatters/sms_trip.py: SMS_SYMBOL_BY_METRIC (metric_id -> SMS-Symbol) +
    format_sms(..., thresholds=...) wendet pro-Symbol-Schwellwert an
  - src/app/loader.py: _parse_display_config erhält sms_threshold (kein Datenverlust)

RED-Erwartung:
  AC-1 Mapping/Render: ImportError / TypeError (Symbol-Map + thresholds-Param fehlen)
  AC-2 Default-Baseline: GREEN-Guard (bestehendes Verhalten, muss vor UND nach Fix grün sein)
  AC-3 Loader-Roundtrip: AttributeError (sms_threshold existiert nicht / wird nicht geparst)

AC-4 (kein Feld bei Nicht-Threshold-Metriken) und AC-5 (Persistenz im Editor) sind
FRONTEND-ACs → werden in der E2E-Phase via staging-validator (Playwright) bewiesen,
nicht hier (analog #614 AC-5).

KEINE Mocks — echte SegmentWeatherData, echter SMSTripFormatter.format_sms-Render,
echter Loader-Parse.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


# ---------------------------------------------------------------------------
# Helpers (real domain objects, no mocks)
# ---------------------------------------------------------------------------

def _seg(hour: int, wind: float, tmin=None, tmax=None):
    """Real SegmentWeatherData with one wind aggregate at a given start-hour."""
    from app.models import (
        GPXPoint, SegmentWeatherData, SegmentWeatherSummary, TripSegment,
    )
    now = datetime(2026, 5, 1, hour, 0, tzinfo=timezone.utc)
    segment = TripSegment(
        segment_id=hour,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1500),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=2000),
        start_time=now,
        end_time=datetime(2026, 5, 1, hour + 1, 0, tzinfo=timezone.utc),
        duration_hours=1.0, distance_km=4.0, ascent_m=100, descent_m=0,
    )
    agg = SegmentWeatherSummary(temp_min_c=tmin, temp_max_c=tmax, wind_max_kmh=wind)
    return SegmentWeatherData(
        segment=segment, timeseries=None, aggregated=agg,
        fetched_at=now, provider="openmeteo",
    )


def _segments():
    # Wind steigt: 18 km/h @10, 28 @14, 40 @16 (Tagesmaximum).
    return [_seg(10, 18.0, tmin=5.0, tmax=20.0), _seg(14, 28.0), _seg(16, 40.0)]


# ---------------------------------------------------------------------------
# Model — MetricConfig.sms_threshold existiert, Default None
# ---------------------------------------------------------------------------

def test_metricconfig_sms_threshold_default_none():
    """GIVEN frische MetricConfig WHEN ohne sms_threshold gebaut THEN None (additiv)."""
    from app.models import MetricConfig
    mc = MetricConfig(metric_id="wind", enabled=True, bucket="primary", order=0)
    assert mc.sms_threshold is None


# ---------------------------------------------------------------------------
# AC-1 — metric_id -> SMS-Symbol-Mapping + konfigurierter Schwellwert verschiebt
#        die erste-Überschreitung
# ---------------------------------------------------------------------------

def test_ac1_metric_id_to_sms_symbol_mapping():
    """GIVEN das Mapping WHEN nachgeschlagen THEN gibt es R/PR/W/G für die
    threshold-fähigen Metriken."""
    from src.formatters.sms_trip import SMS_SYMBOL_BY_METRIC
    assert SMS_SYMBOL_BY_METRIC["precipitation"] == "R"
    assert SMS_SYMBOL_BY_METRIC["rain_probability"] == "PR"
    assert SMS_SYMBOL_BY_METRIC["wind"] == "W"
    assert SMS_SYMBOL_BY_METRIC["gust"] == "G"
    assert SMS_SYMBOL_BY_METRIC["thunder"] == "TH:"


def test_ac1_configured_threshold_shifts_first_crossing():
    """GIVEN Wind-Schwellwert 25 km/h WHEN Kurzform gerendert (Wind 18@10, 28@14, 40@16)
    THEN erste-Überschreitung = 14 Uhr (W28@14...), NICHT der Default 10 Uhr (W18@10)."""
    from src.formatters.sms_trip import SMSTripFormatter
    out = SMSTripFormatter().format_sms(
        _segments(), stage_name="T", report_type="evening",
        tz=ZoneInfo("UTC"), max_length=4000, thresholds={"W": 25.0},
    )
    assert "W28@14" in out, f"erwartete erste-Überschreitung 14 Uhr, war: {out!r}"
    assert "W18@10" not in out, f"Default-Schwellwert fälschlich aktiv: {out!r}"


# ---------------------------------------------------------------------------
# AC-2 — ohne Konfiguration bit-identisch zum Default (GREEN-Guard)
# ---------------------------------------------------------------------------

def test_ac2_default_baseline_unchanged():
    """GIVEN keine Schwellwert-Konfiguration WHEN Kurzform gerendert THEN bestehendes
    Default-Verhalten (W18@10(40@16)) — Guard, muss vor UND nach Fix grün sein."""
    from src.formatters.sms_trip import SMSTripFormatter
    out = SMSTripFormatter().format_sms(
        _segments(), stage_name="T", report_type="evening",
        tz=ZoneInfo("UTC"), max_length=4000,
    )
    assert "W18@10(40@16)" in out


# ---------------------------------------------------------------------------
# AC-3 — Loader-Roundtrip erhält sms_threshold + übrige Felder (kein Datenverlust)
# ---------------------------------------------------------------------------

def test_ac3_loader_roundtrip_preserves_sms_threshold():
    """GIVEN display_config dict mit metrics[].sms_threshold=5.0 + anderen Feldern
    WHEN parse THEN sms_threshold bleibt 5.0 UND übrige MetricConfig-Felder erhalten."""
    from app.loader import _parse_display_config
    raw = {
        "trip_id": "rt-624",
        "metrics": [
            {"metric_id": "wind", "enabled": True, "bucket": "primary",
             "order": 0, "sms_threshold": 5.0},
            {"metric_id": "gust", "enabled": True, "bucket": "primary", "order": 1},
        ],
        "updated_at": "2026-06-06T08:00:00",
    }
    dc = _parse_display_config(raw)
    wind = next(m for m in dc.metrics if m.metric_id == "wind")
    gust = next(m for m in dc.metrics if m.metric_id == "gust")
    assert wind.sms_threshold == 5.0
    assert wind.enabled is True and wind.bucket == "primary" and wind.order == 0
    assert gust.sms_threshold is None  # nicht gesetzt -> Default None
