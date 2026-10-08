"""Epic #1539 S1a (Adversary F005): ``exclusive_lock(..., timeout_s=)`` wirkt.

Echter Sperrhalter (zweiter Deskriptor, flock im eigenen Thread), kein Mock.
"""
from __future__ import annotations

import fcntl
import os
import sys
import threading
import time
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from services import file_lock  # noqa: E402


def _halte(ziel: Path):
    halten, frei = threading.Event(), threading.Event()

    def lauf() -> None:
        fd = os.open(str(ziel) + ".lock", os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            halten.set()
            frei.wait(timeout=15)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    th = threading.Thread(target=lauf, daemon=True)
    th.start()
    assert halten.wait(timeout=5)
    return frei, th


@pytest.mark.timeout(20)
def test_timeout_s_verkuerzt_die_wartefrist_und_default_bleibt(monkeypatch, tmp_path):
    ziel = tmp_path / "x.json"
    monkeypatch.setattr(file_lock, "BRIEFING_LOCK_TIMEOUT_SECONDS", 3.0)
    frei, th = _halte(ziel)
    try:
        t0 = time.monotonic()
        with pytest.raises(file_lock.LockTimeout):
            with file_lock.exclusive_lock(ziel, timeout_s=0.2):
                pass
        assert time.monotonic() - t0 < 1.5, "timeout_s wurde ignoriert (Default-Frist abgewartet)"
        t0 = time.monotonic()
        with pytest.raises(file_lock.LockTimeout):
            with file_lock.exclusive_lock(ziel):
                pass
        assert time.monotonic() - t0 >= 2.5, "Default-Frist nicht mehr BRIEFING_LOCK_TIMEOUT_SECONDS"
    finally:
        frei.set()
        th.join(timeout=5)
