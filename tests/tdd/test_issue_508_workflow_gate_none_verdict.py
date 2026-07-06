"""TDD RED: Tests für Issue #508 — Workflow Gate: None-Verdict blockiert Commit.

Alle Tests laufen gegen echten Code (keine Mocks).
Subprocess-Tests nutzen On-Disk-Workflow-JSON-Files in tmp_path.

Spec: docs/specs/modules/issue_508_workflow_gate_none_verdict.md
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


HOOKS_DIR = Path("/home/hem/gregor_zwanzig/.claude/hooks")
PRE_COMMIT_GATE_PY = HOOKS_DIR / "pre_commit_gate.py"
WORKFLOW_PY = HOOKS_DIR / "workflow.py"

sys.path.insert(0, str(HOOKS_DIR))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_repo(tmp_path: Path) -> Path:
    """Minimales Fake-Repo mit .git + .claude/workflows/_log/ + openspec.yaml."""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".claude" / "workflows" / "_log").mkdir(parents=True)
    (tmp_path / "openspec.yaml").write_text(
        "project:\n  name: test\n"
        "workflow:\n  spec_auto_advance: true\n"
        "protected_paths: []\n"
    )
    return tmp_path


def _run_workflow(args: list[str], tmp_path: Path, session_id: str = "test-508") -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CLAUDE_CODE_SESSION_ID"] = session_id
    for k in ("GZ_ACTIVE_WORKFLOW", "GZ_HOOK_SESSION_ID"):
        env.pop(k, None)
    return subprocess.run(
        [sys.executable, str(WORKFLOW_PY)] + args,
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )


def _start_and_patch_workflow(
    tmp_path: Path,
    name: str,
    verdict: str | None,
    include_phase6b: bool,
    session_id: str,
) -> None:
    """Startet einen echten Workflow via workflow.py start, dann patcht verdict + transitions."""
    r = _run_workflow(["start", name], tmp_path, session_id=session_id)
    assert r.returncode == 0, f"workflow start failed: {r.stderr}"

    wf_file = tmp_path / ".claude" / "workflows" / f"{name}.json"
    data = json.loads(wf_file.read_text())

    if include_phase6b:
        data["phase_transitions"] = [
            {"from": "phase4_approved", "to": "phase6_implement", "at": "2026-06-01T10:00:00", "trigger": "command"},
            {"from": "phase6_implement", "to": "phase6b_adversary", "at": "2026-06-01T11:00:00", "trigger": "command"},
            {"from": "phase6b_adversary", "to": "phase7_validate", "at": "2026-06-01T12:00:00", "trigger": "command"},
        ]
    else:
        data["phase_transitions"] = [
            {"from": "phase1_context", "to": "phase3_spec", "at": "2026-06-01T10:00:00", "trigger": "command"},
            {"from": "phase3_spec", "to": "phase4_approved", "at": "2026-06-01T10:05:00", "trigger": "user_keyword"},
        ]

    data["adversary_verdict"] = verdict
    data["current_phase"] = "phase6_implement"
    wf_file.write_text(json.dumps(data))


def _workflow_data_with_phase6b(verdict: str | None) -> dict:
    """Workflow-State mit phase6b in Transitions."""
    return {
        "name": "test-wf",
        "current_phase": "phase6_implement",
        "adversary_verdict": verdict,
        "phase_transitions": [
            {"from": "phase4_approved", "to": "phase6_implement", "at": "2026-06-01T10:00:00", "trigger": "command"},
            {"from": "phase6_implement", "to": "phase6b_adversary", "at": "2026-06-01T11:00:00", "trigger": "command"},
            {"from": "phase6b_adversary", "to": "phase7_validate", "at": "2026-06-01T12:00:00", "trigger": "command"},
        ],
        "adversary_findings_total": 0,
        "fix_loop_iterations": 0,
        "affected_files": [],
    }


def _workflow_data_without_phase6b(verdict: str | None) -> dict:
    """Workflow-State OHNE phase6b in Transitions (Infra/Doku-Workflow)."""
    return {
        "name": "test-wf-infra",
        "current_phase": "phase6_implement",
        "adversary_verdict": verdict,
        "phase_transitions": [
            {"from": "phase1_context", "to": "phase3_spec", "at": "2026-06-01T10:00:00", "trigger": "command"},
            {"from": "phase3_spec", "to": "phase4_approved", "at": "2026-06-01T10:05:00", "trigger": "user_keyword"},
            {"from": "phase4_approved", "to": "phase6_implement", "at": "2026-06-01T10:06:00", "trigger": "command"},
        ],
        "adversary_findings_total": 0,
        "fix_loop_iterations": 0,
        "affected_files": [],
    }


# ---------------------------------------------------------------------------
# AC-1: None-Verdict + phase6b → Gate blockt
# ---------------------------------------------------------------------------

class TestNoneVerdictGateBlocks:
    """AC-1: None-Verdict + phase6b in Transitions → _check_none_verdict_block gibt (False, reason)."""

    def test_none_verdict_with_phase6b_is_blocked(self):
        """
        GIVEN: Workflow hat phase6b in Transitions, adversary_verdict = None
        WHEN:  _check_none_verdict_block aufgerufen
        THEN:  gibt (False, ...) zurück mit "qa_gate" im Reason
        """
        from pre_commit_gate import _check_none_verdict_block  # existiert noch nicht → ImportError

        data = _workflow_data_with_phase6b(verdict=None)
        allowed, reason = _check_none_verdict_block(data)

        assert allowed is False
        assert "qa_gate" in reason.lower() or "adversary" in reason.lower()

    def test_none_verdict_with_phase6b_reason_contains_command(self):
        """
        GIVEN: None-Verdict + phase6b
        WHEN:  _check_none_verdict_block aufgerufen
        THEN:  Reason enthält den konkreten qa_gate.py-Aufruf
        """
        from pre_commit_gate import _check_none_verdict_block

        data = _workflow_data_with_phase6b(verdict=None)
        _, reason = _check_none_verdict_block(data)

        assert "qa_gate.py" in reason


# ---------------------------------------------------------------------------
# AC-2: None-Verdict OHNE phase6b → Gate lässt durch
# ---------------------------------------------------------------------------

class TestNoneVerdictWithoutPhase6bAllowed:
    """AC-2: None-Verdict aber KEINE phase6b-Transition → kein Block."""

    def test_none_verdict_without_phase6b_is_allowed(self):
        """
        GIVEN: Workflow hat KEINE phase6b-Transition, adversary_verdict = None
        WHEN:  _check_none_verdict_block aufgerufen
        THEN:  gibt (True, ...) zurück
        """
        from pre_commit_gate import _check_none_verdict_block

        data = _workflow_data_without_phase6b(verdict=None)
        allowed, reason = _check_none_verdict_block(data)

        assert allowed is True

    def test_empty_transitions_is_allowed(self):
        """
        GIVEN: phase_transitions leer (sehr alter Workflow), verdict = None
        WHEN:  _check_none_verdict_block aufgerufen
        THEN:  gibt (True, ...) zurück — kein False-Positive
        """
        from pre_commit_gate import _check_none_verdict_block

        data = {"adversary_verdict": None, "phase_transitions": []}
        allowed, _ = _check_none_verdict_block(data)

        assert allowed is True

    def test_missing_transitions_key_is_allowed(self):
        """
        GIVEN: phase_transitions fehlt komplett (leerer State)
        WHEN:  _check_none_verdict_block aufgerufen
        THEN:  gibt (True, ...) zurück — kein Absturz, kein False-Positive
        """
        from pre_commit_gate import _check_none_verdict_block

        data = {"adversary_verdict": None}
        allowed, _ = _check_none_verdict_block(data)

        assert allowed is True


# ---------------------------------------------------------------------------
# AC-3: VERIFIED-Verdict + phase6b → Gate lässt durch
# ---------------------------------------------------------------------------

class TestVerifiedVerdictAllowed:
    """AC-3: VERIFIED-Verdict → kein Block, egal ob phase6b lief."""

    def test_verified_verdict_with_phase6b_is_allowed(self):
        """
        GIVEN: Workflow hat phase6b, adversary_verdict = "VERIFIED"
        WHEN:  _check_none_verdict_block aufgerufen
        THEN:  gibt (True, ...) zurück
        """
        from pre_commit_gate import _check_none_verdict_block

        data = _workflow_data_with_phase6b(verdict="VERIFIED")
        allowed, reason = _check_none_verdict_block(data)

        assert allowed is True

    def test_broken_verdict_with_phase6b_is_blocked(self):
        """
        GIVEN: adversary_verdict = "BROKEN"
        WHEN:  _check_none_verdict_block aufgerufen
        THEN:  gibt (False, ...) zurück — BROKEN soll ebenfalls blockieren
        """
        from pre_commit_gate import _check_none_verdict_block

        data = _workflow_data_with_phase6b(verdict="BROKEN")
        allowed, reason = _check_none_verdict_block(data)

        assert allowed is False
        assert "broken" in reason.lower()


# ---------------------------------------------------------------------------
# AC-4: workflow.py write-log warnt bei None + phase6b (subprocess)
# ---------------------------------------------------------------------------

class TestWriteLogWarnsOnNoneVerdict:
    """AC-4: write-log gibt WARNING auf stderr wenn Verdict fehlt und phase6b lief."""

    def test_write_log_warns_when_verdict_none_and_phase6b_ran(self, tmp_path):
        """
        GIVEN: Workflow mit phase6b-Transition, adversary_verdict = null
        WHEN:  workflow.py write-log success
        THEN:  stderr enthält "WARNING" und "qa_gate"
        """
        repo = _setup_repo(tmp_path)
        sid = "test-508-writelog"
        name = "wf-none-verdict"
        _start_and_patch_workflow(repo, name, verdict=None, include_phase6b=True, session_id=sid)

        result = _run_workflow(["write-log", "success"], repo, session_id=sid)

        assert "WARNING" in result.stderr or "warning" in result.stderr.lower(), (
            f"Expected WARNING in stderr, got:\nstdout={result.stdout}\nstderr={result.stderr}"
        )
        assert "qa_gate" in result.stderr, (
            f"Expected qa_gate.py hint in stderr, got:\nstdout={result.stdout}\nstderr={result.stderr}"
        )

    def test_write_log_still_writes_log_despite_warning(self, tmp_path):
        """
        GIVEN: None-Verdict + phase6b
        WHEN:  workflow.py write-log success
        THEN:  Log-Datei wird trotzdem geschrieben (kein harter Block)
        """
        repo = _setup_repo(tmp_path)
        sid = "test-508-logwrite"
        name = "wf-none-log-written"
        _start_and_patch_workflow(repo, name, verdict=None, include_phase6b=True, session_id=sid)

        _run_workflow(["write-log", "success"], repo, session_id=sid)

        log_dir = repo / ".claude" / "workflows" / "_log"
        log_files = list(log_dir.glob(f"*_{name}.yaml"))
        assert len(log_files) == 1, f"Expected log file, found: {log_files}"


# ---------------------------------------------------------------------------
# AC-5: workflow.py write-log schweigt bei VERIFIED
# ---------------------------------------------------------------------------

class TestWriteLogSilentOnVerified:
    """AC-5: write-log gibt KEINE WARNING wenn Verdict = VERIFIED."""

    def test_write_log_no_warning_when_verified(self, tmp_path):
        """
        GIVEN: Workflow mit phase6b, adversary_verdict = "VERIFIED"
        WHEN:  workflow.py write-log success
        THEN:  stderr enthält KEIN "WARNING" bezüglich Verdict
        """
        repo = _setup_repo(tmp_path)
        sid = "test-508-verified"
        name = "wf-verified"
        _start_and_patch_workflow(repo, name, verdict="VERIFIED", include_phase6b=True, session_id=sid)

        result = _run_workflow(["write-log", "success"], repo, session_id=sid)

        verdict_warning = any(
            "qa_gate" in line.lower() or ("warning" in line.lower() and "verdict" in line.lower())
            for line in result.stderr.splitlines()
        )
        assert not verdict_warning, (
            f"Unexpected verdict WARNING for VERIFIED workflow:\nstdout={result.stdout}\nstderr={result.stderr}"
        )

    def test_write_log_no_warning_when_no_phase6b(self, tmp_path):
        """
        GIVEN: Workflow OHNE phase6b-Transition, verdict = None (Infra-Workflow)
        WHEN:  workflow.py write-log success
        THEN:  stderr enthält KEINE qa_gate-Warnung
        """
        repo = _setup_repo(tmp_path)
        sid = "test-508-infra"
        name = "wf-infra-no-phase6b"
        _start_and_patch_workflow(repo, name, verdict=None, include_phase6b=False, session_id=sid)

        result = _run_workflow(["write-log", "success"], repo, session_id=sid)

        assert "qa_gate" not in result.stderr, (
            f"Unexpected qa_gate warning for infra workflow:\nstdout={result.stdout}\nstderr={result.stderr}"
        )
