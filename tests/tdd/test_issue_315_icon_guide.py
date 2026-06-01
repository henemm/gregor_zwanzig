"""TDD-Tests für Issue #315 — Icon-Leitfaden (Lucide-Icon-Standard).

Prüft die Akzeptanzkriterien der Spec docs/specs/modules/issue_315_icon_guide.md:

AC-2: Kein bare `import Pencil ` mehr in frontend/src/ (muss PencilIcon sein)
AC-3: Kein bare kurzer Lucide-Alias ohne Icon-Suffix in frontend/src/
AC-4: sveltekit_best_practices.md enthält WIcon-Abgrenzungshinweis

Keine Mocks — greift direkt auf das Dateisystem zu.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
BEST_PRACTICES = REPO_ROOT / "docs" / "reference" / "sveltekit_best_practices.md"

# Kurze/mehrdeutige Icon-Namen, die das `Icon`-Suffix benötigen
AMBIGUOUS_ICONS = ["Pencil", "X", "Check", "Trash2", "Plus", "Upload", "Archive"]


def _grep_count(pattern: str, path: Path, include: str = "*.svelte") -> list[str]:
    """Gibt alle Treffer von grep zurück (Leerzeile = kein Treffer)."""
    result = subprocess.run(
        ["grep", "-rn", pattern, str(path), f"--include={include}"],
        capture_output=True,
        text=True,
    )
    lines = [l for l in result.stdout.splitlines() if l.strip()]
    return lines


# ---------------------------------------------------------------------------
# AC-2: PencilIcon — kein bare `import Pencil ` mehr
# ---------------------------------------------------------------------------

class TestAC2PencilIconAlias:
    """AC-2: Beide Svelte-Dateien mit „Bearbeiten"-Button verwenden PencilIcon."""

    def test_no_bare_pencil_import_in_frontend(self):
        """
        GIVEN: alle .svelte-Dateien unter frontend/src/
        WHEN:  grep auf `import Pencil ` (ohne Icon-Suffix)
        THEN:  0 Treffer — alle Pencil-Imports heißen PencilIcon
        """
        hits = _grep_count(r"import Pencil ", FRONTEND_SRC)
        assert hits == [], (
            f"Bare 'import Pencil' gefunden (sollte PencilIcon sein):\n"
            + "\n".join(hits)
        )

    def test_waypoint_card_uses_text_buttons_not_pencil_icon(self):
        """
        GIVEN: WaypointCard.svelte
        WHEN:  grep auf PencilIcon / grep auf Text-Button „Umbenennen"
        THEN:  Issue #522 ersetzte Icon-Buttons durch Text-Buttons →
               PencilIcon muss FEHLEN, „Umbenennen" muss vorhanden sein
        """
        waypointcard = FRONTEND_SRC / "lib/components/trip-detail/waypoints/WaypointCard.svelte"
        pencil_hits = _grep_count("PencilIcon", waypointcard, include="*.svelte")
        assert pencil_hits == [], (
            "PencilIcon darf seit Issue #522 nicht mehr in WaypointCard sein "
            "(Text-Buttons ersetzen Icon-Buttons):\n" + "\n".join(pencil_hits)
        )
        rename_hits = _grep_count("Umbenennen", waypointcard, include="*.svelte")
        assert rename_hits, "Text-Button 'Umbenennen' fehlt in WaypointCard.svelte (Issue #522)"

    def test_pencil_icon_alias_present_in_design_page(self):
        """
        GIVEN: _design/+page.svelte
        WHEN:  grep auf PencilIcon
        THEN:  mindestens 1 Treffer
        """
        design_page = FRONTEND_SRC / "routes/_design/+page.svelte"
        hits = _grep_count("PencilIcon", design_page, include="*.svelte")
        assert hits, "PencilIcon fehlt in _design/+page.svelte"


# ---------------------------------------------------------------------------
# AC-3: Kein bare kurzer Icon-Alias ohne Suffix in frontend/src/
# ---------------------------------------------------------------------------

class TestAC3NoAmbiguousBareImports:
    """AC-3: Alle kurzen/mehrdeutigen Lucide-Icons tragen das Icon-Suffix."""

    @pytest.mark.parametrize("icon_name", AMBIGUOUS_ICONS)
    def test_no_bare_import_for_ambiguous_icon(self, icon_name: str):
        """
        GIVEN: alle .svelte-Dateien unter frontend/src/
        WHEN:  grep auf `import <IconName> ` (bare, kein Icon-Suffix)
        THEN:  0 Treffer
        """
        pattern = rf"import {icon_name} "
        hits = _grep_count(pattern, FRONTEND_SRC)
        assert hits == [], (
            f"Bare 'import {icon_name}' gefunden (sollte {icon_name}Icon sein):\n"
            + "\n".join(hits)
        )

    def test_x_icon_alias_in_dialog_content(self):
        """
        GIVEN: dialog-content.svelte (Dialog-Schließen-Button)
        WHEN:  grep auf XIcon
        THEN:  mindestens 1 Treffer
        """
        dialog = FRONTEND_SRC / "lib/components/ui/dialog/dialog-content.svelte"
        hits = _grep_count("XIcon", dialog, include="*.svelte")
        assert hits, "XIcon fehlt in dialog-content.svelte"

    def test_trash2_icon_alias_in_stagerow(self):
        """
        GIVEN: StageRow.svelte
        WHEN:  grep auf Trash2Icon
        THEN:  mindestens 1 Treffer
        """
        stagerow = FRONTEND_SRC / "lib/components/trip-wizard/steps/StageRow.svelte"
        hits = _grep_count("Trash2Icon", stagerow, include="*.svelte")
        assert hits, "Trash2Icon fehlt in StageRow.svelte"

    def test_plus_icon_alias_in_step2stages(self):
        """
        GIVEN: Step2Stages.svelte
        WHEN:  grep auf PlusIcon
        THEN:  mindestens 1 Treffer
        """
        step2 = FRONTEND_SRC / "lib/components/trip-wizard/steps/Step2Stages.svelte"
        hits = _grep_count("PlusIcon", step2, include="*.svelte")
        assert hits, "PlusIcon fehlt in Step2Stages.svelte"

    def test_archive_icon_alias_in_bottomnav(self):
        """
        GIVEN: BottomNav.svelte
        WHEN:  grep auf ArchiveIcon
        THEN:  mindestens 1 Treffer
        """
        bottomnav = FRONTEND_SRC / "lib/components/ui/sidebar/BottomNav.svelte"
        hits = _grep_count("ArchiveIcon", bottomnav, include="*.svelte")
        assert hits, "ArchiveIcon fehlt in BottomNav.svelte"

    def test_x_icon_alias_in_topappbar(self):
        """
        GIVEN: TopAppBar.svelte
        WHEN:  grep auf XIcon
        THEN:  mindestens 1 Treffer
        """
        topappbar = FRONTEND_SRC / "lib/components/ui/sidebar/TopAppBar.svelte"
        hits = _grep_count("XIcon", topappbar, include="*.svelte")
        assert hits, "XIcon fehlt in TopAppBar.svelte"


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
