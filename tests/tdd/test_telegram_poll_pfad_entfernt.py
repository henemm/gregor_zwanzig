"""Rückbau des Telegram-Poll-Pfads (#1369).

Der Poll-Pfad (`getUpdates` mit rohem Bot-Token) lief an den Egress-Guards aus
#1363 vorbei und hatte seit der Webhook-Umstellung (#637) keinen Aufrufer.
Er ist entfernt; der Webhook-Eingang bleibt.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_endpoint_inbound_telegram_existiert_nicht(monkeypatch):
    """AC-1: POST /api/scheduler/inbound-telegram -> 404 (Route entfernt)."""
    from fastapi.testclient import TestClient

    from api.main import app

    monkeypatch.setenv("GZ_CORE_SHARED_SECRET", "tdd-1369")
    client = TestClient(app, headers={"X-GZ-Core-Auth": "tdd-1369"})

    resp = client.post("/api/scheduler/inbound-telegram")

    assert resp.status_code == 404, f"Endpoint existiert noch: {resp.status_code}"
    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/api/scheduler/inbound-telegram" not in paths


def test_reader_hat_keinen_poll_pfad():
    """AC-2: kein _get_updates / poll_and_process / _offset mehr."""
    from services.inbound_telegram_reader import InboundTelegramReader

    reader = InboundTelegramReader()
    for name in ("_get_updates", "poll_and_process", "_offset"):
        assert not hasattr(InboundTelegramReader, name), f"Klasse hat noch {name}"
        assert not hasattr(reader, name), f"Instanz hat noch {name}"

    # doc-compliance-test
    quelle = (REPO / "src/services/inbound_telegram_reader.py").read_text()
    assert "getUpdates" not in quelle


def test_webhook_eingang_bleibt():
    """AC-3 (Schutz): die Befehlsverarbeitung des Webhooks existiert weiter."""
    from services.inbound_telegram_reader import InboundTelegramReader

    assert callable(getattr(InboundTelegramReader, "_process_update", None))
    assert callable(getattr(InboundTelegramReader, "_process_start_command", None))


def test_doku_nennt_rueckbau():
    """AC-5: keine offene Rest-Lücke / kein Notfall-Fallback mehr in der Doku."""
    # doc-compliance-test
    egress = (REPO / "docs/specs/modules/egress_guard_telegram.md").read_text()
    webhook = (REPO / "docs/specs/modules/telegram_webhook_inbound.md").read_text()

    assert "Rest-Lücke `_get_updates`" not in egress
    assert "nicht löschen — Notfall-Fallback" not in webhook
    assert "Poll-Job reaktivieren" not in webhook
    assert "Poll-Job-Reaktivierung" not in webhook
    assert "#1369" in webhook
