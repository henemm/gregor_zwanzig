# doc-compliance-test
"""Drift-Wächter: docs/adr/README.md-Index vs. ADR-Dateien (Issue #1343).

Der ADR-Index ist vor #1343 zweimal nachweislich gedriftet (issue_1165:
fehlende/doppelte Nummern; 2026-07: ADR-0002 in der Datei Superseded, im Index
„Akzeptiert"). Dieser Test erzwingt:

1. Jede Datei docs/adr/NNNN-*.md ist im README-Index verlinkt.
2. Der Index-Status stimmt mit der **Status:**-Zeile der Datei überein
   (Klassen-Abgleich: akzeptiert / abgelöst / vorgeschlagen / zurückgezogen).

Rot heißt IMMER: Index bzw. Datei nachziehen — nie diesen Test aufweichen.

Regel-Budget: Prüfdatum 2026-10-20 — kein nachweisbarer Fang bis dahin → Rückbau.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ADR_DIR = REPO / "docs" / "adr"
README = ADR_DIR / "README.md"


def _status_class(status_text: str) -> str:
    # Nur der Status-Präfix zählt — Zusätze nach "—" oder "(" (z. B.
    # "Akzeptiert — präzisiert durch ADR-0015") dürfen nicht umklassifizieren.
    t = re.split(r"[—(]", status_text, maxsplit=1)[0].lower()
    if "abgelöst" in t or "superseded" in t or "abgeloest" in t:
        return "abgelöst"
    if "zurückgezogen" in t or "zurueckgezogen" in t:
        return "zurückgezogen"
    if "vorgeschlagen" in t:
        return "vorgeschlagen"
    if "akzeptiert" in t:
        return "akzeptiert"
    return f"unbekannt({status_text[:40]})"


def _adr_files() -> list[Path]:
    return sorted(p for p in ADR_DIR.glob("[0-9][0-9][0-9][0-9]-*.md"))


def test_every_adr_file_is_in_index():
    index = README.read_text(encoding="utf-8")
    missing = [p.name for p in _adr_files() if f"({p.name})" not in index]
    assert not missing, f"ADR-Dateien ohne Index-Zeile in docs/adr/README.md: {missing}"


def test_index_status_matches_file_status():
    index = README.read_text(encoding="utf-8")
    mismatches = []
    for p in _adr_files():
        m_file = re.search(r"\*\*Status:\*\*\s*(.+)", p.read_text(encoding="utf-8"))
        if not m_file:
            mismatches.append(f"{p.name}: keine **Status:**-Zeile in der Datei")
            continue
        m_index = re.search(
            r"\(" + re.escape(p.name) + r"\)[^|]*\|[^|]*\|\s*([^|\n]+)", index
        )
        if not m_index:
            continue  # von test_every_adr_file_is_in_index gemeldet
        file_cls = _status_class(m_file.group(1))
        index_cls = _status_class(m_index.group(1))
        if file_cls != index_cls:
            mismatches.append(f"{p.name}: Datei={file_cls!r} vs. Index={index_cls!r}")
    assert not mismatches, (
        "Status-Drift zwischen ADR-Dateien und docs/adr/README.md-Index:\n  "
        + "\n  ".join(mismatches)
    )
