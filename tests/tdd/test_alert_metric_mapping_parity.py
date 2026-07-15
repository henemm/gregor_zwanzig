"""RED test for Bug #1257: catalog metric_id → AlertMetric forward mapping.

Two vocabularies exist without a translator: the metric catalog (`gust`,
`precipitation`, `temperature`, ...) and `AlertMetric` (`wind_gust`,
`precipitation_sum`, ...). `_ALERT_METRIC_TO_CATALOG_ID` in
`src/services/weather_change_detection.py` already provides the backward
mapping (AlertMetric → tuple of catalog ids). The fix introduces an explicit,
named FORWARD mapping `catalog_id_to_alert_metrics()` (catalog id → set of
alertable AlertMetric values), computed as the inverse of
`_ALERT_METRIC_TO_CATALOG_ID`, filtered to the Go-side alertable vocabulary
(`AlertableMetrics`): wind_gust, precipitation_sum, temperature_min,
temperature_max, snow_line, thunder_level.

This test MUST fail right now with an ImportError, because
`catalog_id_to_alert_metrics` does not exist yet (TDD RED, Phase 5).

No mocks — deterministic core-layer test against the real module dict.
"""
from __future__ import annotations

from app.models import AlertMetric
from services.weather_change_detection import (
    _ALERT_METRIC_TO_CATALOG_ID,
    catalog_id_to_alert_metrics,
)

# Go-side alertable vocabulary (AlertableMetrics), mirrored here to detect drift.
_ALERTABLE_METRIC_VALUES = {
    "wind_gust",
    "precipitation_sum",
    "temperature_min",
    "temperature_max",
    "snow_line",
    "thunder_level",
}


def test_gust_maps_to_wind_gust():
    assert catalog_id_to_alert_metrics()["gust"] == {"wind_gust"}


def test_precipitation_maps_to_precipitation_sum():
    assert catalog_id_to_alert_metrics()["precipitation"] == {"precipitation_sum"}


def test_thunder_maps_to_thunder_level():
    assert catalog_id_to_alert_metrics()["thunder"] == {"thunder_level"}


def test_temperature_maps_to_both_min_and_max():
    assert catalog_id_to_alert_metrics()["temperature"] == {
        "temperature_min",
        "temperature_max",
    }


def test_snowfall_limit_maps_to_snow_line():
    assert catalog_id_to_alert_metrics()["snowfall_limit"] == {"snow_line"}


def test_freezing_level_maps_to_snow_line():
    assert catalog_id_to_alert_metrics()["freezing_level"] == {"snow_line"}


def test_forward_mapping_is_exact_inverse_of_backward_mapping():
    """Drift guard: forward mapping must equal the computed inverse of
    _ALERT_METRIC_TO_CATALOG_ID, filtered to the alertable vocabulary.

    This keeps Go (AlertableMetrics) and Python (_ALERT_METRIC_TO_CATALOG_ID)
    in sync automatically — if either side changes without updating the other,
    this test fails.
    """
    expected: dict[str, set[str]] = {}
    for metric, catalog_ids in _ALERT_METRIC_TO_CATALOG_ID.items():
        if metric.value not in _ALERTABLE_METRIC_VALUES:
            continue
        for catalog_id in catalog_ids:
            expected.setdefault(catalog_id, set()).add(metric.value)

    assert catalog_id_to_alert_metrics() == expected

    # Sanity: every value produced is a real AlertMetric value in the
    # alertable vocabulary, and non-alertable metrics (e.g. CAPE, VISIBILITY,
    # FRESH_SNOW, *_CHANGE) never leak into the forward mapping.
    all_values = {v for values in catalog_id_to_alert_metrics().values() for v in values}
    assert all_values <= _ALERTABLE_METRIC_VALUES
    assert all_values == {m.value for m in AlertMetric} & _ALERTABLE_METRIC_VALUES
