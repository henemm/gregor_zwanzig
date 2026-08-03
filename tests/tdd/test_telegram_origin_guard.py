"""Issue #1476 — Telegram-Herkunftssperre.

Wiederholungsfall: ein Testlauf hat dem PO eine echte Telegram-Nachricht
geschickt. Die drei bestehenden Waechter (#1288/#1363) haengen ALLE an
`settings.is_test_mode` — ein Skript, das `Settings()` normal laedt (wie ein
Agent es aus einem Arbeitsordner typischerweise tut), laeuft mit
`is_test_mode=False`, `env="production"`, auch aus einem Arbeitsordner. Damit
schalten sich alle drei Waechter ab.

Der neue Schutz haengt am ORT, von dem der Code laeuft (`Path(__file__)`),
nicht an einem Schalter — s. `app.origin_guard`.

Boundary-Sink auf httpx.post (Vorbild test_telegram_test_mode_guard.py,
Issue #1288) — KEIN Live-Telegram, kein echter Bot-API-Call. Der Sink
beweist positiv wie negativ, ob ein POST stattgefunden haette.

Spec: docs/specs/fast/fix-1476-telegram-herkunftssperre.md
"""
from __future__ import annotations

import logging
from pathlib import Path

import httpx
import pytest

from app import origin_guard as origin_guard_mod
from app.config import Settings
from app.origin_guard import checkout_root, classify_origin
from output.channels import telegram as telegram_mod
from output.channels.base import OutputConfigError
from output.channels.telegram import TelegramOutput

PROD_CHAT_ID = "PROD_CHAT_ID_777"
STAGING_CHAT_ID = "STAGING_CHAT_ID_555"
TEST_CHAT_ID = "TEST_CHAT_ID_424242"


class _FakeBotApiResponse:
    status_code = 200
    text = '{"ok": true}'

    def __init__(self, message_id: int) -> None:
        self._message_id = message_id

    def json(self):
        return {"ok": True, "result": {"message_id": self._message_id}}


class _HttpxPostSink:
    """Zeichnet jeden httpx.post-Aufruf auf, antwortet wie eine wohlwollende
    Bot-API — beweist, ob ein POST stattfand UND mit welcher chat_id."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, url, json=None, timeout=None, **kwargs):
        self.calls.append({"url": url, "payload": json})
        return _FakeBotApiResponse(message_id=len(self.calls))


@pytest.fixture
def httpx_sink(monkeypatch) -> _HttpxPostSink:
    sink = _HttpxPostSink()
    monkeypatch.setattr(httpx, "post", sink)
    return sink


def _prod_style_settings(**overrides) -> Settings:
    """Normal geladene Konfiguration wie ein Skript sie ohne for_testing()/
    with_user_profile() erhaelt: is_test_mode=False, env='production'."""
    defaults = dict(
        telegram_bot_token="prod-bot-token",
        telegram_chat_id=PROD_CHAT_ID,
        telegram_test_chat_id=TEST_CHAT_ID,
    )
    defaults.update(overrides)
    settings = Settings(**defaults)
    assert settings.is_test_mode is False
    assert settings.env == "production"
    return settings


# ---------------------------------------------------------------------------
# AC-1 — der Aufruf, der heute (vor #1476) durchgeht
# ---------------------------------------------------------------------------


def test_ac1_test_origin_switches_away_from_prod_chat(httpx_sink):
    """GIVEN Code, das aus einem Arbeitsordner (Testlauf-Herkunft) laeuft,
    mit normal geladener Konfiguration / WHEN eine Telegram-Nachricht an die
    Produktions-Chat-ID abgeschickt wird / THEN geht KEINE Nachricht an
    diese ID — es wird auf die Test-Chat-ID umgeschaltet.

    Keine Herkunft wird hier gefaked: telegram.py laeuft real aus diesem
    Worktree, dessen Checkout-Wurzel weder Prod- noch Staging-Wurzel ist —
    genau der Fall, der den Schalter nicht setzt."""
    TelegramOutput(_prod_style_settings()).send("Betreff", "Testnachricht")

    calls = httpx_sink.calls
    assert len(calls) == 1
    assert calls[0]["payload"]["chat_id"] == TEST_CHAT_ID
    assert calls[0]["payload"]["chat_id"] != PROD_CHAT_ID


# ---------------------------------------------------------------------------
# AC-2 — keine Test-Chat-ID konfiguriert: harter Abbruch statt stillem Prod-Send
# ---------------------------------------------------------------------------


def test_ac2_missing_test_chat_id_hard_aborts_without_any_post(httpx_sink):
    """GIVEN dieselbe Lage, aber KEINE Test-Chat-ID konfiguriert / WHEN
    gesendet wird / THEN bricht der Versand mit OutputConfigError ab —
    statt still an den echten Empfaenger zu senden."""
    settings = _prod_style_settings(telegram_test_chat_id="")

    with pytest.raises(OutputConfigError, match="1476"):
        TelegramOutput(settings).send("Betreff", "Testnachricht")

    assert httpx_sink.calls == []


# ---------------------------------------------------------------------------
# AC-3 — echter Produktionsdienst bleibt unangetastet
# ---------------------------------------------------------------------------


def test_ac3_production_origin_delivers_unchanged(httpx_sink, monkeypatch):
    """GIVEN der echte Produktionsdienst (Code unter /home/hem/gregor_zwanzig)
    / WHEN eine Nachricht an die Produktions-Chat-ID geht / THEN wird sie
    UNVERAENDERT zugestellt. Da dieser Test nicht real aus dem Prod-Checkout
    laeuft, wird NUR die Konstante PROD_ROOT auf die eigene Checkout-Wurzel
    gefaked — die echte Klassifikationslogik (classify_origin) LAEUFT
    durch, statt nur eine vorgetaeuschte Rueckgabe zurueckzugeben."""
    monkeypatch.setattr(
        origin_guard_mod, "PROD_ROOT", checkout_root(Path(telegram_mod.__file__))
    )

    TelegramOutput(_prod_style_settings()).send("Betreff", "Prodnachricht")

    calls = httpx_sink.calls
    assert len(calls) == 1
    assert calls[0]["payload"]["chat_id"] == PROD_CHAT_ID


# ---------------------------------------------------------------------------
# AC-4 — Staging-Dienst bleibt unveraendert (eigener Bot, Test-Chat-ID)
# ---------------------------------------------------------------------------


def test_ac4_staging_origin_unaffected_by_new_guard(httpx_sink, monkeypatch):
    """GIVEN der Staging-Dienst (Code unter /home/hem/gregor_zwanzig_staging)
    / WHEN gesendet wird / THEN bleibt das heutige Verhalten unveraendert —
    der neue Guard greift NICHT zusaetzlich bei Herkunft='staging'. Wie bei
    AC-3 wird nur die Wurzel-Konstante (STAGING_ROOT) gefaked, die
    Klassifikationslogik selbst laeuft echt durch."""
    monkeypatch.setattr(
        origin_guard_mod, "STAGING_ROOT", checkout_root(Path(telegram_mod.__file__))
    )
    settings = _prod_style_settings(telegram_chat_id=STAGING_CHAT_ID)

    TelegramOutput(settings).send("Betreff", "Stagingnachricht")

    calls = httpx_sink.calls
    assert len(calls) == 1
    assert calls[0]["payload"]["chat_id"] == STAGING_CHAT_ID


# ---------------------------------------------------------------------------
# AC-5 — Umschaltung wird genau einmal protokolliert
# ---------------------------------------------------------------------------


def test_ac5_switch_logs_reason_and_target_chat_id_exactly_once(httpx_sink, caplog):
    """GIVEN eine Umschaltung hat stattgefunden / WHEN das Protokoll gelesen
    wird / THEN steht dort GENAU EINMAL eine Zeile mit Grund und
    Ziel-Chat-ID — eine stille Umleitung waere wieder ein blinder Fleck."""
    with caplog.at_level(logging.WARNING):
        TelegramOutput(_prod_style_settings()).send("Betreff", "Testnachricht")

    switch_logs = [
        r for r in caplog.records
        if "1476" in r.getMessage() and TEST_CHAT_ID in r.getMessage()
    ]
    assert len(switch_logs) == 1, (
        f"erwartet genau 1 Protokollzeile, gefunden: {[r.getMessage() for r in caplog.records]}"
    )


# ---------------------------------------------------------------------------
# Klassifikations-Logik (app.origin_guard) — insb. Worktree-Fallstrick
# ---------------------------------------------------------------------------


def test_classify_origin_exact_roots_only():
    """Nur EXAKT die bekannten Wurzeln zaehlen als production/staging.

    Kritischer Fall: ein Git-Worktree liegt PHYSISCH innerhalb der
    Prod-Wurzel (.claude/worktrees/<name>/...) — ein reiner Praefix- bzw.
    is_relative_to()-Vergleich wuerde ihn faelschlich als Produktion
    einstufen."""
    assert classify_origin(Path("/home/hem/gregor_zwanzig")) == "production"
    assert classify_origin(Path("/home/hem/gregor_zwanzig_staging")) == "staging"
    assert classify_origin(
        Path("/home/hem/gregor_zwanzig/.claude/worktrees/intake-1394")
    ) == "test"
    assert classify_origin(Path("/some/other/clone")) == "test"


def test_checkout_root_derives_from_channel_module_depth():
    """`<wurzel>/src/output/channels/<datei>.py` -> `<wurzel>`."""
    assert checkout_root(
        Path("/home/hem/gregor_zwanzig/src/output/channels/telegram.py")
    ) == Path("/home/hem/gregor_zwanzig")
    assert checkout_root(
        Path("/home/hem/gregor_zwanzig_staging/src/output/channels/email.py")
    ) == Path("/home/hem/gregor_zwanzig_staging")
