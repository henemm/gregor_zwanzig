# doc-compliance-test
"""Bug #567 — Stale /7-deploy & "approved" Referenzen in .claude/commands/.

Doku-Compliance: nach #563 muss /7-deploy aus der Phasen-Tabelle und dem
Tech-Lead-Brief-Verweis verschwunden sein und das Approval-Keyword "approved"
in den README-Workflows durch "go" ersetzt sein.

Spec: docs/specs/modules/bug_567_stale_deploy_refs.md
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / ".claude" / "commands" / "README.md"
IMPLEMENT = REPO_ROOT / ".claude" / "commands" / "5-implement.md"


def _readme_lines() -> list[str]:
    return README.read_text(encoding="utf-8").splitlines()


def _implement_text() -> str:
    return IMPLEMENT.read_text(encoding="utf-8")


class TestBug567StaleDeployRefs:
    """AC-1..AC-6 aus bug_567_stale_deploy_refs spec."""

    def test_ac1_phase_table_no_7_deploy_in_phase_8(self) -> None:
        """AC-1: Phasen-Tabelle Phase 8 enthaelt /7-deploy nicht mehr."""
        for line in _readme_lines():
            if line.startswith("| 8 |"):
                assert "/7-deploy" not in line, (
                    f"Phase-8-Zeile enthaelt noch /7-deploy: {line!r}"
                )
                return
        pytest.fail("Phase-8-Zeile in README.md nicht gefunden")

    def test_ac2_phase_table_phase_4_uses_go(self) -> None:
        """AC-2: Phasen-Tabelle Phase 4 nennt 'go' statt 'approved'."""
        for line in _readme_lines():
            if line.startswith("| 4 |"):
                assert '"go"' in line, (
                    f"Phase-4-Zeile nennt 'go' nicht: {line!r}"
                )
                assert '"approved"' not in line, (
                    f"Phase-4-Zeile nennt noch 'approved': {line!r}"
                )
                return
        pytest.fail("Phase-4-Zeile in README.md nicht gefunden")

    def test_ac3_example_workflows_use_go(self) -> None:
        """AC-3: README-Beispiel-Workflows verwenden # User: "go"."""
        text = README.read_text(encoding="utf-8")
        assert '# User: "approved"' not in text, (
            "Beispiel-Workflow enthaelt noch '# User: \"approved\"'"
        )
        assert '# User: "go"' in text, (
            "Beispiel-Workflow enthaelt kein '# User: \"go\"'"
        )

    def test_ac4_state_list_uses_go(self) -> None:
        """AC-4: State-Liste nennt 'go' statt 'approved'.

        Der State-Name phase4_approved bleibt unveraendert.
        """
        text = README.read_text(encoding="utf-8")
        assert 'User "approved"' not in text, (
            "State-Liste verwendet noch 'User \"approved\"'"
        )
        assert 'User "go"' in text, (
            "State-Liste verwendet kein 'User \"go\"'"
        )
        assert "phase4_approved" in text, (
            "State-Name phase4_approved soll erhalten bleiben"
        )

    def test_ac5_implement_tech_lead_brief_points_to_validate(self) -> None:
        """AC-5: 5-implement.md verweist auf /6-validate Step 5 statt /7-deploy."""
        text = _implement_text()
        assert "/7-deploy" not in text, (
            "5-implement.md enthaelt noch Verweis auf /7-deploy"
        )
        assert "/6-validate" in text, (
            "5-implement.md verweist nicht auf /6-validate"
        )

    def test_ac6_no_7_deploy_references_in_commands_dir(self) -> None:
        """AC-6: kein /7-deploy mehr in .claude/commands/."""
        commands_dir = REPO_ROOT / ".claude" / "commands"
        hits: list[tuple[Path, int, str]] = []
        for md_file in commands_dir.glob("*.md"):
            for lineno, line in enumerate(
                md_file.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if "/7-deploy" in line:
                    hits.append((md_file, lineno, line))
        assert not hits, (
            "Es gibt noch /7-deploy-Treffer in .claude/commands/: "
            + ", ".join(f"{p.name}:{ln}" for p, ln, _ in hits)
        )
