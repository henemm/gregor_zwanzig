"""Groessenbasierte Rotation append-only JSONL-Journale (Issue #2224, #2883).

Gemeinsamer Helfer fuer die Diagnose-Journale (Warn-Dienst, Open-Meteo,
Anreicherung): genau EINE Vorgaenger-Generation ``<journal>.1``. Gelesen werden
aktuelle Datei plus ``.1`` (Go: ``internal/scheduler/journal_rotation.go``).

SPEC: docs/specs/modules/fix_2883_diagnose_journal_rotation.md
"""
from __future__ import annotations

import fcntl
import os
from pathlib import Path


def rotate_if_needed(path: Path, max_bytes: int) -> None:
    """Benennt das Journal in ``<path>.1`` um, sobald es ``max_bytes`` erreicht.

    Schneller Pfad ohne Sperre unter der Schwelle. Sonst exklusive Sperre auf
    ``<path>.lock`` und erneute Groessenpruefung UNTER der Sperre: ein zweiter
    Thread, der ebenfalls die volle Datei sah, darf die gerade erzeugte ``.1``
    nicht mit der frischen, kleinen aktuellen Datei ueberschreiben. Jeder
    Fehler wird geschluckt (fail-soft)."""
    try:
        try:
            if path.stat().st_size < max_bytes:
                return
        except FileNotFoundError:
            return
        with open(path.with_name(path.name + ".lock"), "a") as lock_fh:
            fcntl.flock(lock_fh, fcntl.LOCK_EX)
            try:
                if path.stat().st_size >= max_bytes:
                    os.replace(path, path.with_name(path.name + ".1"))
            finally:
                fcntl.flock(lock_fh, fcntl.LOCK_UN)
    except Exception:
        pass  # Rotation darf den Abruf NIE beeintraechtigen
