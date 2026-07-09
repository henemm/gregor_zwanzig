"""Stub direct providers for the Cross-Provider-Fallback regions (#1141).

Slice #1141 delivers ONLY the routing scaffold — no real region provider.
`RegionalStubProvider.fetch_forecast` always raises
`ProviderNotImplementedError` so callers (the total-outage seam in
`OpenMeteoProvider.fetch_forecast`) can distinguish "stub not wired yet"
from "direct provider technically failed" (`ProviderRequestError`).

The real providers land in follow-up slices: #1142 (GeoSphere AT),
#1143 (Météo-France FR), #1144 (DWD DE).
"""
from __future__ import annotations

from functools import partial
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from providers.base import ProviderNotImplementedError

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


# No-arg factories for the provider registry (get_provider calls factory()).
make_at_direct = partial(RegionalStubProvider, "at_direct")
make_de_direct = partial(RegionalStubProvider, "de_direct")
make_fr_direct = partial(RegionalStubProvider, "fr_direct")
