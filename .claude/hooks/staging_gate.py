#!/usr/bin/env python3
"""
Staging Gate Hook (Issue #521 — Staging Validator Agent)

Zwei Modi:

Mode A — Verdict schreiben (vom Staging Validator Agent aufgerufen):
    python3 staging_gate.py --write-verdict "VERIFIED: ..." \
        --findings-json /tmp/findings.json [--e2e-path PATH]

    Schreibt .claude/e2e_verified.json mit verified_commit, staging_verdict,
    findings, verified_at, scope, environment.
    Exit 0 bei VERIFIED/AMBIGUOUS, Exit 1 bei BROKEN.
    Datei wird NUR bei Exit 0 geschrieben (kein BROKEN-Artefakt).

Mode B — Gate-Check (von deploy-gregor-prod.sh aufgerufen):
    python3 staging_gate.py --check [--e2e-path PATH] [--scope SCOPE]

    Prüft Reihenfolge:
      1. GZ_SKIP_E2E_GATE=1 → Warn + Exit 0
      2. --scope=docs-only ODER detect_scope==docs-only → Exit 0
      3. e2e_verified.json fehlt → Exit 1
      4. verified_commit != git rev-parse HEAD → Exit 1
      5. staging_verdict beginnt nicht mit VERIFIED → Exit 1
      6. verified_at älter als 24h → Exit 1
      7. Alle OK → Exit 0

Mode C — Scope detection:
    python3 staging_gate.py --detect-scope  # gibt Scope-String auf stdout
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO_DIR = Path("/home/hem/gregor_zwanzig")
CANONICAL_E2E_PATH = REPO_DIR / ".claude" / "e2e_verified.json"
STALE_HOURS = 24


def _log(msg: str, stream=sys.stdout) -> None:
    print(f"[staging-gate] {msg}", file=stream)


def _head_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, cwd=str(REPO_DIR),
    )
    return result.stdout.strip()


def _detect_committed_scope() -> str:
    """Klassifiziert den letzten Commit (HEAD~1..HEAD) in einen Scope.

    Returns: frontend-only | backend | full-stack | docs-only
    """
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
        capture_output=True, text=True, cwd=str(REPO_DIR),
    )
    files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
    if not files:
        return "docs-only"

    has_frontend = False
    has_backend = False
    for path in files:
        if path.startswith("frontend/"):
            has_frontend = True
        elif (
            path.startswith("src/")
            or path.startswith("api/")
            or path.startswith("internal/")
            or path.startswith("cmd/")
        ):
            has_backend = True
        elif (
            path.startswith("docs/")
            or path.startswith(".claude/")
            or path.endswith(".md")
            or path.startswith("README")
            or path == ".gitignore"
        ):
            pass
        else:
            has_backend = True

    if has_frontend and has_backend:
        return "full-stack"
    if has_frontend:
        return "frontend-only"
    if has_backend:
        return "backend"
    return "docs-only"


def write_verdict(verdict: str, findings_path: Path, e2e_path: Path) -> int:
    """Mode A: Verdict in e2e_verified.json schreiben."""
    verdict_upper = verdict.strip().upper()
    if verdict_upper.startswith("BROKEN"):
        _log(f"BROKEN-Verdict erhalten: {verdict}")
        _log("Kein VERIFIED-Artefakt geschrieben — /e2e-verify erneut ausführen.", stream=sys.stderr)
        return 1

    try:
        findings = json.loads(findings_path.read_text()) if findings_path.exists() else []
    except (json.JSONDecodeError, OSError) as exc:
        _log(f"Findings-Datei nicht lesbar: {exc}", stream=sys.stderr)
        return 1

    scope = _detect_committed_scope()
    payload = {
        "verified_commit": _head_sha(),
        "staging_verdict": verdict,
        "findings": findings,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "scope": scope,
        "environment": "staging",
    }
    e2e_path.parent.mkdir(parents=True, exist_ok=True)
    e2e_path.write_text(json.dumps(payload, indent=2))
    _log(f"Verdict geschrieben: {verdict} (commit={payload['verified_commit'][:8]}, scope={scope})")
    return 0


def gate_check(e2e_path: Path, scope_override: str | None) -> int:
    """Mode B: Gate-Check für deploy-gregor-prod.sh."""
    if os.environ.get("GZ_SKIP_E2E_GATE") == "1":
        _log("WARN: GZ_SKIP_E2E_GATE=1 — Staging-Gate übersprungen (Notfall-Override).", stream=sys.stderr)
        return 0

    scope = scope_override or _detect_committed_scope()
    if scope == "docs-only":
        _log(f"Scope '{scope}' — Staging-Gate übersprungen (kein UI/Backend-Change).")
        return 0

    if not e2e_path.exists():
        _log(
            f"FEHLER: e2e_verified.json fehlt unter {e2e_path}. "
            "/e2e-verify ausführen, dann erneut deployen.",
            stream=sys.stderr,
        )
        return 1

    try:
        data = json.loads(e2e_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        _log(f"FEHLER: e2e_verified.json nicht lesbar: {exc}", stream=sys.stderr)
        return 1

    head = _head_sha()
    verified_commit = data.get("verified_commit", "")
    if verified_commit != head:
        _log(
            f"FEHLER: verified_commit ({verified_commit[:8]}) != HEAD-SHA ({head[:8]}). "
            "Veraltete Verifikation — /e2e-verify erneut ausführen.",
            stream=sys.stderr,
        )
        return 1

    verdict = data.get("staging_verdict", "")
    if not verdict.startswith("VERIFIED"):
        _log(
            f"FEHLER: staging_verdict ist nicht VERIFIED (war: {verdict!r}). "
            "/e2e-verify ausführen, dann erneut deployen.",
            stream=sys.stderr,
        )
        return 1

    verified_at_str = data.get("verified_at", "")
    try:
        verified_at = datetime.fromisoformat(verified_at_str)
        if verified_at.tzinfo is None:
            verified_at = verified_at.replace(tzinfo=timezone.utc)
    except ValueError:
        _log(f"FEHLER: verified_at ist kein ISO-Timestamp: {verified_at_str!r}", stream=sys.stderr)
        return 1

    age = datetime.now(timezone.utc) - verified_at
    if age > timedelta(hours=STALE_HOURS):
        _log(
            f"FEHLER: Verifikation ist {age.total_seconds()/3600:.1f}h alt (max {STALE_HOURS}h). "
            "Artefakt abgelaufen — /e2e-verify erneut ausführen.",
            stream=sys.stderr,
        )
        return 1

    _log(f"OK: Staging-Gate bestanden (commit={head[:8]}, verdict={verdict!r}).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="staging_gate")
    parser.add_argument("--check", action="store_true", help="Mode B: Gate-Check")
    parser.add_argument("--write-verdict", help="Mode A: Verdict-String zum Schreiben")
    parser.add_argument("--findings-json", help="Pfad zur Findings-JSON (Mode A)")
    parser.add_argument("--e2e-path", help="Pfad zur e2e_verified.json (Override)")
    parser.add_argument("--scope", help="Scope-Override (frontend-only|backend|full-stack|docs-only)")
    parser.add_argument("--detect-scope", action="store_true", help="Mode C: Scope ausgeben")
    args = parser.parse_args()

    e2e_path = Path(args.e2e_path) if args.e2e_path else CANONICAL_E2E_PATH

    if args.detect_scope:
        print(_detect_committed_scope())
        return 0

    if args.write_verdict:
        findings_path = Path(args.findings_json) if args.findings_json else Path("/dev/null")
        return write_verdict(args.write_verdict, findings_path, e2e_path)

    if args.check:
        return gate_check(e2e_path, args.scope)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
