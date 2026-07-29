"""TDD RED — Issue #1409 (Lieferung A): Wirkungsnachweis worktree-relative Pruefling-Pfade.

SPEC: docs/specs/modules/fix_1409_worktree_test_paths.md (AC-5, AC-6)

Ein reiner Pfad-Assert ("liegt der Pfad unter der Worktree-Wurzel?") waere selbst
wieder Kosmetik. Belastbar ist nur der Mutations-Beleg: ein Miniatur-Repo in
tmp_path bekommt eine echte Kopie der Testdatei UND eine echte Kopie ihres
Pruefling-Hooks. Dann wird ausschliesslich die tmp_path-Kopie des Prueflings
gebrochen und dieselbe Testfunktion als echter pytest-Subprozess laufen gelassen.

  * Loest die Testdatei ihren Pruefling worktree-relativ auf, sieht sie den
    gebrochenen Pruefling  -> Subprozess-Exit != 0  -> hier GRUEN.
  * Ist der Hauptrepo-Pfad fest verdrahtet (heutiger Zustand), laedt sie die
    unberuehrte Hauptrepo-Kopie -> Subprozess-Exit 0 (falsches Gruen)
    -> hier ROT. Das ist die RED-Bedingung dieser Datei.

RED-Erwartung (Stand vor dem Fix):
  AC-6 Exemplar 1 FAIL: test_issue_862_849_col_labels.py bleibt trotz gebrochener
                        tmp_path-Kopie von briefing_mail_validator.py gruen.
  AC-6 Exemplar 2 FAIL: test_622_fidelity_pre_actions.py bleibt trotz gebrochener
                        tmp_path-Kopie von design_fidelity_diff.py gruen.
  AC-5      FAIL: test_issue_465_workflow_optimierung.py verweist noch auf
                  .claude/hooks/workflow.py — eine Datei, die es nirgends gibt.

Ausfuehrung:
    uv run pytest tests/tdd/test_worktree_path_resolution_effect.py -v
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Startet pytest im pytest: der Subprozess-Lauf sprengt das globale ini-Timeout
# (30s, #1210). Muster: test_622_fidelity_pre_actions.py:31.
pytestmark = pytest.mark.timeout(180)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOKS_DIR = _REPO_ROOT / ".claude" / "hooks"
_TDD_DIR = _REPO_ROOT / "tests" / "tdd"

_SUBPROC_TIMEOUT = 120


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _build_mini_repo(tmp_path: Path, test_src: Path, hook_src: Path) -> tuple[Path, Path]:
    """Miniatur-Repo mit derselben Verzeichnistiefe wie das echte Repo.

    tmp_path/tests/tdd/<test>.py  +  tmp_path/.claude/hooks/<hook>.py
    Die Tiefe muss stimmen, damit Path(__file__).resolve().parents[2] in der
    Kopie auf tmp_path zeigt.

    Mitkopiert werden zusaetzlich die Geschwister-Hilfsmodule `_*.py` aus dem
    Hook-Verzeichnis: Pruefling wie briefing_mail_validator.py erweitern beim
    Import sys.path um ihr EIGENES Verzeichnis (Zeile 34) und importieren von
    dort `_e2e_paths`/`_validator_log`. Ohne sie waere die tmp_path-Kopie schon
    gar nicht ladbar (ModuleNotFoundError) — der Nachweis wuerde am Import
    scheitern statt an der Mutation. Mutiert wird weiterhin ausschliesslich die
    Pruefling-Kopie, nie ein Hilfsmodul.
    """
    assert test_src.exists(), f"Testdatei nicht gefunden: {test_src}"
    assert hook_src.exists(), f"Pruefling nicht gefunden: {hook_src}"

    tests_dir = tmp_path / "tests" / "tdd"
    hooks_dir = tmp_path / ".claude" / "hooks"
    tests_dir.mkdir(parents=True, exist_ok=True)
    hooks_dir.mkdir(parents=True, exist_ok=True)

    test_copy = tests_dir / test_src.name
    hook_copy = hooks_dir / hook_src.name
    shutil.copy2(test_src, test_copy)
    shutil.copy2(hook_src, hook_copy)
    for helper in sorted(hook_src.parent.glob("_*.py")):
        shutil.copy2(helper, hooks_dir / helper.name)

    assert test_copy.resolve().parents[2] == tmp_path.resolve(), (
        "Miniatur-Repo hat die falsche Tiefe — parents[2] der Testkopie zeigt "
        f"auf {test_copy.resolve().parents[2]} statt auf {tmp_path.resolve()}."
    )
    return test_copy, hook_copy


def _run_pytest_in(mini_repo: Path, nodeid: str) -> subprocess.CompletedProcess:
    """Gezielte Testfunktion als echter pytest-Subprozess im Miniatur-Repo."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    return subprocess.run(
        [sys.executable, "-m", "pytest", nodeid, "-p", "no:cacheprovider", "-q"],
        cwd=str(mini_repo),
        capture_output=True,
        text=True,
        timeout=_SUBPROC_TIMEOUT,
        env=env,
    )


def _assert_control_green(result: subprocess.CompletedProcess, label: str) -> None:
    assert result.returncode == 0, (
        f"{label}: Kontroll-Lauf VOR der Mutation ist nicht gruen (Exit "
        f"{result.returncode}). Damit ist weder Mutation noch Testfunktions-Auswahl "
        "belastbar — der Bug ist dann NICHT bewiesen.\n"
        f"stdout:\n{result.stdout[-1500:]}\nstderr:\n{result.stderr[-800:]}"
    )


def _assert_mutation_seen(result: subprocess.CompletedProcess, label: str, hook: str) -> None:
    assert result.returncode != 0, (
        f"{label}: Die tmp_path-Kopie von {hook} ist gebrochen, der Test meldet "
        "aber weiter Gruen (Exit 0). Er hat also NICHT die gebrochene Kopie "
        "geladen, sondern die unberuehrte Hauptrepo-Kopie — genau der Bug aus "
        "#1409. Fix: Pruefling worktree-relativ ueber "
        "Path(__file__).resolve().parents[2] aufloesen.\n"
        f"stdout:\n{result.stdout[-1500:]}"
    )


# ─── AC-6, Exemplar 1: glatter Fall (nur Pruefling-Pfad) ─────────────────────

def test_ac6_glatter_fall_briefing_mail_validator(tmp_path):
    """AC-6: test_issue_862_849_col_labels.py muss den Worktree-Validator laden.

    Gewaehlte Testfunktion: test_validator_en_blacklist_removed — sie laedt den
    Pruefling per importlib und braucht kein Netz.
    Mutation: _EN_BLACKLIST wird in der tmp_path-Kopie wieder eingefuehrt; genau
    dessen Abwesenheit prueft die Testfunktion.
    """
    test_copy, hook_copy = _build_mini_repo(
        tmp_path,
        _TDD_DIR / "test_issue_862_849_col_labels.py",
        _HOOKS_DIR / "briefing_mail_validator.py",
    )
    nodeid = f"tests/tdd/{test_copy.name}::test_validator_en_blacklist_removed"

    _assert_control_green(_run_pytest_in(tmp_path, nodeid), "Exemplar 1")

    original = hook_copy.read_text()
    assert "_EN_BLACKLIST" not in original, (
        "Mutation waere wirkungslos: _EN_BLACKLIST steht bereits im Pruefling."
    )
    hook_copy.write_text(original + '\n\n_EN_BLACKLIST = ["MUTATION-1409"]\n')

    _assert_mutation_seen(
        _run_pytest_in(tmp_path, nodeid), "Exemplar 1", "briefing_mail_validator.py"
    )


# ─── AC-6, Exemplar 2: gemischter Fall (Drei-Konstanten-Split) ──────────────

def test_ac6_gemischter_fall_design_fidelity_diff(tmp_path):
    """AC-6: test_622_fidelity_pre_actions.py muss das Worktree-Diff-Tool lesen.

    Gewaehlte Testfunktion: test_ac4_pre_action_registered_for_step2 — sie liest
    den Pruefling als Text und braucht weder Playwright noch SOLL-Bilder.
    Mutation: der SCREEN_PRE_ACTIONS-Schluessel wird in der tmp_path-Kopie
    umbenannt; die Datei bleibt gueltiges Python.
    """
    test_copy, hook_copy = _build_mini_repo(
        tmp_path,
        _TDD_DIR / "test_622_fidelity_pre_actions.py",
        _HOOKS_DIR / "design_fidelity_diff.py",
    )
    nodeid = (
        f"tests/tdd/{test_copy.name}"
        "::TestAC4WizardStep2EtappenPreAction::test_ac4_pre_action_registered_for_step2"
    )

    _assert_control_green(_run_pytest_in(tmp_path, nodeid), "Exemplar 2")

    original = hook_copy.read_text()
    anchor = '"I-wizard-step2-etappen": [\n'
    assert original.count(anchor) == 1, (
        f"Mutations-Anker {anchor!r} kommt {original.count(anchor)}x vor "
        "(erwartet: genau 1x) — Mutation nicht eindeutig platzierbar."
    )
    hook_copy.write_text(
        original.replace(anchor, '"I-wizard-step2-etappen-MUTATION-1409": [\n')
    )

    _assert_mutation_seen(
        _run_pytest_in(tmp_path, nodeid), "Exemplar 2", "design_fidelity_diff.py"
    )


# ─── AC-5: kein Verweis mehr auf den nicht existierenden workflow.py ────────

def test_ac5_issue_465_hat_keinen_toten_workflow_py_verweis():
    """AC-5: In test_issue_465_workflow_optimierung.py darf kein Verweis auf
    .claude/hooks/workflow.py mehr stehen.

    Geprueft wird die WIRKUNG, nicht blosse String-Presenz: fuer jeden gefundenen
    Verweis wird belegt, dass die Zieldatei gar nicht existiert. Ein Test ueber
    einen nicht existierenden Pruefling kann nichts pruefen — der Interpreter
    liefert Exit 2 ("can't open file"), was ein `returncode != 0`-Assert als
    Erfolg verbucht: strukturell falsches Gruen.
    """
    target = _TDD_DIR / "test_issue_465_workflow_optimierung.py"
    src = target.read_text()

    referenced = re.findall(r'["\']([^"\']*/workflow\.py)["\']', src)
    dead = [p for p in referenced if not Path(p).exists()]
    assert not dead, (
        f"{target.name} verweist auf workflow.py-Pfade, die nirgends existieren: "
        f"{dead}. Jeder Test darueber ist strukturell falsch gruen (Interpreter-"
        "Exit 2 statt Pruefling-Verhalten). workflow.py ist seit der "
        "Plugin-Migration kein Repo-Bestandteil mehr — Verweis und zugehoeriger "
        "Test sind zu loeschen (Spec #1409, Abschnitt 2)."
    )

    leftovers = [
        f"Zeile {i}: {line.strip()}"
        for i, line in enumerate(src.splitlines(), start=1)
        if re.search(r"\bWORKFLOW_PY\b", line)
    ]
    assert not leftovers, (
        f"WORKFLOW_PY taucht in {target.name} noch auf: {leftovers}. "
        "Konstante und der darauf laufende Test sind ersatzlos zu entfernen."
    )
