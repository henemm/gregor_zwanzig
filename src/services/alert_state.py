"""Alert-Melde-Gedächtnis (Issue #816, Epic #813 Slice 1).

Persistiert pro Trip, welche Metrik/Segment-Abweichungen zuletzt per Alert
gemeldet wurden — gegen Wiederholungs-Spam. Mandantengetrennt unter
``data/users/<user_id>/alert_state/<trip_id>.json``.

Schema (pro Datei):

    {
      "<metric>:<segment_id>": {
        "last_reported_value": <float>,
        "reported_at": "<ISO-8601>"
      },
      ...
    }

Reset beim Briefing-Versand (Scheduler) — danach vergleicht der nächste Alert
wieder gegen das frische Briefing.

SPEC: docs/specs/modules/issue_816_alert_deviation_core.md
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger("alert_state")


class AlertStateService:
    """Lädt/speichert/löscht das Alert-Melde-Gedächtnis pro Trip (mandantengetrennt)."""

    def __init__(self, user_id: str = "default") -> None:
        self._user_id = user_id
        self._state_dir = Path(f"data/users/{user_id}/alert_state")

    def _path(self, trip_id: str) -> Path:
        return self._state_dir / f"{trip_id}.json"

    def load(self, trip_id: str) -> dict:
        """Return the alert-state dict for a trip (empty dict if none/corrupt)."""
        path = self._path(trip_id)
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text())
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Corrupt alert_state for {trip_id}: {e}")
            return {}

    def save(self, trip_id: str, state: dict) -> None:
        """Persist the alert-state dict for a trip."""
        try:
            self._state_dir.mkdir(parents=True, exist_ok=True)
            self._path(trip_id).write_text(json.dumps(state, indent=2))
        except OSError as e:
            logger.error(f"Failed to save alert_state for {trip_id}: {e}")

    def reset(self, trip_id: str) -> None:
        """Clear the alert-state for a trip (remove file). Idempotent."""
        path = self._path(trip_id)
        try:
            if path.exists():
                path.unlink()
        except OSError as e:
            logger.warning(f"Failed to reset alert_state for {trip_id}: {e}")
