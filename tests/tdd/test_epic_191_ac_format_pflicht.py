"""TDD: Acceptance-Criteria-Format Pflicht — reparierte lokale Tests.

Spec: docs/specs/modules/epic_191_ac_format_pflicht.md
Issue: #194 (Workflow C von Epic #191)

Repair (#903 lokaler Teil 2):
- T1 (workflow_gate._spec_has_valid_ac_format) ENTFERNT → Plugin-Issue #14
- T3 (workflow_gate.py live) ENTFERNT → Plugin-Issue #14
- T4.test_spec_validator_agent_documents_ac_check ENTFERNT → Plugin-Issue #14
  (AC-Format-Enforcement liegt in workflow_gate, das ins Plugin wanderte)

Verbleibend (lokal testbar):
- T2: get_ac_format_required_since (AC-5, AC-6) — config_loader existiert lokal
- T4: test_template_contains_ac_section (AC-8) — Template-Datei existiert lokal
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"


@pytest.fixture
def hooks_on_path():
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    yield
    for mod_name in ("config_loader",):
        if mod_name in sys.modules:
            del sys.modules[mod_name]


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


# ---------- T4: Template Doku ----------------------------------------


class TestT4TemplateAndValidatorDocs:
    """AC-8: Template enthält AC-Format-Vorgaben."""

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
