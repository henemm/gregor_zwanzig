"""TDD-RED: Workflow Execution Log + Phase Transition Audit Trail + Fix-Loop-Counter.

Spec: docs/specs/modules/epic_191_logbuch_audit.md
Issue: #193 (Workflow B von Epic #191)

13 Tests in 5 Klassen gegen 9 Acceptance Criteria:
- T1: write_log YAML (AC-1) - 3 Tests
- T2: complete-Block (AC-2, AC-8) - 3 Tests
- T3: Phase-Transitions + Fix-Loop (AC-3, AC-4) - 3 Tests (Bestand absichern)
- T4: Status-Erweiterung (AC-5) - 1 Test
- T5: Updater-Patch (AC-6, AC-7, AC-9) - 3 Tests

Erwartet: ~10 Tests RED (write_log/complete-block/updater-patch fehlen),
~3 Tests GREEN (Transitions+Fix-Loop bereits in Workflow A implementiert).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"

# Session-Env-Vars, die aus einer laufenden Workflow-Shell in die Subprozesse
# (und den In-Process-Import von workflow.py) lecken koennen. Seit Commit 59bd925
# (Symlink-Fallback aus, Issue #333) triggert ein gesetztes GZ_ACTIVE_WORKFLOW,
# das auf einen im fake_repo nicht existenten Workflow zeigt, ein FATAL exit 1.
# Diese Tests muessen daher die Env-Vars isolieren und den fake_repo-Workflow
# explizit als aktiv markieren (Issue #355, Muster aus bug_333).
_SESSION_ENV_VARS = (
    "GZ_ACTIVE_WORKFLOW",
    "CLAUDE_CODE_SESSION_ID",
    "GZ_HOOK_SESSION_ID",
)


def _subprocess_env(active: str | None = "demo-wf") -> dict:
    """Sauberes env-dict fuer subprocess-Aufrufe: keine Session-Leaks aus Shell.

    Setzt GZ_ACTIVE_WORKFLOW auf den im fake_repo existierenden Workflow
    (Default 'demo-wf'), damit _active_name() im Subprocess aufloest statt FATAL
    zu triggern.
    """
    env = {k: v for k, v in os.environ.items() if k not in _SESSION_ENV_VARS}
    if active is not None:
        env["GZ_ACTIVE_WORKFLOW"] = active
    return env


# ---------- Fixtures ----------------------------------------------------


@pytest.fixture
def hooks_on_path():
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    yield
    for mod_name in (
        "config_loader",
        "workflow_state_multi",
        "workflow",
        "workflow_state_updater",
    ):
        if mod_name in sys.modules:
            del sys.modules[mod_name]


@pytest.fixture
def fake_repo(tmp_path, monkeypatch, hooks_on_path):
    """Minimales v3-Repo mit einem aktiven Workflow in phase6b_adversary."""
    # Isolation gegen Shell-Leaks (Issue #355/#333): Session-Vars entfernen,
    # damit weder Subprozess noch In-Process-Import einen fremden Workflow
    # aufloest (sonst FATAL exit 1). GZ_ACTIVE_WORKFLOW wird unten gesetzt.
    for var in _SESSION_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    main_repo = tmp_path / "main_repo"
    main_repo.mkdir()
    (main_repo / ".git").mkdir()
    claude_dir = main_repo / ".claude"
    claude_dir.mkdir()
    wf_dir = claude_dir / "workflows"
    wf_dir.mkdir()

    wf_state = {
        "name": "demo-wf",
        "current_phase": "phase6b_adversary",
        "created": "2026-05-11T10:00:00",
        "last_updated": "2026-05-11T12:00:00",
        "spec_file": "docs/specs/modules/demo.md",
        "spec_approved": True,
        "context_file": "docs/context/demo.md",
        "affected_files": ["a.py", "b.py", "c.py"],
        "test_artifacts": [
            {"type": "test_output", "path": "docs/artifacts/demo/red.txt",
             "description": "Red", "phase": "phase5_tdd_red"}
        ],
        "red_test_done": True,
        "red_test_result": "5/5 failed",
        "ui_test_red_done": False,
        "green_test_done": True,
        "green_test_result": "5/5 passed",
        "green_approved": True,
        "adversary_verdict": "VERIFIED",
        "adversary_ambiguous_override": None,
        "phase_transitions": [
            {"from": "phase0_idle", "to": "phase1_context",
             "at": "2026-05-11T10:00:00", "trigger": "command"},
            {"from": "phase6_implement", "to": "phase6b_adversary",
             "at": "2026-05-11T11:30:00", "trigger": "command"},
        ],
        "fix_loop_iterations": 0,
        "phases_completed": ["phase1_context", "phase2_analyse"],
        "backlog_status": "in_progress",
    }
    (wf_dir / "demo-wf.json").write_text(json.dumps(wf_state, indent=2))
    (wf_dir / ".active").symlink_to("demo-wf.json")

    # In-Process-Tests (set_phase-Import) brauchen den aktiven Workflow explizit.
    monkeypatch.setenv("GZ_ACTIVE_WORKFLOW", "demo-wf")
    monkeypatch.chdir(main_repo)
    return main_repo


# ---------- T1: write_log YAML ----------------------------------------


class TestT1WriteLog:
    """AC-1: write_log schreibt gültiges YAML mit Pflichtfeldern."""

    def test_write_log_creates_yaml_file(self, fake_repo):
        """AC-1: workflow.py write-log erstellt _log/YYYY-MM-DD_<name>.yaml."""
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "write-log", "success"],
            capture_output=True, text=True, cwd=str(fake_repo),
            env=_subprocess_env(),
        )
        assert result.returncode == 0, f"write-log fehlgeschlagen: {result.stderr}"

        log_dir = fake_repo / ".claude" / "workflows" / "_log"
        assert log_dir.exists(), "_log Verzeichnis muss erstellt werden"
        log_files = list(log_dir.glob("*_demo-wf.yaml"))
        assert len(log_files) == 1, f"Erwartet 1 Log-File, gefunden {len(log_files)}"

    def test_write_log_yaml_has_required_fields(self, fake_repo):
        """AC-1: YAML enthält alle Pflichtfelder."""
        import yaml

        subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "write-log", "success"],
            capture_output=True, text=True, cwd=str(fake_repo), check=True,
            env=_subprocess_env(),
        )

        log_file = next((fake_repo / ".claude" / "workflows" / "_log").glob("*_demo-wf.yaml"))
        data = yaml.safe_load(log_file.read_text())

        required = {
            "workflow_id", "project", "completed_at",
            "phases_completed", "phases_skipped",
            "tdd_red_confirmed", "adversary_verdict",
            "adversary_fix_loop_iterations",
            "scope_files_changed", "outcome",
        }
        missing = required - data.keys()
        assert not missing, f"Pflichtfelder fehlen: {missing}"

        assert data["workflow_id"] == "demo-wf"
        assert data["adversary_verdict"] == "VERIFIED"
        assert data["tdd_red_confirmed"] is True
        assert data["scope_files_changed"] == 3
        assert data["outcome"] == "success"

    def test_write_log_default_outcome_is_success(self, fake_repo):
        """AC-1: Aufruf ohne Argument liefert outcome=success."""
        import yaml

        subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "write-log"],
            capture_output=True, text=True, cwd=str(fake_repo), check=True,
            env=_subprocess_env(),
        )

        log_file = next((fake_repo / ".claude" / "workflows" / "_log").glob("*_demo-wf.yaml"))
        data = yaml.safe_load(log_file.read_text())
        assert data["outcome"] == "success"


# ---------- T2: complete-Block + phase8 Bypass-Schutz -----------------


class TestT2CompleteBlock:
    """AC-2, AC-8: cmd_complete blockt ohne Log; phase phase8_complete ebenfalls."""

    def test_complete_blocked_without_log(self, fake_repo):
        """AC-2: workflow.py complete ohne Log → Exit 1 mit klarer Meldung."""
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "complete"],
            capture_output=True, text=True, cwd=str(fake_repo),
            env=_subprocess_env(),
        )
        assert result.returncode != 0, "complete darf ohne Log nicht erlaubt sein"
        assert "BLOCKED" in (result.stderr + result.stdout), \
            "Fehlermeldung muss 'BLOCKED' enthalten"
        assert "write-log" in (result.stderr + result.stdout), \
            "Fehlermeldung muss auf write-log hinweisen"

    def test_complete_allowed_with_log(self, fake_repo):
        """AC-2: Nach write-log läuft complete durch."""
        subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "write-log", "success"],
            capture_output=True, text=True, cwd=str(fake_repo), check=True,
            env=_subprocess_env(),
        )
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "complete"],
            capture_output=True, text=True, cwd=str(fake_repo),
            env=_subprocess_env(),
        )
        assert result.returncode == 0, f"complete sollte mit Log erlaubt sein: {result.stderr}"

        # Workflow ist archiviert
        archive = fake_repo / ".claude" / "workflows" / "_archive" / "demo-wf.json"
        assert archive.exists()

    def test_direct_jump_to_phase8_blocked_without_log(self, fake_repo):
        """AC-8: workflow.py phase phase8_complete ohne Log → blockiert."""
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "phase", "phase8_complete"],
            capture_output=True, text=True, cwd=str(fake_repo),
            env=_subprocess_env(),
        )
        assert result.returncode != 0, \
            "Direkter Sprung zu phase8_complete ohne Log muss blockiert sein"
        assert "BLOCKED" in (result.stderr + result.stdout)


# ---------- T3: Phase-Transitions + Fix-Loop (Bestand) ----------------


class TestT3TransitionsAndFixLoop:
    """AC-3, AC-4: Bereits in Workflow A implementiert — Bestand absichern."""

    def test_phase_command_logs_transition(self, fake_repo):
        """AC-3: cmd_phase loggt phase_transitions mit from/to/at/trigger."""
        subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "phase", "phase7_validate"],
            capture_output=True, text=True, cwd=str(fake_repo), check=True,
            env=_subprocess_env(),
        )

        state = json.loads((fake_repo / ".claude" / "workflows" / "demo-wf.json").read_text())
        last_transition = state["phase_transitions"][-1]
        assert last_transition["from"] == "phase6b_adversary"
        assert last_transition["to"] == "phase7_validate"
        assert last_transition["trigger"] == "command"
        assert "at" in last_transition and last_transition["at"]  # ISO-Timestamp

    def test_fix_loop_increment_on_phase6b_to_phase6(self, fake_repo):
        """AC-4: phase6b_adversary → phase6_implement inkrementiert fix_loop_iterations."""
        # Setze State auf phase6b_adversary mit fix_loop=0
        wf_file = fake_repo / ".claude" / "workflows" / "demo-wf.json"
        state = json.loads(wf_file.read_text())
        state["current_phase"] = "phase6b_adversary"
        state["fix_loop_iterations"] = 0
        wf_file.write_text(json.dumps(state, indent=2))

        subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "phase", "phase6_implement"],
            capture_output=True, text=True, cwd=str(fake_repo), check=True,
            env=_subprocess_env(),
        )

        state = json.loads(wf_file.read_text())
        assert state["fix_loop_iterations"] == 1, \
            f"fix_loop_iterations soll 1 sein, war {state['fix_loop_iterations']}"

    def test_fix_loop_no_increment_on_other_transitions(self, fake_repo):
        """AC-4: phase6_implement → phase6b_adversary inkrementiert NICHT."""
        wf_file = fake_repo / ".claude" / "workflows" / "demo-wf.json"
        state = json.loads(wf_file.read_text())
        state["current_phase"] = "phase6_implement"
        state["fix_loop_iterations"] = 0
        wf_file.write_text(json.dumps(state, indent=2))

        subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "phase", "phase6b_adversary"],
            capture_output=True, text=True, cwd=str(fake_repo), check=True,
            env=_subprocess_env(),
        )

        state = json.loads(wf_file.read_text())
        assert state["fix_loop_iterations"] == 0, \
            "Vorwärts-Übergang darf nicht inkrementieren"


# ---------- T4: cmd_status zeigt Counter ------------------------------


class TestT4StatusExtension:
    """AC-5: status zeigt fix_loop_iterations und Anzahl phase_transitions."""

    def test_status_shows_fix_loop_and_transitions(self, fake_repo):
        """AC-5: status-Output enthält 'Fix-Loop-Iterations' und 'Phase-Transitions'."""
        wf_file = fake_repo / ".claude" / "workflows" / "demo-wf.json"
        state = json.loads(wf_file.read_text())
        state["fix_loop_iterations"] = 3
        # 2 Transitions sind schon im Fixture
        wf_file.write_text(json.dumps(state, indent=2))

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "status"],
            capture_output=True, text=True, cwd=str(fake_repo), check=True,
            env=_subprocess_env(),
        )
        output = result.stdout

        assert "Fix-Loop-Iterations: 3" in output, \
            f"Fix-Loop-Counter fehlt im Status-Output: {output}"
        assert "Phase-Transitions: 2" in output, \
            f"Phase-Transitions-Count fehlt im Status-Output: {output}"
        assert "Execution Log:" in output, \
            "Log-Status fehlt im Status-Output"


# ---------- T5: workflow_state_updater Patch --------------------------


class TestT5UpdaterPatch:
    """AC-6, AC-7, AC-9: Updater nutzt set_phase mit user_keyword-Trigger."""

    def test_updater_uses_set_phase_not_direct_dict(self):
        """AC-6: workflow_state_updater.py darf 'current_phase' nicht direkt im Dict setzen.

        F002 (Fix-Loop 1): Auch `.update({"current_phase": ...})` zählt als
        Direkt-Edit und ist verboten — bisher wurde damit der Regex umgangen.
        """
        import re

        src = (HOOKS_DIR / "workflow_state_updater.py").read_text()

        # Verbotene Direkt-Edits: workflow["current_phase"] = ... oder w["current_phase"] = ...
        direct_assignments = re.findall(
            r'\w+\[\s*["\']current_phase["\']\s*\]\s*=',
            src,
        )
        assert not direct_assignments, \
            f"Direkter Dict-Edit von current_phase verboten — fanden: {direct_assignments}"

        # F002: .update({"current_phase": ...}) ist Test-Gaming und ebenfalls verboten
        update_with_phase = re.findall(
            r'\w+\.update\(\s*\{[^}]*["\']current_phase["\']',
            src,
        )
        assert not update_with_phase, \
            f".update() mit current_phase verboten (Test-Gaming): {update_with_phase}"

        # set_phase muss importiert oder aufgerufen werden
        assert "set_phase" in src, \
            "workflow_state_updater.py muss set_phase nutzen"

    def test_set_phase_logs_transition_with_trigger(self, fake_repo):
        """AC-9: workflow_state_multi.set_phase loggt Transition mit Trigger-Param."""
        sys.path.insert(0, str(HOOKS_DIR))
        from workflow_state_multi import set_phase

        ok = set_phase("demo-wf", "phase7_validate", trigger="user_keyword")
        assert ok

        state = json.loads((fake_repo / ".claude" / "workflows" / "demo-wf.json").read_text())
        last = state["phase_transitions"][-1]
        assert last["to"] == "phase7_validate"
        assert last["trigger"] == "user_keyword", \
            f"Trigger muss 'user_keyword' sein, war '{last['trigger']}'"

    def test_set_phase_default_trigger_is_manual(self, fake_repo):
        """AC-9: set_phase ohne explizites trigger= → 'manual'."""
        sys.path.insert(0, str(HOOKS_DIR))
        from workflow_state_multi import set_phase

        set_phase("demo-wf", "phase7_validate")

        state = json.loads((fake_repo / ".claude" / "workflows" / "demo-wf.json").read_text())
        last = state["phase_transitions"][-1]
        assert last["trigger"] == "manual"


# ---------- Fix-Loop 1: Adversary-Findings F001/F003/F004 -------------


class TestFixLoop1Findings:
    """Regressions-Tests für die in Fix-Loop 1 behobenen Adversary-Findings."""

    def test_f001_status_tolerates_null_phase_transitions(self, fake_repo):
        """F001 (HIGH): cmd_status darf nicht crashen wenn phase_transitions=None.

        Vorher: ``len(data.get('phase_transitions', []))`` ergibt ``len(None)``
        und wirft ``TypeError`` wenn der Key existiert aber ``null`` ist.
        """
        wf_file = fake_repo / ".claude" / "workflows" / "demo-wf.json"
        state = json.loads(wf_file.read_text())
        state["phase_transitions"] = None
        state["fix_loop_iterations"] = None
        state["test_artifacts"] = None
        wf_file.write_text(json.dumps(state, indent=2))

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "status"],
            capture_output=True, text=True, cwd=str(fake_repo),
            env=_subprocess_env(),
        )
        assert result.returncode == 0, \
            f"status darf bei null-Feldern nicht crashen: stderr={result.stderr}"
        # Die Zähler müssen 0 zeigen, nicht crashen
        assert "Phase-Transitions: 0" in result.stdout
        assert "Fix-Loop-Iterations: 0" in result.stdout
        assert "Test Artifacts: 0" in result.stdout

    def test_f001_phase_command_tolerates_null_phase_transitions(self, fake_repo):
        """F001 (HIGH): cmd_phase darf bei phase_transitions=None nicht crashen."""
        wf_file = fake_repo / ".claude" / "workflows" / "demo-wf.json"
        state = json.loads(wf_file.read_text())
        state["phase_transitions"] = None
        state["fix_loop_iterations"] = None
        wf_file.write_text(json.dumps(state, indent=2))

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "phase", "phase7_validate"],
            capture_output=True, text=True, cwd=str(fake_repo),
            env=_subprocess_env(),
        )
        assert result.returncode == 0, \
            f"phase-cmd darf bei null nicht crashen: stderr={result.stderr}"
        # Eine Transition muss jetzt drinstehen
        state2 = json.loads(wf_file.read_text())
        assert isinstance(state2["phase_transitions"], list)
        assert len(state2["phase_transitions"]) == 1
        assert state2["phase_transitions"][0]["to"] == "phase7_validate"

    def test_f003_workflow_name_rejects_glob_metacharacters(self, fake_repo):
        """F003 (MEDIUM): _validate_name lehnt *, ?, [ ab.

        Andernfalls hätte ``log_dir.glob(f"*_{name}.yaml")`` False-Positive
        Matches auf unverwandte Log-Files.
        """
        sys.path.insert(0, str(HOOKS_DIR))
        if "workflow" in sys.modules:
            del sys.modules["workflow"]
        from workflow import _validate_name

        for bad in ("foo*", "wf-?-bar", "[abc]", "*", "?", "[", "name[1]"):
            with pytest.raises(ValueError, match="glob metacharacter"):
                _validate_name(bad)

        # Sanity: normale Namen funktionieren weiter
        _validate_name("wf-050")
        _validate_name("epic-191-fix-loop-1")

    def test_f004_empty_log_file_does_not_unblock_complete(self, fake_repo):
        """F004 (LOW): 0-Byte-Log-File darf complete nicht unblocken.

        Vorher: ``any(log_dir.glob(...))`` prüfte nur Existenz — ein leerer
        ``touch``-File hätte den Gate passieren lassen.
        """
        log_dir = fake_repo / ".claude" / "workflows" / "_log"
        log_dir.mkdir(parents=True, exist_ok=True)
        empty_log = log_dir / "2026-05-11_demo-wf.yaml"
        empty_log.touch()
        assert empty_log.stat().st_size == 0

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "complete"],
            capture_output=True, text=True, cwd=str(fake_repo),
            env=_subprocess_env(),
        )
        assert result.returncode != 0, \
            "complete darf bei 0-Byte-Log-File nicht durchgehen"
        assert "BLOCKED" in (result.stderr + result.stdout)

        # Und auch der direkte Phase-Sprung muss blockiert bleiben
        result2 = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "phase", "phase8_complete"],
            capture_output=True, text=True, cwd=str(fake_repo),
            env=_subprocess_env(),
        )
        assert result2.returncode != 0, \
            "Direkter Sprung zu phase8_complete darf bei 0-Byte-Log nicht durchgehen"
        assert "BLOCKED" in (result2.stderr + result2.stdout)
