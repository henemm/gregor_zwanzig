"""Internal Read-Only Endpoints für Tooling/Validator (Issue #115).

Spec: docs/specs/modules/validator_internal_loaded_endpoint.md

Macht den Python-Loader-Output für den External Validator (Issue #110)
direkt beobachtbar. Nicht versionsstabil, nicht für Frontend/Endbenutzer.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

# Hinweis Modul-Duplikat (pythonpath enthaelt "src" UND "."): dieser Router
# importiert ``app.loader`` bewusst zweimal unter verschiedenen Namen. Der
# bestehende /loaded-Endpoint nutzt seit jeher die "src."-Variante (eigenes
# Modul-Objekt, eigenes ``_DATA_ROOT`` -- von ``tests/conftest.py::_isolate_data_root``
# NICHT gepatcht, siehe dortige Tests gegen echte data/users/default/). Der neue
# Stage-Weather-Endpoint braucht dagegen genau diese Isolation (Issue #1212
# RED-Tests speichern via `app.loader.save_trip`), daher die zweite, kurze
# Import-Variante fuer ``load_all_trips``.
from src.app.loader import load_all_trips as _legacy_load_all_trips, _trip_to_dict
from app.loader import load_all_trips
from providers.base import get_provider
from services.stage_weather import compute_stage_weather

router = APIRouter()


@router.get("/api/_internal/trip/{trip_id}/loaded")
async def loaded_trip(trip_id: str, user_id: str = Query(...)):
    """Liefert den hydrierten Trip als JSON, inklusive der vom Loader
    auto-injizierten ``display_config``. Kanonische Serialisierung via
    ``_trip_to_dict`` — Datetimes als ISO-Strings, Enums als ``.value``.
    """
    trip = next((t for t in _legacy_load_all_trips(user_id) if t.id == trip_id), None)
    if trip is None:
        raise HTTPException(
            status_code=404,
            detail=f"Trip {trip_id} nicht gefunden fuer User {user_id}",
        )
    return _trip_to_dict(trip)


def get_stage_weather_provider():
    """Default-Provider fuer den Stage-Weather-Endpoint (Issue #1212, Slice R1).

    ``get_provider("openmeteo")`` entspricht dem im Briefing-Pfad genutzten
    Standard-Provider (trip_report_scheduler.py) und respektiert
    GZ_TEST_FIXTURE_DIR (Offline-Test-Modus, FixtureProvider) -- Aufloesung
    erst zur Request-Zeit, nicht beim Modul-Import.
    """
    return get_provider("openmeteo")


@router.get("/api/_internal/trips/{trip_id}/stages-weather")
async def stages_weather(
    trip_id: str,
    user_id: str = Query(...),
    provider=Depends(get_stage_weather_provider),
):
    """Etappen-Wetter + Risiko fuer einen Trip (Issue #1212, Slice R1).

    Spiegelt den Go-Handler `StagesWeatherHandler` 1:1 im Response-Vertrag,
    nutzt aber die Python-RiskEngine als Single Source of Truth (ADR-0015).
    Read-only, keine Seiteneffekte.
    """
    try:
        trips = load_all_trips(user_id)
    except Exception:
        return JSONResponse(status_code=500, content={"error": "store_error"})

    trip = next((t for t in trips if t.id == trip_id), None)
    if trip is None:
        return JSONResponse(status_code=404, content={"error": "not_found"})

    try:
        results = compute_stage_weather(trip, provider)
    except Exception:
        # F001 (Adversary, Issue #1212): Last-Resort-Guard -- falls trotz der
        # Pro-Stage-Guards in compute_stage_weather doch etwas Unerwartetes
        # ausserhalb der Stage-Schleife bricht, darf der Request nicht mit
        # einem ungefangenen 500 crashen (AC-5).
        return JSONResponse(status_code=500, content={"error": "store_error"})
    return {"results": results}
