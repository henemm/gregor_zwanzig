"""TDD: Issue #1077 — Telegram-Test-Leak fixen.

Spec: docs/specs/modules/issue_1077_telegram_test_chat_isolation.md
Issue: #1077

Root Cause: with_user_profile() ueberschreibt telegram_chat_id bedingungslos
aus dem Nutzerprofil, auch fuer Test-Nutzer/Staging (force_test=True). Dadurch
landet ein Test-Telegram-Versand im ECHTEN Chat des Profils statt im
Stalwart-Test-Chat.

Keine Mocks. Echte Settings-Roundtrip-Tests gegen ein temporaeres data/-Verzeichnis.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestIssue1077TelegramTestChatIsolation:

    def test_test_user_telegram_forced_to_test_chat_not_profile_chat(self, tmp_path, monkeypatch):
        """AC-1: Given ein Test-Nutzer mit realer telegram_chat_id im Profil,
        When with_user_profile() aufgerufen wird, Then wird telegram_chat_id
        auf telegram_test_chat_id gezwungen statt auf die Profil-Chat-ID."""
        sys.path.insert(0, str(REPO_ROOT / "src"))
        from app.config import Settings

        user_dir = tmp_path / "data" / "users" / "tg-live-e2e"
        user_dir.mkdir(parents=True)
        (user_dir / "user.json").write_text(
            json.dumps({
                "id": "tg-live-e2e",
                "is_test_user": True,
                "telegram_chat_id": "8346977700",
            }),
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        s = Settings(env="staging", telegram_test_chat_id="TESTCHAT999", telegram_chat_id="realdefault")
        result = s.with_user_profile("tg-live-e2e")

        assert result.telegram_chat_id == "TESTCHAT999", \
            f"Test-Nutzer muss auf Test-Chat geroutet werden, war {result.telegram_chat_id!r}"
        assert result.telegram_chat_id != "8346977700", \
            "Test-Nutzer darf NIE die echte Profil-Chat-ID nutzen (Leak, Issue #1077)"

    def test_real_user_telegram_still_taken_from_profile(self, tmp_path, monkeypatch):
        """AC-2: Given ein echter Nutzer (kein Test-Nutzer, keine Staging-Umgebung),
        When with_user_profile() aufgerufen wird, Then bleibt telegram_chat_id
        wie bisher aus dem Profil uebernommen."""
        sys.path.insert(0, str(REPO_ROOT / "src"))
        from app.config import Settings

        user_dir = tmp_path / "data" / "users" / "henning"
        user_dir.mkdir(parents=True)
        (user_dir / "user.json").write_text(
            json.dumps({
                "id": "henning",
                "telegram_chat_id": "REALCHAT",
            }),
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        s = Settings(env="production", telegram_test_chat_id="TESTCHAT999")
        result = s.with_user_profile("henning")

        assert result.telegram_chat_id == "REALCHAT", \
            f"Echter Nutzer muss weiterhin die Profil-Chat-ID erhalten, war {result.telegram_chat_id!r}"
