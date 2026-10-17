"""Merker "Erstes Briefing erhalten" (Issue #2521 S2, AC-12).

Schreibt ``data/users/<user_id>/first_briefing.json`` genau einmal beim ersten
planmaessig zugestellten Briefing (Trip oder Ortsvergleich). Eigene Datei:
Python schreibt ``user.json`` nirgends (kein Race mit dem Go-Merge-Schreiber).
Fail-soft: nie eine Ausnahme nach aussen.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger("first_briefing")

MARKER_FILE = "first_briefing.json"


def mark_first_briefing(user_id: str) -> None:
    """Setzt den Merker fuer ``user_id``, falls er noch fehlt (einmalig)."""
    try:
        from app.loader import get_data_dir

        if not user_id or user_id == "default":
            return
        pfad = get_data_dir(user_id) / MARKER_FILE
        if pfad.exists():
            return
        inhalt = {"first_briefing_at": datetime.now(timezone.utc).isoformat()}
        tmp = pfad.with_name(MARKER_FILE + ".tmp")
        tmp.write_text(json.dumps(inhalt), encoding="utf-8")
        os.replace(tmp, pfad)
    except Exception as exc:  # noqa: BLE001 -- fail-soft, Versand darf nie scheitern
        logger.warning("first_briefing nicht geschrieben (%s): %s", user_id, exc)
