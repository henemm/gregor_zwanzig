"""AlertCheckStateStore — „zuletzt erreicht" je Trip fuer den Alarmlauf.

Epic #2261, Scheibe A-2 S1: ``check_all_trips`` prueft die Trips in der
Reihenfolge ihres letzten Erreichens (aelteste zuerst), damit ein Abbruch an
der Zeitgrenze nicht immer dieselben Trips auslaesst. Datei je Nutzer:
``data/users/<user_id>/alert_last_checked.json`` mit ``{trip_id: ISO-UTC}``.

Fail-open durchgaengig: ein Fehler hier schadet nur der Fairness des
naechsten Laufs, nie dem Versand.

SPEC: docs/specs/modules/fix_2261_a2s1_alarmlauf_reihenfolge.md
"""
from __future__ import annotations

import fcntl
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Iterable

from services.file_lock import LOCK_TIMEOUT_SECONDS, acquire_exclusive

logger = logging.getLogger("alert_check_state")

STATE_FILENAME = "alert_last_checked.json"


class AlertCheckStateStore:
    """Persistierte „zuletzt erreicht"-Stempel eines Nutzers."""

    def __init__(self, user_id: str, filename: str = STATE_FILENAME) -> None:
        from app.loader import get_data_dir

        self._dir = get_data_dir(user_id)
        self._filename = filename
        self._path = self._dir / filename

    def load(self, known_trip_ids: Iterable[str]) -> dict[str, datetime]:
        """Stempel der bekannten Trips; bei jedem Fehler leer + WARNING."""
        known = set(known_trip_ids)
        try:
            stamps = self._read()
        except (OSError, ValueError, TypeError, AttributeError) as e:
            logger.warning(f"{self._filename} unlesbar ({self._path}): {e} — Reihenfolge nach Trip-ID")
            return {}
        return {k: v for k, v in stamps.items() if k in known}

    def record(self, reached: dict[str, datetime], known_trip_ids: Iterable[str]) -> None:
        """Max-Merge der neuen Stempel, Prune unbekannter IDs, atomar
        schreiben. Lock-Timeout oder Schreibfehler ⇒ WARNING, kein Raise."""
        known = set(known_trip_ids)
        fd = None
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            lock_path = str(self._path) + ".lock"
            fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
            if not acquire_exclusive(fd, LOCK_TIMEOUT_SECONDS):
                logger.warning(f"{self._filename}: Sperre {lock_path} nicht erhalten — Stempel nicht gespeichert")
                return
            try:
                try:
                    merged = self._read()
                except (OSError, ValueError, TypeError, AttributeError):
                    merged = {}
                for trip_id, at in reached.items():
                    at = _aware(at)
                    if trip_id not in merged or at > merged[trip_id]:
                        merged[trip_id] = at
                merged = {k: v for k, v in merged.items() if k in known}
                self._write(merged)
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError as e:
            logger.warning(f"{self._filename} nicht geschrieben ({self._path}): {e}")
        finally:
            if fd is not None:
                os.close(fd)

    def _read(self) -> dict[str, datetime]:
        if not self._path.exists():
            return {}
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("kein JSON-Objekt")
        return {str(k): _aware(datetime.fromisoformat(v)) for k, v in raw.items()}

    def _write(self, stamps: dict[str, datetime]) -> None:
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self._dir), prefix=".alert_last_checked_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(json.dumps({k: v.isoformat() for k, v in sorted(stamps.items())}, indent=2))
            os.replace(tmp_name, self._path)
        except OSError:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
            raise


def _aware(at: datetime) -> datetime:
    return at if at.tzinfo is not None else at.replace(tzinfo=timezone.utc)


def sort_by_last_reached(units: list, stamps: dict, id_of, now_utc: datetime) -> None:
    """Aelteste „zuletzt erreicht"-Zeit zuerst, fehlender Stempel = aeltester,
    ID als Tie-Break (in place). EIN Baustein fuer alle Alarmlaeufe
    (Trip, Ortsvergleich; Epic #2261 A-2 S1/S2)."""
    units.sort(key=lambda u: (id_of(u) in stamps, stamps.get(id_of(u), now_utc), id_of(u)))
