"""
TDD RED Tests — Bug #382: Select.svelte iOS-Auto-Zoom (latente #272-Regression)

SPEC: docs/specs/modules/bug_382_select_ios_zoom.md

Hintergrund:
  Select.svelte setzt font-size: var(--g-text-sm) (= 13px) auf .gz-select select
  mit CSS-Spezifität (0,1,1). Der globale iOS-Safari-Auto-Zoom-Guard in app.css
  (Bug #272) hat nur Spezifität (0,0,1) und verliert — alle 14 Einsatzorte der
  Komponente lösen beim Fokus auf iOS den ungewollten Viewport-Zoom aus.

Fix:
  Scoped @media (max-width: 767px) Block in Select.svelte — identisches Muster
  wie SavePresetDialog.svelte (Z. 337–342, fix aus #272).

RED-Zustand (jetzt):
  Select.svelte hat keinen @media-Override → ac3/ac1 FAIL.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SELECT_SVELTE = (
    REPO_ROOT / "frontend" / "src" / "lib" / "components" / "ui" / "select" / "Select.svelte"
)


# ---------------------------------------------------------------------------
# Strukturelle Prüfung
# ---------------------------------------------------------------------------


def test_select_svelte_exists():
    """Select.svelte muss im Repository existieren."""
    assert SELECT_SVELTE.exists(), f"Datei nicht gefunden: {SELECT_SVELTE}"


# ---------------------------------------------------------------------------
# AC-3 — Select.svelte enthält scoped @media-Override
# ---------------------------------------------------------------------------


def test_ac3_select_svelte_has_mobile_media_query():
    """
    GIVEN: Select.svelte ohne iOS-Fix
    WHEN:  der <style>-Block nach einem @media (max-width: 767px)-Block durchsucht wird
    THEN:  der Block muss vorhanden sein — sonst greift der Guard nicht

    RED: Derzeit kein @media-Block in Select.svelte vorhanden.
    """
    content = SELECT_SVELTE.read_text()
    assert "@media (max-width: 767px)" in content, (
        "Select.svelte enthält keinen @media (max-width: 767px)-Block — "
        "iOS-Auto-Zoom-Guard (#272/#382) fehlt"
    )


def test_ac3_select_svelte_mobile_query_sets_font_size_16px():
    """
    GIVEN: Select.svelte mit @media-Block
    WHEN:  die Regel .gz-select select innerhalb des Blocks gelesen wird
    THEN:  font-size muss exakt 16px sein (< 16px löst iOS-Zoom aus)

    RED: Derzeit kein @media-Block in Select.svelte vorhanden.
    """
    content = SELECT_SVELTE.read_text()
    pattern = re.compile(
        r"@media\s*\(max-width:\s*767px\)[^{]*\{.*?"
        r"\.gz-select\s+select[^{]*\{[^}]*font-size\s*:\s*16px",
        re.DOTALL,
    )
    assert pattern.search(content), (
        "Select.svelte enthält keinen scoped Override: "
        "@media (max-width: 767px) { .gz-select select { font-size: 16px } } — "
        "iOS-Auto-Zoom für alle 14 Select-Einsatzorte nicht behoben"
    )


# ---------------------------------------------------------------------------
# AC-2 — Desktop unverändert (Basisregel bleibt)
# ---------------------------------------------------------------------------


def test_ac2_base_font_size_preserved():
    """
    GIVEN: Select.svelte nach dem Fix
    WHEN:  die Basisregel .gz-select select gelesen wird
    THEN:  font-size: var(--g-text-sm) muss weiterhin vorhanden sein
           (Desktop-Darstellung darf nicht zurückgesetzt werden)
    """
    content = SELECT_SVELTE.read_text()
    assert "font-size: var(--g-text-sm)" in content, (
        "Select.svelte enthält keine Basisregel font-size: var(--g-text-sm) mehr — "
        "Desktop-Darstellung würde auf Browser-Default fallen"
    )


# ---------------------------------------------------------------------------
# AC-1 — Scoped Override hat höhere Effektiv-Spezifität als Basisregel
# ---------------------------------------------------------------------------


def test_ac1_mobile_override_comes_after_base_rule():
    """
    GIVEN: Select.svelte mit Basisregel und @media-Override
    WHEN:  die Quelltextpositionen der beiden Regeln verglichen werden
    THEN:  der @media-Block muss NACH der .gz-select select Basisregel stehen
           (gleiche Spezifität → Quelltextreihenfolge entscheidet, spätere Regel gewinnt)

    RED: Derzeit kein @media-Block vorhanden, test_ac3_* schlägt bereits fehl.
    """
    content = SELECT_SVELTE.read_text()
    base_pos = content.find("font-size: var(--g-text-sm)")
    media_pos = content.find("@media (max-width: 767px)")

    assert base_pos != -1, "Basisregel font-size: var(--g-text-sm) fehlt"
    assert media_pos != -1, "@media-Block fehlt"
    assert media_pos > base_pos, (
        f"@media-Block (Position {media_pos}) steht vor der Basisregel "
        f"(Position {base_pos}) — Mobile-Override verliert den Quelltextvergleich"
    )
