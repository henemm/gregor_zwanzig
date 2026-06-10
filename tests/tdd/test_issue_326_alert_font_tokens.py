"""
TDD RED: Issue #326 — AP-017 (Schrift-Skala) + AP-008 (Spacing) in Alert-Karten

Tests prüfen, dass AlertQuietHoursCard.svelte und AlertCooldownCard.svelte
keine hardcodierten font-size-, padding-, margin-, gap- und border-radius-Werte
mehr im <style>-Block haben — alle Werte müssen über --g-text-*, --g-s-* bzw.
--g-radius-* Tokens kommen. Zusätzlich: tote .toggle-label-Regel entfernt.

Erkennung: Zahl + Längeneinheit (rem/px/em). Bare `0` (z. B. `margin: 0 0 var()`)
und Token-Referenzen (`var(--g-s-4)`) lösen KEINEN Treffer aus.
Bewusst NICHT geprüft (semantisch erlaubt, AP-008): min-height, width, border (1px).

Test-Manifest: docs/specs/tests/issue_326_alert_font_tokens_tests.md
"""
import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
QUIET = ROOT / "frontend/src/lib/components/alerts-tab/AlertQuietHoursCard.svelte"
COOLDOWN = ROOT / "frontend/src/lib/components/alerts-tab/AlertCooldownCard.svelte"

# Zahl mit Längeneinheit innerhalb eines bestimmten Property-Werts (bis zum ; oder })
LENGTH = r'\d*\.?\d+(?:rem|px|em)\b'
FONT_SIZE_RE = re.compile(rf'font-size\s*:[^;{{}}]*{LENGTH}')
SPACING_RE = re.compile(rf'\b(?:padding|margin|gap|border-radius)\s*:[^;{{}}]*{LENGTH}')


def _style_lines(svelte_path: Path):
    """(Zeilennummer, Inhalt) der <style>-Block-Zeilen, ohne Kommentarzeilen."""
    content = svelte_path.read_text()
    m = re.search(r'<style[^>]*>(.*?)</style>', content, re.DOTALL)
    if not m:
        return []
    start_line = content[: m.start(1)].count('\n') + 1
    out = []
    for i, line in enumerate(m.group(1).splitlines(), start_line):
        stripped = line.strip()
        if stripped.startswith(('//', '/*', '*')):
            continue
        out.append((i, line))
    return out


def _hits(svelte_path: Path, pattern: re.Pattern):
    return [f"Z.{i}: {line.strip()}" for i, line in _style_lines(svelte_path)
            if pattern.search(line)]


# --- AC-1 / AC-2: keine hardcodierten font-size ---

def test_quiet_hours_no_hardcoded_font_size():
    """
    GIVEN: AlertQuietHoursCard.svelte nach dem Fix
    WHEN: Scan des <style>-Blocks auf font-size mit Zahl+Einheit
    THEN: Hoechstens 1 Treffer (iOS-Guard: font-size 16px verhindert Auto-Zoom)
    """
    hits = _hits(QUIET, FONT_SIZE_RE)
    ios_guard = [h for h in hits if "16px" in h]
    non_ios = [h for h in hits if "16px" not in h]
    assert non_ios == [], "Hardcodierte font-size (non-iOS) in AlertQuietHoursCard.svelte: " + ", ".join(non_ios)
    assert len(ios_guard) <= 1, "Mehr als 1 iOS-Guard font-size in AlertQuietHoursCard.svelte: " + ", ".join(ios_guard)

def test_cooldown_no_hardcoded_font_size():
    """
    GIVEN: AlertCooldownCard.svelte nach dem Fix
    WHEN: Scan des <style>-Blocks auf font-size mit Zahl+Einheit
    THEN: Hoechstens 1 Treffer (iOS-Guard: font-size 16px verhindert Auto-Zoom)
    """
    hits = _hits(COOLDOWN, FONT_SIZE_RE)
    ios_guard = [h for h in hits if "16px" in h]
    non_ios = [h for h in hits if "16px" not in h]
    assert non_ios == [], "Hardcodierte font-size (non-iOS) in AlertCooldownCard.svelte: " + ", ".join(non_ios)
    assert len(ios_guard) <= 1, "Mehr als 1 iOS-Guard font-size in AlertCooldownCard.svelte: " + ", ".join(ios_guard)

# --- AC-3: keine hardcodierten Spacing-/Radius-Werte ---

def test_quiet_hours_no_hardcoded_spacing():
    """
    GIVEN: AlertQuietHoursCard.svelte nach dem Fix
    WHEN: Scan auf padding/margin/gap/border-radius mit Zahl+Einheit
    THEN: 0 Treffer (alle via --g-s-* / --g-radius-*; min-height/width/border bleiben)
    """
    hits = _hits(QUIET, SPACING_RE)
    assert hits == [], "Hardcodiertes Spacing/Radius in AlertQuietHoursCard.svelte:\n" + "\n".join(hits)


def test_cooldown_no_hardcoded_spacing():
    """
    GIVEN: AlertCooldownCard.svelte nach dem Fix
    WHEN: Scan auf padding/margin/gap/border-radius mit Zahl+Einheit
    THEN: 0 Treffer (alle via --g-s-* / --g-radius-*; min-height/width/border bleiben)
    """
    hits = _hits(COOLDOWN, SPACING_RE)
    assert hits == [], "Hardcodiertes Spacing/Radius in AlertCooldownCard.svelte:\n" + "\n".join(hits)


# --- AC-4: tote .toggle-label-Regel entfernt ---

def test_quiet_hours_dead_toggle_label_removed():
    """
    GIVEN: AlertQuietHoursCard.svelte nach dem Fix
    WHEN: Suche nach 'toggle-label' (Markup + Style)
    THEN: 0 Vorkommen — tote, ungenutzte Regel ist entfernt
    """
    count = QUIET.read_text().count("toggle-label")
    assert count == 0, f"'toggle-label' noch {count}x in AlertQuietHoursCard.svelte (tote Regel)"


# --- Positiv-Checks: Ersetzung statt Löschung ---

def test_quiet_hours_uses_text_tokens():
    """
    GIVEN: AlertQuietHoursCard.svelte nach dem Fix
    WHEN: Suche nach Typografie-Tokens
    THEN: Beide eingesetzten Tokens kommen vor (font-size wurde ersetzt, nicht entfernt)
    """
    content = QUIET.read_text()
    assert "var(--g-text-sm)" in content, "--g-text-sm fehlt in AlertQuietHoursCard.svelte"
    assert "var(--g-text-xs)" in content, "--g-text-xs fehlt in AlertQuietHoursCard.svelte"


def test_cooldown_uses_text_tokens():
    """
    GIVEN: AlertCooldownCard.svelte nach dem Fix
    WHEN: Suche nach Typografie-Tokens
    THEN: Beide eingesetzten Tokens kommen vor (font-size wurde ersetzt, nicht entfernt)
    """
    content = COOLDOWN.read_text()
    assert "var(--g-text-sm)" in content, "--g-text-sm fehlt in AlertCooldownCard.svelte"
    assert "var(--g-text-xs)" in content, "--g-text-xs fehlt in AlertCooldownCard.svelte"
