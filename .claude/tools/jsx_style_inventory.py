#!/usr/bin/env python3
"""
JSX Style Inventory — Anti-Drift Tool für Epic #575

Extrahiert ALLE Inline-Styles aus einer JSX-Vorlage und zeigt sie als
Checkliste. Der Developer Agent MUSS vor der Übernahme prüfen, ob jeder
Inline-Style in der Svelte-Version 1:1 erscheint.

Usage:
    python3 .claude/tools/jsx_style_inventory.py <jsx-file>
    python3 .claude/tools/jsx_style_inventory.py claude-code-handoff/current/jsx/screen-home.jsx
"""
import re
import sys
from pathlib import Path


def extract_styles(jsx_path: Path) -> list[dict]:
    """Extract all style={{...}} blocks from JSX file with line numbers."""
    content = jsx_path.read_text()
    lines = content.splitlines()

    entries = []
    style_re = re.compile(r"style=\{\{([^}]+(?:\}[^}]*)*)\}\}")
    for i, line in enumerate(lines, 1):
        for match in style_re.finditer(line):
            block = match.group(1).strip()
            entries.append({
                "line": i,
                "style": block,
                "context": line.strip()[:120],
            })

    return entries


def extract_text_content(jsx_path: Path) -> list[dict]:
    """Extract visible text content from JSX (between > and <)."""
    content = jsx_path.read_text()
    lines = content.splitlines()

    text_re = re.compile(r">([A-ZÄÖÜa-zäöüß][^<>\{\}]{2,})<")
    entries = []
    for i, line in enumerate(lines, 1):
        for match in text_re.finditer(line):
            text = match.group(1).strip()
            if text and not text.startswith(("http", "/", "{")):
                entries.append({
                    "line": i,
                    "text": text,
                })
    return entries


def extract_mock_fields(jsx_path: Path) -> list[str]:
    """Extract field accesses like sub.region, trip.profileLabel."""
    content = jsx_path.read_text()
    # Pattern: identifier.field where identifier is lowercase
    field_re = re.compile(r"\b([a-z]\w*)\.(\w+)")
    fields = set()
    for m in field_re.finditer(content):
        obj, field = m.group(1), m.group(2)
        if obj in ("console", "Math", "window", "document", "React", "Object", "Array", "JSON", "string", "number"):
            continue
        fields.add(f"{obj}.{field}")
    return sorted(fields)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: jsx_style_inventory.py <jsx-file>", file=sys.stderr)
        sys.exit(2)

    jsx_path = Path(sys.argv[1])
    if not jsx_path.exists():
        print(f"ERROR: {jsx_path} not found", file=sys.stderr)
        sys.exit(2)

    styles = extract_styles(jsx_path)
    texts = extract_text_content(jsx_path)
    fields = extract_mock_fields(jsx_path)

    print(f"=== JSX Style Inventory: {jsx_path.name} ===\n")

    print(f"## Inline-Styles ({len(styles)}) — MÜSSEN 1:1 in Svelte erscheinen\n")
    for s in styles:
        print(f"- [ ] Line {s['line']}: `style={{{{ {s['style']} }}}}`")
        print(f"      Context: `{s['context']}`")
    print()

    print(f"## Sichtbarer Text ({len(texts)}) — Wortlaut prüfen\n")
    for t in texts[:40]:
        print(f"- Line {t['line']}: \"{t['text']}\"")
    if len(texts) > 40:
        print(f"  ... + {len(texts) - 40} mehr")
    print()

    print(f"## Mock-Felder ({len(fields)}) — Backend-Pre-Check\n")
    print("Diese Felder werden im JSX-Mock referenziert. Falls sie im TypeScript-Modell")
    print("FEHLEN, MUSS das Backend erweitert werden, BEVOR das UI gebaut wird.\n")
    for f in fields:
        print(f"- {f}")
    print()

    print("## Übernahme-Checkliste\n")
    print("- [ ] Alle Inline-Styles 1:1 als `style=\"\"` oder `style:` übernommen")
    print("- [ ] Keine Inline-Styles in Tailwind/CSS-Klassen übersetzt")
    print("- [ ] Sichtbarer Text wortgleich übernommen")
    print("- [ ] Mock-Felder gegen TypeScript-Modell gediffed")
    print("- [ ] Keine erfundenen Conditional-States (Loading, Empty, Fallback)")
    print("- [ ] Keine Re-Architektur in Sub-Komponenten während Übernahme")


if __name__ == "__main__":
    main()
