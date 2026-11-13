# doc-compliance-test
"""ADR-0118 (Fix-Loop Bildabgleich Runde 1, Issue #2980, Scheibe c2 von #2913).

Spec: docs/specs/modules/feat_2913_c2_seitenkopf.md — AC-29.

Die PO-Entscheidungen vom 13.11.2026 (Handy-Reiter als Text-Reiter mit Unterstrich,
Kennzahlenzeile #416 entfällt) und die Akzent-Hauptaktion „Test schicken ▾“ mit Fläche
`--g-accent-deep` weichen von ADR-0109/0110/0111 ab. Entscheidungen werden nie still
rückgängig gemacht (CLAUDE.md): neues ADR-0118, Teilablösungs-Vermerk in den drei alten
ADRs — in der Datei UND im Index docs/adr/README.md (Statusklasse „abgelöst“, siehe
tests/test_adr_index_drift.py::_status_class).

Doku-Test (liest Markdown als Daten), Marker oben.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ADR_DIR = REPO / "docs" / "adr"
README = ADR_DIR / "README.md"

ABGELOEST = ("0109", "0110", "0111")
VERMERK = re.compile(r"Teilweise abgelöst durch \[?ADR-0118", re.IGNORECASE)


def _adr(nummer: str) -> Path:
    treffer = sorted(ADR_DIR.glob(f"{nummer}-*.md"))
    assert len(treffer) == 1, f"ADR-{nummer}: erwartet genau eine Datei docs/adr/{nummer}-*.md, gefunden {[p.name for p in treffer]}"
    return treffer[0]


def _status(p: Path) -> str:
    m = re.search(r"\*\*Status:\*\*\s*(.+)", p.read_text(encoding="utf-8"))
    assert m, f"{p.name}: keine **Status:**-Zeile"
    return m.group(1).strip()


def _index_zeile(p: Path) -> str:
    zeilen = [z for z in README.read_text(encoding="utf-8").splitlines() if f"({p.name})" in z and z.startswith("|")]
    assert len(zeilen) == 1, f"docs/adr/README.md: erwartet genau eine Indexzeile mit ({p.name}), gefunden {len(zeilen)}"
    return zeilen[0]


def test_adr_0118_existiert_mit_h1_status_und_im_index():
    p = _adr("0118")
    text = p.read_text(encoding="utf-8")
    h1 = next((z for z in text.splitlines() if z.startswith("# ")), "")
    assert h1.startswith("# ADR-0118"), f"H1 von {p.name} beginnt nicht mit „# ADR-0118“: {h1!r}"
    assert re.match(r"akzeptiert", _status(p), re.IGNORECASE), f"{p.name}: Status „{_status(p)}“ statt Akzeptiert"
    zeile = _index_zeile(p)
    assert zeile.startswith("| [0118]"), f"Indexzeile beginnt nicht mit „| [0118]“: {zeile[:60]!r}"
    assert "2980" in text and "2980" in zeile, "ADR-0118 bzw. Indexzeile verweist nicht auf Issue #2980"


def test_adr_0118_nennt_die_drei_entscheidungen():
    text = _adr("0118").read_text(encoding="utf-8")
    flach = re.sub(r"\s+", " ", text)
    # 1) Handy-Reiter als Text-Reiter mit Unterstrich (statt Pillen)
    assert re.search(r"Unterstrich", flach) and re.search(r"Handy|mobil", flach, re.IGNORECASE), "ADR-0118 nennt die Handy-Reiter mit Unterstrich nicht"
    assert re.search(r"Pill", flach), "ADR-0118 nennt nicht, dass die Handy-Pillen entfallen"
    # 2) „Test schicken ▾“ als Akzent-Hauptaktion mit Fläche --g-accent-deep (bewusste Abweichung vom Mockup-Orange)
    assert "Test schicken" in flach, "ADR-0118 nennt den Knopf „Test schicken ▾“ nicht"
    assert "--g-accent-deep" in flach, "ADR-0118 nennt die Fläche --g-accent-deep nicht"
    assert re.search(r"accent", flach) and re.search(r"4,5|WCAG|AA", flach), "ADR-0118 begründet die Akzent-Fläche nicht mit dem Kontrast (WCAG-AA, 4,5:1)"
    # 3) Kennzahlenzeile #416 entfällt
    assert "#416" in flach and re.search(r"Kennzahl", flach), "ADR-0118 nennt den Wegfall der Kennzahlenzeile #416 nicht"
    # Bezug auf die teilweise abgelösten ADRs
    for n in ABGELOEST:
        assert f"ADR-{n}" in flach, f"ADR-0118 nennt das teilweise abgelöste ADR-{n} nicht"


def test_adr_0109_0110_0111_teilweise_abgeloest_in_datei_und_index():
    fehler = []
    for n in ABGELOEST:
        p = _adr(n)
        status = _status(p)
        if not VERMERK.search(status):
            fehler.append(f"{p.name}: Datei-Status „{status[:90]}“ ohne „Teilweise abgelöst durch ADR-0118“")
        spalten = [s.strip() for s in _index_zeile(p).strip("|").split("|")]
        index_status = spalten[-1] if spalten else ""
        if not VERMERK.search(index_status):
            fehler.append(f"{p.name}: Index-Status „{index_status[:90]}“ ohne „Teilweise abgelöst durch ADR-0118“")
    assert not fehler, "AC-29 Teilablösung nicht vermerkt:\n  " + "\n  ".join(fehler)
