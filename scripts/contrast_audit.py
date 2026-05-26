#!/usr/bin/env python3
"""Contrast-Audit der Ink-Skala (WCAG-AA auf weisser Card) — Issue #377.

Reproduzierbares Mess-Werkzeug ohne externe Dependencies. Berechnet die
relative Luminanz nach WCAG 2.1 (Anhang) und das Kontrastverhaeltnis aller
Design-Tokens gegenueber den drei produktiven Hintergruenden.

Ausfuehrung:
    python3 scripts/contrast_audit.py
"""

# Token-Werte: Single Source of Truth ist frontend/src/app.css; hier gespiegelt
# fuer das Audit (15 als Textfarbe verwendete Tokens).
TOKENS: dict[str, str] = {
    "--g-ink": "#1a1a18",
    "--g-ink-2": "#45433d",
    "--g-ink-3": "#6b675c",
    "--g-ink-muted": "#5c5a52",
    "--g-ink-4": "#9a958a",
    "--g-ink-faint": "#9c9a90",
    "--g-accent": "#c45a2a",
    "--g-accent-deep": "#8c3e1a",
    "--g-good": "#3d6b3a",
    "--g-warn": "#c08a1a",
    "--g-warning": "#c8882a",
    "--g-bad": "#a83232",
    "--g-danger": "#b33a2a",
    "--g-info": "#2a6cb3",
    "--g-success": "#3a7d44",
}

# Produktive Hintergruende (app.css): card / card-alt / paper.
BACKGROUNDS: dict[str, str] = {
    "card #ffffff": "#ffffff",
    "card-alt #faf8f1": "#faf8f1",
    "paper #f6f4ee": "#f6f4ee",
}


def _linearize(c: float) -> float:
    """sRGB-Kanal -> linear (WCAG 2.1 Anhang)."""
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    """Hex-Farbe (#rrggbb) -> relative Luminanz [0..1]."""
    r, g, b = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)


def contrast_ratio(fg: str, bg: str) -> float:
    """Kontrastverhaeltnis zweier Farben (immer >= 1.0)."""
    l1, l2 = relative_luminance(fg), relative_luminance(bg)
    bright, dark = max(l1, l2), min(l1, l2)
    return (bright + 0.05) / (dark + 0.05)


def classify(ratio: float) -> str:
    """Ratio -> WCAG-Freigabe-Klasse."""
    if ratio >= 7:
        return "AAA-text"
    if ratio >= 4.5:
        return "AA-text"
    if ratio >= 3:
        return "AA-large"
    return "FAIL"


def main() -> None:
    """Druckt eine Markdown-Tabelle aller Tokens x Hintergruende."""
    bg_names = list(BACKGROUNDS)
    header = "| Token | Wert | " + " | ".join(bg_names) + " |"
    sep = "|" + "---|" * (2 + len(bg_names))
    print(header)
    print(sep)
    for token, hex_val in TOKENS.items():
        cells = []
        for bg_hex in BACKGROUNDS.values():
            ratio = contrast_ratio(hex_val, bg_hex)
            cells.append(f"{ratio:.2f} ({classify(ratio)})")
        print(f"| `{token}` | {hex_val} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
