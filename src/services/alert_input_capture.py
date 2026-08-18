"""Alarm-Eingangsprotokoll -- rollierender Mitschnitt des ROHEN
Eingangszustands jeder verarbeiteten Alarm-Meldung (Issue #1948, Scheibe S1).

Zweig a (Delta-Alarm): nutzerskopiert unter
``data/users/<user_id>/alert_input/`` (``capture_user_scoped()``). Zweig b
(amtliche Warnung)/c (Nowcast): System-Ablage unter
``data/debug/alert_input/<branch>/`` (``capture_system()``), Korrelation
mit ``alert_log`` ueber ``latest_capture_id()``.

SPEC: docs/specs/modules/alarm_eingangsprotokoll.md (AC-1..AC-9)

Fail-open (wie ``alert_log._append()``/``weather_snapshot.save_dated()``):
jeder Schreibvorgang faengt ALLE Exceptions, loggt eine Warnung, gibt
``None`` zurueck. Retention (Vorlage ``_prune_dated_snapshots``): pro
Verzeichnis bleiben nach jedem Schreiben nur die 50 juengsten Dateien.
"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.loader import VALID_USER_ID_RE, get_data_dir, get_data_root

logger = logging.getLogger("alert_input_capture")

_MAX_FILES_PER_DIR = 50
_UNSAFE_KEY_CHARS = re.compile(r"[^A-Za-z0-9_.-]+")


def _safe_key(value: str) -> str:
    """Macht einen beliebigen Quell-Schluessel dateinamen-tauglich."""
    return _UNSAFE_KEY_CHARS.sub("_", str(value))[:80] or "key"


def _prune(dir_path: Path) -> None:
    """Behaelt nur die ``_MAX_FILES_PER_DIR`` juengsten ``*.json``-Dateien."""
    files = sorted(dir_path.glob("*.json"), key=lambda p: (p.stat().st_mtime, p.name))
    for old_file in files[:-_MAX_FILES_PER_DIR]:
        try:
            old_file.unlink()
        except OSError as e:
            logger.warning("alert_input_capture: Bereinigung fehlgeschlagen (%s): %s", old_file, e)


def capture_user_scoped(
    user_id: str,
    *,
    entity_type: str,
    entity_id: str,
    payload: dict,
) -> Optional[str]:
    """Zweig a. Datei: data/users/<user_id>/alert_input/forecast_change_
    <entity_type>_<entity_id>_<timestamp>.json. ``user_id`` PFLICHT ohne
    Vorgabewert (kein stiller "default"-Fallback, Pruefung wie
    ``get_data_dir``). Rueckgabe: capture_id oder None (fail-open)."""
    try:
        if not VALID_USER_ID_RE.match(user_id):
            raise ValueError(f"invalid user_id: {user_id!r}")
        capture_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        record = {
            "capture_id": capture_id,
            "captured_at": now.isoformat(),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "payload": payload,
        }
        dir_path = get_data_dir(user_id) / "alert_input"
        filename = (
            f"forecast_change_{_safe_key(entity_type)}_{_safe_key(entity_id)}_"
            f"{now.strftime('%Y%m%dT%H%M%S%f')}.json"
        )
        dir_path.mkdir(parents=True, exist_ok=True)
        (dir_path / filename).write_text(json.dumps(record, indent=2))
        _prune(dir_path)
        return capture_id
    except Exception as e:
        logger.warning(
            "alert_input_capture.capture_user_scoped fehlgeschlagen fuer "
            "%s/%s (%s): %s", entity_type, entity_id, user_id, e,
        )
        return None


def capture_system(
    *,
    branch: str,
    source_key: str,
    payload: dict,
) -> Optional[str]:
    """Zweig b/c. Datei: data/debug/alert_input/<branch>/<source_key>_
    <timestamp>.json. Strukturell KEIN Header-/Request-/Auth-Parameter
    (AC-7) -- der Aufrufer kann keine Zugangsdaten uebergeben, die diese
    Funktion nicht entgegen nimmt. Rueckgabe: capture_id oder None
    (fail-open)."""
    try:
        capture_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        record = {
            "capture_id": capture_id,
            "captured_at": now.isoformat(),
            "branch": branch,
            "source_key": source_key,
            "payload": payload,
        }
        dir_path = get_data_root() / "debug" / "alert_input" / branch
        filename = f"{_safe_key(source_key)}_{now.strftime('%Y%m%dT%H%M%S%f')}.json"
        dir_path.mkdir(parents=True, exist_ok=True)
        (dir_path / filename).write_text(json.dumps(record, indent=2))
        _prune(dir_path)
        return capture_id
    except Exception as e:
        logger.warning(
            "alert_input_capture.capture_system fehlgeschlagen fuer %s/%s: %s",
            branch, source_key, e,
        )
        return None


def latest_capture_id(branch: str, source_key: str, *, max_age: float) -> Optional[str]:
    """Juengste capture_id fuer (branch, source_key), nicht aelter als
    max_age Sekunden -- Korrelations-Lookup fuer Zweig b/c (Zeitfenster =
    Cache-TTL des jeweiligen Zweigs). None, wenn nichts passt (fail-open)."""
    try:
        dir_path = get_data_root() / "debug" / "alert_input" / branch
        if not dir_path.exists():
            return None
        now = time.time()
        best: tuple[float, str] | None = None
        for f in dir_path.glob("*.json"):
            try:
                record = json.loads(f.read_text())
            except (OSError, ValueError):
                continue
            if record.get("source_key") != source_key:
                continue
            captured_at = record.get("captured_at")
            capture_id = record.get("capture_id")
            if not captured_at or not capture_id:
                continue
            try:
                captured_ts = datetime.fromisoformat(captured_at).timestamp()
            except ValueError:
                continue
            age = now - captured_ts
            if age < 0 or age > max_age:
                continue
            if best is None or captured_ts > best[0]:
                best = (captured_ts, capture_id)
        return best[1] if best else None
    except Exception as e:
        logger.warning(
            "alert_input_capture.latest_capture_id fehlgeschlagen fuer %s/%s: %s",
            branch, source_key, e,
        )
        return None
