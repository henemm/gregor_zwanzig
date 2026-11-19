# doc-compliance-test
"""AC-6 (#3158): Die Doku der Netzsperre beschreibt den Hoehen-Nachschlag im
Handler-Paket als Lauf gegen einen lokalen Fixture-Server, nicht mehr als
geduldete Ausnahme."""

from pathlib import Path

DOKU = Path(__file__).resolve().parent.parent / "docs" / "reference" / "gates_und_ratschen.md"


def _netzsperre_absatz() -> str:
    text = DOKU.read_text(encoding="utf-8")
    start = text.index("**Netzfreiheit der Go-Kern-Tests")
    ende = text.index("\n\n", start)
    return text[start:ende]


def test_netzsperre_absatz_verweist_auf_hoehen_fixture():
    absatz = _netzsperre_absatz()
    assert "hoehenDienstAuf" in absatz
    assert "Fixture" in absatz


def test_netzsperre_absatz_ohne_duldung_des_hoehen_nachschlags():
    absatz = _netzsperre_absatz()
    assert "Duldung, Folgebefund #3158" not in absatz
    assert "gilt dort als erwartet abgelehnt" not in absatz
