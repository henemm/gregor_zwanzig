# doc-compliance-test
"""TDD RED — Issue #3022: Orts-Vergleich, Reiter Zustellung/Wetter im Zustand ``laedt``.

Spec: docs/specs/modules/fix_3022_zustellung_laedt.md (AC-5).
Daten: docs/context/einstellungen_neu/elementliste_besitzer.json (gelesen vom Elementlisten-Abgleich,
frontend/e2e/elementliste_abgleich_logik.ts). Geprüft wird der Dateninhalt, nicht Quelltext.

Die 62 Besitzer-Einträge mit Verweis ``#3022`` (59 ``orte.zustellung.laedt.*``, 3 ``orte.wetter.laedt.*``)
haben die Abweichung „Reiter bleibt leer, solange der Katalog hängt“ verdeckt. Nach dem Fix zeigen die
Reiter ihren Inhalt sofort; die Einträge müssen raus, sonst bleiben sie als verwaiste Besitzer stehen bzw.
verdecken eine erneute Abweichung. Einträge anderer Herkunft für denselben Zustand (#2913, #3122)
bleiben unberührt.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BESITZER = ROOT / "docs" / "context" / "einstellungen_neu" / "elementliste_besitzer.json"


def _besitzer() -> list[dict]:
    return json.loads(BESITZER.read_text(encoding="utf-8"))["besitzer"]


def test_ac5_kein_besitzer_mit_verweis_3022():
    rest = [b.get("id") or b.get("abschnitt") or b for b in _besitzer() if b.get("verweis") == "#3022"]
    assert rest == [], f"#3022: noch {len(rest)} Besitzer-Einträge mit Verweis #3022: {rest[:5]} …"

