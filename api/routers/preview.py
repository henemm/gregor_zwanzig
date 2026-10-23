"""Preview-Router: SMS-Kurzform-Vorschau (Epic #140, Option C).

Spec: docs/specs/modules/epic_140_output_vorschau.md

Endpoint:
- GET /api/preview/{trip_id}/sms — liefert JSON {subject, token_line, char_count}

Issue #1743 (PO-Entscheid 22.10.2026): die Briefing-Vorschau je Kanal ist
entfallen; damit sind GET /api/preview/{trip_id}/email, GET
/api/preview/{trip_id}/telegram und POST /api/preview/compare/{preset_id}
entfernt. /sms bleibt, weil die Staging-Specs damit die zugestellte
SMS-Kurzform messen.

Auth: user_id-Query-Param wird vom Go-Proxy aus der Session injiziert (Bug #199).
Trip-Owner-Check: Loader-Pfad ist user-scoped (`data/users/<user>/briefings/<id>.json`,
Issue #1250 Cutover, ADR-0023), damit gilt: wer fremde user_id schickt, kommt nicht an
fremde Trips.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.config import Settings
from services.preview_service import PreviewService, VALID_REPORT_TYPES

router = APIRouter()


def _build_service(user_id: str) -> PreviewService:
    return PreviewService(Settings().with_user_profile(user_id))


@router.get("/api/preview/{trip_id}/sms")
def preview_sms(
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
