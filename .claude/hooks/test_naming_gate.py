#!/usr/bin/env python3
"""Testnamen-Gate (PO-go 2026-07-09): blockt das Anlegen NEUER issue-nummerierter Testdateien.

Durchsetzung von CLAUDE.md -> "Test-Politik: Zwei Schichten" (Namensregel):
Neue Testdateien heissen nach VERHALTEN (test_alert_throttle.py), nicht nach
Issue-Nummer (test_issue_1234.py). Bestandsdateien (262 Stueck) bleiben editierbar;
ihre Sanierung laeuft ueber #1196.

Regel-Budget: Pruefdatum 2026-10-09 — danach deaktiviert sich das Gate selbst;
Entscheidung (behalten/entfernen) faellt im Gate-Audit #1197.
Fail-open: Parse-Fehler blockieren nie fremde Arbeit.
"""
import json
import os
import re
import sys
from datetime import date

EXPIRY = date(2026, 10, 9)
PATTERN = re.compile(
    r"(tests/.*test_(issue|bug|feature)_\d|frontend/e2e/.*(issue|bug)[-_]\d)",
    re.IGNORECASE,
)


def main() -> int:
    try:
        data = json.load(sys.stdin)
        file_path = (data.get("tool_input") or {}).get("file_path") or ""
    except Exception:
        return 0  # fail-open

    if not file_path or date.today() > EXPIRY:
        return 0
    if not PATTERN.search(file_path.replace("\\", "/")):
        return 0
    if os.path.exists(file_path):
        return 0  # Bestand bleibt editierbar — nur NEUE Dateien sind gesperrt

    sys.stderr.write(
        "TESTNAMEN-GATE (CLAUDE.md -> Test-Politik, PO-go 2026-07-09):\n"
        "Neue Testdateien werden nach VERHALTEN benannt, nicht nach Issue-Nummer.\n"
        "Beispiel: tests/tdd/test_alert_throttle.py statt test_issue_1234.py.\n"
        "Der Repro-Test fuer einen Bug gehoert in die passende Verhaltens-/Modul-Datei\n"
        "(bestehende Datei erweitern oder eine nach dem Verhalten benannte neue anlegen).\n"
        "(Bestandsdateien sind nicht betroffen. Kontext: #1196. Pruefdatum dieses Gates: 2026-10-09.)\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
