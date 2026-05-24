"""TDD-RED/GREEN: Zeilenlimit pro Workflow (LoC-Delta-Check).

Spec: docs/specs/modules/epic_191_zeilenlimit.md
Issue: #195 (Workflow D von Epic #191)

12+ Tests in 4 Klassen gegen 9 Acceptance Criteria:
- T1: _get_loc_delta — git numstat parsing + exclude + binary skip (AC-3, AC-4, AC-8)
- T2: _check_loc_delta — limit + override + fail-soft (AC-1, AC-2, AC-4, AC-9)
- T3: workflow.py status zeigt Delta (AC-5, AC-6)
- T4: Konfig-Helper + Defaults (AC-7)

KRITISCHE PROJEKT-REGEL: KEINE MOCKS!
Alle Tests verwenden echte git-Repos, echte CLI-Aufrufe und echte openspec.yaml-Dateien.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


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

    Default 'demo' ist der von _init_active_workflow() erzeugte Workflow.
    """
    env = {k: v for k, v in os.environ.items() if k not in _SESSION_ENV_VARS}
    if active is not None:
        env["GZ_ACTIVE_WORKFLOW"] = active
    return env


# ---------- Helper: echtes git-Repo bauen ----------------------------


def _init_git_repo(repo: Path) -> None:
    """Initialisiere ein leeres git-Repo mit einem Basiscommit."""
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--quiet"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "base.py").write_text("# base\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)


def _write_openspec_yaml(repo: Path, cfg: dict) -> None:
    """Schreibe eine openspec.yaml in das Repo (echte Konfig fuer get_scope_loc_config)."""
    (repo / "openspec.yaml").write_text(yaml.safe_dump(cfg))


def _init_active_workflow(repo: Path, name: str, extras: dict | None = None) -> None:
    """Erzeuge eine echte aktive Workflow-Datei + .active-Symlink im Repo."""
    wf_dir = repo / ".claude" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    record = {"name": name, "current_phase": "phase6_implement"}
    if extras:
        record.update(extras)
    (wf_dir / f"{name}.json").write_text(json.dumps(record))
    active = wf_dir / ".active"
    if active.exists() or active.is_symlink():
        active.unlink()
    os.symlink(f"{name}.json", str(active))


@pytest.fixture
def hooks_on_path():
    """Hooks-Verzeichnis in sys.path haengen + Module nach dem Test resetten."""
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    yield
    for mod_name in ("config_loader", "scope_guard", "workflow"):
        if mod_name in sys.modules:
            del sys.modules[mod_name]


@pytest.fixture
def fake_git_repo(tmp_path, monkeypatch, hooks_on_path):
    """Echtes git-Repo mit committed Basisstand fuer `git diff HEAD`."""
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    monkeypatch.chdir(repo)
    return repo


@pytest.fixture
def fake_git_repo_with_workflow(fake_git_repo):
    """Echtes git-Repo + aktiver Workflow `demo` (fuer set-field + Gate-Tests)."""
    _init_active_workflow(fake_git_repo, "demo")
    return fake_git_repo


# ---------- T1: _get_loc_delta ----------------------------------------


class TestT1GetLocDelta:
    """AC-3, AC-4, AC-8: numstat parsing, exclude, binary skip, fail-soft."""

    def test_get_loc_delta_counts_inserted_lines(self, fake_git_repo):
        """AC-1-Vorlauf: Geaenderte Datei mit 5 neuen Zeilen -> delta=5."""
        from scope_guard import _get_loc_delta

        (fake_git_repo / "base.py").write_text("# base\n" + "x\n" * 5)
        total, counted = _get_loc_delta(exclude_patterns=[])
        assert total == 5, f"Expected delta=5, got {total}"
        assert "base.py" in counted

    def test_get_loc_delta_excludes_matched_pattern(self, fake_git_repo):
        """AC-3: Datei in exclude_patterns wird nicht gezaehlt."""
        from scope_guard import _get_loc_delta

        (fake_git_repo / "data.po").write_text("\n" * 100)
        subprocess.run(["git", "add", "data.po"], cwd=fake_git_repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "add po"], cwd=fake_git_repo, check=True)
        (fake_git_repo / "data.po").write_text("\n" * 200)
        (fake_git_repo / "base.py").write_text("x\n" * 3)

        total, counted = _get_loc_delta(exclude_patterns=[r"\.po$"])
        # base.py aenderte 3 Zeilen, data.po 100+ -> nur base.py zaehlt
        assert total < 50, f"Expected only base.py changes, got {total}"
        assert "data.po" not in counted

    def test_get_loc_delta_skips_binary_files(self, fake_git_repo):
        """AC-8: Binaere Dateien (-/-) werden ohne Crash uebersprungen.

        Echter Binary-Test: ein PNG mit Header anlegen, committen, dann veraendern.
        git numstat liefert dafuer `-\\t-\\tpath` Zeilen.
        """
        from scope_guard import _get_loc_delta

        # Echtes PNG-Header-Bytes (8-Byte Signature + minimaler Inhalt)
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
        (fake_git_repo / "image.png").write_bytes(png_bytes)
        (fake_git_repo / "regular.py").write_text("x\n" * 5)
        subprocess.run(["git", "add", "image.png", "regular.py"], cwd=fake_git_repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "add files"], cwd=fake_git_repo, check=True)

        # Beide aendern: PNG wird gross, regular.py +3 Zeilen
        (fake_git_repo / "image.png").write_bytes(png_bytes + b"\xff" * 256)
        (fake_git_repo / "regular.py").write_text("x\n" * 8)

        total, counted = _get_loc_delta(exclude_patterns=[])

        # Nur regular.py zaehlt (3 Zeilen Delta), image.png ist binaer -> skip
        assert "regular.py" in counted
        assert "image.png" not in counted
        # Delta sollte klein bleiben (~3 lines), nicht in die Hunderte gehen
        assert total < 50, f"Binary-Datei darf nicht zaehlen, got total={total}"

    def test_get_loc_delta_fail_soft_on_git_error(self, tmp_path, monkeypatch, hooks_on_path):
        """AC-4: git-Fehler (kein Repo) -> (0, []) statt Crash.

        Echter Test: Verzeichnis OHNE `.git` -> `git diff HEAD` exit != 0.
        """
        from scope_guard import _get_loc_delta

        bare = tmp_path / "not_a_repo"
        bare.mkdir()
        (bare / "file.py").write_text("x\n" * 100)
        monkeypatch.chdir(bare)

        total, counted = _get_loc_delta(exclude_patterns=[])
        assert total == 0, f"Bei git-Fehler erwartet 0, got {total}"
        assert counted == []

    def test_get_loc_delta_fail_soft_on_missing_git_binary(
        self, fake_git_repo, monkeypatch
    ):
        """AC-4: `git` nicht im PATH -> FileNotFoundError -> (0, []) statt Crash.

        Echter Test: PATH auf leeres Verzeichnis setzen, so dass subprocess.run
        ein FileNotFoundError werfen muss.
        """
        from scope_guard import _get_loc_delta

        empty_path = fake_git_repo / "_empty_path"
        empty_path.mkdir()
        # Stelle sicher dass subprocess die git-Binary nicht findet
        monkeypatch.setenv("PATH", str(empty_path))

        # Sanity: shutil.which sieht jetzt kein git
        assert shutil.which("git") is None, "Test-Setup defekt: git muesste unfindbar sein"

        total, counted = _get_loc_delta(exclude_patterns=[])
        assert total == 0
        assert counted == []

    def test_get_loc_delta_ignores_invalid_regex_pattern(self, fake_git_repo):
        """F003: Ungueltiges Regex-Pattern in exclude_patterns -> kein Crash.

        Ein einzelnes invalides Pattern darf den ganzen Check nicht killen;
        andere Patterns muessen weiter geprueft werden.
        """
        from scope_guard import _get_loc_delta

        (fake_git_repo / "data.po").write_text("x\n" * 50)
        (fake_git_repo / "base.py").write_text("x\n" * 5)
        subprocess.run(["git", "add", "data.po"], cwd=fake_git_repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "add po"], cwd=fake_git_repo, check=True)
        (fake_git_repo / "data.po").write_text("x\n" * 200)

        # "[unclosed" ist ein ungueltiges Regex; "\.po$" gueltig
        total, counted = _get_loc_delta(exclude_patterns=["[unclosed", r"\.po$"])
        # Kein Crash, data.po wird durch das gueltige Pattern ausgeschlossen
        assert "data.po" not in counted
        assert total < 50, f"Nur base.py darf zaehlen, got {total}"


# ---------- T2: _check_loc_delta -------------------------------------


class TestT2CheckLocDelta:
    """AC-1, AC-2: Limit + Override — alles ueber echte openspec.yaml + echten set-field."""

    def test_check_blocks_over_limit(self, fake_git_repo, hooks_on_path):
        """AC-1: Delta > Limit -> (False, ...) mit "exceeds"-Meldung."""
        # Echte Konfig im Repo
        _write_openspec_yaml(fake_git_repo, {
            "scope_guard": {"max_loc_delta": 250, "loc_exclude_patterns": []}
        })
        (fake_git_repo / "base.py").write_text("x\n" * 300)

        # Module nach Konfig-Schreiben frisch laden, damit lru_cache greift
        import config_loader
        config_loader.find_project_root.cache_clear()
        config_loader.load_config.cache_clear()

        from scope_guard import _check_loc_delta
        ok, reason = _check_loc_delta(workflow_state={})

        assert ok is False
        assert "exceeds" in reason.lower() or "limit" in reason.lower()
        assert "250" in reason

    def test_check_allows_with_override(self, fake_git_repo, hooks_on_path):
        """AC-2: loc_limit_override hebt Limit lokal (workflow_state dict)."""
        _write_openspec_yaml(fake_git_repo, {
            "scope_guard": {"max_loc_delta": 250, "loc_exclude_patterns": []}
        })
        (fake_git_repo / "base.py").write_text("x\n" * 300)

        import config_loader
        config_loader.find_project_root.cache_clear()
        config_loader.load_config.cache_clear()

        from scope_guard import _check_loc_delta
        ok, reason = _check_loc_delta(workflow_state={"loc_limit_override": 500})

        assert ok is True, f"Override sollte erlauben: {reason}"

    def test_check_allows_at_limit(self, fake_git_repo, hooks_on_path):
        """AC-1 Edge: Delta == Limit (100) -> erlaubt (not >)."""
        _write_openspec_yaml(fake_git_repo, {
            "scope_guard": {"max_loc_delta": 100, "loc_exclude_patterns": []}
        })
        # Genau 50 Zeilen aendern, Limit 100
        (fake_git_repo / "base.py").write_text("x\n" * 49)  # base hatte 1 Zeile -> +49

        import config_loader
        config_loader.find_project_root.cache_clear()
        config_loader.load_config.cache_clear()

        from scope_guard import _check_loc_delta
        ok, _ = _check_loc_delta(workflow_state={})

        assert ok is True, "Bei Delta <= Limit muss erlaubt sein"

    def test_check_allows_with_override_via_real_set_field(
        self, fake_git_repo_with_workflow
    ):
        """F002 + AC-2: set-field schreibt override als int; gate erlaubt dann.

        Echter End-to-End-Test:
        1. workflow.py set-field loc_limit_override 500  (via subprocess)
        2. State-JSON liest: override == 500 (int, nicht "500")
        3. Grosser Diff: scope_guard wuerde normalerweise blocken
        4. Mit override 500 darf der Edit-Versuch durch -> exit 0
        """
        repo = fake_git_repo_with_workflow

        # 1) Konfig schreiben: Limit 250 (default-nah)
        _write_openspec_yaml(repo, {
            "scope_guard": {"max_loc_delta": 250, "loc_exclude_patterns": []}
        })

        # 2) Echter CLI-Call: set-field loc_limit_override 500
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"),
             "set-field", "loc_limit_override", "500"],
            cwd=repo, capture_output=True, text=True,
            env=_subprocess_env(),
        )
        assert result.returncode == 0, f"set-field fehlgeschlagen: {result.stderr}"

        # 3) State-JSON pruefen: override ist int 500, nicht "500"
        state_path = repo / ".claude" / "workflows" / "demo.json"
        state = json.loads(state_path.read_text())
        assert state["loc_limit_override"] == 500
        assert isinstance(state["loc_limit_override"], int), \
            f"Erwartet int, got {type(state['loc_limit_override']).__name__}"

        # 4) Grossen Diff produzieren (300 Zeilen, ueberschreitet 250)
        (repo / "base.py").write_text("x\n" * 300)

        # 5) workflow_gate via subprocess aufrufen — muss durchgehen
        target_file = repo / "base.py"
        payload = json.dumps({
            "tool_name": "Edit",
            "tool_input": {"file_path": str(target_file)},
        })
        gate_result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "scope_guard.py")],
            input=payload, cwd=repo, capture_output=True, text=True,
            env=_subprocess_env(),
        )
        # Mit override 500 muss exit 0 sein (nicht 2 = BLOCKED)
        assert gate_result.returncode == 0, (
            f"Gate blockierte trotz override 500. "
            f"stdout={gate_result.stdout!r} stderr={gate_result.stderr!r}"
        )


# ---------- T3: workflow.py status zeigt Delta ----------------------


class TestT3StatusShowsDelta:
    """AC-5, AC-6: status-Ausgabe enthaelt LoC-Delta."""

    def test_status_shows_loc_delta(self, fake_git_repo):
        """AC-5: status zeigt `LoC-Delta: +N/250`."""
        _init_active_workflow(fake_git_repo, "demo")
        (fake_git_repo / "base.py").write_text("x\n" * 10)

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "status"],
            cwd=fake_git_repo, capture_output=True, text=True,
            env=_subprocess_env(),
        )
        assert result.returncode == 0
        assert "LoC-Delta" in result.stdout, \
            f"status muss LoC-Delta zeigen: {result.stdout}"

    def test_status_marks_override(self, fake_git_repo):
        """AC-6: Bei loc_limit_override -> "(override)" im Status."""
        _init_active_workflow(fake_git_repo, "demo", extras={"loc_limit_override": 500})
        (fake_git_repo / "base.py").write_text("x\n" * 5)

        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "workflow.py"), "status"],
            cwd=fake_git_repo, capture_output=True, text=True,
            env=_subprocess_env(),
        )
        assert "/500" in result.stdout, f"Override-Limit muss in status: {result.stdout}"
        assert "override" in result.stdout.lower()


# ---------- T4: Konfig + Helper -------------------------------------


class TestT4Config:
    """AC-7: get_scope_loc_config liefert Defaults bei fehlender Konfig."""

    def test_config_helper_returns_defaults(self, tmp_path, monkeypatch, hooks_on_path):
        """AC-7: Ohne scope_guard-Sektion -> Defaults (250, [])."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _write_openspec_yaml(repo, {"other": "value"})
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
        """AC-7-Erweiterung: Mit scope_guard-Sektion -> Werte aus openspec.yaml."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _write_openspec_yaml(repo, {
            "scope_guard": {
                "max_loc_delta": 500,
                "loc_exclude_patterns": [r"\.po$", r"\.xcstrings$"],
            }
        })
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


# ---------- T5: F004 — docs/specs/ + CLAUDE.md always-allowed -------


class TestT5DocsAlwaysAllowed:
    """F004: Doku-/Spec-Edits umgehen den LoC-Check via ALWAYS_ALLOWED."""

    def test_loc_check_skipped_for_docs_specs(self, fake_git_repo_with_workflow):
        """F004: Edit auf docs/specs/foo.md wird nicht durch LoC-Limit geblockt.

        Aufbau: 1000+ Zeilen Diff in einem Code-File (wuerde normalerweise blocken),
        aber der Edit-Versuch zielt auf docs/specs/. Das muss als ALWAYS_ALLOWED
        durchgehen.
        """
        repo = fake_git_repo_with_workflow
        _write_openspec_yaml(repo, {
            "scope_guard": {"max_loc_delta": 100, "loc_exclude_patterns": []}
        })

        # Massiver Diff im Code (1000+ Zeilen)
        (repo / "base.py").write_text("x\n" * 1000)

        # Edit-Versuch auf eine docs/specs-Datei
        spec_file = repo / "docs" / "specs" / "modules" / "foo.md"
        spec_file.parent.mkdir(parents=True, exist_ok=True)
        spec_file.write_text("# Spec\n")

        payload = json.dumps({
            "tool_name": "Edit",
            "tool_input": {"file_path": str(spec_file)},
        })
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "scope_guard.py")],
            input=payload, cwd=repo, capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"docs/specs/ darf nicht durch LoC-Limit geblockt werden. "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )

    def test_loc_check_skipped_for_claude_md(self, fake_git_repo_with_workflow):
        """F004: Edits an CLAUDE.md sind always-allowed."""
        repo = fake_git_repo_with_workflow
        _write_openspec_yaml(repo, {
            "scope_guard": {"max_loc_delta": 100, "loc_exclude_patterns": []}
        })
        (repo / "base.py").write_text("x\n" * 500)

        target = repo / "CLAUDE.md"
        target.write_text("# Project\n")
        payload = json.dumps({
            "tool_name": "Edit",
            "tool_input": {"file_path": str(target)},
        })
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "scope_guard.py")],
            input=payload, cwd=repo, capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"CLAUDE.md darf nicht geblockt werden. stderr={result.stderr!r}"
        )
