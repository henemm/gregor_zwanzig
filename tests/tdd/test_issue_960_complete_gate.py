"""Regressionstest für Issue #960 — workflow.py complete muss das Adversary-Verdict-Gate
erzwingen (nicht nur `phase phase8_complete`, sondern auch der explizite `complete`-Pfad).

Vor dem Fix rief `cmd_complete` `_validate_transition(data, "phase8_complete")` NICHT auf,
wodurch ein Workflow ohne (oder mit BROKEN-) Adversary-Verdikt trotzdem als "completed"
archiviert werden konnte. Der Fix (siehe `.claude/hooks/workflow.py`, `cmd_complete`,
Kommentar "Issue #960") ruft jetzt denselben `_validate_transition`-Check auf wie eine
explizite Phasen-Transition nach `phase8_complete`.

Alle Tests laufen gegen echten Code (keine Mocks). Subprocess-Tests nutzen
On-Disk-Workflow-JSON-Files in tmp_path — Pattern übernommen aus
tests/tdd/test_issue_508_workflow_gate_none_verdict.py.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOKS_DIR = Path("/home/hem/gregor_zwanzig/.claude/hooks")
WORKFLOW_PY = HOOKS_DIR / "workflow.py"

sys.path.insert(0, str(HOOKS_DIR))


# ---------------------------------------------------------------------------
# Helpers (Pattern aus test_issue_508_workflow_gate_none_verdict.py)
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


def _run_workflow(args: list[str], tmp_path: Path, session_id: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CLAUDE_CODE_SESSION_ID"] = session_id
    env["OPENSPEC_ACTIVE_WORKFLOW"] = ""  # wird nach start() explizit gesetzt vom Aufrufer
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


def _start_workflow(tmp_path: Path, name: str, session_id: str, workflow_type: str = "feature") -> None:
    env = os.environ.copy()
    env["CLAUDE_CODE_SESSION_ID"] = session_id
    for k in ("GZ_ACTIVE_WORKFLOW", "GZ_HOOK_SESSION_ID"):
        env.pop(k, None)
    r = subprocess.run(
        [sys.executable, str(WORKFLOW_PY), "start", name, "--type", workflow_type],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )
    assert r.returncode == 0, f"workflow start failed: {r.stdout}\n{r.stderr}"


def _patch_workflow_for_complete(
    tmp_path: Path,
    name: str,
    verdict: "str | None",
    extra_fields: "dict | None" = None,
) -> None:
    """Patcht den State so, dass ALLE Vorbedingungen von _validate_transition VOR dem
    Verdict-Check erfuellt sind — es soll ausschliesslich der Verdict-Check greifen.
    """
    ctx_file = tmp_path / "ctx.md"
    ctx_file.write_text("# context\n")
    spec_file = tmp_path / "spec.md"
    spec_file.write_text("# spec\n")  # kein 'created:' Feld -> grandfathered, kein ADR-Check

    wf_file = tmp_path / ".claude" / "workflows" / f"{name}.json"
    data = json.loads(wf_file.read_text())

    data["workflow_type"] = "feature"
    data["current_phase"] = "phase7_validate"
    data["context_file"] = str(ctx_file)
    data["spec_file"] = str(spec_file)
    data["spec_approved"] = True
    data["red_test_done"] = True
    data["adversary_verdict"] = verdict
    data["phase_transitions"] = [
        {"from": "phase6_implement", "to": "phase6b_adversary", "at": "2026-07-01T10:00:00", "trigger": "command"},
        {"from": "phase6b_adversary", "to": "phase7_validate", "at": "2026-07-01T11:00:00", "trigger": "command"},
    ]
    if extra_fields:
        data.update(extra_fields)
    wf_file.write_text(json.dumps(data))


def _write_log_file(tmp_path: Path, name: str) -> None:
    """Legt eine Execution-Log-Datei an, damit cmd_complete nicht schon am
    'No execution log'-Vorab-Check scheitert (das ist NICHT der #960-Check)."""
    log_dir = tmp_path / ".claude" / "workflows" / "_log"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / f"2026-07-01_{name}.yaml").write_text("workflow_id: dummy\noutcome: success\n")


# ---------------------------------------------------------------------------
# AC: complete ohne/mit ungueltigem Verdikt blockt; mit gueltigem Verdikt laeuft durch.
# ---------------------------------------------------------------------------

class TestCompleteBlocksWithoutValidVerdict:
    """Kern-Regression #960: `workflow.py complete` darf NICHT ohne VERIFIED-Verdikt
    durchlaufen — vorher wurde _validate_transition im complete-Pfad gar nicht geprüft."""

    def test_complete_without_verdict_is_blocked(self, tmp_path):
        """
        GIVEN: Workflow mit allen Vorbedingungen erfuellt, adversary_verdict = null
        WHEN:  workflow.py complete
        THEN:  Exit-Code != 0, stderr nennt Adversary-Verdict/BLOCKED
        """
        repo = _setup_repo(tmp_path)
        sid = "test-960-none"
        name = "wf-960-none-verdict"

        _start_workflow(repo, name, session_id=sid)
        _patch_workflow_for_complete(repo, name, verdict=None)
        _write_log_file(repo, name)

        result = _run_workflow(["complete"], repo, session_id=sid)

        assert result.returncode != 0, (
            f"Expected non-zero exit for missing verdict, got 0.\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        combined = (result.stdout + result.stderr).lower()
        assert "adversary verdict" in combined or "blocked" in combined, (
            f"Expected 'Adversary verdict' or 'BLOCKED' in output, got:\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )

        # State darf NICHT archiviert worden sein.
        archive_file = repo / ".claude" / "workflows" / "_archive" / f"{name}.json"
        assert not archive_file.exists(), "Workflow wurde trotz fehlendem Verdikt archiviert!"

    def test_complete_with_broken_verdict_is_blocked(self, tmp_path):
        """
        GIVEN: adversary_verdict = "BROKEN — test failed"
        WHEN:  workflow.py complete
        THEN:  Exit-Code != 0
        """
        repo = _setup_repo(tmp_path)
        sid = "test-960-broken"
        name = "wf-960-broken-verdict"

        _start_workflow(repo, name, session_id=sid)
        _patch_workflow_for_complete(repo, name, verdict="BROKEN — test failed")
        _write_log_file(repo, name)

        result = _run_workflow(["complete"], repo, session_id=sid)

        assert result.returncode != 0, (
            f"Expected non-zero exit for BROKEN verdict, got 0.\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )

        archive_file = repo / ".claude" / "workflows" / "_archive" / f"{name}.json"
        assert not archive_file.exists(), "Workflow wurde trotz BROKEN-Verdikt archiviert!"


class TestCompleteSucceedsWithValidVerdict:
    """Gegenprobe: ein gueltiges VERIFIED-Verdikt darf den complete-Pfad NICHT blockieren
    (sonst waere der #960-Fix zu scharf und wuerde legitime Workflows blockieren)."""

    def test_complete_with_verified_verdict_succeeds(self, tmp_path):
        """
        GIVEN: adversary_verdict = "VERIFIED — alle ACs bestaetigt", alle Vorbedingungen erfuellt
        WHEN:  workflow.py complete
        THEN:  Exit-Code == 0, Workflow-State liegt in _archive/, current_phase ist phase8_complete
        """
        repo = _setup_repo(tmp_path)
        sid = "test-960-verified"
        name = "wf-960-verified-verdict"

        _start_workflow(repo, name, session_id=sid)
        _patch_workflow_for_complete(repo, name, verdict="VERIFIED — alle ACs bestaetigt")
        _write_log_file(repo, name)

        result = _run_workflow(["complete"], repo, session_id=sid)

        assert result.returncode == 0, (
            f"Expected exit 0 for VERIFIED verdict, got {result.returncode}.\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )

        archive_file = repo / ".claude" / "workflows" / "_archive" / f"{name}.json"
        assert archive_file.exists(), "Workflow wurde nicht archiviert trotz VERIFIED-Verdikt."
        archived_data = json.loads(archive_file.read_text())
        assert archived_data.get("current_phase") == "phase8_complete"

        # Aktive Workflow-Datei muss entfernt sein.
        active_file = repo / ".claude" / "workflows" / f"{name}.json"
        assert not active_file.exists()


class TestCompleteBlocksExpressSamplingWithoutVerdict:
    """Zweiter Bypass, den #960 mitgeschlossen hat: ein Express-Workflow in der
    Sampling-Pflicht-Runde durfte trotz fehlendem Verdikt 'complete' abschliessen
    (Counter-Reset lief VOR dem Verdict-Check)."""

    def test_express_sampling_required_without_verdict_is_blocked(self, tmp_path):
        """
        GIVEN: Express-Workflow, express_sampling_required = true, adversary_verdict = null
        WHEN:  workflow.py complete
        THEN:  Exit-Code != 0 — Sampling-Runde darf nicht ohne Verdikt durchlaufen
        """
        repo = _setup_repo(tmp_path)
        sid = "test-960-express"
        name = "wf-960-express-sampling"

        _start_workflow(repo, name, session_id=sid, workflow_type="express")
        _patch_workflow_for_complete(
            repo, name, verdict=None,
            extra_fields={"workflow_type": "express", "express_sampling_required": True},
        )
        _write_log_file(repo, name)

        result = _run_workflow(["complete"], repo, session_id=sid)

        assert result.returncode != 0, (
            f"Expected non-zero exit for express sampling round without verdict, got 0.\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )

        archive_file = repo / ".claude" / "workflows" / "_archive" / f"{name}.json"
        assert not archive_file.exists(), (
            "Express-Sampling-Workflow wurde trotz fehlendem Verdikt archiviert!"
        )
