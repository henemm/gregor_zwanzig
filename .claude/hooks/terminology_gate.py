#!/usr/bin/env python3
"""Stop-Hook: verbotene Produktbegriffe in der Antwort an den PO abfangen.

Das Produkt kennt "Trip", "Etappe", "Ortsvergleich" und "Briefing" — NICHT "Tour".
Der PO hat den Begriff dreimal korrigiert (2026-08-03 zweimal, 2026-08-04 erneut),
jedesmal lag die Merkregel im Kontext und hat nicht gewirkt. Deshalb prueft der Hook
die Antwort selbst, statt sich auf eine Vereinbarung zu verlassen.

Fail-open: jeder Fehler laesst die Antwort durch. Ein kaputter Hook darf die Sitzung
nicht blockieren.
"""

import json
import re
import sys

# "Tour"/"Touren" als eigenstaendiges Wort (faengt auch "Touren-Versand", da der
# Bindestrich eine Wortgrenze ist) plus die gaengigen Zusammenschreibungen.
# "Tourismus"/"Tournee" schlagen bewusst NICHT an.
FORBIDDEN = re.compile(
    r"\bTour(?:en)?\b|\bTouren(?:planer|plan|bericht|liste|uebersicht|übersicht)",
    re.IGNORECASE,
)

HINT = (
    "STOPP — verbotener Produktbegriff in deiner Antwort: {found}\n\n"
    "Das Produkt kennt keine 'Tour'. Korrekt sind: Trip · Etappe · Ortsvergleich · Briefing.\n"
    "Der PO hat das dreimal korrigiert. Formuliere die Antwort neu und sende sie erneut."
)


def last_assistant_text(transcript_path: str) -> str:
    """Text der juengsten Assistant-Antwort (alle Bloecke seit der letzten User-Zeile)."""
    with open(transcript_path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()

    chunks: list[str] = []
    for raw in reversed(lines):
        raw = raw.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        etype = entry.get("type")
        if etype == "user":
            break
        if etype != "assistant":
            continue
        content = (entry.get("message") or {}).get("content") or []
        if isinstance(content, str):
            chunks.append(content)
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                chunks.append(block.get("text") or "")
    return "\n".join(reversed(chunks))


def strip_quotes(text: str) -> str:
    """Zitierte Zeilen ausklammern — der PO darf den Begriff verwenden, ich nicht."""
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith(">"))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path")
        if not path:
            return 0
        text = strip_quotes(last_assistant_text(path))
    except Exception:
        return 0  # fail-open

    hits = FORBIDDEN.findall(text)
    matches = sorted({m.group(0) for m in FORBIDDEN.finditer(text)})
    if not hits:
        return 0

    print(HINT.format(found=", ".join(f"'{m}'" for m in matches)), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
