"""Internal Read-Only Endpoints für Tooling/Validator (Issue #115).

Spec: docs/specs/modules/validator_internal_loaded_endpoint.md

Macht den Python-Loader-Output für den External Validator (Issue #110)
direkt beobachtbar. Nicht versionsstabil, nicht für Frontend/Endbenutzer.
"""
from fastapi import APIRouter, HTTPException, Query

from src.app.loader import load_all_trips, _trip_to_dict

router = APIRouter()


@router.get("/api/_internal/trip/{trip_id}/loaded")
async def loaded_trip(trip_id: str, user_id: str = Query(...)):
    """Liefert den hydrierten Trip als JSON, inklusive der vom Loader
    auto-injizierten ``display_config``. Kanonische Serialisierung via
    ``_trip_to_dict`` — Datetimes als ISO-Strings, Enums als ``.value``.
    """
    trip = next((t for t in load_all_trips(user_id) if t.id == trip_id), None)
    if trip is None:
        raise HTTPException(
            status_code=404,
            detail=f"Trip {trip_id} nicht gefunden fuer User {user_id}",
        )
    return _trip_to_dict(trip)
