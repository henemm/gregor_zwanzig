"""Direct providers for the Cross-Provider-Fallback regions (#1141/#1142).

Slice #1141 delivered ONLY the routing scaffold — no real region provider.
`RegionalStubProvider.fetch_forecast` always raises
`ProviderNotImplementedError` so callers (the total-outage seam in
`OpenMeteoProvider.fetch_forecast`) can distinguish "stub not wired yet"
from "direct provider technically failed" (`ProviderRequestError`).

Slice #1142 replaces the AT stub with `GeoSphereDirectProvider`, a thin
adapter delegating to the existing, production-used `GeoSphereProvider`
(unchanged) — called WITHOUT the hidden Open-Meteo cloud-layer enrichment
(`include_cloud_layers=False`), so the fallback for an Open-Meteo total
outage doesn't itself contact Open-Meteo again.

Slice #1143 replaces the FR stub with `MeteoFranceDirectProvider`
(`src/providers/meteofrance.py`), registered directly (no adapter here).

Slice #1144 replaces the DE stub with `DwdDirectProvider`
(`src/providers/dwd.py`), registered directly (no adapter here). After
#1144 no region stub is left open — AT/FR/DE all have a real direct
provider; `RegionalStubProvider` stays in this module as a generic
building block but is no longer instantiated by `_load_providers()`.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

import httpx

from providers.base import ProviderNotImplementedError, ProviderRequestError
from providers.geosphere import GeoSphereProvider

if TYPE_CHECKING:
    from app.config import Location
    from app.models import NormalizedTimeseries


class RegionalStubProvider:
    """Parametrized stub — one class, one instance per region name."""

    def __init__(self, region_name: str) -> None:
        self._name = region_name

    @property
    def name(self) -> str:
        return self._name

    def fetch_forecast(
        self,
        location: "Location",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        enrich_ensemble: bool = True,
        enrich_snow: bool = True,
    ) -> "NormalizedTimeseries":
        raise ProviderNotImplementedError(
            self._name,
            f"Direktprovider für {self._name} noch nicht angebunden (Slice #1141)",
        )


class GeoSphereDirectProvider:
    """Issue #1142: thin `at_direct` adapter delegating to the existing,
    production-used `GeoSphereProvider` — reused as-is (no behaviour change
    for `comparison_engine`/`radar_service`/Trip-Services, which keep using
    `get_provider("geosphere")` directly via their own instances)."""

    def __init__(self) -> None:
        self._inner = GeoSphereProvider()

    @property
    def name(self) -> str:
        return "at_direct"

    def fetch_forecast(
        self,
        location: "Location",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        enrich_ensemble: bool = True,
        enrich_snow: bool = True,  # ignored, fetch_combined already includes SNOWGRID
    ) -> "NormalizedTimeseries":
        # `fetch_combined` (unlike `GeoSphereProvider.fetch_forecast`) does
        # NOT translate httpx exceptions into `ProviderRequestError` — the
        # adapter must do it itself, otherwise a raw httpx exception would
        # propagate instead (breaking the seam's error handling, AC-3/AC-4).
        try:
            return self._inner.fetch_combined(
                lat=location.latitude,
                lon=location.longitude,
                start=start,
                end=end,
                include_cloud_layers=False,
            )
        except httpx.HTTPStatusError as e:
            raise ProviderRequestError(
                self.name, f"HTTP {e.response.status_code}: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise ProviderRequestError(self.name, f"Request failed: {e}")
