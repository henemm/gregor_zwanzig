"""Issue #629 — Format-Modell auf Roh/Einfach reduzieren.

Datensichere Migration: persistiertes `format_mode in {scale, symbol}` wird beim
Laden auf None normalisiert (Rückfall auf default_format_mode der Metrik) +
use_friendly_format=True, sodass die effektive Darstellung bit-identisch bleibt.

Echte Load/Save-Roundtrips über loader.py — KEINE Mocks (CLAUDE.md).
SPEC: docs/specs/modules/issue_629_format_reduktion.md
"""
from app.loader import load_trip_from_dict, _trip_to_dict, _resolve_format_mode
from app.metric_catalog import get_metric


def _trip_with_modes(metric_entries):
    """Minimaler Trip-Dict mit display_config.metrics aus (id, format_mode, extra)."""
    metrics = []
    for entry in metric_entries:
        mc = {
            "metric_id": entry["metric_id"],
            "enabled": entry.get("enabled", True),
            "aggregations": entry.get("aggregations", ["min", "max"]),
            "use_friendly_format": entry.get("use_friendly_format", True),
        }
        if "format_mode" in entry:
            mc["format_mode"] = entry["format_mode"]
        for k in ("alert_enabled", "alert_threshold", "horizons",
                  "morning_enabled", "evening_enabled", "bucket", "order"):
            if k in entry:
                mc[k] = entry[k]
        metrics.append(mc)
    return {
        "trip": {
            "id": "t-629",
            "name": "Format-Test",
            "stages": [{
                "id": "S1", "name": "Tag 1", "date": "2026-06-10",
                "waypoints": [{"id": "W1", "name": "Start",
                               "lat": 47.0, "lon": 11.0, "elevation_m": 2000}],
            }],
            "display_config": {"metrics": metrics},
        }
    }


def _mc_by_id(trip, metric_id):
    for mc in trip.display_config.metrics:
        if mc.metric_id == metric_id:
            return mc
    raise AssertionError(f"Metric {metric_id} not in loaded display_config")


# ── AC-4: Migration normalisiert scale/symbol auf None, Darstellung unverändert ──

def test_ac4_scale_normalized_to_none():
    """wind_direction mit format_mode='scale' → nach Laden None + friendly True."""
    trip = load_trip_from_dict(_trip_with_modes([
        {"metric_id": "wind_direction", "format_mode": "scale"},
    ]))
    mc = _mc_by_id(trip, "wind_direction")
    assert mc.format_mode is None, "scale muss zu None normalisiert werden"
    assert mc.use_friendly_format is True


def test_ac4_symbol_normalized_to_none():
    """cloud_total mit format_mode='symbol' → nach Laden None + friendly True."""
    trip = load_trip_from_dict(_trip_with_modes([
        {"metric_id": "cloud_total", "format_mode": "symbol"},
    ]))
    mc = _mc_by_id(trip, "cloud_total")
    assert mc.format_mode is None, "symbol muss zu None normalisiert werden"
    assert mc.use_friendly_format is True


def test_ac3_effective_render_mode_unchanged_after_migration():
    """AC-3: Effektiver Darstellungs-Modus bleibt identisch (Default = scale/symbol)."""
    trip = load_trip_from_dict(_trip_with_modes([
        {"metric_id": "wind_direction", "format_mode": "scale"},
        {"metric_id": "cloud_total", "format_mode": "symbol"},
    ]))
    saved = _trip_to_dict(trip)["display_config"]["metrics"]
    saved_by_id = {m["metric_id"]: m for m in saved}
    # Resolver auf die GESPEICHERTE Form: muss den Metrik-Default liefern,
    # der genau scale/symbol IST → unveränderte Ausgabe.
    assert _resolve_format_mode(saved_by_id["wind_direction"], "wind_direction") \
        == get_metric("wind_direction").default_format_mode == "scale"
    assert _resolve_format_mode(saved_by_id["cloud_total"], "cloud_total") \
        == get_metric("cloud_total").default_format_mode == "symbol"


def test_ac4_kept_modes_untouched():
    """raw und simplified bleiben unverändert erhalten."""
    trip = load_trip_from_dict(_trip_with_modes([
        {"metric_id": "wind", "format_mode": "raw"},
        {"metric_id": "visibility", "format_mode": "simplified"},
    ]))
    assert _mc_by_id(trip, "wind").format_mode == "raw"
    assert _mc_by_id(trip, "visibility").format_mode == "simplified"


def test_ac4_other_fields_preserved_through_migration():
    """Alle übrigen MetricConfig-Felder überleben die scale/symbol-Normalisierung."""
    trip = load_trip_from_dict(_trip_with_modes([
        {
            "metric_id": "cloud_total", "format_mode": "symbol",
            "enabled": False, "aggregations": ["avg"],
            "alert_enabled": True, "alert_threshold": 42.0,
            "horizons": {"today": True, "tomorrow": False, "day_after": True},
            "morning_enabled": True, "evening_enabled": False,
        },
    ]))
    mc = _mc_by_id(trip, "cloud_total")
    assert mc.format_mode is None
    assert mc.enabled is False
    assert mc.aggregations == ["avg"]
    assert mc.alert_enabled is True
    assert mc.alert_threshold == 42.0
    assert mc.horizons == {"today": True, "tomorrow": False, "day_after": True}
    assert mc.morning_enabled is True
    assert mc.evening_enabled is False


# ── AC-5: Roundtrip load→save→load ohne Datenverlust, kein scale/symbol persistiert ──

def test_ac5_roundtrip_no_data_loss_and_no_legacy_mode_persisted():
    """load→save→load: nur format_mode normalisiert, sonst feld-identisch; kein
    scale/symbol mehr im serialisierten Dict."""
    src = _trip_with_modes([
        {"metric_id": "wind_direction", "format_mode": "scale",
         "enabled": True, "aggregations": ["avg"]},
        {"metric_id": "cloud_total", "format_mode": "symbol",
         "enabled": False, "aggregations": ["avg"], "alert_enabled": True,
         "alert_threshold": 7.0},
        {"metric_id": "wind", "format_mode": "raw", "aggregations": ["max"]},
    ])
    trip1 = load_trip_from_dict(src)
    serialized = _trip_to_dict(trip1)

    # Kein scale/symbol darf irgendwo persistiert sein.
    modes = [m.get("format_mode") for m in serialized["display_config"]["metrics"]]
    assert "scale" not in modes
    assert "symbol" not in modes

    # Zweiter Load: Felder müssen stabil bleiben (keine weitere Drift).
    trip2 = load_trip_from_dict({"trip": serialized})
    for mid in ("wind_direction", "cloud_total", "wind"):
        a, b = _mc_by_id(trip1, mid), _mc_by_id(trip2, mid)
        assert a.format_mode == b.format_mode
        assert a.enabled == b.enabled
        assert a.aggregations == b.aggregations
        assert a.alert_enabled == b.alert_enabled
        assert a.alert_threshold == b.alert_threshold

    # raw bleibt raw, scale/symbol wurden zu None.
    assert _mc_by_id(trip2, "wind").format_mode == "raw"
    assert _mc_by_id(trip2, "wind_direction").format_mode is None
    assert _mc_by_id(trip2, "cloud_total").format_mode is None
