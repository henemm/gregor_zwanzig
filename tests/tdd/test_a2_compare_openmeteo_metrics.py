"""
A2 (Epic #1301) — Ortsvergleich holt Wetterdaten ueberall ueber
get_provider("openmeteo") statt ueber die standort-basierte Provider-Auswahl
``_select_provider_for_location`` (die fuer Alpen-Orte direkt einen
GeoSphereProvider erzeugte und damit die Test-Fixture umging).

Kein ``live``-Marker: laeuft ueber die autouse-Fixture in tests/conftest.py,
die GZ_TEST_FIXTURE_DIR auf fixtures/openmeteo/ setzt. Netzfrei.

SPEC: docs/specs/modules/epic_1301_a2_compare_openmeteo.md
"""
from __future__ import annotations

from app.user import SavedLocation


def test_alps_location_gets_openmeteo_metrics_filled():
    """AC-1: Ein Alpen-Ort (Innsbruck) muss ueber den openmeteo-Fixture-Weg
    Werte fuer pop/uv/visibility/cape/freezing_level bekommen.

    Vor A2 rot: der Alpen-Zweig instanziiert direkt einen GeoSphereProvider
    und umgeht damit GZ_TEST_FIXTURE_DIR -> die Metriken bleiben leer bzw.
    der Fetch schlaegt fehl (result["error"] gesetzt).
    """
    from services.comparison_engine import fetch_forecast_for_location

    loc = SavedLocation(
        id="test-innsbruck-a2",
        name="Innsbruck",
        lat=47.2692,
        lon=11.4041,
        elevation_m=574,
    )

    result = fetch_forecast_for_location(loc, hours=48)

    assert result["error"] is None, (
        f"fetch_forecast_for_location lieferte einen Fehler: {result['error']}"
    )

    dps = result["raw_data"]
    assert dps, "raw_data ist leer — kein Datenpunkt vom Provider erhalten"

    assert any(dp.pop_pct is not None for dp in dps), (
        "pop_pct ist in allen Datenpunkten None — Alpen-Ort umgeht die "
        "openmeteo-Fixture (A2 noch nicht umgesetzt)"
    )
    assert any(dp.uv_index is not None for dp in dps), (
        "uv_index ist in allen Datenpunkten None — Alpen-Ort umgeht die "
        "openmeteo-Fixture (A2 noch nicht umgesetzt)"
    )
    assert any(dp.visibility_m is not None for dp in dps), (
        "visibility_m ist in allen Datenpunkten None — Alpen-Ort umgeht die "
        "openmeteo-Fixture (A2 noch nicht umgesetzt)"
    )
    assert any(dp.cape_jkg is not None for dp in dps), (
        "cape_jkg ist in allen Datenpunkten None — Alpen-Ort umgeht die "
        "openmeteo-Fixture (A2 noch nicht umgesetzt)"
    )
    assert any(dp.freezing_level_m is not None for dp in dps), (
        "freezing_level_m ist in allen Datenpunkten None — Alpen-Ort umgeht "
        "die openmeteo-Fixture (A2 noch nicht umgesetzt) oder FixtureProvider "
        "parst das Feld noch nicht"
    )


def test_select_provider_function_removed():
    """AC-2: Die standort-basierte Provider-Auswahl muss ersatzlos entfallen —
    der Vergleich holt ueberall openmeteo ueber get_provider("openmeteo").
    """
    import services.comparison_engine as ce

    assert not hasattr(ce, "_select_provider_for_location"), (
        "A2: standort-basierte Provider-Auswahl muss entfallen — Vergleich "
        "holt ueberall openmeteo"
    )
