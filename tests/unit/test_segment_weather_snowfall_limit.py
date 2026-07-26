"""Tages-Mittelwert der Schneefallgrenze im ECHTEN Trip-Pfad (#1391, AC-5).

Ergaenzung zu `test_change_detection.py::TestFromDisplayConfigSnowfallLimit`
(die dort konstruiert `SegmentWeatherSummary` direkt und ueberspringt damit
den Berechnungsweg). Am Code nachgewiesen (Team-Lead-Korrektur zum
Kontext-Dokument): `compute_extended_metrics()` -- der ECHTE Trip-Segment-
Pfad, aufgerufen aus `segment_weather.py:280-281` -- berechnet 13 Groessen,
`_compute_snowfall_limit()` ist NICHT darunter. Nur `summarize_points()` (der
Compare-Pfad-Helfer) ruft sie auf. Ohne diesen Nachweis wuerde selbst eine
korrekte Katalog-Korrektur (#1391) den Trip-Tageswert dauerhaft bei `None`
belassen -- der Alarm bliebe stumm, obwohl eine Schwelle existiert.

Kern-Schicht, deterministisch: keine Mocks. `SegmentWeatherService` wird mit
einem echten (Fake-)Provider-Objekt konstruiert -- kein `Mock()`/`patch()`,
sondern eine simple Klasse mit `.name` und `.fetch_forecast()`, die eine
feste Zeitreihe liefert (Vorbild: `CountingFakeProvider` in
`tests/unit/test_alert_data_freshness.py`). Der reale Aufrufweg
(`fetch_segment_weather()` -> `_aggregate_for_segment()` ->
`compute_basis_metrics()` -> `compute_extended_metrics()`) laeuft
unveraendert durch.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    MetricConfig,
    NormalizedTimeseries,
    Provider,
    TripSegment,
    UnifiedWeatherDisplayConfig,
)
from services.segment_weather import SegmentWeatherService
from services.weather_cache import reset_shared_weather_cache_for_tests
from services.weather_change_detection import WeatherChangeDetectionService

SEGMENT_START = datetime(2026, 7, 20, 9, tzinfo=timezone.utc)
SEGMENT_END = datetime(2026, 7, 20, 12, tzinfo=timezone.utc)  # 3 Stunden: 9, 10, 11 Uhr


class _FixedSnowfallProvider:
    """Echter (Fake-)Provider, KEIN Mock: liefert eine feste stuendliche
    Zeitreihe mit `snowfall_limit_m`. `.name` faellt auf einen String
    zurueck, `select_model()` fehlt bewusst -- `_resolve_model_id()`
    (segment_weather.py) faengt das ab (Fallback auf den Provider-Namen)."""

    def __init__(self, snowfall_limits_m: list[float], start: datetime) -> None:
        self._values = snowfall_limits_m
        self._start = start

    @property
    def name(self) -> str:
        return "test-fixture"

    def fetch_forecast(
        self,
        location,
        start=None,
        end=None,
        enrich_ensemble: bool = True,
        enrich_snow: bool = True,
    ) -> NormalizedTimeseries:
        meta = ForecastMeta(
            provider=Provider.OPENMETEO,
            model="test",
            grid_res_km=1.0,
            run=datetime.now(timezone.utc),
            interp="point",
        )
        data = [
            ForecastDataPoint(ts=self._start + timedelta(hours=i), snowfall_limit_m=v)
            for i, v in enumerate(self._values)
        ]
        return NormalizedTimeseries(meta=meta, data=data)


def _segment(segment_id: str) -> TripSegment:
    point = GPXPoint(lat=47.0, lon=11.0, elevation_m=1000)
    return TripSegment(
        segment_id=segment_id,
        start_point=point,
        end_point=point,
        start_time=SEGMENT_START,
        end_time=SEGMENT_END,
        duration_hours=3.0,
        distance_km=5.0,
        ascent_m=300,
        descent_m=0,
    )


def _fetch(values: list[float], segment_id: str) -> "SegmentWeatherData":
    provider = _FixedSnowfallProvider(values, SEGMENT_START)
    service = SegmentWeatherService(provider)
    return service.fetch_segment_weather(
        _segment(segment_id), enrich_ensemble=False, enrich_snow=False,
    )


# ===========================================================================
# AC-5 — der echte Trip-Pfad liefert den Tageswert (heute: None)
# ===========================================================================


def test_trip_segment_snowfall_limit_uses_real_aggregation_pipeline():
    """AC-5 (rot vor Fix): `fetch_segment_weather()` -> `_aggregate_for_segment()`
    -> `compute_basis_metrics()` -> `compute_extended_metrics()` (der ECHTE
    Trip-Pfad) soll fuer die Segment-Stunden 2600/2500/2400 m das Minimum
    2400 m liefern. `compute_extended_metrics()` setzt `snowfall_limit_m`
    heute nicht -- das Feld bleibt `None`.
    """
    reset_shared_weather_cache_for_tests()
    try:
        result = _fetch([2600, 2500, 2400], "seg-1391-ac5")

        assert result.aggregated.snowfall_limit_m == 2400, (
            f"snowfall_limit_m={result.aggregated.snowfall_limit_m} -- erwartet "
            "2400 (Minimum ueber die drei Segment-Stunden). "
            "compute_extended_metrics() (src/services/weather_metrics.py:697) "
            "berechnet 13 Groessen, die Schneefallgrenze ist NICHT darunter -- "
            "nur summarize_points() (Compare-Pfad) tut das (#1391)."
        )
    finally:
        reset_shared_weather_cache_for_tests()


# ===========================================================================
# Kettentest — echte Stundenreihe -> Trip-Pfad -> from_display_config() ->
# detect_changes() erkennt das Absinken
# ===========================================================================


def test_trip_path_end_to_end_drop_is_detected():
    """Kettentest (rot vor Fix, aus zwei Gruenden gleichzeitig): eine reale
    Stundenreihe durchlaeuft den vollstaendigen Trip-Pfad
    (`fetch_segment_weather`) fuer einen "alten" und einen "neuen" Zustand,
    danach `WeatherChangeDetectionService.from_display_config()` und
    `detect_changes()`. Ein Absinken von 2500 m auf 2200 m (-300 m, > 200 m
    Schwelle) MUSS als Change erkannt werden. Faellt heute doppelt: das
    Trip-Aggregat bleibt `None` (AC-5) UND selbst mit Wert baute
    `from_display_config()` mangels `summary_fields` keine Schwelle auf
    (AC-1) -- beide Ursachen zusammen ergeben den stummen Alarm aus
    Nutzersicht.
    """
    reset_shared_weather_cache_for_tests()
    try:
        old_data = _fetch([2600, 2500, 2500], "seg-1391-chain")  # Minimum 2500

        # Cache-Reset zwischen den beiden Faengen -- sonst liefert der
        # Shared-Cache (gleiche Koordinate) den alten Wert zurueck statt neu
        # vom (neuen) Fake-Provider zu holen.
        reset_shared_weather_cache_for_tests()

        new_data = _fetch([2300, 2250, 2200], "seg-1391-chain")  # Minimum 2200

        assert old_data.aggregated.snowfall_limit_m == 2500, (
            "Vorbedingung verletzt: alter Trip-Tageswert ist nicht 2500 -- "
            f"tatsaechlich {old_data.aggregated.snowfall_limit_m}"
        )
        assert new_data.aggregated.snowfall_limit_m == 2200, (
            "Vorbedingung verletzt: neuer Trip-Tageswert ist nicht 2200 -- "
            f"tatsaechlich {new_data.aggregated.snowfall_limit_m}"
        )

        display_config = UnifiedWeatherDisplayConfig(
            trip_id="tdd-1391-chain",
            metrics=[MetricConfig(metric_id="snowfall_limit", enabled=True, alert_threshold=200.0)],
        )
        service = WeatherChangeDetectionService.from_display_config(display_config)
        changes = service.detect_changes(old_data, new_data)

        sl_changes = [c for c in changes if c.metric == "snowfall_limit_m"]
        assert sl_changes, (
            "End-to-End (echte Stundenreihe -> Trip-Pfad -> "
            "from_display_config() -> detect_changes()) erkennt das Absinken "
            f"der Schneefallgrenze um 300 m nicht: changes={changes} (#1391)."
        )
        assert sl_changes[0].direction == "decrease"
    finally:
        reset_shared_weather_cache_for_tests()
