"""
Unit tests for src/output/adapters/trip_result.py — TDD RED Phase β4.

SPEC: docs/specs/modules/wintersport_profile_consolidation.md
TESTS-SPEC: docs/specs/tests/wintersport_profile_consolidation_tests.md
EPIC: render-pipeline-consolidation (#96), Phase β4

RED-Zustand (jetzt):
  src/output/adapters/trip_result.py existiert noch NICHT → ModuleNotFoundError.

GREEN-Zustand (nach β4-Implementation):
  _trip_result_to_normalized(result) -> NormalizedForecast (deterministisch, pure)
  _waypoint_to_detail(wf)            -> WaypointDetail
  _summary_to_rows(summary)          -> list[tuple[str, str]]
  _wintersport_default_config()      -> list[MetricSpec]
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone

import pytest

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    NormalizedTimeseries,
    Provider,
)
from app.trip import Stage, TimeWindow, Trip, Waypoint
from services.aggregation import (
    AggregatedSummary,
    AggregatedValue,
    AggregationFunc,
    WaypointForecast,
)
from services.trip_forecast import TripForecastResult

from src.output.tokens.dto import (
    DailyForecast,
    HourlyValue,
    MetricSpec,
    NormalizedForecast,
)


# ---------------------------------------------------------------------------
# Fixtures (analog tests/test_formatters.py::TestWintersportFormatter)
# ---------------------------------------------------------------------------


def _make_simple_result(
    *,
    temp_min: float | None = -15.0,
    temp_max: float | None = -5.0,
    wind_chill: float | None = -28.0,
    wind: float | None = 45.0,
    gust: float | None = 70.0,
    precipitation: float | None = 0.0,
    snow_depth: float | None = 180.0,
    snow_new: float | None = 25.0,
    snowfall_limit: float | None = 1800.0,
    visibility: float | None = 5000.0,
    cloud_cover: float | None = 60.0,
    avalanche_regions: list[str] | None = None,
) -> TripForecastResult:
    """Build a deterministic TripForecastResult mit Stubaier-Skitour-Profil."""
    wp1 = Waypoint(
        id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1700,
        time_window=TimeWindow(start=time(8, 0), end=time(10, 0)),
    )
    wp2 = Waypoint(
        id="G2", name="Gipfel", lat=47.05, lon=11.05, elevation_m=3200,
        time_window=TimeWindow(start=time(11, 0), end=time(13, 0)),
    )

    stage = Stage(
        id="T1", name="Tag 1", date=date(2026, 1, 15), waypoints=[wp1, wp2],
    )
    trip = Trip(
        id="stubai-test",
        name="Stubaier Skitour",
        stages=[stage],
        avalanche_regions=avalanche_regions if avalanche_regions is not None else ["AT-7"],
    )

    fixed_ts = datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)
    meta = ForecastMeta(
        provider=Provider.GEOSPHERE, model="AROME",
        run=fixed_ts, grid_res_km=2.5, interp="bilinear",
    )
    dp1 = ForecastDataPoint(
        ts=fixed_ts, t2m_c=-5.0, wind10m_kmh=15.0, gust_kmh=25.0,
        wind_chill_c=-12.0,
    )
    dp2 = ForecastDataPoint(
        ts=fixed_ts, t2m_c=-15.0, wind10m_kmh=45.0, gust_kmh=70.0,
        wind_chill_c=-28.0,
    )
    wf1 = WaypointForecast(
        waypoint=wp1, timeseries=NormalizedTimeseries(meta=meta, data=[dp1]),
    )
    wf2 = WaypointForecast(
        waypoint=wp2, timeseries=NormalizedTimeseries(meta=meta, data=[dp2]),
    )

    summary = AggregatedSummary(
        temp_min=AggregatedValue(
            value=temp_min,
            source_waypoint="Gipfel" if temp_min is not None else None,
            aggregation=AggregationFunc.MIN,
        ),
        temp_max=AggregatedValue(
            value=temp_max,
            source_waypoint="Start" if temp_max is not None else None,
            aggregation=AggregationFunc.MAX,
        ),
        wind_chill=AggregatedValue(
            value=wind_chill,
            source_waypoint="Gipfel" if wind_chill is not None else None,
            aggregation=AggregationFunc.MIN,
        ),
        wind=AggregatedValue(
            value=wind,
            source_waypoint="Gipfel" if wind is not None else None,
            aggregation=AggregationFunc.MAX,
        ),
        gust=AggregatedValue(
            value=gust,
            source_waypoint="Gipfel" if gust is not None else None,
            aggregation=AggregationFunc.MAX,
        ),
        precipitation=AggregatedValue(
            value=precipitation, aggregation=AggregationFunc.SUM,
        ),
        snow_new=AggregatedValue(
            value=snow_new, aggregation=AggregationFunc.MAX,
        ),
        snow_depth=AggregatedValue(
            value=snow_depth,
            source_waypoint="Gipfel" if snow_depth is not None else None,
            aggregation=AggregationFunc.AT_HIGHEST,
        ),
        visibility=AggregatedValue(
            value=visibility, aggregation=AggregationFunc.MIN,
        ),
        snowfall_limit=AggregatedValue(
            value=snowfall_limit, aggregation=AggregationFunc.MIN,
        ),
        cloud_cover=AggregatedValue(
            value=cloud_cover, aggregation=AggregationFunc.MAX,
        ),
    )

    return TripForecastResult(
        trip=trip, waypoint_forecasts=[wf1, wf2], summary=summary,
    )


def _all_none_summary_result() -> TripForecastResult:
    """Result mit allen AggregatedValue.value=None (Edge-Case Spec §7)."""
    return _make_simple_result(
        temp_min=None, temp_max=None, wind_chill=None, wind=None, gust=None,
        precipitation=None, snow_depth=None, snow_new=None,
        snowfall_limit=None, visibility=None, cloud_cover=None,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_adapter_produces_normalized_forecast():
    """
    GIVEN: TripForecastResult mit befüllter AggregatedSummary.
    WHEN:  _trip_result_to_normalized(result) aufgerufen.
    THEN:  Rückgabe ist NormalizedForecast; days[0] enthält
           temp_min_c, temp_max_c, wind_chill_c, snow_depth_cm,
           snow_new_24h_cm, snowfall_limit_m aus summary befüllt.

    Spec §5.1 Adapter-Verantwortung.
    """
    from src.output.adapters.trip_result import _trip_result_to_normalized

    result = _make_simple_result()
    forecast = _trip_result_to_normalized(result)

    assert isinstance(forecast, NormalizedForecast)
    assert len(forecast.days) >= 1
    day = forecast.days[0]
    assert isinstance(day, DailyForecast)
    assert day.temp_min_c == -15.0
    assert day.temp_max_c == -5.0
    assert day.wind_chill_c == -28.0
    assert day.snow_depth_cm == 180.0
    assert day.snow_new_24h_cm == 25.0
    assert day.snowfall_limit_m == 1800.0


def test_adapter_handles_all_none_summary():
    """
    GIVEN: Summary mit allen AggregatedValue.value=None.
    WHEN:  _trip_result_to_normalized(result) aufgerufen.
    THEN:  Keine Exception; daily.temp_min_c, snow_depth_cm, etc. == None.

    Spec §7 Fehlerbehandlung — All-None → DailyForecast-Defaults.
    """
    from src.output.adapters.trip_result import _trip_result_to_normalized

    result = _all_none_summary_result()
    forecast = _trip_result_to_normalized(result)

    assert isinstance(forecast, NormalizedForecast)
    assert len(forecast.days) >= 1
    day = forecast.days[0]
    assert day.temp_min_c is None
    assert day.temp_max_c is None
    assert day.wind_chill_c is None
    assert day.snow_depth_cm is None
    assert day.snow_new_24h_cm is None
    assert day.snowfall_limit_m is None


def test_adapter_pure_function():
    """
    GIVEN: Zwei Aufrufe mit identischem TripForecastResult.
    WHEN:  _trip_result_to_normalized(result) zweimal aufgerufen.
    THEN:  Beide Ergebnisse sind ==.

    Pure function — Determinismus gemäß Spec §3.3.
    """
    from src.output.adapters.trip_result import _trip_result_to_normalized

    result = _make_simple_result()
    out_a = _trip_result_to_normalized(result)
    out_b = _trip_result_to_normalized(result)
    assert out_a == out_b


def test_adapter_avalanche_level_is_none():
    """
    GIVEN: AggregatedSummary hat kein avalanche_level-Feld (out-of-scope).
    WHEN:  _trip_result_to_normalized(result) aufgerufen.
    THEN:  daily.avalanche_level is None.

    Spec §5.1 Tabellenzeile 'avalanche_level' + §13 Out-of-Scope.
    """
    from src.output.adapters.trip_result import _trip_result_to_normalized

    result = _make_simple_result()
    forecast = _trip_result_to_normalized(result)
    day = forecast.days[0]
    assert day.avalanche_level is None


def test_adapter_hourly_samples_anchor_at_hour_12():
    """
    GIVEN: summary.wind.value=45.
    WHEN:  _trip_result_to_normalized(result) aufgerufen.
    THEN:  daily.wind_hourly == (HourlyValue(12, 45.0),) — Default-Anker.

    Spec §5.1 'als Single-Sample bei Stunde 12 (Default-Stunde, da
    AggregatedSummary keine Stunde kennt)'.
    """
    from src.output.adapters.trip_result import _trip_result_to_normalized

    result = _make_simple_result(wind=45.0)
    forecast = _trip_result_to_normalized(result)
    day = forecast.days[0]

    assert day.wind_hourly == (HourlyValue(12, 45.0),)


def test_waypoint_to_detail_extracts_id_name_elevation_timewindow():
    """
    GIVEN: WaypointForecast mit Waypoint(id='G2', name='Gipfel',
           elevation_m=3200, time_window=...).
    WHEN:  _waypoint_to_detail(wf) aufgerufen.
    THEN:  Rückgabe WaypointDetail mit id, name, elevation_m, time_window
           befüllt.

    Spec §4.2 WaypointDetail-Dataclass.
    """
    from src.output.adapters.trip_result import (
        WaypointDetail,
        _waypoint_to_detail,
    )

    result = _make_simple_result()
    wf = result.waypoint_forecasts[1]  # Gipfel-Waypoint
    detail = _waypoint_to_detail(wf)

    assert isinstance(detail, WaypointDetail)
    assert detail.id == "G2"
    assert detail.name == "Gipfel"
    assert detail.elevation_m == 3200
    # time_window wird als String oder TimeWindow-Repräsentation erwartet —
    # Test prüft nur Vorhandensein eines Wertes ungleich None.
    assert detail.time_window is not None


def test_summary_to_rows_formats_temperature_range():
    """
    GIVEN: summary.temp_min.value=-15 (source=Gipfel),
           summary.temp_max.value=-5 (source=Start).
    WHEN:  _summary_to_rows(summary) aufgerufen.
    THEN:  Output enthält Tupel ('Temperatur', '-15.0 bis -5.0°C (Gipfel)').

    Spec §A4 + §5.3 Schritt 3: Adapter erzeugt formatierte Zeilen
    analog WintersportFormatter._format_summary().
    """
    from src.output.adapters.trip_result import _summary_to_rows

    result = _make_simple_result()
    rows = _summary_to_rows(result.summary)

    assert any(
        label == "Temperatur"
        and "-15.0 bis -5.0°C" in value
        and "Gipfel" in value
        for label, value in rows
    ), f"Erwartete Temperatur-Zeile mit Bereich + Quelle nicht gefunden in {rows!r}"


def test_summary_to_rows_omits_none_fields():
    """
    GIVEN: summary.snow_depth.value = None.
    WHEN:  _summary_to_rows(summary) aufgerufen.
    THEN:  Es gibt keine Zeile mit Label 'Schneehöhe' im Output.

    Spec §A4: Adapter unterdrückt Felder ohne Wert.
    """
    from src.output.adapters.trip_result import _summary_to_rows

    result = _make_simple_result(snow_depth=None)
    rows = _summary_to_rows(result.summary)

    assert all(label != "Schneehöhe" for label, _value in rows), (
        f"'Schneehöhe' darf bei snow_depth=None nicht erscheinen: {rows!r}"
    )


def test_wintersport_default_config_enables_av_wc_sn_sn24_sfl():
    """
    GIVEN: Aufruf von _wintersport_default_config().
    WHEN:  Rückgabewert inspiziert.
    THEN:  Liste enthält MetricSpec für AV, WC, SN, SN24+, SFL — alle
           enabled=True.

    Spec §4.1 Compact-Pfad: 'config = _wintersport_default_config()
    produziert die Standard-MetricSpec-Liste für Wintersport (alle
    Wintersport-Tokens enabled, keine Friendly-Form)'.
    """
    from src.output.adapters.trip_result import _wintersport_default_config

    specs = _wintersport_default_config()
    assert isinstance(specs, list)
    by_sym = {s.symbol: s for s in specs}
    for required in ("AV", "WC", "SN", "SN24+", "SFL"):
        assert required in by_sym, (
            f"Wintersport-Default-Config muss Symbol {required!r} enthalten: "
            f"{sorted(by_sym.keys())!r}"
        )
        assert by_sym[required].enabled is True, (
            f"Wintersport-Default-Config: {required!r} muss enabled=True haben."
        )
        assert isinstance(by_sym[required], MetricSpec)
