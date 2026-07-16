"""TDD RED: alle vier Mail-Validatoren schreiben ihr Validation-YAML in einen
git-Worktree hinein, statt (wie das Renderer-Mail-Gate liest) ins
shared-repo `_log` (Issue #1282, Fix-Workflow fix-1282-1283-gate-honesty,
AC-4).

Mocks sind in diesem Projekt VERBOTEN. Alle Tests laufen gegen ein echtes
Temp-Git-Repo mit einem echten `git worktree add`-Linked-Worktree + echte
Direktimporte der Validator-Kopien (Vorbild: Modul-Kopie-Muster aus
tests/tdd/test_issue_1084_gate_scope_cache.py). Kein Netz, keine echte
Mail-Zustellung -- nur die Log-Schreib-Funktion wird direkt aufgerufen.

Getestete AC (docs/specs/modules/gate_honesty_mail_selftest.md):
  AC-4: Given alle vier Validatoren (briefing, email_spec, radar, official)
        laufen in einem git-Worktree / When sie ihr Validation-YAML
        schreiben / Then landet es im shared-repo `_log`
        (git-common-dir, via `_e2e_paths.shared_repo_dir()`) -- das Gate
        (das ueber `_shared_repo_root()` aus dem Hauptrepo liest) sieht den
        Nachweis auch aus einem Worktree heraus. Liefert `shared_repo_dir()`
        None (kein Git-Repo), greift der bisherige `__file__`-relative
        Fallback.

Aktuell (rot): alle vier Validatoren ermitteln ihren log_dir ausschliesslich
`__file__`-relativ (z.B. `hooks_dir.parent / "workflows" / "_log"`). Aus
einem Worktree heraus zeigt das auf den Worktree-lokalen Pfad, nicht auf das
Hauptrepo -- das Gate im Hauptrepo sieht den Nachweis nie.
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOKS_SRC = _REPO_ROOT / ".claude" / "hooks"

# (Dateiname, Log-Datei-Glob-Muster, Zusatz-Kwargs fuer _write_validation_log)
_VALIDATORS = [
    ("briefing_mail_validator.py", "*_briefing_validation.yaml", {}),
    ("email_spec_validator.py", "*_email_validation.yaml", {"min_locations": 3}),
    ("radar_alert_mail_validator.py", "*_radar_alert_validation.yaml", {}),
    ("official_alert_mail_validator.py", "*_official_alert_validation.yaml", {}),
]


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, check=True,
                           capture_output=True, text=True)


def _setup_main_with_worktree(tmp_path: Path, module_filename: str) -> tuple[Path, Path]:
    """Echtes Hauptrepo + echter Linked-Worktree (`git worktree add`).

    Der Validator wird ins Hauptrepo committet, bevor der Worktree angelegt
    wird -- dadurch bekommt der Worktree automatisch seine EIGENE
    (Working-Tree-lokale) Kopie der Datei, exakt wie im echten Projekt.
    """
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init")
    _git(main, "config", "user.email", "t@t.de")
    _git(main, "config", "user.name", "Test")

    hooks = main / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    shutil.copy(_HOOKS_SRC / module_filename, hooks / module_filename)
    (main / "README.md").write_text("# baseline\n")
    _git(main, "add", "-A")
    _git(main, "commit", "-m", "baseline")

    wt = tmp_path / "worktree"
    _git(main, "worktree", "add", str(wt), "-b", "wt-branch")
    return main, wt


def _load_module_from(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# AC-4: aus dem Worktree geschriebenes Log muss im Hauptrepo-_log landen
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("module_filename,glob_pattern,extra_kwargs", _VALIDATORS)
def test_validator_writes_log_into_shared_main_repo_not_worktree(
    tmp_path, module_filename, glob_pattern, extra_kwargs,
):
    main, wt = _setup_main_with_worktree(tmp_path, module_filename)

    wt_module_path = wt / ".claude" / "hooks" / module_filename
    assert wt_module_path.exists(), (
        f"Testvoraussetzung: Worktree hat eigene Hooks-Kopie ({wt_module_path})"
    )

    mod_name = f"validator_{module_filename.replace('.', '_')}_{tmp_path.name}"
    mod = _load_module_from(wt_module_path, mod_name)

    mod._write_validation_log(success=True, errors=[], **extra_kwargs)

    main_log_dir = main / ".claude" / "workflows" / "_log"
    wt_log_dir = wt / ".claude" / "workflows" / "_log"
    main_logs = list(main_log_dir.glob(glob_pattern))
    wt_logs = list(wt_log_dir.glob(glob_pattern))

    assert main_logs, (
        f"AC-4: {module_filename} muss aus einem Worktree heraus in das "
        f"shared-repo _log ({main_log_dir}) schreiben (Auflösung ueber "
        "_e2e_paths.shared_repo_dir(), git-common-dir), nicht nur "
        f"worktree-lokal ({wt_log_dir}). Aktuell (rot) berechnet "
        f"{module_filename} seinen log_dir ausschliesslich __file__-relativ. "
        f"main_logs={main_logs!r} wt_logs={wt_logs!r}"
    )


# ---------------------------------------------------------------------------
# Fail-soft: ausserhalb eines Git-Repos greift weiterhin der alte Fallback
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("module_filename,glob_pattern,extra_kwargs", _VALIDATORS)
def test_validator_log_write_succeeds_without_git_repo_fail_soft(
    tmp_path, module_filename, glob_pattern, extra_kwargs,
):
    """AC-4 Fail-soft: liefert shared_repo_dir() None (kein Git-Repo im
    Pfad), muss der bisherige __file__-relative Fallback weiterhin greifen
    -- kein Absturz, das Log wird trotzdem irgendwo geschrieben."""
    standalone = tmp_path / "standalone_no_git"
    hooks_dir = standalone / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True)
    shutil.copy(_HOOKS_SRC / module_filename, hooks_dir / module_filename)

    mod_name = f"validator_nogit_{module_filename.replace('.', '_')}_{tmp_path.name}"
    mod = _load_module_from(hooks_dir / module_filename, mod_name)

    mod._write_validation_log(success=True, errors=[], **extra_kwargs)

    logs = list((standalone / ".claude" / "workflows" / "_log").glob(glob_pattern))
    assert logs, (
        f"Fail-soft-Fallback: ausserhalb eines Git-Repos muss {module_filename} "
        f"weiterhin ein Log schreiben (__file__-relativer Fallback). logs={logs!r}"
    )
