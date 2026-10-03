"""TDD RED — Issue #2261 Teil A (A-1), AC-13: Erledigt-Vermerke der
abgeloesten Entscheidungen (Doku-Abnahme, kein Verhaltenstest).

SPEC: docs/specs/modules/feat_2261_a1_radar_vorlauf.md — AC-13, Abschnitt
"Abgeloeste Entscheidungen".

Eine dokumentierte Entscheidung wird nie still rueckgaengig gemacht: die
Schwelle 55 aus `fix_2009_nowcast_vorlauf` und der Verweis darauf in
`feat_2051_s3_reichweite_und_guete` tragen einen Abloesungsvermerk mit
Verweis auf diese Spec; der Begruendungskommentar an
`RADAR_ONSET_THRESHOLD_MIN` nennt den PO-Entscheid A-1 statt der
55-Begruendung.

Pfade relativ zu DIESER Testdatei (nie ueber den Hauptrepo-Pfad).
"""
# doc-compliance-test
from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SPECS = _REPO / "docs" / "specs" / "modules"
_NEUE_SPEC = "feat_2261_a1_radar_vorlauf"


def _lesen(pfad: Path) -> str:
    assert pfad.is_file(), f"Datei fehlt: {pfad}"
    return pfad.read_text(encoding="utf-8")  # doc-compliance-test


def test_fix_2009_traegt_abloesungsvermerk():
    """AC-13: `fix_2009_nowcast_vorlauf.md` traegt einen Abloesungsvermerk
    ("abgeloest durch feat_2261_a1_radar_vorlauf", PO-Entscheid A-1).

    RED heute: kein Vermerk."""
    # doc-compliance-test
    text = _lesen(_SPECS / "fix_2009_nowcast_vorlauf.md")
    assert _NEUE_SPEC in text, (
        f"AC-13: fix_2009_nowcast_vorlauf.md verweist nicht auf {_NEUE_SPEC}."
    )
    # Vermerk und Verweis gehoeren zusammen (hoechstens 300 Zeichen Abstand),
    # nicht irgendwo verstreut im Dokument.
    assert re.search(
        rf"abgel(ö|oe)st[\s\S]{{0,300}}{_NEUE_SPEC}|{_NEUE_SPEC}[\s\S]{{0,300}}abgel(ö|oe)st",
        text, re.IGNORECASE,
    ), (
        "AC-13: fix_2009_nowcast_vorlauf.md traegt keinen Abloesungsvermerk "
        f"('abgelöst durch {_NEUE_SPEC}')."
    )


def test_feat_2051_s3_verweist_auf_neue_schwelle():
    """AC-13: `feat_2051_s3_reichweite_und_guete.md` (bisher Verweis auf
    Schwelle 55 neben Guetegrenze 60) verweist auf diese Spec.

    RED heute: kein Verweis."""
    # doc-compliance-test
    text = _lesen(_SPECS / "feat_2051_s3_reichweite_und_guete.md")
    assert _NEUE_SPEC in text, (
        f"AC-13: feat_2051_s3_reichweite_und_guete.md verweist nicht auf "
        f"{_NEUE_SPEC} (Ausloeseschwelle = Horizont 180, Guetegrenze bleibt 60)."
    )


def test_radar_service_kommentar_nennt_a1_statt_55_begruendung():
    """AC-13: der Begruendungskommentar ueber `RADAR_ONSET_THRESHOLD_MIN`
    nennt den PO-Entscheid A-1 und nicht mehr die 55-Begruendung
    ("55 liegt knapp oberhalb von 53 …", "schliesst 68+ aus").

    Geprueft wird ein Fenster OBERHALB der Zuweisung (nicht nur die direkt
    anschliessenden Kommentarzeilen) -- eine dazwischen eingefuegte neue
    Konstante (z. B. `RADAR_MEASURE_OFFSET_MIN`) verschiebt den Block sonst.

    RED heute: Kommentar traegt die 55-Begruendung, kein A-1."""
    # doc-compliance-test
    zeilen = _lesen(_REPO / "src" / "services" / "radar_service.py").splitlines()  # doc-compliance-test
    idx = next(
        (i for i, z in enumerate(zeilen)
         if re.match(r"^RADAR_ONSET_THRESHOLD_MIN\s*=", z)),
        None,
    )
    assert idx is not None, "Zuweisung RADAR_ONSET_THRESHOLD_MIN nicht gefunden."
    fenster = "\n".join(zeilen[max(0, idx - 45): idx + 1])
    assert "A-1" in fenster, (
        f"AC-13: der Begruendungskommentar ueber RADAR_ONSET_THRESHOLD_MIN "
        f"nennt den PO-Entscheid A-1 nicht.\n{fenster}"
    )
    for alt in ("55 liegt knapp", "68+"):
        assert alt not in fenster, (
            f"AC-13: der Kommentar traegt noch die abgeloeste "
            f"55-Begruendung ('{alt}').\n{fenster}"
        )
