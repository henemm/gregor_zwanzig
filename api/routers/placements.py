"""Tabelle "Was steht wo" lesen: ``GET /api/briefings/{entity_id}/placements``
(Issue #3122 B2, Spec feat_3122_was_steht_wo Teil A Nr. 9).

Router ohne Prefix (wie ``briefings_send``): der Go-Dispatcher prueft Anmeldung
und Besitz, laedt das Abo und reicht ``?kind=...&user_id=...`` durch. Der Kern
liest das Abo erneut im Bestand DIESES Nutzers (fremd/unbekannt = 404) und baut
die Antwort in ``services.placements_view_service``. Geschrieben wird hier
nichts; die Schreibwege (PUT, Anlage) bedient Go allein.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse

from app.loader import InvalidUserIdError
from i18n import resolve_user_lang
from services.send_outcomes import error_body

router = APIRouter(tags=["briefings"])
logger = logging.getLogger("placements")


def _error(code: str, user_id: str, text_key: str | None = None,
           **values: str) -> JSONResponse:
    status, body = error_body(code, lang=resolve_user_lang(user_id),
                              text_key=text_key, **values)
    return JSONResponse(status_code=status, content=body)


@router.get("/api/briefings/{entity_id}/placements")
def get_briefing_placements(
    entity_id: str,
    user_id: str = Query(...),
    kind: str | None = Query(None),
):
    """Spalten, Zeilen, Beispielwerte, Marken, SMS-Beispiel, Ausblick und
    Legende der Tabelle; ``kind`` fehlt/unbekannt = 400 ``kind_required``."""
    from services.placements_view_service import (
        KINDS, AboNichtGefunden, build_placements_view,
    )

    if kind not in KINDS:
        return _error("kind_required", user_id)
    try:
        return build_placements_view(kind, entity_id, user_id)
    except (AboNichtGefunden, InvalidUserIdError):
        return _error("not_found", user_id, entity_id=entity_id)


@router.post("/api/briefings/placements/vorschau")
def post_placements_vorschau(
    user_id: str = Query(...),
    kind: str | None = Query(None),
    entwurf: Any = Body(None),
):
    """#3304: Ansicht der Tabelle fuer einen noch nicht angelegten Entwurf
    (Koerper), ``stored=false``, schreibt nichts, kein ETag. Entwurf kein
    lesbares Objekt = 422 ``invalid_preset``."""
    from services.placements_view_service import (
        KINDS, EntwurfUnlesbar, build_placements_preview,
    )

    if kind not in KINDS:
        return _error("kind_required", user_id)
    try:
        return build_placements_preview(kind, entwurf, user_id)
    except EntwurfUnlesbar:
        return _error("invalid_preset", user_id,
                      text_key="versand.vorschau.entwurf_unlesbar")


@router.get("/api/briefings/{entity_id}/placements/erstanlage")
def get_placements_erstanlage(
    entity_id: str,
    user_id: str = Query(...),
    kind: str | None = Query(None),
):
    """#3275/#3237: volle Tabelle eines frisch angelegten Abos aus seiner
    Grundauswahl (nur fuer die Go-Anlage, Trip und Orte):
    ``{"placements": {...}}``. Schreibt nichts."""
    from services.placements_view_service import (
        KINDS, AboNichtGefunden, erstanlage_placements,
    )

    if kind not in KINDS:
        return _error("kind_required", user_id)
    try:
        return erstanlage_placements(kind, entity_id, user_id)
    except (AboNichtGefunden, InvalidUserIdError):
        return _error("not_found", user_id, entity_id=entity_id)
