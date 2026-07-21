"""
Segment weather service - fetches weather for GPX trip segments.

Wraps ForecastService to provide weather data for TripSegment objects
from Story 1 (GPX Upload & Segment-Planung).

SPEC: docs/specs/modules/segment_weather.md v1.0
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

import logging

from app.config import Location
from app.debug import DebugBuffer
from app.models import SegmentWeatherData, SegmentWeatherSummary, TripSegment

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.models import NormalizedTimeseries
    from providers.base import WeatherProvider
    from services.weather_cache import WeatherCacheService


class SegmentWeatherService:
    """
    Service for fetching weather forecasts for trip segments.

    Wraps existing provider infrastructure to fetch weather data
    for segment coordinates and time windows.

    Example:
        >>> from providers.base import get_provider
        >>> provider = get_provider("geosphere")
        >>> service = SegmentWeatherService(provider)
        >>> segment = TripSegment(...)  # From Story 1
        >>> weather = service.fetch_segment_weather(segment)
        >>> print(f"Provider: {weather.provider}")
    """

    def __init__(
        self,
        provider: "WeatherProvider",
        cache: Optional["WeatherCacheService"] = None,
        debug: Optional[DebugBuffer] = None,
    ) -> None:
        """
        Initialize with a weather provider.

        Args:
            provider: Weather data provider
            cache: Optional weather cache (default: create new)
            debug: Optional debug buffer for logging
        """
        self._provider = provider
        self._debug = debug if debug is not None else DebugBuffer()

        # Initialize cache (Feature 2.4). Issue #1329: default is now the
        # PROCESS-WIDE shared singleton (10min TTL) instead of a fresh
        # per-instance cache -- every caller used to build its own
        # SegmentWeatherService with cache=None, so nothing was ever
        # actually shared. Explicit injection still overrides it (tests).
        if cache is None:
            from services.weather_cache import get_shared_weather_cache
            cache = get_shared_weather_cache()
        self._cache = cache

    @property
    def provider_name(self) -> str:
        """Name of the underlying weather provider."""
        return self._provider.name

    def fetch_segment_weather(
        self,
        segment: TripSegment,
        enrich_ensemble: bool = True,
        enrich_snow: bool = True,
        priority: str = "user_briefing",
    ) -> SegmentWeatherData:
        """
        Fetch weather forecast for a trip segment.

        Algorithm (updated for Issue #1329, Adversary-Fund F001):
        -1. Resolve model_id (part of the cache bucket)
        0. Check shared cache for a RAW timeseries whose window COVERS this
           segment's window (Feature 2.4 + Issue #1329 Teil 1). The cache
           never stores a derived SegmentWeatherData -- identity and
           aggregate are ALWAYS computed here, from THIS segment, never
           taken from another caller's cached result (F001 fix).
        0b. Check forecast budget gate on cache miss (Issue #1329 Teil 2)
        1. Validate segment time window (start < end)
        2. Extract coordinates from segment.start_point
        3. Create Location object
        4. Call provider.fetch_forecast(location, start, end)
        5. Store raw timeseries in cache (Feature 2.4)
        6. Aggregate metrics over THIS segment's own window (2.2a + 2.2b)
        7. Return SegmentWeatherData

        Args:
            segment: Trip segment with coordinates and time window
            enrich_ensemble: If True (default), let provider enrich with
                ensemble-spread confidence; if False, skip ensemble-API call
                (Bug #288 — alert-checks must not consume daily quota).
            enrich_snow: If True (default), let provider fill-only-enrich
                Alpen-Orte with SNOWGRID-Schnee (Epic #1301 A3); if False,
                skip the SNOWGRID call (alert-checks).
            priority: Verbrauchsbudget-Prioritaet (Issue #1329):
                "user_briefing" (default, NIE gedrosselt), "alert_check"
                (gedrosselt ab 95% Tagesbudget) oder "polling" (ab 80%).
                Rueckwaertskompatibler Default schuetzt alle bestehenden
                Aufrufer, die priority nicht kennen.

        Returns:
            SegmentWeatherData with populated metrics, ALWAYS carrying
            THIS segment's own identity and an aggregate computed ONLY over
            THIS segment's own window (Adversary-Fund F001 fix -- even on a
            cache hit against a wider cached window). Bei Budget-Drosselung
            (Issue #1329): has_error=True, error_message="budget_throttled".

        Raises:
            ProviderRequestError: If the provider request fails
            ValueError: If segment time window is invalid
        """
        from services.forecast_budget import ForecastBudgetGate

        budget_gate = ForecastBudgetGate()

        # Step -1: Modellkennung VOR dem Cache-Zugriff bestimmen (Issue
        # #1329): der Cache-Schluessel muss das Modell einschliessen, sonst
        # koennten zwei Orte mit unterschiedlichem Modell denselben
        # Schluessel treffen und Daten des falschen Modells liefern.
        model_id = self._resolve_model_id(
            segment.start_point.lat, segment.start_point.lon
        )

        # Step 0: Check shared cache for a covering RAW timeseries (Feature
        # 2.4 + Issue #1329 Teil 1). NEVER returns a cached SegmentWeatherData
        # (Adversary-Fund F001) -- aggregation always happens below, for
        # THIS segment.
        cached = self._cache.get(segment, enrich_ensemble, enrich_snow, model_id)
        if cached is not None:
            self._debug.add("weather.cache: HIT (raw timeseries)")
            budget_gate.record_cache_hit()
            return self._aggregate_for_segment(
                segment, cached.timeseries, fetched_at=cached.cached_at
            )

        self._debug.add("weather.cache: MISS - fetching from provider")
        budget_gate.record_cache_miss()

        # Step 0b: Verbrauchsbudget pruefen (Issue #1329 Teil 2) -- NUR bei
        # Cache-Miss, denn ein Cache-Hit verbraucht kein Kontingent.
        if not budget_gate.allow(priority):
            self._debug.add(f"budget.throttled: priority={priority}")
            return SegmentWeatherData(
                segment=segment,
                timeseries=None,
                aggregated=SegmentWeatherSummary(),
                fetched_at=datetime.now(timezone.utc),
                provider=self._provider.name,
                has_error=True,
                error_message="budget_throttled",
            )

        # Step 1: Validate time window
        self._validate_segment(segment)

        # Step 2 & 3: Log segment info and create Location
        self._debug.add(f"segment: {segment.segment_id}")
        self._debug.add(
            f"coords: {segment.start_point.lat:.4f}N, {segment.start_point.lon:.4f}E"
        )
        self._debug.add(
            f"time: {segment.start_time.isoformat()} - {segment.end_time.isoformat()}"
        )
        self._debug.add(f"duration: {segment.duration_hours:.1f}h")

        # Create Location from segment start_point
        location = Location(
            latitude=segment.start_point.lat,
            longitude=segment.start_point.lon,
            name=f"Segment {segment.segment_id}",
            elevation_m=round(segment.start_point.elevation_m)
            if segment.start_point.elevation_m is not None
            else None,
        )

        # Step 4: Fetch weather data (WEATHER-04: catch provider errors)
        from providers.base import ProviderRequestError
        try:
            budget_gate.record_call()  # Issue #1329: tatsaechlicher Upstream-Versuch
            timeseries = self._provider.fetch_forecast(
                location,
                start=segment.start_time,
                end=segment.end_time,
                enrich_ensemble=enrich_ensemble,
                enrich_snow=enrich_snow,
            )
        except ProviderRequestError as e:
            logger.error(f"Provider failed for segment {segment.segment_id}: {e}")
            self._debug.add(f"provider.error: {e}")
            return SegmentWeatherData(
                segment=segment,
                timeseries=None,
                aggregated=SegmentWeatherSummary(),
                fetched_at=datetime.now(timezone.utc),
                provider=self._provider.name,
                has_error=True,
                error_message=str(e),
            )

        # Step 5: Log provider response, store RAW timeseries in cache
        # (Feature 2.4 + Issue #1329 Teil 1, F001 fix: never the derived
        # SegmentWeatherData).
        self._debug.add(f"forecast.points: {len(timeseries.data)}")
        self._debug.add(f"forecast.model: {timeseries.meta.model}")
        fetched_at = datetime.now(timezone.utc)
        self._cache.put(segment, timeseries, enrich_ensemble, enrich_snow, model_id)

        # Step 6+7: Aggregate over THIS segment's own window and wrap
        return self._aggregate_for_segment(segment, timeseries, fetched_at=fetched_at)

    def _aggregate_for_segment(
        self,
        segment: TripSegment,
        timeseries: "NormalizedTimeseries",
        fetched_at: datetime,
    ) -> SegmentWeatherData:
        """Filtert eine (moeglicherweise breitere, gecachte) Zeitreihe auf
        GENAU dieses Segment-Fenster und aggregiert NUR darueber (Issue
        #1329, Adversary-Fund F001-Fix): Identitaet (`segment`) und Aggregat
        entstehen bei JEDEM Aufruf hier, beim aufrufenden Segment -- nie aus
        einem fremden Cache-Kontext (weder Trip- noch Compare-Identitaet
        sickert je in einen anderen Aufrufer)."""
        # OpenMeteo returns full-day (24h) data; aggregation must use only
        # segment hours. Unfiltered timeseries is kept for table display.
        # Issue #1334: Vergleich ueber volle Zeitstempel (geflooret auf die
        # Stunde) statt nur die Stundenzahl -- der fruehere reine
        # Stunden-Wraparound-Vergleich zog faelschlich gleiche Uhrzeiten von
        # JEDEM Tag der Zeitreihe (falsche Min/Max bei Segmenten ueber
        # Mitternacht). `dp.ts` und `segment.start_time`/`.end_time` sind
        # beide UTC-aware und direkt vergleichbar.
        start_floor = segment.start_time.replace(minute=0, second=0, microsecond=0)
        end_floor = segment.end_time.replace(minute=0, second=0, microsecond=0)
        # Bug #806: Randstunde exklusiv am Ende (< end_floor), damit jede Stunde
        # genau einem Segment gehört (Vermeidung von Widersprüchen bei Start-Punkt-Sampling).
        # Bug #856: Wenn Start- und Endstunde identisch sind (Segment < 1h, gleiche UTC-Stunde),
        # würde < end_floor immer False liefern → Fallback auf == start_floor.
        filtered_data = [
            dp for dp in timeseries.data
            if (
                (dp.ts == start_floor)
                if start_floor == end_floor
                else (start_floor <= dp.ts < end_floor)
            )
        ]
        from app.models import NormalizedTimeseries as NTS
        filtered_ts = NTS(meta=timeseries.meta, data=filtered_data)
        self._debug.add(f"filtered.points: {len(filtered_data)} (of {len(timeseries.data)})")

        # Compute basis + extended metrics from FILTERED timeseries
        from services.weather_metrics import WeatherMetricsService

        metrics_service = WeatherMetricsService(debug=self._debug)
        basis_summary = metrics_service.compute_basis_metrics(filtered_ts)
        extended_summary = metrics_service.compute_extended_metrics(filtered_ts, basis_summary)

        return SegmentWeatherData(
            segment=segment,
            timeseries=timeseries,
            aggregated=extended_summary,
            fetched_at=fetched_at,
            provider=self._provider.name,
        )

    def _resolve_model_id(self, lat: float, lon: float) -> str:
        """Modellkennung fuer den Cache-Schluessel (Issue #1329 Teil 1.2).

        Nutzt, falls vorhanden, `select_model()` des BEREITS injizierten
        Providers (`self._provider`) -- KEINE Wegwerf-Instanz. Bislang
        implementiert nur `OpenMeteoProvider.select_model()`
        (`providers/openmeteo.py:411`), eine reine Funktion der Koordinate
        ohne Netzzugriff. Provider ohne diese Methode (z.B. GeoSphereProvider,
        FixtureProvider, Test-Fakes) fallen auf den Provider-Namen zurueck:
        unterscheidet ausreichend zwischen Anbietern, auch wenn er innerhalb
        eines Anbieters keine Modellvarianten kennt (Tech-Lead-Entscheidung
        2026-07-20, ersetzt die urspruengliche Spec-Vorgabe eines direkten
        Modul-Imports von `select_model`, das tatsaechlich eine
        Instanzmethode ist).
        """
        select_model = getattr(self._provider, "select_model", None)
        if callable(select_model):
            model_id, _, _ = select_model(lat, lon)
            return model_id
        return self._provider.name

    def _validate_segment(self, segment: TripSegment) -> None:
        """
        Validate segment data.

        Checks:
        - start_time and end_time are timezone-aware UTC (ERROR if not)
        - start_time < end_time (ERROR if not)
        - coordinates in valid ranges (ERROR if not)
        - elevation in valid ranges (ERROR if not)
        - end_time in future (WARNING if past, but allow)

        Raises:
            ValueError: If segment data is invalid
        """
        # Validate timezone-aware UTC datetimes
        if segment.start_time.tzinfo is None:
            raise ValueError(
                f"start_time must be timezone-aware, got naive datetime: "
                f"{segment.start_time}"
            )
        if segment.start_time.tzinfo != timezone.utc:
            raise ValueError(
                f"start_time must be UTC, got: {segment.start_time.tzinfo}"
            )
        if segment.end_time.tzinfo is None:
            raise ValueError(
                f"end_time must be timezone-aware, got naive datetime: "
                f"{segment.end_time}"
            )
        if segment.end_time.tzinfo != timezone.utc:
            raise ValueError(
                f"end_time must be UTC, got: {segment.end_time.tzinfo}"
            )

        # Validate time window order
        if segment.start_time >= segment.end_time:
            raise ValueError(
                f"Invalid segment time window: "
                f"start ({segment.start_time}) >= end ({segment.end_time})"
            )

        # Validate coordinates (geographic ranges)
        for point_name, point in [
            ("start_point", segment.start_point),
            ("end_point", segment.end_point),
        ]:
            if not (-90.0 <= point.lat <= 90.0):
                raise ValueError(
                    f"Invalid {point_name} latitude: {point.lat} "
                    f"(must be -90.0 to 90.0)"
                )
            if not (-180.0 <= point.lon <= 180.0):
                raise ValueError(
                    f"Invalid {point_name} longitude: {point.lon} "
                    f"(must be -180.0 to 180.0)"
                )

        # Validate elevation (if provided)
        for point_name, point in [
            ("start_point", segment.start_point),
            ("end_point", segment.end_point),
        ]:
            if point.elevation_m is not None:
                if point.elevation_m < -500.0:
                    raise ValueError(
                        f"Invalid {point_name} elevation: {point.elevation_m}m "
                        f"(must be >= -500m, Dead Sea is lowest at -430m)"
                    )
                if point.elevation_m > 9000.0:
                    raise ValueError(
                        f"Invalid {point_name} elevation: {point.elevation_m}m "
                        f"(exceeds Mt. Everest at 8848m)"
                    )

        # Optional: Warn if time window is in the past
        now = datetime.now(timezone.utc)
        if segment.end_time < now:
            self._debug.add(
                f"WARNING: Segment time window is in the past "
                f"(end: {segment.end_time}, now: {now})"
            )
