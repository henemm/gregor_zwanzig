"""Geteilter In-Process-Lock gegen doppelten manuellen Versand (#1756, #2124).

Modul-Ebene (nicht instanz-gebunden): pro Request entsteht eine neue
Service-Instanz, ein Instanzattribut wuerde nie mit sich selbst kollidieren.
Wirkt nur innerhalb eines Prozesses (siehe Spec #1756 "Known Limitations").

Der Schluessel enthaelt IMMER ``user_id`` (Mandantentrennung),
Trip: ``(user_id, trip_id, report_type)``, Compare: ``("compare", user_id, preset_id)``.
"""

from __future__ import annotations

import threading
from typing import Dict, Tuple

_send_locks: Dict[Tuple[str, ...], bool] = {}
_send_locks_guard = threading.Lock()


def try_acquire_send_lock(*key_parts: str) -> bool:
    with _send_locks_guard:
        if _send_locks.get(key_parts):
            return False
        _send_locks[key_parts] = True
        return True


def release_send_lock(*key_parts: str) -> None:
    with _send_locks_guard:
        _send_locks.pop(key_parts, None)
