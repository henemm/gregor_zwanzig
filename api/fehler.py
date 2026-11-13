"""Fehlerantworten in der Sprache des Nutzers mit stabilem ``code`` (Issue #2674).

Antwortform: ``{"detail": "<Text in Kontosprache>", "code": "<code>"}``; ``detail``
bleibt ein String (rueckwaertskompatibel). Die Sprache kommt aus der ``user_id``
des Aufrufs (vom Go-Proxy aus der Sitzung); ohne Nutzer gilt Deutsch, nie ein
Rueckfall auf ``"default"``.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from i18n import resolve_user_lang, t

#: Code fuer Ausnahmen ohne eigenen Code. Issue #2961: deren Text kann
#: Interna (Pfade, Hostnamen) tragen -- nach aussen geht nur der Katalogtext
#: ``api.fehler.unbekannt``, der Ausnahmetext landet im Log.
UNBEKANNT = "unbekannt"

logger = logging.getLogger(__name__)


class ApiFehler(HTTPException):
    """HTTPException mit zusaetzlichem stabilem ``code``."""

    def __init__(self, status_code: int, detail: str, code: str) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.code = code


def _lang(nutzer: str | None):
    return resolve_user_lang(nutzer) if nutzer else "de"


def api_fehler(status: int, code: str, nutzer: str | None, **params: object) -> ApiFehler:
    """Fehler ``code`` mit Text ``api.fehler.<code>`` in der Sprache von ``nutzer``."""
    return ApiFehler(status, t(f"api.fehler.{code}", _lang(nutzer), **params), code)


def meldung_aus(exc: Exception, nutzer: str | None) -> str:
    """Lokalisierter Text einer ``fehler_mit_code``-Ausnahme, sonst Katalogtext."""
    code = getattr(exc, "code", None)
    if not isinstance(code, str):
        logger.warning("Fehler ohne Code an Client gemeldet (%s): %s", type(exc).__name__, exc)
        return t(f"api.fehler.{UNBEKANNT}", _lang(nutzer))
    return t(f"api.fehler.{code}", _lang(nutzer), **getattr(exc, "params", {}))


def api_fehler_aus(exc: Exception, status: int, nutzer: str | None) -> ApiFehler:
    """ApiFehler aus einer Dienst-Ausnahme; ohne ``.code`` mit Katalogtext."""
    code = getattr(exc, "code", None)
    return ApiFehler(status, meldung_aus(exc, nutzer), code if isinstance(code, str) else UNBEKANNT)


def register_fehler_handler(app: FastAPI) -> None:
    """Antwortet auf ``ApiFehler`` mit ``detail`` und ``code``."""

    @app.exception_handler(ApiFehler)
    async def _antwort(_request: Request, exc: ApiFehler) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code,
                            content={"detail": exc.detail, "code": exc.code},
                            headers=getattr(exc, "headers", None))
