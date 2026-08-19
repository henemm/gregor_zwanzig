"""TDD RED — Issue #1475 Scheibe S5a (Epic #1419), AC-4: Tagesaggregation
des Hagel-Kennzeichens (Prioritaet ja > unbekannt > nein).

SPEC: docs/specs/modules/feat_1475_s5a_hagel_wmo_flag.md, Implementation
Details Abschnitt 3 (`hail_priority()`) + Abschnitt 4 (`_compute_hail_flag`,
`compute_basis_metrics`, `aggregate_stage`).

RED-Ursache (heute):
  - `output.metric_format.hail_priority` existiert nicht -> ImportError.
  - `SegmentWeatherSummary` kennt kein Feld `hail_flag` -> TypeError bei
    Konstruktion.
  - `aggregate_stage()`'s generischer Level-2-Mechanismus kennt keine Regel
    "hail_priority" und faellt auf den blinden `else: values[0]`-Zweig
    zurueck -- bei einer Segmentreihenfolge [None, True] liefert das
    faelschlich `None` statt der korrekten Prioritaet `True` (Spec Known
    Limitation 3 / Gegenprobe).

Kern-Schicht, deterministisch, keine Mocks/patch()/MagicMock.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.models import (  # noqa: E402
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from services.weather_metrics import WeatherMetricsService  # noqa: E402


# =============================================================================
# Direkter Unit-Test von `hail_priority()` (Implementation Details Abschnitt 3)
# =============================================================================

class TestHailPriorityFunction:
    """`hail_priority()` erwartet die ROHEN (nicht vorgefilterten) Werte --
    ein blosses `any()`/`max()` waere bei einer Mischung aus True/None/False
    falsch (Spec Known Limitations Punkt 3)."""

    def test_ein_true_zwischen_none_gewinnt(self):
        from output.metric_format import hail_priority

        assert hail_priority([None, True, None]) is True

    def test_nur_none_bleibt_none(self):
        from output.metric_format import hail_priority

        assert hail_priority([None, None]) is None

    def test_leere_liste_ist_none(self):
        from output.metric_format import hail_priority

        assert hail_priority([]) is None

    def test_false_ohne_true_oder_none_bleibt_false(self):
        """Strukturell in S5a unerreichbar (kein Erzeuger liefert `False`),
        aber die Funktion selbst muss die Prioritaetsregel korrekt tragen,
        weil S5b/S5c direkt darauf aufbauen (Spec Known Limitation 1/3)."""
        from output.metric_format import hail_priority

        assert hail_priority([False, False]) is False


# =============================================================================
# AC-4 — Level-1: eine bestaetigte Hagelstunde darf nicht von umgebenden
# "unbekannt"-Stunden verdeckt werden (compute_basis_metrics)
# =============================================================================

def _timeseries_eine_hagelstunde_drei_unbekannt() -> NormalizedTimeseries:
    base = datetime(2026, 8, 4, 8, 0, tzinfo=timezone.utc)
    data = []
    for h in range(4):
        data.append(ForecastDataPoint(
            ts=base + timedelta(hours=h),
            t2m_c=15.0 + h, wind10m_kmh=10.0, gust_kmh=15.0,
            precip_1h_mm=0.0, cloud_total_pct=40, humidity_pct=55,
            thunder_level=ThunderLevel.HIGH if h == 1 else ThunderLevel.NONE,
            hail_flag=True if h == 1 else None,
        ))
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0)
    return NormalizedTimeseries(meta=meta, data=data)


def test_ac4_compute_basis_metrics_traegt_true_trotz_umgebender_unbekannt():
    ts = _timeseries_eine_hagelstunde_drei_unbekannt()
    summary = WeatherMetricsService().compute_basis_metrics(ts, tz=None)

    assert summary.hail_flag is True, (
        f"Eine einzelne bestaetigte Hagelstunde (True) darf nicht von drei "
        f"umgebenden 'unbekannt'-Stunden (None) verdeckt werden -- bekam "
        f"{summary.hail_flag!r}"
    )
    assert summary.aggregation_config.get("hail_flag") == "hail_priority", (
        "SegmentWeatherSummary.aggregation_config muss 'hail_flag': "
        f"'hail_priority' tragen, bekam: {summary.aggregation_config!r}"
    )


# =============================================================================
# AC-4 — Level-2: aggregate_stage() ueber mehrere Segmente hinweg
# =============================================================================

def _segment(hail_flag, start_hour: int) -> SegmentWeatherData:
    seg = TripSegment(
        segment_id=start_hour,
        start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=400.0),
        end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=900.0),
        start_time=datetime(2026, 8, 4, start_hour, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 4, start_hour + 2, 0, tzinfo=timezone.utc),
        duration_hours=2.0, distance_km=5.0, ascent_m=100.0, descent_m=50.0,
    )
    ts = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
        data=[ForecastDataPoint(
            ts=datetime(2026, 8, 4, start_hour, 0, tzinfo=timezone.utc),
            t2m_c=15.0, hail_flag=hail_flag,
        )],
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts,
        aggregated=SegmentWeatherSummary(
            temp_min_c=14.0, temp_max_c=16.0, hail_flag=hail_flag,
            aggregation_config={
                "temp_min_c": "min", "temp_max_c": "max",
                "hail_flag": "hail_priority",
            },
        ),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def test_ac4_aggregate_stage_true_gewinnt_ungeachtet_der_reihenfolge():
    """AC-4 Gegenprobe: erstes Segment `None`, zweites Segment `True` --
    ein blindes `values[0]`-Verhalten (heutiger Fallback-Zweig fuer
    unbekannte agg_rule-Werte in `aggregate_stage()`, Spec Known Limitation
    3) wuerde faelschlich `None` liefern. Die korrekte Prioritaetsregel
    (ja > unbekannt > nein) muss `True` liefern."""
    from services.weather_metrics import aggregate_stage

    segmente = [_segment(None, 8), _segment(True, 10)]
    ergebnis = aggregate_stage(segmente)

    assert ergebnis.hail_flag is True, (
        f"aggregate_stage() muss True liefern, sobald IRGENDEIN Segment "
        f"True traegt -- unabhaengig von der Reihenfolge. Bekam "
        f"{ergebnis.hail_flag!r}"
    )
