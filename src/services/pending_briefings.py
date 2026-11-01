"""Geteilte Nachhol-Vermerke fuer Trip UND Ortsvergleich (Issue #2587).

SPEC: docs/specs/modules/feat_2587_compare_briefing_nachholen.md
Vorbild: docs/specs/modules/fix_1662_versandfehler_nachliefern.md (Trip)

Ablage je Nutzer: ``data/users/<user_id>/pending_briefings.json`` mit
``{"entries": [...]}``. Beide Arten teilen sich die Datei (Go
``BriefingHealth`` zaehlt jeden Eintrag, Export-Liste und Infra-Pruefung
kennen sie bereits). Unterschieden wird ueber ``kind``:

* kein ``kind`` (Bestand) oder ``kind == "route"`` -> Trip-Vermerk
  (Schluessel ``trip_id``),
* ``kind == "vergleich"`` -> Ortsvergleich-Vermerk (Schluessel
  ``(preset_id, report_type)``).

Code-Teilung (ADR-0097): dieses Modul traegt bewusst KEIN ``trip_``/
``compare_``-Praefix. Es kennt nur die kind-/schluesselparametrisierten
Operationen (laden, atomar schreiben, ersetzen, entfernen, attempts
hochzaehlen) und den Hinweis-Text. Die Nachhol-SCHLEIFEN bleiben getrennt.

Schreibweise: Read-Modify-Write mit Merge -- nur der eigene Schluessel wird
ersetzt/entfernt, fremde Eintraege (auch die der anderen Art) bleiben
unangetastet (#102). Atomares Schreiben (tmp + ``os.replace``). Lesen
fail-soft (fehlende/kaputte Datei => leere Liste, #1012 F001).
"""
from __future__ import annotations

import fcntl
import json
import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

from i18n import Lang, t

logger = logging.getLogger("pending_briefings")

PENDING_FILENAME = "pending_briefings.json"
#: Sperrdatei neben der Ablage: ``trip-reports`` und ``compare-presets-daily``
#: schreiben dieselbe Datei (Lost-Update-Schutz).
LOCK_FILENAME = ".pending_briefings.lock"
KIND_ROUTE = "route"
KIND_VERGLEICH = "vergleich"
DISPATCH_ERROR = "dispatch_error"

#: Zuordnung eines Eintrags zur Art/zum Schluessel des Aufrufers.
Match = Callable[[dict], bool]


def load_pending_entries(path: Path) -> dict:
    """Issue #1012 Adversary-Fix F001: liest pending_briefings.json robust.

    Fehlende oder kaputte Datei (z.B. abgebrochener Schreibvorgang) liefert ein
    leeres Schema statt eine ungefangene JSONDecodeError zu werfen, die sonst
    den kompletten stündlichen Versandlauf VOR dem regulären Versand crasht
    (HTTP 500, kein Trip bekommt sein Briefing).
    """
    if not path.exists():
        return {"entries": []}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Corrupt pending_briefings.json at {path}, ignoring: {e}")
        return {"entries": []}


def write_pending_data(path: Path, data: dict) -> None:
    """Atomarer Schreibvorgang (tmp + os.replace) — verhindert eine halb
    geschriebene Datei bei einem Absturz mitten im Schreibvorgang."""
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, indent=2))
    os.replace(tmp_path, path)


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    """Exklusive Sperre (``fcntl.flock``) fuer ein komplettes Read-Modify-Write;
    gilt je offener Datei, also auch zwischen Threads eines Prozesses."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.parent / LOCK_FILENAME, "a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def pending_path(user_id: str) -> Path:
    """Ablage DIESES Nutzers. ``user_id`` kommt immer vom Aufrufer (echte
    Kennung aus dem Auth-/Scheduler-Kontext, nie ein Rueckfall)."""
    from app.loader import get_data_dir

    return get_data_dir(user_id) / PENDING_FILENAME


def is_trip_entry(entry: dict) -> bool:
    """Trip-Vermerk: kein ``kind`` (Bestandsformat) oder ``kind == "route"``."""
    return entry.get("kind") in (None, "", KIND_ROUTE)


def is_compare_entry(entry: dict) -> bool:
    """Ortsvergleich-Vermerk: ``kind == "vergleich"``."""
    return entry.get("kind") == KIND_VERGLEICH


def entries_matching(path: Path, match: Match) -> list:
    """Alle Eintraege, die ``match`` erfuellen (fail-soft gelesen)."""
    return [
        e for e in load_pending_entries(path).get("entries", [])
        if isinstance(e, dict) and match(e)
    ]


def upsert_entry(path: Path, match: Match, entry: dict) -> None:
    """Ersetzt alle Eintraege, die ``match`` erfuellen, durch ``entry`` (RMW).

    Pro Schluessel hoechstens ein Eintrag: ein neuer Fehlschlag ersetzt den
    alten, fremde Eintraege bleiben unveraendert.
    """
    with _locked(path):
        data = load_pending_entries(path)
        rest = [e for e in data.get("entries", []) if not (isinstance(e, dict) and match(e))]
        rest.append(entry)
        data["entries"] = rest
        write_pending_data(path, data)


def remove_entries(path: Path, match: Match) -> int:
    """Entfernt alle Eintraege, die ``match`` erfuellen (RMW).

    Schreibt nur bei tatsaechlicher Aenderung; die Datei bleibt bestehen
    (auch mit leerer Liste). Rueckgabe: Zahl der entfernten Eintraege.
    """
    if not path.exists():
        return 0
    with _locked(path):
        data = load_pending_entries(path)
        entries = data.get("entries", [])
        rest = [e for e in entries if not (isinstance(e, dict) and match(e))]
        removed = len(entries) - len(rest)
        if removed:
            data["entries"] = rest
            write_pending_data(path, data)
    return removed


def bump_attempts(path: Path, match: Match) -> None:
    """Issue #1012 (b2, Lärmschutz): attempts += 1, Eintrag bleibt bestehen."""
    if not path.exists():
        return
    with _locked(path):
        data = load_pending_entries(path)
        for e in data.get("entries", []):
            if isinstance(e, dict) and match(e):
                e["attempts"] = e.get("attempts", 0) + 1
        write_pending_data(path, data)


def dispatch_error_hint(slot_hour, *, lang: Lang = "de") -> str:
    """Nachhol-Hinweis nach Versandfehler (#1662 AC-3, #2587 AC-5).

    EIN Text fuer Trip und Ortsvergleich. Stunde zweistellig (``07:00``,
    Wortlaut AC-5); ein unlesbarer Wert faellt auf die bisherige Fassung
    zurueck, statt den Nachholversand abzubrechen.
    """
    try:
        stunde = f"{int(slot_hour):02d}:00"
    except (TypeError, ValueError):
        stunde = f"{slot_hour}:00"
    return t("versand.scheduler.zustellung_fehlgeschlagen", lang, stunde=stunde)
