"""
TDD RED Tests — Bug #328: Hardcodierte font-sizes + Hex-Farben in SavePresetDialog.svelte

SPEC: docs/specs/modules/bug_328_savepreset_tokens.md
TEST-MANIFEST: docs/specs/tests/bug_328_savepreset_tokens_tests.md

Hintergrund:
  SavePresetDialog.svelte enthält im <style>-Block 7 hardcodierte font-size-Werte
  (AP-010) und 2 Inline-Hex-Farben (AP-007). Diese werden auf Design-Tokens gemappt:
    0.8125rem -> var(--g-text-xs)   0.875rem -> var(--g-text-sm)
    #dc2626   -> var(--g-danger)    #fff     -> var(--g-paper)

  AUSNAHME: Die font-size: 16px im @media (max-width: 767px)-Block ist der iOS-Zoom-
  Schutz aus Bug #272 und bleibt EXAKT 16px (--g-text-md ist nur 15px, würde Auto-Zoom
  reaktivieren). Sie erhält stattdessen einen erklärenden Kommentar.

RED-Zustand (jetzt):
  Noch 7 hardcodierte font-sizes + 2 Hex-Farben vorhanden, keine Tokens -> Kern-Tests FAIL.

Echte Datei wird gelesen, keine Mocks.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

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
# Strukturelle Prüfung
# ---------------------------------------------------------------------------


def test_file_exists():
    """Die zu ändernde Datei muss im Repository existieren."""
    assert SAVE_PRESET_DIALOG.exists(), f"Datei nicht gefunden: {SAVE_PRESET_DIALOG}"


# ---------------------------------------------------------------------------
# AC-1 — keine hardcodierten font-sizes außer dem iOS-Zoom-Guard
# ---------------------------------------------------------------------------


def test_ac1_only_ios_guard_font_size_remains():
    """
    GIVEN SavePresetDialog.svelte
    WHEN  man alle `font-size: <ziffer>` Deklarationen sammelt
    THEN  bleibt genau ein hardcodierter Wert — die iOS-Guard-Regel mit 16px
    """
    content = SAVE_PRESET_DIALOG.read_text()
    hardcoded = re.findall(r"font-size:\s*([0-9][^;\n]*)", content)
    assert len(hardcoded) == 1, (
        f"Erwartet genau 1 hardcodierte font-size (iOS-Guard 16px), "
        f"gefunden {len(hardcoded)}: {hardcoded}"
    )
    assert hardcoded[0].strip() == "16px", (
        f"Die verbleibende hardcodierte font-size muss 16px (iOS-Guard) sein, "
        f"ist aber: {hardcoded[0]!r}"
    )


def test_ac1_ios_guard_has_explanatory_comment():
    """
    GIVEN die verbleibende 16px-Regel (iOS-Zoom-Schutz)
    WHEN  man den umgebenden <style>-Block prüft
    THEN  muss ein erklärender Kommentar mit Verweis auf den iOS-Zoom-Guard / #272 vorhanden sein
    """
    content = SAVE_PRESET_DIALOG.read_text().lower()
    assert "ios" in content and ("zoom" in content or "272" in content), (
        "Kein erklärender iOS-Zoom-Guard-Kommentar (Verweis auf iOS-Zoom bzw. #272) gefunden — "
        "die 16px-Ausnahme muss begründet sein, damit sie nicht versehentlich 'aufgeräumt' wird."
    )


def test_ac1_uses_text_size_tokens():
    """
    GIVEN SavePresetDialog.svelte nach Tokenisierung
    WHEN  man nach font-size-Token-Nutzung sucht
    THEN  müssen --g-text-xs und --g-text-sm verwendet werden
    """
    content = SAVE_PRESET_DIALOG.read_text()
    assert "var(--g-text-xs)" in content, "font-size-Token --g-text-xs fehlt (für 0.8125rem-Stellen)"
    assert "var(--g-text-sm)" in content, "font-size-Token --g-text-sm fehlt (für 0.875rem-Stellen)"


# ---------------------------------------------------------------------------
# AC-2 — keine Inline-Hex-Farben mehr
# ---------------------------------------------------------------------------


def test_ac2_no_inline_hex_colors():
    """
    GIVEN SavePresetDialog.svelte
    WHEN  man nach `color: #...` Hex-Literalen sucht
    THEN  darf es keine Treffer mehr geben
    """
    content = SAVE_PRESET_DIALOG.read_text()
    hex_colors = re.findall(r"color:\s*#[0-9a-fA-F]{3,8}", content)
    assert hex_colors == [], (
        f"Inline-Hex-Farben gefunden (AP-007-Verstoß): {hex_colors} — "
        f"müssen durch var(--g-danger) bzw. var(--g-paper) ersetzt werden."
    )


def test_ac2_uses_color_tokens():
    """
    GIVEN SavePresetDialog.svelte nach Tokenisierung
    WHEN  man nach den erwarteten Farb-Tokens sucht
    THEN  müssen --g-danger (Fehler-Rot) und --g-paper (Button-Schrift) verwendet werden
    """
    content = SAVE_PRESET_DIALOG.read_text()
    assert "var(--g-danger)" in content, "Farb-Token --g-danger fehlt (Ersatz für #dc2626)"
    assert "var(--g-paper)" in content, "Farb-Token --g-paper fehlt (Ersatz für #fff)"


# ---------------------------------------------------------------------------
# AC-3 / Regressions-Guard — iOS-Zoom-Schutz aus Bug #272 bleibt intakt
# ---------------------------------------------------------------------------


def test_ios_zoom_guard_media_query_intact():
    """
    GIVEN der iOS-Zoom-Schutz aus Bug #272
    WHEN  man die @media (max-width: 767px)-Regel prüft
    THEN  muss .field input/textarea weiterhin auf exakt 16px gesetzt werden

    Dieser Test ist auch im RED-Zustand grün — er sichert ab, dass die
    Tokenisierung den bestehenden iOS-Schutz NICHT bricht.
    """
    content = SAVE_PRESET_DIALOG.read_text()
    pattern = re.compile(
        r"@media\s*\(max-width:\s*767px\)[^{]*\{[^}]*"
        r"\.field[^{]*\{[^}]*font-size\s*:\s*16px",
        re.DOTALL,
    )
    assert pattern.search(content), (
        "iOS-Zoom-Guard (#272) verloren: @media (max-width: 767px) { .field ... { font-size: 16px } } fehlt"
    )
