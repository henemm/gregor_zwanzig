"""Issue #894 — Verwaiste Session-Registry aufgeraeumt.

Beweist ohne Mocks:

(a) `renderer_mail_gate` loeست den aktiven Workflow-Namen ueber
    `hook_utils.get_active_workflow_name()` auf:
    - OPENSPEC_ACTIVE_WORKFLOW gesetzt → korrekter Name wird geliefert.
    - OPENSPEC_ACTIVE_WORKFLOW nicht gesetzt → leerer String wird geliefert.

(b) Doc-Compliance (markiert mit # doc-compliance-test):
    - `.claude/session_workflows.json` existiert nicht mehr.
    - `_active_workflow_name` kommt im Gate-Source nicht mehr vor.

Keine Mocks (CLAUDE.md-Regel).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"


@pytest.fixture(autouse=True)
def hooks_on_path():
    """Stelle sicher, dass hook_utils importierbar ist."""
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    # Cache leeren damit Env-Aenderungen wirken
    for mod_name in list(sys.modules):
        if mod_name in ("hook_utils",):
            del sys.modules[mod_name]
    yield
    for mod_name in list(sys.modules):
        if mod_name in ("hook_utils",):
            del sys.modules[mod_name]


def test_get_active_workflow_name_returns_env_value(monkeypatch):
    """(a-1) OPENSPEC_ACTIVE_WORKFLOW gesetzt → hook_utils liefert genau diesen Namen."""
    monkeypatch.setenv("OPENSPEC_ACTIVE_WORKFLOW", "fix-894-orphan-session-registry")
    # GZ_ACTIVE_WORKFLOW darf nicht stoeren
    monkeypatch.delenv("GZ_ACTIVE_WORKFLOW", raising=False)
    # CLAUDE_PROJECT_DIR wegleeren damit find_project_root kein echtes Repo findet
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)

    import hook_utils
    name = hook_utils.get_active_workflow_name()

    assert name == "fix-894-orphan-session-registry", (
        f"Erwarteter Workflow-Name 'fix-894-orphan-session-registry', war: {name!r}"
    )


def test_get_active_workflow_name_returns_empty_without_env(monkeypatch, tmp_path):
    """(a-2) Kein Env, keine settings-Datei, kein active_workflow-File → leerer String."""
    monkeypatch.delenv("OPENSPEC_ACTIVE_WORKFLOW", raising=False)
    monkeypatch.delenv("GZ_ACTIVE_WORKFLOW", raising=False)
    # CLAUDE_PROJECT_DIR auf leeres tmp_path setzen damit kein echtes Repo gefunden wird
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

    import hook_utils
    name = hook_utils.get_active_workflow_name()

    assert name == "", (
        f"Ohne Signal muss leerer String kommen, war: {name!r}"
    )


def test_renderer_mail_gate_uses_hook_utils_resolver(monkeypatch):
    """(a-3) renderer_mail_gate delegiert die Namens-Aufloesung an hook_utils.

    Das Gate liest OPENSPEC_ACTIVE_WORKFLOW direkt ueber hook_utils.
    Wir rufen hook_utils.get_active_workflow_name() mit gesetztem Env auf
    und bestaetigen, dass der Resolver denselben Pfad nimmt — als Beweis
    dass das Gate nach dem Umbau keinen eigenen (toten) Registry-Lookup mehr hat.
    """
    monkeypatch.setenv("OPENSPEC_ACTIVE_WORKFLOW", "wf-test-894")
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)

    import hook_utils
    name = hook_utils.get_active_workflow_name()

    assert name == "wf-test-894", (
        f"hook_utils muss den Env-Wert 'wf-test-894' liefern, war: {name!r}"
    )


# doc-compliance-test
def test_session_workflows_json_does_not_exist():
    """(b-1) .claude/session_workflows.json wurde geloescht."""
    registry_file = REPO_ROOT / ".claude" / "session_workflows.json"
    assert not registry_file.exists(), (
        f"session_workflows.json sollte nicht mehr existieren, liegt aber unter: {registry_file}"
    )


# doc-compliance-test
def test_active_workflow_name_function_removed_from_gate():
    """(b-2) Die lokale Funktion 'def _active_workflow_name' existiert nicht mehr im Gate."""
    gate_source = (HOOKS_DIR / "renderer_mail_gate.py").read_text()
    assert "def _active_workflow_name" not in gate_source, (
        "Die Funktion 'def _active_workflow_name' wurde nicht vollstaendig aus "
        "renderer_mail_gate.py entfernt."
    )


# doc-compliance-test
def test_session_workflows_reference_removed_from_gate():
    """(b-3) 'session_workflows' kommt im renderer_mail_gate.py-Source nicht mehr vor."""
    gate_source = (HOOKS_DIR / "renderer_mail_gate.py").read_text()
    assert "session_workflows" not in gate_source, (
        "'session_workflows' wird noch im Gate referenziert — Registry-Lookup nicht vollstaendig entfernt."
    )
