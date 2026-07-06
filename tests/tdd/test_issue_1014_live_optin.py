"""
Issue #1014 — Live-Telegram-Tests nur opt-in (GZ_TELEGRAM_LIVE).

Root Cause: `test_issue_1001_telegram_bubbles.py` sourct beim Modul-**Import**
Staging-Telegram-Creds nach `os.environ` und öffnet damit für alle nachfolgend
importierten Live-Testdateien die `skipif`-Gates, ohne dass ein bewusstes
Opt-in stattgefunden hat. Ein breiter `pytest tests/tdd`-Lauf könnte dadurch
ungefragt echte Telegram-Nachrichten versenden.

Spec: docs/specs/modules/issue_1014_telegram_live_optin.md (AC-1..AC-4).

KEINE Mocks (Projektregel). AC-1 und AC-3 sind prozess-isoliert bewiesen
(subprocess), damit der `os.environ`-Zustand dieses Testprozesses selbst
nicht durch `GZ_TELEGRAM_LIVE` verfälscht wird.

SICHERHEIT: Jeder Subprocess-Lauf in dieser Datei bekommt zusätzlich zum
bereinigten Environment einen kaputten HTTP(S)-Proxy (127.0.0.1:1, nichts
lauscht dort) als Verteidigung-in-der-Tiefe — selbst falls ein `skipif`-Gate
(wie im Root-Cause-Bug) fälschlich offen wäre, kann dadurch KEIN Paket
`api.telegram.org` erreichen. Diese Datei importiert absichtlich die noch
nicht existierenden Funktionen `live_telegram_enabled()`, `load_staging_telegram_env()`
und `staging_live_settings()` aus `_telegram_live_fixture` — der resultierende
`ImportError` verhindert JEDE Testausführung (RED-Zustand), also auch jeden
Subprocess-Start, bis die Fixture-Funktionen implementiert sind.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.tdd._telegram_live_fixture import (
    live_telegram_enabled,
    staging_live_settings,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

_LIVE_TELEGRAM_TEST_FILES = [
    "tests/tdd/test_issue_686_telegram_functional_live.py",
    "tests/tdd/test_issue_650_telegram_foundation.py",
    "tests/tdd/test_issue_671_bot_menu_autoset.py",
    "tests/tdd/test_e2e_telegram_pipeline.py",
    "tests/tdd/test_952_onset_alert_e2e.py",
    "tests/tdd/test_issue_1001_telegram_bubbles.py",
]

# Unerreichbarer lokaler Proxy — jede echte HTTP(S)-Verbindung schlägt sofort
# mit ConnectError fehl, selbst wenn ein skipif-Gate fälschlich offen wäre.
_BLOCKED_PROXY = "http://127.0.0.1:1"


def _clean_subprocess_env() -> dict:
    """Environment ohne GZ_TELEGRAM_* + Netzwerk-Blockade (Defense-in-Depth)."""
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("GZ_TELEGRAM_"):
            del env[key]
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        env[key] = _BLOCKED_PROXY
    for key in ("NO_PROXY", "no_proxy"):
        env[key] = ""
    existing_pythonpath = env.get("PYTHONPATH", "")
    parts = [str(_REPO_ROOT), str(_REPO_ROOT / "src")]
    if existing_pythonpath:
        parts.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(parts)
    return env


# ---------------------------------------------------------------------------
# AC-1 — Opt-in-Pflicht: ohne GZ_TELEGRAM_LIVE werden ALLE Live-Tests
# übersprungen und os.environ bleibt unverändert.
# ---------------------------------------------------------------------------


def test_without_optin_all_live_tests_skip_and_env_unchanged(monkeypatch):
    # -- Teil A: direkter In-Process-Beweis für live_telegram_enabled() --
    for key in ("GZ_TELEGRAM_LIVE", "GZ_TELEGRAM_BOT_TOKEN", "GZ_TELEGRAM_TEST_CHAT_ID", "GZ_TELEGRAM_CHAT_ID"):
        monkeypatch.delenv(key, raising=False)

    before = {k: v for k, v in os.environ.items() if k.startswith("GZ_TELEGRAM_")}
    assert live_telegram_enabled() is False
    after = {k: v for k, v in os.environ.items() if k.startswith("GZ_TELEGRAM_")}
    assert before == after == {}, (
        "live_telegram_enabled() darf ohne GZ_TELEGRAM_LIVE=1 os.environ nicht veraendern"
    )

    # -- Teil B: isolierter Subprocess-pytest-Lauf ueber alle 6 Live-Dateien --
    env = _clean_subprocess_env()
    result = subprocess.run(
        [sys.executable, "-m", "pytest", *_LIVE_TELEGRAM_TEST_FILES, "-v"],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=240,
    )
    combined = result.stdout + result.stderr

    assert '"ok": true' not in combined and '"ok":true' not in combined, (
        "Ausgabe enthaelt eine echte Telegram-API-Erfolgsantwort — es duerfte "
        "KEINE echte Sendung stattgefunden haben:\n" + combined[-4000:]
    )
    assert "GZ_TELEGRAM_LIVE" in combined, (
        "Ohne Opt-in muessen die Skip-Gruende auf das zentrale GZ_TELEGRAM_LIVE-"
        "Gate verweisen (#1014) — heutige Skip-Gruende nennen stattdessen "
        "fehlende Creds, was implizites Opt-in ueber gesourcte .env-Dateien "
        "erlaubt:\n" + combined[-4000:]
    )


# ---------------------------------------------------------------------------
# AC-2 — Opt-in aktiv: GZ_TELEGRAM_LIVE=1 + vorhandene Staging-Creds
# fuehren zu True und sourcen os.environ genau in diesem Moment.
# ---------------------------------------------------------------------------


def test_with_optin_gate_returns_true_and_sources_env(monkeypatch):
    staging_env_path = Path("/home/hem/gregor_zwanzig_staging/.env")
    if not staging_env_path.exists():
        pytest.skip("gregor_zwanzig_staging/.env nicht vorhanden auf diesem Host")

    monkeypatch.setenv("GZ_TELEGRAM_LIVE", "1")
    monkeypatch.delenv("GZ_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("GZ_TELEGRAM_TEST_CHAT_ID", raising=False)
    assert "GZ_TELEGRAM_BOT_TOKEN" not in os.environ

    try:
        assert live_telegram_enabled() is True
        assert os.environ.get("GZ_TELEGRAM_BOT_TOKEN")
        assert os.environ.get("GZ_TELEGRAM_TEST_CHAT_ID")
    finally:
        monkeypatch.delenv("GZ_TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("GZ_TELEGRAM_TEST_CHAT_ID", raising=False)
        monkeypatch.delenv("GZ_TELEGRAM_CHAT_ID", raising=False)


# ---------------------------------------------------------------------------
# AC-3 — Kein Import-Nebeneffekt: reiner Modul-Import von test_issue_1001
# darf os.environ nicht um GZ_TELEGRAM_*-Keys veraendern.
# ---------------------------------------------------------------------------


def test_module_import_alone_sets_no_telegram_env_vars():
    env = _clean_subprocess_env()
    code = (
        "import tests.tdd.test_issue_1001_telegram_bubbles\n"
        "import os\n"
        "leaked = [k for k in os.environ if k.startswith('GZ_TELEGRAM_')]\n"
        "assert not leaked, leaked\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        "Reiner Import von test_issue_1001_telegram_bubbles setzt GZ_TELEGRAM_*-"
        "Keys in os.environ (Autoload-Bug #1014):\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# AC-4 — Kein CWD-.env-Token in Live-Sends: der fuer den Live-Send verwendete
# Settings-Token stammt explizit aus os.environ["GZ_TELEGRAM_BOT_TOKEN"].
# ---------------------------------------------------------------------------


def test_issue_671_live_send_uses_sourced_token_not_cwd_env(monkeypatch):
    monkeypatch.setenv("GZ_TELEGRAM_BOT_TOKEN", "fake-token-ac4")
    monkeypatch.setenv("GZ_TELEGRAM_TEST_CHAT_ID", "1")

    settings = staging_live_settings()

    assert settings.telegram_bot_token == os.environ["GZ_TELEGRAM_BOT_TOKEN"] == "fake-token-ac4"
