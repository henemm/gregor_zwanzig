"""TDD RED: Tests für Issue #465 — Workflow-Optimierung: Typen, Auto-Advance, Observability.

Alle Tests nutzen subprocess gegen echte On-Disk-Workflow-JSON-Files in tmp_path.
Keine Mocks.

Spec: docs/specs/modules/issue_465_workflow_optimierung.md
Test-Manifest: docs/specs/tests/issue_465_workflow_optimierung_tests.md
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest
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


def _read_workflow(tmp_path: Path, name: str) -> dict:
    p = tmp_path / ".claude" / "workflows" / f"{name}.json"
    return json.loads(p.read_text())


def _start_workflow(tmp_path: Path, name: str, extra_args: list[str] | None = None,
                    session_id: str = "test-session-001") -> subprocess.CompletedProcess:
    args = ["start", name] + (extra_args or [])
    return _run(args, tmp_path, extra_env={"CLAUDE_CODE_SESSION_ID": session_id})


def _write_sample_log(log_dir: Path, name: str, verdict: str = "VERIFIED") -> None:
    """Schreibt ein minimales Execution-Log YAML für Stats-Tests."""
    data = {
        "workflow_id": name,
        "project": "test",
        "completed_at": datetime.now().isoformat(),
        "phases_completed": ["phase1_context", "phase6_implement"],
        "phases_skipped": [],
        "override_used": False,
        "tdd_red_confirmed": True,
        "adversary_verdict": verdict,
        "adversary_findings_total": 0,
        "adversary_fix_loop_iterations": 0,
        "scope_files_changed": 3,
        "scope_loc_delta": "+42",
        "outcome": "success",
        "workflow_type": "feature",
    }
    (log_dir / f"2026-05-30_{name}.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True)
    )


# ---------------------------------------------------------------------------
# AC-1: --type bugfix → phase4_approved + skip-Transitions
# ---------------------------------------------------------------------------

def test_ac1_start_type_bugfix_sets_phase4_approved(tmp_path):
    """AC-1: workflow.py start <name> --type bugfix setzt current_phase=phase4_approved
    und legt Skip-Transitions für Phasen 1–3 an.
    """
    _setup_repo(tmp_path)
    result = _start_workflow(tmp_path, "my-fix", ["--type", "bugfix"])

    assert result.returncode == 0, f"start --type bugfix schlug fehl:\n{result.stderr}"

    wf = _read_workflow(tmp_path, "my-fix")

    assert wf.get("workflow_type") == "bugfix", (
        f"workflow_type erwartet 'bugfix', got: {wf.get('workflow_type')!r}"
    )
    assert wf.get("current_phase") == "phase4_approved", (
        f"current_phase erwartet 'phase4_approved', got: {wf.get('current_phase')!r}"
    )
    transitions = wf.get("phase_transitions", [])
    skip_triggers = [t for t in transitions if "type_skip" in t.get("trigger", "")]
    assert len(skip_triggers) >= 3, (
        f"Erwarte >= 3 Skip-Transitions, got: {len(skip_triggers)}\n"
        f"Transitions: {json.dumps(transitions, indent=2)}"
    )


# ---------------------------------------------------------------------------
# AC-2: --type docs → phase3_spec + korrekte Skips
# ---------------------------------------------------------------------------

def test_ac2_start_type_docs_sets_phase3_spec(tmp_path):
    """AC-2: workflow.py start <name> --type docs setzt current_phase=phase3_spec
    und legt Skips für Phasen 1+2 sowie 5+6b+7 an.
    """
    _setup_repo(tmp_path)
    result = _start_workflow(tmp_path, "my-doc", ["--type", "docs"])

    assert result.returncode == 0, f"start --type docs schlug fehl:\n{result.stderr}"

    wf = _read_workflow(tmp_path, "my-doc")

    assert wf.get("workflow_type") == "docs", (
        f"workflow_type erwartet 'docs', got: {wf.get('workflow_type')!r}"
    )
    assert wf.get("current_phase") == "phase3_spec", (
        f"current_phase erwartet 'phase3_spec', got: {wf.get('current_phase')!r}"
    )
    transitions = wf.get("phase_transitions", [])
    skipped_targets = {t.get("to") for t in transitions if "type_skip" in t.get("trigger", "")}
    assert "phase1_context" in skipped_targets, (
        f"phase1_context nicht in Skip-Targets: {skipped_targets}"
    )
    assert "phase2_analyse" in skipped_targets, (
        f"phase2_analyse nicht in Skip-Targets: {skipped_targets}"
    )
    # Auch diese müssen in den Skips sein:
    assert "phase5_tdd_red" in skipped_targets, (
        f"phase5_tdd_red nicht in Skip-Targets: {skipped_targets}"
    )
    assert "phase6b_adversary" in skipped_targets, (
        f"phase6b_adversary nicht in Skip-Targets: {skipped_targets}"
    )
    assert "phase7_validate" in skipped_targets, (
        f"phase7_validate nicht in Skip-Targets: {skipped_targets}"
    )


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
# AC-4: workflow.py stats — Verdict-Ausgabe
# ---------------------------------------------------------------------------

def test_ac4_stats_shows_verdict_distribution(tmp_path):
    """AC-4: workflow.py stats zeigt Verdict-Verteilung mit absoluten Zahlen."""
    _setup_repo(tmp_path)
    log_dir = tmp_path / ".claude" / "workflows" / "_log"
    _write_sample_log(log_dir, "wf-001", "VERIFIED")
    _write_sample_log(log_dir, "wf-002", "BROKEN")
    _write_sample_log(log_dir, "wf-003", "VERIFIED")

    result = _run(["stats"], tmp_path)

    assert result.returncode == 0, f"stats schlug fehl:\n{result.stderr}"
    output = result.stdout
    assert "VERIFIED" in output, f"'VERIFIED' nicht in Ausgabe:\n{output}"
    assert "BROKEN" in output, f"'BROKEN' nicht in Ausgabe:\n{output}"


# ---------------------------------------------------------------------------
# AC-5: workflow.py stats --json → valides JSON
# ---------------------------------------------------------------------------

def test_ac5_stats_json_flag_outputs_valid_json(tmp_path):
    """AC-5: workflow.py stats --json gibt valides JSON mit den erwarteten Schlüsseln."""
    _setup_repo(tmp_path)
    log_dir = tmp_path / ".claude" / "workflows" / "_log"
    _write_sample_log(log_dir, "wf-a", "VERIFIED")

    result = _run(["stats", "--json"], tmp_path)

    assert result.returncode == 0, f"stats --json schlug fehl:\n{result.stderr}"

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        pytest.fail(f"stdout ist kein valides JSON: {e}\nstdout: {result.stdout!r}")

    for key in ("total_workflows", "verdicts", "verdict_rate"):
        assert key in data, (
            f"Schlüssel '{key}' fehlt in JSON-Ausgabe: {list(data.keys())}"
        )


# ---------------------------------------------------------------------------
# AC-6: auto-advance-spec + Flag=true → Phase1→Phase2
# ---------------------------------------------------------------------------

def test_ac6_auto_advance_spec_advances_from_phase1(tmp_path):
    """AC-6: auto-advance-spec wechselt von phase1_context zu phase2_analyse
    wenn spec_auto_advance=true; Transition erhält trigger=auto:spec_advance.
    """
    _setup_repo(tmp_path, spec_auto_advance=True)
    _start_workflow(tmp_path, "my-feature")

    wf = _read_workflow(tmp_path, "my-feature")
    assert wf.get("current_phase") == "phase1_context", (
        f"Vorbedingung: muss in phase1_context starten, got: {wf.get('current_phase')!r}"
    )

    result = _run(
        ["auto-advance-spec"],
        tmp_path,
        extra_env={"CLAUDE_CODE_SESSION_ID": "test-session-001"},
    )

    assert result.returncode == 0, f"auto-advance-spec schlug fehl:\n{result.stderr}"

    wf = _read_workflow(tmp_path, "my-feature")
    assert wf.get("current_phase") == "phase2_analyse", (
        f"current_phase erwartet 'phase2_analyse', got: {wf.get('current_phase')!r}"
    )
    transitions = wf.get("phase_transitions", [])
    auto_triggers = [t for t in transitions if t.get("trigger") == "auto:spec_advance"]
    assert len(auto_triggers) >= 1, (
        f"Erwarte Transition mit trigger='auto:spec_advance'.\n"
        f"Transitions: {json.dumps(transitions, indent=2)}"
    )


# ---------------------------------------------------------------------------
# AC-7: auto-advance-spec + Flag=false → kein-op
# ---------------------------------------------------------------------------

def test_ac7_auto_advance_spec_noop_when_flag_false(tmp_path):
    """AC-7: auto-advance-spec ist kein-op wenn spec_auto_advance=false."""
    _setup_repo(tmp_path, spec_auto_advance=False)
    _start_workflow(tmp_path, "my-feature-noadv", session_id="test-session-002")

    result = _run(
        ["auto-advance-spec"],
        tmp_path,
        extra_env={"CLAUDE_CODE_SESSION_ID": "test-session-002"},
    )

    assert result.returncode == 0, f"auto-advance-spec schlug fehl:\n{result.stderr}"

    wf = _read_workflow(tmp_path, "my-feature-noadv")
    assert wf.get("current_phase") == "phase1_context", (
        f"Phase darf sich nicht ändern wenn Flag false, got: {wf.get('current_phase')!r}"
    )


# ---------------------------------------------------------------------------
# AC-9: write-log enthält phase_durations und workflow_type
# ---------------------------------------------------------------------------

def test_ac9_write_log_contains_phase_durations(tmp_path):
    """AC-9: write-log schreibt phase_durations (Dict mit positiven Werten) und workflow_type."""
    _setup_repo(tmp_path)
    session_id = "test-session-ac9"

    _start_workflow(tmp_path, "my-obs-wf", session_id=session_id)

    _run(["phase", "phase2_analyse", "--trigger=command"], tmp_path,
         extra_env={"CLAUDE_CODE_SESSION_ID": session_id})
    time.sleep(0.05)
    _run(["phase", "phase3_spec", "--trigger=command"], tmp_path,
         extra_env={"CLAUDE_CODE_SESSION_ID": session_id})

    result = _run(["write-log", "success"], tmp_path,
                  extra_env={"CLAUDE_CODE_SESSION_ID": session_id})
    assert result.returncode == 0, f"write-log schlug fehl:\n{result.stderr}"

    log_dir = tmp_path / ".claude" / "workflows" / "_log"
    log_files = [f for f in log_dir.glob("*.yaml") if "email_validation" not in f.name]
    assert len(log_files) >= 1, f"Kein Log-File in {log_dir}"

    log_data = yaml.safe_load(log_files[0].read_text())

    assert "phase_durations" in log_data, (
        f"Schlüssel 'phase_durations' fehlt.\nLog: {log_data}"
    )
    assert isinstance(log_data["phase_durations"], dict), (
        f"'phase_durations' muss dict sein, got: {type(log_data['phase_durations'])}"
    )
    assert len(log_data["phase_durations"]) >= 1, (
        f"'phase_durations' muss >= 1 Eintrag haben: {log_data['phase_durations']}"
    )
    for val in log_data["phase_durations"].values():
        assert isinstance(val, int) and val >= 0, (
            f"Dauer muss nicht-negativer Integer sein, got: {val!r}"
        )
    assert "workflow_type" in log_data, (
        f"Schlüssel 'workflow_type' fehlt.\nLog: {log_data}"
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
