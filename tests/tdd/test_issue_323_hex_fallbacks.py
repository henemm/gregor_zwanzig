"""
TDD RED: Issue #323 — AP-007 Restdrift: Hex-Fallbacks bereinigen

Tests prüfen, dass keine Hex-Farbliterale mehr in SmsPhoneFrame.svelte
und profileSignature.ts enthalten sind, und dass accentFallback vollständig
entfernt wurde.

Regex filtert Issue-Nummern in Kommentaren heraus — geprüft werden nur
echte CSS-Farbwerte (im <style>-Block) bzw. TS-Werte (nicht Kommentarzeilen).
"""
import re
from pathlib import Path

HEX_PATTERN = re.compile(r'#[0-9a-fA-F]{3,6}(?![0-9a-fA-F])')

ROOT = Path(__file__).parents[2]
SMS_FRAME = ROOT / "frontend/src/lib/components/preview/SmsPhoneFrame.svelte"
PROFILE_SIG_TS = ROOT / "frontend/src/lib/utils/profileSignature.ts"
DESIGN_PAGE = ROOT / "frontend/src/routes/_design/+page.svelte"


def _css_hex_lines(svelte_path: Path) -> list[str]:
    """Gibt Zeilen mit Hex-Literalen im <style>-Block zurück (keine Kommentare)."""
    content = svelte_path.read_text()
    style_match = re.search(r'<style[^>]*>(.*?)</style>', content, re.DOTALL)
    if not style_match:
        return []
    style_content = style_match.group(1)
    start_line = content[: style_match.start(1)].count('\n') + 1
    hits = []
    for i, line in enumerate(style_content.splitlines(), start_line):
        stripped = line.strip()
        if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
            continue
        if HEX_PATTERN.search(line):
            hits.append(f"Z.{i}: {stripped}")
    return hits


def _ts_hex_lines(ts_path: Path) -> list[str]:
    """Gibt Zeilen mit Hex-Literalen in einer TS-Datei zurück (keine Kommentare)."""
    hits = []
    for i, line in enumerate(ts_path.read_text().splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
            continue
        if HEX_PATTERN.search(line):
            hits.append(f"Z.{i}: {stripped}")
    return hits


def test_smsphoneframe_no_hex_literals():
    """
    GIVEN: SmsPhoneFrame.svelte nach dem Fix
    WHEN: Hex-Scan des <style>-Blocks (keine Kommentarzeilen)
    THEN: 0 Treffer
    """
    hits = _css_hex_lines(SMS_FRAME)
    assert hits == [], f"Noch {len(hits)} Hex-Literal(e) in SmsPhoneFrame.svelte <style>:\n" + "\n".join(hits)


def test_profile_signature_no_hex_literals():
    """
    GIVEN: profileSignature.ts nach dem Fix
    WHEN: Hex-Scan (keine Kommentarzeilen)
    THEN: 0 Treffer
    """
    hits = _ts_hex_lines(PROFILE_SIG_TS)
    assert hits == [], f"Noch {len(hits)} Hex-Literal(e) in profileSignature.ts:\n" + "\n".join(hits)


def test_accent_fallback_field_removed_from_type():
    """
    GIVEN: profileSignature.ts nach dem Fix
    WHEN: Suche nach 'accentFallback'
    THEN: Keine Vorkommen (Feld aus Interface + SIGNATURES entfernt)
    """
    content = PROFILE_SIG_TS.read_text()
    count = content.count("accentFallback")
    assert count == 0, f"'accentFallback' noch {count}× in profileSignature.ts vorhanden"


def test_accent_fallback_not_used_in_design_page():
    """
    GIVEN: _design/+page.svelte nach dem Fix
    WHEN: Suche nach 'accentFallback'
    THEN: Keine Vorkommen (Z.158 wurde entfernt)
    """
    content = DESIGN_PAGE.read_text()
    count = content.count("accentFallback")
    assert count == 0, f"'accentFallback' noch {count}× in _design/+page.svelte vorhanden"


def test_accent_fallback_not_used_in_any_productive_component():
    """
    GIVEN: Alle .svelte-Dateien in frontend/src/ (außer _design)
    WHEN: Suche nach 'accentFallback'
    THEN: Keine produktive Komponente nutzt accentFallback
    """
    svelte_dir = ROOT / "frontend/src"
    matches = []
    for f in svelte_dir.rglob("*.svelte"):
        if "_design" in str(f):
            continue
        if "accentFallback" in f.read_text():
            matches.append(str(f.relative_to(ROOT)))
    assert matches == [], "accentFallback noch in produktiven Komponenten:\n" + "\n".join(matches)
