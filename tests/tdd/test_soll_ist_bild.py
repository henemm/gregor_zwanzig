"""#3037 AC-5: Soll/Ist-Bild für den PO — Mockup links, Staging rechts, beschriftet, unverzerrt.

Kern-Schicht: echte PNG-Dateien über PIL, kein Netz, keine Mocks.
Spec: docs/specs/modules/feat_3037_was_steht_wo_abnahme.md
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

ROT = (220, 30, 30)
BLAU = (30, 60, 220)


def _png(pfad: Path, breite: int, hoehe: int, farbe: tuple[int, int, int]) -> Path:
    Image.new("RGB", (breite, hoehe), farbe).save(pfad)
    return pfad


def test_mockup_links_staging_rechts_unverzerrt_bei_unterschiedlicher_hoehe(tmp_path: Path) -> None:
    """GIVEN Mockup 390×600 (rot) und Staging 390×900 (blau) WHEN zusammengesetzt
    THEN links liegt das Mockup in Originalgröße, rechts das Staging-Bild in Originalgröße;
    der Rest der kürzeren Seite ist Hintergrund, nicht gestrecktes Bild."""
    from soll_ist_bild import soll_ist

    m = _png(tmp_path / "m.png", 390, 600, ROT)
    s = _png(tmp_path / "s.png", 390, 900, BLAU)
    bild = soll_ist(m, s, kontext="orte", breite=390, sprache="en")

    assert bild.width >= 2 * 390
    assert bild.height >= 900
    # Kopfzeile oberhalb der Bilder: Bildinhalt beginnt erst darunter.
    kopf = bild.height - 900
    assert kopf > 0, "Beschriftung braucht eine eigene Kopfzeile"
    links_mitte = bild.getpixel((195, kopf + 300))
    rechts_mitte = bild.getpixel((bild.width - 195, kopf + 450))
    assert links_mitte[:3] == ROT, f"links nicht das Mockup: {links_mitte}"
    assert rechts_mitte[:3] == BLAU, f"rechts nicht Staging: {rechts_mitte}"
    # Unterhalb der Mockup-Höhe links: kein Rot mehr (nicht gestreckt).
    unter_mockup = bild.getpixel((195, kopf + 750))
    assert unter_mockup[:3] != ROT, "Mockup wurde auf Staging-Höhe gestreckt"
    # Staging-Bild rechts reicht bis unten (volle Höhe, nicht gestaucht).
    assert bild.getpixel((bild.width - 195, kopf + 899))[:3] == BLAU


def test_beschriftung_nennt_soll_ist_kontext_breite_sprache() -> None:
    """GIVEN Kontext, Breite, Sprache WHEN die Beschriftung gebildet wird
    THEN enthält sie „Soll (Mockup)“, „Ist (Staging)“, den Kontext, die Breite und die Sprache."""
    from soll_ist_bild import beschriftung

    links, rechts = beschriftung(kontext="ort1", breite=1280, sprache="de")
    assert links.startswith("Soll (Mockup)")
    assert rechts.startswith("Ist (Staging)")
    for teil in ("ort1", "1280", "DE"):
        assert teil in links and teil in rechts, (teil, links, rechts)


def test_unterschiedliche_breite_bricht_klar_ab(tmp_path: Path) -> None:
    """GIVEN Mockup 1280 breit und Staging 390 breit WHEN zusammengesetzt
    THEN klarer Abbruch (ValueError mit beiden Breiten) statt stiller Skalierung."""
    from soll_ist_bild import soll_ist

    m = _png(tmp_path / "m.png", 1280, 100, ROT)
    s = _png(tmp_path / "s.png", 390, 100, BLAU)
    with pytest.raises(ValueError, match=r"1280.*390|390.*1280"):
        soll_ist(m, s, kontext="trip", breite=1280, sprache="de")


def test_kommandozeile_schreibt_je_kombination_ein_png(tmp_path: Path) -> None:
    """GIVEN ein Bildordner mit mockup-<ctx>-de-<breite>.png und staging-<ctx>-<lang>-<breite>.png
    WHEN das Skript über die Kommandozeile läuft THEN entsteht je Staging-Bild ein soll-ist-<ctx>-<lang>-<breite>.png."""
    ordner = tmp_path / "bilder"
    ordner.mkdir()
    _png(ordner / "mockup-orte-de-390.png", 390, 50, ROT)
    _png(ordner / "staging-orte-de-390.png", 390, 60, BLAU)
    _png(ordner / "staging-orte-en-390.png", 390, 70, BLAU)
    ziel = tmp_path / "aus"
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "soll_ist_bild.py"), str(ordner), str(ziel)],
        capture_output=True, text=True, check=False,
    )
    assert r.returncode == 0, r.stderr
    erzeugt = sorted(p.name for p in ziel.glob("*.png"))
    assert erzeugt == ["soll-ist-orte-de-390.png", "soll-ist-orte-en-390.png"], erzeugt
