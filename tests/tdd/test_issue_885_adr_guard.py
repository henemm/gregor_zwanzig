"""Issue #885 — ADR-Enforcement: Commit-Gate + Spec-Pflichtfeld (TDD RED).

Mock-frei: direkte Funktionsaufrufe + echte Temp-Git-Repos + Subprocess-Aufrufe.
`adr_guard.py` EXISTIERT in der RED-Phase NOCH NICHT → alle Tests schlagen rot fehl.
`_validate_transition` in workflow.py kennt den ADR-Check noch nicht → AC-5 schlägt rot.

ACs abgedeckt:
  AC-1: Entscheidungsfläche gestaged, kein ADR, kein [no-adr] → Gate blockiert (Exit 2)
  AC-2: Entscheidungsfläche + docs/adr/*.md mitgestaged → durchgelassen (Exit 0)
  AC-3: Entscheidungsfläche, kein ADR, aber [no-adr] in Message → durchgelassen (Exit 0)
  AC-4: Nur Nicht-Entscheidungs-Datei gestaged → No-Op (Exit 0)
  AC-5: _validate_transition blockt bei fehlendem ADR-Feld in Spec; erlaubt bei ADR-<n>/"keine"
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Repo-Pfade
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOKS_DIR = _REPO_ROOT / ".claude" / "hooks"

# Das neue Modul, das in RED-Phase noch nicht existiert.
_ADR_GUARD_SRC = _HOOKS_DIR / "adr_guard.py"

# bash_gate.py für Integrationstests (existiert bereits)
_BASH_GATE_SRC = _HOOKS_DIR / "bash_gate.py"

_WF_NAME = "issue-885-adr-enforcement"


# ---------------------------------------------------------------------------
# Hilfs-Import: adr_guard-Modul laden (schlägt RED rot da Datei fehlt)
# ---------------------------------------------------------------------------

def _load_adr_guard():
    """Importiert adr_guard als Modul. Schlägt mit FileNotFoundError/ImportError fehl
    wenn das Modul noch nicht existiert — das ist der erwartete RED-Zustand."""
    if not _ADR_GUARD_SRC.exists():
        raise ImportError(f"adr_guard.py nicht gefunden: {_ADR_GUARD_SRC}")
    spec = importlib.util.spec_from_file_location("adr_guard", _ADR_GUARD_SRC)
    mod = importlib.util.module_from_spec(spec)
    # Hooks-Dir muss im sys.path sein damit adr_guard hook_utils importieren kann
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Git-Repo-Fixtures
# ---------------------------------------------------------------------------

def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True,
                   capture_output=True, text=True)


def _setup_repo(tmp_path: Path) -> Path:
    """Standalone Git-Repo mit Kopien aller benötigten Hook-Dateien."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.de")
    _git(repo, "config", "user.name", "Test")

    # .claude/hooks anlegen + alle relevanten Hooks kopieren
    hooks = repo / ".claude" / "hooks"
    hooks.mkdir(parents=True)

    # bash_gate.py kopieren (Haupt-Gate)
    shutil.copy(_BASH_GATE_SRC, hooks / "bash_gate.py")

    # adr_guard.py kopieren (RED: fehlt → FileNotFoundError beim _setup_repo, OK für AC-1..4)
    if _ADR_GUARD_SRC.exists():
        shutil.copy(_ADR_GUARD_SRC, hooks / "adr_guard.py")

    # Alle Hilfs-Module kopieren, die bash_gate importiert
    for helper in ("hook_utils.py", "config_loader.py", "workflow.py",
                   "workflow_state_multi.py", "override_token.py"):
        src = _HOOKS_DIR / helper
        if src.exists():
            shutil.copy(src, hooks / helper)

    # Workflow-Dir anlegen + leere Settings (kein aktiver Workflow → Gate überspringt 5b/5c)
    (repo / ".claude" / "workflows" / "_log").mkdir(parents=True)
    settings = repo / ".claude" / "settings.local.json"
    settings.write_text(json.dumps({"env": {"OPENSPEC_ACTIVE_WORKFLOW": ""}}))

    # Baseline-Commit (leeres Repo erlaubt kein git diff --cached)
    readme = repo / "README.md"
    readme.write_text("# test repo\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "baseline")

    return repo


def _run_bash_gate(repo: Path, command: str) -> subprocess.CompletedProcess:
    """Ruft bash_gate.py via Subprocess auf mit korrektem stdin-JSON."""
    stdin_payload = json.dumps({"tool_input": {"command": command}})
    env = dict(os.environ)
    # Kein aktiver Workflow → Gate überspringt 5b/5c (Rebase + Adversary)
    env.pop("OPENSPEC_ACTIVE_WORKFLOW", None)
    env.pop("GZ_ACTIVE_WORKFLOW", None)
    return subprocess.run(
        [sys.executable, str(repo / ".claude" / "hooks" / "bash_gate.py")],
        cwd=repo,
        input=stdin_payload,
        capture_output=True,
        text=True,
        env=env,
    )


def _stage_file(repo: Path, rel_path: str, content: str = "# changed\n") -> None:
    """Datei im Repo anlegen (ggf. Eltern-Dirs) und stagen."""
    full = repo / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)
    _git(repo, "add", rel_path)


# ---------------------------------------------------------------------------
# AC-1: Entscheidungsfläche gestaged, kein ADR, kein [no-adr] → blockiert
# ---------------------------------------------------------------------------

class TestAC1BlockWhenDecisionSurfaceWithoutAdr:
    """AC-1: Gate blockt Commit wenn Entscheidungsfläche ohne ADR gestaged."""

    def test_adr_guard_module_importable(self):
        """adr_guard.py muss importierbar sein (RED: Datei fehlt → ImportError)."""
        guard = _load_adr_guard()
        assert hasattr(guard, "check"), "adr_guard muss eine Funktion 'check' exportieren"

    def test_check_blocks_when_decision_surface_no_adr(self):
        """check() blockiert bei Entscheidungsfläche ohne ADR: gibt Fehlermeldung zurück."""
        guard = _load_adr_guard()
        staged = ["src/outputs/telegram.py"]
        msg = "fix: adjust formatting"
        result = guard.check(staged, msg, {})
        assert result is not None, (
            "check() muss eine Block-Meldung zurückgeben wenn Entscheidungsfläche "
            "ohne ADR gestaged und kein [no-adr] in Message"
        )
        assert "src/outputs/telegram.py" in result, (
            f"Block-Meldung muss die betroffene Datei nennen: {result!r}"
        )
        assert "docs/adr" in result.lower() or "no-adr" in result.lower(), (
            f"Block-Meldung muss die zwei Auswege nennen: {result!r}"
        )

    def test_integration_bash_gate_blocks_decision_surface(self, tmp_path):
        """Integration: bash_gate.py blockiert (Exit 2) bei Entscheidungsfläche ohne ADR."""
        repo = _setup_repo(tmp_path)
        _stage_file(repo, "src/outputs/telegram.py")

        res = _run_bash_gate(repo, 'git commit -m "fix: adjust channel code"')
        assert res.returncode == 2, (
            f"bash_gate muss Commit mit Entscheidungsfläche blockieren (Exit 2). "
            f"rc={res.returncode} stderr={res.stderr!r}"
        )
        output = res.stderr + res.stdout
        assert "telegram.py" in output or "adr" in output.lower(), (
            f"Fehlermeldung muss Datei oder ADR nennen: {output!r}"
        )


# ---------------------------------------------------------------------------
# AC-2: Entscheidungsfläche + docs/adr/*.md mitgestaged → erlaubt
# ---------------------------------------------------------------------------

class TestAC2AllowWhenAdrStaged:
    """AC-2: Gate lässt durch wenn passendes docs/adr/*.md mitgestaged."""

    def test_check_allows_when_adr_staged(self):
        """check() gibt None zurück wenn docs/adr/NNNN-*.md mitgestaged."""
        guard = _load_adr_guard()
        staged = ["src/outputs/telegram.py", "docs/adr/0010-telegram-output.md"]
        msg = "feat: add telegram channel [relates to ADR-10]"
        result = guard.check(staged, msg, {})
        assert result is None, (
            f"check() muss None zurückgeben wenn ADR mitgestaged: {result!r}"
        )

    def test_integration_bash_gate_allows_with_adr_staged(self, tmp_path):
        """Integration: bash_gate.py lässt durch (Exit 0) wenn ADR mitgestaged."""
        repo = _setup_repo(tmp_path)
        _stage_file(repo, "src/outputs/telegram.py")
        _stage_file(repo, "docs/adr/0010-telegram-output.md",
                    content="# ADR-10: Telegram Output\n\n## Status: Accepted\n")

        res = _run_bash_gate(repo, 'git commit -m "feat: telegram channel"')
        assert res.returncode == 0, (
            f"Mit mitgestagetem ADR muss Gate durchlassen (Exit 0). "
            f"rc={res.returncode} stderr={res.stderr!r}"
        )


# ---------------------------------------------------------------------------
# AC-3: [no-adr] in Message → erlaubt (bewusste Verneinung)
# ---------------------------------------------------------------------------

class TestAC3AllowWhenNoAdrMarker:
    """AC-3: Gate lässt durch wenn Commit-Message [no-adr] enthält."""

    def test_check_allows_when_no_adr_in_message(self):
        """check() gibt None zurück wenn [no-adr] in Commit-Message."""
        guard = _load_adr_guard()
        staged = ["src/outputs/telegram.py"]
        msg = "fix: minor typo in telegram output [no-adr]"
        result = guard.check(staged, msg, {})
        assert result is None, (
            f"check() muss None zurückgeben bei [no-adr] in Message: {result!r}"
        )

    def test_integration_bash_gate_allows_with_no_adr_marker(self, tmp_path):
        """Integration: bash_gate.py lässt durch (Exit 0) mit [no-adr] in Message."""
        repo = _setup_repo(tmp_path)
        _stage_file(repo, "src/outputs/telegram.py")

        res = _run_bash_gate(repo, 'git commit -m "fix: typo in telegram output [no-adr]"')
        assert res.returncode == 0, (
            f"Mit [no-adr] in Message muss Gate durchlassen (Exit 0). "
            f"rc={res.returncode} stderr={res.stderr!r}"
        )


# ---------------------------------------------------------------------------
# AC-4: Nur Nicht-Entscheidungs-Datei gestaged → No-Op (Exit 0)
# ---------------------------------------------------------------------------

class TestAC4NoOpForNonDecisionFiles:
    """AC-4: Gate ist No-Op wenn keine Entscheidungsfläche gestaged."""

    def test_check_noop_for_non_decision_file(self):
        """check() gibt None zurück wenn nur Services/andere Dateien gestaged."""
        guard = _load_adr_guard()
        staged = ["src/services/foo.py"]
        msg = "fix: service logic"
        result = guard.check(staged, msg, {})
        assert result is None, (
            f"check() muss None zurückgeben für Nicht-Entscheidungsdatei: {result!r}"
        )

    def test_check_noop_for_tests_and_docs(self):
        """check() gibt None zurück für Tests, docs/ und sonstige Nicht-Flächen."""
        guard = _load_adr_guard()
        for path in ["tests/tdd/test_something.py", "docs/features/foo.md", "README.md"]:
            result = guard.check([path], "fix: update", {})
            assert result is None, (
                f"check() muss None zurückgeben für {path!r}: {result!r}"
            )

    def test_integration_bash_gate_noop_non_decision_file(self, tmp_path):
        """Integration: bash_gate.py lässt durch (Exit 0) bei reiner Service-Datei."""
        repo = _setup_repo(tmp_path)
        _stage_file(repo, "src/services/foo.py")

        res = _run_bash_gate(repo, 'git commit -m "fix: service logic"')
        assert res.returncode == 0, (
            f"Ohne Entscheidungsfläche muss Gate No-Op sein (Exit 0). "
            f"rc={res.returncode} stderr={res.stderr!r}"
        )


# ---------------------------------------------------------------------------
# AC-5: _validate_transition blockt bei fehlendem ADR-Feld in Spec
# ---------------------------------------------------------------------------

class TestAC5ValidateTransitionAdrField:
    """AC-5: workflow.py _validate_transition prüft ADR-Pflichtfeld ab phase4_approved."""

    # Helfer: _validate_transition importieren
    @staticmethod
    def _load_validate_transition():
        """Importiert _validate_transition aus workflow.py.

        Achtung: Funktion existiert, aber ADR-Check-Logik fehlt noch (RED-Zustand).
        """
        spec = importlib.util.spec_from_file_location(
            "workflow_885_test", _HOOKS_DIR / "workflow.py"
        )
        mod = importlib.util.module_from_spec(spec)
        if str(_HOOKS_DIR) not in sys.path:
            sys.path.insert(0, str(_HOOKS_DIR))
        spec.loader.exec_module(mod)
        return mod._validate_transition

    @staticmethod
    def _write_spec_without_adr(tmp_dir: Path) -> Path:
        """Spec-Fixture ohne ausgefülltes ADR-Feld (leeres / fehlendes ADR-Feld).
        Hat created: 2026-06-25 → Neuspec → ADR-Check greift."""
        spec_file = tmp_dir / "spec_no_adr.md"
        spec_file.write_text(
            "---\n"
            "created: 2026-06-25\n"
            "---\n\n"
            "# Test Spec Without ADR\n\n"
            "## Acceptance Criteria\n\n"
            "**AC-1:** Given X / When Y / Then Z (kein ADR-Feld vorhanden)\n\n"
            "## Architektur-Entscheidung (ADR)\n\n"
            "<!-- TODO: Architektur-Entscheidung ausfüllen -->\n"
        )
        return spec_file

    @staticmethod
    def _write_spec_with_adr_number(tmp_dir: Path) -> Path:
        """Spec-Fixture mit ausgefülltem ADR-Nr.-Feld (ADR-5).
        Hat created: 2026-06-25 → Neuspec → ADR-Check greift → erlaubt wegen ADR-5."""
        spec_file = tmp_dir / "spec_with_adr.md"
        spec_file.write_text(
            "---\n"
            "created: 2026-06-25\n"
            "---\n\n"
            "# Test Spec With ADR\n\n"
            "## Acceptance Criteria\n\n"
            "**AC-1:** Given X / When Y / Then Z\n\n"
            "## Architektur-Entscheidung (ADR)\n\n"
            "- **ADR-Nr.:** ADR-5 — Wechsel von Provider A zu Provider B\n"
            "- **Rationale:** Performance-Gründe\n"
        )
        return spec_file

    @staticmethod
    def _write_spec_with_adr_keine(tmp_dir: Path) -> Path:
        """Spec-Fixture mit 'keine' als ADR-Angabe (bewusste Verneinung).
        Hat created: 2026-06-25 → Neuspec → ADR-Check greift → erlaubt wegen 'keine'."""
        spec_file = tmp_dir / "spec_with_keine.md"
        spec_file.write_text(
            "---\n"
            "created: 2026-06-25\n"
            "---\n\n"
            "# Test Spec With 'keine'\n\n"
            "## Acceptance Criteria\n\n"
            "**AC-1:** Given X / When Y / Then Z\n\n"
            "## Architektur-Entscheidung (ADR)\n\n"
            "- **ADR-Nr.:** keine — Dieses Vorhaben trifft keine Architekturentscheidung.\n"
        )
        return spec_file

    @staticmethod
    def _make_workflow_data(spec_file: Path, context_file: Path) -> dict:
        """Minimaler Workflow-State für _validate_transition."""
        return {
            "name": "test-885",
            "workflow_type": "feature",
            "current_phase": "phase3_spec",
            "spec_file": str(spec_file),
            "spec_approved": True,
            "context_file": str(context_file),
        }

    def test_blocks_when_adr_field_missing_or_empty(self, tmp_path):
        """_validate_transition blockt Transition zu phase4_approved wenn ADR-Feld leer."""
        validate = self._load_validate_transition()
        context_file = tmp_path / "context.md"
        context_file.write_text("# context\n")
        spec_file = self._write_spec_without_adr(tmp_path)

        data = self._make_workflow_data(spec_file, context_file)
        error = validate(data, "phase4_approved")

        assert error is not None, (
            "_validate_transition muss Fehler zurückgeben wenn ADR-Feld nicht ausgefüllt "
            f"(spec: {spec_file})"
        )
        assert "adr" in error.lower(), (
            f"Fehlermeldung muss 'ADR' erwähnen: {error!r}"
        )

    def test_allows_when_adr_number_present(self, tmp_path):
        """_validate_transition erlaubt Transition wenn ADR-<n> in Spec vorhanden."""
        validate = self._load_validate_transition()
        context_file = tmp_path / "context.md"
        context_file.write_text("# context\n")
        spec_file = self._write_spec_with_adr_number(tmp_path)

        data = self._make_workflow_data(spec_file, context_file)
        error = validate(data, "phase4_approved")

        assert error is None, (
            f"_validate_transition muss None zurückgeben wenn ADR-Nr vorhanden: {error!r}"
        )

    def test_allows_when_adr_field_says_keine(self, tmp_path):
        """_validate_transition erlaubt Transition wenn 'keine' im ADR-Feld steht."""
        validate = self._load_validate_transition()
        context_file = tmp_path / "context.md"
        context_file.write_text("# context\n")
        spec_file = self._write_spec_with_adr_keine(tmp_path)

        data = self._make_workflow_data(spec_file, context_file)
        error = validate(data, "phase4_approved")

        assert error is None, (
            f"_validate_transition muss None zurückgeben wenn 'keine' im ADR-Feld: {error!r}"
        )

    def test_adr_check_does_not_affect_lower_phases(self, tmp_path):
        """ADR-Check greift nur ab phase4_approved — frühere Phasen bleiben unberührt."""
        validate = self._load_validate_transition()
        context_file = tmp_path / "context.md"
        context_file.write_text("# context\n")
        spec_file = self._write_spec_without_adr(tmp_path)

        # Transition zu phase3_spec (vor phase4_approved) — kein ADR-Check erwartet
        data = {
            "name": "test-885",
            "workflow_type": "feature",
            "current_phase": "phase2_analyse",
            "context_file": str(context_file),
        }
        error = validate(data, "phase3_spec")

        assert error is None, (
            f"ADR-Check darf für phase3_spec nicht greifen: {error!r}"
        )


# ---------------------------------------------------------------------------
# F001: Rueckwaertskompatibilitaet — Altspecs grandfathered
# ---------------------------------------------------------------------------

class TestF001BackwardCompatibility:
    """F001: Altspecs (created < 2026-06-25) werden nicht durch ADR-Check geblockt."""

    @staticmethod
    def _load_validate_transition():
        spec = importlib.util.spec_from_file_location(
            "workflow_885_f001", _HOOKS_DIR / "workflow.py"
        )
        mod = importlib.util.module_from_spec(spec)
        if str(_HOOKS_DIR) not in sys.path:
            sys.path.insert(0, str(_HOOKS_DIR))
        spec.loader.exec_module(mod)
        return mod._validate_transition

    def test_old_spec_without_adr_section_is_grandfathered(self, tmp_path):
        """Altspec (created: 2026-01-01, keine ADR-Sektion) → Transition erlaubt."""
        validate = self._load_validate_transition()
        context_file = tmp_path / "context.md"
        context_file.write_text("# context\n")

        spec_file = tmp_path / "old_spec.md"
        spec_file.write_text(
            "---\n"
            "created: 2026-01-01\n"
            "---\n\n"
            "# Alte Spec\n\n"
            "## Acceptance Criteria\n\n"
            "**AC-1:** Given X / When Y / Then Z\n"
            # Keine ADR-Sektion vorhanden
        )

        data = {
            "name": "test-f001",
            "workflow_type": "feature",
            "current_phase": "phase3_spec",
            "spec_file": str(spec_file),
            "spec_approved": True,
            "context_file": str(context_file),
        }
        error = validate(data, "phase4_approved")

        assert error is None, (
            f"Altspec (created: 2026-01-01) darf NICHT durch ADR-Check geblockt werden: {error!r}"
        )

    def test_spec_without_created_field_is_grandfathered(self, tmp_path):
        """Spec ohne created-Feld → grandfathered → Transition erlaubt."""
        validate = self._load_validate_transition()
        context_file = tmp_path / "context.md"
        context_file.write_text("# context\n")

        spec_file = tmp_path / "no_created.md"
        spec_file.write_text(
            "# Spec ohne created-Feld\n\n"
            "## Acceptance Criteria\n\n"
            "**AC-1:** Given X / When Y / Then Z\n"
        )

        data = {
            "name": "test-f001b",
            "workflow_type": "feature",
            "current_phase": "phase3_spec",
            "spec_file": str(spec_file),
            "spec_approved": True,
            "context_file": str(context_file),
        }
        error = validate(data, "phase4_approved")

        assert error is None, (
            f"Spec ohne created-Feld darf nicht geblockt werden: {error!r}"
        )

    def test_new_spec_with_created_today_enforces_adr(self, tmp_path):
        """Neuspec (created: 2026-06-25, keine ADR-Sektion) → ADR-Check greift → blockt."""
        validate = self._load_validate_transition()
        context_file = tmp_path / "context.md"
        context_file.write_text("# context\n")

        spec_file = tmp_path / "new_spec_no_adr.md"
        spec_file.write_text(
            "---\n"
            "created: 2026-06-25\n"
            "---\n\n"
            "# Neue Spec ohne ADR\n\n"
            "## Acceptance Criteria\n\n"
            "**AC-1:** Given X / When Y / Then Z\n\n"
            "## Architektur-Entscheidung (ADR)\n\n"
            "- **ADR-Nr.:** <!-- Platzhalter -->\n"
        )

        data = {
            "name": "test-f001c",
            "workflow_type": "feature",
            "current_phase": "phase3_spec",
            "spec_file": str(spec_file),
            "spec_approved": True,
            "context_file": str(context_file),
        }
        error = validate(data, "phase4_approved")

        assert error is not None, (
            "Neuspec (created: 2026-06-25) ohne ausgefuelltes ADR-Feld muss geblockt werden"
        )
        assert "adr" in error.lower(), f"Fehlermeldung muss ADR erwaehnen: {error!r}"

    def test_new_spec_with_adr_number_is_allowed(self, tmp_path):
        """Neuspec (created: 2026-06-25) mit ADR-7 → erlaubt."""
        validate = self._load_validate_transition()
        context_file = tmp_path / "context.md"
        context_file.write_text("# context\n")

        spec_file = tmp_path / "new_spec_with_adr.md"
        spec_file.write_text(
            "---\n"
            "created: 2026-06-25\n"
            "---\n\n"
            "# Neue Spec mit ADR\n\n"
            "## Acceptance Criteria\n\n"
            "**AC-1:** Given X / When Y / Then Z\n\n"
            "## Architektur-Entscheidung (ADR)\n\n"
            "- **ADR-Nr.:** ADR-7 — Neues Gate-System\n"
            "- **Rationale:** Performance-Gruende\n"
        )

        data = {
            "name": "test-f001d",
            "workflow_type": "feature",
            "current_phase": "phase3_spec",
            "spec_file": str(spec_file),
            "spec_approved": True,
            "context_file": str(context_file),
        }
        error = validate(data, "phase4_approved")

        assert error is None, (
            f"Neuspec mit ADR-7 muss erlaubt werden: {error!r}"
        )


# ---------------------------------------------------------------------------
# F002: --message= Form (Gleichheitszeichen) muss [no-adr] erkennen
# ---------------------------------------------------------------------------

class TestF002CommitMessageParsing:
    """F002: [no-adr] muss auch bei --message="..." (Gleichheitszeichen) erkannt werden."""

    def test_no_adr_with_equals_message_form(self, tmp_path):
        """Integration: git commit --message="… [no-adr]" muss durchgelassen werden (Exit 0)."""
        repo = _setup_repo(tmp_path)
        _stage_file(repo, "src/outputs/telegram.py")

        res = _run_bash_gate(repo, 'git commit --message="fix: typo in output [no-adr]"')
        assert res.returncode == 0, (
            f"git commit --message='... [no-adr]' (Gleichheitsform) muss Exit 0 liefern. "
            f"rc={res.returncode} stderr={res.stderr!r}"
        )

    def test_no_adr_with_space_message_form(self, tmp_path):
        """Integration: git commit --message '… [no-adr]' (Space-Form) muss durchgelassen werden."""
        repo = _setup_repo(tmp_path)
        _stage_file(repo, "src/outputs/telegram.py")

        res = _run_bash_gate(repo, "git commit --message 'fix: typo in output [no-adr]'")
        assert res.returncode == 0, (
            f"git commit --message '...' (Space-Form) mit [no-adr] muss Exit 0 liefern. "
            f"rc={res.returncode} stderr={res.stderr!r}"
        )


# ---------------------------------------------------------------------------
# F004: Template-Platzhalter "[ADR-NNNN oder "keine"]" soll nicht durchrutschen
# ---------------------------------------------------------------------------

class TestF004TemplatePlaceholder:
    """F004: Unausgefuellter Template-Platzhalter '[ADR-NNNN oder "keine"]' blockiert bei Neuspec."""

    @staticmethod
    def _load_validate_transition():
        spec = importlib.util.spec_from_file_location(
            "workflow_885_f004", _HOOKS_DIR / "workflow.py"
        )
        mod = importlib.util.module_from_spec(spec)
        if str(_HOOKS_DIR) not in sys.path:
            sys.path.insert(0, str(_HOOKS_DIR))
        spec.loader.exec_module(mod)
        return mod._validate_transition

    def test_template_placeholder_keine_blocks_new_spec(self, tmp_path):
        """Unausgefuellter Template-Platzhalter '[ADR-NNNN oder "keine"]' wird als leer gewertet → blockt."""
        validate = self._load_validate_transition()
        context_file = tmp_path / "context.md"
        context_file.write_text("# context\n")

        # Exakt der Template-Text aus docs/specs/_template.md
        spec_file = tmp_path / "template_copy.md"
        spec_file.write_text(
            "---\n"
            "created: 2026-06-25\n"
            "---\n\n"
            "# Template Spec\n\n"
            "## Acceptance Criteria\n\n"
            "**AC-1:** Given X / When Y / Then Z\n\n"
            '## Architektur-Entscheidung (ADR)\n\n'
            '- **ADR-Nr.:** [ADR-NNNN oder "keine"]\n'
            "- **Rationale:** [kurz: warum diese Entscheidung]\n"
        )

        data = {
            "name": "test-f004",
            "workflow_type": "feature",
            "current_phase": "phase3_spec",
            "spec_file": str(spec_file),
            "spec_approved": True,
            "context_file": str(context_file),
        }
        error = validate(data, "phase4_approved")

        assert error is not None, (
            'Unausgefuellter Platzhalter "[ADR-NNNN oder \\"keine\\"]" darf nicht als '
            "ausgefuellter Wert gelten — muss blockieren"
        )

    def test_real_keine_without_brackets_allows(self, tmp_path):
        """Echtes 'keine' (ohne Klammern) soll erlaubt sein."""
        validate = self._load_validate_transition()
        context_file = tmp_path / "context.md"
        context_file.write_text("# context\n")

        spec_file = tmp_path / "real_keine.md"
        spec_file.write_text(
            "---\n"
            "created: 2026-06-25\n"
            "---\n\n"
            "# Spec mit echtem keine\n\n"
            "## Acceptance Criteria\n\n"
            "**AC-1:** Given X / When Y / Then Z\n\n"
            "## Architektur-Entscheidung (ADR)\n\n"
            "- **ADR-Nr.:** keine — Dieses Vorhaben trifft keine Architekturentscheidung.\n"
            "- **Rationale:** Nur ein kleines Bug-Fix.\n"
        )

        data = {
            "name": "test-f004b",
            "workflow_type": "feature",
            "current_phase": "phase3_spec",
            "spec_file": str(spec_file),
            "spec_approved": True,
            "context_file": str(context_file),
        }
        error = validate(data, "phase4_approved")

        assert error is None, (
            f"Echtes 'keine' (ohne Klammern) muss erlaubt sein: {error!r}"
        )


# ---------------------------------------------------------------------------
# F005: adr_guard.py selbst (Guard-Hooks) ist Entscheidungsflaeche
# ---------------------------------------------------------------------------

class TestF005SelfExempt:
    """F005: Staged .claude/hooks/adr_guard.py ohne ADR → Gate blockt."""

    def test_adr_guard_itself_is_decision_surface(self):
        """adr_guard.py selbst matcht das erweiterte Pattern .*_(gate|guard).py."""
        guard = _load_adr_guard()
        staged = [".claude/hooks/adr_guard.py"]
        msg = "fix: improve adr guard logic"
        result = guard.check(staged, msg, {})
        assert result is not None, (
            "adr_guard.py muss als Entscheidungsflaeche erkannt werden "
            "(Pattern: .*_(gate|guard).py)"
        )

    def test_integration_bash_gate_blocks_adr_guard_change(self, tmp_path):
        """Integration: staged .claude/hooks/adr_guard.py ohne ADR → Gate blockt (Exit 2).

        Die Datei wird mit vollstaendiger check()-Funktion gestaged (realistisches Szenario:
        Entwickler aendert den Guard, der Import in bash_gate muss noch funktionieren).
        """
        repo = _setup_repo(tmp_path)
        # Vollstaendiger Inhalt mit check()-Funktion, damit bash_gate den Guard importieren
        # kann — sonst AttributeError in try/except → stilles Allow (kein echter Test)
        modified_guard_content = (
            _ADR_GUARD_SRC.read_text()
            + "\n# modified: extra comment to create a staged change\n"
        )
        _stage_file(repo, ".claude/hooks/adr_guard.py", content=modified_guard_content)

        res = _run_bash_gate(repo, 'git commit -m "fix: adjust guard logic"')
        assert res.returncode == 2, (
            f"Staged adr_guard.py ohne ADR muss geblockt werden (Exit 2). "
            f"rc={res.returncode} stderr={res.stderr!r}"
        )
