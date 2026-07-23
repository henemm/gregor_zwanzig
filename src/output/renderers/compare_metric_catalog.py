"""Compare-Metrik-Katalog (Backend-Datenquelle fuer #1350 Teil 1).

Liefert die 25 Ortsvergleich-Metriken als explizite, angereicherte Struktur
(Label/Unit/Decimals/`higherIsBetter`/`kind`/Wertebereich bzw. Enum-/Ordinal-
Werte). Migriert 1:1 aus den heutigen Frontend-Quellen
`compareMetricDefs.ts::ALL_METRICS` und `corridorEditorState.ts` (Thunder-
Ordinal-Sonderbehandlung, PO-Entscheidung 2026-07-12) — siehe
docs/specs/modules/compare_metric_catalog_endpoint.md.

Teil 1 (Strangler-Migration, Issue #1350): Der Katalog wird NUR bereitgestellt,
noch nicht vom Frontend konsumiert. Keine Aenderung an compareMetricDefs.ts,
corridorEditorState.ts oder der `active_metrics`/`corridors`-Persistenz.

Keys sind identisch zu `compare_metric_ids.py::FRONTEND_TO_RENDERER_METRIC_ID`
(keine sechste Kopie der Keyliste) -- der Modul-Import-Assert unten macht eine
kuenftige Drift wie #1324 strukturell unmoeglich: fehlt ein Key im Katalog oder
im Resolver, schlaegt der Import fehl.
"""
from __future__ import annotations

from output.renderers.compare_metric_ids import FRONTEND_TO_RENDERER_METRIC_ID

# Reihenfolge = ALL_METRICS-Reihenfolge im Frontend (compareMetricDefs.ts),
# erleichtert visuellen Diff in Teil 2 (Spec "Expected Behavior").
COMPARE_METRIC_CATALOG: list[dict] = [
    {"key": "snow_depth_cm", "label": "Schneehöhe", "unit": "cm", "decimals": 0,
     "higherIsBetter": True, "kind": "range", "rangeMin": 0, "rangeMax": 200, "step": 5},
    {"key": "snow_new_sum_cm", "label": "Neuschnee", "unit": "cm", "decimals": 0,
     "higherIsBetter": True, "kind": "range", "rangeMin": 0, "rangeMax": 50, "step": 1},
    {"key": "sunny_hours_h", "label": "Sonnenstunden", "unit": "h", "decimals": 1,
     "higherIsBetter": True, "kind": "range", "rangeMin": 0, "rangeMax": 12, "step": 0.5},
    {"key": "wind_max_kmh", "label": "Windspitzen", "unit": "km/h", "decimals": 0,
     "higherIsBetter": False, "kind": "range", "rangeMin": 0, "rangeMax": 100, "step": 5},
    {"key": "cloud_avg_pct", "label": "Bewölkung Ø", "unit": "%", "decimals": 0,
     "higherIsBetter": False, "kind": "range", "rangeMin": 0, "rangeMax": 100, "step": 5},
    {"key": "visibility_min_m", "label": "Sichtweite min", "unit": "m", "decimals": 0,
     "higherIsBetter": True, "kind": "range", "rangeMin": 0, "rangeMax": 10000, "step": 500},
    {"key": "precip_sum_mm", "label": "Niederschlag", "unit": "mm", "decimals": 1,
     "higherIsBetter": False, "kind": "range", "rangeMin": 0, "rangeMax": 30, "step": 0.5},
    {"key": "uv_index_max", "label": "UV-Index max", "unit": "", "decimals": 0,
     "higherIsBetter": False, "kind": "range", "rangeMin": 0, "rangeMax": 12, "step": 1},
    {"key": "temp_max_c", "label": "Temperatur max", "unit": "°C", "decimals": 0,
     "higherIsBetter": True, "kind": "range", "rangeMin": -20, "rangeMax": 45, "step": 1},
    {"key": "thunder_level_max", "label": "Gewitter", "unit": "", "decimals": 0,
     "higherIsBetter": False, "kind": "ordinal",
     "ordinalLabels": ["kein", "mittel", "hoch"]},
    {"key": "temp_min_c", "label": "Temperatur min", "unit": "°C", "decimals": 0,
     "higherIsBetter": True, "kind": "range", "rangeMin": -30, "rangeMax": 30, "step": 1},
    {"key": "gust_max_kmh", "label": "Böen", "unit": "km/h", "decimals": 0,
     "higherIsBetter": False, "kind": "range", "rangeMin": 0, "rangeMax": 150, "step": 5},
    {"key": "cape_max_jkg", "label": "Gewitter-Energie (CAPE)", "unit": "J/kg", "decimals": 0,
     "higherIsBetter": False, "kind": "range", "rangeMin": 0, "rangeMax": 3000, "step": 100},
    {"key": "freezing_level_m", "label": "Nullgradgrenze", "unit": "m", "decimals": 0,
     "higherIsBetter": True, "kind": "range", "rangeMin": 0, "rangeMax": 5000, "step": 100},
    {"key": "pop_max_pct", "label": "Regenwahrscheinlichkeit", "unit": "%", "decimals": 0,
     "higherIsBetter": False, "kind": "range", "rangeMin": 0, "rangeMax": 100, "step": 5},
    {"key": "wind_direction_deg", "label": "Windrichtung", "unit": "°", "decimals": 0,
     "higherIsBetter": False, "kind": "range", "rangeMin": 0, "rangeMax": 360, "step": 10},
    {"key": "wind_chill_min_c", "label": "Gefühlte Temp. min", "unit": "°C", "decimals": 0,
     "higherIsBetter": True, "kind": "range", "rangeMin": -30, "rangeMax": 30, "step": 1},
    {"key": "humidity_avg_pct", "label": "Luftfeuchtigkeit Ø", "unit": "%", "decimals": 0,
     "higherIsBetter": False, "kind": "range", "rangeMin": 0, "rangeMax": 100, "step": 5},
    {"key": "dewpoint_avg_c", "label": "Taupunkt Ø", "unit": "°C", "decimals": 0,
     "higherIsBetter": False, "kind": "range", "rangeMin": -20, "rangeMax": 30, "step": 1},
    {"key": "snowfall_limit_m", "label": "Schneefallgrenze", "unit": "m", "decimals": 0,
     "higherIsBetter": True, "kind": "range", "rangeMin": 0, "rangeMax": 5000, "step": 100},
    {"key": "precip_type_dominant", "label": "Niederschlagsart", "unit": "", "decimals": 0,
     "higherIsBetter": False, "kind": "enum",
     "enumValues": ["RAIN", "SNOW", "MIXED", "FREEZING_RAIN"]},
    {"key": "cloud_low_avg_pct", "label": "Wolken tief", "unit": "%", "decimals": 0,
     "higherIsBetter": False, "kind": "range", "rangeMin": 0, "rangeMax": 100, "step": 5},
    {"key": "cloud_mid_avg_pct", "label": "Wolken mittel", "unit": "%", "decimals": 0,
     "higherIsBetter": False, "kind": "range", "rangeMin": 0, "rangeMax": 100, "step": 5},
    {"key": "cloud_high_avg_pct", "label": "Wolken hoch", "unit": "%", "decimals": 0,
     "higherIsBetter": False, "kind": "range", "rangeMin": 0, "rangeMax": 100, "step": 5},
    {"key": "pressure_avg_hpa", "label": "Luftdruck Ø", "unit": "hPa", "decimals": 0,
     "higherIsBetter": True, "kind": "range", "rangeMin": 950, "rangeMax": 1050, "step": 5},
]

# Drift-Wächter (Spec Punkt 3): Katalog-Keys MÜSSEN mit der autoritativen
# Key-Liste aus compare_metric_ids.py identisch sein -- fehlt ein Key auf
# einer der beiden Seiten, schlägt der Import fehl (statt still zu driften,
# vgl. #1324).
_catalog_keys = {entry["key"] for entry in COMPARE_METRIC_CATALOG}
_resolver_keys = set(FRONTEND_TO_RENDERER_METRIC_ID.keys())
assert _catalog_keys == _resolver_keys, (
    "compare_metric_catalog.py Keys weichen von "
    "compare_metric_ids.FRONTEND_TO_RENDERER_METRIC_ID ab: "
    f"nur im Katalog: {_catalog_keys - _resolver_keys}, "
    f"nur im Resolver: {_resolver_keys - _catalog_keys}"
)


def get_compare_metric_catalog() -> list[dict]:
    """Liefert die 25 Ortsvergleich-Metriken (read-only Kopie der Katalog-Liste)."""
    return [dict(entry) for entry in COMPARE_METRIC_CATALOG]
