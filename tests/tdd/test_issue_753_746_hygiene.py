"""
TDD RED — Issues #753 + #746: Test-Hygiene & user-story-planner Checkpoint
Spec: docs/specs/modules/issue_753_746_test_hygiene_and_planner_checkpoint.md

# doc-compliance-test
Diese Tests prüfen Workflow-Artefakte (Test-Dateien, Spec-Dateien, Agent-Markdown)
als Compliance-Nachweis — explizit erlaubte Ausnahme laut CLAUDE.md
("Dokumentations-Compliance-Tests die Workflow-Dateien selbst als Artefakt prüfen").

KEINE MOCKS — liest echte Repo-Inhalte.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[2]
TDD_DIR = REPO_ROOT / "tests" / "tdd"
FORBIDDEN_TEST = TDD_DIR / "test_issue_299_edit_report_config_polish.py"
OBSOLETE_SPEC = (
    REPO_ROOT
    / "docs" / "specs" / "modules"
    / "issue_299_edit_report_config_section_polish.md"
)
PLANNER = REPO_ROOT / ".claude" / "agents" / "user-story-planner.md"
COMPONENT_NAME = "EditReportConfigSection.svelte"


# ---------------------------------------------------------------------------
# AC-1: Verbotener Datei-Inhalt-Test entfernt
# ---------------------------------------------------------------------------

def test_forbidden_filecontent_test_removed():  # doc-compliance-test
    """AC-1: test_issue_299_edit_report_config_polish.py existiert nicht mehr."""
    assert not FORBIDDEN_TEST.exists(), (
        f"{FORBIDDEN_TEST.relative_to(REPO_ROOT)} existiert noch. Der Test liest "
        f"{COMPONENT_NAME}-Quelltext und assertet auf CSS-Klassen/Testids — "
        "verbotenes Datei-Inhalt-Anti-Pattern (Issue #753). Muss gelöscht sein."
    )


# Bekannter Rest-Befund: weitere Dateien mit demselben Anti-Pattern werden im
# systematischen Sweep #754 behandelt (sprengen das 250-LoC-Limit dieses Workflows).
# test_issue_278_form_controls.py liest EditReportConfigSection.svelte ebenfalls,
# ist aber Teil von #754. Dieser Test schützt vor NEUEN Einführungen.
DEFERRED_SWEEP = {"test_issue_278_form_controls.py"}  # tracked by #754


def test_no_test_reads_editreportconfig_source():  # doc-compliance-test
    """AC-1: Kein (neuer) Test liest EditReportConfigSection.svelte per read_text().

    Die spezifisch in #753 entfernte Datei darf nicht zurückkehren; bekannte
    Rest-Befunde sind über DEFERRED_SWEEP (#754) dokumentiert.
    """
    offenders = []
    for path in TDD_DIR.glob("test_*.py"):
        if path.name == Path(__file__).name or path.name in DEFERRED_SWEEP:
            continue
        text = path.read_text()
        if COMPONENT_NAME in text and "read_text()" in text:
            offenders.append(path.name)
    assert not offenders, (
        f"Folgende Tests lesen {COMPONENT_NAME}-Quelltext per read_text() "
        f"(verbotenes Anti-Pattern, Issue #753): {offenders}. "
        "Falls bewusst zum Sweep #754 gehörend, in DEFERRED_SWEEP aufnehmen."
    )


# ---------------------------------------------------------------------------
# AC-3: Obsolete #299-Spec entfernt
# ---------------------------------------------------------------------------

def test_obsolete_spec_removed():  # doc-compliance-test
    """AC-3: Die verwaiste #299-Spec ist entfernt."""
    assert not OBSOLETE_SPEC.exists(), (
        f"{OBSOLETE_SPEC.relative_to(REPO_ROOT)} existiert noch — verweist auf "
        "einen gelöschten Test. Muss entfernt sein (Issue #753 AC-3)."
    )


# ---------------------------------------------------------------------------
# AC-4 + AC-5: user-story-planner Checkpoint vor Phase 5
# ---------------------------------------------------------------------------

def _planner_text() -> str:
    assert PLANNER.exists(), f"{PLANNER} fehlt"
    return PLANNER.read_text()


def _between_phase4_and_phase5(text: str) -> str:
    """Liefert den Abschnitt zwischen dem Phase-4- und dem Phase-5-Markdown-Header.

    Bewusst auf die Markdown-Section-Header (`### Phase 4` / `### Phase 5`) gestützt,
    damit ein Checkpoint-Heading, das selbst das Wort 'Phase 5' enthält
    (z.B. 'PFLICHT-CHECKPOINT vor Phase 5'), den Abschnitt nicht vorzeitig abschneidet.
    """
    lower = text.lower()
    i4 = lower.find("### phase 4")
    i5 = lower.find("### phase 5", i4 + 1 if i4 >= 0 else 0)
    assert i4 >= 0 and i5 > i4, (
        "Konnte die Markdown-Header '### Phase 4' und '### Phase 5' in "
        "user-story-planner.md nicht finden — Struktur unerwartet (Issue #746)."
    )
    return text[i4:i5]


def test_planner_has_po_checkpoint_before_phase5():  # doc-compliance-test
    """AC-4: PFLICHT-Checkpoint mit Bestätigungs-Erwartung zwischen Phase 4 und Phase 5."""
    section = _between_phase4_and_phase5(_planner_text())
    low = section.lower()
    assert "checkpoint" in low and ("pflicht" in low or "mandatory" in low), (
        "Zwischen Phase 4 und Phase 5 fehlt ein als PFLICHT markierter Checkpoint "
        "(Issue #746 AC-4)."
    )
    # Muss Story + Acceptance Criteria + Feature-Liste dem PO vorlegen
    assert "story" in low, "Checkpoint legt die Story nicht vor (AC-4)."
    assert "acceptance" in low or "akzeptanz" in low, (
        "Checkpoint legt die Acceptance Criteria nicht vor (AC-4)."
    )
    assert "feature" in low, "Checkpoint legt die Feature-Liste nicht vor (AC-4)."
    # Muss auf explizite Bestätigung warten
    assert "bestätig" in low or "go" in low or "confirm" in low, (
        "Checkpoint wartet nicht auf explizite PO-Bestätigung (AC-4)."
    )


def test_planner_checkpoint_mandates_stop():  # doc-compliance-test
    """AC-5: Ohne Bestätigung STOP — keine Issues, kein Dokument."""
    section = _between_phase4_and_phase5(_planner_text())
    low = section.lower()
    assert "stop" in low, (
        "Checkpoint schreibt kein STOP bei fehlender Bestätigung vor (Issue #746 AC-5)."
    )
    # Keine Issue-Erstellung ohne Bestätigung
    assert "gh issue create" in low or "issue" in low, (
        "Checkpoint benennt das Issue-Anlegen nicht als blockierte Aktion (AC-5)."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
