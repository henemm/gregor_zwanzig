"""Inventar-Drift-Waechter Python <-> Go (Issue #1337, Scheibe Go-Prozess).

Spec: docs/specs/modules/egress_guard_go.md ("## Test Plan" Test 10; AC-10).

Der Egress-Waechter existiert in zwei Prozessen — Python (`src/app/egress_guard.py`)
und Go (`internal/egress/inventory.go`). Zwei Listen driften auseinander; genau
diese Drift ist die Kernursache von #1337 ("wer 14 Tueren einzeln bewacht,
vergisst irgendwann eine"). Dieser Test erzwingt Deckungsgleichheit Host fuer
Host — Vorbild: ``tests/test_adr_index_drift.py``.

Gelesen wird die Go-Quelle als Text (kein Go-Toolchain-Aufruf noetig), die
Python-Seite ueber den echten Import — damit kann die Python-Liste nicht durch
einen Parser-Fehler stillschweigend falsch gelesen werden.

Erwartung in dieser Phase (TDD RED): ``internal/egress/inventory.go`` existiert
noch nicht -> ROT.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.egress_guard import INVENTORY, IsolationKind

REPO_ROOT = Path(__file__).resolve().parents[1]
GO_INVENTORY = REPO_ROOT / "internal" / "egress" / "inventory.go"

# Zeilenform in der Go-Quelle:  "api.open-meteo.com": TestAccess,
_GO_ENTRY = re.compile(r'"(?P<host>[a-z0-9.\-]+)"\s*:\s*(?P<kind>TestAccess|Blocked)\s*,')

_GO_KIND_TO_PY = {
    "TestAccess": IsolationKind.TEST_ACCESS,
    "Blocked": IsolationKind.BLOCKED,
}


def _parse_go_inventory(text: str) -> dict[str, IsolationKind]:
    """Parst die Go-Inventar-Eintraege aus Quelltext.

    F002: Jede Zeile wird am ERSTEN ``//`` abgeschnitten und nur der Teil DAVOR
    gegen den Eintrags-Regex geprueft. Damit zaehlt eine voll auskommentierte
    Zeile (``// "host": TestAccess,``) NICHT als Deklaration (der Teil vor
    ``//`` ist leer), waehrend ein legitimer Inline-Kommentar hinter einem
    echten Eintrag (``"host": TestAccess, // Notiz``) weiterhin matcht.
    """
    entries: dict[str, IsolationKind] = {}
    for line in text.splitlines():
        code = line.split("//", 1)[0]
        m = _GO_ENTRY.search(code)
        if m:
            entries[m.group("host")] = _GO_KIND_TO_PY[m.group("kind")]
    return entries


def _read_go_inventory() -> dict[str, IsolationKind]:
    assert GO_INVENTORY.exists(), (
        f"Go-Inventar fehlt: {GO_INVENTORY.relative_to(REPO_ROOT)} — der Go-Dienst "
        "haette dann keinen Egress-Waechter (Issue #1337)."
    )
    entries = _parse_go_inventory(GO_INVENTORY.read_text(encoding="utf-8"))
    assert entries, f"Keine Inventar-Eintraege in {GO_INVENTORY.name} gefunden."
    return entries


def test_inventories_are_identical():
    """GIVEN je eine Inventar-Quelle in Python und in Go
    WHEN ein Host nur in einer Quelle steht oder unterschiedlich eingestuft ist
    THEN schlaegt dieser Test rot und benennt den abweichenden Host.
    """
    go_inventory = _read_go_inventory()

    only_python = sorted(set(INVENTORY) - set(go_inventory))
    only_go = sorted(set(go_inventory) - set(INVENTORY))
    different = sorted(
        host
        for host in set(INVENTORY) & set(go_inventory)
        if INVENTORY[host] is not go_inventory[host]
    )

    assert not only_python, f"Nur im Python-Inventar deklariert: {only_python}"
    assert not only_go, f"Nur im Go-Inventar deklariert: {only_go}"
    assert not different, f"Unterschiedliche Einstufung Python vs. Go: {different}"


def test_parser_ignores_commented_out_lines():
    """GIVEN eine auskommentierte Inventarzeile und ein Inline-Kommentar
    WHEN der Go-Quelltext geparst wird
    THEN zaehlt nur der echte Eintrag als deklariert (F002 — sonst bliebe der
    Drift-Test gruen, obwohl der Go-Guard-Test real rot wuerde, AC-10-Verstoss).
    """
    text = (
        'var Inventory = map[string]Kind{\n'
        '\t// "auskommentiert.example.com": TestAccess,\n'
        '\t"echt.example.com": TestAccess, // Notiz hinter echtem Eintrag\n'
        '}\n'
    )
    parsed = _parse_go_inventory(text)

    assert "auskommentiert.example.com" not in parsed, (
        "Auskommentierte Zeile wurde faelschlich als Deklaration gezaehlt (F002)."
    )
    assert parsed.get("echt.example.com") is IsolationKind.TEST_ACCESS, (
        "Eintrag mit legitimem Inline-Kommentar wurde nicht erkannt."
    )


def test_go_inventory_declares_go_only_hosts():
    """GIVEN der Go-Dienst ruft Dienste, die der Python-Prozess nie ruft
    WHEN das gemeinsame Inventar geprueft wird
    THEN sind auch diese Hosts deklariert (sonst legt der Tripwire Staging lahm).
    """
    go_only_call_sites = {
        "nominatim.openstreetmap.org",
        "api.open-elevation.com",
        "www.komoot.com",
        "uptime.betterstack.com",
    }
    missing = sorted(go_only_call_sites - set(INVENTORY))
    assert not missing, f"Im Go-Dienst gerufen, aber nirgends deklariert: {missing}"
