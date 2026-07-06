"""
TDD RED: Bug #565 — Workflow Kontext-Reset: /compact durch /clear ersetzen

Tests prüfen, dass die drei Command-Files (5-implement.md, 6-validate.md, 7-deploy.md)
kein `/compact` mehr enthalten und stattdessen `/clear` mit einem Re-Read-Block
(workflow.py status + Spec-Pfad) am Phasenbeginn vorweisen.
"""

from pathlib import Path

COMMANDS_DIR = Path(__file__).parent.parent.parent / ".claude" / "commands"

IMPLEMENT_MD = COMMANDS_DIR / "5-implement.md"
VALIDATE_MD = COMMANDS_DIR / "6-validate.md"
DEPLOY_MD = COMMANDS_DIR / "7-deploy.md"


class TestAC1ImplementMd:
    """AC-1: 5-implement.md enthält kein /compact, aber /clear + Re-Read-Block."""

    def test_no_compact_in_implement(self):
        """
        GIVEN: 5-implement.md enthält bisher einen /compact-Aufruf
        WHEN: Datei auf /compact geprüft wird
        THEN: /compact kommt nicht mehr vor
        """
        content = IMPLEMENT_MD.read_text(encoding="utf-8")
        lines_with_compact = [
            (i + 1, line) for i, line in enumerate(content.splitlines())
            if line.strip() == "/compact"
        ]
        assert lines_with_compact == [], (
            "5-implement.md enthält noch /compact in Zeilen: "
            + ", ".join(f"{ln}" for ln, _ in lines_with_compact)
        )

    def test_has_clear_in_implement(self):
        """
        GIVEN: 5-implement.md hat keinen /clear-Aufruf
        WHEN: Datei auf /clear geprüft wird
        THEN: /clear kommt mindestens einmal vor
        """
        content = IMPLEMENT_MD.read_text(encoding="utf-8")
        lines_with_clear = [
            line for line in content.splitlines()
            if line.strip() == "/clear"
        ]
        assert lines_with_clear, (
            "5-implement.md enthält keinen /clear-Aufruf — fehlt der Reset-Block?"
        )

    def test_has_reread_block_in_implement(self):
        """
        GIVEN: 5-implement.md hat keinen Re-Read-Block nach /clear
        WHEN: Datei auf workflow.py status nach /clear geprüft wird
        THEN: workflow_state_multi.py status oder workflow.py status taucht
              nach dem /clear-Aufruf auf
        """
        content = IMPLEMENT_MD.read_text(encoding="utf-8")
        clear_pos = content.find("/clear")
        assert clear_pos != -1, "5-implement.md enthält kein /clear"

        after_clear = content[clear_pos:]
        has_status = (
            "workflow_state_multi.py status" in after_clear
            or "workflow.py status" in after_clear
        )
        assert has_status, (
            "In 5-implement.md fehlt nach /clear der Re-Read-Block "
            "(workflow_state_multi.py status oder workflow.py status)"
        )


class TestAC2ValidateMd:
    """AC-2: 6-validate.md hat /clear + Re-Read-Block am Anfang, vor den 4 Agents."""

    def test_has_clear_in_validate(self):
        """
        GIVEN: 6-validate.md hat keinen /clear-Aufruf
        WHEN: Datei auf /clear geprüft wird
        THEN: /clear kommt mindestens einmal vor
        """
        content = VALIDATE_MD.read_text(encoding="utf-8")
        lines_with_clear = [
            line for line in content.splitlines()
            if line.strip() == "/clear"
        ]
        assert lines_with_clear, (
            "6-validate.md enthält keinen /clear-Aufruf — fehlt der Reset-Block?"
        )

    def test_clear_before_parallel_agents_in_validate(self):
        """
        GIVEN: 6-validate.md startet mit 4 parallelen Agents ohne Reset
        WHEN: Position von /clear vs. erstem Agent-Start geprüft wird
        THEN: /clear steht vor dem ersten Parallel-Agent-Block
        """
        content = VALIDATE_MD.read_text(encoding="utf-8")
        clear_pos = content.find("/clear")
        assert clear_pos != -1, "6-validate.md enthält kein /clear"

        # Der erste Agent-Block beginnt mit "### Agent 1" oder "Launch **all 4"
        agent_markers = ["### Agent 1", "Launch **all 4"]
        first_agent_pos = min(
            (content.find(m) for m in agent_markers if content.find(m) != -1),
            default=-1,
        )
        assert first_agent_pos != -1, (
            "Konnte keinen Agent-Start-Marker in 6-validate.md finden"
        )
        assert clear_pos < first_agent_pos, (
            f"/clear (pos {clear_pos}) steht NACH dem ersten Agent-Block "
            f"(pos {first_agent_pos}) — muss davor stehen"
        )

    def test_has_reread_block_in_validate(self):
        """
        GIVEN: 6-validate.md hat keinen Re-Read-Block nach /clear
        WHEN: Datei auf workflow.py status nach /clear geprüft wird
        THEN: workflow_state_multi.py status oder workflow.py status taucht
              nach dem /clear-Aufruf auf
        """
        content = VALIDATE_MD.read_text(encoding="utf-8")
        clear_pos = content.find("/clear")
        assert clear_pos != -1, "6-validate.md enthält kein /clear"

        after_clear = content[clear_pos:]
        has_status = (
            "workflow_state_multi.py status" in after_clear
            or "workflow.py status" in after_clear
        )
        assert has_status, (
            "In 6-validate.md fehlt nach /clear der Re-Read-Block "
            "(workflow_state_multi.py status oder workflow.py status)"
        )


class TestAC3DeployMd:
    """AC-3: 7-deploy.md hat /clear + Re-Read-Block am Anfang, vor E2E."""

    def test_has_clear_in_deploy(self):
        """
        GIVEN: 7-deploy.md hat keinen /clear-Aufruf
        WHEN: Datei auf /clear geprüft wird
        THEN: /clear kommt mindestens einmal vor
        """
        content = DEPLOY_MD.read_text(encoding="utf-8")
        lines_with_clear = [
            line for line in content.splitlines()
            if line.strip() == "/clear"
        ]
        assert lines_with_clear, (
            "7-deploy.md enthält keinen /clear-Aufruf — fehlt der Reset-Block?"
        )

    def test_clear_before_e2e_in_deploy(self):
        """
        GIVEN: 7-deploy.md startet E2E ohne vorherigen Kontext-Reset
        WHEN: Position von /clear vs. E2E-Schritt geprüft wird
        THEN: /clear steht vor dem ersten E2E-Marker
        """
        content = DEPLOY_MD.read_text(encoding="utf-8")
        clear_pos = content.find("/clear")
        assert clear_pos != -1, "7-deploy.md enthält kein /clear"

        e2e_markers = ["/e2e-verify", "e2e_verified", "E2E gegen Staging"]
        first_e2e_pos = min(
            (content.find(m) for m in e2e_markers if content.find(m) != -1),
            default=-1,
        )
        assert first_e2e_pos != -1, (
            "Konnte keinen E2E-Marker in 7-deploy.md finden"
        )
        assert clear_pos < first_e2e_pos, (
            f"/clear (pos {clear_pos}) steht NACH dem E2E-Schritt "
            f"(pos {first_e2e_pos}) — muss davor stehen"
        )

    def test_has_reread_block_in_deploy(self):
        """
        GIVEN: 7-deploy.md hat keinen Re-Read-Block nach /clear
        WHEN: Datei auf workflow.py status nach /clear geprüft wird
        THEN: workflow_state_multi.py status oder workflow.py status taucht
              nach dem /clear-Aufruf auf
        """
        content = DEPLOY_MD.read_text(encoding="utf-8")
        clear_pos = content.find("/clear")
        assert clear_pos != -1, "7-deploy.md enthält kein /clear"

        after_clear = content[clear_pos:]
        has_status = (
            "workflow_state_multi.py status" in after_clear
            or "workflow.py status" in after_clear
        )
        assert has_status, (
            "In 7-deploy.md fehlt nach /clear der Re-Read-Block "
            "(workflow_state_multi.py status oder workflow.py status)"
        )


class TestAC4NoneHaveCompact:
    """AC-4: Keine der drei Dateien enthält /compact."""

    def test_implement_no_compact(self):
        """5-implement.md darf kein /compact enthalten."""
        content = IMPLEMENT_MD.read_text(encoding="utf-8")
        assert "/compact" not in content, (
            "5-implement.md enthält noch /compact"
        )

    def test_validate_no_compact(self):
        """6-validate.md darf kein /compact enthalten."""
        content = VALIDATE_MD.read_text(encoding="utf-8")
        assert "/compact" not in content, (
            "6-validate.md enthält /compact (sollte es nicht)"
        )

    def test_deploy_no_compact(self):
        """7-deploy.md darf kein /compact enthalten."""
        content = DEPLOY_MD.read_text(encoding="utf-8")
        assert "/compact" not in content, (
            "7-deploy.md enthält /compact (sollte es nicht)"
        )
