# doc-compliance-test
"""TDD RED — Issue #1708 Scheibe C, AC-10: Reihenfolge-Doku im
Operations-Playbook.

Spec: docs/specs/modules/fix_1708_c_tote_ablage_loeschen.md, AC-10.

Reiner Vorhandensein-Nachweis (Ausnahme laut CLAUDE.md-Testpolitik
ausdrücklich für `# doc-compliance-test` zulässig): das Playbook muss die
Reihenfolge lokal -> Staging -> Prod-Cleanup (manuell, vor Deploy) -> Deploy
mit scharfer Phase 5 nennen und auf das Cleanup-Script verweisen.

Heute ROT: der Absatz existiert noch nicht.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK = REPO_ROOT / "docs" / "reference" / "operations_playbook.md"


def test_playbook_documents_1708c_cleanup_order():
    text = PLAYBOOK.read_text(encoding="utf-8")

    assert "cleanup_1708c_dead_trips.py" in text, (
        "AC-10 verletzt: Playbook verweist nicht auf das Cleanup-Script"
    )
    assert "trips.TOT-legacy" in text or "trips" in text.lower(), (
        "AC-10 verletzt: Playbook nennt die betroffene Ablage nicht"
    )

    # Die vier Reihenfolge-Schritte müssen alle im selben Abschnitt genannt
    # sein (grobe Reihenfolge-Prüfung: jeder Marker kommt NACH dem vorigen).
    markers = ["lokal", "Staging", "Prod-Cleanup", "deploy-gregor-prod.sh"]
    positions = [text.find(m) for m in markers]
    assert all(p != -1 for p in positions), (
        f"AC-10 verletzt: nicht alle Reihenfolge-Marker gefunden: "
        f"{dict(zip(markers, positions))}"
    )
    assert positions == sorted(positions), (
        f"AC-10 verletzt: Reihenfolge-Marker stehen nicht in der richtigen "
        f"Abfolge: {dict(zip(markers, positions))}"
    )
