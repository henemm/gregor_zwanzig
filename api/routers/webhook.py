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
from collections import deque

from fastapi import APIRouter, Body

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
def telegram_webhook(update: dict = Body(...)):
    """Verarbeitet ein einzelnes von Go weitergeleitetes Telegram-Update.

    Idempotent gegen Doppel-Zustellung (update_id-Dedup). Immer 200, auch bei
    Duplikat — verhindert Telegram-Retry-Sturm.
    """
    global _reader
    from services.inbound_telegram_reader import InboundTelegramReader

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
