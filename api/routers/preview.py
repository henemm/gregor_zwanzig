"""Preview-Router für Email + SMS Vorschau (Epic #140, Option C).

Spec: docs/specs/modules/epic_140_output_vorschau.md

Endpoints:
- GET /api/preview/{trip_id}/email — liefert HTML-String der Vorschau
- GET /api/preview/{trip_id}/sms — liefert JSON {subject, token_line, char_count}

Auth: user_id-Query-Param wird vom Go-Proxy aus der Session injiziert (Bug #199).
Trip-Owner-Check: Loader-Pfad ist user-scoped (`data/users/<user>/trips/<id>.json`),
damit gilt: wer fremde user_id schickt, kommt nicht an fremde Trips.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from src.app.config import Settings
from src.services.preview_service import PreviewService, VALID_REPORT_TYPES

router = APIRouter()


def _build_service(user_id: str) -> PreviewService:
    return PreviewService(Settings().with_user_profile(user_id))


@router.get("/api/preview/{trip_id}/email", response_class=HTMLResponse)
async def preview_email(
    trip_id: str,
    user_id: str = Query(..., description="Session-User (vom Go-Proxy injiziert)"),
    type: str = Query("morning", description="morning | evening"),
    date: str | None = Query(None, description="ISO-Datum, default: nächste Stage"),
    demo: bool = Query(False, description="Issue #483: Fixture-Daten statt Live-API"),
):
    if type not in VALID_REPORT_TYPES:
        raise HTTPException(status_code=422, detail=f"Ungültiger type '{type}'")
    service = _build_service(user_id)
    try:
        html = service.render_email_preview(
            trip_id, user_id=user_id, report_type=type, target_date=date, demo=demo,
        )
        return HTMLResponse(content=html)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/api/preview/{trip_id}/sms")
async def preview_sms(
    trip_id: str,
    user_id: str = Query(...),
    type: str = Query("morning"),
    date: str | None = Query(None),
    demo: bool = Query(False, description="Issue #483: Fixture-Daten statt Live-API"),
):
    if type not in VALID_REPORT_TYPES:
        raise HTTPException(status_code=422, detail=f"Ungültiger type '{type}'")
    service = _build_service(user_id)
    try:
        subject, token_line = service.render_sms_preview(
            trip_id, user_id=user_id, report_type=type, target_date=date, demo=demo,
        )
        return {
            "subject": subject,
            "token_line": token_line,
            "char_count": len(token_line),
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


def _narrow_payload(subject: str, body: str, bubbles: list[str] | None = None) -> dict:
    """JSON-Antwort für Signal/Telegram-Vorschau (Issue #363, #1001 additiv)."""
    payload = {
        "subject": subject,
        "body": body,
        "char_count": len(body),
        "max_line_width": max(
            (len(line) for line in body.splitlines()), default=0,
        ),
    }
    if bubbles is not None:
        payload["bubbles"] = bubbles
    return payload


@router.get("/api/preview/{trip_id}/telegram")
async def preview_telegram(
    trip_id: str,
    user_id: str = Query(...),
    type: str = Query("morning"),
    date: str | None = Query(None),
    demo: bool = Query(False, description="Issue #483: Fixture-Daten statt Live-API"),
):
    if type not in VALID_REPORT_TYPES:
        raise HTTPException(status_code=422, detail=f"Ungültiger type '{type}'")
    service = _build_service(user_id)
    try:
        subject, body, bubbles = service.render_telegram_preview(
            trip_id, user_id=user_id, report_type=type, target_date=date, demo=demo,
        )
        return _narrow_payload(subject, body, bubbles)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
