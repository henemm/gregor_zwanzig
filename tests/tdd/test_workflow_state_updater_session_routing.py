"""Integration test for workflow_state_updater.py session routing (Issue #332).

Verifies that the UserPromptSubmit hook respects the session-registry
(.claude/session_workflows.json) instead of falling back to the legacy
'last globally active workflow' field.

NO MOCKS: spawns the real hook via subprocess against an isolated
tmp_path repo, with real on-disk workflow JSON files and a real
session_workflows.json registry.

Spec: docs/specs/modules/bug_332_approval_hook_session_id.md
Test-Manifest: docs/specs/tests/bug_332_approval_hook_session_id_tests.md
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

import pytest


HOOK_PATH = Path("/home/hem/gregor_zwanzig/.claude/hooks/workflow_state_updater.py")


def _make_workflow_file(workflows_dir: Path, name: str, phase: str = "phase3_spec") -> Path:
    """Create a minimal workflow state file mirroring the real schema."""
    workflows_dir.mkdir(parents=True, exist_ok=True)
    wf = {
        "version": "3.0",
        "name": name,
        "current_phase": phase,
        "spec_approved": False,
        "phases_completed": [],
        "phase_transitions": [],
        "fix_loop_iterations": 0,
        "loc_delta": 0,
        "loc_limit_override": None,
        "test_artifacts": [],
        "adversary_verdict": None,
        "execution_log_written": False,
        "spec_file": f"docs/specs/modules/{name}.md",
        "created_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
    }
    p = workflows_dir / f"{name}.json"
    p.write_text(json.dumps(wf, indent=2))
    return p


def _setup_isolated_repo(tmp_path: Path) -> Path:
    """Create a self-contained fake repo with .git + .claude/workflows/."""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "workflows").mkdir()
    return tmp_path


def _run_hook(cwd: Path, payload: dict, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    """Spawn the real hook with the given stdin payload."""
    env = os.environ.copy()
    # Scrub interference from the host repo's workflow state.
    for k in ("GZ_ACTIVE_WORKFLOW", "GZ_HOOK_SESSION_ID", "CLAUDE_CODE_SESSION_ID",
              "CLAUDE_USER_PROMPT", "CLAUDE_TOOL_INPUT"):
        env.pop(k, None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(cwd),
        env=env,
        timeout=10,
    )


def _read_phase(workflow_file: Path) -> str:
    return json.loads(workflow_file.read_text())["current_phase"]


def _read_spec_approved(workflow_file: Path) -> bool:
    return json.loads(workflow_file.read_text()).get("spec_approved", False)


# A decoy workflow is added that sorts alphabetically BEFORE the real targets
# so the legacy-fallback ("first non-archived workflow") points to the decoy.
# This guarantees both AC-1 and AC-2 FAIL while the bug is present and only
# PASS once the session-registry is honoured.

# ---------------------------------------------------------------------------
# AC-1: session sid-a approves -> only target_a advances, target_b + decoy untouched
# ---------------------------------------------------------------------------
def test_ac1_session_a_approval_only_advances_workflow_a(tmp_path: Path) -> None:
    repo = _setup_isolated_repo(tmp_path)
    wf_decoy = _make_workflow_file(repo / ".claude" / "workflows", "aaa_decoy_legacy_fallback")
    wf_a = _make_workflow_file(repo / ".claude" / "workflows", "target_a")
    wf_b = _make_workflow_file(repo / ".claude" / "workflows", "target_b")
    registry = repo / ".claude" / "session_workflows.json"
    registry.write_text(json.dumps({
        "sid-a": "target_a",
        "sid-b": "target_b",
    }))

    proc = _run_hook(repo, {"session_id": "sid-a", "user_prompt": "approved"})

    assert proc.returncode == 0, f"hook failed: {proc.stderr}"
    assert _read_phase(wf_a) == "phase4_approved", "target_a should have advanced"
    assert _read_spec_approved(wf_a) is True
    assert _read_phase(wf_b) == "phase3_spec", "target_b must remain untouched"
    assert _read_spec_approved(wf_b) is False
    assert _read_phase(wf_decoy) == "phase3_spec", \
        "decoy must remain untouched — Bug-Beweis: bei Bug nimmt der Hook DIESEN per Legacy-Fallback"


# ---------------------------------------------------------------------------
# AC-2: session sid-b approves -> only target_b advances, target_a + decoy untouched
# ---------------------------------------------------------------------------
def test_ac2_session_b_approval_only_advances_workflow_b(tmp_path: Path) -> None:
    repo = _setup_isolated_repo(tmp_path)
    wf_decoy = _make_workflow_file(repo / ".claude" / "workflows", "aaa_decoy_legacy_fallback")
    wf_a = _make_workflow_file(repo / ".claude" / "workflows", "target_a")
    wf_b = _make_workflow_file(repo / ".claude" / "workflows", "target_b")
    registry = repo / ".claude" / "session_workflows.json"
    registry.write_text(json.dumps({
        "sid-a": "target_a",
        "sid-b": "target_b",
    }))

    proc = _run_hook(repo, {"session_id": "sid-b", "user_prompt": "approved"})

    assert proc.returncode == 0, f"hook failed: {proc.stderr}"
    assert _read_phase(wf_b) == "phase4_approved", "target_b should have advanced"
    assert _read_spec_approved(wf_b) is True
    assert _read_phase(wf_a) == "phase3_spec", "target_a must remain untouched"
    assert _read_spec_approved(wf_a) is False
    assert _read_phase(wf_decoy) == "phase3_spec", \
        "decoy must remain untouched"


# ---------------------------------------------------------------------------
# AC-3: single-session fallback via GZ_ACTIVE_WORKFLOW (no registry entry)
# ---------------------------------------------------------------------------
def test_ac3_single_session_fallback_via_env_var(tmp_path: Path) -> None:
    repo = _setup_isolated_repo(tmp_path)
    wf_solo = _make_workflow_file(repo / ".claude" / "workflows", "solo_workflow")
    # No session_workflows.json registry → falls through to env var.

    proc = _run_hook(
        repo,
        {"user_prompt": "approved"},  # no session_id in payload
        extra_env={"GZ_ACTIVE_WORKFLOW": "solo_workflow"},
    )

    assert proc.returncode == 0, f"hook failed: {proc.stderr}"
    assert _read_phase(wf_solo) == "phase4_approved", \
        "single-session fallback via env-var must still work"
    assert _read_spec_approved(wf_solo) is True


# ---------------------------------------------------------------------------
# AC-4: session-registry has PRECEDENCE over GZ_ACTIVE_WORKFLOW env-var
# ---------------------------------------------------------------------------
def test_ac4_session_registry_wins_over_env_var(tmp_path: Path) -> None:
    repo = _setup_isolated_repo(tmp_path)
    wf_a = _make_workflow_file(repo / ".claude" / "workflows", "session_a_workflow")
    wf_c = _make_workflow_file(repo / ".claude" / "workflows", "wrong_target_c")
    registry = repo / ".claude" / "session_workflows.json"
    registry.write_text(json.dumps({"sid-a": "session_a_workflow"}))

    proc = _run_hook(
        repo,
        {"session_id": "sid-a", "user_prompt": "approved"},
        extra_env={"GZ_ACTIVE_WORKFLOW": "wrong_target_c"},  # decoy
    )

    assert proc.returncode == 0, f"hook failed: {proc.stderr}"
    assert _read_phase(wf_a) == "phase4_approved", \
        "session-registry must win — workflow A should advance"
    assert _read_phase(wf_c) == "phase3_spec", \
        "env-var decoy workflow C must remain untouched"
