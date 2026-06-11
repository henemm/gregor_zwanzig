"""
TDD tests for Issue #726 — portable Renderer-Pfade im Compliance-Test.

Der Compliance-Test in test_issue_623_trend_channels.py öffnete die Renderer-
Quelldateien über hartkodierte absolute Pfade auf einen fremden Worktree
(`idempotent-strolling-cray`) → FileNotFoundError in jedem anderen Worktree.

Diese Tests beweisen das Verhalten aus Sicht des Test-Laufs:
- AC-1: Die Renderer-Pfade lösen relativ zum aktuellen Repo auf und existieren.
- AC-2: Kein absoluter `.claude/worktrees/`-Pfad mehr im Quelltext (doc-compliance).
- AC-3: Die Schwellenwert-Erkennung bleibt wirksam (flaggt `wk > 30`).

IMPORTANT: NO mocks, NO patch, NO MagicMock. Real file/path operations only.
"""
from __future__ import annotations

from pathlib import Path

# Diese Symbole müssen vom Fix in test_issue_623_trend_channels.py auf
# Modulebene bereitgestellt werden (Refactor erzwungen durch RED).
from tests.tdd.test_issue_623_trend_channels import (  # noqa: E402
    _RENDERER_FILES,
    _THRESHOLD_BAD_PATTERNS,
    _scan_threshold_violations,
)


class TestIssue726PathPortability:
    """#726: Renderer-Pfade im Compliance-Test sind worktree-portabel."""

    def test_renderer_paths_resolve_in_current_repo(self):
        """AC-1: Alle Renderer-Pfade liegen im aktuellen Repo und existieren."""
        repo_root = Path(__file__).resolve().parents[2]
        assert _RENDERER_FILES, "Renderer-Pfadliste darf nicht leer sein"
        for p in _RENDERER_FILES:
            p = Path(p)
            assert p.is_absolute(), f"{p} sollte absolut (repo-relativ aufgelöst) sein"
            # Pfad muss unter dem aktuellen Repo-Root liegen, nicht unter Fremd-Worktree.
            assert repo_root in p.parents, f"{p} liegt nicht unter {repo_root}"
            assert p.exists(), f"Renderer-Datei fehlt: {p}"

    def test_no_hardcoded_worktree_path_in_source(self):
        """AC-2: Der Compliance-Test enthält keinen absoluten Worktree-Pfad mehr.

        # doc-compliance-test
        """
        src = (
            Path(__file__).resolve().parent / "test_issue_623_trend_channels.py"
        ).read_text()
        assert ".claude/worktrees/" not in src, (
            "Hartkodierter Worktree-Pfad weiterhin im Test vorhanden"
        )
        assert "idempotent-strolling-cray" not in src, (
            "Fremder Worktree-Name weiterhin im Test vorhanden"
        )

    def test_scanner_still_flags_threshold_violation(self, tmp_path):
        """AC-3: Die Bad-Pattern-Erkennung flaggt eine echte Schwellenwert-Verletzung."""
        bad = tmp_path / "fake_renderer.py"
        bad.write_text("def render(wk):\n    if wk > 30:\n        return 'orange'\n")
        violations = _scan_threshold_violations([bad])
        assert violations, "Scanner muss `wk > 30` als Verstoß erkennen"
        assert any("wk > 30" in v or "wk>30" in v for v in violations)

    def test_scanner_clean_file_has_no_violations(self, tmp_path):
        """AC-3 (Gegenprobe): Eine saubere Datei erzeugt keine Violations."""
        clean = tmp_path / "clean_renderer.py"
        clean.write_text("def render(tokens):\n    return tokens.wind\n")
        assert _scan_threshold_violations([clean]) == []

    def test_bad_pattern_list_unchanged(self):
        """AC-3: Die Bad-Pattern-Liste enthält weiterhin die fünf Kern-Schwellen."""
        assert len(_THRESHOLD_BAD_PATTERNS) == 5
