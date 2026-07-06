"""
TDD RED — Issue #1020 (Root Cause zu henemm-security#199): Playwright-
storage_state()-Dateien landen mit Modus 664 (world-readable) in /tmp, weil der
reale Login-Flow sie per einfachem `open(STATE_FILE, "w")` unter der Server-
umask 0002 schreibt. Jeder lokale Account auf dem Server kann das echte
gz_session-Cookie fuer staging.gregor20.henemm.com auslesen.

Spec: docs/specs/modules/fix_1020_tmp_cookie_perms.md

RED-Erwartung:
  - test_ac1_state_file_not_world_readable: schlaegt fehl, weil der reale
    Login-Flow aus test_702_alerts_mobile_parity._ensure_session_state() die
    Datei aktuell mit Modus 664 (Gruppe+Andere lesbar) schreibt.

Kein Mock: Es wird ein echter Playwright-Login gegen Staging durchgefuehrt (ueber
`test_issue_727_trips_null_safety._ensure_session_state()` — eine der 5 vom Fix
betroffenen Dateien) und die tatsaechlichen Dateirechte der real geschriebenen
Datei auf Disk geprueft.

Ausfuehrung:
    uv run pytest tests/tdd/test_issue_1020_tmp_cookie_perms.py -v
"""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_issue_727_trips_null_safety import STATE_FILE, _ensure_session_state  # noqa: E402


def _fresh_state_file() -> dict:
    """Erzwingt einen echten Neu-Login (kein Cache-Treffer), damit die Datei
    tatsaechlich frisch geschrieben wird."""
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
    return _ensure_session_state()


def test_ac1_state_file_not_world_readable():
    """AC-1: Eine neu geschriebene Session-State-Datei ist fuer Gruppe/Andere
    nicht zugreifbar (weder Lesen, Schreiben noch Ausfuehren)."""
    _fresh_state_file()
    assert os.path.exists(STATE_FILE), "Session-State-Datei wurde nicht geschrieben"

    mode = stat.S_IMODE(os.stat(STATE_FILE).st_mode)
    assert mode & 0o077 == 0, (
        f"Session-State-Datei {STATE_FILE} hat Modus {oct(mode)} — Gruppe "
        "und/oder Andere haben Zugriff auf ein echtes gz_session-Cookie fuer "
        "staging.gregor20.henemm.com (henemm-security#199 / Issue #1020)"
    )


def test_ac2_cached_state_still_readable_after_fix():
    """AC-2: Der bestehende Wiederverwendungs-Mechanismus (Login-Ersparnis durch
    Cache-Datei) funktioniert nach dem Rechte-Fix unveraendert weiter — ein
    zweiter Aufruf liest die zuvor geschriebene Datei zurueck, statt sich
    erneut einzuloggen."""
    first_state = _fresh_state_file()
    second_state = _ensure_session_state()

    first_cookies = {c["name"] for c in first_state.get("cookies", [])}
    second_cookies = {c["name"] for c in second_state.get("cookies", [])}

    assert "gz_session" in first_cookies
    assert first_cookies == second_cookies
