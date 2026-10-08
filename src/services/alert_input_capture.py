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
``None`` zurueck. Retention (Issue #2218 Scheibe C, B2-71): je Quelle
(``source_key``) bleiben die Mitschnitte der letzten 24 h, die juengste je
Quelle immer; ein Gesamtdeckel je Verzeichnis (Dateizahl und Bytes) verdraengt
bei Ueberschreitung die aeltesten Dateien und meldet das per Warnung.
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

_MAX_AGE_SECONDS = 24 * 3600
_MAX_FILES_PER_DIR_TOTAL = 10000
_MAX_BYTES_PER_DIR = 256 * 1024 * 1024
_UNSAFE_KEY_CHARS = re.compile(r"[^A-Za-z0-9_.-]+")
# Dateiname ``{key}_{%Y%m%dT%H%M%S%f}.json``: Zeitstempel fest 21 Zeichen,
# daher ist der Key auch bei ``_`` im Key eindeutig abtrennbar.
_CAPTURE_NAME_RE = re.compile(r"^(.+)_\d{8}T\d{12}\.json$")


def _safe_key(value: str) -> str:
    """Macht einen beliebigen Quell-Schluessel dateinamen-tauglich."""
    return _UNSAFE_KEY_CHARS.sub("_", str(value))[:80] or "key"


def _unlink(path: Path) -> bool:
    try:
        path.unlink()
        return True
    except OSError as e:
        logger.warning("alert_input_capture: Bereinigung fehlgeschlagen (%s): %s", path, e)
        return False


def _prune(dir_path: Path) -> None:
    """Aufbewahrung je Key nach Alter (24 h, juengste je Key bleibt) plus
    Gesamtdeckel je Verzeichnis (Dateizahl/Bytes, aelteste zuerst)."""
    entries = []
    for p in dir_path.glob("*.json"):
        try:
            st = p.stat()
        except OSError:
            continue
        entries.append((st.st_mtime, p.name, st.st_size, p))
    entries.sort()
    cutoff = time.time() - _MAX_AGE_SECONDS
    newest_per_key: dict[str, str] = {}
    for mtime, name, _size, _p in entries:
        m = _CAPTURE_NAME_RE.match(name)
        if m:
            newest_per_key[m.group(1)] = name
    kept = []
    for entry in entries:
        mtime, name, _size, path = entry
        m = _CAPTURE_NAME_RE.match(name)
        if m and mtime < cutoff and newest_per_key.get(m.group(1)) != name:
            if _unlink(path):
                continue
        kept.append(entry)
    total_bytes = sum(e[2] for e in kept)
    removed = 0
    while kept and (len(kept) > _MAX_FILES_PER_DIR_TOTAL or total_bytes > _MAX_BYTES_PER_DIR):
        _mtime, _name, size, path = kept.pop(0)
        _unlink(path)
        total_bytes -= size
        removed += 1
    if removed:
        logger.warning(
            "alert_input_capture: Gesamtdeckel in %s griff, %d aelteste Datei(en) "
            "verdraengt (verbleibend %d Dateien, %d Bytes)",
            dir_path, removed, len(kept), total_bytes,
        )


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
        # Issue #2218 (Adversary F006): bei 24-h-Aufbewahrung nur die Dateien
        # DIESES Keys oeffnen -- Vorfilter per Dateinamen-Praefix, juengste
        # zuerst (Zeitstempel fester Laenge sortiert lexikalisch). Der
        # ``source_key`` im JSON wird weiter geprueft: ``_safe_key`` kuerzt,
        # zwei Keys koennen dasselbe Praefix tragen.
        prefix = _safe_key(source_key)
        candidates = sorted(
            (f for f in dir_path.glob("*.json")
             if (m := _CAPTURE_NAME_RE.match(f.name)) and m.group(1) == prefix),
            key=lambda f: f.name, reverse=True,
        )
        for f in candidates:
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
            # Dateiname und ``captured_at`` stammen aus demselben Zeitpunkt:
            # der erste gueltige Kandidat ist der juengste.
            return capture_id
        return None
    except Exception as e:
        logger.warning(
            "alert_input_capture.latest_capture_id fehlgeschlagen fuer %s/%s: %s",
            branch, source_key, e,
        )
        return None
