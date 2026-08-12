"""BriefingSlotStore — Idempotenz-Vermerk je (trip_id, ortstag, slot) (#1725).

SPEC: docs/specs/modules/fix_1725_faelligkeit_und_idempotenz.md
ADR-0051 (Idempotenz-Schluessel), ADR-0044 (Kalendertag folgt der Ortszeit)

Eigener Speicher ``data/users/<uid>/briefing_slots.json`` statt Wiederverwendung
von ``briefing_log.json`` (dort sind Eintraege ohne Kanaele verboten, #1007 F001)
oder ``throttle_state.json`` (Cooldown-Fenster, kein Slot-Schluessel).

Schreibmuster wie ``throttle_store._update()``: Sidecar-Sperre ueber
``services.file_lock.acquire_exclusive`` plus ``tempfile``+``os.replace``.

🔴 Fehlerrichtung UMGEKEHRT zum Vorbild: ``throttle_store`` ueberspringt bei
Sperren-Timeout still den Schreibvorgang (fail-open) — dort kostet das einen
doppelten Hinweis. Hier heisst "nicht geschrieben" Doppelversand an echte
Empfaenger inklusive kostenpflichtiger Premium-SMS, also fail-closed:
:meth:`BriefingSlotStore.reserve` liefert ohne Sperre ``False``, und der
Aufrufer sendet dann NICHT (AC-13).
"""
from __future__ import annotations

import fcntl
import json
import logging
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from services import file_lock
from services.file_lock import acquire_exclusive
from utils.timezone import UTC, local_dt

logger = logging.getLogger("briefing_slots")

#: Zeitgrenze fuer die Sidecar-Sperre. Wird zur LAUFZEIT als Modul-Attribut
#: gelesen (``briefing_slots.LOCK_TIMEOUT_SECONDS``) statt in eine lokale
#: Konstante gebunden — sonst kann ein Test die Frist nicht kuerzen und
#: wartet die vollen 2 s (Spec, Known Limitations zu T13).
LOCK_TIMEOUT_SECONDS = file_lock.LOCK_TIMEOUT_SECONDS

_STATE_FILENAME = "briefing_slots.json"
_LOCK_SUFFIX = ".lock"
_BRIEFING_LOG_FILENAME = "briefing_log.json"


class BriefingSlotStore:
    """Vermerk-Speicher fuer den Schluessel ``(trip_id, slot, local_day)``.

    ``local_day`` ist der ORTSTAG des Laufs (ADR-0044), nicht der Zieltag des
    Briefings — ein Abend-Briefing berichtet ueber morgen, gehoert aber zum
    heutigen Slot.
    """

    def __init__(self, user_id: str, data_dir: Optional[Path] = None) -> None:
        self._user_id = user_id
        if data_dir is not None:
            self._dir = Path(data_dir)
        else:
            from app.loader import get_data_dir
            self._dir = get_data_dir(user_id)
        self._path = self._dir / _STATE_FILENAME

    # --- Oeffentliche Schnittstelle (Spec „Schnittstelle") ---

    def is_recorded(
        self, trip_id: str, slot: str, local_day: date,
        zone: Optional[ZoneInfo] = None,
    ) -> bool:
        """Liegt ein Vermerk vor?

        Schliesst die Rueckwaerts-Ableitung aus ``briefing_log.json`` ein
        (AC-9) — die greift aber nur, solange dieser Speicher noch keine
        eigene Datei hat (s. :meth:`_log_bezeugt_versand`).
        """
        if self._find(self._load(), trip_id, slot, local_day) is not None:
            return True
        return self._log_bezeugt_versand(trip_id, slot, local_day, zone)

    def reserve(
        self, trip_id: str, slot: str, local_day: date,
        zone: Optional[ZoneInfo] = None,
    ) -> bool:
        """``True`` nur bei FRISCHER Reservierung.

        ``False`` bei bestehendem Vermerk, beim Rollout-Nachweis aus
        ``briefing_log.json`` (AC-9) UND bei nicht erhaltener Sperre (AC-13).
        """
        def _op(data: dict) -> bool:
            if self._find(data, trip_id, slot, local_day) is not None:
                return False
            if self._log_bezeugt_versand(trip_id, slot, local_day, zone):
                return False
            data.setdefault("entries", []).append(
                self._eintrag(trip_id, slot, local_day, None)
            )
            return True

        return self._update(_op)

    def record_outcome(
        self, trip_id: str, slot: str, local_day: date, outcome: str,
    ) -> None:
        """Ausgang des Versandversuchs festhalten (Read-Modify-Write)."""
        def _op(data: dict) -> bool:
            eintrag = self._find(data, trip_id, slot, local_day)
            if eintrag is None:
                data.setdefault("entries", []).append(
                    self._eintrag(trip_id, slot, local_day, outcome)
                )
            else:
                eintrag["outcome"] = outcome
            return True

        self._update(_op)

    def release(self, trip_id: str, slot: str, local_day: date) -> None:
        """Reservierung zuruecknehmen (``channels_unreachable`` / Ausnahme)."""
        def _op(data: dict) -> bool:
            eintraege = data.get("entries", [])
            rest = [
                e for e in eintraege
                if not self._passt(e, trip_id, slot, local_day)
            ]
            if len(rest) == len(eintraege):
                return False
            data["entries"] = rest
            return True

        self._update(_op)

    # --- Schluessel ---

    @staticmethod
    def _eintrag(trip_id: str, slot: str, local_day: date, outcome: Optional[str]) -> dict:
        return {
            "trip_id": trip_id,
            "slot": slot,
            "local_day": local_day.isoformat(),
            "recorded_at": datetime.now(tz=timezone.utc).isoformat(),
            "outcome": outcome,
        }

    @staticmethod
    def _passt(eintrag: object, trip_id: str, slot: str, local_day: date) -> bool:
        """Alle DREI Glieder muessen stimmen — je eines weggelassen faellt ein
        anderer Nutzer, ein anderer Slot oder der Folgetag mit heraus."""
        return (
            isinstance(eintrag, dict)
            and eintrag.get("trip_id") == trip_id
            and eintrag.get("slot") == slot
            and eintrag.get("local_day") == local_day.isoformat()
        )

    def _find(
        self, data: dict, trip_id: str, slot: str, local_day: date,
    ) -> Optional[dict]:
        for eintrag in data.get("entries", []):
            if self._passt(eintrag, trip_id, slot, local_day):
                return eintrag
        return None

    # --- Rueckwaerts-Ableitung aus briefing_log.json (AC-9) ---

    def _log_bezeugt_versand(
        self, trip_id: str, slot: str, local_day: date, zone: Optional[ZoneInfo],
    ) -> bool:
        """Solange ``briefing_slots.json`` NICHT existiert, gilt ein Slot als
        erledigt, wenn ``briefing_log.json`` einen Versand mit passender
        Trip-Kennung und Slot-Art traegt, dessen ``sent_at`` in ``local_day``
        faellt.

        Deckt den Rollout-Uebergang ab: ein Deploy mitten im Nachhol-Fenster,
        wenn der eigene Speicher noch gar nicht angelegt ist. ``zone`` ist die
        Ortszone des Trips; ohne sie wird ``sent_at`` gegen UTC ausgewertet
        (nur der Scheduler kennt die Zone).

        🔴 Die Existenz-Bedingung steht bewusst HIER, an EINER Stelle, durch
        die beide Aufrufer (:meth:`is_recorded`, :meth:`reserve`) laufen. Sie
        ist die engere von zwei moeglichen Lesarten (PO-Entscheidung
        2026-08-11): Die Ableitung dient allein dem Rollout-Uebergang, danach
        ist der eigene Speicher massgeblich. Preis dafuer: beim Rollout bleibt
        ein einmaliges Fenster von Stunden, in dem ein Trip ungeschuetzt ist,
        sobald ein ANDERER Trip die Datei bereits angelegt hat — ein seltenes
        doppeltes Briefing gegen einen sonst dauerhaften Ausfall.

        🔴 Die enge Lesart allein genuegte NICHT (Adversary F004): sie
        verkuerzte den Schaden am On-Demand-Pfad von dauerhaft auf einen Tag,
        beseitigte ihn aber nicht. ``_append_briefing_log`` haelt seit diesem
        Fix ``on_demand`` im Eintrag fest, und die Schleife unten ueberspringt
        solche Eintraege — sonst naehme ein per SMS angefordertes „heute" dem
        Nutzer sein regulaeres Briefing desselben Ortstags (AC-12), still, ohne
        Protokollzeile.
        """
        if self._path.exists():
            return False
        pfad = self._dir / _BRIEFING_LOG_FILENAME
        if not pfad.exists():
            return False
        try:
            data = json.loads(pfad.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return False
        if not isinstance(data, dict):
            return False
        for eintrag in data.get("entries", []):
            if not isinstance(eintrag, dict):
                continue
            if eintrag.get("trip_id") != trip_id or eintrag.get("kind") != slot:
                continue
            if eintrag.get("on_demand") is True:
                # Issue #1725 (Adversary F004): ein angefordertes Briefing
                # („heute"/„morgen" per SMS, Test-Versand-Knopf) darf dem
                # Nutzer sein REGULAERES nicht wegnehmen (AC-12). Bestandsdaten
                # tragen das Feld nicht — ein fehlender Schluessel gilt deshalb
                # als regulaer, die Ableitung greift dort weiterhin. Das ist
                # die sichere Richtung: lieber ein Briefing zu wenig als eines
                # doppelt.
                continue
            sent_at = self._parse(eintrag.get("sent_at"))
            if sent_at is None:
                continue
            if local_dt(sent_at, zone or UTC).date() == local_day:
                return True
        return False

    @staticmethod
    def _parse(raw: object) -> Optional[datetime]:
        if not raw or not isinstance(raw, str):
            return None
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None

    # --- Load / Write (atomar, reload-vor-write) ---

    def _load(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _write(self, data: dict) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self._dir), prefix=".briefing_slots_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as f:
                f.write(json.dumps(data, indent=2))
            os.replace(tmp_name, self._path)
        except OSError:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
            raise

    def _update(self, mutate: Callable[[dict], bool]) -> bool:
        """Reload-mutate-write unter einer Sidecar-Sperre.

        Die Sperre liegt auf ``<state>.lock``, NICHT auf der Zieldatei —
        ``_write()`` tauscht deren Inode per ``os.replace``, ein Lock darauf
        wuerde danach nichts mehr serialisieren (Begruendung wie
        ``throttle_store._update``).

        Rueckgabe ist das Ergebnis von ``mutate`` (``True`` = geschrieben) —
        und ``False``, wenn die Sperre nicht innerhalb
        ``LOCK_TIMEOUT_SECONDS`` zu bekommen war. Genau hier weicht dieser
        Speicher bewusst vom Vorbild ab: nicht "Schreibvorgang uebersprungen
        und weiter", sondern "nicht reserviert" — der Aufrufer sendet dann
        nicht (AC-13).
        """
        self._dir.mkdir(parents=True, exist_ok=True)
        lock_path = str(self._path) + _LOCK_SUFFIX
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            if not acquire_exclusive(fd, LOCK_TIMEOUT_SECONDS):
                logger.warning(
                    "Dateisperre %s nicht innerhalb %.2fs erhalten -- "
                    "kein Vermerk, also kein Versand",
                    lock_path, LOCK_TIMEOUT_SECONDS,
                )
                return False
            try:
                data = self._load()
                geaendert = mutate(data)
                if geaendert:
                    self._write(data)
                return geaendert
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
