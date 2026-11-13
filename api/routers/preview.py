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

from fastapi import APIRouter, Query

from api.fehler import api_fehler, api_fehler_aus, kontingent_erschoepft

from app.config import Settings
from services.forecast_budget import interaktiver_abruf
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
        raise api_fehler(422, "typ_ungueltig", user_id, type=type)
    service = _build_service(user_id)
    try:
        # Issue #2961 (ADR-0117): eine Vorschau ist ein interaktiver Ausloeser.
        # Lehnt das Kontingent einen Abruf ab, gibt es keine still
        # unvollstaendige Vorschau, sondern 429 mit Katalogtext.
        with interaktiver_abruf(user_id) as kontingent:
            subject, token_line = service.render_sms_preview(
                trip_id, user_id=user_id, report_type=type, target_date=date, demo=demo,
            )
        if kontingent.gedrosselt:
            raise kontingent_erschoepft(user_id)
        return {
            "subject": subject,
            "token_line": token_line,
            "char_count": len(token_line),
        }
    except (FileNotFoundError, LookupError) as e:
        raise api_fehler_aus(e, 404, user_id)
    except ValueError as e:
        raise api_fehler_aus(e, 422, user_id)
    except RuntimeError as e:
        raise api_fehler_aus(e, 503, user_id)
