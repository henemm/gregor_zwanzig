"""ThrottleStore — gemeinsamer Cooldown-Speicher (Issue #1213).

Ersetzt sechs parallel implementierte Cooldown-Prüfungen und drei-plus
getrennte State-Dateien durch EINE Klasse mit EINEM State-File pro Nutzer
(``throttle_state.json``). Behebt vier latente Bugs: stiller Totalausfall
bei defektem Trip-Eintrag (heute reisst EIN kaputter Eintrag ALLE Trips mit),
gegenteilige `null`-Cooldown-Semantik zwischen Trip- und Compare-Pfad,
Lost-Update zwischen API-Prozess und Scheduler, fehlende Tageslimit-Prüfung
im Compare-Pfad.

SPEC: docs/specs/modules/throttle_store.md
"""
from __future__ import annotations

import fcntl
import json
import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("throttle_store")

_STATE_FILENAME = "throttle_state.json"
_LOCK_SUFFIX = ".lock"
_LEGACY_TRIP_FILE = "alert_throttle.json"
_LEGACY_COMPARE_FILE = "compare_alert_throttle.json"
_LEGACY_RADAR_FILE = "radar_alert_throttle.json"


class ThrottleStore:
    """Ein State-File pro Nutzer für alle Cooldown-Scopes.

    Scopes: ``trip``, ``radar``, ``compare_preset``. Struktur der Datei:
    ``{scope: {key: iso_timestamp}}``.
    """

    def __init__(self, user_id: str, data_dir: Optional[Path] = None) -> None:
        self._user_id = user_id
        if data_dir is not None:
            self._dir = Path(data_dir)
        else:
            from app.loader import get_data_dir
            self._dir = get_data_dir(user_id)
        self._path = self._dir / _STATE_FILENAME
        self._migrate_if_needed()

    # --- Public API ---

    def last_sent(self, scope: str, key: str) -> Optional[datetime]:
        data = self._load()
        return self._parse(data.get(scope, {}).get(key))

    def is_throttled(
        self, scope: str, key: str, cooldown_minutes: Optional[int], now: datetime
    ) -> bool:
        """Identisch zu `DeviationAlertEngine.is_cooldown_active` (falsy
        cooldown -> nicht gedrosselt), zusätzlich tz-Normalisierung des
        gespeicherten Werts (via `last_sent()`)."""
        if not cooldown_minutes:
            return False
        last = self.last_sent(scope, key)
        if last is None:
            return False
        return now - last < timedelta(minutes=cooldown_minutes)

    def record(self, scope: str, key: str, now: datetime) -> None:
        self._update(lambda data: data.setdefault(scope, {}).__setitem__(key, now.isoformat()))

    def clear(self, scope: str, key: str) -> None:
        def _op(data: dict) -> None:
            data.get(scope, {}).pop(key, None)
        self._update(_op)

    # --- Load / Write (atomar, reload-vor-write) ---

    def _load(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text())
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _write(self, data: dict) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self._dir), prefix=".throttle_state_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as f:
                f.write(json.dumps(data, indent=2))
            os.replace(tmp_name, self._path)
        except OSError:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
            raise

    def _update(self, mutate: Callable[[dict], None]) -> None:
        """Reload-merge-write unter einer Dateisperre: schützt vor Lost
        Updates zwischen zwei Prozessen (z.B. API + Scheduler) UND zwischen
        Threads desselben Prozesses. Die Sperre liegt auf einer Sidecar-Datei
        (``<state>.lock``), NICHT auf der Zieldatei selbst — `_write()`
        tauscht deren Inode per `os.replace`, ein Lock darauf würde nach dem
        Replace nichts mehr serialisieren. Reload + Mutate + Write finden
        komplett innerhalb der Sperre statt, damit kein zweiter Aufrufer
        dazwischen liest."""
        self._dir.mkdir(parents=True, exist_ok=True)
        lock_path = str(self._path) + _LOCK_SUFFIX
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                data = self._load()
                mutate(data)
                self._write(data)
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    @staticmethod
    def _parse(raw: object) -> Optional[datetime]:
        if not raw or not isinstance(raw, str):
            return None
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    # --- Migration (lazy, idempotent, beim ersten Zugriff pro Nutzer) ---

    def _migrate_if_needed(self) -> None:
        if self._path.exists():
            return  # bereits (mindestens einmal) migriert — kein Re-Merge
        migrated: dict = {}
        changed_trip = self._migrate_flat_file(_LEGACY_TRIP_FILE, "trip", migrated)
        changed_compare = self._migrate_flat_file(_LEGACY_COMPARE_FILE, "compare_preset", migrated)
        changed_radar = self._migrate_radar(migrated)
        if not (changed_trip or changed_compare or changed_radar):
            return

        def _merge_missing_only(data: dict) -> None:
            """Läuft innerhalb des `_update()`-Locks: schreibt jeden migrierten
            scope/key NUR, falls er im gerade (unter Lock) geladenen State
            noch fehlt. Schützt vor F002 — überschreibt niemals einen
            Eintrag, den ein paralleler `record()` bereits gesetzt hat, egal
            ob dieser vor oder nach der Migrations-Lesephase lief."""
            for scope, entries in migrated.items():
                bucket = data.setdefault(scope, {})
                for key, iso in entries.items():
                    bucket.setdefault(key, iso)

        self._update(_merge_missing_only)

    def _migrate_flat_file(self, filename: str, scope: str, data: dict) -> bool:
        """`{key: iso}`-Altdatei (Trip/Compare) -> `data[scope][key]`.

        Ein defekter Timestamp isoliert NUR seinen eigenen Eintrag (AC-2/AC-3)
        statt die gesamte Migration abzubrechen.
        """
        path = self._dir / filename
        if not path.exists():
            return False
        try:
            raw = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return False
        if not isinstance(raw, dict):
            return False
        changed = False
        bucket = data.setdefault(scope, {})
        for key, iso in raw.items():
            parsed = self._parse(iso)
            if parsed is None:
                continue  # korrupter Nachbar-Eintrag isoliert sich selbst
            bucket[key] = parsed.isoformat()
            changed = True
        return changed

    def _migrate_radar(self, data: dict) -> bool:
        """Radar-Konsolidierung: primäre Quelle ist der `alert_state`-Key
        `radar_throttle.reported_at` je Trip (Read-Only, #102 — die
        Alt-Datei wird nicht angefasst); Fallback ist die Legacy-Datei
        `radar_alert_throttle.json`. Bei Konflikt gewinnt der jüngere Wert."""
        candidates: dict[str, datetime] = {}

        alert_state_dir = self._dir / "alert_state"
        if alert_state_dir.is_dir():
            for f in sorted(alert_state_dir.glob("*.json")):
                try:
                    raw = json.loads(f.read_text())
                except (json.JSONDecodeError, OSError):
                    continue
                if not isinstance(raw, dict):
                    continue
                entry = raw.get("radar_throttle")
                if not isinstance(entry, dict):
                    continue
                parsed = self._parse(entry.get("reported_at"))
                if parsed is not None:
                    candidates[f.stem] = parsed

        legacy_path = self._dir / _LEGACY_RADAR_FILE
        if legacy_path.exists():
            try:
                legacy_raw = json.loads(legacy_path.read_text())
            except (json.JSONDecodeError, OSError):
                legacy_raw = {}
            if isinstance(legacy_raw, dict):
                for trip_id, iso in legacy_raw.items():
                    parsed = self._parse(iso)
                    if parsed is None:
                        continue
                    existing = candidates.get(trip_id)
                    if existing is None or parsed > existing:
                        candidates[trip_id] = parsed

        changed = False
        bucket = data.setdefault("radar", {})
        for trip_id, dt in candidates.items():
            bucket[trip_id] = dt.isoformat()
            changed = True
        return changed
