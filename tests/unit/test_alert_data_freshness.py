"""Issue #1329, Scheibe C+: Alarm-Datenfrische ohne explizites Cache-Clear
(AC-6).

SPEC: docs/specs/modules/fix_1329_forecast_cache_budget.md (AC-6)
Ausfuehrung:
    uv run pytest tests/unit/test_alert_data_freshness.py -v

Kern-Schicht, netzfrei (autouse `_use_fixture_provider` in
tests/conftest.py laesst `get_provider("openmeteo")`, das
`_fetch_fresh_weather` intern verwendet, auf die statische
`FixtureProvider` zeigen — kein Live-API-Call). KEINE Mocks/patch — der
Alarm-Pfad wird ECHT ueber `TripAlertService._fetch_fresh_weather`
durchlaufen (Vorbild: `tests/tdd/test_bug_338_openmeteo_call_counter.py`,
das exakt so `TripAlertService.__new__(TripAlertService)` nutzt, um die
`__init__`-Abhaengigkeiten fuer einen weissbox-Methodentest zu umgehen).

Frische wird ueber den bereits existierenden `SegmentWeatherData.fetched_at`
gemessen (kein Provider-Call-Zaehler noetig, da `_fetch_fresh_weather`
seinen Provider intern fest verdrahtet, siehe `trip_alert.py:814-820`):
- Ein Cache-HIT liefert `entry.cached_at` (den urspruenglichen Fetch-
  Zeitpunkt) als `fetched_at` zurueck (Adversary-Fund F001-Fix: der Cache
  liefert seit dem Fix nur noch die rohe Zeitreihe + `cached_at`, kein
  abgeleitetes `SegmentWeatherData` mehr -- `_aggregate_for_segment`
  reicht `cached_at` unveraendert als `fetched_at` durch).
- Ein Cache-MISS (weil TTL abgelaufen) liefert ein NEUES `fetched_at`.
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
    TripSegment,
)
from services.segment_weather import SegmentWeatherService
from services.trip_alert import TripAlertService
from services.weather_cache import (
    get_shared_weather_cache,
    reset_shared_weather_cache_for_tests,
)

TTL_SECONDS = 600  # 10 Minuten, Spec 1.3


class CountingFakeProvider:
    """Zaehlender Fake-Provider (KEIN Mock/patch) — nur fuer das SEEDING des
    Shared-Cache genutzt (Vor-Population der zwei Testeintraege). Der
    eigentliche Alarm-Pfad (`_fetch_fresh_weather`) verwendet intern
    `get_provider("openmeteo")`, das durch die autouse-Fixture in
    tests/conftest.py auf die netzfreie `FixtureProvider` umgeleitet wird."""

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
            for i in range(4)
        ]
        return NormalizedTimeseries(meta=meta, data=data)


def _segment(segment_id, lat: float, lon: float, start: datetime) -> TripSegment:
    point = GPXPoint(lat=lat, lon=lon, elevation_m=1200.0)
    end = start + timedelta(hours=4)
    return TripSegment(
        segment_id=segment_id,
        start_point=point,
        end_point=point,
        start_time=start,
        end_time=end,
        duration_hours=4.0,
        distance_km=0.0,
        ascent_m=0,
        descent_m=0,
    )


@pytest.fixture(autouse=True)
def _reset_shared_cache():
    reset_shared_weather_cache_for_tests()
    yield
    reset_shared_weather_cache_for_tests()


def _age_cache_entry_at(cache, lat: float, lon: float, new_timestamp: datetime) -> None:
    """Weissbox-Zugriff auf den EINEN passenden Cache-Eintrag (identifiziert
    ueber lat/lon, Issue #1329 -- der Cache-Eintrag traegt seit dem
    F001-Fix keine Segment-Identitaet mehr): setzt `cached_at`. Auf einem
    Cache-HIT reicht `_aggregate_for_segment` genau diesen Zeitstempel als
    `fetched_at` durch (kein `datetime.now()`), daher reicht die Mutation
    hier aus, um die Alarm-Frische deterministisch zu steuern."""
    for entry in cache._cache.values():
        if abs(entry.lat - round(lat, 4)) < 1e-9 and abs(entry.lon - round(lon, 4)) < 1e-9:
            entry.cached_at = new_timestamp
            return
    raise AssertionError(f"Kein Cache-Eintrag fuer lat={lat}, lon={lon} gefunden")


def test_alarm_path_reuses_fresh_entry_and_refetches_stale_entry_without_clear():
    provider = CountingFakeProvider()
    hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

    seg_fresh = _segment("alert-fresh", 47.1015, 11.2958, hour)
    seg_stale = _segment("alert-stale", 47.2190, 11.8767, hour)

    # Shared Cache mit einem frischen und einem (noch) frischen Eintrag
    # vorbefuellen — ueber die stabile oeffentliche API, kein Cache-Internas-
    # Schreibzugriff.
    seeding_service = SegmentWeatherService(provider)
    fresh_seed = seeding_service.fetch_segment_weather(
        seg_fresh, enrich_ensemble=False, enrich_snow=False
    )
    stale_seed = seeding_service.fetch_segment_weather(
        seg_stale, enrich_ensemble=False, enrich_snow=False
    )
    assert provider.call_count == 2, (
        "Vorbedingung: zwei unterschiedliche Orte muessen beim Seeding "
        f"zwei Upstream-Calls ausloesen, tatsaechlich: {provider.call_count}"
    )

    cache = get_shared_weather_cache()

    fresh_original_fetched_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    stale_original_fetched_at = datetime.now(timezone.utc) - timedelta(minutes=15)
    _age_cache_entry_at(cache, 47.1015, 11.2958, fresh_original_fetched_at)
    _age_cache_entry_at(cache, 47.2190, 11.8767, stale_original_fetched_at)

    alert_service = TripAlertService.__new__(TripAlertService)
    call_time = datetime.now(timezone.utc)

    # WICHTIG: `_fetch_fresh_weather` darf hier KEIN `_cache.clear()` mehr
    # ausfuehren (trip_alert.py:833, AC-6-Verhaltensaenderung) — genau das
    # ist heute (RED) noch der Fall.
    results = alert_service._fetch_fresh_weather([fresh_seed, stale_seed])

    by_segment_id = {r.segment.segment_id: r for r in results}
    assert set(by_segment_id) == {"alert-fresh", "alert-stale"}, (
        f"Erwartete beide Segmente im Ergebnis, tatsaechlich: {sorted(by_segment_id)}"
    )

    fresh_result = by_segment_id["alert-fresh"]
    stale_result = by_segment_id["alert-stale"]

    assert fresh_result.fetched_at == fresh_original_fetched_at, (
        "AC-6: ein < 10 Min alter Cache-Eintrag muss als Cache-HIT bedient "
        "werden (fetched_at bleibt der urspruengliche Cache-Zeitstempel, "
        f"kein erneuter Fetch); tatsaechlich: {fresh_result.fetched_at} "
        f"(erwartet: {fresh_original_fetched_at})"
    )
    assert stale_result.fetched_at >= call_time, (
        "AC-6: ein > 10 Min alter Cache-Eintrag (TTL-abgelaufen) muss neu "
        f"vom Provider geholt werden (neuer fetched_at-Zeitstempel); "
        f"tatsaechlich: {stale_result.fetched_at} (Aufrufzeitpunkt: {call_time})"
    )

    check_time = datetime.now(timezone.utc)
    for label, result in (("fresh", fresh_result), ("stale", stale_result)):
        age_seconds = (check_time - result.fetched_at).total_seconds()
        assert age_seconds <= TTL_SECONDS, (
            f"AC-6: Ergebnis '{label}' ist {age_seconds:.0f}s alt "
            f"(> TTL {TTL_SECONDS}s) — die Alarm-Frische darf trotz Wegfall "
            "des expliziten Cache-Clears nie ueber den TTL hinaus veralten"
        )
