"""
TDD RED: Bug #330 — AP-017 Schrift-Skala-Drift: hardcodierte font-sizes in ModeCard.svelte

Tests prüfen, dass im <style>-Block von ModeCard.svelte keine numerischen
font-size-Literale mehr stehen (AC-1) und dass stattdessen genau die fünf
erwarteten --g-text-* Tokens referenziert werden (AC-2).

Kein Mock — die echte Quelldatei wird gelesen. Kommentarzeilen werden gefiltert.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
MODE_CARD = ROOT / "frontend/src/lib/components/alert-rules-editor/ModeCard.svelte"

# Numerisches font-size-Literal: font-size: <ziffer>...  (rem/px/em/% etc.)
FONT_SIZE_LITERAL = re.compile(r'font-size:\s*[0-9]')
# Token-Referenz: font-size: var(--g-text-XYZ)
FONT_SIZE_TOKEN = re.compile(r'font-size:\s*var\(\s*(--g-text-[a-z0-9]+)')


def _style_lines(svelte_path: Path) -> list[tuple[int, str]]:
    """(Zeilennummer, Inhalt) der <style>-Zeilen ohne reine Kommentarzeilen."""
    content = svelte_path.read_text()
    style_match = re.search(r'<style[^>]*>(.*?)</style>', content, re.DOTALL)
    if not style_match:
        return []
    style_content = style_match.group(1)
    start_line = content[: style_match.start(1)].count('\n') + 1
    out = []
    for i, line in enumerate(style_content.splitlines(), start_line):
        stripped = line.strip()
        if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
            continue
        out.append((i, line))
    return out


def test_no_hardcoded_font_sizes():
    """
    GIVEN: ModeCard.svelte <style>-Block
    WHEN: nach numerischen font-size-Literalen gesucht wird (font-size:\\s*[0-9])
    THEN: 0 Treffer (alle Werte sind tokenisiert)
    """
    hits = [f"Z.{i}: {line.strip()}" for i, line in _style_lines(MODE_CARD)
            if FONT_SIZE_LITERAL.search(line)]
    assert hits == [], (
        f"Noch {len(hits)} hardcodierte font-size(s) in ModeCard.svelte:\n"
        + "\n".join(hits)
    )


def test_font_sizes_use_correct_tokens():
    """
    GIVEN: ModeCard.svelte <style>-Block
    WHEN: alle font-size: var(--g-text-*) Token-Referenzen gesammelt werden
    THEN: genau 5 Referenzen mit Verteilung --g-text-xs×3, --g-text-sm×1, --g-text-md×1
    """
    tokens = []
    for _, line in _style_lines(MODE_CARD):
        m = FONT_SIZE_TOKEN.search(line)
        if m:
            tokens.append(m.group(1))
    counts = {t: tokens.count(t) for t in set(tokens)}
    expected = {"--g-text-xs": 3, "--g-text-sm": 1, "--g-text-md": 1}
    assert counts == expected, (
        f"Erwartet {expected}, gefunden {counts} "
        f"(insgesamt {len(tokens)} font-size-Token-Referenzen)"
    )
