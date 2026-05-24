"""TDD-RED: Acceptance-Criteria-Format Pflicht.

Spec: docs/specs/modules/epic_191_ac_format_pflicht.md
Issue: #194 (Workflow C von Epic #191)

11 Tests in 4 Klassen gegen 9 Acceptance Criteria:
- T1: _spec_has_valid_ac_format Helper (AC-1, AC-2, AC-3, AC-4, AC-7) - 5 Tests
- T2: get_ac_format_required_since (AC-5, AC-6) - 2 Tests
- T3: workflow_gate phase6-Block live (AC-1 Edge) - 2 Tests
- T4: Template + spec-validator Doku (AC-8, AC-9) - 2 Tests

Erwartet RED: alle 11, da neue Funktionalität.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"

# Session-Env-Vars, die aus einer laufenden Workflow-Shell lecken und seit
# Commit 59bd925 (#333) ein FATAL exit 1 auslösen, wenn sie auf einen im
# Test-Repo nicht existenten Workflow zeigen (Symlink-Fallback aus). (#355)
_SESSION_ENV_VARS = (
    "GZ_ACTIVE_WORKFLOW",
    "CLAUDE_CODE_SESSION_ID",
    "GZ_HOOK_SESSION_ID",
)


def _subprocess_env(active: str | None = "demo") -> dict:
    """env-dict für subprocess-Aufrufe ohne Session-Leaks; setzt aktiven Workflow.

    Default 'demo' ist der im jeweiligen Test angelegte Workflow.
    """
    env = {k: v for k, v in os.environ.items() if k not in _SESSION_ENV_VARS}
    if active is not None:
        env["GZ_ACTIVE_WORKFLOW"] = active
    return env


@pytest.fixture
def hooks_on_path():
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    yield
    for mod_name in ("config_loader", "workflow_gate"):
        if mod_name in sys.modules:
            del sys.modules[mod_name]


@pytest.fixture
def tmp_spec(tmp_path):
    """Erzeugt eine Spec-Datei mit konfigurierbarem Frontmatter + Body."""
    def _make(created: str | None = None, has_section: bool = True,
              ac_entries: int = 2, ac_min_chars: int = 80,
              no_frontmatter: bool = False) -> Path:
        lines = []
        if not no_frontmatter:
            lines.append("---")
            lines.append("entity_id: demo_spec")
            lines.append("type: module")
            if created is not None:
                lines.append(f"created: {created}")
            lines.append("status: draft")
            lines.append('version: "1.0"')
            lines.append("---")
            lines.append("")
        lines.append("# Demo Spec")
        lines.append("")
        if has_section:
            lines.append("## Acceptance Criteria")
            lines.append("")
            for i in range(1, ac_entries + 1):
                filler = "x" * ac_min_chars
                lines.append(f"- **AC-{i}:** Given precondition / When action / Then outcome {filler}")
            lines.append("")
        path = tmp_path / "demo_spec.md"
        path.write_text("\n".join(lines))
        return path
    return _make


# ---------- T1: _spec_has_valid_ac_format Helper ----------------------


class TestT1SpecHasValidAcFormat:
    """AC-1 bis AC-4 + AC-7: Helper-Logik."""

    def test_new_spec_with_valid_ac_passes(self, tmp_spec, hooks_on_path):
        """AC-7: Neue Spec mit >=1 AC-N (>=30 chars) → (True, ...)."""
        from workflow_gate import _spec_has_valid_ac_format

        spec = tmp_spec(created="2026-05-15", has_section=True, ac_entries=2)
        ok, reason = _spec_has_valid_ac_format(spec, stichtag="2026-05-11")
        assert ok is True, f"Sollte gültig sein, war: {reason}"

    def test_new_spec_missing_section_blocks(self, tmp_spec, hooks_on_path):
        """AC-1: Neue Spec ohne ## Acceptance Criteria → (False, ...)."""
        from workflow_gate import _spec_has_valid_ac_format

        spec = tmp_spec(created="2026-05-15", has_section=False)
        ok, reason = _spec_has_valid_ac_format(spec, stichtag="2026-05-11")
        assert ok is False
        assert "Acceptance Criteria" in reason

    def test_new_spec_section_without_ac_entries_blocks(self, tmp_spec, hooks_on_path):
        """AC-2: Section da, aber keine AC-N-Einträge → (False, ...)."""
        from workflow_gate import _spec_has_valid_ac_format

        spec = tmp_spec(created="2026-05-15", has_section=True, ac_entries=0)
        ok, reason = _spec_has_valid_ac_format(spec, stichtag="2026-05-11")
        assert ok is False
        assert "AC-" in reason

    def test_legacy_spec_passes_without_ac(self, tmp_spec, hooks_on_path):
        """AC-3: Spec mit created < Stichtag → (True, "legacy ...")."""
        from workflow_gate import _spec_has_valid_ac_format

        spec = tmp_spec(created="2026-04-01", has_section=False)
        ok, reason = _spec_has_valid_ac_format(spec, stichtag="2026-05-11")
        assert ok is True
        assert "legacy" in reason.lower()

    def test_spec_without_created_field_passes(self, tmp_spec, hooks_on_path):
        """AC-4: Spec ohne created-Feld → defensives Default (True)."""
        from workflow_gate import _spec_has_valid_ac_format

        spec = tmp_spec(created=None, has_section=False)
        ok, reason = _spec_has_valid_ac_format(spec, stichtag="2026-05-11")
        assert ok is True, f"Defensives Default sollte erlauben: {reason}"

    def test_spec_without_frontmatter_passes(self, tmp_spec, hooks_on_path):
        """AC-4 (Edge): Spec ganz ohne Frontmatter → (True, ...)."""
        from workflow_gate import _spec_has_valid_ac_format

        spec = tmp_spec(no_frontmatter=True, has_section=False)
        ok, reason = _spec_has_valid_ac_format(spec, stichtag="2026-05-11")
        assert ok is True

    def test_no_stichtag_passes_everything(self, tmp_spec, hooks_on_path):
        """AC-6: stichtag=None → immer (True, ...)."""
        from workflow_gate import _spec_has_valid_ac_format

        spec = tmp_spec(created="2026-12-31", has_section=False)
        ok, reason = _spec_has_valid_ac_format(spec, stichtag=None)
        assert ok is True


# ---------- T2: Konfiguration ----------------------------------------


class TestT2Config:
    """AC-5: Config-Loader liest ac_format_required_since."""

    def test_get_ac_format_required_since_reads_config(self, tmp_path, monkeypatch, hooks_on_path):
        """AC-5: openspec.yaml mit Konfig → richtiger String zurück."""
        import yaml

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "openspec.yaml").write_text(yaml.safe_dump({
            "spec_validation": {"ac_format_required_since": "2026-05-11"}
        }))
        monkeypatch.chdir(repo)

        import config_loader
        config_loader.load_config.cache_clear()
        try:
            config_loader.find_project_root.cache_clear()
        except AttributeError:
            pass

        result = config_loader.get_ac_format_required_since()
        assert result == "2026-05-11"

    def test_get_ac_format_required_since_none_when_absent(self, tmp_path, monkeypatch, hooks_on_path):
        """AC-6: Ohne Konfig-Key → None."""
        import yaml

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "openspec.yaml").write_text(yaml.safe_dump({"other": "value"}))
        monkeypatch.chdir(repo)

        import config_loader
        config_loader.load_config.cache_clear()
        try:
            config_loader.find_project_root.cache_clear()
        except AttributeError:
            pass

        result = config_loader.get_ac_format_required_since()
        assert result is None


# ---------- T3: workflow_gate Hard-Block live -------------------------


class TestT3WorkflowGateLive:
    """AC-1 als Integrationstest: workflow_gate blockt Edit in phase6."""

    def test_workflow_gate_blocks_phase6_edit_for_invalid_spec(self, tmp_path, monkeypatch, hooks_on_path):
        """Phase 6 + neue Spec ohne AC → Exit 2."""
        import yaml

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        (repo / ".claude").mkdir()
        (repo / "openspec.yaml").write_text(yaml.safe_dump({
            "spec_validation": {"ac_format_required_since": "2026-05-11"}
        }))

        # Spec ohne AC, mit created >= Stichtag
        spec_dir = repo / "docs" / "specs" / "modules"
        spec_dir.mkdir(parents=True)
        spec = spec_dir / "demo.md"
        spec.write_text("---\nentity_id: demo\ncreated: 2026-05-15\n---\n# Demo\n")

        # Workflow-State in phase6 mit spec_file
        wf_dir = repo / ".claude" / "workflows"
        wf_dir.mkdir()
        (wf_dir / "demo.json").write_text(json.dumps({
            "name": "demo",
            "current_phase": "phase6_implement",
            "spec_file": "docs/specs/modules/demo.md",
            "spec_approved": True,
            "red_test_done": True,
        }))
        (wf_dir / ".active").symlink_to("demo.json")

        # Code-Edit simulieren
        target = repo / "src" / "app" / "demo.py"
        target.parent.mkdir(parents=True)
        target.write_text("# placeholder\n")

        monkeypatch.chdir(repo)
        payload = json.dumps({
            "tool_name": "Edit",
            "tool_input": {"file_path": str(target)},
        })
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow_gate.py")],
            input=payload, text=True, capture_output=True,
            env=_subprocess_env(),
        )
        assert result.returncode == 2, \
            f"Erwartet Block (Exit 2), bekam {result.returncode}. Stderr: {result.stderr}"
        assert "Acceptance Criteria" in (result.stderr + result.stdout), \
            f"Fehlermeldung muss AC nennen: {result.stderr}"

    def test_workflow_gate_allows_phase6_edit_for_legacy_spec(self, tmp_path, monkeypatch, hooks_on_path):
        """Phase 6 + Legacy-Spec (created < Stichtag) → erlaubt."""
        import yaml

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        (repo / ".claude").mkdir()
        (repo / "openspec.yaml").write_text(yaml.safe_dump({
            "spec_validation": {"ac_format_required_since": "2026-05-11"}
        }))

        spec_dir = repo / "docs" / "specs" / "modules"
        spec_dir.mkdir(parents=True)
        spec = spec_dir / "demo.md"
        spec.write_text("---\nentity_id: demo\ncreated: 2026-04-01\n---\n# Demo\n")

        wf_dir = repo / ".claude" / "workflows"
        wf_dir.mkdir()
        (wf_dir / "demo.json").write_text(json.dumps({
            "name": "demo",
            "current_phase": "phase6_implement",
            "spec_file": "docs/specs/modules/demo.md",
            "spec_approved": True,
            "red_test_done": True,
        }))
        (wf_dir / ".active").symlink_to("demo.json")

        target = repo / "src" / "app" / "demo.py"
        target.parent.mkdir(parents=True)
        target.write_text("# placeholder\n")

        monkeypatch.chdir(repo)
        payload = json.dumps({
            "tool_name": "Edit",
            "tool_input": {"file_path": str(target)},
        })
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow_gate.py")],
            input=payload, text=True, capture_output=True,
            env=_subprocess_env(),
        )
        # AC-3-Schutz: Legacy darf nicht blockiert werden — Exit 0 erwartet.
        # (Andere Gates wie tdd_enforcement laufen separat — der workflow_gate selbst muss OK sagen)
        assert result.returncode == 0, \
            f"Legacy-Spec sollte erlaubt sein, war Exit {result.returncode}: {result.stderr}"


# ---------- T4: Template + spec-validator Doku ------------------------


class TestT4TemplateAndValidatorDocs:
    """AC-8, AC-9: Template und spec-validator-Agent-Doku."""

    def test_template_contains_ac_section(self):
        """AC-8: docs/specs/_template.md enthält ## Acceptance Criteria + AC-1/AC-2."""
        template = REPO_ROOT / "docs" / "specs" / "_template.md"
        content = template.read_text()
        assert "## Acceptance Criteria" in content
        assert "**AC-1:**" in content
        assert "**AC-2:**" in content
        assert "Given" in content
        assert "When" in content
        assert "Then" in content

    def test_spec_validator_agent_documents_ac_check(self):
        """AC-9: .claude/agents/spec-validator.md dokumentiert AC-Format-Check."""
        agent_doc = REPO_ROOT / ".claude" / "agents" / "spec-validator.md"
        content = agent_doc.read_text()
        # Sektion über Acceptance-Criteria-Format
        assert "Acceptance-Criteria-Format" in content or "Acceptance Criteria Format" in content
        # Stichtagslogik dokumentiert
        assert "ac_format_required_since" in content or "Stichtag" in content
