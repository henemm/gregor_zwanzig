# doc-compliance-test
"""Doku-Wächter Issue #2390, AC-7 (Spec fix_2390_e2e_auth_gueltigkeitsprobe.md).

Given docs/reference/gates_und_ratschen.md beschreibt das Anmelde-Verhalten
von frontend/e2e/global.setup.ts / When ein Leser den Satz zur Anmeldung liest /
Then steht dort, dass sich das Setup neu anmeldet, wenn admin.json fehlt,
abgelaufen ist ODER vom laufenden Server abgelehnt wird.

Warum ein Dateiinhalt-Test: das Prüfobjekt IST die Dokumentation — der alte
Satz („nur einloggt, wenn admin.json fehlt/abgelaufen") würde nach dem Fix den
Code falsch beschreiben und die nächste Sitzung auf den falschen Stand setzen.

Pfade relativ zu dieser Datei (Pfadregel #1409).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "reference" / "gates_und_ratschen.md"


def test_setup_satz_nennt_ablehnung_durch_server() -> None:
    text = re.sub(r"\s+", " ", DOC.read_text(encoding="utf-8"))
    idx = text.find("admin.json` fehlt/abgelaufen")
    assert idx != -1, "Satz zur Setup-Anmeldung in gates_und_ratschen.md nicht gefunden"
    umgebung = text[idx : idx + 200]
    assert re.search(r"vom laufenden Server abgelehnt", umgebung), (
        "AC-7: Der Satz muss nennen, dass sich das Setup auch neu anmeldet, "
        "wenn der laufende Server den Anmeldezustand ablehnt."
    )
