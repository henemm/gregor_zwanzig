"""
TDD RED — Issue #784: staging_gate taggt Worktree-HEAD statt Hauptrepo-HEAD.

Mocks sind in diesem Projekt VERBOTEN. Alle Tests laufen gegen das ECHTE
`staging_gate.py`/`_e2e_paths.py`, ein echtes temporäres Git-Repo (Hauptrepo) und
einen echten daran hängenden `git worktree`. Es wird KEIN Mock/patch eingesetzt —
nur reale Git-Operationen, reale Subprozess-Aufrufe und reale Dateien.

Bug-Reproduktion aus der Praxis (#733, #744, #760, #770, #777): Wird `--write-verdict`
mit cwd im Worktree (Commit B) ausgeführt, während das Hauptrepo auf Commit A steht,
trägt die Attestation fälschlich A (bzw. den HEAD des hartkodierten Hauptrepos) statt B.

Getestete ACs (docs/specs/modules/issue_784_staging_gate_worktree_head.md):
  AC-1: --write-verdict aus Worktree → verified_commit == Worktree-HEAD (B), nicht A.
  AC-1/Ort: shared_repo_dir(cwd=worktree) == Hauptrepo, worktree_repo_dir == Worktree.
  AC-2: --check aus Worktree mit B-Attestation → Exit 0 (keine ff-Krücke).
  AC-3: --check aus Hauptrepo (HEAD=A) mit B-Attestation → Exit 1 (Mismatch, schärfer).

RED-Sicherheit: Die Subprozess-`--write-verdict`/`--check`-Tests übergeben `--e2e-path`
in das TEMP-Repo, damit die noch unkorrigierte (buggy) Version NICHT ins echte
Hauptrepo `/home/hem/gregor_zwanzig` schreibt. Der eigentliche Bug zeigt sich am
`verified_commit`-Feld bzw. am Exit-Code, nicht am Schreibziel.
"""

import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
STAGING_GATE = HOOKS_DIR / "staging_gate.py"
E2E_PATHS = HOOKS_DIR / "_e2e_paths.py"
# sys.path-Einfügung für _e2e_paths-Import zentral in tests/tdd/conftest.py.


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git(args, cwd):
    return subprocess.run(["git"] + args, capture_output=True, text=True, cwd=str(cwd))


def _load_module(path: Path, name: str):
    if not path.exists():
        raise FileNotFoundError(f"{path} existiert nicht")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _init_main_repo(root: Path) -> str:
    """Hauptrepo mit 2 Commits (HEAD~1 existiert), HEAD = A, src/ berührt (backend)."""
    _git(["init", "-q", "-b", "main"], root)
    _git(["config", "user.email", "t@example.com"], root)
    _git(["config", "user.name", "Tester"], root)
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    (root / "src" / "x.py").write_text("a = 1\n")
    _git(["add", "-A"], root)
    _git(["commit", "-qm", "A1"], root)
    (root / "src" / "x.py").write_text("a = 2\n")
    _git(["add", "-A"], root)
    _git(["commit", "-qm", "A2 (main HEAD)"], root)
    return _git(["rev-parse", "HEAD"], root).stdout.strip()


@pytest.fixture
def main_and_worktree(tmp_path):
    """Echtes Hauptrepo (HEAD=A) + echter Worktree (HEAD=B, B != A), backend-Scope."""
    main = tmp_path / "main"
    main.mkdir()
    a = _init_main_repo(main)
    wt = tmp_path / "wt"
    _git(["worktree", "add", "-q", "-b", "ws-784", str(wt), "HEAD"], main)
    # Eigener Commit B im Worktree (berührt src/ → backend-Scope, nicht docs-only).
    (wt / "src" / "x.py").write_text("a = 3  # worktree change\n")
    _git(["add", "-A"], wt)
    _git(["commit", "-qm", "B (worktree HEAD)"], wt)
    b = _git(["rev-parse", "HEAD"], wt).stdout.strip()
    # Hauptrepo bleibt auf A.
    assert _git(["rev-parse", "HEAD"], main).stdout.strip() == a
    assert a != b
    return main, wt, a, b


def _run_gate(args, cwd):
    env = dict(os.environ)
    env.pop("GZ_SKIP_E2E_GATE", None)  # Notfall-Override darf Test nicht verfälschen.
    return subprocess.run(
        [sys.executable, str(STAGING_GATE)] + args,
        capture_output=True, text=True, cwd=str(cwd), env=env,
    )


def _write_attestation(main: Path, commit: str, scope: str = "backend") -> Path:
    out = main / ".claude" / "e2e_verified" / f"{commit}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "verified_commit": commit,
        "staging_verdict": "VERIFIED: alles gut",
        "findings": [],
        "verified_at": _now_iso(),
        "scope": scope,
        "environment": "staging",
    }))
    return out


# ---------------------------------------------------------------------------
# AC-1: write-verdict aus Worktree taggt Worktree-HEAD (B), nicht Hauptrepo-HEAD (A)
# ---------------------------------------------------------------------------
class TestWriteVerdictTagsWorktreeHead:
    def test_verified_commit_is_worktree_head(self, main_and_worktree, tmp_path):
        main, wt, a, b = main_and_worktree
        out = main / ".claude" / "e2e_verified" / f"{b}.json"
        findings = tmp_path / "findings.json"
        findings.write_text("[]")
        r = _run_gate(
            ["--write-verdict", "VERIFIED: ok",
             "--findings-json", str(findings),
             "--e2e-path", str(out)],
            cwd=wt,
        )
        assert r.returncode == 0, f"write-verdict scheiterte: {r.stderr}\n{r.stdout}"
        data = json.loads(out.read_text())
        # Kern des #784-Bugs: muss der Worktree-HEAD (B) sein, NICHT A, NICHT real-repo.
        assert data["verified_commit"] == b, (
            f"verified_commit={data['verified_commit'][:8]} erwartet B={b[:8]} "
            f"(A={a[:8]}) — taggt fälschlich Hauptrepo-/Fremd-HEAD."
        )
        assert data["verified_commit"] != a


# ---------------------------------------------------------------------------
# AC-1 (Ort): Pfad-Helfer trennen Datei-Ort (Hauptrepo) von Commit-Quelle (Worktree)
# ---------------------------------------------------------------------------
class TestRepoDirHelpers:
    def test_worktree_repo_dir_resolves_to_worktree(self, main_and_worktree):
        main, wt, a, b = main_and_worktree
        mod = _load_module(E2E_PATHS, "_e2e_paths_784")
        assert mod.worktree_repo_dir(cwd=wt).resolve() == wt.resolve()

    def test_shared_repo_dir_from_worktree_is_hauptrepo(self, main_and_worktree):
        main, wt, a, b = main_and_worktree
        mod = _load_module(E2E_PATHS, "_e2e_paths_784b")
        # --git-common-dir aus dem Worktree → <hauptrepo>/.git → .parent == Hauptrepo.
        assert mod.shared_repo_dir(cwd=wt).resolve() == main.resolve()

    def test_shared_repo_dir_from_hauptrepo_is_itself(self, main_and_worktree):
        main, wt, a, b = main_and_worktree
        mod = _load_module(E2E_PATHS, "_e2e_paths_784c")
        assert mod.shared_repo_dir(cwd=main).resolve() == main.resolve()


# ---------------------------------------------------------------------------
# AC-2: check aus Worktree mit B-Attestation → Exit 0 (keine ff-Krücke nötig)
# ---------------------------------------------------------------------------
class TestCheckFromWorktreePasses:
    def test_check_passes_for_worktree_head(self, main_and_worktree):
        main, wt, a, b = main_and_worktree
        att = _write_attestation(main, b)
        r = _run_gate(["--check", "--e2e-path", str(att), "--scope", "backend"], cwd=wt)
        assert r.returncode == 0, (
            f"--check aus Worktree (HEAD=B) sollte bestehen, "
            f"war Exit {r.returncode}: {r.stderr}\n{r.stdout}"
        )


# ---------------------------------------------------------------------------
# AC-3: check aus Hauptrepo (HEAD=A) mit B-Attestation → Exit 1 (schärfer, nicht schwächer)
# ---------------------------------------------------------------------------
class TestCheckFromHauptrepoBlocksMismatch:
    def test_check_blocks_when_head_mismatches_attestation(self, main_and_worktree):
        main, wt, a, b = main_and_worktree
        att = _write_attestation(main, b)
        r = _run_gate(["--check", "--e2e-path", str(att), "--scope", "backend"], cwd=main)
        assert r.returncode == 1, (
            f"--check aus Hauptrepo (HEAD=A != B) muss blocken, war Exit {r.returncode}: "
            f"{r.stdout}\n{r.stderr}"
        )
