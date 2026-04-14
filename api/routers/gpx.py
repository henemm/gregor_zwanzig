"""GPX Proxy endpoint — parses GPX file via existing Python pipeline."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

router = APIRouter()


@router.post("/api/gpx/parse")
async def parse_gpx(
    file: UploadFile = File(...),
    stage_date: Optional[date] = Query(None),
    start_hour: int = Query(8, ge=0, le=23),
):
    from src.web.pages.trips import gpx_to_stage_data

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="no_file_content")

    try:
        result = gpx_to_stage_data(content, file.filename, stage_date, start_hour)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result
