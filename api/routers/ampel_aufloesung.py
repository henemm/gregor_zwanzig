"""Ampel fuer Entwuerfe aufloesen: ``POST /api/ampel/aufloesung`` (Issue #2988 S2).

Spec: docs/specs/modules/rework_2988_ampel_ableitung.md. Zustandslos: gerechnet
wird allein in ``app.ampel.resolve_entwurf``; ``user_id`` (von Go aus der
Anmeldung) bestimmt nur die Sprache der Fehlertexte.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.ampel import resolve_entwurf
from i18n import resolve_user_lang, t

router = APIRouter(tags=["ampel"])

MAX_EINTRAEGE = 32


async def _rohtext(request: Request) -> bytes:
    return await request.body()


def _kein_json(wert: str) -> Any:
    raise ValueError(wert)  # NaN/Infinity nimmt json.loads sonst an, Go nicht


def _eintrag_ok(e: Any) -> bool:
    return (isinstance(e, dict)
            and all(e.get(k) is None or isinstance(e[k], str) for k in ("preset_name", "profil"))
            and (e.get("metrics") is None or isinstance(e["metrics"], list)))


def _eintraege(roh: bytes) -> list[dict] | None:
    """Eintraege des Rumpfs; ``None`` = Formfehler (auch zu tief verschachtelt)."""
    try:
        rumpf = json.loads(roh.decode("utf-8"), parse_constant=_kein_json)
    except (ValueError, RecursionError):
        return None
    liste = rumpf.get("eintraege") if isinstance(rumpf, dict) else None
    if not isinstance(liste, list) or len(liste) > MAX_EINTRAEGE:
        return None
    return liste if all(_eintrag_ok(e) for e in liste) else None


@router.post("/api/ampel/aufloesung")
def post_ampel_aufloesung(user_id: str = Query(..., min_length=1), roh: bytes = Depends(_rohtext)):
    """Je Eintrag ``{"vorlage_id", "ampel"}`` in gleicher Reihenfolge. Formfehler
    = 400 ``bad_request`` ohne Teilantwort; der Inhalt von ``ampel`` ist nie ein
    Fehler. Antwort direkt, ohne den rekursiven Encoder von FastAPI."""
    eintraege = _eintraege(roh)
    if eintraege is None:
        text = t("api.fehler.unbekannt", resolve_user_lang(user_id))
        return JSONResponse(status_code=400, content={"detail": text, "code": "bad_request"})
    return JSONResponse({"ergebnisse": [resolve_entwurf(e) for e in eintraege]})
