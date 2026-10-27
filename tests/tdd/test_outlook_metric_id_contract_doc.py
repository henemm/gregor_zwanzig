"""RED — #1848 A2: die Schnittstellen-Referenz beschreibt das Speicherformat
des Ausblicks richtig.

SPEC: docs/specs/modules/feat_1848_a2_ausblick_kennungen.md — AC-11
KONTEXT: docs/context/feat-1848-a2-outlook-kennungen.md — R-A2-5, R-A2-8

Warum dieser Test noetig ist: ``test_api_contract_drift.py`` bewacht die
Ausblick-Zeile NICHT (kein ``outlook``-Treffer, R-A2-8). Der Vertragstext
faellt also nicht von selbst auf, wenn er dem Code widerspricht — und er tut
es bereits heute an zwei Stellen (R-A2-5): er nennt
``CompareOutlookLayoutControls.svelte`` als einzigen Schreiber und behauptet
'der Trip bekommt keine Auswahlfläche', obwohl der Trip seit ADR-0055
(#1720 S1) ebenfalls schreibt.

# doc-compliance-test — hier ist der DOKUMENTTEXT der Pruefling, nicht
# Programmverhalten. Ein Dateiinhalt-Check ist deshalb der Sache angemessen
# (CLAUDE.md, Ausnahme-Regel).
"""
from __future__ import annotations

from pathlib import Path

# Pfadregel #1409: relativ zur eigenen Testdatei, nicht zum Hauptrepo.
VERTRAG = Path(__file__).resolve().parents[2] / "docs" / "reference" / "api_contract.md"


def _outlook_absatz() -> str:
    zeilen = [z for z in VERTRAG.read_text(encoding="utf-8").splitlines()
              if z.lstrip().startswith("- `outlook_metrics`")]
    assert len(zeilen) == 1, (
        f"In {VERTRAG.name} steht {len(zeilen)} Mal eine `outlook_metrics`-"
        "Zeile — erwartet ist genau eine (Vertragstext)."
    )
    return zeilen[0]


def test_ac11_vertrag_nennt_kennungsformat_altform_und_den_trip_als_schreiber():
    """AC-11: Given die Schnittstellen-Referenz beschreibt das Speicherformat
    des Ausblicks / When A2 ausgeliefert ist / Then nennt sie das
    Kennungsformat, benennt die Altform als weiterhin lesbar und fuehrt den
    Trip neben dem Ortsvergleich als schreibende Flaeche auf.
    """
    absatz = _outlook_absatz()

    assert "KEIN Altformat" not in absatz, (
        "Der Vertrag behauptet weiterhin 'KEIN Altformat'. Nach A2 liest der "
        "Aufloeser die Paar-Altform DAUERHAFT weiter — sie ist keine "
        "Uebergangskruecke, sondern Bestandsdaten-Vertraeglichkeit (AC-11)."
    )
    assert "keine Auswahlfläche" not in absatz, (
        "Der Vertrag behauptet weiterhin, der Trip bekomme keine "
        "Auswahlfläche. Seit ADR-0055 (#1720 S1) schreibt der Trip ebenfalls "
        "`outlook_metrics` (AC-11, R-A2-5)."
    )
    assert "ausschließlich `[{\"metric_id\"" not in absatz, (
        "Der Vertrag schreibt weiterhin das Paar-Objekt als ausschliessliche "
        "Elementform fest (AC-11)."
    )

    assert "Trip" in absatz, (
        "Der Vertrag nennt den Trip nicht als schreibende Flaeche neben dem "
        f"Ortsvergleich (AC-11). Zeile:\n{absatz}"
    )
    assert any(marke in absatz for marke in ("Altform", "Altformat", "Bestandsform")), (
        "Der Vertrag benennt die Paar-Altform nicht als weiterhin lesbar "
        f"(AC-11). Zeile:\n{absatz}"
    )
    assert '`["temperature"' in absatz or "`string[]`" in absatz, (
        "Der Vertrag nennt das Kennungsformat nicht — erwartet ist die "
        "Elementform als reine Zeichenkette (z. B. `[\"temperature\", "
        f"\"gust\"]` bzw. `string[]`) (AC-11). Zeile:\n{absatz}"
    )
