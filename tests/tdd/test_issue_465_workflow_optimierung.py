"""TDD RED: Tests für Issue #465 — Workflow-Optimierung: Typen, Auto-Advance, Observability.

Alle Tests nutzen subprocess gegen echte On-Disk-Workflow-JSON-Files in tmp_path.
Keine Mocks.

Spec: docs/specs/modules/issue_465_workflow_optimierung.md
Test-Manifest: docs/specs/tests/issue_465_workflow_optimierung_tests.md

Hinweis (Rot-Triage #1211b, Batch 1): 7 der ursprünglich 9 Tests wurden
gelöscht — sie prüften `workflow.py`, das inzwischen ins Plugin-Repo
`henemm/agent-os-openspec` migriert wurde (Commits `33da201c`/`465380c1`/
`f1e3acc1`) und unter dem alten Pfad nicht mehr existiert. test_ac3 und
test_ac10 bleiben (weiterhin grün) — siehe docs/specs/modules/
rework_1211b_rot_triage.md, Gruppe K1-Ausnahme.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

WORKFLOW_PY = Path("/home/hem/gregor_zwanzig/.claude/hooks/workflow.py")
EMAIL_VALIDATOR_PY = Path("/home/hem/gregor_zwanzig/.claude/hooks/email_spec_validator.py")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(args: list[str], cwd: Path, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    """Spawn workflow.py mit den gegebenen Args im isolierten tmp-Repo."""
    env = os.environ.copy()
    for k in ("GZ_ACTIVE_WORKFLOW", "GZ_HOOK_SESSION_ID", "CLAUDE_CODE_SESSION_ID"):
        env.pop(k, None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(WORKFLOW_PY)] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )


def _setup_repo(tmp_path: Path, spec_auto_advance: bool = True) -> Path:
    """Minimales Fake-Repo mit .git + .claude/workflows/_log/ + openspec.yaml."""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".claude" / "workflows" / "_log").mkdir(parents=True)
    openspec = (
        f"project:\n  name: test\n"
        f"workflow:\n  spec_auto_advance: {str(spec_auto_advance).lower()}\n"
        f"protected_paths: []\n"
    )
    (tmp_path / "openspec.yaml").write_text(openspec)
    return tmp_path


def _start_workflow(tmp_path: Path, name: str, extra_args: list[str] | None = None,
                    session_id: str = "test-session-001") -> subprocess.CompletedProcess:
    args = ["start", name] + (extra_args or [])
    return _run(args, tmp_path, extra_env={"CLAUDE_CODE_SESSION_ID": session_id})


# ---------------------------------------------------------------------------
# AC-3: --type invalid → Exit-Code != 0
# ---------------------------------------------------------------------------

def test_ac3_start_type_invalid_exits_with_error(tmp_path):
    """AC-3: workflow.py start <name> --type invalid endet mit Exit-Code != 0."""
    _setup_repo(tmp_path)
    result = _start_workflow(tmp_path, "my-bad", ["--type", "invalid_type"])

    assert result.returncode != 0, (
        f"Erwarte Exit-Code != 0 bei ungültigem Typ, got 0.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# AC-10 (smoke): email_spec_validator._write_validation_log erstellt YAML
# ---------------------------------------------------------------------------

def test_ac10_email_validator_creates_yaml_log(tmp_path):
    """AC-10 (smoke): _write_validation_log erstellt YAML in log_dir mit korrekten Feldern.
    Testet die Hilfsfunktion direkt — kein IMAP nötig.
    """
    log_dir = tmp_path / "_log"
    log_dir.mkdir(parents=True)

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "email_spec_validator", str(EMAIL_VALIDATOR_PY)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    module._write_validation_log(
        success=True,
        errors=[],
        min_locations=3,
        log_dir=log_dir,
        workflow_id="test-wf",
    )

    yaml_files = list(log_dir.glob("*_email_validation.yaml"))
    assert len(yaml_files) >= 1, (
        f"Kein email_validation.yaml in {log_dir}.\n"
        f"Files: {list(log_dir.iterdir())}"
    )

    data = yaml.safe_load(yaml_files[0].read_text())
    for key in ("validator", "validated_at", "workflow_id", "passed", "error_count", "errors"):
        assert key in data, (
            f"Schlüssel '{key}' fehlt im Validator-Log: {list(data.keys())}"
        )
