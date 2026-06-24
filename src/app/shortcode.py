"""Trip-Shortcode-Generierung — GZ#XXXX, pro Nutzer eindeutig (Bug #775)."""
from __future__ import annotations

import re

from app.loader import load_all_trips


def generate_shortcode(trip_name: str, user_id: str) -> str:
    """Leitet GZ#XXXX vom Trip-Namen ab, eindeutig pro Nutzer.

    Beispiel: "Hermannsweg mit Astrid 2026" → "GZ#HERM"
    Kollision: GZ#HERM → GZ#HERM2 → GZ#HERM3 usw.
    """
    base = re.sub(r"[^A-Z]", "", trip_name.upper())[:4] or "TRIP"
    existing = {t.shortcode for t in load_all_trips(user_id, include_archived=True) if t.shortcode}
    code = f"GZ#{base}"
    n = 2
    while code in existing:
        code = f"GZ#{base}{n}"
        n += 1
    return code
