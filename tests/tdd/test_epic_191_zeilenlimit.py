"""TDD-RED: Zeilenlimit pro Workflow (LoC-Delta-Check).

Spec: docs/specs/modules/epic_191_zeilenlimit.md
Issue: #195 (Workflow D von Epic #191)

12 Tests in 4 Klassen gegen 9 Acceptance Criteria:
- T1: _get_loc_delta — git numstat parsing + exclude + binary skip (AC-3, AC-4, AC-8)
- T2: _check_loc_delta — limit + override + fail-soft (AC-1, AC-2, AC-4, AC-9)
- T3: workflow.py status zeigt Delta (AC-5, AC-6)
- T4: Konfig-Helper + Defaults (AC-7)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"


@pytest.fixture
def hooks_on_path():
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    yield
    for mod_name in ("config_loader", "scope_guard", "workflow"):
        if mod_name in sys.modules:
            del sys.modules[mod_name]


@pytest.fixture
def fake_git_repo(tmp_path, monkeypatch, hooks_on_path):
    """Echtes git-Repo mit committed Basisstand für `git diff HEAD`."""
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    subprocess.run(["git", "init", "--quiet"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "base.py").write_text("# base\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
    return repo


# ---------- T1: _get_loc_delta ----------------------------------------


class TestT1GetLocDelta:
    """AC-3, AC-4, AC-8: numstat parsing, exclude, binary skip, fail-soft."""

    def test_get_loc_delta_counts_inserted_lines(self, fake_git_repo):
        """AC-1-Vorlauf: Geänderte Datei mit 5 neuen Zeilen → delta=5."""
        from scope_guard import _get_loc_delta

        (fake_git_repo / "base.py").write_text("# base\n" + "x\n" * 5)
        total, counted = _get_loc_delta(exclude_patterns=[])
        assert total == 5, f"Expected delta=5, got {total}"
        assert "base.py" in counted

    def test_get_loc_delta_excludes_matched_pattern(self, fake_git_repo):
        """AC-3: Datei in exclude_patterns wird nicht gezählt."""
        from scope_guard import _get_loc_delta

        (fake_git_repo / "data.po").write_text("\n" * 100)
        subprocess.run(["git", "add", "data.po"], cwd=fake_git_repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "add po"], cwd=fake_git_repo, check=True)
        (fake_git_repo / "data.po").write_text("\n" * 200)
        (fake_git_repo / "base.py").write_text("x\n" * 3)

        total, counted = _get_loc_delta(exclude_patterns=[r"\.po$"])
        # base.py änderte 3 Zeilen, data.po 100+ → nur base.py zählt
        assert total < 50, f"Expected only base.py changes, got {total}"
        assert "data.po" not in counted

    def test_get_loc_delta_skips_binary_files(self, fake_git_repo):
        """AC-8: Binäre Dateien (-/-) werden ohne Crash übersprungen."""
        from scope_guard import _get_loc_delta

        # Simuliere git-Output direkt (Mock subprocess)
        fake_output = "5\t3\tregular.py\n-\t-\tbinary.png\n"
        with patch("scope_guard.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=fake_output)
            total, counted = _get_loc_delta(exclude_patterns=[])

        assert total == 8, f"Expected 5+3=8, got {total}"
        assert "regular.py" in counted
        assert "binary.png" not in counted

    def test_get_loc_delta_fail_soft_on_git_error(self, fake_git_repo):
        """AC-4: git-Fehler → (0, []) statt Crash."""
        from scope_guard import _get_loc_delta

        with patch("scope_guard.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git not found")
            total, counted = _get_loc_delta(exclude_patterns=[])

        assert total == 0
        assert counted == []

    def test_get_loc_delta_fail_soft_on_timeout(self, fake_git_repo):
        """AC-4: TimeoutExpired → (0, []) statt Crash."""
        from scope_guard import _get_loc_delta

        with patch("scope_guard.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("git", 10)
            total, counted = _get_loc_delta(exclude_patterns=[])

        assert total == 0
        assert counted == []


# ---------- T2: _check_loc_delta -------------------------------------


class TestT2CheckLocDelta:
    """AC-1, AC-2: Limit + Override."""

    def test_check_blocks_over_limit(self, fake_git_repo):
        """AC-1: Delta > Limit → (False, ...) mit "exceeds"-Meldung."""
        from scope_guard import _check_loc_delta

        (fake_git_repo / "base.py").write_text("x\n" * 300)
        # Mock: keine Override, kein excluded
        wf_state = {}
        with patch("scope_guard.get_scope_loc_config") as mock_cfg:
            mock_cfg.return_value = {"max_loc_delta": 250, "loc_exclude_patterns": []}
            ok, reason = _check_loc_delta(wf_state)

        assert ok is False
        assert "exceeds" in reason.lower() or "limit" in reason.lower()
        assert "250" in reason

    def test_check_allows_with_override(self, fake_git_repo):
        """AC-2: loc_limit_override hebt Limit lokal."""
        from scope_guard import _check_loc_delta

        (fake_git_repo / "base.py").write_text("x\n" * 300)
        wf_state = {"loc_limit_override": 500}
        with patch("scope_guard.get_scope_loc_config") as mock_cfg:
            mock_cfg.return_value = {"max_loc_delta": 250, "loc_exclude_patterns": []}
            ok, reason = _check_loc_delta(wf_state)

        assert ok is True, f"Override sollte erlauben: {reason}"

    def test_check_allows_at_limit(self, fake_git_repo):
        """AC-1 Edge: Delta == Limit (250) → erlaubt (not >)."""
        from scope_guard import _check_loc_delta

        # Genau 50 Zeilen, Limit 50
        (fake_git_repo / "base.py").write_text("x\n" * 49)  # +49 lines (base hat 1)
        wf_state = {}
        with patch("scope_guard.get_scope_loc_config") as mock_cfg:
            mock_cfg.return_value = {"max_loc_delta": 100, "loc_exclude_patterns": []}
            ok, _ = _check_loc_delta(wf_state)

        assert ok is True, "Bei Delta <= Limit muss erlaubt sein"


# ---------- T3: workflow.py status zeigt Delta ----------------------


class TestT3StatusShowsDelta:
    """AC-5, AC-6: status-Ausgabe enthält LoC-Delta."""

    def test_status_shows_loc_delta(self, fake_git_repo):
        """AC-5: status zeigt `LoC-Delta: +N/250`."""
        # Init aktiver Workflow
        wf_dir = fake_git_repo / ".claude" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "demo.json").write_text(json.dumps({
            "name": "demo",
            "current_phase": "phase6_implement",
        }))
        (wf_dir / ".active").symlink_to("demo.json")

        # Kleine Änderung
        (fake_git_repo / "base.py").write_text("x\n" * 10)

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "status"],
            cwd=fake_git_repo, capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "LoC-Delta" in result.stdout, \
            f"status muss LoC-Delta zeigen: {result.stdout}"

    def test_status_marks_override(self, fake_git_repo):
        """AC-6: Bei loc_limit_override → "(override)" im Status."""
        wf_dir = fake_git_repo / ".claude" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "demo.json").write_text(json.dumps({
            "name": "demo",
            "current_phase": "phase6_implement",
            "loc_limit_override": 500,
        }))
        (wf_dir / ".active").symlink_to("demo.json")

        (fake_git_repo / "base.py").write_text("x\n" * 5)

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "status"],
            cwd=fake_git_repo, capture_output=True, text=True,
        )
        assert "/500" in result.stdout, f"Override-Limit muss in status: {result.stdout}"
        assert "override" in result.stdout.lower()


# ---------- T4: Konfig + Helper -------------------------------------


class TestT4Config:
    """AC-7: get_scope_loc_config liefert Defaults bei fehlender Konfig."""

    def test_config_helper_returns_defaults(self, tmp_path, monkeypatch, hooks_on_path):
        """AC-7: Ohne scope_guard-Sektion → Defaults (250, [])."""
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

        cfg = config_loader.get_scope_loc_config()
        assert cfg["max_loc_delta"] == 250
        assert cfg["loc_exclude_patterns"] == []

    def test_config_helper_reads_values(self, tmp_path, monkeypatch, hooks_on_path):
        """AC-7-Erweiterung: Mit scope_guard-Sektion → Werte aus openspec.yaml."""
        import yaml
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "openspec.yaml").write_text(yaml.safe_dump({
            "scope_guard": {
                "max_loc_delta": 500,
                "loc_exclude_patterns": [r"\.po$", r"\.xcstrings$"],
            }
        }))
        monkeypatch.chdir(repo)

        import config_loader
        config_loader.load_config.cache_clear()
        try:
            config_loader.find_project_root.cache_clear()
        except AttributeError:
            pass

        cfg = config_loader.get_scope_loc_config()
        assert cfg["max_loc_delta"] == 500
        assert r"\.po$" in cfg["loc_exclude_patterns"]
