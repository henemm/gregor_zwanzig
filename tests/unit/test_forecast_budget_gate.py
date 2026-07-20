"""Issue #1329, Scheibe C+: Verbrauchsbudget mit Prioritaetsgate (Teil 2).

SPEC: docs/specs/modules/fix_1329_forecast_cache_budget.md (AC-5, AC-7)
Ausfuehrung:
    uv run pytest tests/unit/test_forecast_budget_gate.py -v

Kern-Schicht, netzfrei. Zaehlerdatei wird direkt vorpraepariert (kein Mock
der Klasse), Budget-Simulation gemaess Test Plan der Spec.

AC-8 (Go-Status-Endpunkt `/api/scheduler/status`) ist NICHT Teil dieser
Scheibe -- Go-seitig, eigenes Ticket.

Adversary-Fund F002 (MEDIUM, behoben): der Tageszaehler nutzte
`date.today()` (lokale Wanduhr) statt `datetime.now(timezone.utc).date()`.
Der Zaehler ist ein GLOBALER Tageszaehler fuer das open-meteo-Kontingent,
dessen Reset-Zeitpunkt UTC-nah ist -- ein lokal verschobener Tageswechsel
haette den Zaehler zur falschen Zeit zurueckgesetzt. Fix: `allow()` nimmt
einen optionalen, injizierbaren `now`-Parameter (aware UTC-Datetime,
Konvention aus `test_throttle_store.py`: "now ist ueberall ein expliziter
aware-UTC-Parameter, nie datetime.now() fuer Zeitvergleiche") -- der
Tagesschluessel wird IMMER aus `now.astimezone(timezone.utc).date()`
abgeleitet, nie aus `date.today()`.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest

from app.loader import get_data_root
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    TripSegment,
)
from services.forecast_budget import ForecastBudgetGate
from services.segment_weather import SegmentWeatherService
from services.weather_cache import (
    get_shared_weather_cache,
    reset_shared_weather_cache_for_tests,
)


class CountingFakeProvider:
    """Zaehlender Fake-Provider (KEIN Mock/patch) — siehe
    `test_forecast_cache_sharing.py` fuer dieselbe Konstruktion."""

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


def _segment(segment_id, lat: float, lon: float, start: datetime) -> TripSegment:
    point = GPXPoint(lat=lat, lon=lon, elevation_m=1200.0)
    end = start + timedelta(hours=2)
    return TripSegment(
        segment_id=segment_id,
        start_point=point,
        end_point=point,
        start_time=start,
        end_time=end,
        duration_hours=2.0,
        distance_km=0.0,
        ascent_m=0,
        descent_m=0,
    )


def _current_hour(offset_hours: int = 1) -> datetime:
    return datetime.now(timezone.utc).replace(
        minute=0, second=0, microsecond=0
    ) + timedelta(hours=offset_hours)


@pytest.fixture(autouse=True)
def _reset_shared_cache():
    reset_shared_weather_cache_for_tests()
    yield
    reset_shared_weather_cache_for_tests()


def _budget_path():
    return get_data_root() / "diagnostics" / "forecast_budget.json"


def _write_budget(calls_openmeteo: int, cache_hits: int = 0, cache_misses: int = 0) -> None:
    """Datei direkt vorbereiten (kein Mock der Klasse) — Test Plan Vorgabe."""
    path = _budget_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": date.today().isoformat(),
        "calls": {"openmeteo": calls_openmeteo},
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
    }
    path.write_text(json.dumps(payload))


def _write_corrupt_budget() -> None:
    path = _budget_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-valid-json,,,")


# ---------------------------------------------------------------------------
# AC-5: >= 95% Budget -> alert_check UND polling abgewiesen, user_briefing frei
# ---------------------------------------------------------------------------

def test_budget_at_95_percent_blocks_alert_check_and_polling_but_not_briefing():
    _write_budget(calls_openmeteo=8550)  # 8550 / 9000 = 0.95

    gate = ForecastBudgetGate()

    assert gate.allow("alert_check") is False, (
        "AC-5: bei >= 95% Budget muss alert_check abgewiesen werden"
    )
    assert gate.allow("polling") is False, (
        "AC-5: bei >= 95% Budget muss polling abgewiesen werden"
    )
    assert gate.allow("user_briefing") is True, (
        "AC-5: user_briefing darf NIE gedrosselt werden, auch nicht bei 95%"
    )


# ---------------------------------------------------------------------------
# >= 80% Budget -> nur polling abgewiesen, alert_check laeuft noch durch
# ---------------------------------------------------------------------------

def test_budget_at_80_percent_blocks_only_polling():
    _write_budget(calls_openmeteo=7200)  # 7200 / 9000 = 0.80

    gate = ForecastBudgetGate()

    assert gate.allow("polling") is False, (
        "Ab 80% Budget muss polling abgewiesen werden"
    )
    assert gate.allow("alert_check") is True, (
        "Bei 80% (< 95%-Schwelle) muss alert_check noch durchlaufen"
    )
    assert gate.allow("user_briefing") is True


def test_budget_below_80_percent_allows_everything():
    _write_budget(calls_openmeteo=1000)  # 1000 / 9000 ~ 0.11

    gate = ForecastBudgetGate()

    assert gate.allow("polling") is True
    assert gate.allow("alert_check") is True
    assert gate.allow("user_briefing") is True


# ---------------------------------------------------------------------------
# AC-7: kaputte/unlesbare Zaehlerdatei -> fail-open, KEIN Aufruf blockiert
# ---------------------------------------------------------------------------

def test_corrupted_counter_file_never_blocks_any_priority():
    _write_corrupt_budget()

    gate = ForecastBudgetGate()

    for priority in ("user_briefing", "alert_check", "polling"):
        assert gate.allow(priority) is True, (
            f"AC-7: Prioritaet '{priority}' darf bei kaputtem Zaehler "
            "NICHT blockiert werden (fail-open)"
        )


def test_missing_counter_file_never_blocks_any_priority():
    # Bewusst KEINE Datei schreiben — erster Zugriff ueberhaupt.
    assert not _budget_path().exists()

    gate = ForecastBudgetGate()

    for priority in ("user_briefing", "alert_check", "polling"):
        assert gate.allow(priority) is True, (
            f"Fehlende Zaehlerdatei darf '{priority}' nicht blockieren "
            "(fail-open, erster Zugriff nach Tageswechsel/Neustart)"
        )


def test_unknown_priority_is_never_throttled_even_under_budget_pressure():
    _write_budget(calls_openmeteo=8999)  # praktisch voll ausgeschoepft

    gate = ForecastBudgetGate()

    assert gate.allow("some_future_priority") is True, (
        "Unbekannte Prioritaeten sind fail-open (Spec 2.1: 'nie drosseln')"
    )


# ---------------------------------------------------------------------------
# End-to-End ueber fetch_segment_weather(priority=...) — Rueckgabewert
# ---------------------------------------------------------------------------

def test_end_to_end_alert_priority_blocked_at_95_percent_never_reaches_provider():
    _write_budget(calls_openmeteo=8550)
    provider = CountingFakeProvider()
    seg = _segment("alarm-seg", 47.2692, 11.4041, _current_hour())
    service = SegmentWeatherService(provider)

    result = service.fetch_segment_weather(
        seg, enrich_ensemble=False, enrich_snow=False, priority="alert_check"
    )

    assert provider.call_count == 0, (
        "AC-5: ein bei 95% Budget gedrosselter alert_check-Aufruf darf den "
        f"Provider gar nicht erst erreichen, tatsaechliche Calls: "
        f"{provider.call_count}"
    )
    assert result.has_error is True
    assert result.error_message == "budget_throttled", (
        f"Erwartete error_message 'budget_throttled', tatsaechlich: "
        f"{result.error_message!r}"
    )


def test_end_to_end_user_briefing_priority_reaches_provider_even_at_95_percent():
    _write_budget(calls_openmeteo=8550)
    provider = CountingFakeProvider()
    seg = _segment("briefing-seg", 48.1000, 16.3000, _current_hour(offset_hours=5))
    service = SegmentWeatherService(provider)

    result = service.fetch_segment_weather(
        seg, enrich_ensemble=True, enrich_snow=True, priority="user_briefing"
    )

    assert provider.call_count == 1, (
        "AC-5: user_briefing muss auch bei 95% Budget den Provider "
        f"erreichen, tatsaechliche Calls: {provider.call_count}"
    )
    assert result.has_error is False


def test_end_to_end_polling_priority_blocked_at_80_percent():
    _write_budget(calls_openmeteo=7200)
    provider = CountingFakeProvider()
    seg = _segment("polling-seg", 47.0000, 12.0000, _current_hour(offset_hours=6))
    service = SegmentWeatherService(provider)

    result = service.fetch_segment_weather(
        seg, enrich_ensemble=False, enrich_snow=False, priority="polling"
    )

    assert provider.call_count == 0, (
        "Ab 80% Budget muss ein polling-Aufruf den Provider gar nicht "
        f"erreichen, tatsaechliche Calls: {provider.call_count}"
    )
    assert result.has_error is True
    assert result.error_message == "budget_throttled"


def test_default_priority_without_explicit_argument_is_never_throttled():
    """Rueckwaertskompatibilitaet: Aufrufer, die `priority` nicht angeben,
    duerfen NIE gedrosselt werden (Default `user_briefing`, Spec 2.1)."""
    _write_budget(calls_openmeteo=8999)
    provider = CountingFakeProvider()
    seg = _segment("legacy-caller-seg", 47.5000, 10.5000, _current_hour(offset_hours=7))
    service = SegmentWeatherService(provider)

    result = service.fetch_segment_weather(seg, enrich_ensemble=False, enrich_snow=False)

    assert provider.call_count == 1, (
        "Aufrufer ohne explizites priority= muessen auf dem sicheren "
        f"Default (user_briefing, nie gedrosselt) laufen, tatsaechliche "
        f"Calls: {provider.call_count}"
    )
    assert result.has_error is False


# ---------------------------------------------------------------------------
# Adversary-Fund F002: UTC-Tageswechsel, nicht lokale Wanduhr
# ---------------------------------------------------------------------------

def test_counter_from_yesterday_utc_is_ignored_at_todays_utc_boundary():
    """F002: ein Zaehlerstand, der auf GESTERN (UTC) datiert ist, darf am
    heutigen UTC-Tag NICHT mehr wirken -- selbst wenn er praktisch
    ausgeschoepft war. Der Tagesvergleich MUSS ueber die injizierte,
    aware-UTC `now` erfolgen (Konvention `test_throttle_store.py`), nicht
    ueber eine implizite lokale Wanduhr."""
    now_utc = datetime.now(timezone.utc)
    yesterday_utc = (now_utc - timedelta(days=1)).date().isoformat()

    path = _budget_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "date": yesterday_utc,
        "calls": {"openmeteo": 8999},  # gestern praktisch ausgeschoepft
        "cache_hits": 0,
        "cache_misses": 0,
    }))

    gate = ForecastBudgetGate()

    assert gate.allow("polling", now=now_utc) is True, (
        "F002: ein 'gestern' (UTC) geschriebener, fast ausgeschoepfter "
        "Zaehlerstand darf am heutigen UTC-Tag NICHT mehr wirken -- der "
        "Tageswechsel muss anhand von now.astimezone(UTC).date() erkannt "
        "werden, nicht anhand der lokalen Wanduhr (date.today())"
    )
    assert gate.allow("alert_check", now=now_utc) is True


def test_counter_from_today_utc_still_applies_with_injected_now():
    """Gegenprobe zu F002: ein Zaehlerstand, der auf HEUTE (UTC, via
    injiziertem `now`) datiert ist, wirkt weiterhin normal -- der Fix
    aendert nur die Tagesgrenze, nicht die Zaehllogik selbst."""
    now_utc = datetime.now(timezone.utc)
    today_utc = now_utc.date().isoformat()

    path = _budget_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "date": today_utc,
        "calls": {"openmeteo": 8550},  # 95% -- ab hier alert_check/polling aus
        "cache_hits": 0,
        "cache_misses": 0,
    }))

    gate = ForecastBudgetGate()

    assert gate.allow("alert_check", now=now_utc) is False, (
        "Ein heutiger (UTC), fast ausgeschoepfter Zaehlerstand muss "
        "weiterhin ganz normal drosseln -- der F002-Fix betrifft nur die "
        "TagesGRENZE, nicht die Zaehllogik"
    )
    assert gate.allow("user_briefing", now=now_utc) is True
