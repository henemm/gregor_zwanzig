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


# ── Fix-Loop 1 (Adversary F001/F002): gezeichnete Beschriftung, CLI-Parameter, Abstand, Exit-Code ──

HELL_SCHWELLE = 600  # Summe R+G+B: Hintergrund (246,244,238) = 728, Schrift (26,26,24) = 76


def _dunkle_pixel(bild: Image.Image, x0: int, x1: int, y0: int, y1: int) -> int:
    """Zahl der dunklen Pixel (Schrift) im Rechteck [x0, x1) × [y0, y1)."""
    return sum(
        1
        for x in range(x0, x1)
        for y in range(y0, y1)
        if sum(bild.getpixel((x, y))[:3]) < HELL_SCHWELLE
    )


def _gleich(a: Image.Image, b: Image.Image) -> bool:
    from PIL import ImageChops

    return a.size == b.size and ImageChops.difference(a.convert("RGB"), b.convert("RGB")).getbbox() is None


def test_kopfzeile_zeigt_beschriftung_links_und_rechts_dunkel_auf_hell(tmp_path: Path) -> None:
    """GIVEN Mockup und Staging je 1280 breit WHEN zusammengesetzt
    THEN steht über JEDEM der beiden Bilder gezeichnete Schrift (dunkle Pixel auf hellem Kopf),
    links über dem Mockup, rechts über dem Staging-Bild — fehlt eine der beiden Beschriftungen, ist der Kopf dort leer."""
    from soll_ist_bild import soll_ist

    m = _png(tmp_path / "m.png", 1280, 50, ROT)
    s = _png(tmp_path / "s.png", 1280, 50, BLAU)
    bild = soll_ist(m, s, kontext="orte", breite=1280, sprache="de")
    kopf = bild.height - 50
    rechts_x = bild.width - 1280
    # Kopf ist hell (Hintergrund), nicht Bildinhalt.
    assert sum(bild.getpixel((1270, 2))[:3]) >= HELL_SCHWELLE, "Kopfzeile nicht hell"
    links = _dunkle_pixel(bild, 0, 1280, 0, kopf)
    rechts = _dunkle_pixel(bild, rechts_x, bild.width, 0, kopf)
    assert links > 50, f"Kopfzeile links ohne Beschriftung ({links} dunkle Pixel)"
    assert rechts > 50, f"Kopfzeile rechts ohne Beschriftung ({rechts} dunkle Pixel)"


def test_beschriftung_links_und_rechts_verschieden_soll_und_ist(tmp_path: Path) -> None:
    """GIVEN dasselbe Bild links und rechts WHEN zusammengesetzt
    THEN unterscheiden sich die beiden Kopfhälften (links „Soll (Mockup)“, rechts „Ist (Staging)“)."""
    from soll_ist_bild import soll_ist

    m = _png(tmp_path / "m.png", 1280, 20, ROT)
    s = _png(tmp_path / "s.png", 1280, 20, ROT)
    bild = soll_ist(m, s, kontext="orte", breite=1280, sprache="de")
    kopf = bild.height - 20
    rechts_x = bild.width - 1280
    links = bild.crop((0, 0, 1280, kopf))
    rechts = bild.crop((rechts_x, 0, bild.width, kopf))
    assert not _gleich(links, rechts), "linke und rechte Beschriftung identisch"


def test_mockup_hoeher_als_staging_staging_wird_nicht_gestreckt(tmp_path: Path) -> None:
    """GIVEN Mockup 390×900 (rot) und Staging 390×600 (blau) WHEN zusammengesetzt
    THEN reicht das Mockup links bis unten, das Staging-Bild rechts endet bei 600 px (darunter Hintergrund)."""
    from soll_ist_bild import soll_ist

    m = _png(tmp_path / "m.png", 390, 900, ROT)
    s = _png(tmp_path / "s.png", 390, 600, BLAU)
    bild = soll_ist(m, s, kontext="ort1", breite=390, sprache="de")
    kopf = bild.height - 900
    assert kopf > 0
    assert bild.getpixel((195, kopf + 899))[:3] == ROT, "Mockup nicht in voller Höhe"
    assert bild.getpixel((bild.width - 195, kopf + 599))[:3] == BLAU, "Staging nicht in voller Höhe"
    unter_staging = bild.getpixel((bild.width - 195, kopf + 750))
    assert unter_staging[:3] != BLAU, "Staging-Bild wurde auf Mockup-Höhe gestreckt"


def test_abstand_zwischen_beiden_bildern_ist_hintergrund(tmp_path: Path) -> None:
    """GIVEN Mockup und Staging je 390 breit WHEN zusammengesetzt
    THEN liegt zwischen beiden Bildern eine Hintergrundspalte (die Bilder stoßen nicht aneinander)."""
    from soll_ist_bild import soll_ist

    m = _png(tmp_path / "m.png", 390, 300, ROT)
    s = _png(tmp_path / "s.png", 390, 300, BLAU)
    bild = soll_ist(m, s, kontext="orte", breite=390, sprache="de")
    kopf = bild.height - 300
    assert bild.width > 2 * 390, f"kein Abstand: Gesamtbreite {bild.width}"
    for x in range(390, bild.width - 390):
        p = bild.getpixel((x, kopf + 150))[:3]
        assert p not in (ROT, BLAU), f"Spalte {x} im Abstand trägt Bildinhalt {p}"
        assert sum(p) >= HELL_SCHWELLE, f"Abstand bei x={x} nicht hell: {p}"


def test_kommandozeile_uebergibt_kontext_breite_sprache_pixelgleich(tmp_path: Path) -> None:
    """GIVEN staging-ort1-en-390.png und mockup-ort1-de-390.png WHEN das Skript über die Kommandozeile läuft
    THEN ist soll-ist-ort1-en-390.png pixelgleich mit soll_ist(kontext="ort1", breite=390, sprache="en")
    und verschieden von einem Bild mit vertauschten oder falschen Parametern."""
    from soll_ist_bild import soll_ist

    ordner = tmp_path / "bilder"
    ordner.mkdir()
    m = _png(ordner / "mockup-ort1-de-390.png", 390, 40, ROT)
    s = _png(ordner / "staging-ort1-en-390.png", 390, 40, BLAU)
    ziel = tmp_path / "aus"
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "soll_ist_bild.py"), str(ordner), str(ziel)],
        capture_output=True, text=True, check=False,
    )
    assert r.returncode == 0, r.stderr
    with Image.open(ziel / "soll-ist-ort1-en-390.png") as roh:
        cli = roh.convert("RGB")
    erwartet = soll_ist(m, s, kontext="ort1", breite=390, sprache="en")
    assert _gleich(cli, erwartet), "Kommandozeile übergibt Kontext/Breite/Sprache anders als erwartet"
    # Gegenprobe: falsche Parameter ergeben ein anderes Bild (der Vergleich ist scharf).
    for falsch in (
        dict(kontext="en", breite=390, sprache="ort1"),
        dict(kontext="ort1", breite=1280, sprache="en"),
        dict(kontext="ort1", breite=390, sprache="de"),
    ):
        assert not _gleich(cli, soll_ist(m, s, **falsch)), falsch


def test_kommandozeile_fehlendes_mockup_exit_1_mit_meldung(tmp_path: Path) -> None:
    """GIVEN ein Staging-Bild ohne passendes Mockup WHEN das Skript läuft
    THEN endet es mit Exit 1 und nennt das fehlende Mockup auf stderr."""
    ordner = tmp_path / "bilder"
    ordner.mkdir()
    _png(ordner / "staging-trip-de-1280.png", 1280, 40, BLAU)
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "soll_ist_bild.py"), str(ordner), str(tmp_path / "aus")],
        capture_output=True, text=True, check=False,
    )
    assert r.returncode == 1, (r.returncode, r.stderr)
    assert "mockup-trip-de-1280.png" in r.stderr, r.stderr
    assert "staging-trip-de-1280.png" in r.stderr, r.stderr
