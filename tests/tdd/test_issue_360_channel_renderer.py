"""TDD RED — Issue #360: Kanal-bewusster Renderer für Signal/Telegram.

SPEC: docs/specs/modules/issue_360_signal_channel_renderer.md (AC-1..AC-8).
TEST-MANIFEST: docs/specs/tests/issue_360_signal_channel_renderer_tests.md.

Diese Tests beschreiben die NOCH NICHT existierende API:
  - src/output/renderers/channel_layout.py  (CHANNEL_LIMITS, METRIC_PRIORITY,
    ChannelLayout, render_for_channel, auto_distribute)
  - src/output/renderers/narrow.py          (render_narrow)
  - src/app/models.py: MetricConfig.bucket/.order, TripReport.signal_text/.telegram_text

Alle Tests sind in der RED-Phase rot (ImportError/AttributeError/AssertionError),
weil die Funktionen/Felder noch nicht existieren.

KEINE Mocks — reine Datenstrukturen + echte Aufrufe der (zu bauenden) Funktionen.
Builder-Muster für SegmentWeatherData und das save/load-Roundtrip sind aus
tests/tdd/test_reports_pro_typ.py bzw. tests/integration/test_config_persistence.py
übernommen.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timezone
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_dc(metric_specs):
    """Build UnifiedWeatherDisplayConfig from (id, bucket, order) tuples.

    Each metric is enabled=True. bucket/order are the new #360 fields.
    """
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig

    metrics = []
    for metric_id, bucket, order in metric_specs:
        metrics.append(MetricConfig(
            metric_id=metric_id,
            enabled=True,
            bucket=bucket,
            order=order,
        ))
    return UnifiedWeatherDisplayConfig(
        trip_id="issue-360",
        metrics=metrics,
        updated_at=datetime.now(timezone.utc),
    )


# The 9 highest-priority catalog metrics (per METRIC_PRIORITY in the spec),
# all flagged as "primary" with explicit order — used by AC-2/AC-3/AC-5.
_NINE_PRIMARY = [
    ("temperature", "primary", 0),
    ("wind", "primary", 1),
    ("gust", "primary", 2),
    ("rain_probability", "primary", 3),
    ("precipitation", "primary", 4),
    ("wind_chill", "primary", 5),
    ("cloud_total", "primary", 6),
    ("thunder", "primary", 7),
    ("fresh_snow", "primary", 8),
]


def _make_segment_data():
    """Build minimal real SegmentWeatherData with a few hours of forecast.

    Pattern copied from tests/tdd/test_reports_pro_typ.py — NO mocks.
    Populates many dp-fields so multiple metric columns produce real values.
    """
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, TripSegment,
    )

    now = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)
    points = []
    for h in range(6):
        points.append(ForecastDataPoint(
            ts=datetime(2026, 5, 1, 9 + h, 0, tzinfo=timezone.utc),
            t2m_c=15.0 + h,
            wind10m_kmh=10.0 + h,
            gust_kmh=22.0 + h,
            pop_pct=40,
            precip_1h_mm=0.4,
            wind_chill_c=12.0 + h,
            cloud_total_pct=55,
            freezing_level_m=2800,
            uv_index=5.0,
        ))

    meta = ForecastMeta(
        provider=Provider.OPENMETEO,
        model="icon_d2",
        run=now,
        grid_res_km=2.0,
        interp="nearest",
    )
    ts = NormalizedTimeseries(meta=meta, data=points)
    segment = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1500),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=2000),
        start_time=now,
        end_time=datetime(2026, 5, 1, 15, 0, tzinfo=timezone.utc),
        duration_hours=6.0,
        distance_km=12.0,
        ascent_m=500,
        descent_m=0,
    )
    return SegmentWeatherData(
        segment=segment,
        timeseries=ts,
        aggregated=SegmentWeatherSummary(),
        fetched_at=now,
        provider="openmeteo",
    )


# ===========================================================================
# AC-1: Signal, <=5 primary -> alle in table_columns, demoted_count == 0
# ===========================================================================


def test_ac1_signal_five_primary_all_in_table():
    """GIVEN eine Tour mit 5 aktiven primary-Metriken
    WHEN render_for_channel("signal", dc, "morning") läuft
    THEN liegen alle 5 Metriken in table_columns und demoted_count == 0."""
    from src.output.renderers.channel_layout import render_for_channel

    dc = _build_dc([
        ("temperature", "primary", 0),
        ("wind", "primary", 1),
        ("gust", "primary", 2),
        ("rain_probability", "primary", 3),
        ("precipitation", "primary", 4),
    ])

    layout = render_for_channel("signal", dc, "morning")

    assert layout.table_columns == [
        "temperature", "wind", "gust", "rain_probability", "precipitation",
    ]
    assert layout.detail_metrics == []
    assert layout.demoted_count == 0


# ===========================================================================
# AC-2: Signal, 9 primary -> 5 in table, 4 in detail, demoted_count == 4
# ===========================================================================


@pytest.mark.skip(reason="Signal-Kanal entfernt (Bug #610 Schritt 2/2) — Signal-spezifisches Limit (6 Spalten) nicht mehr relevant")
def test_ac2_signal_nine_primary_caps_at_five():
    """GIVEN eine Tour mit 9 aktiven primary-Metriken
    WHEN render_for_channel("signal", dc, "morning") läuft
    THEN enthält table_columns genau 5 Einträge (Zeit + 5 = 6 Spalten),
         detail_metrics die übrigen 4 und demoted_count == 4.

    OBSOLET: Signal-Kanal wurde in Bug #610 (Schritt 2/2) entfernt.
    """
    pass


# ===========================================================================
# AC-3: Email, gleicher dc -> alle primary in table, demoted_count == 0
# ===========================================================================


def test_ac3_email_no_limit_keeps_all_primary():
    """GIVEN derselbe dc mit 9 primary-Metriken
    WHEN render_for_channel("email", dc, "morning") läuft
    THEN sind alle 9 primary-Metriken in table_columns und demoted_count == 0."""
    from src.output.renderers.channel_layout import render_for_channel

    dc = _build_dc(_NINE_PRIMARY)

    layout = render_for_channel("email", dc, "morning")

    assert layout.table_columns == [m[0] for m in _NINE_PRIMARY]
    assert len(layout.table_columns) == 9
    assert layout.detail_metrics == []
    assert layout.demoted_count == 0


# ===========================================================================
# AC-4: SMS -> table_columns == [], alles flach in detail_metrics
# ===========================================================================


def test_ac4_sms_pushes_everything_to_detail():
    """GIVEN derselbe dc mit 9 primary-Metriken
    WHEN render_for_channel("sms", dc, "morning") läuft
    THEN ist table_columns == [] und alle Werte liegen flach in detail_metrics."""
    from src.output.renderers.channel_layout import render_for_channel

    dc = _build_dc(_NINE_PRIMARY)

    layout = render_for_channel("sms", dc, "morning")

    assert layout.table_columns == []
    assert layout.detail_metrics == [m[0] for m in _NINE_PRIMARY]
    assert len(layout.detail_metrics) == 9


# ===========================================================================
# AC-5: render_narrow("signal", ... 9 primary) -> jede Body-Zeile <=26 Zeichen,
#       Body endet mit ·-getrennter Detail-Zeile
# ===========================================================================


@pytest.mark.skip(reason="Signal-Kanal entfernt (Bug #610 Schritt 2/2) — Signal-26-Zeichen-Constraint nicht mehr relevant")
def test_ac5_render_narrow_signal_line_width_and_detail_trailer():
    """OBSOLET: Signal-Kanal wurde in Bug #610 (Schritt 2/2) entfernt."""
    pass


# ===========================================================================
# AC-6: format_email(...) befüllt report.signal_text, != email_plain
# ===========================================================================


@pytest.mark.skip(reason="Signal-Kanal entfernt (Bug #610 Schritt 2/2) — TripReport.signal_text Feld entfernt")
def test_ac6_format_email_populates_signal_text():
    """OBSOLET: Signal-Kanal und TripReport.signal_text wurden in Bug #610 (Schritt 2/2) entfernt."""
    pass


# ===========================================================================
# AC-7: Legacy-Trip-JSON ohne bucket/order -> load -> save -> load:
#       gültige bucket/order, kein anderes Feld geändert (Roundtrip ohne Diff)
# ===========================================================================


def test_ac7_legacy_roundtrip_assigns_bucket_order_without_diff(tmp_path: Path):
    """GIVEN eine Legacy-Trip-JSON ohne bucket/order auf den Metriken
    WHEN der Trip geladen, neu gespeichert und wieder geladen wird
    THEN haben alle MetricConfig gültige bucket/order (via auto_distribute)
         und kein anderes Feld hat sich geändert (Roundtrip ohne Daten-Diff)."""
    from app.loader import load_trip, _trip_to_dict

    # Legacy-JSON: display_config.metrics OHNE bucket/order.
    legacy = {
        "id": "legacy-360",
        "name": "Legacy Trip",
        "stages": [
            {
                "id": "S1",
                "name": "Stage 1",
                "date": date(2026, 5, 1).isoformat(),
                "waypoints": [
                    {"id": "W1", "name": "Start", "lat": 47.0, "lon": 11.0,
                     "elevation_m": 1000},
                    {"id": "W2", "name": "End", "lat": 47.1, "lon": 11.1,
                     "elevation_m": 1500},
                ],
                "start_time": time(9, 0).isoformat(),
            }
        ],
        "avalanche_regions": [],
        "aggregation": {"profile": "summer-trekking"},
        "display_config": {
            "trip_id": "legacy-360",
            "metrics": [
                {"metric_id": "temperature", "enabled": True,
                 "aggregations": ["min", "max"]},
                {"metric_id": "wind", "enabled": True,
                 "aggregations": ["max"]},
                {"metric_id": "precipitation", "enabled": True,
                 "aggregations": ["sum"]},
                {"metric_id": "humidity", "enabled": False,
                 "aggregations": ["avg"]},
            ],
            "show_night_block": True,
            "night_interval_hours": 2,
            "thunder_forecast_days": 2,
            "multi_day_trend_reports": ["evening"],
            "sms_metrics": [],
            "updated_at": datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc).isoformat(),
        },
        "alert_rules": [],
    }
    legacy_path = tmp_path / "legacy-360.json"
    legacy_path.write_text(json.dumps(legacy, indent=2), encoding="utf-8")

    # Load (migrate) -> save -> load again.
    loaded = load_trip(legacy_path)
    for mc in loaded.display_config.metrics:
        assert mc.bucket in ("primary", "secondary"), (
            f"Migration muss gültiges bucket setzen, war: {mc.bucket!r}"
        )
        assert isinstance(mc.order, int) and mc.order >= 0, (
            f"Migration muss gültigen order >=0 setzen, war: {mc.order!r}"
        )

    saved_path = tmp_path / "legacy-360-saved.json"
    saved_path.write_text(
        json.dumps(_trip_to_dict(loaded), indent=2), encoding="utf-8",
    )
    reloaded = load_trip(saved_path)

    # Roundtrip ohne Daten-Diff: alle bisherigen Felder unverändert.
    orig_by_id = {mc.metric_id: mc for mc in loaded.display_config.metrics}
    for mc in reloaded.display_config.metrics:
        o = orig_by_id[mc.metric_id]
        assert mc.bucket == o.bucket
        assert mc.order == o.order
        assert mc.enabled == o.enabled
        assert mc.aggregations == o.aggregations
        assert mc.use_friendly_format == o.use_friendly_format
        assert mc.alert_enabled == o.alert_enabled
        assert mc.alert_threshold == o.alert_threshold

    assert reloaded.name == loaded.name
    assert len(reloaded.stages) == len(loaded.stages)


# ===========================================================================
# AC-7b (F002): Teil-Migration — eine Metrik trägt bucket/order, andere
#       aktive Metriken NICHT. Letztere dürfen nicht still auf secondary
#       fallen, sondern erben das auto_distribute-Ergebnis.
# ===========================================================================


def test_ac7b_partial_migration_keeps_active_metric_primary(tmp_path: Path):
    """GIVEN eine teil-migrierte Trip-JSON: temperature trägt explizit
         bucket='primary'/order=0, aber wind und precipitation (beide enabled)
         tragen KEIN bucket/order
    WHEN der Trip geladen wird
    THEN sind wind und precipitation NICHT 'secondary' (sondern primary via
         auto_distribute), erscheinen also in der Signal-Tabelle."""
    from app.loader import load_trip
    from src.output.renderers.channel_layout import render_for_channel

    partial = {
        "id": "partial-360",
        "name": "Partial Trip",
        "stages": [
            {
                "id": "S1",
                "name": "Stage 1",
                "date": date(2026, 5, 1).isoformat(),
                "waypoints": [
                    {"id": "W1", "name": "Start", "lat": 47.0, "lon": 11.0,
                     "elevation_m": 1000},
                    {"id": "W2", "name": "End", "lat": 47.1, "lon": 11.1,
                     "elevation_m": 1500},
                ],
                "start_time": time(9, 0).isoformat(),
            }
        ],
        "avalanche_regions": [],
        "aggregation": {"profile": "summer-trekking"},
        "display_config": {
            "trip_id": "partial-360",
            "metrics": [
                # Nur temperature ist explizit migriert.
                {"metric_id": "temperature", "enabled": True,
                 "aggregations": ["min", "max"], "bucket": "primary", "order": 0},
                # wind + precipitation aktiv, aber OHNE bucket/order.
                {"metric_id": "wind", "enabled": True,
                 "aggregations": ["max"]},
                {"metric_id": "precipitation", "enabled": True,
                 "aggregations": ["sum"]},
            ],
            "show_night_block": True,
            "night_interval_hours": 2,
            "thunder_forecast_days": 2,
            "multi_day_trend_reports": ["evening"],
            "sms_metrics": [],
            "updated_at": datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc).isoformat(),
        },
        "alert_rules": [],
    }
    path = tmp_path / "partial-360.json"
    path.write_text(json.dumps(partial, indent=2), encoding="utf-8")

    loaded = load_trip(path)
    by_id = {mc.metric_id: mc for mc in loaded.display_config.metrics}

    # temperature: explizit gesetzt, bleibt primary.
    assert by_id["temperature"].bucket == "primary"
    # F002-Kern: wind + precipitation dürfen NICHT still auf secondary fallen.
    assert by_id["wind"].bucket == "primary", (
        "Nicht-migrierte aktive Metrik 'wind' muss primary erben, nicht secondary"
    )
    assert by_id["precipitation"].bucket == "primary", (
        "Nicht-migrierte aktive Metrik 'precipitation' muss primary erben"
    )

    # Und sie müssen tatsächlich in der Signal-Tabelle landen.
    layout = render_for_channel("signal", loaded.display_config, "morning")
    assert "wind" in layout.table_columns
    assert "precipitation" in layout.table_columns


# ===========================================================================
# AC-8: dc mit gesetzter order -> table_columns folgt genau dieser Reihenfolge
# ===========================================================================


def test_ac8_order_determines_column_sequence():
    """GIVEN eine Tour mit konfigurierter (nicht-aufsteigender) order
    WHEN render_for_channel("email", dc, "morning") rendert
    THEN erscheinen die Spalten in genau der durch order festgelegten
         Reihenfolge."""
    from src.output.renderers.channel_layout import render_for_channel

    # Bewusst durcheinander definiert, order legt die Reihenfolge fest.
    dc = _build_dc([
        ("precipitation", "primary", 2),
        ("temperature", "primary", 0),
        ("wind", "primary", 1),
    ])

    layout = render_for_channel("email", dc, "morning")

    assert layout.table_columns == ["temperature", "wind", "precipitation"]
