"""
Bug #600: TDD-Tests müssen Verhalten beweisen, nicht Dateiinhalt prüfen.

Prüft, ob die drei Workflow-Dokumente das explizite Verbot von
Dateiinhalt-Checks als TDD-Nachweis enthalten.

Hinweis: Diese Tests prüfen Dokumentations-Compliance — d.h. ob die
Regeln tatsächlich in den Workflow-Dateien stehen. Das ist der einzige
Kontext, in dem file.read_text()-Checks akzeptabel sind: wenn das
Dokument selbst das Artefakt ist, nicht ein Proxy für Feature-Verhalten.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]


def test_claude_md_verbietet_dateiinhalt_checks():
    """AC-1: CLAUDE.md enthält explizites Verbot von file.read_text()-Checks."""
    content = (PROJECT_ROOT / "CLAUDE.md").read_text()
    mock_section_start = content.find("KEINE MOCKED TESTS")
    assert mock_section_start != -1, "Abschnitt 'KEINE MOCKED TESTS' fehlt in CLAUDE.md"

    section = content[mock_section_start:]
    assert "file.read_text()" in section, (
        "CLAUDE.md: Verbot von file.read_text()-Checks fehlt im KEINE-MOCKED-TESTS-Abschnitt"
    )
    assert "Verhaltensnachweis" in section or "Verhaltenstest" in section, (
        "CLAUDE.md: Hinweis auf Verhaltensnachweis fehlt im KEINE-MOCKED-TESTS-Abschnitt"
    )
    assert "Playwright" in section, (
        "CLAUDE.md: Konkrete Alternative (Playwright) fehlt im KEINE-MOCKED-TESTS-Abschnitt"
    )


def test_tdd_red_skill_verhaltenstest_pflicht():
    """AC-2: /4-tdd-red Skill enthält Verhaltenstest-Pflicht nach 'MUST BE RED'."""
    skill_path = PROJECT_ROOT / ".claude" / "commands" / "4-tdd-red.md"
    content = skill_path.read_text()

    must_be_red_pos = content.find("MUST BE RED")
    assert must_be_red_pos != -1, "Abschnitt 'MUST BE RED' fehlt in 4-tdd-red.md"

    section_after = content[must_be_red_pos:]
    assert "Verhaltenstest-Pflicht" in section_after, (
        "4-tdd-red.md: 'Verhaltenstest-Pflicht' fehlt nach dem MUST-BE-RED-Block"
    )
    assert "file.read_text()" in section_after, (
        "4-tdd-red.md: Verbot von file.read_text() fehlt nach dem MUST-BE-RED-Block"
    )


def test_spec_template_dateiinhalt_check_warnung():
    """AC-3: Spec-Template enthält Warnung gegen Dateiinhalt-Checks in der Test-Zeile."""
    content = (PROJECT_ROOT / "docs" / "specs" / "_template.md").read_text()

    ac_section_pos = content.find("Acceptance Criteria")
    assert ac_section_pos != -1, "Abschnitt 'Acceptance Criteria' fehlt in _template.md"

    ac_section = content[ac_section_pos:]
    assert "Dateiinhalt" in ac_section or "dateiinhalt" in ac_section.lower(), (
        "_template.md: Kein Hinweis auf Dateiinhalt-Checks im Acceptance-Criteria-Block"
    )
