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
import shlex
import sys
from datetime import date

EXPIRY = date(2026, 10, 9)
MARKER_RE = re.compile(r"\[triage:(a|b|c|po)\]", re.IGNORECASE)
REPO_RE = re.compile(r"--repo[= ]\s*(\S+)")


def _has_create_call(tokens: list[str]) -> bool:
    """True, wenn die Tokens 'gh issue create' als drei aufeinanderfolgende
    Werte enthalten (#1197). Ein gequotetes 'gh issue create' ist bei shlex EIN
    Token → kein Match → kein False-Block bei zitiertem Text (AC-4)."""
    for i in range(len(tokens) - 2):
        if tokens[i] == "gh" and tokens[i + 1] == "issue" and tokens[i + 2] == "create":
            return True
    return False


def _body_file_marker(tokens: list[str]) -> bool:
    """Liest den Marker aus einer per --body-file/-F referenzierten Datei (#1197).
    Unterstuetzt '--body-file <pfad>', '--body-file=<pfad>', '-F <pfad>', '-F=<pfad>'.
    '-' (stdin) / nicht lesbar → defensiv ignorieren (Fallback auf cmd-Check)."""
    path = None
    for i, tok in enumerate(tokens):
        if tok in ("--body-file", "-F"):
            if i + 1 < len(tokens):
                path = tokens[i + 1]
            break
        if tok.startswith("--body-file=") or tok.startswith("-F="):
            path = tok.split("=", 1)[1]
            break
    if not path or path == "-":
        return False
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return bool(MARKER_RE.search(fh.read()))
    except OSError:
        return False


def main() -> int:
    try:
        data = json.load(sys.stdin)
        cmd = (data.get("tool_input") or {}).get("command") or ""
    except Exception:
        return 0  # fail-open

    try:
        tokens = shlex.split(cmd)
    except ValueError:
        return 0  # unbalancierte Quotes o.ae. — fail-open (blockt nie fremde Arbeit)

    if not _has_create_call(tokens):
        return 0  # kein echter 'gh issue create'-Aufruf (auch: zitierter Text)
    if date.today() > EXPIRY:
        return 0  # Pruefdatum erreicht — Gate inaktiv (Regel-Budget), Entscheidung: #1197

    repo_match = REPO_RE.search(cmd)
    if repo_match and "gregor_zwanzig" not in repo_match.group(1).lower():
        return 0  # anderes Repo (z. B. henemm-infra) — nicht Gegenstand dieses Gates

    if MARKER_RE.search(cmd) or _body_file_marker(tokens):
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
