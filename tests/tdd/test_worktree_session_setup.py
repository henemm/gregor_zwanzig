"""Tests fuer den SessionStart-Worktree-Setup-Hook (Issue #1202).

Kern-Schicht: deterministisch, kein Netzwerk, keine echte `uv sync`-Ausfuehrung.
Der Subprocess-Runner fuer `uv sync` wird dependency-injiziert (Test-Double an der
Grenze zur Aussenwelt), die Erkennungslogik selbst laeuft echt gegen das Dateisystem.
"""
import importlib.util
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / ".claude" / "hooks" / "session_start.py"


def _load_hook():
    spec = importlib.util.spec_from_file_location("session_start_hook", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_worktree(tmp_path):
    """Baut ein simuliertes Hauptrepo mit Worktree darunter.

    Rueckgabe: (mainrepo_root, worktree_root).
    """
    mainrepo = tmp_path / "gregor"
    worktree = mainrepo / ".claude" / "worktrees" / "testws"
    worktree.mkdir(parents=True)
    return mainrepo, worktree


# --- Worktree-Erkennung ---------------------------------------------------


def test_hauptrepo_pfad_loest_keine_aktion_aus(tmp_path):
    """CLAUDE_PROJECT_DIR ohne /.claude/worktrees/ -> keine Aktion."""
    hook = _load_hook()
    mainrepo = tmp_path / "gregor"
    (mainrepo / "frontend").mkdir(parents=True)
    # node_modules im Hauptrepo, damit ein Symlink theoretisch moeglich waere
    (mainrepo / "frontend" / "node_modules").mkdir()
    (mainrepo / ".venv" / "bin").mkdir(parents=True)
    (mainrepo / ".venv" / "bin" / "python").write_text("#!/bin/sh\n")

    rc = hook.run(str(mainrepo))

    assert rc == 0
    # Kein zusaetzlicher Symlink, .venv unangetastet
    assert not (mainrepo / "frontend" / "node_modules").is_symlink()
    assert (mainrepo / ".venv" / "bin" / "python").exists()


# --- node_modules-Fix -----------------------------------------------------


def test_fehlendes_node_modules_wird_symlink(tmp_path):
    hook = _load_hook()
    mainrepo, worktree = _make_worktree(tmp_path)
    # Hauptrepo hat echtes node_modules
    (mainrepo / "frontend" / "node_modules").mkdir(parents=True)
    # Worktree hat frontend/, aber KEIN node_modules
    (worktree / "frontend").mkdir(parents=True)

    rc = hook.run(str(worktree))

    assert rc == 0
    link = worktree / "frontend" / "node_modules"
    assert link.is_symlink()
    assert link.resolve() == (mainrepo / "frontend" / "node_modules").resolve()


def test_vorhandenes_node_modules_wird_nicht_ueberschrieben(tmp_path):
    hook = _load_hook()
    mainrepo, worktree = _make_worktree(tmp_path)
    (mainrepo / "frontend" / "node_modules").mkdir(parents=True)
    # Worktree hat bereits ein ECHTES node_modules-Verzeichnis
    (worktree / "frontend" / "node_modules").mkdir(parents=True)
    marker = worktree / "frontend" / "node_modules" / "keep.txt"
    marker.write_text("keep")

    rc = hook.run(str(worktree))

    assert rc == 0
    nm = worktree / "frontend" / "node_modules"
    assert not nm.is_symlink()
    assert marker.exists()


def test_kein_frontend_im_worktree_kein_fehler(tmp_path):
    hook = _load_hook()
    mainrepo, worktree = _make_worktree(tmp_path)
    (mainrepo / "frontend" / "node_modules").mkdir(parents=True)
    # Worktree ohne frontend/

    rc = hook.run(str(worktree))

    assert rc == 0
    assert not (worktree / "frontend").exists()


# --- venv-Erkennung -------------------------------------------------------


def test_is_venv_broken_true_bei_unzugaenglich(tmp_path):
    hook = _load_hook()
    py = tmp_path / ".venv" / "bin" / "python"
    py.parent.mkdir(parents=True)
    py.write_text("#!/bin/sh\n")
    os.chmod(py, 0o000)
    try:
        assert hook.is_venv_broken(tmp_path) is True
    finally:
        os.chmod(py, 0o755)


def test_is_venv_broken_false_bei_zugaenglich(tmp_path):
    hook = _load_hook()
    py = tmp_path / ".venv" / "bin" / "python"
    py.parent.mkdir(parents=True)
    py.write_text("#!/bin/sh\n")
    os.chmod(py, 0o755)
    assert hook.is_venv_broken(tmp_path) is False


def test_is_venv_broken_false_bei_fehlendem_venv(tmp_path):
    hook = _load_hook()
    assert hook.is_venv_broken(tmp_path) is False


def test_repair_venv_schiebt_kaputtes_beiseite_und_ruft_runner(tmp_path):
    hook = _load_hook()
    venv = tmp_path / ".venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin" / "python").write_text("#!/bin/sh\n")

    calls = []

    def fake_runner(cmd, **kwargs):
        calls.append((cmd, kwargs))

        class _R:
            returncode = 0

        return _R()

    hook.repair_venv(tmp_path, runner=fake_runner)

    # Kaputtes .venv wurde umbenannt (nicht geloescht)
    assert not venv.exists()
    broken = list(tmp_path.glob(".venv.broken-*"))
    assert len(broken) == 1
    assert (broken[0] / "bin" / "python").exists()
    # Runner wurde mit uv sync im richtigen cwd aufgerufen
    assert len(calls) == 1
    cmd, kwargs = calls[0]
    assert cmd[:2] == ["uv", "sync"]
    assert str(kwargs.get("cwd")) == str(tmp_path)


# --- Nie blockieren -------------------------------------------------------


def test_run_immer_exit0_bei_kaputtem_venv_im_worktree(tmp_path):
    """Volllauf im Worktree: unzugaengliches .venv -> beiseite + Runner, Exit 0."""
    hook = _load_hook()
    mainrepo, worktree = _make_worktree(tmp_path)
    py = worktree / ".venv" / "bin" / "python"
    py.parent.mkdir(parents=True)
    py.write_text("#!/bin/sh\n")
    os.chmod(py, 0o000)

    calls = []

    def fake_runner(cmd, **kwargs):
        calls.append(cmd)

        class _R:
            returncode = 0

        return _R()

    try:
        rc = hook.run(str(worktree), runner=fake_runner)
    finally:
        for b in worktree.glob(".venv.broken-*"):
            os.chmod(b / "bin" / "python", 0o755)

    assert rc == 0
    assert list(worktree.glob(".venv.broken-*"))
    assert calls and calls[0][:2] == ["uv", "sync"]


def test_run_wirft_nie_und_exit0_ohne_frontend_ohne_venv(tmp_path):
    hook = _load_hook()
    mainrepo, worktree = _make_worktree(tmp_path)
    # weder frontend noch .venv
    rc = hook.run(str(worktree))
    assert rc == 0


def test_run_exit0_wenn_runner_fehler_wirft(tmp_path):
    hook = _load_hook()
    mainrepo, worktree = _make_worktree(tmp_path)
    py = worktree / ".venv" / "bin" / "python"
    py.parent.mkdir(parents=True)
    py.write_text("#!/bin/sh\n")
    os.chmod(py, 0o000)

    def boom(cmd, **kwargs):
        raise RuntimeError("uv sync explodiert")

    try:
        rc = hook.run(str(worktree), runner=boom)
    finally:
        for b in worktree.glob(".venv.broken-*"):
            if (b / "bin" / "python").exists():
                os.chmod(b / "bin" / "python", 0o755)

    assert rc == 0
