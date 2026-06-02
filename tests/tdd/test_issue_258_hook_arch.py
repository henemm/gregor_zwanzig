"""Regression-Guard: Issue #258 Hook-Architektur (Fast-Path + cmd_cleanup).

Spec:    docs/specs/modules/issue_258_hook_arch_fix.md (Original-Spec, #258)
Update:  docs/specs/modules/bug_333_test_issue_258_obsolete.md (Test-Refresh, #333)
Issue:   https://github.com/henemm/gregor_zwanzig/issues/258

Tests gegen 14 Acceptance Criteria, gruppiert in 4 Test-Klassen:

- TestReadActiveWorkflowFast    (AC-1, AC-2, AC-3)         — 4 Tests
- TestCmdCompleteOptionalName   (AC-6, AC-7, AC-8, AC-9)   — 6 Tests
- TestCmdCleanup                (AC-10 … AC-13)            — 5 Tests
- TestHotPathIntegration        (AC-4, AC-5)               — 2 Tests

Update 2026-05-22 (#333): Commit 59bd925 hat den Symlink-Fallback in
_active_name() deaktiviert — Tests setzen seitdem zusätzlich
GZ_ACTIVE_WORKFLOW (in-process via _activate(), subprocess via
_subprocess_env()). Test AC-3 wurde von "dangling → None" auf
"dangling/missing → FATAL exit 1" umformuliert (Verhaltens-Drift,
nicht Setup-Anpassung). Production-Code unverändert.

Keine Mocks (CLAUDE.md-Regel), echte Filesystem-Operationen via tmp_path,
echte subprocess-Calls für CLI-Tests.
"""

from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"


# ---------- Fixtures ----------------------------------------------------


@pytest.fixture
def hooks_on_path():
    """Stellt sicher, dass die Hooks-Module frisch importiert werden."""
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    yield
    for mod_name in (
        "config_loader",
        "workflow",
        "workflow_state_multi",
        "tdd_enforcement",
        "workflow_gate",
    ):
        if mod_name in sys.modules:
            del sys.modules[mod_name]


@pytest.fixture
def fake_repo(tmp_path, monkeypatch, hooks_on_path):
    """Minimales v3-Repo mit `.claude/workflows/`-Layout und `git init`."""
    # Isolation gegen Shell-Leaks aus laufenden Workflows (Issue #333):
    # Drei Session-Vars müssen explizit aus der Test-Env verschwinden,
    # sonst sieht der subprocess-aufgerufene workflow.py die kontaminierten
    # Werte und triggert FATAL "set but no matching workflow file exists".
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
    return repo


# ---------- Helper ----------------------------------------------------


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
        "created": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
    }
    p.write_text(json.dumps(data, indent=2))
    return p


def _set_active(repo: Path, name: str) -> None:
    """Lege oder erneuere den `.active`-Symlink."""
    link = repo / ".claude" / "workflows" / ".active"
    if link.is_symlink() or link.exists():
        link.unlink()
    os.symlink(f"{name}.json", str(link))


def _write_valid_log(repo: Path, name: str) -> Path:
    """Schreibe ein nicht-leeres Execution-Log, damit `cmd_complete` nicht
    durch die Epic-191-Log-Gate blockiert wird."""
    log_dir = repo / ".claude" / "workflows" / "_log"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}_{name}.yaml"
    log_path.write_text(
        "workflow_id: " + name + "\n"
        "outcome: success\n"
        "completed_at: '2026-05-18T11:00:00'\n"
    )
    return log_path


def _subprocess_env(active: str | None = None) -> dict:
    """Sauberes env-dict für subprocess-Aufrufe: keine Session-Leaks aus Shell.

    Optional setzt es GZ_ACTIVE_WORKFLOW auf einen im fake_repo existierenden
    Workflow, damit _active_name() im Subprocess auflöst statt FATAL zu triggern.
    """
    env = {k: v for k, v in os.environ.items()
           if k not in ("GZ_ACTIVE_WORKFLOW", "CLAUDE_CODE_SESSION_ID",
                        "GZ_HOOK_SESSION_ID")}
    if active is not None:
        env["GZ_ACTIVE_WORKFLOW"] = active
    return env


def _activate(repo: Path, name: str, monkeypatch) -> None:
    """Markiere `name` als aktiven Workflow für In-Process-Tests.

    Setzt sowohl den (legacy) .active-Symlink als auch die heute autoritative
    Env-Var GZ_ACTIVE_WORKFLOW. Der Symlink bleibt, weil cmd_start/cmd_complete
    ihn in Production weiter pflegen — er ist nur kein Fallback mehr."""
    _set_active(repo, name)
    monkeypatch.setenv("GZ_ACTIVE_WORKFLOW", name)


# ---------- TestReadActiveWorkflowFast (AC-1, AC-2, AC-3) ----------


class TestReadActiveWorkflowFast:
    """Fast-Path-Reader: `read_active_workflow_fast()` in `workflow.py`."""

    def test_returns_none_when_no_active_symlink(self, fake_repo):
        """AC-2: Kein `.active`-Symlink → None, kein Crash."""
        from workflow import read_active_workflow_fast

        result = read_active_workflow_fast()
        assert result is None, (
            f"Erwartet None bei fehlendem Symlink, war {result!r}"
        )

    def test_returns_name_and_data_when_active_exists(self, fake_repo,
                                                       monkeypatch):
        """AC-1: Aktiver Workflow gesetzt + JSON existiert → (name, dict)-Tuple."""
        _create_workflow(fake_repo, "issue-258-hot-path-hooks",
                         phase="phase5_tdd_red")
        _activate(fake_repo, "issue-258-hot-path-hooks", monkeypatch)

        from workflow import read_active_workflow_fast

        result = read_active_workflow_fast()
        assert result is not None, "Fast-Path muss (name, data) liefern"
        name, data = result
        assert name == "issue-258-hot-path-hooks"
        assert isinstance(data, dict)
        assert data["current_phase"] == "phase5_tdd_red"
        assert data["name"] == "issue-258-hot-path-hooks"

    def test_fatal_when_env_workflow_file_missing(self, fake_repo,
                                                   monkeypatch, capsys):
        """AC-3: ENV zeigt auf nicht-existente JSON → FATAL exit 1.

        Verhaltens-Drift (Commit 59bd925): Symlink-Fallback ist deaktiviert.
        Wenn GZ_ACTIVE_WORKFLOW gesetzt ist, die Datei aber fehlt, triggert
        _active_name() ein klares SystemExit(1) mit FATAL-Banner auf stderr
        statt graceful None zurückzugeben. Dieser Test verifiziert die
        strengere Fail-Loud-Semantik."""
        wf_path = _create_workflow(fake_repo, "ghost", phase="phase1_context")
        monkeypatch.setenv("GZ_ACTIVE_WORKFLOW", "ghost")
        # ENV bleibt, JSON wird gelöscht → ENV zeigt auf nicht-existente Datei
        wf_path.unlink()

        from workflow import read_active_workflow_fast

        with pytest.raises(SystemExit) as exc:
            read_active_workflow_fast()
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "FATAL" in err and "ghost" in err, (
            f"stderr muss 'FATAL' und 'ghost' enthalten: {err!r}"
        )

    def test_no_filesystem_aggregation(self, fake_repo, monkeypatch):
        """AC-1: Fast-Path liest exakt 1 JSON, ruft KEIN glob() auf.

        Verifikation: Wir patchen `Path.glob` so dass jeder Aufruf wirft.
        Wenn `read_active_workflow_fast()` intern auf `.glob()` zurückfällt
        (statt nur den `.active`-Symlink aufzulösen), schlägt der Test fehl.
        Pragmatisch: 5 weitere Live-JSONs + 3 Archive-JSONs liegen rum —
        kein einziger davon darf vom Fast-Path angefasst werden.
        """
        # Erstelle den aktiven Workflow + viele "Distraktoren"
        _create_workflow(fake_repo, "active-wf", phase="phase5_tdd_red")
        _activate(fake_repo, "active-wf", monkeypatch)
        for i in range(5):
            _create_workflow(fake_repo, f"other-{i}", phase="phase1_context")
        for i in range(3):
            _create_workflow(fake_repo, f"old-{i}", phase="phase8_complete",
                             archived=True)

        from workflow import read_active_workflow_fast

        # Patch Path.glob nach dem Import, sodass jeder glob-Aufruf wirft
        original_glob = Path.glob

        def explode_on_glob(self, pattern):
            raise RuntimeError(
                f"Fast-Path darf nicht globben — "
                f"Path({self!s}).glob({pattern!r}) aufgerufen"
            )

        monkeypatch.setattr(Path, "glob", explode_on_glob)
        try:
            result = read_active_workflow_fast()
        finally:
            monkeypatch.setattr(Path, "glob", original_glob)

        assert result is not None
        name, data = result
        assert name == "active-wf"
        assert data["current_phase"] == "phase5_tdd_red"


# ---------- TestCmdCompleteOptionalName (AC-6 … AC-9) ----------


class TestCmdCompleteOptionalName:
    """`workflow.py complete [<name>]` — optionales Argument + Warn/Error."""

    def test_complete_without_arg_removes_symlink(self, fake_repo):
        """AC-6 + AC-9: complete ohne Argument funktioniert, danach scheitert
        complete <unknown> sauber mit exit 1 + ERROR.

        RED-Pflicht: Heute akzeptiert `cmd_complete` kein Argument und ruft
        immer `_read_active()` auf. Der zweite Sub-Lauf (complete <unknown>
        ohne aktiven Workflow) endet heute mit 'No active workflow.' statt
        mit der präzisen Issue-#258-Fehlermeldung 'ERROR: Workflow ...
        not found'. Test FAILT daher solange.
        """
        _create_workflow(fake_repo, "wf-a", phase="phase7_validate")
        _set_active(fake_repo, "wf-a")
        _write_valid_log(fake_repo, "wf-a")

        # 1. complete ohne Arg → archiviert wf-a, entfernt Symlink
        first = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "complete"],
            capture_output=True,
            text=True,
            cwd=str(fake_repo),
            env=_subprocess_env("wf-a"),
        )
        assert first.returncode == 0, (
            f"complete ohne Arg sollte erfolgreich sein: {first.stderr}"
        )
        link = fake_repo / ".claude" / "workflows" / ".active"
        assert not link.is_symlink() and not link.exists(), (
            ".active muss nach complete entfernt sein"
        )

        # 2. complete <unknown-name> → präzise ERROR-Meldung mit Workflow-Name
        # Heutiger Code würde mit 'No active workflow.' abbrechen, ohne den
        # Namen zu erwähnen. Issue #258 verlangt 'ERROR: Workflow ... not found'.
        unknown = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"),
             "complete", "totally-unknown-wf"],
            capture_output=True,
            text=True,
            cwd=str(fake_repo),
            env=_subprocess_env(None),
        )
        assert unknown.returncode == 1, (
            f"complete <unknown> muss exit 1 liefern (Issue #258): "
            f"stderr={unknown.stderr!r}"
        )
        combined = unknown.stderr + unknown.stdout
        assert "ERROR" in combined and "totally-unknown-wf" in combined, (
            f"Fehlermeldung muss 'ERROR' + Workflow-Name enthalten: "
            f"{combined!r}"
        )

    def test_complete_with_active_name_removes_symlink(self, fake_repo):
        """AC-7: complete <name> mit name == active → identisch zu ohne Arg.

        RED-Pflicht: Wir nehmen einen Workflow-Namen, der NICHT der heutige
        Default ist (ohne `.active` zu setzen, dann complete <name>) — das
        prüft den neuen Code-Pfad. Heutige Implementation ruft `_read_active`
        und bricht ohne `.active`-Symlink mit exit 1 ab.
        """
        # Workflow erstellt, aber NICHT als aktiv markiert
        _create_workflow(fake_repo, "wf-b", phase="phase7_validate")
        _write_valid_log(fake_repo, "wf-b")
        # Setze stattdessen einen anderen Dummy als aktiv
        _create_workflow(fake_repo, "wf-dummy-active",
                         phase="phase5_tdd_red")
        _set_active(fake_repo, "wf-dummy-active")

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"),
             "complete", "wf-b"],
            capture_output=True,
            text=True,
            cwd=str(fake_repo),
            env=_subprocess_env("wf-dummy-active"),
        )
        # Erwartet: exit 0 — komplettiert wf-b, Warn-Banner für anderen
        # aktiven Workflow, .active bleibt unverändert
        assert result.returncode == 0, (
            f"complete <other-existing-name> muss erfolgreich sein "
            f"(Issue #258): {result.stderr}"
        )
        # wf-b ist archiviert
        archived = (fake_repo / ".claude" / "workflows" / "_archive"
                    / "wf-b.json")
        assert archived.exists(), "wf-b muss archiviert sein"
        # .active bleibt auf wf-dummy-active
        link = fake_repo / ".claude" / "workflows" / ".active"
        assert link.is_symlink(), (
            ".active muss erhalten bleiben (wf-b war nicht aktiv)"
        )
        target = os.readlink(str(link))
        assert Path(target).stem == "wf-dummy-active", (
            f".active-Ziel falsch: {target}"
        )

    def test_complete_with_other_name_keeps_symlink(self, fake_repo):
        """AC-8: complete <other> → `.active` bleibt unverändert."""
        _create_workflow(fake_repo, "wf-active", phase="phase5_tdd_red")
        _create_workflow(fake_repo, "wf-other", phase="phase7_validate")
        _set_active(fake_repo, "wf-active")
        _write_valid_log(fake_repo, "wf-other")

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"),
             "complete", "wf-other"],
            capture_output=True,
            text=True,
            cwd=str(fake_repo),
            env=_subprocess_env("wf-active"),
        )
        assert result.returncode == 0, (
            f"complete <other> sollte erfolgreich sein: {result.stderr}"
        )
        link = fake_repo / ".claude" / "workflows" / ".active"
        assert link.is_symlink(), (
            ".active muss bei complete <other> erhalten bleiben"
        )
        target = os.readlink(str(link))
        assert Path(target).stem == "wf-active", (
            f".active-Ziel darf nicht geändert sein, war: {target}"
        )

    def test_complete_with_other_name_prints_warning(self, fake_repo):
        """AC-8: complete <other> → stderr enthält 'WARNING'."""
        _create_workflow(fake_repo, "wf-active", phase="phase5_tdd_red")
        _create_workflow(fake_repo, "wf-other", phase="phase7_validate")
        _set_active(fake_repo, "wf-active")
        _write_valid_log(fake_repo, "wf-other")

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"),
             "complete", "wf-other"],
            capture_output=True,
            text=True,
            cwd=str(fake_repo),
            env=_subprocess_env("wf-active"),
        )
        combined = result.stderr + result.stdout
        assert "WARNING" in combined, (
            f"Warn-Banner muss bei complete <other> auf stderr/stdout "
            f"erscheinen — bekam: {combined!r}"
        )
        assert "wf-other" in combined and "wf-active" in combined, (
            f"Warn-Banner muss beide Workflow-Namen nennen: {combined!r}"
        )

    def test_complete_with_nonexistent_name_exits_1(self, fake_repo):
        """AC-9: complete <name> mit unbekanntem Workflow → exit 1 + ERROR."""
        _create_workflow(fake_repo, "wf-active", phase="phase5_tdd_red")
        _set_active(fake_repo, "wf-active")

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"),
             "complete", "does-not-exist"],
            capture_output=True,
            text=True,
            cwd=str(fake_repo),
            env=_subprocess_env("wf-active"),
        )
        assert result.returncode == 1, (
            f"Erwartet exit 1, bekam {result.returncode}: {result.stderr}"
        )
        combined = result.stderr + result.stdout
        assert "ERROR" in combined, (
            f"Fehlermeldung muss 'ERROR' enthalten: {combined!r}"
        )
        assert "does-not-exist" in combined, (
            f"Fehlermeldung muss Workflow-Namen nennen: {combined!r}"
        )

    def test_complete_archives_workflow_json(self, fake_repo):
        """AC-6/AC-7: Nach complete <name> liegt die JSON in `_archive/<name>.json`.

        RED-Pflicht: Wir archivieren explizit einen NICHT-aktiven Workflow
        via Name-Argument. Heutiger Code ignoriert das Argument und würde
        statt 'wf-archive-me' den aktiven 'wf-other-active' archivieren —
        also FAILED, weil die geforderte Archive-Datei nicht da ist.
        """
        _create_workflow(fake_repo, "wf-archive-me", phase="phase7_validate")
        _create_workflow(fake_repo, "wf-other-active",
                         phase="phase5_tdd_red")
        _set_active(fake_repo, "wf-other-active")
        _write_valid_log(fake_repo, "wf-archive-me")

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"),
             "complete", "wf-archive-me"],
            capture_output=True,
            text=True,
            cwd=str(fake_repo),
            env=_subprocess_env("wf-other-active"),
        )
        assert result.returncode == 0, (
            f"complete <wf-archive-me> fehlgeschlagen: {result.stderr}"
        )

        archived = (fake_repo / ".claude" / "workflows" / "_archive"
                    / "wf-archive-me.json")
        live = fake_repo / ".claude" / "workflows" / "wf-archive-me.json"
        assert archived.exists(), (
            "wf-archive-me muss nach _archive/ verschoben sein "
            "(via expliziten Namen, NICHT der aktive Workflow)"
        )
        assert not live.exists(), (
            "wf-archive-me darf nicht mehr im Live-Verzeichnis liegen"
        )
        # Sanity: der aktive Workflow wurde NICHT angefasst
        other_live = (fake_repo / ".claude" / "workflows"
                      / "wf-other-active.json")
        other_archived = (fake_repo / ".claude" / "workflows" / "_archive"
                          / "wf-other-active.json")
        assert other_live.exists(), (
            "wf-other-active (aktiv) muss im Live-Verzeichnis bleiben"
        )
        assert not other_archived.exists(), (
            "wf-other-active darf NICHT versehentlich archiviert sein"
        )


# ---------- TestCmdCleanup (AC-10 … AC-13) ----------


class TestCmdCleanup:
    """`workflow.py cleanup [--yes]` — Dry-Run + Batch-Archive."""

    def test_cleanup_dry_run_lists_candidates(self, fake_repo):
        """AC-10: Dry-Run listet alle `phase8_complete`-Kandidaten auf stdout."""
        _create_workflow(fake_repo, "done-1", phase="phase8_complete")
        _create_workflow(fake_repo, "done-2", phase="phase8_complete")
        _create_workflow(fake_repo, "still-open", phase="phase5_tdd_red")

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "cleanup"],
            capture_output=True,
            text=True,
            cwd=str(fake_repo),
        )
        assert result.returncode == 0, (
            f"cleanup-dry-run sollte exit 0 liefern: {result.stderr}"
        )
        assert "done-1" in result.stdout, (
            f"done-1 muss als Kandidat gelistet sein: {result.stdout!r}"
        )
        assert "done-2" in result.stdout, (
            f"done-2 muss als Kandidat gelistet sein: {result.stdout!r}"
        )
        assert "still-open" not in result.stdout, (
            f"still-open darf NICHT als Kandidat erscheinen: {result.stdout!r}"
        )

    def test_cleanup_dry_run_writes_nothing(self, fake_repo):
        """AC-10: Dry-Run verändert keinen File-Bestand."""
        _create_workflow(fake_repo, "done-1", phase="phase8_complete")
        _create_workflow(fake_repo, "done-2", phase="phase8_complete")
        _create_workflow(fake_repo, "still-open", phase="phase5_tdd_red")

        wf_dir = fake_repo / ".claude" / "workflows"
        archive_dir = wf_dir / "_archive"

        before_live = sorted(p.name for p in wf_dir.glob("*.json"))
        before_archive = sorted(p.name for p in archive_dir.glob("*.json"))

        subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "cleanup"],
            capture_output=True,
            text=True,
            cwd=str(fake_repo),
            check=True,
        )

        after_live = sorted(p.name for p in wf_dir.glob("*.json"))
        after_archive = sorted(p.name for p in archive_dir.glob("*.json"))

        assert before_live == after_live, (
            f"Dry-Run darf Live-Dateien nicht verändern: "
            f"{before_live} → {after_live}"
        )
        assert before_archive == after_archive, (
            f"Dry-Run darf Archive nicht verändern: "
            f"{before_archive} → {after_archive}"
        )

    def test_cleanup_yes_archives_all_completed(self, fake_repo):
        """AC-11: cleanup --yes verschiebt alle phase8_complete nach _archive/."""
        _create_workflow(fake_repo, "done-1", phase="phase8_complete")
        _create_workflow(fake_repo, "done-2", phase="phase8_complete")
        _create_workflow(fake_repo, "still-open", phase="phase5_tdd_red")

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"),
             "cleanup", "--yes"],
            capture_output=True,
            text=True,
            cwd=str(fake_repo),
        )
        assert result.returncode == 0, (
            f"cleanup --yes sollte exit 0 liefern: {result.stderr}"
        )

        wf_dir = fake_repo / ".claude" / "workflows"
        archive_dir = wf_dir / "_archive"

        assert not (wf_dir / "done-1.json").exists(), (
            "done-1 muss aus Live-Verzeichnis entfernt sein"
        )
        assert not (wf_dir / "done-2.json").exists(), (
            "done-2 muss aus Live-Verzeichnis entfernt sein"
        )
        assert (archive_dir / "done-1.json").exists(), (
            "done-1 muss in _archive/ liegen"
        )
        assert (archive_dir / "done-2.json").exists(), (
            "done-2 muss in _archive/ liegen"
        )

    def test_cleanup_no_candidates_exits_cleanly(self, fake_repo):
        """AC-12: Keine `phase8_complete`-Workflows → exit 0 + 'Nothing to clean up'."""
        _create_workflow(fake_repo, "wf-x", phase="phase5_tdd_red")
        _create_workflow(fake_repo, "wf-y", phase="phase3_spec")

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "cleanup"],
            capture_output=True,
            text=True,
            cwd=str(fake_repo),
        )
        assert result.returncode == 0, (
            f"Erwartet exit 0, bekam {result.returncode}: {result.stderr}"
        )
        combined = result.stdout + result.stderr
        assert "Nothing to clean up" in combined, (
            f"Output muss 'Nothing to clean up' enthalten: {combined!r}"
        )

    def test_cleanup_leaves_active_workflows_alone(self, fake_repo):
        """AC-11: Nicht-`phase8_complete` Workflows werden nicht angefasst."""
        _create_workflow(fake_repo, "impl-wf", phase="phase6_implement")
        _create_workflow(fake_repo, "adv-wf", phase="phase6b_adversary")
        _create_workflow(fake_repo, "spec-wf", phase="phase3_spec")
        _create_workflow(fake_repo, "done-wf", phase="phase8_complete")

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"),
             "cleanup", "--yes"],
            capture_output=True,
            text=True,
            cwd=str(fake_repo),
        )
        assert result.returncode == 0, (
            f"cleanup --yes sollte exit 0 liefern: {result.stderr}"
        )

        wf_dir = fake_repo / ".claude" / "workflows"
        archive_dir = wf_dir / "_archive"

        # Aktive (nicht phase8) bleiben Live
        for name in ("impl-wf", "adv-wf", "spec-wf"):
            live = wf_dir / f"{name}.json"
            archived = archive_dir / f"{name}.json"
            assert live.exists(), (
                f"{name} darf nicht aus Live-Dir verschwinden"
            )
            assert not archived.exists(), (
                f"{name} darf nicht ins _archive/ wandern"
            )

        # done-wf wandert
        assert not (wf_dir / "done-wf.json").exists()
        assert (archive_dir / "done-wf.json").exists()


# ---------- TestHotPathIntegration (AC-4, AC-5) ----------


class TestHotPathIntegration:
    """Hot-Path-Hooks rufen `read_active_workflow_fast()` auf."""

    def test_tdd_enforcement_imports_fast_path(self, hooks_on_path):
        """AC-4: `tdd_enforcement.check_tdd_requirements` nutzt den Fast-Path.

        Die Funktion muss `read_active_workflow_fast` aufrufen (statt das
        `_aggregate_state`-basierte `get_active_workflow()`). Wir prüfen das
        am Source-Code via `inspect.getsource`. Test FAILT solange die
        Umstellung nicht erfolgt ist.
        """
        import tdd_enforcement

        src = inspect.getsource(tdd_enforcement.check_tdd_requirements)
        assert "read_active_workflow_fast" in src, (
            f"check_tdd_requirements muss read_active_workflow_fast nutzen — "
            f"Source enthielt das Symbol nicht.\n--- Source ---\n{src}"
        )

    def test_workflow_gate_uses_fast_path(self, hooks_on_path):
        """AC-5: `workflow_gate.main` (oder lokales load_state) nutzt Fast-Path.

        `workflow_gate.py` definiert ein lokales `load_state()` (Z. ~94),
        das via `_aggregate_state` alle Workflow-JSONs aggregiert. Die Spec
        fordert Umstellung auf `read_active_workflow_fast`. Wir prüfen das
        am Modul-Source, weil sowohl Import als auch direkter Aufruf
        akzeptable Umstellungs-Varianten sind.
        """
        gate_src = (HOOKS_DIR / "workflow_gate.py").read_text()
        assert "read_active_workflow_fast" in gate_src, (
            "workflow_gate.py muss read_active_workflow_fast referenzieren "
            "(Import oder direkter Aufruf). Aktuell nicht vorhanden."
        )
