#!/usr/bin/env python3
"""Issue #811 — Renderer-Mail-Gate (un-ueberspringbar).

Blockiert `git commit`, sobald eine Mail-Inhalts-Datei gestaged ist, bis im
aktiven Workflow ZWEI frische Nachweise vorliegen:

  (a) Matrix-Test-Nachweis: state["gates"]["renderer_mail"]["matrix"] mit
      {passed: true, mail_files_hash: <sha256 der gestagten Mail-Dateien>}.
      Der Hash bindet den Nachweis an genau den gestagten Stand (Anti-Stale).
  (b) Validator-Nachweis: jüngstes .claude/workflows/_log/*_briefing_validation.yaml
      mit workflow_id == aktiver Workflow UND passed: true.

KEIN globaler/ENV-Bypass — der Nachweis lebt ausschliesslich pro Workflow in
.claude/workflows/<name>.json.

Modi:
  (kein Argument)  Hook-Modus: stdin-JSON {"tool_input":{"command":"git commit ..."}}
  record-matrix    Recorder: berechnet sha256 der gestagten Mail-Dateien und
                   schreibt ihn nach state.gates.renderer_mail.matrix.

Exit-Codes: 0 = erlaubt/no-op, 2 = blockiert.

Vorbild fuer stdin/diff/Exit-Konventionen: pre_commit_gate.py.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Geschuetzte Mail-Inhalts-Pfade (Spec).
_MAIL_PATTERNS = [
    re.compile(r"src/output/renderers/email/.*\.py$"),
    re.compile(r"src/formatters/.*\.py$"),
    re.compile(r"src/outputs/email\.py$"),
]


def _repo_root() -> Path:
    """Staging-Repo: cwd-Toplevel — hier liegt der Index + die Mail-Dateien."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        if out:
            return Path(out)
    except Exception:
        pass
    return Path.cwd()


def _shared_repo_root() -> Path:
    """Shared-Repo fuer .claude/workflows/ — Hauptrepo bei Worktrees.

    Analog workflow.py: git-common-dir → Eltern-Verzeichnis ist das Repo, dem
    der .git-Store gehoert. Im Worktree zeigt das aufs Hauptrepo (gemeinsamer
    Workflow-State); im Standalone-Repo aufs Repo selbst.
    """
    try:
        common = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        if common:
            p = Path(common)
            if not p.is_absolute():
                p = (Path.cwd() / p).resolve()
            return p.parent
    except Exception:
        pass
    return _repo_root()


def _is_mail_file(name: str) -> bool:
    return any(p.search(name) for p in _MAIL_PATTERNS)


def _staged_files(repo: Path) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=repo, capture_output=True, text=True, check=False,
    ).stdout
    return [f for f in out.split() if f]


def _staged_mail_hash(repo: Path, staged: list[str]) -> str:
    """sha256 der gestagten Mail-Inhalts-Datei(en) — identisch zur Testberechnung."""
    h = hashlib.sha256()
    for name in sorted(staged):
        if _is_mail_file(name):
            try:
                h.update((repo / name).read_bytes())
            except OSError:
                pass
    return h.hexdigest()


def _active_workflow_name() -> str:
    return os.environ.get("GZ_ACTIVE_WORKFLOW", "").strip()


def _state_path(repo: Path, name: str) -> Path:
    return repo / ".claude" / "workflows" / f"{name}.json"


def _read_tool_input() -> dict:
    raw = os.environ.get("CLAUDE_TOOL_INPUT", "")
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    try:
        data = json.load(sys.stdin)
        return data.get("tool_input", data)
    except Exception:
        return {}


def _max_mail_mtime(repo: Path, staged: list[str]) -> float:
    """Groesste mtime der gestagten Mail-Inhalts-Dateien (0.0 wenn keine vorhanden)."""
    mtimes = []
    for name in staged:
        if _is_mail_file(name):
            try:
                mtimes.append((repo / name).stat().st_mtime)
            except OSError:
                pass
    return max(mtimes) if mtimes else 0.0


def _validator_log_ok(shared: Path, name: str, repo: Path, staged: list[str]) -> bool:
    """Juengstes briefing_validation.yaml mit workflow_id == name, passed: true
    UND validated_at FRISCHER als die letzte Mail-Datei-mtime (AC-2b Freshness).

    Fail-safe: fehlendes/unparsbares validated_at → als ungueltig behandeln → block.
    """
    log_dir = shared / ".claude" / "workflows" / "_log"
    if not log_dir.exists():
        return False
    logs = sorted(
        log_dir.glob("*_briefing_validation.yaml"),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    mail_mtime = _max_mail_mtime(repo, staged)
    for log in logs:
        try:
            text = log.read_text()
        except OSError:
            continue
        wid = re.search(r"^workflow_id:\s*(\S+)", text, re.M)
        if not wid or wid.group(1).strip().strip("'\"") != name:
            continue
        passed = re.search(r"^passed:\s*(\w+)", text, re.M)
        if not (passed and passed.group(1).strip().lower() == "true"):
            return False
        # Freshness: validated_at muss nach der letzten Mail-Datei-mtime liegen.
        vat = re.search(r"^validated_at:\s*'?([^'\n]+)'?", text, re.M)
        if not vat:
            return False  # fehlendes validated_at → fail-safe block
        try:
            vat_str = vat.group(1).strip().strip("'\"")
            vat_dt = datetime.fromisoformat(vat_str)
            if vat_dt.tzinfo is None:
                vat_dt = vat_dt.replace(tzinfo=timezone.utc)
            vat_ts = vat_dt.timestamp()
        except (ValueError, TypeError):
            return False  # unparsbares validated_at → fail-safe block
        if vat_ts < mail_mtime:
            return False  # Log aelter als letzte Mail-Datei-Aenderung → stale
        return True
    return False


def _block(msg: str) -> None:
    print("=" * 70, file=sys.stderr)
    print("BLOCKED - Renderer-Mail-Gate (#811)", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print(msg, file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    sys.exit(2)


def _do_record(repo: Path, shared: Path, name: str) -> None:
    """record-matrix: Hash der gestagten Mail-Dateien in den State schreiben."""
    if not name:
        print("record-matrix: GZ_ACTIVE_WORKFLOW nicht gesetzt.", file=sys.stderr)
        sys.exit(2)
    path = _state_path(shared, name)
    if not path.exists():
        print(f"record-matrix: Workflow-State fehlt: {path}", file=sys.stderr)
        sys.exit(2)
    staged = _staged_files(repo)
    mail_hash = _staged_mail_hash(repo, staged)
    state = json.loads(path.read_text())
    state.setdefault("gates", {}).setdefault("renderer_mail", {})["matrix"] = {
        "passed": True,
        "mail_files_hash": mail_hash,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(state, indent=2))
    sys.exit(0)


def _do_hook(repo: Path, shared: Path, name: str) -> None:
    tool_input = _read_tool_input()
    command = tool_input.get("command", "")
    if "git commit" not in command:
        sys.exit(0)

    staged = _staged_files(repo)
    mail_staged = [f for f in staged if _is_mail_file(f)]
    if not mail_staged:
        sys.exit(0)  # keine Mail-Inhalts-Datei → no-op

    if not name:
        _block(
            "Keine aktive Workflow-Identitaet (GZ_ACTIVE_WORKFLOW). "
            "Mail-Inhalts-Aenderung erfordert einen aktiven Workflow mit Nachweis."
        )
    path = _state_path(shared, name)
    if not path.exists():
        _block(f"Workflow-State fehlt: {path}")
    try:
        state = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        _block(f"Workflow-State unlesbar: {path}")

    matrix = (
        state.get("gates", {}).get("renderer_mail", {}).get("matrix", {})
    )
    expected = _staged_mail_hash(repo, staged)
    matrix_ok = (
        matrix.get("passed") is True
        and matrix.get("mail_files_hash") == expected
    )
    validator_ok = _validator_log_ok(shared, name, repo, staged)

    if matrix_ok and validator_ok:
        sys.exit(0)

    missing = []
    if not matrix_ok:
        missing.append(
            "  - Matrix-Test-Nachweis fehlt/veraltet (Hash passt nicht zum "
            "gestagten Mail-Stand).\n"
            "    Abhilfe: uv run pytest tests/tdd/test_issue_811_mode_matrix.py "
            "(schreibt den Nachweis bei gruenem Lauf)."
        )
    if not validator_ok:
        missing.append(
            "  - briefing_mail_validator.py-Erfolgsnachweis fehlt.\n"
            "    Abhilfe: uv run python3 .claude/hooks/briefing_mail_validator.py "
            "gegen die echt zugestellte Mail (Exit 0)."
        )
    _block(
        "Mail-Inhalts-Datei(en) gestaged, aber Nachweise unvollstaendig:\n"
        + "\n".join(missing)
    )


def main() -> None:
    repo = _repo_root()
    shared = _shared_repo_root()
    name = _active_workflow_name()
    if len(sys.argv) > 1 and sys.argv[1] == "record-matrix":
        _do_record(repo, shared, name)
    else:
        _do_hook(repo, shared, name)


if __name__ == "__main__":
    main()
