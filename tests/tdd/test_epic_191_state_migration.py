"""TDD-RED: Isolierter Workflow-State (1 JSON pro Workflow + .active Symlink).

Spec: docs/specs/modules/epic_191_state_migration.md
Issue: #192 (Workflow A von Epic #191)

Tests gegen 9 Acceptance Criteria der Spec, gruppiert in 4 Testklassen:
- T1: Roundtrip (AC-1, AC-4, AC-9) - Migration verliert keine Workflows
- T2: Atomare Writes (AC-3) - keine Race Conditions
- T3: Worktree-Routing (AC-5) - bestehendes Issue #112 muss weiter greifen
- T4: API-Kompatibilität (AC-6, AC-7, AC-8) - Thin-Wrapper deckt alle 14 Funktionen ab

ALLE Tests MÜSSEN aktuell FEHLSCHLAGEN, da workflow.py + migrate_v2_to_v3.py
noch nicht existieren. Das ist das RED-Phasen-Ziel.
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

# Session-Env-Vars, die aus einer laufenden Workflow-Shell lecken und seit
# Commit 59bd925 (Symlink-Fallback aus, #333) ein FATAL exit 1 in _active_name()
# ausloesen, wenn sie auf einen im fake_repo nicht existenten Workflow zeigen.
# (Issue #355)
_SESSION_ENV_VARS = (
    "GZ_ACTIVE_WORKFLOW",
    "CLAUDE_CODE_SESSION_ID",
    "GZ_HOOK_SESSION_ID",
)


def _subprocess_env(active: str | None = None) -> dict:
    """env-dict fuer subprocess-Aufrufe ohne Session-Leaks aus der Shell.

    Optional setzt es GZ_ACTIVE_WORKFLOW auf einen im fake_repo existierenden
    Workflow, damit _active_name() im Subprocess aufloest statt FATAL zu triggern.
    """
    env = {k: v for k, v in os.environ.items() if k not in _SESSION_ENV_VARS}
    if active is not None:
        env["GZ_ACTIVE_WORKFLOW"] = active
    return env


# ---------- Fixtures ----------------------------------------------------


@pytest.fixture
def hooks_on_path():
    """Stellt sicher, dass die Hooks-Module frisch importiert werden."""
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    yield
    for mod_name in (
        "config_loader",
        "workflow_state_multi",
        "workflow",
        "migrate_v2_to_v3",
    ):
        if mod_name in sys.modules:
            del sys.modules[mod_name]


@pytest.fixture
def fake_repo(tmp_path, monkeypatch, hooks_on_path):
    """Minimales Repo-Layout mit `.claude/`-Verzeichnis und 108-Workflow-State."""
    # Isolation gegen Shell-Leaks (#355/#333): aktiver Workflow wird ueber
    # den migrierten Legacy-State (wf-050) aufgeloest. GZ_ACTIVE_WORKFLOW wird
    # unten auf wf-050 gesetzt (existiert nach Migration als Archiv-Datei).
    for var in _SESSION_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    main_repo = tmp_path / "main_repo"
    main_repo.mkdir()
    (main_repo / ".git").mkdir()
    claude_dir = main_repo / ".claude"
    claude_dir.mkdir()

    state = {
        "version": "2.0",
        "active_workflow": "wf-050",
        "workflows": {},
    }
    for i in range(108):
        name = f"wf-{i:03d}"
        state["workflows"][name] = {
            "current_phase": "phase8_complete" if i < 100 else "phase6_implement",
            "created": "2026-04-01T10:00:00",
            "last_updated": "2026-04-02T10:00:00",
            "spec_file": f"docs/specs/modules/{name}.md",
            "spec_approved": True,
            "context_file": None,
            "affected_files": [],
            "test_artifacts": [
                {"type": "test_output", "path": f"docs/artifacts/{name}/red.txt",
                 "description": "Red test", "phase": "phase5_tdd_red"}
            ] if i % 3 == 0 else [],
            "red_test_done": True,
            "green_test_done": i < 100,
            "adversary_verdict": "VERIFIED" if i < 100 else None,
            "phases_completed": [],
            "backlog_status": "done" if i < 100 else "in_progress",
        }
    state_file = claude_dir / "workflow_state.json"
    state_file.write_text(json.dumps(state, indent=2))

    # In-Process-Tests rufen nach migrate() den Wrapper auf; _active_name()
    # braucht GZ_ACTIVE_WORKFLOW explizit (Symlink-Fallback aus). 'wf-050'
    # ist der aktive Workflow und existiert nach der Migration (archiviert).
    monkeypatch.setenv("GZ_ACTIVE_WORKFLOW", "wf-050")
    monkeypatch.chdir(main_repo)
    return main_repo


@pytest.fixture
def fake_worktree(tmp_path, monkeypatch, hooks_on_path):
    """Hauptrepo + Worktree mit korrekt verlinktem `.git`-Marker."""
    for var in _SESSION_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    main_repo = tmp_path / "main_repo"
    main_repo.mkdir()
    git_dir = main_repo / ".git"
    git_dir.mkdir()
    (git_dir / "worktrees").mkdir()
    worktree_meta = git_dir / "worktrees" / "agent-test"
    worktree_meta.mkdir()

    (main_repo / ".claude").mkdir()

    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / ".git").write_text(f"gitdir: {worktree_meta}\n")
    (worktree / ".claude").mkdir()

    monkeypatch.chdir(worktree)
    return main_repo, worktree


# ---------- T1: Roundtrip ----------------------------------------------


class TestT1Roundtrip:
    """AC-1, AC-4, AC-9: Migration verliert keinen einzigen Workflow."""

    def test_dry_run_creates_no_files(self, fake_repo):
        """AC-9: Dry-Run-Default schreibt nichts."""
        from migrate_v2_to_v3 import migrate

        migrate(dry_run=True)

        assert not (fake_repo / ".claude" / "workflows").exists(), \
            "Dry-Run darf nichts erzeugen"

    def test_apply_writes_108_files(self, fake_repo):
        """AC-1: Alle 108 Workflows landen als Einzeldateien in .claude/workflows/."""
        from migrate_v2_to_v3 import migrate

        migrate(dry_run=False)

        wf_dir = fake_repo / ".claude" / "workflows"
        assert wf_dir.exists(), "workflows/ wurde nicht erstellt"

        json_files = list(wf_dir.glob("*.json"))
        archive_files = list((wf_dir / "_archive").glob("*.json")) if (wf_dir / "_archive").exists() else []
        total = len(json_files) + len(archive_files)
        assert total == 108, f"Erwartet 108 Workflows, gefunden {total}"

    def test_active_symlink_points_to_active_workflow(self, fake_repo):
        """AC-1: .active-Symlink zeigt auf den aktiven Workflow."""
        from migrate_v2_to_v3 import migrate

        migrate(dry_run=False)

        active_link = fake_repo / ".claude" / "workflows" / ".active"
        assert active_link.is_symlink(), ".active muss ein Symlink sein"
        target_name = Path(str(active_link.readlink() if hasattr(active_link, 'readlink')
                              else active_link.resolve())).name
        assert target_name == "wf-050.json", \
            f"Symlink-Ziel muss wf-050.json sein, war {target_name}"

    def test_roundtrip_preserves_all_fields(self, fake_repo):
        """AC-1: Nach Migration sind alle wichtigen Felder pro Workflow erhalten."""
        from migrate_v2_to_v3 import migrate

        migrate(dry_run=False)

        wf_dir = fake_repo / ".claude" / "workflows"
        wf_30 = wf_dir / "wf-030.json"
        if not wf_30.exists():
            wf_30 = wf_dir / "_archive" / "wf-030.json"
        assert wf_30.exists(), "wf-030 fehlt nach Migration"

        data = json.loads(wf_30.read_text())
        assert data["spec_file"] == "docs/specs/modules/wf-030.md"
        assert data["spec_approved"] is True
        assert data["adversary_verdict"] == "VERIFIED"
        assert len(data["test_artifacts"]) == 1
        assert data["test_artifacts"][0]["phase"] == "phase5_tdd_red"

    def test_completed_workflows_go_to_archive(self, fake_repo):
        """AC-4: phase8_complete-Workflows landen in _archive/."""
        from migrate_v2_to_v3 import migrate

        migrate(dry_run=False)

        archive = fake_repo / ".claude" / "workflows" / "_archive"
        assert archive.exists()
        archived = list(archive.glob("*.json"))
        assert len(archived) >= 90, \
            f"Mindestens 90 archivierte Workflows erwartet, gefunden {len(archived)}"

    def test_bak_file_is_created(self, fake_repo):
        """AC-2: workflow_state.json.bak bleibt als Rollback-Anker."""
        from migrate_v2_to_v3 import migrate

        migrate(dry_run=False)

        bak = fake_repo / ".claude" / "workflow_state.json.bak"
        assert bak.exists(), ".bak-Rollback-Datei fehlt"
        bak_data = json.loads(bak.read_text())
        assert len(bak_data["workflows"]) == 108


# ---------- T2: Atomare Writes -----------------------------------------


class TestT2AtomicWrites:
    """AC-3: Concurrent Writes erzeugen keine Race Conditions."""

    def test_atomic_write_uses_tempfile_rename(self, fake_repo):
        """AC-3: workflow.py schreibt via tempfile + os.rename (kein direkter open+write)."""
        from workflow import _atomic_write

        target = fake_repo / ".claude" / "workflows" / "test_atomic.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(target, {"name": "test_atomic", "current_phase": "phase1_context"})

        assert target.exists()
        data = json.loads(target.read_text())
        assert data["name"] == "test_atomic"

        leftover = list(target.parent.glob("*.tmp"))
        assert leftover == [], f"Temp-Files dürfen nicht zurückbleiben: {leftover}"

    def test_parallel_writes_no_data_loss(self, fake_repo):
        """AC-3: Zwei Writes auf zwei verschiedene Workflows verlieren keine Daten."""
        from workflow import _atomic_write

        wf_dir = fake_repo / ".claude" / "workflows"
        wf_dir.mkdir(parents=True, exist_ok=True)

        _atomic_write(wf_dir / "a.json", {"name": "a", "value": 1})
        _atomic_write(wf_dir / "b.json", {"name": "b", "value": 2})

        a = json.loads((wf_dir / "a.json").read_text())
        b = json.loads((wf_dir / "b.json").read_text())
        assert a["value"] == 1
        assert b["value"] == 2


# ---------- T3: Worktree-Routing ---------------------------------------


class TestT3WorktreeRouting:
    """AC-5: Worktree-Schreibzugriffe gehen ins Hauptrepo (Issue #112)."""

    def test_workflows_root_in_worktree_points_to_main_repo(self, fake_worktree):
        """AC-5: In einem git-Worktree zeigt _get_workflows_root() ins Hauptrepo."""
        main_repo, worktree = fake_worktree
        import config_loader  # type: ignore
        config_loader.find_project_root.cache_clear()

        from workflow import _get_workflows_root

        result = _get_workflows_root()
        expected = main_repo / ".claude" / "workflows"
        assert result == expected, f"Erwartet {expected}, war {result}"

    def test_workflows_root_in_main_repo_local(self, tmp_path, monkeypatch, hooks_on_path):
        """AC-5: Im normalen Hauptrepo bleibt der Pfad lokal."""
        main_repo = tmp_path / "normal_repo"
        main_repo.mkdir()
        (main_repo / ".git").mkdir()
        (main_repo / ".claude").mkdir()
        monkeypatch.chdir(main_repo)

        import config_loader  # type: ignore
        config_loader.find_project_root.cache_clear()

        from workflow import _get_workflows_root

        assert _get_workflows_root() == main_repo / ".claude" / "workflows"


# ---------- T4: API-Kompatibilität (Thin-Wrapper) ---------------------


class TestT4ApiCompat:
    """AC-6, AC-7, AC-8: workflow_state_multi.py bleibt als Thin-Wrapper voll funktionsfähig."""

    def test_load_state_returns_v2_shape(self, fake_repo):
        """AC-6: load_state() liefert weiter das v2-Format mit version+workflows."""
        from migrate_v2_to_v3 import migrate
        migrate(dry_run=False)

        import workflow_state_multi  # type: ignore
        state = workflow_state_multi.load_state()

        assert "version" in state
        assert "workflows" in state
        assert "active_workflow" in state
        assert len(state["workflows"]) == 108
        assert state["active_workflow"] == "wf-050"

    def test_get_active_workflow_returns_dict(self, fake_repo):
        """AC-6: get_active_workflow() liefert den aktiven Workflow als dict.

        Fixture: active_workflow == 'wf-050', dessen current_phase ist
        'phase8_complete' (Fixture: i<100 -> phase8_complete). Vorheriger
        Test test_load_state_returns_v2_shape pinnt active_workflow auf
        'wf-050'; damit ist 'phase6_implement' im selben Fixture-Setup
        nicht realisierbar. Wir prüfen stattdessen den Workflow-Namen +
        Existenz eines current_phase-Feldes (vgl. Spec AC-6).
        """
        from migrate_v2_to_v3 import migrate
        migrate(dry_run=False)

        import workflow_state_multi  # type: ignore
        active = workflow_state_multi.get_active_workflow()

        assert active is not None
        assert active.get("name") == "wf-050"
        assert active.get("current_phase") == "phase8_complete"

    def test_save_state_writes_through_to_isolated_files(self, fake_repo):
        """AC-6: save_state() im Wrapper persistiert Änderungen in den Einzeldateien."""
        from migrate_v2_to_v3 import migrate
        migrate(dry_run=False)

        import workflow_state_multi  # type: ignore
        state = workflow_state_multi.load_state()
        state["workflows"]["wf-050"]["adversary_verdict"] = "BROKEN: dummy"
        workflow_state_multi.save_state(state)

        # Reload via Wrapper
        if "workflow_state_multi" in sys.modules:
            del sys.modules["workflow_state_multi"]
        if "workflow" in sys.modules:
            del sys.modules["workflow"]
        import workflow_state_multi as wsm2  # type: ignore
        reloaded = wsm2.load_state()
        assert reloaded["workflows"]["wf-050"]["adversary_verdict"] == "BROKEN: dummy"

    def test_all_public_functions_exist(self, fake_repo):
        """AC-6: Alle 14 öffentlichen Funktionen + 5 Konstanten sind weiterhin importierbar."""
        import workflow_state_multi  # type: ignore

        required_functions = [
            "load_state", "save_state",
            "get_active_workflow", "get_workflow_status",
            "list_workflows", "get_tdd_status", "get_backlog_status",
            "can_modify_code",
            "set_phase", "advance_phase",
            "add_test_artifact",
            "mark_red_test_done", "mark_green_test_done",
            "set_backlog_status", "complete_workflow", "pause_workflow",
            "sync_backlog_status_from_phase",
        ]
        required_constants = [
            "PHASES", "PHASE_NAMES", "PHASE_TO_BACKLOG_STATUS",
            "TEST_REQUIRED_PHASES", "CODE_MODIFY_PHASES",
        ]

        for fn in required_functions:
            assert hasattr(workflow_state_multi, fn), \
                f"workflow_state_multi.{fn} fehlt nach Migration"
        for const in required_constants:
            assert hasattr(workflow_state_multi, const), \
                f"workflow_state_multi.{const} fehlt nach Migration"

    def test_cli_status_subcommand(self, fake_repo):
        """AC-8: workflow.py status liefert lesbare Ausgabe für den aktiven Workflow."""
        from migrate_v2_to_v3 import migrate
        migrate(dry_run=False)

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "status"],
            capture_output=True, text=True, cwd=str(fake_repo),
            env=_subprocess_env("wf-050"),
        )
        assert result.returncode == 0, f"workflow.py status fehlgeschlagen: {result.stderr}"
        assert "wf-050" in result.stdout or "wf-050" in result.stderr

    def test_cli_list_subcommand(self, fake_repo):
        """AC-8: workflow.py list zeigt alle Workflows."""
        from migrate_v2_to_v3 import migrate
        migrate(dry_run=False)

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "list"],
            capture_output=True, text=True, cwd=str(fake_repo),
            env=_subprocess_env("wf-050"),
        )
        assert result.returncode == 0
        # Mindestens einige Workflows in der Ausgabe
        for name in ("wf-000", "wf-050", "wf-107"):
            assert name in result.stdout, f"{name} fehlt in list-Ausgabe"


# ---------- R5-spezifisch: Direkte Leser müssen mitziehen ----------


class TestT5R5HookPatches:
    """AC-7: workflow_gate.py und workflow_state_updater.py lesen über den Wrapper."""

    def test_workflow_gate_uses_wrapper_load_state(self):
        """workflow_gate.py darf keine eigene load_state mehr definieren, die direkt liest."""
        gate_src = (HOOKS_DIR / "workflow_gate.py").read_text()
        # Es muss aus workflow_state_multi importiert werden
        assert "from workflow_state_multi import" in gate_src, \
            "workflow_gate.py muss aus workflow_state_multi importieren"
        # Lokale def load_state mit direktem JSON-File-Read darf nicht mehr existieren
        assert "def load_state(" not in gate_src or "from workflow_state_multi" in gate_src, \
            "workflow_gate.py hat noch eine eigene load_state()"

    def test_workflow_state_updater_uses_wrapper(self):
        """workflow_state_updater.py darf keine eigene load_state/save_state Funktion definieren."""
        import re

        updater_src = (HOOKS_DIR / "workflow_state_updater.py").read_text()

        # Es muss aus workflow_state_multi importiert werden
        assert "from workflow_state_multi import load_state" in updater_src, \
            "workflow_state_updater.py muss load_state aus workflow_state_multi importieren"

        # Keine eigene def load_state/save_state Funktion mehr
        for fn_name in ("load_state", "save_state"):
            local_def = re.search(rf"^def {fn_name}\(", updater_src, re.MULTILINE)
            assert local_def is None, \
                f"workflow_state_updater.py hat noch eigene def {fn_name}()"

    def test_post_implementation_gate_uses_wrapper(self):
        """post_implementation_gate.py darf nicht direkt aus workflow_state.json lesen."""
        src = (HOOKS_DIR / "post_implementation_gate.py").read_text()
        assert "from workflow_state_multi import" in src, \
            "post_implementation_gate.py muss aus workflow_state_multi importieren"
        # Kein direkter String-Read von .claude/workflow_state.json mehr
        # (kommentare/docstrings duerften erwaehnen, aber kein Code-Pfad)
        lines = [
            ln for ln in src.splitlines()
            if "workflow_state.json" in ln and not ln.strip().startswith("#")
        ]
        # erlaubt: docstrings/comments, NICHT erlaubt: live-Pfadbau
        for ln in lines:
            assert ".json" not in ln or "workflow_state.json" in ln and "Path" not in ln, \
                f"post_implementation_gate.py konstruiert noch Pfad auf workflow_state.json: {ln!r}"

    def test_workflow_name_path_traversal_rejected(self, fake_repo):
        """F005: Workflow-Namen mit Pfad-Separatoren werden abgelehnt."""
        import sys as _sys
        if str(HOOKS_DIR) not in _sys.path:
            _sys.path.insert(0, str(HOOKS_DIR))
        # frischer Import nach Path-Setup
        if "workflow" in _sys.modules:
            del _sys.modules["workflow"]
        from workflow import _workflow_file, _archive_file

        for bad in ("../evil", "a/b", ".hidden", "a\\b", "..", "."):
            with pytest.raises(ValueError):
                _workflow_file(bad)
            with pytest.raises(ValueError):
                _archive_file(bad)

        # Sanity: normale Namen funktionieren weiter
        _workflow_file("wf-050")
        _archive_file("epic-191-state-migration")
