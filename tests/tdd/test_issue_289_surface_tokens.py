"""
Issue #289: Keine undefinierten --g-surface / --g-surface-alt Token im Frontend.

Spec: docs/specs/modules/issue_289_surface_tokens.md
Test-Manifest: docs/specs/tests/issue_289_surface_tokens_tests.md

RED-Phase: Tests schlagen fehl, solange die Token noch vorhanden sind.
"""
import re
from pathlib import Path

FRONTEND_LIB = Path(__file__).parents[2] / "frontend" / "src" / "lib"


def _grep(pattern: str, directory: Path) -> list[tuple[Path, int, str]]:
    hits = []
    for path in directory.rglob("*.svelte"):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if re.search(pattern, line):
                hits.append((path, i, line.strip()))
    return hits


def test_no_undefined_g_surface_token():
    """AC-1: var(--g-surface ohne Suffix -0/-1/-2/-raised) → 0 Treffer."""
    hits = _grep(r"var\(--g-surface[^-0-9\)]", FRONTEND_LIB)
    details = "\n".join(f"  {p.relative_to(FRONTEND_LIB.parents[1])}:{n}: {l}" for p, n, l in hits)
    assert hits == [], f"Undefinierter --g-surface Token gefunden ({len(hits)} Stellen):\n{details}"


def test_no_g_surface_alt_token():
    """AC-2: var(--g-surface-alt) → 0 Treffer."""
    hits = _grep(r"var\(--g-surface-alt", FRONTEND_LIB)
    details = "\n".join(f"  {p.relative_to(FRONTEND_LIB.parents[1])}:{n}: {l}" for p, n, l in hits)
    assert hits == [], f"Undefinierter --g-surface-alt Token gefunden ({len(hits)} Stellen):\n{details}"


def test_metric_checkbox_uses_paper_token():
    """AC-3: MetricCheckbox nutzt --g-paper statt --g-surface für background + color."""
    path = FRONTEND_LIB / "components" / "trip-detail" / "MetricCheckbox.svelte"
    content = path.read_text(encoding="utf-8")
    assert "var(--g-paper)" in content, "MetricCheckbox: --g-paper nicht gefunden"
    assert "var(--g-surface, #fff)" not in content, "MetricCheckbox: undefinierter --g-surface noch vorhanden"


def test_preset_row_color_mix_uses_surface0():
    """AC-4: PresetRow color-mix nutzt --g-surface-0, kein Hex-Fallback."""
    path = FRONTEND_LIB / "components" / "trip-detail" / "PresetRow.svelte"
    content = path.read_text(encoding="utf-8")
    assert "var(--g-surface-0)" in content, "PresetRow: --g-surface-0 nicht gefunden"
    assert "var(--g-surface, #fff)" not in content, "PresetRow: undefinierter --g-surface noch vorhanden"
