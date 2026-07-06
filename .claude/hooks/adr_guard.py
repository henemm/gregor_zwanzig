"""ADR Guard -- Commit-Gate Prueflogik (Issue #885).

def check(staged_files, commit_message, config) -> str | None
  None = durchgelassen / str = Block-Meldung mit Auswegen.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Default-Entscheidungsflaechen-Patterns
# ---------------------------------------------------------------------------

DEFAULT_DECISION_SURFACE_PATTERNS: list[str] = [
    # ADR-0017 Slice 3: eine Wurzel fuer alles Ausgabe-Seitige
    r"^src/output/",
    r"^docs/reference/decision_matrix\.md$",
    r"^src/providers/",
    # F005: Guard-Hooks (incl. adr_guard.py itself) are also decision surfaces
    r"^\.claude/hooks/.*_(gate|guard)\.py$",
    r"^src/.*metric.*",
]


def _matches_decision_surface(path: str, patterns: list[str]) -> bool:
    return any(re.search(p, path) for p in patterns)


def check(
    staged_files: list[str],
    commit_message: str,
    config: dict | None = None,
) -> str | None:
    """Prueft ob ein Commit eine ADR benoetigt.

    Returns:
        None  -- kein Block (kein Entscheidungs-Scope / ADR vorhanden / [no-adr])
        str   -- Block-Meldung mit den betroffenen Dateien und Auswegen
    """
    cfg = config or {}
    patterns: list[str] = (
        cfg.get("adr_guard", {}).get("decision_surface_patterns")
        or DEFAULT_DECISION_SURFACE_PATTERNS
    )

    # 1. Entscheidungsflaechen bestimmen
    surfaces = [f for f in staged_files if _matches_decision_surface(f, patterns)]
    if not surfaces:
        return None  # AC-4: kein Scope -> No-Op

    # 2. [no-adr] Marker -> bewusste Verneinung
    if "[no-adr]" in commit_message:
        return None  # AC-3

    # 3. ADR mitgestaged?
    if any(f.startswith("docs/adr/") and f.endswith(".md") for f in staged_files):
        return None  # AC-2

    # 4. Blockieren
    files_str = ", ".join(surfaces)
    return (
        f"BLOCKED: Entscheidungs-tragende Datei(en) ohne ADR: {files_str}.\n"
        "Lege ein docs/adr/NNNN-*.md an ODER schreibe [no-adr] in die Commit-Message."
    )
