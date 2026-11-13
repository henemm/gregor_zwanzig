"""GPX Proxy endpoint — parses GPX file via existing Python pipeline.

Auth: user_id-Query-Param wird vom Go-Proxy aus der Session injiziert (Bug #1352).
Upload-Ziel ist user-scoped (`data/users/<user>/gpx/`), damit gilt: Uploads
verschiedener Nutzer können sich nicht gegenseitig überschreiben.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from api.fehler import api_fehler, api_fehler_aus

router = APIRouter()

# Issue #2961: Obergrenze je hochgeladener Datei. Gelesen wird hoechstens
# eine Einheit mehr, damit eine zu grosse Datei nie ganz im Speicher landet.
MAX_GPX_BYTES = 10 * 1024 * 1024
_READ_CHUNK = 1024 * 1024


async def _read_limited(file: UploadFile) -> bytes | None:
    """Dateiinhalt oder ``None``, wenn er ``MAX_GPX_BYTES`` ueberschreitet."""
    if file.size is not None and file.size > MAX_GPX_BYTES:
        return None
    teile: list[bytes] = []
    gelesen = 0
    while chunk := await file.read(_READ_CHUNK):
        gelesen += len(chunk)
        if gelesen > MAX_GPX_BYTES:
            return None
        teile.append(chunk)
    return b"".join(teile)

# Zweite Verteidigungslinie hinter dem Go-Proxy (Bug #1352): der Proxy verwirft
# client-gesetzte user_id-Werte und injiziert die Session-Kennung. Seit #1364
# prueft get_data_dir() zentral (und wirft ValueError); die Vorab-Pruefung hier
# bleibt bewusst stehen, damit der Endpoint sauber HTTP 400 statt 500 liefert.
# Muster-Quelle ist app.loader.VALID_USER_ID_RE (synchron zu
# internal/handler/passkey.go) — keine lokale Kopie mehr.


@router.post("/api/gpx/parse")
async def parse_gpx(
    file: UploadFile = File(...),
    user_id: str = Query(..., description="Session-User (vom Go-Proxy injiziert)"),
    stage_date: Optional[date] = Query(None),
    start_hour: int = Query(8, ge=0, le=23),
):
    from app.loader import get_data_dir, is_valid_user_id
    from services.gpx_processing import GpxSpeicherVoll, gpx_to_stage_data

    # Vor jedem Pfadbau und vor jedem Schreibzugriff pruefen (fullmatch, #2163).
    if not is_valid_user_id(user_id):
        raise HTTPException(status_code=400, detail="invalid_user_id")

    content = await _read_limited(file)
    if content is None:
        raise api_fehler(413, "gpx_zu_gross", user_id, max_mb=MAX_GPX_BYTES // (1024 * 1024))
    if not content:
        raise HTTPException(status_code=400, detail="no_file_content")

    upload_dir = get_data_dir(user_id) / "gpx"

    try:
        result = gpx_to_stage_data(
            content, file.filename, stage_date, start_hour, upload_dir=upload_dir,
        )
    except GpxSpeicherVoll as e:
        raise api_fehler_aus(e, 409, user_id)
    except ValueError as e:
        raise api_fehler_aus(e, 400, user_id)

    return result
