"""Issue #1061 — AC-3: BOT_COMMANDS-Doku-Drift in architecture.md.

# doc-compliance-test
Prueft, dass docs/features/architecture.md die tatsaechliche BOT_COMMANDS-Liste
aus output.channels.telegram wiedergibt (Anzahl + Namen). Kein Mock — importiert
das echte Modul und introspiziert das Laufzeit-Objekt (kein Produkt-Quelltext-Read
per read_text/grep, CLAUDE.md/#765 AC-4) und liest die echte Doku-Datei.
"""
from __future__ import annotations

import re
from pathlib import Path

from output.channels.telegram import BOT_COMMANDS

REPO_ROOT = Path(__file__).resolve().parents[2]


def _actual_bot_commands() -> list[str]:
    names = [entry["command"] for entry in BOT_COMMANDS]
    assert names, "Keine Befehlsnamen in BOT_COMMANDS gefunden"
    return names


# doc-compliance-test
def test_architecture_doc_lists_actual_bot_commands():
    """AC-3: architecture.md muss die tatsaechliche Anzahl+Namen aus BOT_COMMANDS nennen."""
    actual = _actual_bot_commands()
    doc_path = REPO_ROOT / "docs" / "features" / "architecture.md"
    doc = doc_path.read_text(encoding="utf-8")

    line = next((l for l in doc.splitlines() if re.search(r"\d+ Befehle", l)), None)
    assert line is not None, "Keine Zeile mit 'N Befehle'-Aufzaehlung in architecture.md gefunden"

    assert f"{len(actual)} Befehle" in line, (
        f"architecture.md nennt nicht '{len(actual)} Befehle' "
        f"(tatsaechlich {len(actual)}: {actual}), Zeile: {line!r}"
    )
    for name in actual:
        assert name in line, (
            f"Befehl '{name}' aus BOT_COMMANDS fehlt in der Doku-Zeile: {line!r}"
        )
