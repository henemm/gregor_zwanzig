"""
TDD RED tests for #98 PR 2: Aliase entfernen, Test-Imports umstellen.

Spec: docs/specs/modules/activity_profile.md §6.1, §7.3

Drei Test-Gruppen, die ALLE vor PR 2 fehlschlagen muessen:

1. TestAliasRemoved          — LocationActivityProfile in app.user existiert nicht mehr
2. TestProductionImports     — kein src/ oder api/ importiert LocationActivityProfile mehr
3. TestTestImports           — kein tests/ (ausser dieser Datei) importiert LocationActivityProfile mehr
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()


# =============================================================================
# Test 1: Alias in app.user ist entfernt
# =============================================================================

class TestAliasRemoved:
    """Nach PR 2 darf LocationActivityProfile in app.user nicht mehr existieren."""

    def test_import_raises(self):
        """
        GIVEN: PR 2 entfernt den Alias aus app.user
        WHEN: from app.user import LocationActivityProfile
        THEN: ImportError
        """
        with pytest.raises(ImportError):
            from app.user import LocationActivityProfile  # noqa: F401

    def test_canonical_still_works(self):
        """
        GIVEN: app.profile bleibt die Single Source of Truth
        WHEN: from app.profile import ActivityProfile
        THEN: import succeeds und Werte sind unveraendert
        """
        from app.profile import ActivityProfile

        assert ActivityProfile.WINTERSPORT.value == "wintersport"
        assert ActivityProfile.WANDERN.value == "wandern"
        assert ActivityProfile.SUMMER_TREKKING.value == "summer_trekking"
        assert ActivityProfile.ALLGEMEIN.value == "allgemein"


# =============================================================================
# Test 2: Production-Code nutzt nirgends mehr LocationActivityProfile
# =============================================================================

class TestProductionImports:
    """Kein src/, api/ oder scripts/ darf LocationActivityProfile noch nennen."""

    def _grep(self, *paths: str) -> list[str]:
        try:
            result = subprocess.run(
                ["grep", "-rn", "--include=*.py", "LocationActivityProfile", *paths],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except FileNotFoundError:
            pytest.skip("grep not available")
        if result.returncode not in (0, 1):
            pytest.fail(f"grep failed: {result.stderr}")
        lines = [l for l in result.stdout.splitlines() if l.strip()]
        return lines

    def test_no_references_in_src(self):
        """
        GIVEN: PR 2 hat alle Production-Verwendungen migriert
        WHEN: grep -rn LocationActivityProfile src/
        THEN: keine Treffer
        """
        hits = self._grep("src/")
        assert hits == [], f"Verbleibende Verwendungen in src/:\n" + "\n".join(hits)

    def test_no_references_in_api(self):
        """
        GIVEN: PR 2 hat alle API-Router migriert
        WHEN: grep -rn LocationActivityProfile api/
        THEN: keine Treffer
        """
        hits = self._grep("api/")
        assert hits == [], f"Verbleibende Verwendungen in api/:\n" + "\n".join(hits)


# =============================================================================
# Test 3: Test-Code nutzt nirgends mehr LocationActivityProfile (ausser hier)
# =============================================================================

class TestTestImports:
    """Bestehende Tests sind auf ActivityProfile umgestellt."""

    def test_no_references_in_tests(self):
        """
        GIVEN: PR 2 hat tests/ mechanisch migriert
        WHEN: grep -rn LocationActivityProfile tests/
        THEN: nur diese Datei selbst taucht auf
        """
        try:
            result = subprocess.run(
                ["grep", "-rln", "--include=*.py", "LocationActivityProfile", "tests/"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except FileNotFoundError:
            pytest.skip("grep not available")
        if result.returncode not in (0, 1):
            pytest.fail(f"grep failed: {result.stderr}")
        files = {l.strip() for l in result.stdout.splitlines() if l.strip()}
        rel_self = SELF.relative_to(REPO_ROOT).as_posix()
        forbidden = files - {rel_self}
        assert forbidden == set(), (
            "Verbleibende Test-Verwendungen (PR 2 nicht abgeschlossen):\n"
            + "\n".join(sorted(forbidden))
        )
