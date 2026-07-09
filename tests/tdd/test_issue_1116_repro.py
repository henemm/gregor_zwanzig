"""
Reproduktionsbeweis fuer Issue #1116 (docs/specs/modules/issue_1109_1116_1121_gate_scope.md, Teil A).

Kein neuer Produktivcode fuer diesen Teil -- dieser Test stellt exakt das in
#1116 beschriebene Marker-Vergiftungsszenario nach und beweist, dass es durch
#1096 (Commit fab61d76) bereits strukturell unmoeglich geworden ist. Anders als
die Tests fuer Teil B/C dieser Spec ist dieser Test bewusst BEREITS GRUEN -- das
IST der Beweis (siehe AC-1). Mocks sind in diesem Projekt VERBOTEN; Test laeuft
gegen ein echtes Temp-Git-Repo + echte Subprozess-Aufrufe von staging_gate.py.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOKS_SRC = _REPO_ROOT / ".claude" / "hooks"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, check=True,
                           capture_output=True, text=True)


def _head_sha(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo,
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _setup_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.de")
    _git(repo, "config", "user.name", "Test")

    hooks = repo / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    for name in ("staging_gate.py", "prod_selftest.py", "_e2e_paths.py"):
        shutil.copy(_HOOKS_SRC / name, hooks / name)

    (repo / "README.md").write_text("# baseline\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "baseline")
    return repo


def _run_staging_gate(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(repo / ".claude" / "hooks" / "staging_gate.py"), *args],
        cwd=repo, capture_output=True, text=True,
    )


# ---------------------------------------------------------------------------
# AC-1 (#1116): Erneuter Scope-Aufruf auf demselben HEAD nach vollem
# gate_check()-Lauf liefert weiterhin den korrekten, gecachten Scope --
# KEINE Selbstvergiftung zu docs-only.
# ---------------------------------------------------------------------------

def test_repeated_check_on_same_head_does_not_poison_scope_to_docs_only(tmp_path):
    """Exaktes #1116-Szenario: gate_check() laeuft vollstaendig fuer HEAD
    (Marker zeigt danach exakt auf HEAD mit einem echten Nicht-docs-only-Scope).
    Ein erneuter Aufruf auf demselben HEAD darf NICHT den selbstreferenziellen
    HEAD..HEAD-Diff (leer -> faelschlich docs-only) verwenden, sondern muss den
    gecachten Scope liefern."""
    repo = _setup_repo(tmp_path)

    (repo / "src").mkdir()
    (repo / "src" / "foo.py").write_text("# backend change\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "backend change")
    sha = _head_sha(repo)

    e2e_path = repo / ".claude" / "e2e_verified.json"
    e2e_path.write_text(
        f'{{"verified_commit": "{sha}", "staging_verdict": "VERIFIED: alle ACs gruen", '
        f'"verified_at": "{datetime.now(timezone.utc).isoformat()}", '
        f'"environment": "staging", "scope": "backend", "findings": []}}'
    )

    first = _run_staging_gate(repo, "--check", "--e2e-path", str(e2e_path))
    assert first.returncode == 0, (
        f"Erster --check-Lauf muss bestehen (echter Backend-Commit, gueltiges "
        f"Attestat). rc={first.returncode} stderr={first.stderr!r}"
    )

    second = _run_staging_gate(repo, "--detect-scope")
    scope = (second.stdout + second.stderr).strip().lower()
    assert scope == "backend", (
        f"Zweiter Scope-Aufruf auf demselben HEAD (nach erfolgreichem "
        f"--check) muss weiterhin 'backend' liefern -- das #1116-Szenario "
        f"(faelschlich 'docs-only' durch Selbstreferenz) darf nicht auftreten. "
        f"scope={scope!r}"
    )
