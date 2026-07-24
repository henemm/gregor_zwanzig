"""GPX Proxy endpoint — parses GPX file via existing Python pipeline.

Auth: user_id-Query-Param wird vom Go-Proxy aus der Session injiziert (Bug #1352).
Upload-Ziel ist user-scoped (`data/users/<user>/gpx/`), damit gilt: Uploads
verschiedener Nutzer können sich nicht gegenseitig überschreiben.
"""
import re
from datetime import date
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

router = APIRouter()

# Zweite Verteidigungslinie hinter dem Go-Proxy (Bug #1352): der Proxy verwirft
# client-gesetzte user_id-Werte und injiziert die Session-Kennung. Wird der
# Python-Core direkt erreicht, verhindert dieses Muster -- identisch zu dem, das
# die Go-Registrierung erzwingt (internal/handler/passkey.go) -- einen Ausbruch
# aus dem eigenen Nutzerordner ueber Pfadanteile wie ``../users/bob``.
_VALID_USER_ID = re.compile(r"^[a-zA-Z0-9_-]+$")


@router.post("/api/gpx/parse")
async def parse_gpx(
    file: UploadFile = File(...),
    user_id: str = Query(..., description="Session-User (vom Go-Proxy injiziert)"),
    stage_date: Optional[date] = Query(None),
    start_hour: int = Query(8, ge=0, le=23),
):
    from app.loader import get_data_dir
    from services.gpx_processing import gpx_to_stage_data

    # Vor jedem Pfadbau und vor jedem Schreibzugriff pruefen.
    if not _VALID_USER_ID.match(user_id):
        raise HTTPException(status_code=400, detail="invalid_user_id")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="no_file_content")

    upload_dir = get_data_dir(user_id) / "gpx"

    try:
        result = gpx_to_stage_data(
            content, file.filename, stage_date, start_hour, upload_dir=upload_dir,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result
