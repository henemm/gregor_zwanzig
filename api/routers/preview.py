"""Preview-Router für Email + SMS Vorschau (Epic #140, Option C).

Spec: docs/specs/modules/epic_140_output_vorschau.md

Endpoints:
- GET /api/preview/{trip_id}/email — liefert HTML-String der Vorschau
- GET /api/preview/{trip_id}/sms — liefert JSON {subject, token_line, char_count}

Auth: user_id-Query-Param wird vom Go-Proxy aus der Session injiziert (Bug #199).
Trip-Owner-Check: Loader-Pfad ist user-scoped (`data/users/<user>/briefings/<id>.json`,
Issue #1250 Cutover, ADR-0023), damit gilt: wer fremde user_id schickt, kommt nicht an
fremde Trips.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.config import Settings
from services.compare_preview_service import ComparePreviewService
from services.preview_service import PreviewService, VALID_REPORT_TYPES

router = APIRouter()


def _build_service(user_id: str) -> PreviewService:
    return PreviewService(Settings().with_user_profile(user_id))


@router.get("/api/preview/{trip_id}/email", response_class=HTMLResponse)
def preview_email(
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


@router.post("/api/preview/compare/{preset_id}")
def preview_compare(
    preset_id: str,
    user_id: str = Query(..., description="Session-User (vom Go-Proxy injiziert)"),
    date: str | None = Query(None, description="ISO-Datum, default: heute"),
):
    """Issue #1270: EIN Abruf, ALLE Kanaele (ADR-0011, Vorbild alert-preview).

    Liefert `{subject, email_html, telegram, sms, sms_char_count}` aus EINEM
    ComparisonEngine-Lauf — der Kanalwechsel im Vorschau-Tab braucht damit
    keinen weiteren Request (AC-7). `user_id` kommt wie bei den Trip-Routen aus
    dem Session-Kontext; der Preset-Loader ist user-scoped, ein fremdes Preset
    ist damit nicht aufloesbar (404, AC-6/ADR-0003).
    """
    try:
        return ComparePreviewService().render_all_channels(
            preset_id, user_id=user_id, target_date=date,
        )
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
def preview_telegram(
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


BRIEFING_KINDS = ("route", "vergleich")


@router.get("/api/briefings/{entity_id}/preview")
def preview_briefing(
    entity_id: str,
    kind: str = Query(..., description="route | vergleich (Pflicht, ADR-0023)"),
    user_id: str = Query(..., description="Session-User (vom Go-Proxy injiziert)"),
    type: str = Query("morning", description="morning | evening (nur route)"),
    date: str | None = Query(None, description="ISO-Datum"),
    demo: bool = Query(False, description="Issue #483: Fixture-Daten (nur route)"),
):
    """Issue #2283 S1: kind-neutrale Vorschau, EIN Abruf, ALLE Kanaele.

    Antwortform fuer beide kinds: `{subject, email_html, sms: {text,
    char_count}, telegram: {body, bubbles?}}`. `type`/`demo` gelten nur bei
    `kind=route`; der Vergleich kennt einen festen Berichtstyp und keine
    Demo-Daten. Beide Loader sind user-scoped (fremde ID -> 404, ADR-0003).
    """
    if kind not in BRIEFING_KINDS:
        raise HTTPException(status_code=400, detail="kind_required")
    if kind == "route" and type not in VALID_REPORT_TYPES:
        raise HTTPException(status_code=422, detail=f"Ungültiger type '{type}'")
    try:
        if kind == "route":
            return _build_service(user_id).render_all_channels(
                entity_id, user_id=user_id, report_type=type, target_date=date, demo=demo,
            )
        c = ComparePreviewService().render_all_channels(
            entity_id, user_id=user_id, target_date=date,
        )
        return {
            "subject": c["subject"],
            "email_html": c["email_html"],
            "sms": {"text": c["sms"], "char_count": c["sms_char_count"]},
            "telegram": {"body": c["telegram"]},
        }
    except (FileNotFoundError, LookupError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
