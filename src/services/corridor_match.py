"""Python-Port von corridorInside() — Single-Source-Match-Logik (C5).

Issue #1231, Slice 1. Verbatim portiert aus der JSX-Referenz
(claude-code-handoff/current/jsx/corridor-editor.jsx::corridorInside),
gebraucht vom Compare-Mail-Renderer (Slice 7, mark-Markierung). Muss mit
der TS-Fassung (frontend/src/lib/components/shared/corridor-editor/
corridorMatch.ts) und der Editor-Live-Vorschau identische Ergebnisse
liefern — siehe docs/specs/modules/issue_1231_korridor_editor.md AC-2.

NO MOCKS — reine Funktionslogik.
"""
from __future__ import annotations

from typing import Optional


def corridor_inside(
    value: Optional[float],
    min_bound: Optional[float],
    max_bound: Optional[float],
) -> Optional[bool]:
    """Liegt `value` im Korridor [min_bound, max_bound]?

    - `value is None` -> `None` (kein Messwert, neutral — C1).
    - `min_bound` gesetzt und `value < min_bound` -> `False` (unter dem Korridor).
    - `max_bound` gesetzt und `value > max_bound` -> `False` (über dem Korridor).
    - sonst -> `True` (im Korridor). Grenzwerte selbst zählen als "im
      Korridor" (< / > sind exklusiv geprüft, C2/C5).
    """
    if value is None:
        return None
    if min_bound is not None and value < min_bound:
        return False
    if max_bound is not None and value > max_bound:
        return False
    return True
