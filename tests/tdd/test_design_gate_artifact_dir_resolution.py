"""TDD RED — #1307 Scheibe B, AC-12: Werkzeug und Wächter müssen denselben
Ordner meinen.

Das Vergleichswerkzeug `design_fidelity_diff.py` löst den Ordnernamen für
seinen Bericht über `GZ_ACTIVE_WORKFLOW` auf (`:271`), der Wächter
`pre_issue_close_design_gate.py` sucht ihn über `OPENSPEC_ACTIVE_WORKFLOW`
(`:50`). Werkzeug schreibt nach A, Wächter sucht in B — der frische Bericht
wird nie gefunden.

Geprüft wird die WIRKUNG, nicht der Quelltext: das Werkzeug wird echt
ausgeführt (es legt sein Artefakt-Verzeichnis an, bevor es das fehlende
Soll-Bild bemerkt — kein Netz, kein Playwright nötig), und der Wächter wird
echt ausgeführt. Für jede der beiden Schreibweisen der Workflow-Kennung muss
gelten: der vom Werkzeug angelegte Ordner ist genau der, in dem der Wächter
nachsieht.

Der Wächter wird dabei in BEIDE Richtungen gemessen (mit Nachweis → durch,
ohne Nachweis → blockiert). Nur so ist ein echtes „hier habe ich gesucht" von
einem stillen Fail-open (Exit 0, weil die Kennung gar nicht aufgelöst wurde)
unterscheidbar.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Prüflinge relativ zu DIESER Testdatei (Pfadregel #1409) — sonst prüft ein
# Worktree-Lauf die unveränderte Hauptrepo-Kopie und meldet falsches Grün.
_REPO_ROOT = Path(__file__).resolve().parents[2]
DIFF_TOOL = _REPO_ROOT / ".claude" / "hooks" / "design_fidelity_diff.py"
GATE_HOOK = _REPO_ROOT / ".claude" / "hooks" / "pre_issue_close_design_gate.py"

_WORKFLOW_ENV_VARS = ("OPENSPEC_ACTIVE_WORKFLOW", "GZ_ACTIVE_WORKFLOW")
# Trägt das Label design-compliance (sonst greift der Wächter gar nicht).
_GATE_ISSUE = "603"
# Kein Eintrag in SCREEN_URL_MAP und kein Soll-Bild: das Werkzeug bricht nach
# dem Anlegen des Artefakt-Verzeichnisses ab — genau der Seitenblick, den wir
# brauchen, ohne Staging-Zugriff.
_SCREEN = "test-1307b-kein-sollbild"


def _clean_env(project_dir: Path, workflow: str, var: str) -> dict:
    """Umgebung vollständig selbst gesetzt: beide Schreibweisen erst raus,
    dann genau eine gezielt rein (AC-14-Muster)."""
    env = {k: v for k, v in os.environ.items() if k not in _WORKFLOW_ENV_VARS}
    env[var] = workflow
    env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    env.setdefault("GH_REPO", "henemm/gregor_zwanzig")
    return env


def _run_tool(project_dir: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(DIFF_TOOL), "--screen", _SCREEN],
        capture_output=True, text=True, env=env, cwd=str(project_dir),
    )


def _run_gate(project_dir: Path, env: dict) -> subprocess.CompletedProcess:
    env = {**env, "CLAUDE_TOOL_INPUT": json.dumps(
        {"command": f"gh issue close {_GATE_ISSUE}"})}
    return subprocess.run(
        [sys.executable, str(GATE_HOOK)],
        capture_output=True, text=True, env=env, cwd=str(project_dir),
    )


def _artifact_dirs(project_dir: Path) -> list[str]:
    root = project_dir / "docs" / "artifacts"
    return sorted(p.name for p in root.iterdir()) if root.is_dir() else []


@pytest.mark.parametrize("var", ["OPENSPEC_ACTIVE_WORKFLOW", "GZ_ACTIVE_WORKFLOW"])
def test_tool_and_gate_resolve_the_same_artifact_dir(tmp_path, var):
    """AC-12: Egal welche der beiden Kennungen gesetzt ist — der Bericht landet
    in genau dem Ordner, in dem der Wächter danach sucht."""
    workflow = f"test-1307b-artifact-dir-{var.lower()}"
    env = _clean_env(tmp_path, workflow, var)
    expected = tmp_path / "docs" / "artifacts" / workflow

    # 1) Werkzeug laufen lassen — legt sein Artefakt-Verzeichnis an.
    tool = _run_tool(tmp_path, env)
    assert _artifact_dirs(tmp_path), (
        "Das Werkzeug hat gar kein Artefakt-Verzeichnis angelegt — der Test "
        f"misst nichts. stdout={tool.stdout[:200]!r} stderr={tool.stderr[:200]!r}"
    )
    assert _artifact_dirs(tmp_path) == [workflow], (
        f"Das Werkzeug legt seinen Bericht unter {_artifact_dirs(tmp_path)} ab, "
        f"erwartet wurde der Ordner der gesetzten Workflow-Kennung ({workflow}). "
        f"Gesetzt war {var}."
    )

    # 2) Wächter mit bestandenem Bericht in genau diesem Ordner → lässt durch.
    (expected / f"design-diff-{_SCREEN}.json").write_text(json.dumps({
        "screen": _SCREEN, "diff_pct": 1.0, "passed": True, "workflow": workflow,
    }))
    allowed = _run_gate(tmp_path, env)
    assert allowed.returncode == 0, (
        f"Wächter findet den Bericht in {expected} nicht (Exit "
        f"{allowed.returncode}) — er sucht in einem anderen Ordner als das "
        f"Werkzeug schreibt. Gesetzt war {var}.\n"
        f"stdout: {allowed.stdout[:300]}\nstderr: {allowed.stderr[:300]}"
    )

    # 3) Gegenprobe: ohne Bericht muss er blockieren. Ohne diesen Schritt wäre
    #    ein stilles Fail-open (Kennung gar nicht aufgelöst → Exit 0) von einem
    #    echten Treffer nicht zu unterscheiden.
    (expected / f"design-diff-{_SCREEN}.json").unlink()
    blocked = _run_gate(tmp_path, env)
    assert blocked.returncode == 2, (
        f"Wächter muss ohne Bericht blockieren (Exit 2), lieferte Exit "
        f"{blocked.returncode} — vermutlich hat er die Workflow-Kennung {var} "
        "gar nicht aufgelöst und ist still durchgelaufen.\n"
        f"stdout: {blocked.stdout[:300]}\nstderr: {blocked.stderr[:300]}"
    )
