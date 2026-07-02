"""
TDD RED Phase — Issue #930: Golden-Email-Gate

Drei Tests die ALLE JETZT FEHLSCHLAGEN, weil:
- renderer_mail_gate.py hat noch keinen golden_ok-Check (AC-1)
- tests/golden/email/regenerate.py existiert noch nicht (AC-2)
- settings.json hat noch keinen PreToolUse:Bash-Hook (AC-3)

Spec: docs/specs/modules/issue_930_golden_gate.md

Issue #939: test_renderer_mail_gate_has_golden_check() war ursprünglich ein
reiner Dateiinhalt-Check (`"golden_ok" in source`) — laut CLAUDE.md verboten.
Er wurde durch einen echten Subprozess-Verhaltenstest ersetzt (siehe unten),
der ein Temp-Git-Repo mit echtem src/tests-Stand aufbaut, einen Golden-
Snapshot korrumpiert und beweist, dass renderer_mail_gate.py den Commit
tatsächlich mit Exit 2 blockiert (Referenz-Pattern:
tests/tdd/test_issue_830_radar_alert_validator.py::_run_gate /
_make_temp_git_repo_with_workflow).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
GATE_PATH = REPO_ROOT / ".claude" / "hooks" / "renderer_mail_gate.py"
_MAIL_FILE_REL = Path("src") / "output" / "renderers" / "email" / "html.py"

_IGNORE = shutil.ignore_patterns(
    "__pycache__", "*.pyc", "*.egg-info", ".pytest_cache"
)


def _copy_minimal_project(dest: Path) -> None:
    """Kopiert den minimalen Projekt-Stand (pyproject/uv.lock/src/tests/fixtures),
    der noetig ist damit `uv run pytest tests/golden/email/` im Temp-Repo
    tatsaechlich laeuft (keine Mocks — echter Renderer-Code + echte Goldens).
    """
    for name in ("pyproject.toml", "uv.lock"):
        shutil.copy2(REPO_ROOT / name, dest / name)
    for dirname in ("src", "tests", "fixtures"):
        shutil.copytree(REPO_ROOT / dirname, dest / dirname, ignore=_IGNORE)


def _make_temp_golden_gate_repo(workflow_name: str) -> Path:
    """Erstellt ein eigenstaendiges Git-Repo mit echtem Projekt-Stand +
    Workflow-State-Stub, damit renderer_mail_gate.py darin als Subprozess
    laufen kann (analog _make_temp_git_repo_with_workflow aus Issue #830,
    aber mit echtem src/tests-Inhalt statt nur README, weil das Gate hier
    intern `uv run pytest tests/golden/email/` ausfuehrt).
    """
    tmpdir = Path(tempfile.mkdtemp(prefix="gz_golden_gate_"))
    _copy_minimal_project(tmpdir)
    subprocess.run(["git", "init"], cwd=str(tmpdir), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(tmpdir), check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(tmpdir), check=True, capture_output=True,
    )
    subprocess.run(["git", "add", "-A"], cwd=str(tmpdir), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(tmpdir), check=True, capture_output=True,
    )
    wf_dir = tmpdir / ".claude" / "workflows"
    wf_dir.mkdir(parents=True)
    state = {"name": workflow_name, "phase": "phase6_implementation", "gates": {}}
    (wf_dir / f"{workflow_name}.json").write_text(json.dumps(state))
    return tmpdir


def _stage_mail_file_change(tmpdir: Path) -> bytes:
    """Haengt eine Kommentarzeile an eine echte Mail-Renderer-Datei an und
    staged sie — damit `_is_mail_file()` im Gate anschlaegt. Gibt den
    resultierenden Datei-Inhalt zurueck (fuer die Hash-Berechnung).
    """
    mail_path = tmpdir / _MAIL_FILE_REL
    mail_path.write_text(mail_path.read_text() + "\n# golden-gate-test-touch (#939)\n")
    subprocess.run(
        ["git", "add", str(_MAIL_FILE_REL.as_posix())],
        cwd=str(tmpdir), check=True, capture_output=True,
    )
    return mail_path.read_bytes()


def _write_matrix_and_validator_nachweis(
    tmpdir: Path, workflow_name: str, mail_bytes: bytes
) -> None:
    """Erfuellt matrix_ok + validator_ok, damit im Test AUSSCHLIESSLICH der
    golden_ok-Check den Commit blockiert (isolierter Nachweis fuer AC-1,
    statt zufaellig ueber fehlende Matrix/Validator-Nachweise zu blockieren).
    """
    state_path = tmpdir / ".claude" / "workflows" / f"{workflow_name}.json"
    state = json.loads(state_path.read_text())
    mail_hash = hashlib.sha256(mail_bytes).hexdigest()
    state.setdefault("gates", {})["renderer_mail"] = {
        "matrix": {"passed": True, "mail_files_hash": mail_hash}
    }
    state_path.write_text(json.dumps(state))

    log_dir = tmpdir / ".claude" / "workflows" / "_log"
    log_dir.mkdir(parents=True, exist_ok=True)
    validated_at = datetime.now(timezone.utc).isoformat()
    log_text = (
        f"workflow_id: {workflow_name}\n"
        "passed: true\n"
        f"validated_at: '{validated_at}'\n"
    )
    (log_dir / f"{workflow_name}_briefing_validation.yaml").write_text(log_text)


def _corrupt_golden_snapshot(tmpdir: Path) -> None:
    """Ueberschreibt einen echten Golden-Snapshot mit falschem Inhalt, sodass
    der interne `uv run pytest tests/golden/email/`-Lauf im Gate fehlschlaegt.
    """
    golden_path = (
        tmpdir / "tests" / "golden" / "email" / "gr20-summer-evening-plain.txt"
    )
    golden_path.write_text("KORRUMPIERT-DURCH-TEST-ISSUE-939\n")


def _run_golden_gate(tmpdir: Path, workflow_name: str) -> subprocess.CompletedProcess:
    """Fuehrt renderer_mail_gate.py als echten Subprozess aus. Kein Mock.

    OPENSPEC_ACTIVE_WORKFLOW ist die aktuell gelesene Env-Variable
    (hook_utils.resolve_active_workflow() — GZ_ACTIVE_WORKFLOW ist veraltet,
    siehe .claude/hooks/hook_utils.py). Beide werden gesetzt, schadet nicht.
    """
    env = {
        **os.environ,
        "OPENSPEC_ACTIVE_WORKFLOW": workflow_name,
        "GZ_ACTIVE_WORKFLOW": workflow_name,
        "CLAUDE_TOOL_INPUT": json.dumps({"command": "git commit -m test"}),
    }
    return subprocess.run(
        [sys.executable, str(GATE_PATH)],
        cwd=str(tmpdir),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_renderer_mail_gate_has_golden_check():
    """AC-1: renderer_mail_gate._do_hook() muss einen golden_ok-Check haben.

    Echter Verhaltensnachweis (Issue #939 — ersetzt den frueheren
    Dateiinhalt-Check `"golden_ok" in source`): Ein Temp-Git-Repo mit echtem
    Projekt-Stand wird aufgebaut, ein Golden-Snapshot absichtlich korrumpiert,
    Matrix- und Validator-Nachweise werden erfuellt (damit ausschliesslich
    der Golden-Check faellt), und renderer_mail_gate.py wird als Subprozess
    ausgefuehrt. Erwartung: Exit-Code 2, Block-Message referenziert
    regenerate.py als Abhilfe.
    """
    workflow_name = "issue-939-golden-gate-test"
    tmpdir = _make_temp_golden_gate_repo(workflow_name)
    try:
        mail_bytes = _stage_mail_file_change(tmpdir)
        _write_matrix_and_validator_nachweis(tmpdir, workflow_name, mail_bytes)
        _corrupt_golden_snapshot(tmpdir)

        result = _run_golden_gate(tmpdir, workflow_name)

        assert result.returncode == 2, (
            "Gate soll bei korruptem Golden-Snapshot blockieren (Exit 2), "
            f"hat aber Exit {result.returncode} geliefert.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        combined_output = result.stdout + result.stderr
        assert "regenerate.py" in combined_output, (
            "Block-Message soll auf tests/golden/email/regenerate.py als "
            f"Abhilfe hinweisen. Output war:\n{combined_output}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_regenerate_script_exists():
    """AC-2: tests/golden/email/regenerate.py muss existieren.

    Das Skript wird im Block-Message des Gates als Abhilfe referenziert.
    Ohne das Skript waere die Fehlermeldung irreführend — Nutzer koennen
    nicht regenerieren was nicht existiert.
    """
    regen_path = REPO_ROOT / "tests" / "golden" / "email" / "regenerate.py"
    assert regen_path.exists(), (
        "tests/golden/email/regenerate.py fehlt. "
        "Wird vom renderer_mail_gate.py als Abhilfe im Block-Message referenziert. "
        "Muss Golden-Snapshots neu generieren koennen."
    )


# doc-compliance-test
def test_settings_json_has_preToolUse_renderer_gate():
    """AC-3: settings.json hat einen PreToolUse:Bash-Hook fuer renderer_mail_gate.py.

    Seit Commit ede10a2d ist das Gate aus settings.json entfernt worden und
    wird NIE aufgerufen. Jede Renderer-Aenderung kann ungesichert committed
    werden — das Gate existiert nur noch auf dem Papier.
    """
    settings_path = REPO_ROOT / ".claude" / "settings.json"
    settings = json.loads(settings_path.read_text())
    pretooluse_blocks = settings.get("hooks", {}).get("PreToolUse", [])
    has_renderer_gate = any(
        "renderer_mail_gate" in json.dumps(block)
        for block in pretooluse_blocks
    )
    assert has_renderer_gate, (
        "settings.json hat keinen PreToolUse:Bash-Hook fuer renderer_mail_gate.py. "
        "Das Gate wird nie aufgerufen! "
        "Ein PreToolUse-Block mit matcher='Bash' und command='...renderer_mail_gate.py' "
        "muss in .claude/settings.json eingetragen sein."
    )
