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

The remaining real providers land in follow-up slices: #1143
(Météo-France FR), #1144 (DWD DE).
"""
from __future__ import annotations

from functools import partial
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


# No-arg factories for the provider registry (get_provider calls factory()).
make_de_direct = partial(RegionalStubProvider, "de_direct")
make_fr_direct = partial(RegionalStubProvider, "fr_direct")
