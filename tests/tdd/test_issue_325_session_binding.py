"""Regression-Guard: Issue #325 Session-Binding — eine zuverlässige Auflösung.

Spec:    docs/specs/modules/issue_325_session_binding.md (AC-1 … AC-7)
Issue:   https://github.com/henemm/gregor_zwanzig/issues/325

Kernforderung: Die Auflösung "welcher Workflow gehört zu dieser Session"
läuft über EINE kanonische Reihenfolge — Session-Registry → GZ_ACTIVE_WORKFLOW
→ None. Die stillen Rate-Fallbacks werden entfernt:

- `.active`-Symlink ist KEINE Auflösungsquelle mehr (AC-1).
- `_aggregate_state()` rät NICHT mehr "erster nicht-archivierter Workflow" (AC-2).
- `workflow_state_updater.py` routet Keywords NUR auf den Session-gebundenen
  Workflow (AC-3, AC-4).
- GZ_ACTIVE_WORKFLOW-Override bleibt erhalten (AC-6).
- Reine Hook-/Tooling-Schicht, kein Produktiv-Code (AC-7).

Keine Mocks (CLAUDE.md-Regel): echte Filesystem-Operationen via tmp_path,
echte subprocess-Aufrufe für den Updater-Hook. Vorbild:
tests/tdd/test_issue_258_hook_arch.py.
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


# ---------- Fixtures ----------------------------------------------------


@pytest.fixture
def hooks_on_path():
    """Frischer Import der Hook-Module je Test (kein Cross-Test-Leak)."""
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    yield
    for mod_name in (
        "config_loader",
        "workflow",
        "workflow_state_multi",
        "scope_guard",
    ):
        if mod_name in sys.modules:
            del sys.modules[mod_name]


@pytest.fixture
def fake_repo(tmp_path, monkeypatch, hooks_on_path):
    """Minimales v3-Repo mit `.claude/workflows/`-Layout und `git init`.

    Wie #258: Session-Vars aus der Test-Env entfernen, damit weder In-Process
    noch Subprocess kontaminierte Werte sehen. Zusätzlich den lru_cache von
    config_loader.find_project_root leeren, damit das frische tmp_path-Repo
    als Wurzel erkannt wird (In-Process-Tests).
    """
    for var in ("GZ_ACTIVE_WORKFLOW", "CLAUDE_CODE_SESSION_ID",
                "GZ_HOOK_SESSION_ID"):
        monkeypatch.delenv(var, raising=False)
    repo = tmp_path / "repo"
    (repo / ".claude" / "workflows" / "_archive").mkdir(parents=True)
    (repo / ".claude" / "workflows" / "_log").mkdir(parents=True)
    subprocess.run(
        ["git", "init", str(repo)],
        check=True,
        capture_output=True,
    )
    monkeypatch.chdir(repo)
    # config_loader.find_project_root ist @lru_cache — Cache leeren, sonst
    # zeigt er auf ein Repo eines vorherigen Tests.
    import config_loader
    config_loader.find_project_root.cache_clear()
    config_loader.load_config.cache_clear()
    yield repo
    config_loader.find_project_root.cache_clear()
    config_loader.load_config.cache_clear()


# ---------- Helper ------------------------------------------------------


def _create_workflow(
    repo: Path,
    name: str,
    phase: str = "phase1_context",
    backlog: str = "open",
    archived: bool = False,
) -> Path:
    """Schreibe eine Workflow-JSON in Live- oder Archive-Verzeichnis."""
    if archived:
        p = repo / ".claude" / "workflows" / "_archive" / f"{name}.json"
    else:
        p = repo / ".claude" / "workflows" / f"{name}.json"
    data = {
        "name": name,
        "current_phase": phase,
        "backlog_status": backlog,
        "spec_file": None,
        "spec_approved": False,
        "red_test_done": False,
        "green_test_done": False,
        "test_artifacts": [],
        "adversary_verdict": None,
        "phase_transitions": [],
        "fix_loop_iterations": 0,
        "phases_completed": [],
        "affected_files": [],
        "created": "2026-05-18T10:00:00",
        "last_updated": "2026-05-18T10:00:00",
    }
    p.write_text(json.dumps(data, indent=2))
    return p


def _set_active_symlink(repo: Path, name: str) -> None:
    """Lege oder erneuere den `.active`-Symlink (Lifecycle-Artefakt)."""
    link = repo / ".claude" / "workflows" / ".active"
    if link.is_symlink() or link.exists():
        link.unlink()
    os.symlink(f"{name}.json", str(link))


def _write_registry(repo: Path, mapping: dict) -> None:
    """Schreibe `.claude/session_workflows.json` mit session_id → workflow."""
    reg = repo / ".claude" / "session_workflows.json"
    reg.write_text(json.dumps(mapping, indent=2))


def _subprocess_env(extra: dict | None = None) -> dict:
    """Sauberes env-dict: keine Session-Leaks aus der Shell."""
    env = {k: v for k, v in os.environ.items()
           if k not in ("GZ_ACTIVE_WORKFLOW", "CLAUDE_CODE_SESSION_ID",
                        "GZ_HOOK_SESSION_ID")}
    if extra:
        env.update(extra)
    return env


def _read_phase(repo: Path, name: str) -> str:
    """Lies current_phase aus Live- oder Archive-JSON eines Workflows."""
    live = repo / ".claude" / "workflows" / f"{name}.json"
    arch = repo / ".claude" / "workflows" / "_archive" / f"{name}.json"
    p = live if live.exists() else arch
    return json.loads(p.read_text())["current_phase"]


# ---------- AC-2: kein "erster nicht-archivierter"-Fallback -------------


class TestAggregateNoFirstWorkflowFallback:
    def test_aggregate_no_first_workflow_fallback(self, fake_repo,
                                                  monkeypatch):
        """AC-2: Mehrere nicht-archivierte Workflows, keine Bindung, kein Env
        → get_active_workflow()/_aggregate_state() liefert None statt dem
        ersten Workflow."""
        _create_workflow(fake_repo, "wf-alpha", phase="phase3_spec")
        _create_workflow(fake_repo, "wf-beta", phase="phase5_tdd_red")
        _create_workflow(fake_repo, "wf-gamma", phase="phase1_context")
        # KEINE Registry, KEIN GZ_ACTIVE_WORKFLOW, KEIN Symlink.

        import workflow_state_multi as wsm

        state = wsm.load_state()
        assert state["active_workflow"] is None, (
            "active_workflow muss None sein (kein 'erster nicht-archivierter' "
            f"Fallback), war: {state['active_workflow']!r}"
        )
        assert wsm.get_active_workflow() is None, (
            "get_active_workflow() muss None liefern ohne Session-Bindung/Env"
        )


# ---------- AC-3: Keyword wirkt nur auf Session-gebundenen Workflow ------


class TestKeywordTargetsSessionBoundOnly:
    def test_keyword_targets_session_bound_only(self, fake_repo):
        """AC-3: Registry bindet S_A→wf-a (phase3_spec); wf-b existiert als
        'erster'. Keyword 'approved' der Session S_A setzt NUR wf-a auf
        phase4_approved; wf-b bleibt unverändert."""
        _create_workflow(fake_repo, "wf-a", phase="phase3_spec")
        # wf-b alphabetisch vor wf-a NICHT — aber als 'erster' Distraktor:
        _create_workflow(fake_repo, "wf-b", phase="phase3_spec")
        _write_registry(fake_repo, {"S_A": "wf-a"})

        payload = json.dumps({"session_id": "S_A", "prompt": "approved"})
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow_state_updater.py")],
            input=payload,
            capture_output=True,
            text=True,
            cwd=str(fake_repo),
            env=_subprocess_env(),
        )
        assert result.returncode == 0, (
            f"Updater-Hook darf nie blocken: {result.stderr!r}"
        )
        assert _read_phase(fake_repo, "wf-a") == "phase4_approved", (
            f"wf-a muss auf phase4_approved stehen, war: "
            f"{_read_phase(fake_repo, 'wf-a')!r}\nstdout={result.stdout!r}"
        )
        assert _read_phase(fake_repo, "wf-b") == "phase3_spec", (
            f"wf-b (Distraktor) muss UNVERÄNDERT bleiben, war: "
            f"{_read_phase(fake_repo, 'wf-b')!r}"
        )


# ---------- AC-4: keine Bindung → kein Keyword-Effekt -------------------


class TestKeywordNoBindingNoEffect:
    def test_keyword_no_binding_no_effect(self, fake_repo):
        """AC-4: Keine Registry-Bindung, kein GZ_ACTIVE_WORKFLOW → Keyword
        'approved' verändert KEINEN Workflow."""
        _create_workflow(fake_repo, "wf-x", phase="phase3_spec")
        _create_workflow(fake_repo, "wf-y", phase="phase3_spec")
        # leere/keine Registry

        payload = json.dumps({"session_id": "S_UNBOUND", "prompt": "approved"})
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow_state_updater.py")],
            input=payload,
            capture_output=True,
            text=True,
            cwd=str(fake_repo),
            env=_subprocess_env(),
        )
        assert result.returncode == 0, (
            f"Updater-Hook darf nie blocken: {result.stderr!r}"
        )
        assert _read_phase(fake_repo, "wf-x") == "phase3_spec", (
            f"wf-x muss unverändert bleiben, war: "
            f"{_read_phase(fake_repo, 'wf-x')!r}"
        )
        assert _read_phase(fake_repo, "wf-y") == "phase3_spec", (
            f"wf-y muss unverändert bleiben, war: "
            f"{_read_phase(fake_repo, 'wf-y')!r}"
        )


# ---------- AC-1: Symlink ist KEINE Auflösungsquelle --------------------


class TestActiveNameIgnoresSymlink:
    def test_active_name_ignores_symlink(self, fake_repo):
        """AC-1: `.active`→wf-x, Registry leer, Env leer →
        read_active_workflow_fast() liefert None (Symlink ist kein Resolver),
        kein FATAL, kein wf-x."""
        _create_workflow(fake_repo, "wf-x", phase="phase5_tdd_red")
        _set_active_symlink(fake_repo, "wf-x")
        # KEINE Registry, KEIN GZ_ACTIVE_WORKFLOW.

        from workflow import read_active_workflow_fast, _active_name

        assert _active_name() is None, (
            "_active_name() muss None liefern (Symlink ist keine Quelle)"
        )
        assert read_active_workflow_fast() is None, (
            "read_active_workflow_fast() muss None liefern, nicht wf-x"
        )


# ---------- AC-6: GZ_ACTIVE_WORKFLOW-Override bleibt -------------------


class TestEnvOverrideStillResolves:
    def test_env_override_still_resolves(self, fake_repo, monkeypatch):
        """AC-6: GZ_ACTIVE_WORKFLOW=wf-a gesetzt + Workflow existiert →
        löst auf wf-a auf (Rückwärtskompatibilität)."""
        _create_workflow(fake_repo, "wf-a", phase="phase6_implement")
        _create_workflow(fake_repo, "wf-b", phase="phase1_context")
        monkeypatch.setenv("GZ_ACTIVE_WORKFLOW", "wf-a")

        from workflow import _active_name, read_active_workflow_fast

        assert _active_name() == "wf-a", (
            f"Env-Override muss auf wf-a auflösen, war: {_active_name()!r}"
        )
        fast = read_active_workflow_fast()
        assert fast is not None
        name, data = fast
        assert name == "wf-a"
        assert data["current_phase"] == "phase6_implement"


# ---------- AC-7: nur Tooling-Schicht ---------------------------------


class TestOnlyToolingLayer:
    def test_only_tooling_layer(self):
        """AC-7: Geänderte Dateien liegen ausschließlich in .claude/hooks/,
        tests/ oder docs/ — kein Produktiv-Code unter src/api/internal/
        frontend/cmd."""
        allowed_prefixes = (
            ".claude/hooks/",
            "tests/",
            "docs/",
        )
        forbidden_prefixes = (
            "src/", "api/", "internal/", "frontend/", "cmd/",
        )
        changed = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        ).stdout.splitlines()
        # Auf #325-relevante Dateien einschränken: nur jene, die die
        # Auflösungs-Kette betreffen + diese Testdatei + die Spec.
        relevant = [
            f for f in changed
            if f.endswith("issue_325_session_binding.py")
            or "issue_325_session_binding" in f
            or f in (
                ".claude/hooks/workflow.py",
                ".claude/hooks/workflow_state_multi.py",
                ".claude/hooks/workflow_state_updater.py",
            )
        ]
        for f in relevant:
            assert f.startswith(allowed_prefixes), (
                f"Geänderte #325-Datei außerhalb der erlaubten Schicht: {f}"
            )
            assert not f.startswith(forbidden_prefixes), (
                f"#325 darf keinen Produktiv-Code anfassen: {f}"
            )
