"""TDD RED: Renderer-Mail-Gate blockiert Compare-Mail-Aenderungen ohne
frischen Compare-Nachweis (Issues #1282/#1283, Fix-Workflow
fix-1282-1283-gate-honesty).

Mocks sind in diesem Projekt VERBOTEN. Alle Tests laufen gegen eine echte
Temp-Git-Fixture + einen echten Direktimport der Hook-Kopie (Vorbild:
tests/tdd/test_issue_1084_gate_scope_cache.py::_load_prod_selftest). Die
gestagten Datei-Inhalte und Validator-YAMLs sind echte Dateien im Temp-Repo,
kein IMAP/keine echte Mail-Zustellung noetig -- die Klassifikations-Logik in
``_do_hook`` ist rein Datei-/State-basiert.

Getestete ACs (docs/specs/modules/gate_honesty_mail_selftest.md):
  AC-1: compare_html.py gestaged -> Gate verlangt einen frischen
        *_email_validation.yaml-Nachweis, NICHT (nur) briefing_validation.yaml;
        compare_html.py ist aus briefing_staged ausgeschlossen.
  AC-3: ein geteilter Renderer-Helfer (hier: helpers.py) gestaged -> Gate
        verlangt BEIDE Nachweise (briefing UND compare).
  AC-5: der urspruengliche Fehlpfad (nur Briefing-No-Op-YAML vorhanden, kein
        Compare-YAML) darf NICHT durchgewunken werden.

Aktuell (rot): ``_do_hook`` klassifiziert jede
``src/output/renderers/email/*.py``-Datei, die weder Radar- noch
Official-Alert-Datei ist, als ``briefing_staged`` -- ein reiner
Briefing-Nachweis (``*_briefing_validation.yaml``) genuegt daher faelschlich
auch fuer Compare-Mail-Aenderungen (#1282).
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOKS_SRC = _REPO_ROOT / ".claude" / "hooks"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, check=True,
                           capture_output=True, text=True)


def _setup_repo(tmp_path: Path) -> Path:
    """Standalone Git-Repo mit Baseline-Commit (fuer echte `git diff --cached`)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.de")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("# baseline\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "baseline")
    return repo


def _load_gate_module(tmp_path: Path, module_name: str):
    """Laedt eine isolierte Kopie von renderer_mail_gate.py + hook_utils.py.

    Eigener Modulname pro Aufruf (sys.modules-Kollisionen vermeiden), eigene
    Kopie-Verzeichnis (fuer `sys.path.insert(0, str(Path(__file__).parent))`
    im Originalmodul, damit `import hook_utils` die mitkopierte Datei findet).
    """
    hooks_copy = tmp_path / f"hooks_{module_name}"
    hooks_copy.mkdir(parents=True, exist_ok=True)
    for fname in ("renderer_mail_gate.py", "hook_utils.py"):
        shutil.copy(_HOOKS_SRC / fname, hooks_copy / fname)
    path = hooks_copy / "renderer_mail_gate.py"
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _stage_file(repo: Path, relpath: str, content: str) -> None:
    p = repo / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    _git(repo, "add", relpath)


def _write_workflow_state(repo: Path, name: str, mail_files_hash: str) -> None:
    state_dir = repo / ".claude" / "workflows"
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "gates": {
            "renderer_mail": {
                "matrix": {
                    "passed": True,
                    "mail_files_hash": mail_files_hash,
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                }
            }
        }
    }
    (state_dir / f"{name}.json").write_text(__import__("json").dumps(state))


def _write_validation_yaml(repo: Path, name: str, kind: str, *,
                            passed: bool = True, suffix: str = "") -> Path:
    """kind: 'briefing_validation' oder 'email_validation' (Dateiname-Suffix)."""
    log_dir = repo / ".claude" / "workflows" / "_log"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + suffix
    path = log_dir / f"{ts}_{name}_{kind}.yaml"
    data = {
        "validator": kind,
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "workflow_id": name,
        "passed": passed,
        "error_count": 0,
        "errors": [],
    }
    path.write_text(yaml.safe_dump(data, allow_unicode=True))
    return path


# ---------------------------------------------------------------------------
# AC-1 + AC-5: compare_html.py mit NUR Briefing-Nachweis -> muss blockieren
# ---------------------------------------------------------------------------

def test_compare_html_with_only_briefing_nachweis_must_be_blocked(tmp_path):
    """AC-1/AC-5: staged=compare_html.py, nur briefing_validation.yaml vorhanden
    (KEIN *_email_validation.yaml) -> Gate muss blockieren (Exit 2), weil
    compare_html.py einen eigenen Compare-Nachweis braucht statt sich mit
    einem (wirkungslosen) Briefing-No-Op zufrieden zu geben."""
    repo = _setup_repo(tmp_path)
    name = "test-compare-dispatch-ac1"
    mod = _load_gate_module(tmp_path, "gate_ac1")

    rel = "src/output/renderers/email/compare_html.py"
    _stage_file(repo, rel, "<html>compare v1</html>\n")

    staged = mod._staged_files(repo)
    assert staged == [rel], f"Testvoraussetzung: nur {rel} gestaged, war {staged!r}"
    mail_hash = mod._staged_mail_hash(repo, staged)
    _write_workflow_state(repo, name, mail_hash)
    _write_validation_yaml(repo, name, "briefing_validation", passed=True)
    # bewusst KEIN *_email_validation.yaml geschrieben.

    with pytest.raises(SystemExit) as exc_info:
        mod._do_hook(repo, repo, name)

    assert exc_info.value.code == 2, (
        "AC-1/AC-5: renderer_mail_gate.py:_do_hook muss compare_html.py-"
        "Aenderungen mit nur einem Briefing-Nachweis blockieren (Exit 2), "
        "nicht durchwinken (Exit 0). Aktuell (rot) faellt compare_html.py in "
        "briefing_staged (Zeile ~351) statt einen eigenen "
        "*_email_validation.yaml-Nachweis zu verlangen. "
        f"tatsaechlicher Exit-Code={exc_info.value.code!r}"
    )


# ---------------------------------------------------------------------------
# AC-3: geteilter Renderer-Helfer -> BEIDE Nachweise noetig
# ---------------------------------------------------------------------------

def test_shared_renderer_helper_requires_both_nachweise(tmp_path):
    """AC-3: staged=helpers.py (geteilter Renderer-Helfer fuer Briefing UND
    Compare), nur briefing_validation.yaml vorhanden -> Gate muss blockieren,
    weil ein compare-spezifischer Bruch in helpers.py sonst durch einen
    reinen Briefing-Nachweis schluepfen koennte."""
    repo = _setup_repo(tmp_path)
    name = "test-compare-dispatch-ac3"
    mod = _load_gate_module(tmp_path, "gate_ac3")

    rel = "src/output/renderers/email/helpers.py"
    _stage_file(repo, rel, "def render_shared():\n    return '<x/>'\n")

    staged = mod._staged_files(repo)
    assert staged == [rel], f"Testvoraussetzung: nur {rel} gestaged, war {staged!r}"
    mail_hash = mod._staged_mail_hash(repo, staged)
    _write_workflow_state(repo, name, mail_hash)
    _write_validation_yaml(repo, name, "briefing_validation", passed=True)
    # bewusst KEIN *_email_validation.yaml geschrieben.

    with pytest.raises(SystemExit) as exc_info:
        mod._do_hook(repo, repo, name)

    assert exc_info.value.code == 2, (
        "AC-3: ein Commit, der einen geteilten Renderer-Helfer (helpers.py) "
        "staged, muss BEIDE Nachweise (briefing UND compare) verlangen. "
        "Aktuell (rot) verlangt das Gate fuer helpers.py nur den Briefing-"
        "Nachweis (identisch zu jeder anderen email/*.py-Datei) und laesst "
        "den Commit mit nur briefing_validation.yaml durch. "
        f"tatsaechlicher Exit-Code={exc_info.value.code!r}"
    )


# ---------------------------------------------------------------------------
# Gegenprobe: BEIDE frischen Nachweise vorhanden -> Gate laesst durch
# ---------------------------------------------------------------------------

def test_compare_html_with_both_nachweise_passes(tmp_path):
    """Gegenprobe (soll auch nach dem Fix gruen bleiben): liegen sowohl ein
    frisches *_email_validation.yaml als auch das Briefing-YAML vor, laesst
    das Gate compare_html.py-Aenderungen durch (Exit 0)."""
    repo = _setup_repo(tmp_path)
    name = "test-compare-dispatch-control"
    mod = _load_gate_module(tmp_path, "gate_control")

    rel = "src/output/renderers/email/compare_html.py"
    _stage_file(repo, rel, "<html>compare v2</html>\n")

    staged = mod._staged_files(repo)
    mail_hash = mod._staged_mail_hash(repo, staged)
    _write_workflow_state(repo, name, mail_hash)
    _write_validation_yaml(repo, name, "briefing_validation", passed=True)
    _write_validation_yaml(repo, name, "email_validation", passed=True)

    with pytest.raises(SystemExit) as exc_info:
        mod._do_hook(repo, repo, name)

    assert exc_info.value.code == 0, (
        "Gegenprobe: mit BEIDEN frischen Nachweisen (briefing + email) muss "
        f"das Gate durchlassen (Exit 0). tatsaechlicher Code="
        f"{exc_info.value.code!r}"
    )
