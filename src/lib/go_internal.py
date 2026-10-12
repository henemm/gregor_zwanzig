"""Zentraler Python -> Go Sende-Helfer fuer interne Endpunkte (Issue #2159).

Rueckrichtung zu ADR-0062: der Core traegt das gemeinsame Geheimnis im Header
``X-GZ-Core-Auth``. EIN Ort fuer Basis-URL und Header, damit keine
Aufrufstelle beides selbst baut (oder vergisst).
"""
from __future__ import annotations

import logging
import os

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

CORE_AUTH_HEADER = "X-GZ-Core-Auth"


def go_api_url() -> str:
    """Wirksame Basis-URL der Go-API (Env, sonst Settings, Default :8090)."""
    return os.environ.get("GZ_GO_API_URL") or Settings().go_api_url


def _secret() -> str:
    # Wie api/main.py:_core_shared_secret(): Env zuerst, sonst Settings.
    return os.environ.get("GZ_CORE_SHARED_SECRET") or Settings().core_shared_secret or ""


def post_internal(path: str, json: dict, timeout: float = 5.0) -> httpx.Response:
    """POST an die interne Go-API. Ohne Secret wird NICHT gesendet (RuntimeError)."""
    secret = _secret()
    if not secret:
        logger.error(
            "GZ_CORE_SHARED_SECRET nicht gesetzt -- interner Aufruf %s wird nicht gesendet.",
            path,
        )
        raise RuntimeError("GZ_CORE_SHARED_SECRET nicht gesetzt")
    return httpx.post(
        go_api_url().rstrip("/") + path,
        json=json,
        headers={CORE_AUTH_HEADER: secret},
        timeout=timeout,
    )
