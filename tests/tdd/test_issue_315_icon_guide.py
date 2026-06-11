# doc-compliance-test
"""TDD-Tests für Issue #315 — Icon-Leitfaden (Lucide-Icon-Standard).

Prüft AC-4 der Spec docs/specs/modules/issue_315_icon_guide.md:

AC-4: sveltekit_best_practices.md enthält WIcon-Abgrenzungshinweis

Sweep #754: AC-2/AC-3 (grep auf Produkt-.svelte-Quelltext nach Icon-Import-Namen)
entfernt — Quelltext-Grep ist dasselbe Anti-Pattern wie read_text() (nicht
nutzersichtbar, kein Verhaltenstest). Verbleibend: AC-4 liest ausschließlich
das Docs-Artefakt sveltekit_best_practices.md — legitim als doc-compliance-test.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BEST_PRACTICES = REPO_ROOT / "docs" / "reference" / "sveltekit_best_practices.md"


# ---------------------------------------------------------------------------
# AC-4: WIcon-Abgrenzungshinweis in sveltekit_best_practices.md
# ---------------------------------------------------------------------------

class TestAC4WIconDocumentation:
    """AC-4: sveltekit_best_practices.md enthält WIcon-Abgrenzung."""

    def test_wicon_mentioned_in_best_practices(self):
        """
        GIVEN: docs/reference/sveltekit_best_practices.md
        WHEN:  grep auf 'WIcon'
        THEN:  mindestens 1 Treffer
        """
        content = BEST_PRACTICES.read_text()
        assert "WIcon" in content, (
            "WIcon-Abgrenzungshinweis fehlt in sveltekit_best_practices.md"
        )

    def test_icons_section_exists_in_best_practices(self):
        """
        GIVEN: docs/reference/sveltekit_best_practices.md
        WHEN:  grep auf '## Icons'
        THEN:  mindestens 1 Treffer (Abschnitt muss existieren)
        """
        content = BEST_PRACTICES.read_text()
        assert "## Icons" in content, (
            "## Icons (Lucide)-Abschnitt fehlt in sveltekit_best_practices.md"
        )

    def test_approved_action_table_present(self):
        """
        GIVEN: sveltekit_best_practices.md
        WHEN:  nach 'PencilIcon' und 'Trash2Icon' in der Icon-Tabelle suchen
        THEN:  beide Einträge vorhanden (Tabelle ist befüllt)
        """
        content = BEST_PRACTICES.read_text()
        assert "PencilIcon" in content, "PencilIcon fehlt in der Icon-Tabelle"
        assert "Trash2Icon" in content, "Trash2Icon fehlt in der Icon-Tabelle"

    def test_no_emoji_cross_reference_present(self):
        """
        GIVEN: sveltekit_best_practices.md
        WHEN:  nach AP-009 suchen
        THEN:  Cross-Reference auf Anti-Pattern AP-009 vorhanden
        """
        content = BEST_PRACTICES.read_text()
        assert "AP-009" in content, (
            "Kreuzreferenz auf AP-009 (no-emoji) fehlt in sveltekit_best_practices.md"
        )
