#!/usr/bin/env python3
"""
Adversary Dialog System — Structured QA-Tester / Fixer Verification.

Orchestriert einen strukturierten Dialog zwischen QA-Agent und Implementierer.
Parst die Spec, erstellt eine Checkliste aller Expected-Behavior-Punkte,
und validiert das Dialog-Artifact.

Best Practices:
  - Tri-State Verdict: VERIFIED / BROKEN / AMBIGUOUS
  - Circuit Breaker: Max 3 Iterationen, dann Eskalation
  - Structured Findings: severity, category, evidence, remediation
  - Early-Agreement-Skepticism: Min. 2 Runden Pflicht

Usage (CLI):
  python3 adversary_dialog.py parse <spec-path>
  python3 adversary_dialog.py validate <artifact-path>
  python3 adversary_dialog.py schema
"""

import re
import sys
import time
from datetime import datetime
from pathlib import Path

# Circuit Breaker: max iterations before escalation to user
MAX_ITERATIONS = 3

# Minimum dialog rounds before VERIFIED is accepted
MIN_ROUNDS = 2

# Max age of artifact in minutes
MAX_AGE_MINUTES = 60

# Valid verdicts (tri-state)
VERDICTS = ("VERIFIED", "BROKEN", "AMBIGUOUS")

# Finding severity levels
SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")

# Finding categories
CATEGORIES = (
    "spec_violation",
    "edge_case",
    "regression",
    "security",
    "anti_pattern",
)


def parse_spec_expected_behavior(spec_path: str) -> list[str]:
    """Parse a spec file and extract Expected Behavior bullet points.

    Sucht nach einer '## Expected Behavior' Section und extrahiert
    alle Bullet-Points bis zur naechsten '## ' Section oder Dateiende.
    """
    path = Path(spec_path)
    if not path.exists():
        return []

    content = path.read_text(errors="replace")
    lines = content.splitlines()

    in_section = False
    points = []

    for line in lines:
        stripped = line.strip()

        if re.match(r"^##\s+Expected Behavior", stripped, re.IGNORECASE):
            in_section = True
            continue

        if in_section and re.match(r"^##\s+", stripped):
            break

        if in_section and (
            re.match(r"^-\s+", stripped) or re.match(r"^\d+\.\s+", stripped)
        ):
            point = re.sub(r"^(-\s+|\d+\.\s+)", "", stripped)
            if point:
                points.append(point)

    return points


def create_checklist(points: list[str]) -> list[dict]:
    """Erstellt eine Checkliste aus Expected-Behavior-Punkten."""
    return [
        {"description": p, "status": "open", "evidence": None}
        for p in points
    ]


def render_finding(
    finding_id: str,
    severity: str,
    category: str,
    description: str,
    evidence: str,
    remediation: str = "",
) -> dict:
    """Erstellt ein strukturiertes Finding-Objekt."""
    return {
        "id": finding_id,
        "severity": severity.upper() if severity.upper() in SEVERITIES else "MEDIUM",
        "category": category if category in CATEGORIES else "spec_violation",
        "description": description,
        "evidence": evidence,
        "remediation": remediation,
    }


def render_dialog_artifact(
    workflow_name: str,
    spec_path: str,
    checklist: list[dict],
    rounds: list[dict],
    findings: list[dict],
    final_verdict: str,
    iteration: int = 1,
) -> str:
    """Rendert das Dialog-Protokoll als Markdown-Artifact."""
    lines = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines.append(f"# Adversary Dialog — {workflow_name}")
    lines.append(f"Spec: {spec_path}")
    lines.append(f"Datum: {timestamp}")
    lines.append(f"Iteration: {iteration} / {MAX_ITERATIONS}")
    lines.append("")

    lines.append("## Checkliste")
    for item in checklist:
        marker = "x" if item["status"] == "verified" else " "
        evidence = f" — Beweis: {item['evidence']}" if item.get("evidence") else " — OFFEN"
        lines.append(f"- [{marker}] {item['description']}{evidence}")
    lines.append("")

    if findings:
        lines.append("## Findings")
        lines.append("")
        for f in findings:
            lines.append(f"### {f['id']}: {f['description']}")
            lines.append(f"- **Severity:** {f['severity']}")
            lines.append(f"- **Category:** {f['category']}")
            lines.append(f"- **Evidence:** {f['evidence']}")
            if f.get("remediation"):
                lines.append(f"- **Remediation:** {f['remediation']}")
            lines.append("")

    lines.append("## Dialog")

    if len(rounds) < MIN_ROUNDS:
        lines.append("")
        lines.append(
            f"> **Warnung:** Nur {len(rounds)} Runde(n) dokumentiert. "
            f"Minimum sind {MIN_ROUNDS} Runden."
        )
        lines.append("")

    for r in rounds:
        lines.append(f"### Runde {r['round']}")
        lines.append(f"**Adversary:** {r['adversary']}")
        lines.append(f"**Implementierer:** {r['implementer']}")
        if r.get("verdict"):
            lines.append(f"**Bewertung:** {r['verdict']}")
        lines.append("")

    lines.append("## Verdict")
    lines.append(f"**{final_verdict}**")

    open_count = sum(1 for item in checklist if item["status"] != "verified")
    total = len(checklist)
    lines.append(f"Offene Punkte: {open_count} / {total}")

    if final_verdict.startswith("AMBIGUOUS"):
        lines.append("")
        lines.append("> Ambiguous findings require human review. "
                      "Pipeline is NOT blocked but user should verify.")

    if iteration >= MAX_ITERATIONS:
        lines.append("")
        lines.append(f"> **Circuit Breaker:** Max iterations ({MAX_ITERATIONS}) reached. "
                      "Escalating to user.")

    return "\n".join(lines)


def validate_dialog_artifact(artifact_path: str) -> tuple[bool, str]:
    """Validiert ein Dialog-Artifact.

    Prueft:
    1. Datei existiert
    2. Datei ist < MAX_AGE_MINUTES alt
    3. Alle Checklisten-Punkte sind [x] (abgehakt)
    4. Mindestens MIN_ROUNDS Dialog-Runden dokumentiert
    5. Verdict ist VERIFIED oder AMBIGUOUS (nicht BROKEN)
    """
    path = Path(artifact_path)

    if not path.exists():
        return False, f"Dialog artifact not found: {artifact_path}"

    age_min = (time.time() - path.stat().st_mtime) / 60
    if age_min > MAX_AGE_MINUTES:
        return False, (
            f"Dialog artifact is {age_min:.0f} min old "
            f"(max {MAX_AGE_MINUTES}). Re-run dialog."
        )

    content = path.read_text(errors="replace")

    checked = len(re.findall(r"- \[x\]", content, re.IGNORECASE))
    unchecked = len(re.findall(r"- \[ \]", content))

    if unchecked > 0:
        return False, (
            f"{unchecked} Checklisten-Punkt(e) noch offen. "
            "Alle muessen bewiesen sein."
        )

    if checked == 0:
        return False, "Keine Checklisten-Punkte gefunden."

    rounds = len(re.findall(r"### Runde \d+", content))
    if rounds < MIN_ROUNDS:
        return False, (
            f"Nur {rounds} Dialog-Runde(n) dokumentiert. "
            f"Minimum sind {MIN_ROUNDS} Runden."
        )

    verdict_match = re.search(r"## Verdict\s*\n\*\*(.+?)\*\*", content)
    if not verdict_match:
        return False, "Kein Verdict im Artifact gefunden."

    verdict_text = verdict_match.group(1).strip()

    if verdict_text.startswith("BROKEN"):
        return False, f"Verdict ist '{verdict_text}' — nicht VERIFIED."

    if verdict_text.startswith("AMBIGUOUS"):
        return True, (
            f"Dialog valid (AMBIGUOUS): {checked} Punkte bewiesen, "
            f"{rounds} Runden. User-Review empfohlen."
        )

    if not verdict_text.startswith("VERIFIED"):
        return False, f"Unbekanntes Verdict: '{verdict_text}'"

    return True, (
        f"Dialog valid: {checked} Punkte bewiesen, "
        f"{rounds} Runden, Verdict VERIFIED."
    )


def print_finding_schema():
    """Gibt das Finding-Schema aus."""
    print("Structured Finding Schema:")
    print("  {")
    print('    "id": "F001",')
    print('    "severity": "CRITICAL | HIGH | MEDIUM | LOW",')
    print('    "category": "spec_violation | edge_case | regression | security | anti_pattern",')
    print('    "description": "What is the problem",')
    print('    "evidence": "file:line or test output or screenshot path",')
    print('    "remediation": "Suggested fix"')
    print("  }")
    print()
    print(f"Verdicts: {', '.join(VERDICTS)}")
    print(f"Circuit Breaker: max {MAX_ITERATIONS} iterations")
    print(f"Min Rounds: {MIN_ROUNDS}")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 adversary_dialog.py parse <spec-path>")
        print("  python3 adversary_dialog.py validate <artifact-path>")
        print("  python3 adversary_dialog.py schema")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "parse":
        if len(sys.argv) < 3:
            print("Error: spec-path required")
            sys.exit(1)
        spec_path = sys.argv[2]
        points = parse_spec_expected_behavior(spec_path)
        if not points:
            print("Keine Expected-Behavior-Punkte gefunden.")
            sys.exit(0)
        print(f"{len(points)} Expected-Behavior-Punkte gefunden:")
        for i, p in enumerate(points, 1):
            print(f"  {i}. {p}")

    elif cmd == "validate":
        if len(sys.argv) < 3:
            print("Error: artifact-path required")
            sys.exit(1)
        artifact_path = sys.argv[2]
        valid, message = validate_dialog_artifact(artifact_path)
        print(message)
        sys.exit(0 if valid else 1)

    elif cmd == "schema":
        print_finding_schema()

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
