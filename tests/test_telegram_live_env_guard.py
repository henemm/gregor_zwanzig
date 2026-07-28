"""Guard gegen vorgesetzte Produktiv-Telegram-Creds beim Staging-Live-Testlauf.

Root Cause: `load_staging_telegram_env()` (tests/tdd/_telegram_live_fixture.py)
sourcte Staging-Creds bislang nur fuer Keys, die NICHT bereits in os.environ
standen. Wer vorher `GZ_TELEGRAM_BOT_TOKEN` exportiert hatte (z.B. aus einer
Worktree-.env, die eine Kopie der Produktiv-Konfiguration ist), sendete damit
unbemerkt mit dem Produktiv-Bot an die Staging-Chat-ID -- Telegram antwortet
dann mit `400 chat not found`, was wie ein Produktfehler aussieht, aber ein
Ausfuehrungsfehler ist.

Reine Umgebungslogik, kein Netzzugriff, keine echten Sends -- Kern-Schicht.
"""
from __future__ import annotations

import os

import pytest

from tests.tdd import _telegram_live_fixture as fixture

_STAGING_ENV_CONTENT = (
    "GZ_TELEGRAM_BOT_TOKEN=staging-bot-token-xyz\n"
    "GZ_TELEGRAM_CHAT_ID=1111\n"
    "GZ_TELEGRAM_TEST_CHAT_ID=2222\n"
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in ("GZ_TELEGRAM_BOT_TOKEN", "GZ_TELEGRAM_CHAT_ID", "GZ_TELEGRAM_TEST_CHAT_ID"):
        monkeypatch.delenv(key, raising=False)
    yield


def _point_at_staging_env(monkeypatch, tmp_path, content: str):
    staging_env = tmp_path / "staging.env"
    staging_env.write_text(content, encoding="utf-8")
    monkeypatch.setattr(fixture, "_STAGING_ENV_PATH", staging_env)
    return staging_env


def test_stale_override_aborts_with_command_and_staging_bot_hint(monkeypatch, tmp_path):
    """Vorgesetzter, abweichender Produktiv-Wert -> Abbruch statt stillem Weitermachen."""
    _point_at_staging_env(monkeypatch, tmp_path, _STAGING_ENV_CONTENT)
    monkeypatch.setenv("GZ_TELEGRAM_BOT_TOKEN", "prod-bot-token-abc")

    with pytest.raises(RuntimeError) as excinfo:
        fixture.load_staging_telegram_env()

    message = str(excinfo.value)
    assert "GZ_TELEGRAM_BOT_TOKEN" in message
    assert "sudo -n -u claude-gregor" in message
    assert "GZ_TELEGRAM_LIVE=1" in message
    assert "@GregorZwanzigStaging_bot" in message
    assert "2222" in message, "konkrete Staging-Chat-ID muss genannt werden"
    assert "prod-bot-token-abc" not in message, "Token darf nie in der Meldung landen"
    assert "staging-bot-token-xyz" not in message, "auch der Staging-Token nicht"


def test_matching_override_does_not_abort(monkeypatch, tmp_path):
    """Identischer vorgesetzter Wert ist kein Konflikt -- kein falscher Alarm."""
    _point_at_staging_env(monkeypatch, tmp_path, _STAGING_ENV_CONTENT)
    monkeypatch.setenv("GZ_TELEGRAM_BOT_TOKEN", "staging-bot-token-xyz")

    fixture.load_staging_telegram_env()

    assert os.environ["GZ_TELEGRAM_TEST_CHAT_ID"] == "2222"


def test_unreadable_staging_env_aborts_with_guidance_but_no_chat_id(monkeypatch, tmp_path):
    """Fehlende/unlesbare Staging-.env -> Abbruch mit Anleitung, ohne Chat-ID (nicht lesbar)."""
    missing_path = tmp_path / "does-not-exist" / "staging.env"
    monkeypatch.setattr(fixture, "_STAGING_ENV_PATH", missing_path)

    with pytest.raises(RuntimeError) as excinfo:
        fixture.load_staging_telegram_env()

    message = str(excinfo.value)
    assert "sudo -n -u claude-gregor" in message
    assert "GZ_TELEGRAM_LIVE=1" in message
    assert "@GregorZwanzigStaging_bot" in message
    assert "GZ_TELEGRAM_TEST_CHAT_ID" not in message


def test_no_prior_override_still_sources_all_wanted_keys(monkeypatch, tmp_path):
    """Unveraendertes Verhalten: ohne vorgesetzten Wert werden alle Keys gesourct."""
    _point_at_staging_env(monkeypatch, tmp_path, _STAGING_ENV_CONTENT)

    fixture.load_staging_telegram_env()

    assert os.environ["GZ_TELEGRAM_BOT_TOKEN"] == "staging-bot-token-xyz"
    assert os.environ["GZ_TELEGRAM_CHAT_ID"] == "1111"
    assert os.environ["GZ_TELEGRAM_TEST_CHAT_ID"] == "2222"
