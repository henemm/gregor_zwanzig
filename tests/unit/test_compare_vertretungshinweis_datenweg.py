"""Issue #1563 — Datenweg ``forecast_meta`` je Ort (TDD RED, AC-9).

SPEC: docs/specs/modules/feat_1563_compare_vertretungshinweis.md (R1, AC-9)

Kern-Schicht, netzfrei, ohne Mock-Theater: ein echter Fake-Provider
(erfuellt das ``WeatherProvider``-Protokoll) wird ueber die echte
Provider-Registry eingehaengt (Muster ``test_compare_preview_second_call_uses_cache``).
Beobachtungspunkt: ``LocationResult.forecast_meta`` aus ``ComparisonEngine.run``
bzw. ``result["forecast_meta"]`` aus ``fetch_forecast_for_location``.

RED-Ursache heute: ``LocationResult`` hat kein Feld ``forecast_meta`` und die
Engine reicht ``forecast.meta`` nicht weiter.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider

VIENNA = ZoneInfo("Europe/Vienna")
GEWITTER_FELD = "lightning_density_per_km2_3h"


class FallbackMetaProvider:
    """Liefert eine Zeitreihe, deren ``meta`` eine Vertretung traegt."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.call_count = 0

    @property
    def name(self) -> str:
        return "openmeteo"

    def fetch_forecast(self, location, start=None, end=None,
                       enrich_ensemble: bool = True, enrich_snow: bool = True):
        with self._lock:
            self.call_count += 1
        anchor = datetime.now(timezone.utc).replace(hour=0, minute=0,
                                                    second=0, microsecond=0)
        meta = ForecastMeta(
            provider=Provider.OPENMETEO, model="icon_d2", grid_res_km=2.2,
            run=anchor, fallback_model="icon_eu",
            fallback_metrics=["temperature_2m", GEWITTER_FELD],
            fallback_reason="metric_gap",
        )
        data = [ForecastDataPoint(ts=anchor + timedelta(hours=i), t2m_c=3.0 + i % 7,
                                  wind10m_kmh=10.0, gust_kmh=20.0,
                                  cloud_total_pct=30, precip_1h_mm=0.0, pop_pct=10)
                for i in range(24 * 6)]
        return NormalizedTimeseries(meta=meta, data=data)


@pytest.fixture
def provider(monkeypatch):
    import providers.base as registry

    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)
    if not registry._PROVIDER_FACTORIES:
        registry._load_providers()
    p = FallbackMetaProvider()
    monkeypatch.setitem(registry._PROVIDER_FACTORIES, "openmeteo", lambda: p)
    return p


def _ort():
    from app.user import SavedLocation

    # eindeutige Koordinate je Testlauf -> Cache-Schluessel nicht vorbelegt
    off = (uuid.uuid4().int % 9000) / 100000.0
    return SavedLocation(id=f"loc-1563-{uuid.uuid4().hex[:6]}", name="Seefeld",
                         lat=47.3297 + off, lon=11.1880 + off,
                         elevation_m=1180, timezone="Europe/Vienna")


def _run(loc):
    from services.comparison_engine import ComparisonEngine

    return ComparisonEngine.run(
        locations=[loc], time_window=(9, 16),
        target_date=datetime.now(VIENNA).date() + timedelta(days=1),
        official_alerts_enabled=False,
    )


def test_fetch_forecast_for_location_traegt_meta_im_ergebnis(provider):
    from services.comparison_engine import fetch_forecast_for_location

    res = fetch_forecast_for_location(_ort(), user_id="u-1563-a")
    meta = res.get("forecast_meta")
    assert meta is not None
    assert meta.fallback_model == "icon_eu"
    assert GEWITTER_FELD in meta.fallback_metrics


def test_engine_reicht_forecast_meta_ins_location_result(provider):
    result = _run(_ort())
    lr = result.locations[0]
    assert lr.error is None
    assert lr.forecast_meta is not None
    assert lr.forecast_meta.fallback_model == "icon_eu"
    assert lr.forecast_meta.fallback_reason == "metric_gap"


def test_ac9_cache_treffer_liefert_dasselbe_forecast_meta(provider):
    loc = _ort()
    frisch = _run(loc).locations[0].forecast_meta
    abrufe_nach_erstem = provider.call_count
    gecacht = _run(loc).locations[0].forecast_meta
    assert provider.call_count == abrufe_nach_erstem, "zweiter Lauf muss aus dem Cache kommen"
    assert frisch is not None and gecacht is not None
    assert gecacht.fallback_model == frisch.fallback_model
    assert gecacht.fallback_metrics == frisch.fallback_metrics
    assert gecacht.fallback_reason == frisch.fallback_reason


def test_fehlerort_traegt_kein_forecast_meta(monkeypatch):
    import providers.base as registry
    from providers.base import ProviderRequestError

    class Kaputt(FallbackMetaProvider):
        def fetch_forecast(self, *a, **k):
            raise ProviderRequestError("openmeteo", "stoerung-1563")

    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)
    if not registry._PROVIDER_FACTORIES:
        registry._load_providers()
    monkeypatch.setitem(registry._PROVIDER_FACTORIES, "openmeteo", lambda: Kaputt())
    lr = _run(_ort()).locations[0]
    assert lr.error
    assert lr.forecast_meta is None
