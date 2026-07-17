"""
Trip-Zusammenfassungssatz (``CompactSummaryFormatter.format_stage_summary``)
-- geteilter Trip-Baustein, unabhaengig vom Ortsvergleich.

SPEC: docs/specs/modules/rework_1300_compare_summary_block_removal.md (AC-4)

Herkunft: ``test_trip_summary_text_unchanged_byte_identical`` stand bis #1300
in ``tests/unit/test_compare_location_summary.py`` (dort AC-11) -- einer
Suite, die primaer den mit #1300 zurueckgebauten Ortsvergleichs-
Zusammenfassungsblock prueft und deren restliche Tests deshalb geloescht
werden (#1300 AC-7). Dieser eine Test prueft aber ausschliesslich den
TRIP-Pfad (``format_stage_summary``, nicht den Compare-Wrapper
``format_location_summary``) -- fachlich gehoert er nicht zur Compare-Mail-
Suite (``test_compare_mail_blocks.py``), sondern in eine eigene,
verhaltensbenannte Heimat fuer den geteilten Trip-Baustein. Die Spec (#1300
Implementation Details, Tabelle "Muessen ueberleben") verlangt genau diese
Uebersiedlung als Regressionsschutz: der Rueckbau der Compare-Platzierung
darf den Formulierer selbst nicht veraendern.

Kern-Schicht, deterministisch: keine Mocks, kein Netz. Alle Wetterdaten sind
echte ``ForecastDataPoint``-Objekte; das Aggregat kommt vom echten
``WeatherMetricsService``.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, MetricConfig,
    NormalizedTimeseries, Provider, SegmentWeatherData, ThunderLevel,
    TripSegment, UnifiedWeatherDisplayConfig,
)
from output.renderers.compact_summary import CompactSummaryFormatter
from services.weather_metrics import WeatherMetricsService


def _dp(hour: int, **overrides) -> ForecastDataPoint:
    rain = 1.0 if 13 <= hour <= 15 else 0.0
    defaults = dict(
        ts=datetime(2026, 7, 8, hour, 0, tzinfo=timezone.utc),
        t2m_c=float(8 + (hour - 9)),
        wind10m_kmh=20.0,
        wind_direction_deg=270,
        gust_kmh=25.0,
        precip_1h_mm=rain,
        cloud_total_pct=50,
        thunder_level=ThunderLevel.MED if hour in (13, 14) else ThunderLevel.NONE,
        pop_pct=70 if 13 <= hour <= 15 else 20,
        humidity_pct=65,
        uv_index=6.0 if hour == 12 else 3.0,
        visibility_m=3000 if 13 <= hour <= 15 else 20000,
        wind_chill_c=float(6 + (hour - 9)),
    )
    defaults.update(overrides)
    return ForecastDataPoint(**defaults)


def _hourly() -> list[ForecastDataPoint]:
    return [_dp(h) for h in range(9, 18)]


def _timeseries(hourly: list[ForecastDataPoint]) -> NormalizedTimeseries:
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(2026, 7, 8, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0, interp="point_grid",
    )
    return NormalizedTimeseries(meta=meta, data=hourly)


def _trip_sentence(
    hourly: list[ForecastDataPoint], stage_name: str, metric_ids: list[str],
) -> str:
    """Erzeugt den Satz ueber den ECHTEN Trip-Pfad (CompactSummaryFormatter)."""
    ts = _timeseries(hourly)
    summary = WeatherMetricsService().compute_basis_metrics(ts)
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=39.75, lon=2.65, elevation_m=100.0),
        end_point=GPXPoint(lat=39.76, lon=2.66, elevation_m=200.0),
        start_time=datetime(2026, 7, 8, hourly[0].ts.hour, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 8, hourly[-1].ts.hour + 1, 0, tzinfo=timezone.utc),
        duration_hours=float(hourly[-1].ts.hour + 1 - hourly[0].ts.hour),
        distance_km=5.0, ascent_m=200.0, descent_m=100.0,
    )
    swd = SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=summary,
        fetched_at=datetime(2026, 7, 8, 4, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )
    dc = UnifiedWeatherDisplayConfig(
        trip_id="ref",
        metrics=[
            MetricConfig(metric_id=m, enabled=True, aggregations=["max"], use_friendly_format=True)
            for m in metric_ids
        ],
    )
    return CompactSummaryFormatter().format_stage_summary([swd], stage_name, dc)


def test_trip_summary_text_unchanged_byte_identical():
    """AC-4: Regressionsschutz -- der Trip-Zusammenfassungstext bleibt
    zeichengleich, unabhaengig vom Rueckbau der Compare-Platzierung (#1300).

    Der Erwartungswert ist eine VORHER (Commit d32bd0a5, vor Beginn dieser
    #1300-Arbeit) aufgezeichnete echte Ausgabe von
    ``CompactSummaryFormatter.format_stage_summary()``, kein ausgedachter
    Wert. Dieser Test ist absichtlich schon jetzt gruen und muss gruen
    bleiben -- #1300 entfernt nur die Platzierung im Ortsvergleich, nicht den
    geteilten Formulierer selbst (Spec §Purpose).
    """
    hourly = _hourly()
    recorded = (
        "Sóller → Tossals Verds: 8–16°C, ⛅, trocken, Regen ab 13:00, "
        "mäßiger Wind 20 km/h, ⚡ möglich 13:00–15:00"
    )
    actual = _trip_sentence(
        hourly,
        "Tag 3: von Sóller nach Tossals Verds",
        ["temperature", "cloud_total", "precipitation", "rain_probability",
         "wind", "gust", "wind_direction", "thunder"],
    )
    assert actual == recorded, (
        "Trip-Zusammenfassung hat sich geaendert (Regression). "
        f"vorher: {recorded!r} / jetzt: {actual!r}"
    )
