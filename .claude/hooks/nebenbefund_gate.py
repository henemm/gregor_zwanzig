#!/usr/bin/env python3
"""Nebenbefund-Gate (PO-go 2026-07-09): blockt `gh issue create` ohne Triage-Marker.

Durchsetzung von CLAUDE.md -> "Nebenbefund-Triage". Eigenes Issue nur bei:
  [triage:a]  nutzersichtbares Fehlverhalten
  [triage:b]  Datenverlust-/Sicherheitsrisiko
  [triage:c]  faelschlich blockierendes Gate
  [triage:po] explizit vom PO beauftragt
Alles andere gehoert als Checkbox-Zeile ins Sammel-Issue #1199.

Regel-Budget: Pruefdatum 2026-10-09 — danach deaktiviert sich das Gate selbst;
Entscheidung (behalten/entfernen) faellt im Gate-Audit #1197.
Fail-open: Parse-Fehler blockieren nie fremde Arbeit.
"""
import json
import re
import sys
from datetime import date

EXPIRY = date(2026, 10, 9)
MARKER_RE = re.compile(r"\[triage:(a|b|c|po)\]", re.IGNORECASE)
REPO_RE = re.compile(r"--repo[= ]\s*(\S+)")


def main() -> int:
    try:
        data = json.load(sys.stdin)
        cmd = (data.get("tool_input") or {}).get("command") or ""
    except Exception:
        return 0  # fail-open

    if "gh issue create" not in cmd:
        return 0
    if date.today() > EXPIRY:
        return 0  # Pruefdatum erreicht — Gate inaktiv (Regel-Budget), Entscheidung: #1197

    repo_match = REPO_RE.search(cmd)
    if repo_match and "gregor_zwanzig" not in repo_match.group(1):
        return 0  # anderes Repo (z. B. henemm-infra) — nicht Gegenstand dieses Gates

    if MARKER_RE.search(cmd):
        return 0

    sys.stderr.write(
        "NEBENBEFUND-GATE (CLAUDE.md -> Nebenbefund-Triage, PO-go 2026-07-09):\n"
        "Kein Triage-Marker im Befehl gefunden. Nebenbefunde werden NICHT mehr als\n"
        "Einzel-Issues angelegt, sondern als eine Checkbox-Zeile im Sammel-Issue #1199\n"
        "(Format: '- [ ] JJJJ-MM-TT - 1 Zeile - Fundstelle - Quelle', via Body-Edit von #1199).\n"
        "\n"
        "Ein eigenes Issue ist nur berechtigt bei:\n"
        "  [triage:a]  nutzersichtbares Fehlverhalten\n"
        "  [triage:b]  Datenverlust-/Sicherheitsrisiko\n"
        "  [triage:c]  faelschlich blockierendes Gate\n"
        "  [triage:po] explizit vom PO beauftragt\n"
        "\n"
        "-> Trifft eines zu: Marker in den Issue-BODY aufnehmen und erneut ausfuehren.\n"
        "-> Trifft keines zu: Eintrag in #1199 statt neues Issue.\n"
        "(Test-Befunde -> #1196, Gate-Befunde -> #1197, solange offen. Pruefdatum dieses Gates: 2026-10-09.)\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
