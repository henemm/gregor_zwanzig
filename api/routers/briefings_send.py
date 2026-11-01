"""Kind-neutraler Handversand ``POST /api/briefings/{entity_id}/send`` (#2280).

Spec: docs/specs/modules/feat_2280_handversand_endpoint.md (AC-1..3, AC-9,
AC-10, AC-13)

Router ohne Prefix (wie ``preview.py``): der Go-Dispatcher reicht
``/api/briefings/{id}/send?kind=...&user_id=...`` durch. ``send_briefing`` ist
der EINE Helfer, den auch die Alt-Routen in ``scheduler.py`` rufen — die
Fehlerabbildung gibt es nur hier, ausschliesslich ueber ``send_outcomes``.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from i18n import resolve_user_lang
from services.scheduler_dispatch_service import send_compare_preset
from services.send_outcomes import SEND_OUTCOMES, error_body

router = APIRouter(tags=["briefings"])
logger = logging.getLogger("briefings_send")

_KINDS = ("route", "vergleich")


def _error(code: str, user_id: str, **values: str) -> JSONResponse:
    """Fehlerantwort in der Sprache des angemeldeten Nutzers (#2671)."""
    status, body = error_body(code, lang=resolve_user_lang(user_id), **values)
    return JSONResponse(status_code=status, content=body)


def _send_trip(entity_id: str, user_id: str, report_type: str):
    from app.config import Settings
    from app.loader import load_all_trips
    from services.trip_report_scheduler import TripReportSchedulerService

    trip = next((t for t in load_all_trips(user_id=user_id) if t.id == entity_id), None)
    if trip is None:
        return _error("not_found", user_id, entity_id=entity_id)
    if not trip.stages:
        return _error("no_stage", user_id, report_type=report_type)
    if not Settings().with_user_profile(user_id).can_send_email():
        return _error("smtp_not_configured", user_id)
    try:
        outcome = TripReportSchedulerService(user_id=user_id).send_test_report_outcome(
            trip, report_type,
        )
    except ValueError:
        return _error("invalid_report_type", user_id, report_type=report_type)
    if outcome in SEND_OUTCOMES:
        return _error(outcome, user_id, report_type=report_type)
    return {
        "status": "ok" if outcome == "sent" else outcome,
        "kind": "route", "id": entity_id, "sent": outcome == "sent",
        "report_type": report_type,
    }


def _send_vergleich(entity_id: str, user_id: str):
    try:
        result = send_compare_preset(user_id, entity_id)
    except KeyError:
        return _error("not_found", user_id, entity_id=entity_id)
    except ValueError as e:
        return _error("invalid_preset", user_id, reason=str(e))
    outcome = result.get("status")
    if outcome in SEND_OUTCOMES:
        return _error(outcome, user_id)
    fehlende = result.get("fehlende_orte")
    return {
        "status": outcome, "kind": "vergleich", "id": entity_id, "sent": outcome == "ok",
        **({"fehlende_orte": fehlende} if fehlende else {}),
    }


def send_briefing(kind: str, entity_id: str, user_id: str, report_type: str):
    """Handversand je ``kind``; Fehler als ``{"detail", "code"}`` (4xx/5xx).
    Jede unerwartete Ausnahme wird mit Traceback geloggt und als 500
    ``send_failed`` aus dem Vokabular gemeldet (AC-9) — auch fuer die Alt-Routen."""
    if kind not in _KINDS:
        return _error("kind_required", user_id)
    try:
        if kind == "route":
            return _send_trip(entity_id, user_id, report_type)
        return _send_vergleich(entity_id, user_id)
    except Exception:
        logger.exception("Handversand %s/%s (user %s) fehlgeschlagen", kind, entity_id, user_id)
        return _error("send_failed", user_id)


@router.post("/api/briefings/{entity_id}/send")
def send_briefing_endpoint(
    entity_id: str,
    user_id: str = Query(...),
    kind: str | None = Query(None),
    report_type: str = "morning",
):
    """Handversand fuer Trip (``kind=route``) und Ortsvergleich (``kind=vergleich``).
    ``user_id`` setzt der Go-Proxy aus der Anmeldung; ein Koerper wird ignoriert.
    Fehlendes ``kind`` ist 400 ``kind_required`` aus dem Vokabular (AC-2), nicht
    FastAPIs 422-Validierungsfehler."""
    return send_briefing(kind, entity_id, user_id, report_type)
