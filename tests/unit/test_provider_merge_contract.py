"""
Unit tests for the provider-neutral merge contract (Issue #1302 / Epic #1301, Scheibe A1).

`merge_missing_fields` (src/providers/merge.py) is the freed WEATHER-05b merge
mechanic: it must work with ANY provider's param->field mapping, not just
OpenMeteo's `_PARAM_TO_FIELD`. This suite proves that with a foreign,
non-Open-Meteo mapping (as e.g. a national weather service like MET Norway
would define its own parameter names).

SPEC: docs/specs/modules/rework_1302_merge_contract_extraction.md
TDD RED: both tests MUST FAIL before implementation (ImportError, since
src/providers/merge.py does not exist yet).

No mocks. Real NormalizedTimeseries / ForecastDataPoint objects. No network.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider

# RED: this module does not exist yet (pure extraction target of #1302).
from providers.merge import merge_missing_fields


# A plausible mapping a *foreign*, non-Open-Meteo service would define.
# Deliberately uses different param names than OpenMeteoProvider._PARAM_TO_FIELD
# (which uses "cape", "visibility", "temperature_2m", ...) to prove the merge
# contract has no hidden binding to Open-Meteo's vocabulary.
FOREIGN_PARAM_TO_FIELD = {
    "schnee_hoehe": "snow_depth_cm",
    "sichtweite": "visibility_m",
    "windboe": "gust_kmh",
}


def _make_meta(provider: Provider = Provider.MET, model: str = "met_nordic") -> ForecastMeta:
    return ForecastMeta(
        provider=provider,
        model=model,
        run=datetime(2026, 7, 17, 0, 0, tzinfo=timezone.utc),
        grid_res_km=2.5,
        interp="grid_point",
    )


def _make_dp(
    hour: int,
    snow_depth_cm: float | None = None,
    visibility_m: int | None = None,
    gust_kmh: float | None = None,
) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 7, 18, hour, 0, tzinfo=timezone.utc),
        t2m_c=5.0,
        wind10m_kmh=20.0,
        gust_kmh=gust_kmh,
        precip_1h_mm=0.0,
        cloud_total_pct=40,
        humidity_pct=70,
        snow_depth_cm=snow_depth_cm,
        visibility_m=visibility_m,
    )


def _make_timeseries(
    provider: Provider = Provider.MET,
    model: str = "met_nordic",
    snow_depth_cm: float | None = None,
    visibility_m: int | None = None,
    gust_kmh: float | None = None,
) -> NormalizedTimeseries:
    meta = _make_meta(provider=provider, model=model)
    data = [
        _make_dp(h, snow_depth_cm=snow_depth_cm, visibility_m=visibility_m, gust_kmh=gust_kmh)
        for h in range(8, 11)
    ]
    return NormalizedTimeseries(meta=meta, data=data)


# ---------------------------------------------------------------------------
# AC-1: merge_missing_fields works with a foreign (non-Open-Meteo) mapping.
# ---------------------------------------------------------------------------

class TestMergeMissingFieldsForeignMapping:
    """Proves the contract is provider-neutral: works with a mapping that
    OpenMeteoProvider has never seen."""

    def test_fills_gaps_with_foreign_mapping_and_reports_filled_params(self) -> None:
        primary = _make_timeseries(
            provider=Provider.MET, model="met_nordic",
            snow_depth_cm=None, visibility_m=None,
        )
        fallback = _make_timeseries(
            provider=Provider.MET, model="met_nordic_backup",
            snow_depth_cm=35.0, visibility_m=8000,
        )

        filled = merge_missing_fields(
            primary, fallback,
            missing_params=["schnee_hoehe", "sichtweite"],
            param_to_field=FOREIGN_PARAM_TO_FIELD,
        )

        assert filled == sorted(["schnee_hoehe", "sichtweite"])
        for dp in primary.data:
            assert dp.snow_depth_cm == 35.0
            assert dp.visibility_m == 8000

    def test_unknown_missing_param_is_ignored(self) -> None:
        """A missing_param not present in the (foreign) mapping must be
        skipped silently, not raise -- same contract as the extracted code."""
        primary = _make_timeseries(provider=Provider.MET, snow_depth_cm=None)
        fallback = _make_timeseries(provider=Provider.MET, snow_depth_cm=35.0)

        filled = merge_missing_fields(
            primary, fallback,
            missing_params=["schnee_hoehe", "voellig_unbekannt"],
            param_to_field=FOREIGN_PARAM_TO_FIELD,
        )

        assert filled == ["schnee_hoehe"]


# ---------------------------------------------------------------------------
# AC-2: existing values are NEVER overwritten -- core WEATHER-05b promise.
# ---------------------------------------------------------------------------

class TestMergeMissingFieldsNeverOverwrites:
    """A field that already has a value in primary must survive untouched,
    even when the fallback timeseries offers a differing value for it."""

    def test_existing_value_is_not_overwritten(self) -> None:
        primary = _make_timeseries(
            provider=Provider.MET,
            snow_depth_cm=12.0,      # already has a value
            visibility_m=None,       # gap -- should be filled
        )
        fallback = _make_timeseries(
            provider=Provider.MET,
            snow_depth_cm=99.0,      # differing value -- must be ignored
            visibility_m=6000,
        )

        filled = merge_missing_fields(
            primary, fallback,
            missing_params=["schnee_hoehe", "sichtweite"],
            param_to_field=FOREIGN_PARAM_TO_FIELD,
        )

        # snow_depth_cm was already present -> not reported as filled, not overwritten
        assert "schnee_hoehe" not in filled
        assert "sichtweite" in filled
        for dp in primary.data:
            assert dp.snow_depth_cm == 12.0
            assert dp.visibility_m == 6000

    def test_existing_zero_value_is_not_treated_as_a_gap(self) -> None:
        """The riskiest edge case for AC-2: a *falsy* existing value (0.0mm
        precipitation -- 'it is not raining', a real measurement, not a
        missing one) must survive untouched. If the implementation ever
        switches from `is None` to a falsy check (`if not getattr(...)`),
        this must catch it: 0.0 would then look like a gap and get
        overwritten by the fallback's differing value.
        """
        primary_meta = _make_meta(provider=Provider.MET)
        fallback_meta = _make_meta(provider=Provider.MET, model="met_nordic_backup")

        primary = NormalizedTimeseries(
            meta=primary_meta,
            data=[
                ForecastDataPoint(
                    ts=datetime(2026, 7, 18, hour, 0, tzinfo=timezone.utc),
                    t2m_c=5.0,
                    wind10m_kmh=20.0,
                    precip_1h_mm=0.0,  # real zero -- "it is not raining", not a gap
                    cloud_total_pct=40,
                    humidity_pct=70,
                )
                for hour in range(8, 11)
            ],
        )
        fallback = NormalizedTimeseries(
            meta=fallback_meta,
            data=[
                ForecastDataPoint(
                    ts=datetime(2026, 7, 18, hour, 0, tzinfo=timezone.utc),
                    t2m_c=5.0,
                    wind10m_kmh=20.0,
                    precip_1h_mm=99.0,  # differing value -- must be ignored
                    cloud_total_pct=40,
                    humidity_pct=70,
                )
                for hour in range(8, 11)
            ],
        )

        param_to_field = {**FOREIGN_PARAM_TO_FIELD, "niederschlag": "precip_1h_mm"}
        filled = merge_missing_fields(
            primary, fallback,
            missing_params=["niederschlag"],
            param_to_field=param_to_field,
        )

        # precip_1h_mm was already present (as 0.0) -> not reported as filled,
        # and NOT overwritten with the fallback's 99.0.
        assert "niederschlag" not in filled
        for dp in primary.data:
            assert dp.precip_1h_mm == 0.0
