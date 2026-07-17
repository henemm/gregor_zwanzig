"""Provider-neutral WEATHER-05b merge contract.

Extracted from `OpenMeteoProvider._merge_fallback` (Issue #1302 / Epic #1301,
Scheibe A1). Origin: WEATHER-05b, see `docs/specs/modules/model_metric_fallback.md`.

This function is anbieter-neutral (provider-agnostic): it has no hidden
binding to any single provider's parameter vocabulary. The caller passes
its own `param_to_field` mapping. Pure extraction, no behavior change --
the logic is copied verbatim from `openmeteo.py:357-378`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from app.models import NormalizedTimeseries


def merge_missing_fields(
    primary: "NormalizedTimeseries",
    fallback: "NormalizedTimeseries",
    missing_params: List[str],
    param_to_field: Dict[str, str],
) -> List[str]:
    """Fuellt None-Felder in primary aus fallback -- nur fuer missing_params.

    Ueberschreibt nie einen vorhandenen Wert. Join ueber dp.ts.
    Gibt die tatsaechlich gefuellten Parameter sortiert zurueck.
    """
    fb_by_ts = {dp.ts: dp for dp in fallback.data}
    filled: set = set()

    for dp in primary.data:
        fb_dp = fb_by_ts.get(dp.ts)
        if fb_dp is None:
            continue
        for param in missing_params:
            field_name = param_to_field.get(param)
            if field_name is None:
                continue
            if getattr(dp, field_name, None) is None:
                fb_val = getattr(fb_dp, field_name, None)
                if fb_val is not None:
                    setattr(dp, field_name, fb_val)
                    filled.add(param)

    return sorted(filled)
