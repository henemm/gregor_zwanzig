"""Issue #1329, Scheibe C+: geteilter Forecast-Cache (Teil 1, AC-1..AC-4, AC-9).

SPEC: docs/specs/modules/fix_1329_forecast_cache_budget.md
Ausfuehrung:
    uv run pytest tests/unit/test_forecast_cache_sharing.py -v

Kern-Schicht, netzfrei (autouse `_use_fixture_provider`/`_isolate_data_root`
aus tests/conftest.py). KEINE Mocks/patch/MagicMock — die Fake-Provider
unten implementieren das `WeatherProvider`-Protokoll echt und zaehlen nur
ihre eigenen Aufrufe (kein Mock-Theater, CLAUDE.md-Pflicht).

Adversary-Fund F001 (CRITICAL, behoben): der erste Cache-Entwurf speicherte
das ABGELEITETE `SegmentWeatherData` (inkl. fremder `segment_id` und
fenstergebundenem Aggregat) unter einem Ort/Stunde-Schluessel. Ein
Compare-Aufruf (1h) an derselben Koordinate/Stunde wie ein Trip-Segment (4h)
bekam dadurch STILL die Identitaet und das Aggregat des Trip-Segments zurueck
-- `trip_alert.py`/`deviation_alert_engine.py` matchen `cached` gegen `fresh`
per Identitaet, ein Identitaets-Leck liess dort Alarme UNBEMERKT verschwinden
(kein Fehler, kein Log). Fix: der Cache speichert nur noch die ROHE
Provider-Zeitreihe, Identitaet/Aggregat entstehen IMMER beim Aufrufer
(`SegmentWeatherService._aggregate_for_segment`) -- siehe die
`test_*_f001_*`- und `test_second_caller_*`-Tests unten sowie AC-9 in der
Spec.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripSegment,
)
from services.segment_weather import SegmentWeatherService
from services.weather_cache import (
    get_shared_weather_cache,
    reset_shared_weather_cache_for_tests,
)


class CountingFakeProvider:
    """Zaehlender Fake-Provider (KEIN Mock/patch) — erfuellt das
    `WeatherProvider`-Protokoll (`providers/base.py`) mit echten,
    deterministischen `NormalizedTimeseries`-Objekten und zaehlt dabei jeden
    Aufruf. Test Plan Vorgabe fuer AC-1..AC-4."""

    def __init__(self) -> None:
        self.call_count = 0

    @property
    def name(self) -> str:
        return "openmeteo"

    def fetch_forecast(
        self,
        location,
        start=None,
        end=None,
        enrich_ensemble: bool = True,
        enrich_snow: bool = True,
    ) -> NormalizedTimeseries:
        self.call_count += 1
        meta = ForecastMeta(
            provider=Provider.OPENMETEO,
            model="icon_d2",
            grid_res_km=2.2,
            run=datetime.now(timezone.utc),
            interp="grid_point",
        )
        data = [
            ForecastDataPoint(
                ts=(start or datetime.now(timezone.utc)) + timedelta(hours=i),
                t2m_c=10.0 + i,
            )
            for i in range(3)
        ]
        return NormalizedTimeseries(meta=meta, data=data)


class HourlyCountingFakeProvider:
    """Zaehlender Fake-Provider (KEIN Mock/patch), der -- wie der reale
    OpenMeteo-Provider (Kommentar in `segment_weather.py`: "OpenMeteo
    returns full-day (24h) data") -- IMMER einen vollen UTC-Tag mit 24
    Punkten liefert, unabhaengig vom angefragten Segment-Fenster. Jeder
    Punkt traegt `t2m_c == Stunde des Tages` (deterministisch), damit
    Aggregate ueber unterschiedliche Teilfenster nachweisbar unterschiedlich
    ausfallen -- Grundlage der F001-Identitaets-/Aggregat-Tests."""

    def __init__(self) -> None:
        self.call_count = 0

    @property
    def name(self) -> str:
        return "openmeteo"

    def fetch_forecast(
        self,
        location,
        start=None,
        end=None,
        enrich_ensemble: bool = True,
        enrich_snow: bool = True,
    ) -> NormalizedTimeseries:
        self.call_count += 1
        anchor = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        meta = ForecastMeta(
            provider=Provider.OPENMETEO,
            model="icon_d2",
            grid_res_km=2.2,
            run=datetime.now(timezone.utc),
            interp="grid_point",
        )
        data = [
            ForecastDataPoint(ts=anchor + timedelta(hours=h), t2m_c=float(h))
            for h in range(24)
        ]
        return NormalizedTimeseries(meta=meta, data=data)


class MultiDayHourlyCountingFakeProvider:
    """Wie ``HourlyCountingFakeProvider`` (KEIN Mock/patch), liefert aber
    ZWEI volle UTC-Tage (48h) ab einem festen Tag-1-Anker mit GLOBAL
    fortlaufendem ``t2m_c = float(i)`` (i=0..47) -- Tag 1 Stunde H hat
    einen ANDEREN Wert (i=H) als Tag 2 Stunde H (i=24+H). Grundlage fuer
    Issue #1334 AC-1: der Wraparound-Filter darf NIE Punkte vom falschen
    Tag ziehen -- mit gleichwertigen Werten pro Tag waere das unsichtbar."""

    def __init__(self, day1_anchor: datetime) -> None:
        self.call_count = 0
        self._anchor = day1_anchor

    @property
    def name(self) -> str:
        return "openmeteo"

    def fetch_forecast(
        self,
        location,
        start=None,
        end=None,
        enrich_ensemble: bool = True,
        enrich_snow: bool = True,
    ) -> NormalizedTimeseries:
        self.call_count += 1
        meta = ForecastMeta(
            provider=Provider.OPENMETEO,
            model="icon_d2",
            grid_res_km=2.2,
            run=datetime.now(timezone.utc),
            interp="grid_point",
        )
        data = [
            ForecastDataPoint(ts=self._anchor + timedelta(hours=i), t2m_c=float(i))
            for i in range(48)
        ]
        return NormalizedTimeseries(meta=meta, data=data)


def _safe_test_hour(hour_of_day: int = 10) -> datetime:
    """Ein UTC-Zeitpunkt an einer SICHEREN Tagesstunde (weit weg vom
    Tageswechsel), damit Tests mit mehrstuendigen Fenstern nie ueber
    Mitternacht wraparound-anfaellig werden -- unabhaengig von der
    tatsaechlichen Uhrzeit des Testlaufs."""
    return datetime.now(timezone.utc).replace(
        hour=hour_of_day, minute=0, second=0, microsecond=0
    )


def _segment(
    segment_id,
    lat: float,
    lon: float,
    start: datetime,
    duration_hours: float = 2.0,
) -> TripSegment:
    point = GPXPoint(lat=lat, lon=lon, elevation_m=1200.0)
    end = start + timedelta(hours=duration_hours)
    return TripSegment(
        segment_id=segment_id,
        start_point=point,
        end_point=point,
        start_time=start,
        end_time=end,
        duration_hours=duration_hours,
        distance_km=0.0,
        ascent_m=0,
        descent_m=0,
    )


@pytest.fixture(autouse=True)
def _reset_shared_cache():
    """Isoliert den Prozess-Singleton zwischen Tests (Test-Isolation, wie
    von `reset_shared_weather_cache_for_tests()` in der Spec vorgesehen)."""
    reset_shared_weather_cache_for_tests()
    yield
    reset_shared_weather_cache_for_tests()


def _current_hour(offset_hours: int = 1) -> datetime:
    return datetime.now(timezone.utc).replace(
        minute=0, second=0, microsecond=0
    ) + timedelta(hours=offset_hours)


# ---------------------------------------------------------------------------
# AC-1: Gleiche Koordinate/Stunde, unterschiedliche segment_id -> EIN Call
# ---------------------------------------------------------------------------

def test_same_coordinate_and_hour_different_segment_id_share_one_upstream_call():
    provider = CountingFakeProvider()
    hour = _current_hour()

    seg_trip_a = _segment("trip-a-segment-1", 47.2692, 11.4041, hour)
    seg_trip_b = _segment("trip-b-segment-7", 47.2692, 11.4041, hour)

    # Zwei unabhaengige Service-Instanzen wie in Prod (jeder Aufrufer baut
    # sich seine eigene SegmentWeatherService, siehe trip_alert.py:820 und
    # compare_location_weather_source.py:36) — OHNE explizites cache=.
    service_a = SegmentWeatherService(provider)
    service_b = SegmentWeatherService(provider)

    service_a.fetch_segment_weather(seg_trip_a, enrich_ensemble=False, enrich_snow=False)
    service_b.fetch_segment_weather(seg_trip_b, enrich_ensemble=False, enrich_snow=False)

    assert provider.call_count == 1, (
        "AC-1: zwei Aufrufe fuer dieselbe Koordinate/Stunde mit "
        f"unterschiedlicher segment_id muessen sich EINEN Upstream-Call "
        f"teilen (Cache-Hit beim zweiten Aufruf), tatsaechlich: "
        f"{provider.call_count}"
    )


# ---------------------------------------------------------------------------
# AC-2: Unterschiedliche Koordinate bzw. Stunde -> ZWEI Calls
# ---------------------------------------------------------------------------

def test_different_coordinate_causes_two_upstream_calls():
    provider = CountingFakeProvider()
    hour = _current_hour()

    seg_a = _segment("t1", 47.2692, 11.4041, hour)
    seg_b = _segment("t2", 46.0000, 10.0000, hour)  # anderer Ort

    service = SegmentWeatherService(provider)
    service.fetch_segment_weather(seg_a, enrich_ensemble=False, enrich_snow=False)
    service.fetch_segment_weather(seg_b, enrich_ensemble=False, enrich_snow=False)

    assert provider.call_count == 2, (
        "AC-2: unterschiedliche Koordinaten duerfen NICHT denselben "
        f"Cache-Eintrag treffen, tatsaechlich Calls: {provider.call_count}"
    )


def test_different_hour_causes_two_upstream_calls():
    provider = CountingFakeProvider()
    hour_1 = _current_hour(offset_hours=1)
    hour_2 = _current_hour(offset_hours=3)

    seg_a = _segment("t1", 47.2692, 11.4041, hour_1)
    seg_b = _segment("t2", 47.2692, 11.4041, hour_2)  # gleicher Ort, andere Stunde

    service = SegmentWeatherService(provider)
    service.fetch_segment_weather(seg_a, enrich_ensemble=False, enrich_snow=False)
    service.fetch_segment_weather(seg_b, enrich_ensemble=False, enrich_snow=False)

    assert provider.call_count == 2, (
        "AC-2: unterschiedliche Stunden duerfen NICHT denselben "
        f"Cache-Eintrag treffen, tatsaechlich Calls: {provider.call_count}"
    )


# ---------------------------------------------------------------------------
# AC-3: TTL-Ablauf (10 Min) -> erneuter Call, kein stiller Stale-Serve
# ---------------------------------------------------------------------------

def test_ttl_expiry_triggers_new_upstream_call_no_sleep():
    provider = CountingFakeProvider()
    hour = _current_hour()
    seg = _segment("t1", 47.2692, 11.4041, hour)

    service = SegmentWeatherService(provider)
    service.fetch_segment_weather(seg, enrich_ensemble=False, enrich_snow=False)
    assert provider.call_count == 1

    # Injizierbare Uhr statt sleep (Test Plan): der EINZIGE Cache-Eintrag
    # wird direkt um mehr als den 10-Minuten-TTL (600s) gealtert.
    cache = get_shared_weather_cache()
    assert len(cache._cache) == 1, (
        "Erwartet genau einen Cache-Eintrag nach dem ersten Fetch, "
        f"tatsaechlich: {len(cache._cache)}"
    )
    entry = next(iter(cache._cache.values()))
    entry.cached_at = datetime.now(timezone.utc) - timedelta(seconds=601)

    service.fetch_segment_weather(seg, enrich_ensemble=False, enrich_snow=False)

    assert provider.call_count == 2, (
        "AC-3: ein Cache-Eintrag aelter als der TTL (600s) muss verworfen "
        f"werden -> erneuter Upstream-Call, tatsaechlich Calls: "
        f"{provider.call_count}"
    )


def test_entry_within_ttl_is_served_from_cache():
    provider = CountingFakeProvider()
    hour = _current_hour()
    seg = _segment("t1", 47.2692, 11.4041, hour)

    service = SegmentWeatherService(provider)
    service.fetch_segment_weather(seg, enrich_ensemble=False, enrich_snow=False)

    cache = get_shared_weather_cache()
    entry = next(iter(cache._cache.values()))
    entry.cached_at = datetime.now(timezone.utc) - timedelta(seconds=300)  # < 600s

    service.fetch_segment_weather(seg, enrich_ensemble=False, enrich_snow=False)

    assert provider.call_count == 1, (
        "Ein < 10 Min alter Cache-Eintrag darf KEINEN erneuten Upstream-Call "
        f"ausloesen, tatsaechlich Calls: {provider.call_count}"
    )


# ---------------------------------------------------------------------------
# AC-4: Zwei verschiedene Trips (bzw. Trip + Compare-Preset) am selben Ort
#       im selben Zyklus -> EIN Upstream-Call
# ---------------------------------------------------------------------------

def test_trip_and_compare_preset_at_same_location_share_one_upstream_call():
    """Simuliert die realen Aufrufmuster: `trip_alert.py:820`
    (`SegmentWeatherService(provider)` je Alarm-Check) und
    `compare_location_weather_source.py:36` (`SegmentWeatherService(provider)`
    je Compare-Fetch) — beide OHNE explizites `cache=`, wie in Prod."""
    provider = CountingFakeProvider()
    hour = _current_hour(offset_hours=2)

    # trip_alert.py-Aufrufmuster
    trip_segment = _segment("trip-42-segment-3", 45.5000, 9.2000, hour)
    trip_service = SegmentWeatherService(provider)
    trip_result = trip_service.fetch_segment_weather(
        trip_segment, enrich_ensemble=False, enrich_snow=False
    )

    # compare_location_weather_source.py-Aufrufmuster: synthetisches
    # Ein-Punkt-Segment, andere segment_id, dieselbe Koordinate/Stunde
    compare_segment = _segment("compare-preset-7", 45.5000, 9.2000, hour, duration_hours=1.0)
    compare_service = SegmentWeatherService(provider)
    compare_result = compare_service.fetch_segment_weather(
        compare_segment, enrich_ensemble=False, enrich_snow=False
    )

    assert provider.call_count == 1, (
        "AC-4: Trip und Compare-Preset am selben Ort im selben Zyklus "
        f"muessen sich EINEN Upstream-Call teilen (Beweis fuer "
        f"koordinatenbasierte statt segment_id-basierte Schluesselbildung), "
        f"tatsaechlich: {provider.call_count}"
    )

    # F001-Regressionsschutz: der Cache-Treffer darf NIE die Identitaet des
    # ERSTEN Aufrufers (trip) an den ZWEITEN (compare) durchreichen.
    assert compare_result.segment.segment_id == "compare-preset-7", (
        f"F001-Regression: compare_result traegt segment_id "
        f"{compare_result.segment.segment_id!r} statt der eigenen "
        f"'compare-preset-7'"
    )
    assert trip_result.segment.segment_id == "trip-42-segment-3"


# ---------------------------------------------------------------------------
# AC-9 / Adversary-Fund F001: zweiter Aufrufer mit ABWEICHENDER Fensterdauer
# erhaelt IMMER die eigene Identitaet und ein NUR ueber das eigene Fenster
# berechnetes Aggregat -- nie das des ersten Aufrufers.
# ---------------------------------------------------------------------------

def test_second_caller_with_different_window_keeps_own_identity_and_aggregate():
    """Reproduziert das Adversary-Muster direkt: ein breites Trip-Fenster
    (4h) wird zuerst gefetcht, ein schmaleres Compare-Fenster (1h) am
    selben Ort/derselben Stunde folgt -- der zweite Aufruf MUSS seine
    EIGENE segment_id, seine EIGENE duration_hours und ein NUR ueber sein
    EIGENES Fenster berechnetes Aggregat erhalten."""
    provider = HourlyCountingFakeProvider()
    hour = _safe_test_hour(10)

    trip_segment = _segment("trip-real-leg-3h", 47.0500, 11.1000, hour, duration_hours=4.0)
    compare_segment = _segment(
        "compare-point-99", 47.0500, 11.1000, hour, duration_hours=1.0
    )

    trip_service = SegmentWeatherService(provider)
    compare_service = SegmentWeatherService(provider)

    trip_result = trip_service.fetch_segment_weather(
        trip_segment, enrich_ensemble=False, enrich_snow=False
    )
    compare_result = compare_service.fetch_segment_weather(
        compare_segment, enrich_ensemble=False, enrich_snow=False
    )

    assert provider.call_count == 1, (
        "Trip (4h) und Compare (1h) am selben Ort/derselben Stunde teilen "
        f"sich weiterhin EINEN Upstream-Call, tatsaechlich: {provider.call_count}"
    )

    # F001: EIGENE Identitaet, nie die des ersten Aufrufers.
    assert compare_result.segment.segment_id == "compare-point-99", (
        f"F001-Regression: compare_result traegt fremde segment_id "
        f"{compare_result.segment.segment_id!r}"
    )
    assert compare_result.segment.duration_hours == 1.0

    # F001: EIGENES Aggregat, nur ueber das eigene 1h-Fenster (Stunde 10)
    # berechnet -- nicht das breitere 4h-Aggregat (Stunden 10-13) des Trips.
    assert compare_result.aggregated.temp_min_c == pytest.approx(10.0)
    assert compare_result.aggregated.temp_max_c == pytest.approx(10.0)

    # Kontrollwert: der Trip behaelt sein EIGENES, breiteres Aggregat.
    assert trip_result.segment.segment_id == "trip-real-leg-3h"
    assert trip_result.aggregated.temp_min_c == pytest.approx(10.0)
    assert trip_result.aggregated.temp_max_c == pytest.approx(13.0)


def test_too_small_cached_window_forces_new_upstream_call_no_truncation():
    """F001-Nachbeweis (kein stilles Kuerzen): GIVEN ein zuerst gecachter
    1h-Eintrag / WHEN eine GROESSERE 3h-Anfrage am selben Ort/derselben
    Stunde folgt / THEN ist das ein Cache-MISS -> ein zweiter Upstream-Call,
    und das Ergebnis deckt das VOLLE angeforderte Fenster ab (nicht nur die
    im Cache vorhandene 1h)."""
    provider = HourlyCountingFakeProvider()
    hour = _safe_test_hour(10)

    small_segment = _segment("first-1h", 47.3000, 11.5000, hour, duration_hours=1.0)
    bigger_segment = _segment("second-3h", 47.3000, 11.5000, hour, duration_hours=3.0)

    service = SegmentWeatherService(provider)
    service.fetch_segment_weather(small_segment, enrich_ensemble=False, enrich_snow=False)
    result = service.fetch_segment_weather(
        bigger_segment, enrich_ensemble=False, enrich_snow=False
    )

    assert provider.call_count == 2, (
        "Ein zu kleines gecachtes Fenster darf eine groessere Anfrage NICHT "
        f"bedienen -- erwartet 2 Upstream-Calls, tatsaechlich: {provider.call_count}"
    )
    # Aggregat deckt das VOLLE 3h-Fenster ab (Stunden 10,11,12), nicht nur 1h.
    assert result.segment.segment_id == "second-3h"
    assert result.aggregated.temp_min_c == pytest.approx(10.0)
    assert result.aggregated.temp_max_c == pytest.approx(12.0)


def test_end_to_end_real_call_paths_trip_alert_and_compare_share_cache_with_own_identity():
    """Adversary-Reproduktion woertlich, ueber die ECHTEN Produktionspfade
    (nicht nur `SegmentWeatherService` direkt): `TripAlertService.
    _fetch_fresh_weather` (Trip-Alarmpfad), gefolgt von
    `CompareLocationWeatherSource().fetch()` (Compare-Alarmpfad) am selben
    Ort/derselben Stunde. Netzfrei: `get_provider("openmeteo")` zeigt
    (autouse-Fixture in tests/conftest.py) auf die statische
    `FixtureProvider`."""
    from services.compare_location_weather_source import CompareLocationWeatherSource
    from services.trip_alert import TripAlertService

    lat, lon = 47.0500, 11.5500
    now_hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

    # Platzhalter fuer "cached_weather" (nur .segment wird von
    # _fetch_fresh_weather ausgewertet) -- Fenster deckt Compares implizites
    # [jetzt, jetzt+1h) mit ab, wie ein echtes 4h-Trip-Segment.
    trip_placeholder_segment = _segment(
        "trip-real-leg-3h", lat, lon, now_hour, duration_hours=4.0
    )
    trip_placeholder = SegmentWeatherData(
        segment=trip_placeholder_segment,
        timeseries=None,
        aggregated=SegmentWeatherSummary(),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )

    alert_service = TripAlertService.__new__(TripAlertService)
    trip_results = alert_service._fetch_fresh_weather([trip_placeholder])
    assert len(trip_results) == 1, "Trip-Alarmpfad haette genau 1 Ergebnis liefern muessen"
    assert trip_results[0].segment.segment_id == "trip-real-leg-3h"

    compare_result = CompareLocationWeatherSource().fetch("compare-point-99", lat, lon)

    assert compare_result.id == "compare-point-99", (
        "F001-Regression (Adversary-Fund, woertlich reproduziert): "
        f"CompareLocationWeatherSource.fetch() lieferte die fremde "
        f"Identitaet {compare_result.id!r} statt der eigenen "
        f"'compare-point-99'"
    )

    cache = get_shared_weather_cache()
    matching_entries = [
        entry
        for entry in cache._cache.values()
        if abs(entry.lat - round(lat, 4)) < 1e-9 and abs(entry.lon - round(lon, 4)) < 1e-9
    ]
    assert len(matching_entries) == 1, (
        "AC-4: Trip-Alarmpfad und Compare-Alarmpfad am selben Ort muessen "
        f"sich EINEN Cache-Eintrag teilen (kein separater Compare-Fetch), "
        f"tatsaechlich gefunden: {len(matching_entries)}"
    )


# ---------------------------------------------------------------------------
# Issue #1334: Segment-Filter ueber Mitternacht -- volle Zeitstempel statt
# reiner Stundenzahl (docs/specs/modules/daywindow_gap_and_midnight_fix.md)
# ---------------------------------------------------------------------------

def test_overnight_segment_excludes_same_hour_points_from_wrong_day():
    """AC-1 (#1334, MUSS ROT): Segment 22:00 Tag1 -> 02:00 Tag2 auf einer
    48h-Zeitreihe (zwei volle Tage, ``MultiDayHourlyCountingFakeProvider``).
    NUR die Stunden 22:00/23:00 (Tag1, Werte 22.0/23.0) und 00:00/01:00
    (Tag2, Werte 24.0/25.0) duerfen einfliessen. Der bestehende
    Wraparound-Filter in ``_aggregate_for_segment`` (Z.254:
    ``dp.ts.hour >= seg_start_h or dp.ts.hour < seg_end_h``) vergleicht nur
    die Stunde, nicht das volle Datum -- er zieht dieselben Uhrzeiten von
    BEIDEN Tagen (zusaetzlich Tag2 22:00/23:00 = 46.0/47.0 und Tag1
    00:00/01:00 = 0.0/1.0) -> falsches, zu weites Min/Max."""
    day1_anchor = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    provider = MultiDayHourlyCountingFakeProvider(day1_anchor)

    seg = _segment(
        "overnight-1", 47.5000, 11.0000,
        day1_anchor + timedelta(hours=22), duration_hours=4.0,
    )
    service = SegmentWeatherService(provider)
    result = service.fetch_segment_weather(seg, enrich_ensemble=False, enrich_snow=False)

    assert result.aggregated.temp_min_c == pytest.approx(22.0), (
        "AC-1: Segment 22:00->02:00 darf NUR die Stunden 22:00/23:00 (Tag1) "
        "und 00:00/01:00 (Tag2) aggregieren -- temp_min_c muss 22.0 sein "
        f"(Stunde 22:00 Tag1), tatsaechlich: {result.aggregated.temp_min_c} "
        "(Wraparound zieht faelschlich auch 00:00/01:00 von TAG1 = 0.0/1.0 "
        "mit ein)."
    )
    assert result.aggregated.temp_max_c == pytest.approx(25.0), (
        "AC-1: temp_max_c muss 25.0 sein (Stunde 01:00 Tag2 = Index 25), "
        f"tatsaechlich: {result.aggregated.temp_max_c} (Wraparound zieht "
        "faelschlich auch 22:00/23:00 von TAG2 = 46.0/47.0 mit ein -> 47.0)."
    )


def test_daytime_segment_excludes_end_hour_boundary():
    """AC-2 (#1334 Guard/#806, muss GRUEN bleiben): normales Tag-Segment
    10:00->13:00 -- die Endstunde 13:00 bleibt AUSGESCHLOSSEN (nur Stunden
    10,11,12), bitgleich zur bestehenden #806-Invariante. Bereits heute
    gruen; Regressionsschutz fuer den #1334-Fix."""
    provider = HourlyCountingFakeProvider()
    hour = _safe_test_hour(10)
    seg = _segment("t-daytime-10-13", 47.1000, 11.2000, hour, duration_hours=3.0)

    service = SegmentWeatherService(provider)
    result = service.fetch_segment_weather(seg, enrich_ensemble=False, enrich_snow=False)

    assert result.aggregated.temp_min_c == pytest.approx(10.0)
    assert result.aggregated.temp_max_c == pytest.approx(12.0), (
        "AC-2: Endstunde 13:00 muss ausgeschlossen bleiben (Stunden "
        f"10,11,12 -> max 12.0), tatsaechlich: {result.aggregated.temp_max_c}"
    )


def test_sub_hour_segment_includes_exact_start_hour_point():
    """AC-3 (#1334 Guard/#856, muss GRUEN bleiben): Sub-Stunden-Segment
    10:15->10:45 auf einer stuendlichen Zeitreihe -- enthaelt GENAU den
    10:00-Datenpunkt (nicht leer). Bereits heute gruen; Regressionsschutz
    fuer den #1334-Fix."""
    provider = HourlyCountingFakeProvider()
    hour = _safe_test_hour(10)
    start = hour + timedelta(minutes=15)
    seg = _segment("t-subhour-10-15-10-45", 47.3000, 11.4000, start, duration_hours=0.5)

    service = SegmentWeatherService(provider)
    result = service.fetch_segment_weather(seg, enrich_ensemble=False, enrich_snow=False)

    assert result.aggregated.temp_min_c == pytest.approx(10.0)
    assert result.aggregated.temp_max_c == pytest.approx(10.0), (
        "AC-3: 10:15->10:45 muss genau den 10:00-Punkt liefern (nicht "
        f"leer), tatsaechlich min={result.aggregated.temp_min_c} "
        f"max={result.aggregated.temp_max_c}"
    )
