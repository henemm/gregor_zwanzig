"""Issue #1061 — AC-3: BOT_COMMANDS-Doku-Drift in architecture.md.

# doc-compliance-test
Prueft, dass docs/features/architecture.md die tatsaechliche BOT_COMMANDS-Liste
aus src/output/channels/telegram.py wiedergibt (Anzahl + Namen). Kein Mock —
liest echten Quellcode und echte Doku-Datei.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _actual_bot_commands() -> list[str]:
    telegram_py = REPO_ROOT / "src" / "output" / "channels" / "telegram.py"
    src = telegram_py.read_text(encoding="utf-8")
    match = re.search(r"BOT_COMMANDS\s*=\s*\[(.*?)\n\]", src, re.S)
    assert match, "BOT_COMMANDS-Liste nicht in telegram.py gefunden"
    names = re.findall(r'"command"\s*:\s*"([a-z_]+)"', match.group(1))
    assert names, "Keine Befehlsnamen aus BOT_COMMANDS extrahiert"
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
