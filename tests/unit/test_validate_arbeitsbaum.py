"""`.claude/validate.py` prueft den ARBEITSBAUM, nicht den Claim-State (#2228).

Fehlerbild: validate.py las die zu pruefenden Dateien aus `files_changed` der
State-Datei. Die wird im Alltag nicht befuellt -> „Keine Änderungen zu
validieren" trotz geaenderter Dateien; die Pflicht-Validierung vor „teste es"
war wirkungslos.

Nachweis: validate.py wird in ein Wegwerf-Git-Repo kopiert (dort ist
`Path(__file__).parent.parent` die Repo-Wurzel) und als echter Unterprozess
mit `--quick` (nur Syntax) gestartet. Pfadregel #1409: Pruefling relativ zu
DIESER Datei aufgeloest.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

_VALIDATE = Path(__file__).resolve().parents[2] / ".claude" / "validate.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True, text=True)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / "src" / "app").mkdir(parents=True)
    shutil.copy(_VALIDATE, repo / ".claude" / "validate.py")
    (repo / "src" / "app" / "alt.py").write_text("X = 1\n")
    (repo / "src" / "app" / "unberuehrt.py").write_text("Y = 2\n")
    _git(tmp_path, "init", "-q", str(repo))
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "T")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "basis")
    return repo


def _validate(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(repo / ".claude" / "validate.py"), "--quick"],
        cwd=str(repo), capture_output=True, text=True, timeout=60,
    )


def test_syntaxfehler_im_arbeitsbaum_wird_gefunden(tmp_path):
    """Given eine geaenderte (unstaged) Datei mit Syntaxfehler und keine
    State-Datei / When validate.py laeuft / Then Exit 1 und die Datei ist
    genannt (vorher: 'Keine Änderungen', Exit 0)."""
    repo = _repo(tmp_path)
    (repo / "src" / "app" / "alt.py").write_text("def kaputt(:\n")
    r = _validate(repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "src/app/alt.py" in r.stdout


def test_staged_und_untracked_werden_geprueft_unberuehrte_nicht(tmp_path):
    """Given eine staged geaenderte und eine neue (untracked) .py-Datei /
    Then prueft validate.py genau diese beiden, nicht die unberuehrte."""
    repo = _repo(tmp_path)
    (repo / "src" / "app" / "alt.py").write_text("X = 3\n")
    _git(repo, "add", "src/app/alt.py")
    (repo / "src" / "app" / "neu.py").write_text("Z = 4\n")
    r = _validate(repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "src/app/alt.py" in r.stdout and "src/app/neu.py" in r.stdout
    assert "unberuehrt.py" not in r.stdout
