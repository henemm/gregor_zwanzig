#!/usr/bin/env python3
"""Soll/Ist-Bild für den PO (#3037, AC-5): Mockup links, Staging rechts, beschriftet, unverzerrt.

Spec: docs/specs/modules/feat_3037_was_steht_wo_abnahme.md (Implementation Details Nr. 7).

Beide Bilder bleiben in Originalgröße; das kürzere wird mit hellem Hintergrund aufgefüllt, nie gestreckt.
Unterschiedliche Breiten brechen klar ab (keine stille Skalierung).

Kommandozeile:
    uv run python scripts/soll_ist_bild.py <bildordner> <zielordner>
Für jedes ``staging-<ctx>-<lang>-<breite>.png`` im Bildordner wird das Gegenbild
``mockup-<ctx>-de-<breite>.png`` (Mockup nur Deutsch) gesucht und ``soll-ist-<ctx>-<lang>-<breite>.png``
in den Zielordner geschrieben. Fehlt ein Mockup, steht das auf stderr und der Lauf endet mit Exit 1.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HINTERGRUND = (246, 244, 238)
SCHRIFT = (26, 26, 24)
ABSTAND = 16
KOPF = 40

STAGING_NAME = re.compile(r"^staging-(?P<ctx>[a-z0-9]+)-(?P<lang>[a-z]{2})-(?P<breite>\d+)\.png$")


def beschriftung(kontext: str, breite: int, sprache: str) -> tuple[str, str]:
    """Beschriftung links (Soll) und rechts (Ist) mit Kontext, Breite und Sprache (groß)."""
    rest = f"{kontext} · {breite} px · {sprache.upper()}"
    return f"Soll (Mockup) · {rest}", f"Ist (Staging) · {rest}"


def _schrift() -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    for name in ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, 18)
        except OSError:
            continue
    return ImageFont.load_default()


def soll_ist(mockup_png: Path | str, staging_png: Path | str, *, kontext: str, breite: int, sprache: str) -> Image.Image:
    """Setzt Mockup (links) und Staging (rechts) in Originalgröße nebeneinander, mit Kopfzeile darüber."""
    with Image.open(mockup_png) as m_roh, Image.open(staging_png) as s_roh:
        mockup = m_roh.convert("RGB")
        staging = s_roh.convert("RGB")
    if mockup.width != staging.width:
        raise ValueError(
            f"Breiten verschieden: Mockup {mockup.width} px, Staging {staging.width} px — keine Skalierung"
        )
    hoehe = max(mockup.height, staging.height)
    bild = Image.new("RGB", (mockup.width + ABSTAND + staging.width, KOPF + hoehe), HINTERGRUND)
    bild.paste(mockup, (0, KOPF))
    rechts_x = mockup.width + ABSTAND
    bild.paste(staging, (rechts_x, KOPF))
    links, rechts = beschriftung(kontext, breite, sprache)
    zeichnen = ImageDraw.Draw(bild)
    schrift = _schrift()
    zeichnen.text((8, 10), links, fill=SCHRIFT, font=schrift)
    zeichnen.text((rechts_x + 8, 10), rechts, fill=SCHRIFT, font=schrift)
    return bild


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Aufruf: soll_ist_bild.py <bildordner> <zielordner>", file=sys.stderr)
        return 2
    quelle, ziel = Path(argv[0]), Path(argv[1])
    ziel.mkdir(parents=True, exist_ok=True)
    fehler = 0
    for staging in sorted(quelle.glob("staging-*.png")):
        treffer = STAGING_NAME.match(staging.name)
        if not treffer:
            continue
        ctx, lang, breite = treffer["ctx"], treffer["lang"], int(treffer["breite"])
        mockup = quelle / f"mockup-{ctx}-de-{breite}.png"
        if not mockup.exists():
            print(f"Mockup fehlt für {staging.name}: {mockup.name}", file=sys.stderr)
            fehler += 1
            continue
        bild = soll_ist(mockup, staging, kontext=ctx, breite=breite, sprache=lang)
        bild.save(ziel / f"soll-ist-{ctx}-{lang}-{breite}.png")
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
