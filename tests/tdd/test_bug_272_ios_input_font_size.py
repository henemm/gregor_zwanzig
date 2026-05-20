"""
TDD RED Tests — Issue #272: iOS-Auto-Zoom bei Eingabefeldern mit font-size < 16 px

SPEC: docs/specs/modules/bug_272_ios_input_font_size.md

Hintergrund:
  iOS Safari zoomt automatisch ein, wenn ein fokussiertes <input>, <select> oder
  <textarea> eine font-size < 16 px hat. Das Frontend nutzt Tailwind text-sm (13 px)
  an zahlreichen Raw-Elementen.

Fix:
  1. Unlayered @media (max-width: 767px) in app.css — gewinnt über @layer utilities
  2. Scoped Override in SavePresetDialog.svelte — nötig wegen Spezifität 0-1-1

RED-Zustand (jetzt):
  Beide Regeln fehlen → alle Tests FAIL mit AssertionError.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

APP_CSS = REPO_ROOT / "frontend" / "src" / "app.css"
SAVE_PRESET_DIALOG = (
    REPO_ROOT
    / "frontend"
    / "src"
    / "lib"
    / "components"
    / "trip-detail"
    / "SavePresetDialog.svelte"
)


# ---------------------------------------------------------------------------
# Strukturelle Prüfung — Dateien existieren
# ---------------------------------------------------------------------------


def test_files_exist():
    """Beide zu ändernden Dateien müssen im Repository existieren."""
    assert APP_CSS.exists(), f"Datei nicht gefunden: {APP_CSS}"
    assert SAVE_PRESET_DIALOG.exists(), f"Datei nicht gefunden: {SAVE_PRESET_DIALOG}"


# ---------------------------------------------------------------------------
# AC-1 / AC-2 / AC-5 — Globale unlayered Regel in app.css
# ---------------------------------------------------------------------------


def test_ac1_app_css_contains_mobile_media_query():
    """
    GIVEN app.css ohne iOS-Fix
    WHEN  wir nach einer @media (max-width: 767px) Regel suchen
    THEN  die Regel muss existieren (sonst kein Fix)
    """
    css = APP_CSS.read_text()
    assert "@media (max-width: 767px)" in css, (
        "app.css enthält keine @media (max-width: 767px) Regel — iOS-Fix fehlt"
    )


def test_ac1_app_css_mobile_query_sets_input_font_size_16px():
    """
    GIVEN app.css mit Mobile-Media-Query
    WHEN  die Regel für input, select, textarea gelesen wird
    THEN  font-size muss exakt 16px sein (15px reicht für iOS nicht)
    """
    css = APP_CSS.read_text()
    # Suche den Block: @media (max-width: 767px) { ... input, select, textarea ... font-size: 16px ... }
    pattern = re.compile(
        r"@media\s*\(max-width:\s*767px\)[^{]*\{[^}]*"
        r"input\s*,\s*select\s*,\s*textarea[^{]*\{[^}]*font-size\s*:\s*16px",
        re.DOTALL,
    )
    assert pattern.search(css), (
        "app.css enthält keine Regel: @media (max-width: 767px) { input, select, textarea { font-size: 16px } }"
    )


def test_ac3_app_css_mobile_rule_is_unlayered():
    """
    GIVEN app.css mit Mobile-Media-Query
    WHEN  wir prüfen ob die Regel außerhalb aller @layer-Blöcke liegt
    THEN  die @media-Regel muss NACH dem letzten @layer-Vorkommen stehen

    Hintergrund: Unlayered CSS gewinnt in Tailwind v4 über alle @layer utilities-
    Regeln ohne !important. Die Regel muss nach allen @layer-Blöcken stehen.
    """
    css = APP_CSS.read_text()

    ios_fix_pos = css.find("@media (max-width: 767px)")
    assert ios_fix_pos != -1, (
        "app.css enthält keine @media (max-width: 767px) Regel"
    )

    last_layer_pos = css.rfind("@layer")
    assert ios_fix_pos > last_layer_pos, (
        f"iOS-Fix-Regel steht bei Position {ios_fix_pos}, "
        f"aber letztes @layer steht bei {last_layer_pos} — Regel liegt INNERHALB eines Layers"
    )


# ---------------------------------------------------------------------------
# AC-4 — Scoped Override in SavePresetDialog.svelte
# ---------------------------------------------------------------------------


def test_ac4_save_preset_dialog_has_mobile_textarea_override():
    """
    GIVEN SavePresetDialog.svelte mit Scoped CSS
    WHEN  .field textarea auf einem 375px-Viewport fokussiert wird
    THEN  muss die Scoped-Regel font-size: 16px auf Mobile setzen

    Hintergrund: .field textarea hat Spezifität 0-1-1 und übersteuert globale
    Regeln. Ein separater Scoped Override ist zwingend.
    """
    svelte = SAVE_PRESET_DIALOG.read_text()
    # Suche: @media (max-width: 767px) { .field textarea { font-size: 16px } }
    pattern = re.compile(
        r"@media\s*\(max-width:\s*767px\)[^{]*\{[^}]*"
        r"\.field\s+textarea[^{]*\{[^}]*font-size\s*:\s*16px",
        re.DOTALL,
    )
    assert pattern.search(svelte), (
        "SavePresetDialog.svelte enthält keinen Scoped Override: "
        "@media (max-width: 767px) { .field textarea { font-size: 16px } }"
    )
