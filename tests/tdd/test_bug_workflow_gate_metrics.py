"""TDD RED: Tests für bug-workflow-gate-metrics — Gate-History, Debug-Logs.

Alle Tests nutzen subprocess gegen echte On-Disk-Workflow-JSON-Files in tmp_path.
Keine Mocks.

Spec: docs/specs/modules/bug_workflow_gate_metrics.md
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

WORKFLOW_PY = Path("/home/hem/gregor_zwanzig/.claude/hooks/workflow.py")
UPDATER_PY = Path("/home/hem/gregor_zwanzig/.claude/hooks/workflow_state_updater.py")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(args: list[str], cwd: Path, extra_env: dict | None = None) -> subprocess.CompletedProcess:
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


def _run_updater(stdin_payload: dict, cwd: Path, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    for k in ("GZ_ACTIVE_WORKFLOW", "GZ_HOOK_SESSION_ID", "CLAUDE_CODE_SESSION_ID"):
        env.pop(k, None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(UPDATER_PY)],
        cwd=str(cwd),
        input=json.dumps(stdin_payload),
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )


def _setup_repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".claude" / "workflows" / "_log").mkdir(parents=True)
    (tmp_path / "openspec.yaml").write_text(
        "project:\n  name: test\nworkflow:\n  spec_auto_advance: false\nprotected_paths: []\n"
    )
    return tmp_path


def _start_workflow(tmp_path: Path, name: str, session_id: str = "test-session-001") -> None:
    result = _run(["start", name], tmp_path, extra_env={"CLAUDE_CODE_SESSION_ID": session_id})
    assert result.returncode == 0, f"start fehlgeschlagen: {result.stderr}"


def _write_log(tmp_path: Path, name: str) -> subprocess.CompletedProcess:
    return _run(
        ["write-log", "success"],
        tmp_path,
        extra_env={"GZ_ACTIVE_WORKFLOW": name},
    )


def _read_last_log(tmp_path: Path, name: str) -> dict:
    log_dir = tmp_path / ".claude" / "workflows" / "_log"
    logs = sorted(log_dir.glob(f"*_{name}.yaml"))
    assert logs, f"Kein Log für {name} in {log_dir}"
    return yaml.safe_load(logs[-1].read_text())


def _inject_transitions(tmp_path: Path, name: str, transitions: list[dict]) -> None:
    wf_path = tmp_path / ".claude" / "workflows" / f"{name}.json"
    data = json.loads(wf_path.read_text())
    data["phase_transitions"] = transitions
    wf_path.write_text(json.dumps(data))


# ---------------------------------------------------------------------------
# AC-1: write-log enthält gate_history mit user_approved für spec_approval
# ---------------------------------------------------------------------------

def test_ac1_gate_history_user_approved_in_log(tmp_path):
    """AC-1: Workflow mit user_keyword-Transition phase3→phase4 → gate_history.spec_approval=user_approved."""
    _setup_repo(tmp_path)
    _start_workflow(tmp_path, "wf-ac1")
    _inject_transitions(tmp_path, "wf-ac1", [
        {"from": "phase1_context", "to": "phase2_analyse", "at": "2026-06-04T10:00:00", "trigger": "command"},
        {"from": "phase2_analyse", "to": "phase3_spec", "at": "2026-06-04T10:01:00", "trigger": "command"},
        {"from": "phase3_spec", "to": "phase4_approved", "at": "2026-06-04T10:05:00", "trigger": "user_keyword"},
        {"from": "phase4_approved", "to": "phase5_tdd_red", "at": "2026-06-04T10:06:00", "trigger": "command"},
        {"from": "phase5_tdd_red", "to": "phase6_implement", "at": "2026-06-04T10:10:00", "trigger": "command"},
        {"from": "phase6_implement", "to": "phase6b_adversary", "at": "2026-06-04T10:20:00", "trigger": "command"},
    ])

    result = _write_log(tmp_path, "wf-ac1")
    assert result.returncode == 0, f"write-log fehlgeschlagen: {result.stderr}"

    log = _read_last_log(tmp_path, "wf-ac1")
    assert "gate_history" in log, "gate_history fehlt im YAML-Log"

    gh = log["gate_history"]
    assert "spec_approval" in gh, "spec_approval fehlt in gate_history"
    assert gh["spec_approval"]["status"] == "user_approved", (
        f"Erwartet user_approved, bekommen: {gh['spec_approval']['status']}"
    )
    assert gh["spec_approval"]["trigger"] == "user_keyword"
    assert gh["spec_approval"]["at"] is not None


# ---------------------------------------------------------------------------
# AC-2: bypassed Gate → status=bypassed + gate_anomalies=1
# ---------------------------------------------------------------------------

def test_ac2_gate_history_bypassed_when_command_trigger(tmp_path):
    """AC-2: phase3→phase5 direkt (trigger=command, kein phase4) → spec_approval=bypassed, gate_anomalies=1."""
    _setup_repo(tmp_path)
    _start_workflow(tmp_path, "wf-ac2")
    _inject_transitions(tmp_path, "wf-ac2", [
        {"from": "phase1_context", "to": "phase2_analyse", "at": "2026-06-04T10:00:00", "trigger": "command"},
        {"from": "phase2_analyse", "to": "phase3_spec", "at": "2026-06-04T10:01:00", "trigger": "command"},
        {"from": "phase3_spec", "to": "phase5_tdd_red", "at": "2026-06-04T10:03:00", "trigger": "command"},
        {"from": "phase5_tdd_red", "to": "phase6b_adversary", "at": "2026-06-04T10:15:00", "trigger": "command"},
    ])

    result = _write_log(tmp_path, "wf-ac2")
    assert result.returncode == 0

    log = _read_last_log(tmp_path, "wf-ac2")
    assert "gate_history" in log

    gh = log["gate_history"]
    assert gh["spec_approval"]["status"] == "bypassed", (
        f"Erwartet bypassed, bekommen: {gh['spec_approval']['status']}"
    )

    assert "gate_anomalies" in log, "gate_anomalies fehlt im Log"
    assert log["gate_anomalies"] == 1, f"Erwartet 1 Anomalie, bekommen: {log['gate_anomalies']}"


# ---------------------------------------------------------------------------
# AC-3: workflow.py gates gibt Status für alle 3 Gates aus
# ---------------------------------------------------------------------------

def test_ac3_gates_command_shows_all_three_gates(tmp_path):
    """AC-3: `workflow.py gates` gibt Status für alle 3 Gate-Punkte aus."""
    _setup_repo(tmp_path)
    _start_workflow(tmp_path, "wf-ac3")
    _inject_transitions(tmp_path, "wf-ac3", [
        {"from": "phase2_analyse", "to": "phase3_spec", "at": "2026-06-04T10:01:00", "trigger": "command"},
        {"from": "phase3_spec", "to": "phase4_approved", "at": "2026-06-04T10:05:00", "trigger": "user_keyword"},
    ])

    result = _run(["gates"], tmp_path, extra_env={"GZ_ACTIVE_WORKFLOW": "wf-ac3"})
    assert result.returncode == 0, f"gates fehlgeschlagen: {result.stderr}"

    output = result.stdout
    assert "analyse_summary" in output, "analyse_summary fehlt in gates-Output"
    assert "spec_approval" in output, "spec_approval fehlt in gates-Output"
    assert "deploy_approval" in output, "deploy_approval fehlt in gates-Output"

    assert "user_approved" in output, "user_approved fehlt für spec_approval"

    assert "not_reached" in output.lower() or "NOT REACHED" in output, (
        "not_reached fehlt für deploy_approval"
    )


# ---------------------------------------------------------------------------
# AC-4: Debug-Ausgabe in workflow_state_updater.py wenn "go" kein Gate auslöst
# ---------------------------------------------------------------------------

def test_ac4_debug_output_when_go_has_no_effect(tmp_path):
    """AC-4: 'go' in phase2_analyse (kein Gate-Trigger) → stderr zeigt [DEBUG go]-Zeile."""
    _setup_repo(tmp_path)
    _start_workflow(tmp_path, "wf-ac4")
    _inject_transitions(tmp_path, "wf-ac4", [
        {"from": "phase1_context", "to": "phase2_analyse", "at": "2026-06-04T10:00:00", "trigger": "command"},
    ])
    wf_path = tmp_path / ".claude" / "workflows" / "wf-ac4.json"
    data = json.loads(wf_path.read_text())
    data["current_phase"] = "phase2_analyse"
    wf_path.write_text(json.dumps(data))

    result = _run_updater(
        {"user_prompt": "go", "session_id": "test-session-ac4"},
        tmp_path,
        extra_env={"GZ_ACTIVE_WORKFLOW": "wf-ac4", "CLAUDE_CODE_SESSION_ID": "test-session-ac4"},
    )

    assert result.returncode == 0, f"updater crashed: {result.stderr}"
    assert "[DEBUG go]" in result.stderr, (
        f"[DEBUG go] Zeile fehlt in stderr:\n{result.stderr!r}"
    )
