"""Bezeichner-Vorfilter der Scanner-Ratschen (#3279 Scheibe 1).

Spec: ``docs/specs/modules/rework_3279_scanner_ratschen_tempo_s1.md``.

Ein Scanner, dessen Regel einen bestimmten BEZEICHNER verlangt, muss nur die
Dateien parsen, in denen er vorkommt. 🔴 Nur Bezeichner sind als Filter
zulaessig: ein String-Inhalt (``"%H:%M"``) laesst sich durch Escapes oder
Verkettung zerlegen, ein Bezeichner steht immer zusammenhaengend im Quelltext.
Python liest Bezeichner NFKC-normalisiert, also sucht auch der Filter so.
"""
from __future__ import annotations

import ast
import unicodedata
from collections.abc import Iterable
from pathlib import Path


def quelltext_mit_bezeichnern(
    datei: Path, alle: Iterable[str] = (), eines_aus: Iterable[str] = (),
) -> str | None:
    """Unveraenderter Quelltext von ``datei``, wenn ALLE Bezeichner aus ``alle``
    und (falls angegeben) mindestens einer aus ``eines_aus`` vorkommen, sonst
    ``None``. Lesefehler (``OSError``, ``UnicodeDecodeError``) fliegen: was sie
    bedeuten, entscheidet jeder Scanner selbst."""
    quelltext = datei.read_text(encoding="utf-8")
    text = quelltext if quelltext.isascii() else unicodedata.normalize("NFKC", quelltext)
    if not all(name in text for name in alle):
        return None
    auswahl = tuple(eines_aus)
    if auswahl and not any(name in text for name in auswahl):
        return None
    return quelltext


def unparsbare_dateien(wurzel: Path) -> list[str]:
    """Je nicht les- oder parsbarer ``.py`` unter ``wurzel`` ein Befund mit
    Dateiname. ``ValueError`` umfasst ``UnicodeDecodeError`` und, je nach
    Python-Version, Nullbytes."""
    befunde: list[str] = []
    for datei in sorted(wurzel.rglob("*.py")):
        try:
            ast.parse(datei.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, ValueError) as fehler:
            name = datei.relative_to(wurzel).as_posix()
            befunde.append(f"{name}: {type(fehler).__name__}: {fehler}")
    return befunde
