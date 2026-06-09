"""
e2e_telegram_live.py — Verankerung für funktionale Telegram-Live-Tests (Issue #686).

Dependency-arm: nur stdlib, läuft unter System-python3 ohne App-Deps (siehe #685-Lehre).

Zweck: Wenn ein Change den Telegram-Pfad berührt und GZ_TELEGRAM_TEST_CHAT_ID fehlt,
blockt dieser Hook das Close-Gate (Exit != 0). Ein SKIPPED im Telegram-Live-Pfad
zählt nicht als grün.
"""
from __future__ import annotations

import os
import sys


def gate(scope_touches_telegram: bool, env: dict) -> int:
    """Prüft ob der Telegram-Live-Test als bestanden gewertet werden darf.

    Args:
        scope_touches_telegram: True wenn der Change-Scope Telegram-Code berührt.
        env: Umgebungsvariablen (dict, z.B. dict(os.environ)).

    Returns:
        0  — bestanden oder sauberer Skip (Scope berührt Telegram nicht)
        1  — Nicht-bestanden (Telegram-Scope, aber kein Test-Chat konfiguriert)
    """
    if not scope_touches_telegram:
        # Sauberer Skip: Change berührt Telegram nicht → kein Live-Test nötig
        return 0

    chat_id = env.get("GZ_TELEGRAM_TEST_CHAT_ID", "").strip()
    if not chat_id:
        # Telegram-Scope berührt, aber kein Test-Chat-ID → Nicht-bestanden
        # SKIPPED zählt nicht als grün (AC-5)
        print(
            "ERROR: GZ_TELEGRAM_TEST_CHAT_ID ist nicht gesetzt.\n"
            "Der Change-Scope berührt Telegram. Ein SKIPPED Telegram-Live-Test\n"
            "gilt nicht als grün — bitte GZ_TELEGRAM_TEST_CHAT_ID setzen.",
            file=sys.stderr,
        )
        return 1

    # Token + Chat-ID vorhanden → Live-Test kann laufen (wird via pytest AC-4 ausgeführt)
    return 0


def _scope_touches_telegram(changed_files: list[str] | None = None) -> bool:
    """Heuristik: prüft ob geänderte Dateien den Telegram-Pfad berühren.

    Wird vom __main__-Block genutzt wenn keine explizite Liste übergeben wird.
    Liest geänderte Dateien aus argv oder git diff --name-only HEAD~1.
    """
    import subprocess

    if changed_files is None:
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            changed_files = result.stdout.splitlines()
        except Exception:
            changed_files = []

    telegram_patterns = ("telegram", "inbound_telegram", "trip_command_processor")
    for f in changed_files:
        f_lower = f.lower()
        if any(p in f_lower for p in telegram_patterns):
            return True
    return False


if __name__ == "__main__":
    # Standalone-Aufruf: python3 e2e_telegram_live.py [file1 file2 ...]
    files = sys.argv[1:] if len(sys.argv) > 1 else None
    touches = _scope_touches_telegram(files)
    rc = gate(scope_touches_telegram=touches, env=dict(os.environ))
    if rc != 0:
        print(f"FAIL: Telegram-Live-Gate nicht bestanden (Exit {rc})", file=sys.stderr)
    sys.exit(rc)
