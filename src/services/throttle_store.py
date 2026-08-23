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
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from services.file_lock import LOCK_TIMEOUT_SECONDS, acquire_exclusive

logger = logging.getLogger("throttle_store")

_STATE_FILENAME = "throttle_state.json"
_LOCK_SUFFIX = ".lock"
_LEGACY_TRIP_FILE = "alert_throttle.json"
_LEGACY_COMPARE_FILE = "compare_alert_throttle.json"
_LEGACY_RADAR_FILE = "radar_alert_throttle.json"


class ThrottleStore:
    """Ein State-File pro Nutzer für alle Cooldown-Scopes.

    Scopes und ihr Schlüsselraum:

    * ``trip`` — Trip-Kennung, Vorhersage-Änderungsalarm
    * ``radar`` — Trip-Kennung, Trip-Nowcast
    * ``compare_preset`` — Preset-Kennung, Vergleichs-Änderungsalarm
    * ``compare_radar`` — Preset-Kennung, Vergleichs-Nowcast (Issue #1467 S3).
      Bewusst ein EIGENER Scope: ``radar`` ist ausschließlich mit Trip-Kennungen
      belegt (seit dem #1250-Cutover liegen Trips und Ortsvergleiche im selben
      Verzeichnis und tragen frei gewählte Slugs — Kollision real möglich), und
      ``compare_preset`` ist vom Änderungsalarm auf demselben Preset-Schlüssel
      belegt; eine Wiederverwendung ließe die beiden Alarmarten einander
      gegenseitig unterdrücken.

    Struktur der Datei:
    ``{scope: {key: {"at": iso, "precip_mm": float|null, "urgency": str|null}}}``
    (Issue #2065, ``urgency`` seit #2050 S3c). Bestandseintraege im Alt-Format
    ``{scope: {key: iso}}`` und im #2065-Zwischenformat (ohne ``urgency``)
    bleiben lesbar.
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

    def last_sent_with_precip(
        self, scope: str, key: str
    ) -> tuple[Optional[datetime], Optional[float]]:
        """Zeitpunkt UND zuletzt gemeldete Menge (Issue #2065).

        Bewusst eine EIGENE Lesemethode statt einer Ueberladung von
        `last_sent()`: dessen 15+ Aufrufer erwarten ein `datetime`, nicht ein
        Paar. Bei einem Alt-Eintrag (reiner ISO-String, keine Mengenangabe)
        ist die Menge `None` — der Aufrufer entscheidet konservativ."""
        raw = self._load().get(scope, {}).get(key)
        return self._parse(raw), self._parse_precip(raw)

    def last_sent_with_urgency(
        self, scope: str, key: str
    ) -> tuple[Optional[datetime], Optional[str]]:
        """Zeitpunkt UND Dringlichkeit, mit der die Sperre gebucht wurde
        (Issue #2050 S3c).

        Schwester von `last_sent_with_precip()` und aus demselben Grund eine
        eigene Methode: die 15+ Aufrufer von `last_sent()` erwarten ein
        `datetime`, kein Paar. Bei einem Alt-Eintrag (reiner ISO-String) und
        bei einem #2065-Eintrag ohne Dringlichkeit ist der zweite Wert `None`
        — der Aufrufer entscheidet dann konservativ (kein Durchbruch)."""
        raw = self._load().get(scope, {}).get(key)
        return self._parse(raw), self._parse_urgency(raw)

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

    def record(
        self, scope: str, key: str, now: datetime,
        precip_mm: Optional[float] = None,
        urgency: Optional[str] = None,
    ) -> None:
        """Issue #2065/#2050 S3c: geschrieben wird ausschliesslich das neue
        Format `{"at": iso, "precip_mm": float|null, "urgency": str|null}`.
        Aufrufer ohne Mengenangabe (z.B. der Kurzfristhinweis im Briefing)
        bzw. ohne Dringlichkeit (der amtliche Zweig, `trip_alert.py:2480`)
        hinterlassen `null` — daraus entsteht spaeter keine Vergleichsbasis.

        `urgency` steht bewusst HINTER `precip_mm`: alle bestehenden Aufrufer
        uebergeben hoechstens drei Positionsargumente, ein Einschub davor
        verschoebe die Mengenangabe still."""
        eintrag = {
            "at": now.isoformat(),
            "precip_mm": float(precip_mm) if precip_mm is not None else None,
            "urgency": str(urgency) if urgency is not None else None,
        }
        self._update(lambda data: data.setdefault(scope, {}).__setitem__(key, eintrag))

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
        dazwischen liest.

        Fail-open GEZIELT nur für den Sperren-Timeout (`acquire_exclusive`,
        #1448 S2): wird die Sperre nicht innerhalb `LOCK_TIMEOUT_SECONDS`
        erworben, wird eine WARNING geloggt und der Schreibvorgang
        übersprungen, ohne zu werfen. Alle anderen Fehler (z.B. `mkdir`
        auf einem blockierten Pfad, IO-/JSON-Fehler) bleiben unverändert
        unbehandelt und propagieren wie vor dieser Scheibe — kein neues
        blanket `except Exception`."""
        self._dir.mkdir(parents=True, exist_ok=True)
        lock_path = str(self._path) + _LOCK_SUFFIX
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            start = time.monotonic()
            if not acquire_exclusive(fd, LOCK_TIMEOUT_SECONDS):
                # F003 (Adversary #1448 S2): geloggt wird die TATSAECHLICH
                # gewartete Zeit (`time.monotonic()`-Differenz), nicht die
                # konfigurierte Zeitgrenze -- sonst waere die Diagnosezeile
                # z.B. in Tests mit geschrumpfter Frist schlicht falsch.
                elapsed = time.monotonic() - start
                logger.warning(
                    "Dateisperre %s nicht innerhalb %.2fs erhalten -- "
                    "Schreibvorgang uebersprungen",
                    lock_path, elapsed,
                )
                return
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
        # Issue #2065: zwei Eintragsformen -- Bestandsdaten tragen den reinen
        # ISO-String, neue Eintraege ein Objekt mit `at` und `precip_mm`.
        if isinstance(raw, dict):
            raw = raw.get("at")
        if not raw or not isinstance(raw, str):
            return None
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    @staticmethod
    def _parse_precip(raw: object) -> Optional[float]:
        """Menge aus einem Eintrag — `None` fuer Alt-Eintraege (reiner
        String) und fuer neue Eintraege ohne Mengenangabe (Issue #2065)."""
        if not isinstance(raw, dict):
            return None
        wert = raw.get("precip_mm")
        if isinstance(wert, bool) or not isinstance(wert, (int, float)):
            return None
        return float(wert)

    @staticmethod
    def _parse_urgency(raw: object) -> Optional[str]:
        """Dringlichkeit aus einem Eintrag — `None` fuer Alt-Eintraege (reiner
        String), fuer #2065-Eintraege ohne das Feld und fuer bewusst ohne
        Dringlichkeit gebuchte Sperren (Issue #2050 S3c)."""
        if not isinstance(raw, dict):
            return None
        wert = raw.get("urgency")
        return wert if isinstance(wert, str) and wert else None

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
