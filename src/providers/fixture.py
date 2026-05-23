"""
Offline fixture weather provider.

Loads static recorded weather data from local JSON files (the Go-format
fixtures produced by Issue #263) and satisfies the WeatherProvider protocol.
Activated exclusively in the test context via GZ_TEST_FIXTURE_DIR to avoid
exhausting the server-IP-wide Open-Meteo rate limit (Issue #338/#346).

In production (GZ_TEST_FIXTURE_DIR unset) this module is never imported.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    NormalizedTimeseries,
    Provider,
    ThunderLevel,
)
from providers.base import ProviderError

if TYPE_CHECKING:
    from app.config import Location


@dataclass
class _FixtureLocation:
    name: str
    lat: float
    lon: float
    filename: str


# Hardcoded registry of the 3 E2E test locations — identical to the Go
# implementation (internal/provider/fixture/provider.go).
_FIXTURE_LOCATIONS = [
    _FixtureLocation("Innsbruck", 47.2692, 11.4041, "innsbruck.json"),
    _FixtureLocation("Stubai", 47.1015, 11.2958, "stubai.json"),
    _FixtureLocation("Zillertal", 47.2190, 11.8767, "zillertal.json"),
]


def _nearest(latitude: float, longitude: float) -> _FixtureLocation:
    """Squared Euclidean distance over lat/lon — no sqrt needed."""
    best = _FIXTURE_LOCATIONS[0]
    best_dist = (best.lat - latitude) ** 2 + (best.lon - longitude) ** 2
    for loc in _FIXTURE_LOCATIONS[1:]:
        dist = (loc.lat - latitude) ** 2 + (loc.lon - longitude) ** 2
        if dist < best_dist:
            best_dist = dist
            best = loc
    return best


def _maybe_int(value: object) -> Optional[int]:
    return int(value) if value is not None else None  # type: ignore[arg-type]


def _maybe_thunder(value: object) -> Optional[ThunderLevel]:
    return ThunderLevel(value) if value is not None else None


class FixtureProvider:
    """Weather provider serving static forecasts from local JSON fixtures.

    Thread-safe: no shared mutable state — each fetch_forecast reads from disk.
    """

    def __init__(self, fixture_dir: str) -> None:
        self._dir = fixture_dir  # relative or absolute path

    @property
    def name(self) -> str:
        # Identical to the real provider — transparent for callers.
        return "openmeteo"

    def fetch_forecast(
        self,
        location: "Location",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        enrich_ensemble: bool = True,
    ) -> NormalizedTimeseries:
        """Load the geographically nearest fixture and re-stamp timestamps.

        ``start``/``end`` are ignored — the fixture always provides its fixed
        72 points anchored at the current UTC day. ``enrich_ensemble`` is
        ignored: the FixtureProvider performs no HTTP call whatsoever.
        """
        nearest = _nearest(location.latitude, location.longitude)
        path = Path(self._dir) / nearest.filename
        try:
            raw = json.loads(path.read_text())
        except FileNotFoundError as exc:
            raise ProviderError(
                "fixture", f"Fixture file not found: {path}"
            ) from exc

        if not raw.get("data"):
            raise ProviderError("fixture", f"Fixture has no data: {path}")

        base = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        data_points: list[ForecastDataPoint] = []
        for i, p in enumerate(raw.get("data", [])):
            data_points.append(
                ForecastDataPoint(
                    ts=base + timedelta(hours=i),
                    t2m_c=p.get("t2m_c"),
                    wind10m_kmh=p.get("wind10m_kmh"),
                    gust_kmh=p.get("gust_kmh"),
                    precip_1h_mm=p.get("precip_1h_mm"),
                    cloud_total_pct=_maybe_int(p.get("cloud_total_pct")),
                    wmo_code=_maybe_int(p.get("wmo_code")),
                    thunder_level=_maybe_thunder(p.get("thunder_level")),
                    visibility_m=_maybe_int(p.get("visibility_m")),
                    cape_jkg=p.get("cape_jkg"),
                    is_day=_maybe_int(p.get("is_day")),
                    dni_wm2=p.get("dni_wm2"),
                    uv_index=p.get("uv_index"),
                    snow_depth_cm=p.get("snow_depth_cm"),
                )
            )

        meta = ForecastMeta(
            provider=Provider.OPENMETEO,
            model="fixture",
            grid_res_km=0.0,
        )
        return NormalizedTimeseries(meta=meta, data=data_points)
