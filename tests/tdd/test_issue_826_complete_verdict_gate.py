"""TDD: Issue #826 AC-2 — Verdict-Pflicht beim Workflow-Abschluss (cmd_complete).

Beweist das tatsaechliche Verhalten von cmd_complete via echtem Subprocess gegen
On-Disk-Workflow-JSON in einem temporaeren Verzeichnis. Kein Mock.

Fall A (blockt):   phase6b lief + verdict=None  + Log vorhanden → sys.exit(1), NICHT archiviert
Fall B (durchlass): phase6b lief + verdict=VERIFIED + Log vorhanden → archiviert, phase8_complete
Fall C (Tooling):  kein phase6b  + verdict=None  + Log vorhanden → erfolgreich abgeschlossen
Fall D (BROKEN):   phase6b lief + verdict=BROKEN + Log vorhanden → sys.exit(1), NICHT archiviert
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# Verwende den Worktree-eigenen workflow.py — nicht den des Hauptrepos,
# da Worktree-Writes nur im eigenen Tree erlaubt sind.
# tests/tdd/test_...py → parents[2] = Worktree-Root (shiny-jumping-pine/)
_THIS_FILE = Path(__file__).resolve()
HOOKS_DIR = _THIS_FILE.parents[2] / ".claude" / "hooks"
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


def _run_workflow(args: list[str], tmp_path: Path, session_id: str = "test-826") -> subprocess.CompletedProcess:
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


def _create_workflow_with_state(
    tmp_path: Path,
    name: str,
    verdict: str | None,
    include_phase6b: bool,
    session_id: str,
) -> Path:
    """Startet einen echten Workflow, patcht dann verdict + transitions."""
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
    data["current_phase"] = "phase7_validate"
    wf_file.write_text(json.dumps(data))
    return wf_file


def _write_execution_log(tmp_path: Path, name: str) -> None:
    """Schreibt ein gueltiges Execution-Log damit der Log-Gate nicht blockt."""
    log_dir = tmp_path / ".claude" / "workflows" / "_log"
    log_dir.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    log_path = log_dir / f"{date}_{name}.yaml"
    log_path.write_text(
        f"workflow: {name}\noutcome: success\nat: {datetime.now().isoformat()}\n"
    )


# ---------------------------------------------------------------------------
# Fall A: phase6b lief + verdict=None → cmd_complete MUSS blockieren
# ---------------------------------------------------------------------------

class TestFallA_Phase6bNoneVerdictBlocksComplete:
    """AC-2 Fall A: phase6b lief, verdict=None → cmd_complete gibt non-zero exit."""

    def test_complete_blocked_when_phase6b_ran_and_verdict_none(self, tmp_path):
        """
        GIVEN: Workflow mit phase6b in Transitions, adversary_verdict=None, gültiges Log
        WHEN:  workflow.py complete aufgerufen
        THEN:  Exit-Code != 0 (blockiert), Workflow NICHT in _archive/
        """
        repo = _setup_repo(tmp_path)
        sid = "test-826-fall-a"
        name = "wf-826-fall-a"

        _create_workflow_with_state(repo, name, verdict=None, include_phase6b=True, session_id=sid)
        _write_execution_log(repo, name)

        result = _run_workflow(["complete", name], repo, session_id=sid)

        assert result.returncode != 0, (
            f"EXPECTED cmd_complete to block (non-zero exit) for None verdict + phase6b.\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        # State darf NICHT archiviert sein
        archive = repo / ".claude" / "workflows" / "_archive" / f"{name}.json"
        assert not archive.exists(), (
            f"Workflow should NOT be archived when blocked.\nstderr={result.stderr}"
        )

    def test_complete_blocked_stderr_mentions_qa_gate(self, tmp_path):
        """
        GIVEN: None-Verdict + phase6b
        WHEN:  workflow.py complete
        THEN:  stderr enthält Hinweis auf qa_gate.py
        """
        repo = _setup_repo(tmp_path)
        sid = "test-826-fall-a-msg"
        name = "wf-826-fall-a-msg"

        _create_workflow_with_state(repo, name, verdict=None, include_phase6b=True, session_id=sid)
        _write_execution_log(repo, name)

        result = _run_workflow(["complete", name], repo, session_id=sid)

        assert "qa_gate" in result.stderr or "adversary" in result.stderr.lower(), (
            f"Expected qa_gate hint in stderr.\nstdout={result.stdout}\nstderr={result.stderr}"
        )


# ---------------------------------------------------------------------------
# Fall B: phase6b lief + verdict=VERIFIED → cmd_complete erfolgreich
# ---------------------------------------------------------------------------

class TestFallB_VerifiedVerdictAllowsComplete:
    """AC-2 Fall B: VERIFIED-Verdict → cmd_complete schließt erfolgreich ab."""

    def test_complete_succeeds_when_verified(self, tmp_path):
        """
        GIVEN: Workflow mit phase6b, adversary_verdict='VERIFIED', gültiges Log
        WHEN:  workflow.py complete
        THEN:  Exit-Code 0, Workflow in _archive/ mit phase8_complete
        """
        repo = _setup_repo(tmp_path)
        sid = "test-826-fall-b"
        name = "wf-826-fall-b"

        _create_workflow_with_state(repo, name, verdict="VERIFIED", include_phase6b=True, session_id=sid)
        _write_execution_log(repo, name)

        result = _run_workflow(["complete", name], repo, session_id=sid)

        assert result.returncode == 0, (
            f"EXPECTED cmd_complete to succeed for VERIFIED verdict.\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        archive = repo / ".claude" / "workflows" / "_archive" / f"{name}.json"
        assert archive.exists(), f"Workflow should be archived.\nstdout={result.stdout}"
        archived_data = json.loads(archive.read_text())
        assert archived_data["current_phase"] == "phase8_complete"

    def test_complete_succeeds_verified_with_prefix(self, tmp_path):
        """
        GIVEN: adversary_verdict='VERIFIED: alle ACs bestanden'
        WHEN:  workflow.py complete
        THEN:  Exit-Code 0 (Prefix-Match 'VERIFIED...' erlaubt)
        """
        repo = _setup_repo(tmp_path)
        sid = "test-826-fall-b2"
        name = "wf-826-fall-b2"

        _create_workflow_with_state(repo, name, verdict="VERIFIED: alle ACs bestanden", include_phase6b=True, session_id=sid)
        _write_execution_log(repo, name)

        result = _run_workflow(["complete", name], repo, session_id=sid)

        assert result.returncode == 0, (
            f"VERIFIED: prefix should be allowed.\nstdout={result.stdout}\nstderr={result.stderr}"
        )


# ---------------------------------------------------------------------------
# Fall C: kein phase6b + verdict=None → cmd_complete MUSS erfolgreich sein
# ---------------------------------------------------------------------------

class TestFallC_NoPhase6bAllowsComplete:
    """AC-2 Fall C: Tooling/Doku-Workflow ohne phase6b → darf NICHT blockiert werden."""

    def test_complete_allowed_without_phase6b(self, tmp_path):
        """
        GIVEN: Workflow OHNE phase6b in Transitions, adversary_verdict=None, gültiges Log
        WHEN:  workflow.py complete
        THEN:  Exit-Code 0, archiviert (Tooling-Workflows dürfen nicht blockiert werden)
        """
        repo = _setup_repo(tmp_path)
        sid = "test-826-fall-c"
        name = "wf-826-fall-c"

        _create_workflow_with_state(repo, name, verdict=None, include_phase6b=False, session_id=sid)
        _write_execution_log(repo, name)

        result = _run_workflow(["complete", name], repo, session_id=sid)

        assert result.returncode == 0, (
            f"EXPECTED cmd_complete to SUCCEED for Tooling-Workflow without phase6b.\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        archive = repo / ".claude" / "workflows" / "_archive" / f"{name}.json"
        assert archive.exists(), f"Tooling workflow should be archived.\nstdout={result.stdout}"

    def test_complete_allowed_empty_transitions(self, tmp_path):
        """
        GIVEN: phase_transitions=[] (leerer State), verdict=None
        WHEN:  workflow.py complete
        THEN:  Exit-Code 0 — kein False-Positive-Block
        """
        repo = _setup_repo(tmp_path)
        sid = "test-826-fall-c2"
        name = "wf-826-fall-c2"

        # Start + direkt patchen
        r = _run_workflow(["start", name], repo, session_id=sid)
        assert r.returncode == 0
        wf_file = repo / ".claude" / "workflows" / f"{name}.json"
        data = json.loads(wf_file.read_text())
        data["phase_transitions"] = []
        data["adversary_verdict"] = None
        wf_file.write_text(json.dumps(data))
        _write_execution_log(repo, name)

        result = _run_workflow(["complete", name], repo, session_id=sid)

        assert result.returncode == 0, (
            f"Empty transitions should not block complete.\nstdout={result.stdout}\nstderr={result.stderr}"
        )


# ---------------------------------------------------------------------------
# Fall D: phase6b lief + verdict=BROKEN → cmd_complete MUSS blockieren
# ---------------------------------------------------------------------------

class TestFallD_BrokenVerdictBlocksComplete:
    """AC-2 Fall D: BROKEN-Verdict + phase6b → cmd_complete blockiert."""

    def test_complete_blocked_when_broken(self, tmp_path):
        """
        GIVEN: Workflow mit phase6b, adversary_verdict='BROKEN', gültiges Log
        WHEN:  workflow.py complete
        THEN:  Exit-Code != 0, NICHT archiviert
        """
        repo = _setup_repo(tmp_path)
        sid = "test-826-fall-d"
        name = "wf-826-fall-d"

        _create_workflow_with_state(repo, name, verdict="BROKEN", include_phase6b=True, session_id=sid)
        _write_execution_log(repo, name)

        result = _run_workflow(["complete", name], repo, session_id=sid)

        assert result.returncode != 0, (
            f"EXPECTED cmd_complete to block for BROKEN verdict.\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        archive = repo / ".claude" / "workflows" / "_archive" / f"{name}.json"
        assert not archive.exists(), "BROKEN workflow should NOT be archived."
