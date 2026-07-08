"""
TDD RED für Issue #1079: Staging-Telegram-Webhook antwortet mit 401.

KEINE Mocks — echter, read-only Call gegen die Telegram Bot API
(getWebhookInfo) für den Staging-Bot. Nginx-Basic-Auth blockt den POST von
Telegram an den Webhook-Endpoint mit 401, obwohl der Go-Handler
(internal/handler/telegram_webhook.go) bereits eigenständig per
X-Telegram-Bot-Api-Secret-Token authentifiziert. Dieser Test muss JETZT
fehlschlagen (RED) — last_error_message zeigt den 401 — und erst nach der
Nginx-Location-Ausnahme in henemm-infra (analog /api/health) grün werden.

Live-Opt-in wie bei allen Telegram-Live-Tests (Issue #1014): ohne
GZ_TELEGRAM_LIVE=1 wird übersprungen, kein Secret wird ausgegeben.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from _telegram_live_fixture import live_telegram_enabled  # noqa: E402


@pytest.mark.skipif(
    not live_telegram_enabled(),
    reason="GZ_TELEGRAM_LIVE=1 nicht gesetzt oder Staging-Bot-Creds fehlen — Opt-in erforderlich",
)
def test_staging_telegram_webhook_has_no_401_error():
    """Given der Staging-Bot / When getWebhookInfo abgefragt wird / Then kein 401-Fehler."""
    token = os.environ["GZ_TELEGRAM_BOT_TOKEN"]
    resp = httpx.get(f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=10)
    resp.raise_for_status()
    result = resp.json()["result"]

    last_error = result.get("last_error_message")
    assert last_error is None, (
        f"Staging-Telegram-Webhook meldet einen Fehler: {last_error!r} "
        f"(url={result.get('url')!r}, pending_update_count={result.get('pending_update_count')}). "
        "Erwartete Ursache: Nginx-Basic-Auth blockt den POST mit 401 — Fix liegt in "
        "henemm-infra/nginx/staging.gregor20.henemm.com.conf (siehe #1079)."
    )
