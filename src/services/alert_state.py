"""Alert-Melde-Gedächtnis (Issue #816, Epic #813 Slice 1).

Persistiert pro Entität (Trip, künftig auch Compare-Preset — Issue #1168),
welche Metrik/Segment-Abweichungen zuletzt per Alert gemeldet wurden — gegen
Wiederholungs-Spam. Mandantengetrennt unter
``data/users/<user_id>/alert_state/<entity_id>.json``. Trip übergibt
weiterhin `trip.id` als `entity_id` — bestehende `<trip_id>.json`-Dateien
bleiben unverändert gültig (reine interne Parameter-Umbenennung, Issue #1168).

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

# Issue #1460 (P2): Schlüsselraum der amtlichen Warnungen. Einzige Quelle für
# das Präfix — `official_alert_state_key()` (output/renderers/alert/
# official_alerts.py) baut seine Schlüssel damit, `reset()` schneidet daran.
OFFICIAL_ALERT_KEY_PREFIX = "official_alert:"


class AlertStateService:
    """Lädt/speichert/löscht das Alert-Melde-Gedächtnis pro Trip (mandantengetrennt)."""

    def __init__(self, user_id: str = "default") -> None:
        self._user_id = user_id
        # Issue #1265: get_data_dir() statt hartkodiertem "data/users/..." --
        # respektiert die pytest-Isolation (tests/conftest.py, #1133).
        from app.loader import get_data_dir

        self._state_dir = get_data_dir(user_id) / "alert_state"

    def _path(self, entity_id: str) -> Path:
        return self._state_dir / f"{entity_id}.json"

    def load(self, entity_id: str) -> dict:
        """Return the alert-state dict for an entity (empty dict if none/corrupt)."""
        path = self._path(entity_id)
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text())
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Corrupt alert_state for {entity_id}: {e}")
            return {}

    def save(self, entity_id: str, state: dict) -> None:
        """Persist the alert-state dict for an entity."""
        try:
            self._state_dir.mkdir(parents=True, exist_ok=True)
            self._path(entity_id).write_text(json.dumps(state, indent=2))
        except OSError as e:
            logger.error(f"Failed to save alert_state for {entity_id}: {e}")

    def reset(self, entity_id: str) -> None:
        """Setzt den ÄNDERUNGS-Raum des Melde-Gedächtnisses zurück. Idempotent.

        Issue #1460 (P2): Die amtlichen Warnungen (Schlüssel-Präfix
        ``official_alert:``, s. ``official_alert_state_key()``) haben ihre
        EIGENE Entprellung — sie überleben den Briefing-Versand. Vorher löschte
        der Reset die ganze Datei und damit auch sie; dieselbe, unveränderte
        amtliche Warnung galt danach wieder als „neu" und wurde nach jedem
        Briefing erneut gemeldet (B1).

        Bleibt nach dem Schnitt kein amtlicher Eintrag übrig, verschwindet die
        Datei wie bisher vollständig.
        """
        path = self._path(entity_id)
        try:
            if not path.exists():
                return
            kept = {
                key: value
                for key, value in self.load(entity_id).items()
                if key.startswith(OFFICIAL_ALERT_KEY_PREFIX)
            }
            if kept:
                self.save(entity_id, kept)
            else:
                path.unlink()
        except OSError as e:
            logger.warning(f"Failed to reset alert_state for {entity_id}: {e}")
