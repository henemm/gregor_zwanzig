"""
Internal Telegram Webhook Endpoint — called by the Go gateway after secret-check.

The public, secret-protected entrypoint lives in Go
(`internal/handler/telegram_webhook.go`, route `/api/webhooks/telegram/{secret}`).
Go forwards the raw Telegram-Update body here. This endpoint reuses the existing
command processing (`InboundTelegramReader._process_update`) — no polling loop.

Runs on localhost:8000 (internal only, not exposed by Nginx).

SPEC: docs/specs/modules/telegram_webhook_inbound.md v1.0 (Issue #637)
"""
from __future__ import annotations

import logging
import os
import secrets
from collections import deque

from fastapi import APIRouter, Body, Header, HTTPException

from app.config import Settings

router = APIRouter(tags=["webhook"])
logger = logging.getLogger("telegram.webhook")

_reader = None

# In-memory dedup of already-seen update_ids (idempotency, AC-5).
# A seen-set — NOT a high-watermark — because Telegram update_ids are not
# strictly monotonic across our retry/forwarding path: a smaller update_id may
# legitimately arrive after a larger one. A watermark would falsely drop those.
# Persistence across process restarts is unnecessary: once the Go gateway
# returns 200 immediately, Telegram never resends a delivered update.
_MAX_SEEN = 1000
_seen_ids: set[int] = set()
_seen_order: deque[int] = deque(maxlen=_MAX_SEEN)


def _already_seen(update_id: int) -> bool:
    """True if update_id was processed before; otherwise records it and returns False."""
    if update_id in _seen_ids:
        return True
    if len(_seen_order) == _seen_order.maxlen:
        evicted = _seen_order[0]  # oldest, about to be pushed out by append
        _seen_ids.discard(evicted)
    _seen_order.append(update_id)
    _seen_ids.add(update_id)
    return False


@router.post("/api/internal/telegram-webhook")
def telegram_webhook(
    update: dict = Body(...),
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    """Verarbeitet ein einzelnes von Go weitergeleitetes Telegram-Update.

    Idempotent gegen Doppel-Zustellung (update_id-Dedup). Immer 200, auch bei
    Duplikat — verhindert Telegram-Retry-Sturm.

    Issue #2142 (AC-10, Defense in Depth): Das Telegram-Secret wird hier ein
    zweites Mal geprueft — die allgemeine Core-Auth-Pruefung in ``api/main.py``
    genuegt nicht, denn wer das gemeinsame Geheimnis kennt (jeder Prozess mit
    Lesezugriff auf die ``.env``), koennte sonst Kommandos fuer ein fremdes
    Konto ausloesen. Die Pruefung laeuft VOR dem Dedup: ein abgewiesener
    Request darf die ``update_id`` nicht verbrauchen.
    """
    global _reader
    from services.inbound_telegram_reader import InboundTelegramReader

    expected_telegram_secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
    if not expected_telegram_secret:
        # fail-closed, exakt wie internal/handler/telegram_webhook.go.
        raise HTTPException(status_code=503, detail="webhook not configured")
    if not secrets.compare_digest(
        x_telegram_bot_api_secret_token or "", expected_telegram_secret
    ):
        logger.warning("telegram-webhook: 403 — Telegram-Secret fehlt oder ist falsch (#2142)")
        raise HTTPException(status_code=403, detail="forbidden")

    update_id = update.get("update_id")
    if isinstance(update_id, int) and _already_seen(update_id):
        return {"status": "duplicate"}

    settings = Settings()
    if _reader is None:
        _reader = InboundTelegramReader()
    try:
        _reader._process_update(update, settings)
    except Exception as e:  # fail-soft: never make Telegram retry on our errors
        logger.error("telegram-webhook processing error (update_id=%s): %s", update_id, e)

    return {"status": "ok"}
